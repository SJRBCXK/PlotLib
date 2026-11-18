"""
测试对象：src/plotlib/plot_common.py 的 plan_figures —— 分组绘图计划（STRUCTURE_REVIEW 步骤 6.1）

plan_figures 只做「决定」，不碰任何绘图库：画几张图、每张图有哪些曲线、每条曲线的数据 / 标签 / 颜色 / 样式。
两个后端（matplotlib、Plotly）照着同一份计划画，分组规则只写这一次。

规则（与现在的 group_plotter 一致，这一步不改行为）：
  - 不分组：一张 'main' 图，全部样品按样品号排序，没有分组样式；
  - 分离模式：每个分组一张图，key 为分组名；同一样品可出现在多张图里；颜色按样品；
  - 合并模式：一张 'main' 图；同一样品只画一次，归第一个包含它的分组（先到先得，书写顺序即优先级）；
    同组的线统一用组首色（该组写在第一位的样品的色带位置，只看本组配置，与其他分组无关）；
  - 分组写了的样式按标准写法原样带入 style，翻译留给后端；颜色存色带位置，不存具体颜色值。

数据来自 conftest.py 的 eis_dataset：3 个样品，色带位置 0、1/3、2/3；
通道 0 是频率 [1, 10, 100]，通道 1 是 Zs'，通道 2 是 Zs''（负数）。
"""
import pytest

from plotlib.group import Group


def plan(dataset, config=None, **kwargs):
    """以通道 0 为 X、通道 1 为 Y 生成计划；config 每次新建（Group 会原地格式化传入的配置）。"""
    from plotlib.plot_common import plan_figures

    groups = Group(dataset, config or {})
    kwargs.setdefault('channel_x', 0)
    kwargs.setdefault('channel_y', 1)
    return plan_figures(dataset, groups, **kwargs)


def overlap_config():
    """样品 1 同时属于 A、B 两组；只有 A 写了线型。"""
    return {
        'A': {'num': [0, 1], 'linestyle': 'dash'},
        'B': {'num': [1, 2]},
    }


def samples(figure):
    return [curve.sample_idx for curve in figure.curves]


def positions(figure):
    return [curve.color_position for curve in figure.curves]


# ──────────────────────────────────────────────
# 三种情况：不分组 / 分离 / 合并
# ──────────────────────────────────────────────
def test_no_groups_one_main_figure(eis_dataset):
    """不分组：一张 'main' 图，全部样品，颜色按样品，没有分组名和样式。"""
    figures = plan(eis_dataset)

    assert [f.key for f in figures] == ['main']
    main = figures[0]
    assert samples(main) == [0, 1, 2]
    assert positions(main) == pytest.approx([0, 1/3, 2/3])
    assert [c.group_name for c in main.curves] == [None] * 3
    assert [c.style for c in main.curves] == [{}] * 3


def test_separate_mode_one_figure_per_group(eis_dataset):
    """分离模式：每个分组一张图；样品 1 两张图里都有；颜色按样品；样式只属于写了它的分组。"""
    figures = plan(eis_dataset, overlap_config())

    assert [f.key for f in figures] == ['A', 'B']
    a, b = figures
    assert samples(a) == [0, 1]
    assert samples(b) == [1, 2]
    assert positions(a) == pytest.approx([0, 1/3])
    assert positions(b) == pytest.approx([1/3, 2/3])
    assert [c.group_name for c in a.curves + b.curves] == ['A', 'A', 'B', 'B']
    assert [c.style for c in a.curves] == [{'linestyle': 'dash'}] * 2
    assert [c.style for c in b.curves] == [{}] * 2


def test_merge_mode_first_group_wins(eis_dataset):
    """合并模式：样品 1 只出现一次且归 A；同组用组首色——B 的组首是样品 1（1/3），即使样品 1 已归 A。"""
    figures = plan(eis_dataset, overlap_config(), merge_groups=True)

    assert [f.key for f in figures] == ['main']
    main = figures[0]
    assert samples(main) == [0, 1, 2]
    assert [c.group_name for c in main.curves] == ['A', 'A', 'B']
    assert positions(main) == pytest.approx([0, 0, 1/3])
    assert [c.style for c in main.curves] == [{'linestyle': 'dash'}] * 2 + [{}]


def test_merge_mode_writing_order_is_priority(eis_dataset):
    """先到先得看的是书写顺序：把 B 写在前面，样品 1 就归 B。"""
    config = {
        'B': {'num': [1, 2]},
        'A': {'num': [0, 1], 'linestyle': 'dash'},
    }
    main = plan(eis_dataset, config, merge_groups=True)[0]

    assert samples(main) == [1, 2, 0]
    assert [c.group_name for c in main.curves] == ['B', 'B', 'A']
    assert positions(main) == pytest.approx([1/3, 1/3, 0])
    assert [c.style for c in main.curves] == [{}, {}, {'linestyle': 'dash'}]


# ──────────────────────────────────────────────
# 曲线内容：数据、标签、单位、样式原样带入
# ──────────────────────────────────────────────
def test_curve_data_matches_get_xy_data(eis_dataset):
    """曲线的数据、标签、单位与 get_xy_data 一致；plotrange、neglog 照样传下去。"""
    from plotlib.plot_common import get_xy_data

    curve = plan(eis_dataset, channel_y=2, plotrange=2, neglog_y=True)[0].curves[0]
    x, y, _, y_label, x_unit, y_unit = get_xy_data(
        eis_dataset, 0, 0, 2, neglog_y=True, plotrange=2)

    assert curve.x.tolist() == x.tolist() == [1, 10]
    assert curve.y.tolist() == y.tolist() == [1, 2]
    assert (curve.label, curve.x_unit, curve.y_unit) == (y_label, x_unit, y_unit)
    assert curve.label == 'S0'


def test_group_style_kept_as_written(eis_dataset):
    """分组写的样式按标准写法原样带入，不翻译；写了 color 时 color_position 照常给出。"""
    config = {'A': {'num': [0, 1], 'marker': 'circle', 'color': (255, 0, 0)}}
    a = plan(eis_dataset, config)[0]

    assert [c.style for c in a.curves] == [{'marker': 'circle', 'color': (255, 0, 0)}] * 2
    assert positions(a) == pytest.approx([0, 1/3])
