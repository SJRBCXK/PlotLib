"""
验证 plan_figures 和 plan_bars 生成的绘图计划。

plan_figures 只做「决定」，不碰任何绘图库：画几张图、每张图有哪些曲线、每条曲线的数据 / 标签 / 颜色 / 样式。
两个后端（matplotlib、Plotly）照着同一份计划画，分组规则只写这一次。
by 决定哪些样品进哪张图（'all' / 'group' / 'sample'），图层（Layer）决定每个样品画哪几条、画成什么、挂哪根轴。

规则（by='all' / 'group'）：
  - 不分组（by='all'）：一张 'main' 图，全部样品按样品号排序，没有分组样式；
  - 分离模式：每个分组一张图，key 为分组名；同一样品可出现在多张图里；颜色按样品；
  - 合并模式：一张 'main' 图；同一样品只画一次，归第一个包含它的分组（先到先得，书写顺序即优先级）；
    同组的线统一用组首色（该组写在第一位的样品的色带位置，只看本组配置，与其他分组无关）；
  - 分组写了的样式按标准写法原样带入 style，翻译留给后端；颜色存色带位置，不存具体颜色值。

数据来自 conftest.py 的 eis_dataset：3 个样品，色带位置 0、1/3、2/3；
通道 0 是频率 [1, 10, 100]，通道 1 是 Zs'，通道 2 是 Zs''（负数）。
"""
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pytest
from conftest import bar_data, bar_specs, xy_curves

from plotlib.group import Group
from plotlib.plot_spec import BarStyle, CurveKind, Layer, LineStyle
from plotlib.processor import Reduction


def plan(dataset, config=None, *, channel_x=0, channel_y=1, kind: CurveKind = 'line',
         neglog_x=False, neglog_y=False, **kwargs):
    """
    一个图层（默认通道 0 对通道 1 的折线）：有 config 时 by='group'，否则 by='all'。
    config 每次新建（Group 会原地格式化传入的配置）。
    """
    from plotlib.plan import plan_figures

    layer = Layer(channel_x, channel_y, kind=kind, neglog_x=neglog_x, neglog_y=neglog_y)
    return plan_figures(dataset, Group(dataset, config or {}), [layer], by='group' if config else 'all', **kwargs)


def per_sample(dataset, *layers, **kwargs):
    """每个样品一张图（by='sample'），画给出的各图层。"""
    from plotlib.plan import plan_figures

    return plan_figures(dataset, None, list(layers), by='sample', **kwargs)


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
    assert [c.style for c in main.curves] == [LineStyle()] * 3


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
    assert [c.style for c in a.curves] == [LineStyle(linestyle='dash')] * 2
    assert [c.style for c in b.curves] == [LineStyle()] * 2


def test_merge_mode_first_group_wins(eis_dataset):
    """合并模式：样品 1 只出现一次且归 A；同组用组首色——B 的组首是样品 1（1/3），即使样品 1 已归 A。"""
    figures = plan(eis_dataset, overlap_config(), merge_groups=True)

    assert [f.key for f in figures] == ['main']
    main = figures[0]
    assert samples(main) == [0, 1, 2]
    assert [c.group_name for c in main.curves] == ['A', 'A', 'B']
    assert positions(main) == pytest.approx([0, 0, 1/3])
    assert [c.style for c in main.curves] == [LineStyle(linestyle='dash')] * 2 + [LineStyle()]


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
    assert [c.style for c in main.curves] == [LineStyle(), LineStyle(), LineStyle(linestyle='dash')]


# ──────────────────────────────────────────────
# 曲线内容：数据、标签、单位、样式原样带入
# ──────────────────────────────────────────────
def test_curve_data_matches_get_xy_data(eis_dataset):
    """曲线的数据、标签、单位与 get_xy_data 一致；plotrange、neglog 照样传下去。"""
    from plotlib.plan import get_xy_data

    figure = plan(eis_dataset, channel_y=2, plotrange=2, neglog_y=True)[0]
    curve = xy_curves(figure)[0]
    x, y, _, y_label, x_unit, y_unit = get_xy_data(
        eis_dataset, 0, 0, 2, neglog_y=True, plotrange=2)

    assert curve.x.tolist() == x.tolist() == [1, 10]
    assert curve.y.tolist() == y.tolist() == [1, 2]
    assert curve.label == y_label == 'S0'
    assert (figure.x_unit, figure.y_unit) == (x_unit, y_unit)     # 单位属于图（6.4 起），不在曲线上


