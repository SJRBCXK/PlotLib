"""
测试对象：src/plotlib/plotter.py 的 DataPlotter

思路（Step 5）：不看图、不比像素，而是检查 matplotlib 对象的属性。
DataPlotter 把画出的东西都存在 self.figures 里（{计划的 key: DrawnFigure}，6.5 起四种方法同一形状），测试就从这里取：
  - 线的数据        line.get_xdata() / get_ydata()
  - 线型、颜色      line.get_linestyle() / get_color()
  - 坐标轴标题      ax.get_xlabel() / get_ylabel()
  - 图例文字        [t.get_text() for t in ax.get_legend().get_texts()]
  - 当前打开的图窗  plt.get_fignums()

后端在 conftest.py 里切到了 Agg（不弹窗），每个测试结束自动 plt.close('all')。

分层（2026-11-19 整理）：分组规则（去重、先到先得、组首色、样式归属、色带位置）只在 test_plot_plan.py 测；
这里只测 matplotlib 把计划画对（每张 FigureSpec 一张图、位置 → 颜色、样式翻译）和它独有的功能
（formatter、图例、linestyle、figsize、负对数刻度、x-y 单线图 / 双 Y 轴）。与 Plotly 的对照在 test_backend_parity.py。

数据来自 eis_dataset：每个样品 3 列 [Frequency(Hz), Zs'(ohm), Zs''(ohm)]，
S1 = S0 × 2，S2 = S0 × 3。
"""
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.collections import PathCollection
from matplotlib.colors import to_rgba
from matplotlib.container import BarContainer
from matplotlib.lines import Line2D
from numpy.typing import NDArray

from plotlib.group import Group
from plotlib.plotter import DataPlotter

FREQ, ZS_RE, ZS_IM = 0, 1, 2      # 通道号


def legend_texts(ax):
    return [t.get_text() for t in ax.get_legend().get_texts()]


# ══════════════════════════════════════════════
# plot_multiline：所有样品画在同一张图
# ══════════════════════════════════════════════
def test_plot_multiline_one_line_per_sample(eis_dataset):
    plotter = DataPlotter(eis_dataset, channel_x=FREQ, channel_y=ZS_RE)
    plotter.plot_multiline()

    assert list(plotter.figures) == ['main']
    assert len(plotter.figures['main'].artists) == 3
    assert len(plt.get_fignums()) == 1


def test_plot_multiline_labels(eis_dataset):
    """坐标轴标题取单位，图例取样品名。"""
    ax = DataPlotter(eis_dataset, channel_x=FREQ, channel_y=ZS_RE) \
        .plot_multiline().figures['main'].axes['left']

    assert ax.get_xlabel() == 'Frequency(Hz)'
    assert ax.get_ylabel() == "Zs'(ohm)"
    assert legend_texts(ax) == ['S0', 'S1', 'S2']


def test_plotrange_limits_points(eis_dataset):
    plotter = DataPlotter(eis_dataset, plotrange=2).plot_multiline()
    for line in plotter.figures['main'].artists:
        assert len(line.get_xdata()) == 2


def test_neglog_y(eis_dataset):
    """负对数：数据取绝对值后画，刻度文字再补回负号。Zs'' 全为负数，正好用来测。"""
    plotter = DataPlotter(eis_dataset, channel_x=FREQ, channel_y=ZS_IM)
    plotter.plot_multiline(neglog_y=True)
    m = plotter.figures['main']

    np.testing.assert_array_equal(m.artists[0].get_ydata(), [1, 2, 3])
    assert m.axes['left'].yaxis.get_major_formatter()(2.0, 0) == '-2.00'


