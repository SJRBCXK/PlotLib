"""
测试对象：src/plotlib/plan.py 的 plan_multiline_figures / plan_xy_figures / plan_dual_y_figures —— 绘图计划（docs/WORK_PLAN.md 步骤 6.1、6.4）

plan_multiline_figures 只做「决定」，不碰任何绘图库：画几张图、每张图有哪些曲线、每条曲线的数据 / 标签 / 颜色 / 样式。
两个后端（matplotlib、Plotly）照着同一份计划画，分组规则只写这一次。

规则（与现在的 plot_groups 一致，这一步不改行为）：
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
from plotlib.plot_spec import LineStyle


def plan(dataset, config=None, **kwargs):
    """以通道 0 为 X、通道 1 为 Y 生成计划；config 每次新建（Group 会原地格式化传入的配置）。"""
    from plotlib.plan import plan_multiline_figures

    groups = Group(dataset, config or {})
    kwargs.setdefault('channel_x', 0)
    kwargs.setdefault('channel_y', 1)
    return plan_multiline_figures(dataset, groups, **kwargs)


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
    curve = figure.curves[0]
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
    from plotlib.plan import plan_multiline_figures

    groups = Group(eis_dataset, overlap_config())
    before = groups.to_config()
    plan_multiline_figures(eis_dataset, groups, 0, 1, merge_groups=merge)
    assert groups.to_config() == before


# ══════════════════════════════════════════════
# 计划补全（docs/WORK_PLAN.md 步骤 6.4）：图层面的信息、xy 与双 Y 轴两种计划
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
    画法由 spec 的类型决定（4.3）：多线 / 分组计划只产出 LineSpec，plan_scatter_figures 产出 ScatterSpec。
    两者共用分组规则（不分组、分离、合并三种模式的图、线的顺序、组名、色带位置都相同）；
    样式按画法只取用得上的分组字段：折线取线型、标记、颜色，散点只取标记、颜色，其余不解析。
    """
    from plotlib.plan import plan_scatter_figures
    from plotlib.plot_spec import LineSpec, ScatterSpec, ScatterStyle

    def styled():
        return {'A': {'num': [0, 1], 'linestyle': 'dash', 'marker': 'square', 'color': 'red'}, 'B': {'num': [1, 2]}}

    def outline(figures):
        return [(f.key, f.name, f.layout, [(c.sample_idx, c.group_name, c.color_position, c.label) for c in f.curves])
                for f in figures]

    for config, merge in [(None, False), (styled(), False), (styled(), True)]:
        lines = plan(eis_dataset, config and styled(), merge_groups=merge)
        scatters = plan_scatter_figures(eis_dataset, Group(eis_dataset, styled() if config else {}), 0, 1,
                                        merge_groups=merge)
        assert outline(scatters) == outline(lines)
        assert all(type(c) is LineSpec for f in lines for c in f.curves)
        assert all(type(c) is ScatterSpec for f in scatters for c in f.curves)

    lines = plan(eis_dataset, styled())
    scatters = plan_scatter_figures(eis_dataset, Group(eis_dataset, styled()), 0, 1)
    assert lines[0].curves[0].style == LineStyle(linestyle='dash', marker='square', color='red')
    assert scatters[0].curves[0].style == ScatterStyle(marker='square', color='red')
    assert (lines[1].curves[0].style, scatters[1].curves[0].style) == (LineStyle(), ScatterStyle())