def test_group_style_kept_as_written(eis_dataset):
    """分组写的样式按标准写法原样带入，不翻译；写了 color 时 color_position 照常给出。"""
    config = {'A': {'num': [0, 1], 'marker': 'circle', 'color': (255, 0, 0)}}
    a = plan(eis_dataset, config)[0]

    assert [c.style for c in a.curves] == [LineStyle(marker='circle', color=(255, 0, 0))] * 2
    assert positions(a) == pytest.approx([0, 1/3])


# ──────────────────────────────────────────────
# 色带位置按整个数据集排名；只读 Group
# （两条由 test_plotter.py 搬来：规则在计划里，只在这里测一次）
# ──────────────────────────────────────────────
@pytest.mark.parametrize("merge, expected", [
    (False, [1/3, 2/3]),       # 分离模式：各样品各自的位置
    (True,  [1/3, 1/3]),       # 合并模式：统一为组首（样品 5）的位置
], ids=['separate', 'merge'])
def test_sparse_sample_ids_group_positions(sparse_dataset, merge, expected):
    """
    样品号 0、5、9：排名基于整个数据集，不是只看分组里的样品。
    回归：组首色曾取 cmap(5/3)，被截断成色带末端。
    """
    figure = plan(sparse_dataset, {'A': {'num': [5, 9]}}, merge_groups=merge)[0]
    assert samples(figure) == [5, 9]
    assert positions(figure) == pytest.approx(expected)


@pytest.mark.parametrize("merge", [False, True], ids=['separate', 'merge'])
def test_plan_does_not_modify_group(eis_dataset, merge):
    """生成计划只读分组：前后 group.to_config() 不变。后端不读 Group，所以只需在这里测。"""
    from plotlib.plan import plan_figures

    groups = Group(eis_dataset, overlap_config())
    before = groups.to_config()
    plan_figures(eis_dataset, groups, [Layer(0, 1)], by='group', merge_groups=merge)
    assert groups.to_config() == before


# ══════════════════════════════════════════════
# 坐标轴信息及单 Y 轴和双 Y 轴计划
#   线（LineSpec / ScatterSpec，画法由类型决定）：数据、标签、色带位置、样式、axis（挂在哪根轴上）
#   图（FigureSpec）：key、各轴单位、neglog（哪根轴的刻度补负号）、layout（按哪套排版画）
# eis_dataset：S1 = S0 × 2，S2 = S0 × 3；S0 的 Zs' = [10, 20, 30]，Zs'' = [-1, -2, -3]
# ══════════════════════════════════════════════
FREQ, ZS_RE, ZS_IM = 0, 1, 2
UNITS = {FREQ: 'Frequency(Hz)', ZS_RE: "Zs'(ohm)", ZS_IM: "Zs''(ohm)"}


@pytest.mark.parametrize("config, merge", [
    (None, False),
    (overlap_config(), False),
    (overlap_config(), True),
], ids=['no-groups', 'separate', 'merge'])
def test_plan_figures_carry_figure_info(eis_dataset, config, merge):
    """原有的三种计划都带上图层面的信息：单位在图上、版式 'multiline'；线默认画折线、挂左轴；曲线上不再有单位。"""
    for figure in plan(eis_dataset, config, merge_groups=merge):
        assert (figure.x_unit, figure.y_unit, figure.y2_unit) == (UNITS[FREQ], UNITS[ZS_RE], None)
        assert figure.layout == 'multiline'
        assert figure.neglog == set()
        for curve in figure.curves:
            assert (type(curve).__name__, curve.axis) == ('LineSpec', 'left')
            assert not hasattr(curve, 'x_unit')