def artist_xy(
    artist: Line2D | PathCollection | BarContainer,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """统一返回浮点 NumPy 坐标数组，避免宽泛类型影响切片和数值断言。"""
    if isinstance(artist, Line2D):
        return (
            np.asarray(artist.get_xdata(), dtype=np.float64),
            np.asarray(artist.get_ydata(), dtype=np.float64),
        )
    if isinstance(artist, PathCollection):                  # scatter：点坐标在 offsets 里
        offsets: NDArray[np.float64] = np.asarray(
            artist.get_offsets(), dtype=np.float64,
        )
        return offsets[:, 0], offsets[:, 1]
    if isinstance(artist, BarContainer):                    # bar：每根柱子是一个矩形
        return (
            np.asarray([r.get_x() + r.get_width() / 2 for r in artist], dtype=np.float64),
            np.asarray([r.get_height() for r in artist], dtype=np.float64),
        )
    raise TypeError(type(artist))


@pytest.mark.parametrize("plot_kind, artist_type", [
    ('line',    Line2D),
    ('scatter', PathCollection),
    ('bar',     BarContainer),
])
def test_plot_kind(eis_dataset, plot_kind, artist_type):
    """对象类型对，且画的数据也对（只查类型的话，数据全画成 0 也能通过）。"""
    plotter = DataPlotter(eis_dataset, channel_x=FREQ, channel_y=ZS_RE) \
        .plot_multiline(plot_kind=plot_kind)

    for k, artist in enumerate(plotter.figures['main'].artists):
        assert isinstance(artist, artist_type)
        x, y = artist_xy(artist)
        np.testing.assert_allclose(x, [1, 10, 100]) 
        np.testing.assert_allclose(y, np.array([10, 20, 30]) * (k + 1))


def test_unknown_plot_kind_raises(eis_dataset):
    with pytest.raises(ValueError, match="不支持的 plot_kind: 'pie'"):
        DataPlotter(eis_dataset).plot_multiline(plot_kind='pie')  # pyright: ignore[reportArgumentType]  故意传错值


@pytest.mark.parametrize("figsize, expected_objects, expected_groups", [
    (None,   (10, 8), (16, 12)),     # 不传：各方法用自己的默认尺寸（与以前相同）
    ((6, 4), (6, 4),  (6, 4)),       # 传了：所有绘图方法都用它
], ids=['default', 'override'])
def test_figsize(eis_dataset, figsize, expected_objects, expected_groups):
    """figsize 是构造参数（步骤 6.2 用户新增），None 时保持各方法原来的尺寸。"""
    plotter = DataPlotter(eis_dataset, groups=Group(eis_dataset, {'A': {'num': [0, 1]}}), figsize=figsize)
    assert tuple(plotter.plot_multiline().figures['main'].fig.get_size_inches()) == expected_objects
    assert tuple(plotter.plot_groups().figures['A'].fig.get_size_inches()) == expected_groups


# ──────────────────────────────────────────────
# 用户格式化器
# ──────────────────────────────────────────────
def test_formatters_are_called(eis_dataset):
    """三种 formatter 都被调用，且拿到的是正确的对象。"""
    received = {}

    def axes_formatter(ax, fig):
        received['axes'] = (ax, fig)

    def lines_formatter(lines):
        received['lines'] = lines

    def legend_formatter(legends):
        received['legends'] = legends

    m = DataPlotter(eis_dataset).plot_multiline(
        axes_formatter=axes_formatter,
        lines_formatter=lines_formatter,
        legend_formatter=legend_formatter,
    ).figures['main']

    assert received['axes'] == (m.axes['left'], m.fig)
    assert received['lines'] == m.artists
    assert received['legends'] == [m.axes['left'].get_legend()]


def test_legend_follows_lines_formatter(eis_dataset):
    """
    回归测试：图例句柄是「创建时」的线条样式快照。
    lines_formatter 改了线型后必须重建图例，否则图例还是实线、和图对不上。
    """
    def dashed(lines):
        for line in lines:
            line.set_linestyle('--')

    ax = DataPlotter(eis_dataset).plot_multiline(lines_formatter=dashed).figures['main'].axes['left']
    assert [h.get_linestyle() for h in ax.get_legend().legend_handles] == ['--'] * 3


# ══════════════════════════════════════════════
# plot_groups：把计划画对（分组规则本身在 test_plot_plan.py；
# 分组参数的约定在 test_backend_parity.py 里对两个绘图器一起测）
# ══════════════════════════════════════════════
def make_groups(dataset):
    """每次新建：Group 会原地格式化传入的配置，不能让测试共用同一个字典。"""
    return Group(dataset, {
        'A': {'num': [0, 1], 'linestyle': 'dash'},
        'B': {'num': [1, 2], 'linestyle': 'dot'},   # 样品 1 被 A、B 共用
    })


@pytest.mark.parametrize("merge, expected", [
    (False, {'A': [0, 1], 'B': [1, 2]}),
    (True,  {'main': [0, 1, 2]}),
], ids=['separate', 'merge'])
def test_one_figure_per_spec(eis_dataset, merge, expected):
    """计划里每张 FigureSpec 画成一张 matplotlib 图：figures 的键是 FigureSpec.key，每张图的线与计划的曲线一一对应。"""
    plotter = DataPlotter(eis_dataset, groups=make_groups(eis_dataset)).plot_groups(merge_groups=merge)

    assert {key: [c.sample_idx for c in drawn.spec.curves] for key, drawn in plotter.figures.items()} == expected
    assert len(plt.get_fignums()) == len(expected)


@pytest.mark.parametrize("style, expected", [
    ({'linestyle': 'dash'},  {'linestyle': '--'}),
    ({'marker': 'circle'},   {'marker': 'o'}),
    ({'color': (255, 0, 0)}, {'color': (1.0, 0.0, 0.0, 1.0)}),
    ({'color': '#00ff00'},   {'color': (0.0, 1.0, 0.0, 1.0)}),
    ({},                     {'linestyle': '-', 'marker': 'None'}),   # 没写：linestyle 默认实线、无标记
], ids=['dash', 'marker', 'rgb', 'hex', 'no-style'])
def test_group_style_translated(eis_dataset, style, expected):
    """
    分组写了的样式翻译成 matplotlib 原生值、应用到这组的线上（标准写法 → style.translate_*(v, 'matplotlib')）。
    哪种模式下哪条线用谁的样式是计划的规则（test_plot_plan.py），这里只用分离模式。
    自定义虚线的翻译见 test_style.py（matplotlib 的 get_linestyle 对任何虚线都返回 '--'，看不出段长）。
    """
    groups = Group(eis_dataset, {'A': {'num': [0, 1], **style}})
    lines = DataPlotter(eis_dataset, groups=groups).plot_groups().figures['A'].artists
    getters = {
        'linestyle': lambda line: line.get_linestyle(),
        'marker':    lambda line: line.get_marker(),
        'color':     lambda line: to_rgba(line.get_color()),
    }
    for line in lines:
        for field, value in expected.items():
            assert getters[field](line) == value, field


@pytest.mark.parametrize("linestyle, expected", [
    ('solid', '-'),
    ('dot',   ':'),
])
def test_group_without_linestyle_uses_default_linestyle(eis_dataset, linestyle, expected):
    """分组没写线型时用绘图器的 linestyle（经 rc_context 生效）。"""
    groups = Group(eis_dataset, {'A': {'num': [0, 1]}})
    plotter = DataPlotter(eis_dataset, groups=groups, linestyle=linestyle).plot_groups()
    assert all(a.get_linestyle() == expected for a in plotter.figures['A'].artists)


def test_linestyle_default_and_standard_words(eis_dataset):
    """linestyle 也是线型入口：默认 'solid'，接受标准词，后端写法 '-' 不再接受。"""
    lines = DataPlotter(eis_dataset).plot_multiline().figures['main'].artists
    assert all(line.get_linestyle() == '-' for line in lines)

    lines = DataPlotter(eis_dataset, linestyle='dash').plot_multiline().figures['main'].artists
    assert all(line.get_linestyle() == '--' for line in lines)

    with pytest.raises(ValueError):
        DataPlotter(eis_dataset, linestyle='-')


def test_lines_formatter_overrides_group_style(eis_dataset):
    """优先级：默认样式 < 分组样式 < 用户 formatter（formatter 最后执行）。"""
    from plotlib.formatters import make_lines_formatter
    plotter = DataPlotter(eis_dataset, groups=make_groups(eis_dataset)).plot_groups(
        lines_formatter=make_lines_formatter(linestyle='dashdot'))
    for drawn in plotter.figures.values():
        assert all(a.get_linestyle() == '-.' for a in drawn.artists)


def test_group_without_config_falls_back_to_plot_multiline(eis_dataset):
    plotter = DataPlotter(eis_dataset).plot_groups()
    assert list(plotter.figures) == ['main']
    assert len(plotter.figures['main'].artists) == 3


# ══════════════════════════════════════════════
# plot_xy（原 subplotter_yy）：每个样品一张 x-y 单线图（如 Nyquist：Zs' vs Zs''）
# ══════════════════════════════════════════════
def test_plot_xy(eis_dataset):
    plotter = DataPlotter(eis_dataset).plot_xy(
        channel_x=ZS_RE, channel_y=ZS_IM)

    assert list(plotter.figures) == [0, 1, 2]           # 以样品号为键
    s1 = plotter.figures[1]
    np.testing.assert_array_equal(s1.artist(1).get_xdata(), [20, 40, 60])
    np.testing.assert_array_equal(s1.artist(1).get_ydata(), [-2, -4, -6])
    assert s1.axes['left'].get_xlabel() == "Zs'(ohm)"
    assert s1.axes['left'].get_ylabel() == "Zs''(ohm)"


def test_plot_xy_keeps_default_color(eis_dataset):
    """一张图只有一条线，不按样品换色：仍是 matplotlib 默认颜色序列的第一个色（计划里色带位置为 None）。"""
    plotter = DataPlotter(eis_dataset).plot_xy(channel_x=ZS_RE, channel_y=ZS_IM)
    for drawn in plotter.figures.values():
        [line] = drawn.artists
        assert to_rgba(line.get_color()) == to_rgba('#1f77b4')


@pytest.mark.parametrize("figsize, expected", [
    (None,   (12, 8)),       # 不传：与以前相同
    ((6, 4), (6, 4)),        # 传了：xy 与双 Y 轴也用它（以前写死 (12, 8)，忽略了 figsize）
], ids=['default', 'override'])
def test_figsize_xy_and_dual_y(eis_dataset, figsize, expected):
    plotter = DataPlotter(eis_dataset, figsize=figsize)
    xy = plotter.plot_xy(channel_x=ZS_RE, channel_y=ZS_IM).figures[0].fig
    assert tuple(xy.get_size_inches()) == expected
    dual = plotter.plot_dual_y(right=(FREQ, ZS_IM)).figures[0].fig
    assert tuple(dual.get_size_inches()) == expected


# ══════════════════════════════════════════════
# plot_dual_y：每个样品一张双 Y 轴图
# ══════════════════════════════════════════════
def test_plot_dual_y(eis_dataset):
    # 两侧故意用不同的 X 列：用同一列的话，右轴错用左轴的 X 也看不出来
    plotter = DataPlotter(eis_dataset).plot_dual_y(
        left=(FREQ, ZS_RE), right=(ZS_RE, ZS_IM))

    assert list(plotter.figures) == [0, 1, 2]
    s0 = plotter.figures[0]
    np.testing.assert_array_equal(s0.artist(0).get_xdata(), [1, 10, 100])
    np.testing.assert_array_equal(s0.artist(0).get_ydata(), [10, 20, 30])
    np.testing.assert_array_equal(s0.artist(0, 'right').get_xdata(), [10, 20, 30])
    np.testing.assert_array_equal(s0.artist(0, 'right').get_ydata(), [-1, -2, -3])
    assert s0.artist(0).get_color() == 'red'
    assert s0.artist(0, 'right').get_color() == 'blue'
    assert s0.axes['right'].get_shared_x_axes().joined(s0.axes['left'], s0.axes['right'])   # 共享 X 轴
    assert len(plt.get_fignums()) == 3                                  # twinx 不新建图窗


def test_plot_dual_y_figure_formatter(eis_dataset):
    """整图回调 (fig, axes)：每个样品调用一次，拿到这张图和左右两根轴（原 custom_formatter(ax1, ax2, fig)）。"""
    received = []
    plotter = DataPlotter(eis_dataset).plot_dual_y(
        right=(FREQ, ZS_IM), figure_formatter=lambda fig, axes: received.append((fig, axes)))
    assert len(received) == 3
    first = plotter.figures[0]
    assert received[0] == (first.fig, first.axes) and set(first.axes) == {'left', 'right'}


# ══════════════════════════════════════════════
# 结果形状（6.5）：四种方法都是 {计划的 key: DrawnFigure}
# ══════════════════════════════════════════════
def make_all_kinds(dataset):
    """四种绘图方法各画一次；返回 {方法名: (plotter, 期望的 key, 期望的轴)}。"""
    return {
        'plot_multiline':  (DataPlotter(dataset).plot_multiline(), ['main'], {'left'}),
        'plot_groups': (DataPlotter(dataset, groups=make_groups(dataset)).plot_groups(), ['A', 'B'], {'left'}),
        'plot_xy': (DataPlotter(dataset).plot_xy(channel_x=ZS_RE, channel_y=ZS_IM),
                          [0, 1, 2], {'left'}),
        'plot_dual_y': (DataPlotter(dataset).plot_dual_y(right=(FREQ, ZS_IM)),
                           [0, 1, 2], {'left', 'right'}),
    }


@pytest.mark.parametrize("method", ['plot_multiline', 'plot_groups', 'plot_xy', 'plot_dual_y'])
def test_result_shape_is_uniform(eis_dataset, method):
    """
    四种方法的结果同一形状：figures 的键是计划的 key；每张图是 DrawnFigure，
    线与 spec.curves 一一对应；axes 单轴图为 {'left'}，双 Y 轴图为 {'left', 'right'}。
    """
    from plotlib.plot_spec import DrawnFigure

    plotter, keys, axes = make_all_kinds(eis_dataset)[method]
    assert list(plotter.figures) == keys
    for key, drawn in plotter.figures.items():
        assert isinstance(drawn, DrawnFigure)
        assert drawn.spec.key == key
        assert len(drawn.artists) == len(drawn.spec.curves)
        assert set(drawn.axes) == axes


def test_artist_lookup_by_sample(eis_dataset):
    """
    按样品号（和轴）取线：分组图里同一样品可在多张图；双 Y 轴图里同一样品有左右两条线，靠 axis 区分。
    找不到 → KeyError。
    """
    group = DataPlotter(eis_dataset, groups=make_groups(eis_dataset)).plot_groups()
    np.testing.assert_array_equal(group.figures['B'].artist(1).get_ydata(), [20, 40, 60])

    dual = DataPlotter(eis_dataset).plot_dual_y(right=(FREQ, ZS_IM)).figures[0]
    assert dual.artist(0).get_color() == 'red'
    assert dual.artist(0, 'right').get_color() == 'blue'

    with pytest.raises(KeyError):
        group.figures['A'].artist(2)            # 样品 2 不在 A 组


@pytest.mark.parametrize("plot_kind", ['scatter', 'bar'])
def test_group_color_applies_to_every_kind(eis_dataset, plot_kind):
    """
    颜色一次赋值（6.5，用户定的方案 B）：分组写的 color 在画的时候就给出，散点、柱状图也生效。
    以前只对折线生效（先用色带色画，再只给折线覆盖样式）。
    """
    groups = Group(eis_dataset, {'A': {'num': [0, 1], 'color': (255, 0, 0)}})
    artist = DataPlotter(eis_dataset, groups=groups).plot_groups(plot_kind=plot_kind).figures['A'].artist(0)
    patches = [artist] if plot_kind == 'scatter' else list(artist)     # 柱状图：每根柱子一个矩形
    for patch in patches:
        np.testing.assert_allclose(patch.get_facecolor()[:3] if plot_kind == 'bar'
                                   else patch.get_facecolor()[0][:3], (1.0, 0.0, 0.0))


# ══════════════════════════════════════════════
# 配色：计划给的色带位置 → matplotlib 颜色（位置怎么算见 test_plan_helpers.py、test_plot_plan.py）
# sparse_dataset 的样品号是 0、5、9
# ══════════════════════════════════════════════
PLASMA = plt.get_cmap('plasma')       # DataPlotter 默认色带


def test_sparse_sample_ids_colors(sparse_dataset):
    """
    三条线依次取色带 0、1/3、2/3 处的颜色。
    回归：曾用「样品号 ÷ 样品数」，5/3、9/3 都超过 1 被截断，样品 5 和 9 同色且不报错。
    """
    lines = DataPlotter(sparse_dataset).plot_multiline().figures['main'].artists
    np.testing.assert_allclose([to_rgba(line.get_color()) for line in lines],
                               [PLASMA(p) for p in (0, 1/3, 2/3)])


def test_bar_colors_follow_plan(sparse_dataset):
    """
    柱状图也按计划的位置上色：合并模式下样品 5、9 都是组首（样品 5）的位置 1/3（步骤 6.2 用户选 A 的行为变化）。
    以前 BarContainer 没有 set_color，合并模式下柱子各用各的样品色。
    """
    groups = Group(sparse_dataset, {'A': {'num': [5, 9]}})
    plotter = DataPlotter(sparse_dataset, groups=groups).plot_groups(merge_groups=True, plot_kind='bar')
    for sample in (5, 9):
        for bar in plotter.figures['main'].artist(sample):   # BarContainer 里每根柱子是一个矩形
            np.testing.assert_allclose(bar.get_facecolor(), PLASMA(1/3))


# ══════════════════════════════════════════════
# 负对数刻度（取绝对值在计划里；刻度文字补负号是 matplotlib 的事）
# ══════════════════════════════════════════════
def test_neglog_x(eis_dataset):
    """X 轴负对数：用 Zs''（全负）当 X。"""
    plotter = DataPlotter(eis_dataset, channel_x=ZS_IM, channel_y=ZS_RE)
    m = plotter.plot_multiline(neglog_x=True).figures['main']

    np.testing.assert_array_equal(m.artists[0].get_xdata(), [1, 2, 3])
    assert m.axes['left'].xaxis.get_major_formatter()(2.0, 0) == '-2.00'


def test_neglog_both_axes_keep_their_own_format(eis_dataset):
    """
    两轴同时负对数时各用各的格式。两轴格式故意设成不同，否则看不出区别。
    回归：X、Y 的 lambda 曾共用一个变量（闭包晚绑定），X 轴用上了 Y 轴的格式。
    """
    from plotlib.formatters import make_axes_formatter

    fmt = make_axes_formatter(x_format='{x:.1f}', y_format='{y:.3f}')
    ax = DataPlotter(eis_dataset, channel_x=ZS_IM, channel_y=ZS_IM).plot_multiline(
        axes_formatter=fmt, neglog_x=True, neglog_y=True).figures['main'].axes['left']

    assert ax.xaxis.get_major_formatter()(2.0, 0) == '-2.0'
    assert ax.yaxis.get_major_formatter()(2.0, 0) == '-2.000'


# ══════════════════════════════════════════════
# matplotlib 后端（6.6）：DataPlotter 只管「生成计划 → 交给后端 → 存结果」，画图全在后端
# ══════════════════════════════════════════════
def test_backend_draws_only_from_plan():
    """
    后端只读计划：手工写一张 FigureSpec（不经过数据集、分组），交给后端画，
    画出的数据、标签、颜色、轴标题就是计划写的。6.7 的 Plotly 后端照同一形状测。
    """
    from plotlib.backends.matplotlib_backend import MatplotlibBackend
    from plotlib.plot_spec import Appearance, CurveSpec, FigureSpec

    spec = FigureSpec(key='hand', x_unit='X(u)', y_unit='Y(u)', curves=[
        CurveSpec(sample_idx=7, x=np.array([0, 1, 2]), y=np.array([3, 4, 5]), label='手写一',
                  group_name=None, color_position=None, style={'color': (255, 0, 0)}),
        CurveSpec(sample_idx=8, x=np.array([0, 1, 2]), y=np.array([6, 7, 8]), label='手写二',
                  group_name=None, color_position=0.5, style={}),
    ])
    drawn = MatplotlibBackend(Appearance(), cmap=None).draw(spec, figsize=(6, 4))

    assert drawn.spec is spec
    first, second = drawn.artist(7), drawn.artist(8)
    np.testing.assert_array_equal(first.get_ydata(), [3, 4, 5])
    assert first.get_label() == '手写一'
    assert to_rgba(first.get_color()) == (1.0, 0.0, 0.0, 1.0)                 # 计划写的颜色
    np.testing.assert_allclose(to_rgba(second.get_color()), PLASMA(0.5))      # 计划给的色带位置
    assert drawn.axes['left'].get_xlabel() == 'X(u)'
    assert tuple(drawn.fig.get_size_inches()) == (6, 4)


def test_backend_choice(eis_dataset):
    """backend 参数：默认 matplotlib；'plotly' 用 Plotly 后端（6.7 起）；写错名字列出可选值。"""
    assert DataPlotter(eis_dataset).backend.name == 'matplotlib'
    assert DataPlotter(eis_dataset, backend='plotly').backend.name == 'plotly'
    with pytest.raises(ValueError, match='matplotlib'):
        DataPlotter(eis_dataset, backend='pie')


def test_appearance_translated_to_rc_params():
    """外观参数是后端无关的公共参数（Appearance），由 matplotlib 后端翻译成 rc_params。"""
    from plotlib.backends.matplotlib_backend import MatplotlibBackend
    from plotlib.plot_spec import Appearance

    backend = MatplotlibBackend(Appearance(font_size=30, linestyle='dash'), cmap=None)
    assert backend.rc_params['font.size'] == 30
    assert backend.rc_params['lines.linestyle'] == '--'           # 标准写法翻译成 matplotlib 原生值


# ══════════════════════════════════════════════
# 默认排版（6.6b 起由 layouts.py 的排版预设决定）：改之前先写好，保证抽成预设后图不变
# ══════════════════════════════════════════════
def draw_layout(dataset, layout):
    """按版式各画一张图，返回 (DrawnFigure, 左轴, 右轴或 None)。"""
    plotter = DataPlotter(dataset, channel_x=FREQ, channel_y=ZS_RE)
    drawn = {
        'multiline': lambda: plotter.plot_multiline().figures['main'],
        'xy':        lambda: plotter.plot_xy(channel_x=ZS_RE, channel_y=ZS_IM).figures[0],
        'dual_y':    lambda: plotter.plot_dual_y(right=(FREQ, ZS_IM)).figures[0],
    }[layout]()
    return drawn, drawn.axes['left'], drawn.axes.get('right')


@pytest.mark.parametrize("layout, legend_loc, draggable", [
    ('multiline', 6, True),       # 6 = 'center left'，配合 bbox (1, 0.5) 放在图外右侧
    ('xy',        4, False),      # 4 = 'lower right'
    ('dual_y',    4, False),
])
def test_layout_legend(eis_dataset, layout, legend_loc, draggable):
    """图例：多线图放图外右侧且可拖动；xy、双 Y 轴在右下角。双 Y 轴只有左轴有图例。"""
    _, left, right = draw_layout(eis_dataset, layout)
    legend = left.get_legend()
    assert legend._loc == legend_loc
    assert legend.get_draggable() == draggable
    if right is not None:
        assert right.get_legend() is None


@pytest.mark.parametrize("layout, axis, value, text", [
    ('multiline', 'x',  1.234,  '1.23'),
    ('multiline', 'y',  1.234,  '1.23'),
    ('xy',        'y',  1.234,  '1.2340'),
    ('dual_y',    'y2', 1.234,  '1.2340'),
])
def test_layout_tick_format(eis_dataset, layout, axis, value, text):
    """刻度格式：多线图 x、y 两位小数；xy 的 y、双 Y 轴的右轴四位小数。"""
    _, left, right = draw_layout(eis_dataset, layout)
    target = {'x': left.xaxis, 'y': left.yaxis, 'y2': right.yaxis if right else None}[axis]
    assert target.get_major_formatter()(value, 0) == text


@pytest.mark.parametrize("layout, side, value", [
    ('multiline', 'right', 0.75),
    ('xy',        'left',  0.15),
    ('dual_y',    'right', 0.85),
])
def test_layout_margins(eis_dataset, layout, side, value):
    """边距：绘图区边界占画布的比例（多线图右边给图例让位）。"""
    drawn, _, _ = draw_layout(eis_dataset, layout)
    assert getattr(drawn.fig.subplotpars, side) == pytest.approx(value)


def test_layout_dual_y_axis_colors(eis_dataset):
    """双 Y 轴：左轴（标题、刻度文字、轴线）红，右轴蓝；两条线也是红、蓝。"""
    drawn, left, right = draw_layout(eis_dataset, 'dual_y')
    assert right is not None                    # 双 Y 轴图一定有右轴；也让类型检查器知道
    red, blue = to_rgba('red'), to_rgba('blue')
    assert to_rgba(left.yaxis.label.get_color()) == red
    assert to_rgba(right.yaxis.label.get_color()) == blue
    assert to_rgba(left.spines['left'].get_edgecolor()) == red
    assert to_rgba(right.spines['right'].get_edgecolor()) == blue
    assert to_rgba(left.yaxis.get_ticklabels()[0].get_color()) == red
    assert to_rgba(drawn.artist(0).get_color()) == red
    assert to_rgba(drawn.artist(0, 'right').get_color()) == blue


def test_appearance_dpi(eis_dataset):
    """dpi 是显式的外观参数（默认 100，与 matplotlib 默认相同）：matplotlib 设成 figure.dpi；DataPlotter 有同名参数。"""
    from plotlib.backends.matplotlib_backend import MatplotlibBackend
    from plotlib.plot_spec import Appearance

    assert Appearance().dpi == 100
    assert MatplotlibBackend(Appearance(dpi=150), cmap=None).rc_params['figure.dpi'] == 150
    fig = DataPlotter(eis_dataset, dpi=150).plot_multiline().figures['main'].fig
    assert fig.dpi == 150