def test_xy_one_figure_per_sample(eis_dataset):
    """
    xy（原 subplotter_yy）：每个样品一张图、一条线，key 是样品号。
    一张图只有一条线，不按样品换色：色带位置为 None，表示用后端默认色（与改前相同）。
    """
    from plotlib.plan import plan_xy_figures

    figures = plan_xy_figures(eis_dataset, ZS_RE, ZS_IM)

    assert [f.key for f in figures] == [0, 1, 2]
    for k, figure in enumerate(figures):
        assert figure.layout == 'xy'
        assert (figure.x_unit, figure.y_unit, figure.y2_unit) == (UNITS[ZS_RE], UNITS[ZS_IM], None)
        [curve] = figure.curves
        assert curve.sample_idx == k
        assert curve.x.tolist() == [10 * (k + 1), 20 * (k + 1), 30 * (k + 1)]
        assert curve.y.tolist() == [-1 * (k + 1), -2 * (k + 1), -3 * (k + 1)]
        assert curve.color_position is None
        assert (type(curve).__name__, curve.axis, curve.style) == ('LineSpec', 'left', LineStyle())


def test_xy_neglog(eis_dataset):
    """neglog_y：Y 取绝对值，图上记下 Y 轴刻度要补负号。"""
    from plotlib.plan import plan_xy_figures

    figure = plan_xy_figures(eis_dataset, ZS_RE, ZS_IM, neglog_y=True)[0]
    assert figure.curves[0].y.tolist() == [1, 2, 3]
    assert figure.neglog == {'y'}


def test_dual_y_two_curves_per_sample(eis_dataset):
    """
    双 Y 轴（原 plot_dual_y）：每个样品一张图、两条线，左线挂左轴、右线挂右轴，共用 X 轴。
    两条线不带颜色：左红右蓝属于呈现，由排版预设决定（6.6b；画出来的颜色见 test_plotter.py 的排版测试）；
    两侧画法可以不同（'line' / 'scatter'），写错时报错并列出可选值。
    """
    from plotlib.plan import plan_dual_y_figures
    from plotlib.plot_spec import ScatterStyle

    with pytest.raises(ValueError, match="'line'、'scatter'"):
        plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(ZS_RE, ZS_IM), kinds=('line', 'bar'))  # pyright: ignore[reportArgumentType]
    for wrong_length in [('scatter',), ('line', 'scatter', 'scatter')]:     # 回归（复审）：曾 IndexError / 静默忽略多余的
        with pytest.raises(ValueError, match='两个'):
            plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(ZS_RE, ZS_IM), kinds=wrong_length)  # pyright: ignore[reportArgumentType]
    figures = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(ZS_RE, ZS_IM),
                                  kinds=('line', 'scatter'))

    assert [f.key for f in figures] == [0, 1, 2]
    figure = figures[0]
    assert figure.layout == 'dual_y'
    assert (figure.x_unit, figure.y_unit, figure.y2_unit) == (UNITS[FREQ], UNITS[ZS_RE], UNITS[ZS_IM])

    left, right = figure.curves
    assert (left.axis, type(left).__name__, left.style) == ('left', 'LineSpec', LineStyle())
    assert (right.axis, type(right).__name__, right.style) == ('right', 'ScatterSpec', ScatterStyle())
    assert left.color_position is None and right.color_position is None
    assert left.x.tolist() == [1, 10, 100] and left.y.tolist() == [10, 20, 30]
    assert right.x.tolist() == [10, 20, 30] and right.y.tolist() == [-1, -2, -3]


def test_dual_y_neglog_per_axis(eis_dataset):
    """四根轴各自的 neglog：右线的 X（Zs''，全负）取绝对值；图上记 'x2'（上轴，拼图时会用到）。"""
    from plotlib.plan import plan_dual_y_figures

    figure = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(ZS_IM, ZS_RE), neglog_x2=True)[0]
    left, right = figure.curves
    assert left.x.tolist() == [1, 10, 100]
    assert right.x.tolist() == [1, 2, 3]
    assert figure.neglog == {'x2'}


def test_dual_y_labels_are_units(eis_dataset):
    """
    双 Y 轴两条线是同一个样品的两个变量：图例里每条线写自己的单位，样品名放在图例标题里
    （2026-11-20 用户选定，参照 Origin 图）。
    """
    from plotlib.plan import plan_dual_y_figures

    figure = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(FREQ, ZS_IM))[0]
    assert [c.label for c in figure.curves] == [UNITS[ZS_RE], UNITS[ZS_IM]]
    assert figure.legend_title == 'S0'