def test_plan_figures_neglog(eis_dataset):
    """neglog 记在图上，说明哪根轴的刻度要补负号。"""
    [figure] = plan(eis_dataset, neglog_x=True)
    assert figure.neglog == {'x'}


def test_scatter_plan_shares_rules_and_reads_own_style(eis_dataset):
    """
    画法由 spec 的类型决定（4.3）：图层写 kind='line' 产出 LineSpec，kind='scatter' 产出 ScatterSpec。
    两者共用分组规则（不分组、分离、合并三种模式的图、线的顺序、组名、色带位置都相同）；
    样式按画法只取用得上的分组字段：折线取线型、标记、颜色，散点只取标记、颜色，其余不解析。
    """
    from plotlib.plot_spec import LineSpec, ScatterSpec, ScatterStyle

    def styled():
        return {'A': {'num': [0, 1], 'linestyle': 'dash', 'marker': 'square', 'color': 'red'}, 'B': {'num': [1, 2]}}

    def outline(figures):
        return [(f.key, f.name, f.layout, [(c.sample_idx, c.group_name, c.color_position, c.label) for c in f.curves])
                for f in figures]

    for config, merge in [(None, False), (styled(), False), (styled(), True)]:
        lines = plan(eis_dataset, config and styled(), merge_groups=merge)
        scatters = plan(eis_dataset, config and styled(), merge_groups=merge, kind='scatter')
        assert outline(scatters) == outline(lines)
        assert all(type(c) is LineSpec for f in lines for c in f.curves)
        assert all(type(c) is ScatterSpec for f in scatters for c in f.curves)

    lines = plan(eis_dataset, styled())
    scatters = plan(eis_dataset, styled(), kind='scatter')
    assert lines[0].curves[0].style == LineStyle(linestyle='dash', marker='square', color='red')
    assert scatters[0].curves[0].style == ScatterStyle(marker='square', color='red')
    assert (lines[1].curves[0].style, scatters[1].curves[0].style) == (LineStyle(), ScatterStyle())


def test_xy_one_figure_per_sample(eis_dataset):
    """
    按样品分图时，每个样品对应一张图，图键为样品号。
    一张图只有一个样品，不按样品换色：色带位置为 None，表示用后端默认色（与改前相同）。
    """
    figures = per_sample(eis_dataset, Layer(ZS_RE, ZS_IM))

    assert [f.key for f in figures] == [0, 1, 2]
    for k, figure in enumerate(figures):
        assert figure.layout == 'xy'
        assert (figure.x_unit, figure.y_unit, figure.y2_unit) == (UNITS[ZS_RE], UNITS[ZS_IM], None)
        [curve] = xy_curves(figure)
        assert curve.sample_idx == k
        assert curve.x.tolist() == [10 * (k + 1), 20 * (k + 1), 30 * (k + 1)]
        assert curve.y.tolist() == [-1 * (k + 1), -2 * (k + 1), -3 * (k + 1)]
        assert curve.color_position is None
        assert (type(curve).__name__, curve.axis, curve.style) == ('LineSpec', 'left', LineStyle())


def test_xy_neglog(eis_dataset):
    """neglog_y：Y 取绝对值，图上记下 Y 轴刻度要补负号。"""
    figure = per_sample(eis_dataset, Layer(ZS_RE, ZS_IM, neglog_y=True))[0]
    assert xy_curves(figure)[0].y.tolist() == [1, 2, 3]
    assert figure.neglog == {'y'}


def test_dual_y_two_curves_per_sample(eis_dataset):
    """
    双 Y 轴图按样品生成。两个图层各用一根 Y 轴，并共用 X 轴。
    两条线不带颜色：左红右蓝属于呈现，由排版预设决定（6.6b；画出来的颜色见 test_plotter.py 的排版测试）；
    两侧画法可以不同（'line' / 'scatter'）。写错画法的报错在 test_plot_entry_checks。
    """
    from plotlib.plot_spec import ScatterStyle

    figures = per_sample(eis_dataset, Layer(FREQ, ZS_RE), Layer(ZS_RE, ZS_IM, kind='scatter', side='right'))

    assert [f.key for f in figures] == [0, 1, 2]
    figure = figures[0]
    assert figure.layout == 'dual_y'
    assert (figure.x_unit, figure.y_unit, figure.y2_unit) == (UNITS[FREQ], UNITS[ZS_RE], UNITS[ZS_IM])

    left, right = xy_curves(figure)
    assert (left.axis, type(left).__name__, left.style) == ('left', 'LineSpec', LineStyle())
    assert (right.axis, type(right).__name__, right.style) == ('right', 'ScatterSpec', ScatterStyle())
    assert left.color_position is None and right.color_position is None
    assert left.x.tolist() == [1, 10, 100] and left.y.tolist() == [10, 20, 30]
    assert right.x.tolist() == [10, 20, 30] and right.y.tolist() == [-1, -2, -3]


def test_dual_y_neglog_per_axis(eis_dataset):
    """
    负对数轴的符号按轴确定。共用的 X 轴的负号只看左侧图层；右侧图层的 neglog_x 只把自己的 X 数据取绝对值，
    可以与左侧不同；左右 Y 轴各看各的。刻度上实际画出的负号见 test_plotter.py 的负对数测试。
    """
    # 右线的 X（Zs''，全负）取绝对值，左线不变；X 轴刻度不补负号（左侧没写）
    figure = per_sample(eis_dataset, Layer(FREQ, ZS_RE), Layer(ZS_IM, ZS_RE, side='right', neglog_x=True))[0]
    left, right = xy_curves(figure)
    assert left.x.tolist() == [1, 10, 100]
    assert right.x.tolist() == [1, 2, 3]
    assert figure.neglog == set()

    # 左侧决定 X 轴；只有右侧写 neglog_y 时补的是右 Y 轴
    for layers, expected in (((Layer(ZS_IM, ZS_RE, neglog_x=True), Layer(ZS_IM, ZS_RE, side='right')), {'x'}),
                             ((Layer(FREQ, ZS_RE), Layer(FREQ, ZS_IM, side='right', neglog_y=True)), {'y2'}),
                             ((Layer(FREQ, ZS_IM, neglog_y=True), Layer(FREQ, ZS_RE, side='right')), {'y'})):
        assert per_sample(eis_dataset, *layers)[0].neglog == expected


def dual(dataset, **kwargs):
    """双 Y 轴：左 频率–Zs'，右 频率–Zs''，每个样品一张。"""
    return per_sample(dataset, Layer(FREQ, ZS_RE), Layer(FREQ, ZS_IM, side='right'), **kwargs)


def test_dual_y_labels_are_units(eis_dataset):
    """
    双 Y 轴两条线是同一个样品的两个变量：图例里每条线写自己的单位，样品名放在图例标题里
    """
    figure = dual(eis_dataset)[0]
    assert [c.label for c in figure.curves] == [UNITS[ZS_RE], UNITS[ZS_IM]]
    assert figure.legend_title == 'S0'


# ──────────────────────────────────────────────
# 图例标题及其名称占位符
#   每个样品一张图（xy、双 Y 轴）→ 样品名；分离模式每组一张图 → 组名；
#   只有一张图（多线、合并）没有自己的名字 → '{name}' 不替换；其余文字在任何图里都照用
# ──────────────────────────────────────────────
def test_legend_title_defaults(eis_dataset):
    """默认：多线、分组（分离 / 合并）、xy 不加图例标题；双 Y 轴用样品名。"""
    for figures in (plan(eis_dataset), plan(eis_dataset, overlap_config()),
                    plan(eis_dataset, overlap_config(), merge_groups=True),
                    per_sample(eis_dataset, Layer(ZS_RE, ZS_IM))):
        assert {f.legend_title for f in figures} == {None}
    two_axes = dual(eis_dataset)
    assert [f.legend_title for f in two_axes] == ['S0', 'S1', 'S2']