# ──────────────────────────────────────────────
# 图例标题（2026-11-20 用户提出）：四种绘图方法都能设；'{name}' 换成每张图自己的名字
#   每个样品一张图（xy、双 Y 轴）→ 样品名；分离模式每组一张图 → 组名；
#   只有一张图（多线、合并）没有自己的名字 → '{name}' 不替换；其余文字在任何图里都照用
# ──────────────────────────────────────────────
def test_legend_title_defaults(eis_dataset):
    """默认：多线、分组（分离 / 合并）、xy 不加图例标题；双 Y 轴用样品名。"""
    from plotlib.plan import plan_dual_y_figures, plan_xy_figures

    for figures in (plan(eis_dataset), plan(eis_dataset, overlap_config()),
                    plan(eis_dataset, overlap_config(), merge_groups=True),
                    plan_xy_figures(eis_dataset, ZS_RE, ZS_IM)):
        assert {f.legend_title for f in figures} == {None}
    dual = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(FREQ, ZS_IM))
    assert [f.legend_title for f in dual] == ['S0', 'S1', 'S2']


def test_legend_title_name_placeholder(eis_dataset):
    """'{name}' 换成每张图自己的名字，前后可以加文字；None 表示不加。"""
    from plotlib.plan import plan_dual_y_figures, plan_xy_figures

    separate = plan(eis_dataset, overlap_config(), legend_title='Group {name}')
    assert [f.legend_title for f in separate] == ['Group A', 'Group B']
    xy = plan_xy_figures(eis_dataset, ZS_RE, ZS_IM, legend_title='{name}')
    assert [f.legend_title for f in xy] == ['S0', 'S1', 'S2']
    dual = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(FREQ, ZS_IM),
                               legend_title='Sample: {name}')
    assert [f.legend_title for f in dual] == ['Sample: S0', 'Sample: S1', 'Sample: S2']
    untitled = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(FREQ, ZS_IM), legend_title=None)
    assert {f.legend_title for f in untitled} == {None}


def test_figure_name(eis_dataset):
    """
    每张图自己的名字（6.8；Plotly 翻页时档位标签用它，'{name}' 也换成它）：
    每个样品一张图（xy、双 Y 轴）→ 样品名；分离模式 → 组名；只有一张图（不分组、合并）→ None。
    """
    from plotlib.plan import plan_dual_y_figures, plan_xy_figures

    assert [f.name for f in plan(eis_dataset)] == [None]
    assert [f.name for f in plan(eis_dataset, overlap_config(), merge_groups=True)] == [None]
    assert [f.name for f in plan(eis_dataset, overlap_config())] == ['A', 'B']
    assert [f.name for f in plan_xy_figures(eis_dataset, ZS_RE, ZS_IM)] == ['S0', 'S1', 'S2']
    dual = plan_dual_y_figures(eis_dataset, left=(FREQ, ZS_RE), right=(FREQ, ZS_IM))
    assert [f.name for f in dual] == ['S0', 'S1', 'S2']


@pytest.mark.parametrize("grouped", [False, True], ids=['no_groups', 'merge'])
def test_legend_title_on_single_figure(eis_dataset, grouped):
    """
    只有一张图（不分组、合并模式）：标题是自由文字，照原样用（如突出某个样品时直接写它的名字）；
    这种图没有「自己的名字」，'{name}' 不替换、也不报错（用户定：不给单图加限制）。
    """
    def draw(title):
        return plan(eis_dataset, overlap_config() if grouped else None, merge_groups=grouped, legend_title=title)

    assert draw('S1 (highlighted)')[0].legend_title == 'S1 (highlighted)'
    assert draw('{name}')[0].legend_title == '{name}'