def test_legend_title_name_placeholder(eis_dataset):
    """'{name}' 换成每张图自己的名字，前后可以加文字；None 表示不加。"""
    separate = plan(eis_dataset, overlap_config(), legend_title='Group {name}')
    assert [f.legend_title for f in separate] == ['Group A', 'Group B']
    xy = per_sample(eis_dataset, Layer(ZS_RE, ZS_IM), legend_title='{name}')
    assert [f.legend_title for f in xy] == ['S0', 'S1', 'S2']
    two_axes = dual(eis_dataset, legend_title='Sample: {name}')
    assert [f.legend_title for f in two_axes] == ['Sample: S0', 'Sample: S1', 'Sample: S2']
    untitled = dual(eis_dataset, legend_title=None)
    assert {f.legend_title for f in untitled} == {None}


def test_figure_name(eis_dataset):
    """
    每张图自己的名字（6.8；Plotly 翻页时档位标签用它，'{name}' 也换成它）：
    每个样品一张图（xy、双 Y 轴）→ 样品名；分离模式 → 组名；只有一张图（不分组、合并）→ None。
    """
    assert [f.name for f in plan(eis_dataset)] == [None]
    assert [f.name for f in plan(eis_dataset, overlap_config(), merge_groups=True)] == [None]
    assert [f.name for f in plan(eis_dataset, overlap_config())] == ['A', 'B']
    assert [f.name for f in per_sample(eis_dataset, Layer(ZS_RE, ZS_IM))] == ['S0', 'S1', 'S2']
    two_axes = dual(eis_dataset)
    assert [f.name for f in two_axes] == ['S0', 'S1', 'S2']


@pytest.mark.parametrize("grouped", [False, True], ids=['no_groups', 'merge'])
def test_legend_title_on_single_figure(eis_dataset, grouped):
    """
    只有一张图（不分组、合并模式）：标题是自由文字，照原样用（如突出某个样品时直接写它的名字）；
    全部样品同图或合并分组时，保留标题中的 '{name}' 占位符。
    """
    def draw(title):
        return plan(eis_dataset, overlap_config() if grouped else None, merge_groups=grouped, legend_title=title)

    assert draw('S1 (highlighted)')[0].legend_title == 'S1 (highlighted)'
    assert draw('{name}')[0].legend_title == '{name}'


# ══════════════════════════════════════════════
# 分图方式与图层的组合规则
# ══════════════════════════════════════════════
def test_mixed_layers_per_sample(eis_dataset):
    """
    同一侧画「散点 + 折线」两层（如实测点 + 拟合线）：每个样品一张图，曲线按「样品 → 图层」顺序，
    同一样品的各层顺序与输入的 layers 一致；一个样品画多层时标签是各层 Y 的单位，图例标题自动是样品名。
    """
    from plotlib.plot_spec import LineSpec, ScatterSpec

    figures = per_sample(eis_dataset, Layer(FREQ, ZS_RE, kind='scatter'), Layer(FREQ, ZS_IM))
    assert [f.key for f in figures] == [0, 1, 2]
    for k, figure in enumerate(figures):
        assert figure.layout == 'xy'
        assert [type(c) for c in figure.curves] == [ScatterSpec, LineSpec]
        assert [(c.sample_idx, c.axis) for c in xy_curves(figure)] == [(k, 'left'), (k, 'left')]
        assert [c.label for c in figure.curves] == [UNITS[ZS_RE], UNITS[ZS_IM]]
        assert figure.legend_title == f'S{k}'
        assert (figure.x_unit, figure.y_unit, figure.y2_unit) == (UNITS[FREQ], UNITS[ZS_RE], None)


def test_rules_follow_by_and_layers(eis_dataset):
    """
    合法的组合各自推出：版式预设、是否按色带取色、legend_title='auto' 的结果
    """
    groups = Group(eis_dataset, overlap_config())
    cases = [
        ('all', None, [Layer(0, 1)], 'multiline', True, None),
        ('group', groups, [Layer(0, 1)], 'multiline', True, None),
        ('sample', None, [Layer(0, 1)], 'xy', False, None),
        ('sample', None, [Layer(0, 1), Layer(0, 2, side='right')], 'dual_y', False, 'S0'),
    ]
    from plotlib.plan import plan_figures

    for by, grouping, layers, layout, colored, title in cases:
        figure = plan_figures(eis_dataset, grouping, layers, by=by)[0]
        assert figure.layout == layout, by
        assert all((c.color_position is not None) == colored for c in figure.curves), by
        assert figure.legend_title == title, by

    # 分组只在 by='group' 时使用，也只在那时检查：其他模式给了别的数据集的分组也不报错
    import numpy as np

    from plotlib.dataset import DataSet

    foreign = Group(DataSet().form_array(np.ones(2), ['S'], ['u'], 0), {'A': {'num': [0]}})
    for by in ('all', 'sample'):
        assert plan_figures(eis_dataset, foreign, [Layer(0, 1)], by=by)


def test_plot_entry_checks(eis_dataset):
    """无效参数、未支持的组合及同轴负对数设置冲突均报错。"""
    from plotlib.plan import plan_figures

    groups = Group(eis_dataset, overlap_config())
    left, right = Layer(0, 1), Layer(0, 2, side='right')
    cases = [
        (dict(layers=[]), '图层'),
        (dict(layers=[right], by='sample'), '左侧'),
        (dict(layers=[left], merge_groups=True), 'merge_groups'),
        (dict(layers=[left], by='group', groups=None), '分组'),
        (dict(layers=[left], by='samples'), "'all'、'group'、'sample'"),
        (dict(layers=[Layer(0, 1, kind='bar')]), "'line'、'scatter'"),     # pyright: ignore[reportArgumentType]
        (dict(layers=[Layer(0, 1, side='top')], by='sample'), "'left'、'right'"),   # pyright: ignore[reportArgumentType]
        (dict(layers=[Layer(None, 1)]), '通道'),
        (dict(layers=[left, Layer(0, 2)]), '多个图层'),                    # by='all' 画多层：先不开放
        (dict(layers=[left, Layer(0, 2)], by='group', groups=groups), '多个图层'),
        (dict(layers=[left, right], by='group', groups=groups), '多个图层'),
        (dict(layers=[left, Layer(0, 2, neglog_x=True)], by='sample'), 'neglog_x'),       # 左侧 X 写法不一致
        (dict(layers=[right, left, Layer(0, 2, side='right', neglog_y=True)], by='sample'), 'neglog_y'),
    ]
    for kwargs, message in cases:
        kwargs.setdefault('by', 'all')
        grouping = kwargs.pop('groups', groups)
        with pytest.raises(ValueError, match=message):
            plan_figures(eis_dataset, grouping, kwargs.pop('layers'), **kwargs)


# ══════════════════════════════════════════════
# 柱状图计划的类别、系列和汇总规则
# ══════════════════════════════════════════════
def outline(figure):
    """每个系列的 (键, 标签, 类别, 高度, 配色位置)，高度保留两位小数便于比较。"""
    return [(bar.key, bar.label, bar.categories, [round(h, 2) for h in bar.heights], bar.color_position)
            for bar in bar_specs(figure)]


def test_bar_table_layouts():
    """
    4 种「类别 × 系列」组合（plotrange=2：样品 3 的 F 只取 [1, 3]，均值 2）。系列键是原通道号（channels=[1, 0]），
    样品按样品号排序，分组按配置顺序；G1 = {3, 0}，组内取样品汇总值的平均。
    """
    from plotlib.plan import plan_bars

    data = bar_data()
    groups = Group(data, {'G1': {'num': [3, 0]}, 'G2': {'num': [0]}})
    cases = [
        (dict(x='sample', series='channel'),
         [(1, 'E(%)', ['S0', 'S3'], [30, 10], 0.0), (0, 'F(N)', ['S0', 'S3'], [2, 2], 0.5)]),
        (dict(x='channel', series='sample'),
         [(0, 'S0', ['E(%)', 'F(N)'], [30, 2], 0.0), (3, 'S3', ['E(%)', 'F(N)'], [10, 2], 0.5)]),
        (dict(x='group', series='channel'),
         [(1, 'E(%)', ['G1', 'G2'], [20, 30], 0.0), (0, 'F(N)', ['G1', 'G2'], [2, 2], 0.5)]),
        (dict(x='channel', series='group'),         # 组的配色位置是组首样品的：G1 首个是样品 3
         [('G1', 'G1', ['E(%)', 'F(N)'], [20, 2], 0.5), ('G2', 'G2', ['E(%)', 'F(N)'], [30, 2], 0.0)]),
    ]
    for kwargs, expected in cases:
        figure = plan_bars(data, groups, [1, 0], reduce='mean', plotrange=2, **kwargs)
        assert outline(figure) == expected, kwargs
        assert (figure.key, figure.layout, figure.x_unit, figure.y_unit) == ('main', 'bars', '', '')
        assert [(bar.series_index, bar.series_count, bar.mode, bar.width) for bar in bar_specs(figure)] == \
               [(0, 2, 'group', 0.8), (1, 2, 'group', 0.8)]
        group_names = [bar.group_name for bar in bar_specs(figure)]
        assert group_names == (['G1', 'G2'] if kwargs['series'] == 'group' else [None, None])

    # 分组 + plotrange：截行在取数时做，直接用原来的分组（不复制配置；自定义字段是只读映射时复制会失败）
    from types import MappingProxyType
    custom = Group(data, {'G1': {'num': [3, 0], 'note': MappingProxyType({'batch': 1})}})
    assert outline(plan_bars(data, custom, 0, x='group', reduce='mean', plotrange=2)) == \
        [(0, 'F(N)', ['G1'], [2], 0.0)]

    # 先截行再汇总：不截时样品 3 的 F 均值是 (1 + 3 + 100) / 3
    figure = plan_bars(data, None, 0, reduce='mean')
    assert outline(figure) == [(0, 'F(N)', ['S0', 'S3'], [2, 34.67], 0.0)]

    # Y 轴标题：一个通道用它的列标题；多个通道列标题相同时沿用，不同时留空
    for channels, title in (([0], 'F(N)'), ([0, 2], 'F(N)'), ([0, 1], '')):
        assert plan_bars(data, None, channels, reduce='mean').y_unit == title

    # 缺数据保留位置：样品 3 的通道 2 只取第 1 行时是 NaN，类别仍有两个
    [bar] = bar_specs(plan_bars(data, None, 2, plotrange=1))
    assert bar.categories == ['S0', 'S3']
    assert bar.heights[0] == 5 and np.isnan(bar.heights[1])

    # 样式：分组配置的 color、hatch 只在系列是分组时读；styles 单个对全部系列，字典逐个系列，优先于分组配置
    styled = Group(data, {'G1': {'num': [3, 0], 'color': 'red', 'hatch': 'dot'}, 'G2': {'num': [0]}})
    figure = plan_bars(data, styled, [0], x='channel', series='group', reduce='mean',
                       styles={'G1': BarStyle(hatch='slash')})
    assert [bar.style for bar in figure.curves] == [BarStyle(color='red', hatch='slash'), BarStyle()]
    figure = plan_bars(data, styled, [0, 1], x='group', reduce='mean', styles=BarStyle(edge_color='black'))
    assert [bar.style for bar in figure.curves] == [BarStyle(edge_color='black')] * 2

    # 样式在汇总之前校验：键不是系列的键、纹理写错时，汇总函数一次都没执行
    calls = []

    def counting(values):
        calls.append(1)
        return values[0]

    for wrong in ({99: BarStyle()}, BarStyle(hatch='bad')):
        with pytest.raises(ValueError):
            plan_bars(data, None, 0, reduce=counting, styles=wrong)
    assert calls == []


def test_bar_errors():
    """误差：不用分组时是同一列多行之间的；用到分组时是组内各样品汇总值之间的；误差通道按原行对齐。"""
    from plotlib.plan import plan_bars

    data = bar_data()

    def summary(figure):
        """每个系列的 (高度, 误差, 是否画端帽)；转成 Python 浮点再比较字符串，NaN 也能比。"""
        return [([round(float(h), 3) for h in bar.heights],
                 None if bar.errors is None else [round(float(e), 3) for e in bar.errors], bar.caps)
                for bar in bar_specs(figure)]

    nan = float('nan')
    # 样品 0 的 E 是 [20, 40]：std = 14.142、sem = 10；样品 3 的 E 只有一个值，没有误差 → 这个系列不画端帽
    spreads: list[tuple[Literal['std', 'sem'], float]] = [('std', 14.142), ('sem', 10.0)]
    for errors, error in spreads:
        assert str(summary(plan_bars(data, None, 1, reduce='mean', errors=errors))) == \
               str([([30.0, 10.0], [error, nan], False)])

    # 分组：每个样品先取 max（样品 3 的 F 是 100、样品 0 是 2），G1 均值 51、SEM 49；G2 只有一个样品，没有误差
    groups = Group(data, {'G1': {'num': [3, 0]}, 'G2': {'num': [0]}})
    assert str(summary(plan_bars(data, groups, 0, x='group', reduce='max', errors='sem'))) == \
           str([([51.0, 2.0], [49.0, nan], False)])

    # 误差通道 3，按原行对齐（类别 S0、S3）：
    #   first：F 取第 1 行 → S3 是 1 ± 9；通道 2 的第一个有效值在第 2 行 → S3 是 10 ± 1
    #   max：S3 的 F 最大值 100 在第 3 行，那一行没有误差 → 省略，这个系列不画端帽
    #   mean：对有效行的误差取平均，S3 的 F 是 (9 + 1) / 2 = 5（NaN 忽略）
    cases: list[tuple[Reduction, list]] = [
             ('first', [([2.0, 1.0], [0.2, 9.0], True), ([5.0, 10.0], [0.2, 1.0], True)]),
             ('max', [([2.0, 100.0], [0.2, nan], False), ([5.0, 10.0], [0.2, 1.0], True)]),
             ('mean', [([2.0, 34.667], [0.2, 5.0], True), ([5.0, 10.0], [0.2, 1.0], True)])]
    for reduce, expected in cases:
        figure = plan_bars(data, None, [0, 2], reduce=reduce, errors={0: 3, 2: 3})
        assert str(summary(figure)) == str(expected), str(reduce)

    # 字典里没写的通道不画误差棒（errors 为 None），端帽不受影响
    figure = plan_bars(data, None, [0, 1], reduce='first', errors={0: 3})
    assert summary(figure)[1][1:] == (None, True)

    # 不可哈希的可调用对象（普通 dataclass 实例）也能配误差字典：按「对有效行的误差汇总」处理，这里结果与 'first' 相同
    @dataclass
    class First:
        def __call__(self, values):
            return values[0]

    assert str(summary(plan_bars(data, None, [0, 2], reduce=First(), errors={0: 3, 2: 3}))) == str(cases[0][1])

    # 汇总后的误差也要校验：原始误差（这里就用通道 0 自己）都非负，函数汇总出负数时报错；
    # 柱高有限而误差是无穷大（误差通道里写了 inf）也报错
    with pytest.raises(ValueError, match='误差'):
        plan_bars(data, None, 0, reduce=lambda v: v[0] - v[-1], errors={0: 0})
    infinite_error = bar_data()
    infinite_error.data[0, 3] = np.inf              # 样品 3 的误差通道第 1 行
    with pytest.raises(ValueError, match='误差'):
        plan_bars(infinite_error, None, 0, reduce='first', errors={0: 3})

    # 分组：柱高和误差来自同一批样品汇总值（每个样品只汇总一次）
    seen = []

    def first_seen(values):
        seen.append(values[0])
        return values[0]

    figure = plan_bars(data, groups, 0, x='group', reduce=first_seen, errors='std')
    assert len(seen) == 3                           # G1 两个样品、G2 一个样品，各汇总一次
