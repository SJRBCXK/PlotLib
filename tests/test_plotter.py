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
import re

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.collections import PathCollection
from matplotlib.colors import to_rgba
from matplotlib.container import BarContainer
from matplotlib.lines import Line2D
from numpy.typing import NDArray

from plotlib.group import Group
from plotlib.plot_spec import AxisStyle, LegendStyle, LineStyle
from plotlib.plotter import DataPlotter

FREQ, ZS_RE, ZS_IM = 0, 1, 2      # 通道号


def legend_texts(ax):
    return [t.get_text() for t in ax.get_legend().get_texts()]


# ══════════════════════════════════════════════
# plot_multiline：所有样品画在同一张图
# ══════════════════════════════════════════════
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


@pytest.mark.parametrize("method", ['plot_multiline', 'plot_xy'])
def test_legend_stays_in_place_after_lines_formatter(eis_dataset, method):
    """
    回归（第三方审查 D）：lines_formatter 之后重建的图例留在原位、能否拖动不变（两种图例位置：图外右侧、图内右下）。
    曾把已是像素坐标的锚点再按坐标轴换算一次，图例被移到画布外几十万像素处。渲染后才看得出来。
    """
    def legend_after_draw(**kwargs):
        drawn = next(iter(getattr(DataPlotter(eis_dataset), method)(**kwargs).figures.values()))
        drawn.fig.canvas.draw()
        legend = drawn.axes['left'].get_legend()
        return legend.get_window_extent().p0, legend.get_draggable()

    before, draggable_before = legend_after_draw()
    after, draggable_after = legend_after_draw(lines_formatter=lambda lines: None)
    np.testing.assert_allclose(after, before)
    assert draggable_after == draggable_before


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
    """分组没写线型时用绘图器的全局线型 lines=LineStyle(linestyle=...)（经 rc_context 生效）。"""
    groups = Group(eis_dataset, {'A': {'num': [0, 1]}})
    plotter = DataPlotter(eis_dataset, groups=groups, lines=LineStyle(linestyle=linestyle)).plot_groups()
    assert all(a.get_linestyle() == expected for a in plotter.figures['A'].artists)


def test_global_lines_and_standard_words(eis_dataset):
    """
    全局的线 lines=LineStyle(...)（原 line_width / linestyle 参数）：默认实线、线宽 3；只写要改的，其余沿用默认；
    只收标准写法（后端写法 '-' 报错）；不收颜色（颜色按样品配色）。
    """
    lines = DataPlotter(eis_dataset).plot_multiline().figures['main'].artists
    assert all((line.get_linestyle(), line.get_linewidth()) == ('-', 3) for line in lines)

    lines = DataPlotter(eis_dataset, lines=LineStyle(linestyle='dash')).plot_multiline().figures['main'].artists
    assert all((line.get_linestyle(), line.get_linewidth()) == ('--', 3) for line in lines)

    with pytest.raises(ValueError):
        DataPlotter(eis_dataset, lines=LineStyle(linestyle='-'))
    with pytest.raises(ValueError, match='颜色'):
        DataPlotter(eis_dataset, lines=LineStyle(color='red'))


def test_lines_formatter_overrides_group_style(eis_dataset):
    """优先级：默认样式 < 分组样式 < 用户 formatter（formatter 最后执行）。"""
    from plotlib.formatters import make_lines_formatter
    plotter = DataPlotter(eis_dataset, groups=make_groups(eis_dataset)).plot_groups(
        lines_formatter=make_lines_formatter(LineStyle(linestyle='dashdot')))
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
    """
    X 轴负对数：用 Zs''（全负）当 X。多线图横轴没有预设格式，用的是 matplotlib 默认格式器：
    它要渲染时收到刻度位置才写得出数字，所以先渲染再看刻度文字。
    """
    plotter = DataPlotter(eis_dataset, channel_x=ZS_IM, channel_y=ZS_RE)
    m = plotter.plot_multiline(neglog_x=True).figures['main']

    np.testing.assert_array_equal(m.artists[0].get_xdata(), [1, 2, 3])
    m.fig.canvas.draw()
    labels = [label.get_text() for label in m.axes['left'].get_xticklabels() if label.get_text()]
    assert labels and all(re.fullmatch(r'-\d+(\.\d+)?', text) for text in labels)


def test_neglog_both_axes_keep_their_own_format(eis_dataset):
    """
    两轴同时负对数时各用各的格式。两轴格式故意设成不同，否则看不出区别。
    回归：X、Y 的 lambda 曾共用一个变量（闭包晚绑定），X 轴用上了 Y 轴的格式。
    """
    from plotlib.formatters import make_axes_formatter

    fmt = make_axes_formatter(x=AxisStyle(format='{x:.1f}'), y=AxisStyle(format='{y:.3f}'))
    ax = DataPlotter(eis_dataset, channel_x=ZS_IM, channel_y=ZS_IM).plot_multiline(
        axes_formatter=fmt, neglog_x=True, neglog_y=True).figures['main'].axes['left']

    assert ax.xaxis.get_major_formatter()(2.0, 0) == '-2.0'
    assert ax.yaxis.get_major_formatter()(2.0, 0) == '-2.000'


@pytest.mark.parametrize("draw, axis", [
    (lambda ds: DataPlotter(ds).plot_xy(channel_x=ZS_IM, channel_y=ZS_RE, neglog_x=True), 'x'),
    (lambda ds: DataPlotter(ds).plot_dual_y(left=(FREQ, ZS_IM), right=(FREQ, ZS_RE), neglog_y=True), 'y'),
    (lambda ds: DataPlotter(ds).plot_dual_y(left=(ZS_IM, ZS_RE), right=(ZS_IM, ZS_RE),
                                            neglog_x=True, neglog_x2=True), 'x'),
], ids=['xy_x', 'dual_y_left_y', 'dual_y_shared_x'])
def test_neglog_ticks_render_numbers(eis_dataset, draw, axis):
    """
    回归（第三方审查 C）：渲染后每个刻度都是「一个负号 + 数字」。这几根轴用的是 matplotlib 默认刻度格式（版式没设）。
    曾只包装了默认格式器的调用，它收不到本轮的刻度位置，渲染出来只剩 '-'。
    双 Y 轴左右共用 X 轴：只加一次负号（'x2' 在约定里是上轴，不作用在共用的 X 轴上，与 Plotly 一致）。
    """
    drawn = draw(eis_dataset).figures[0]
    drawn.fig.canvas.draw()
    texts = [t.get_text() for t in getattr(drawn.axes['left'], f'get_{axis}ticklabels')() if t.get_text()]
    assert texts and all(re.fullmatch(r'-\d+(\.\d+)?', t) for t in texts), texts


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
                  group_name=None, color_position=None, style=LineStyle(color=(255, 0, 0))),
        CurveSpec(sample_idx=8, x=np.array([0, 1, 2]), y=np.array([6, 7, 8]), label='手写二',
                  group_name=None, color_position=0.5),
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
    """
    外观参数是后端无关的公共参数（Appearance），由 matplotlib 后端翻译成 rc_params；
    样式对象按「库默认 < 用户写的那一层」叠加（只写线型，线宽仍是默认 3）。
    """
    from plotlib.backends.matplotlib_backend import MatplotlibBackend
    from plotlib.plot_spec import Appearance, FrameStyle, LegendStyle

    backend = MatplotlibBackend(Appearance(font_size=30, lines=LineStyle(linestyle='dash'),
                                           frame=FrameStyle(width=2), legend=LegendStyle(font_size=12)), cmap=None)
    assert backend.rc_params['font.size'] == 30
    assert backend.rc_params['lines.linestyle'] == '--'           # 标准写法翻译成 matplotlib 原生值
    assert backend.rc_params['lines.linewidth'] == 3              # 没写：库默认
    assert backend.rc_params['axes.linewidth'] == 2
    assert backend.rc_params['legend.fontsize'] == backend.rc_params['legend.title_fontsize'] == 12


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
    ('dual_y',    4, False),      # 'lower right' 配合 bbox (1, 1.02)：图外上方、右对齐（位置见下一条测试）
])
def test_layout_legend(eis_dataset, layout, legend_loc, draggable):
    """图例：多线图放图外右侧且可拖动；xy 在右下角；双 Y 轴在图外上方。一张图只有一个图例，建在左轴上。"""
    _, left, right = draw_layout(eis_dataset, layout)
    legend = left.get_legend()
    assert legend._loc == legend_loc
    assert legend.get_draggable() == draggable
    if right is not None:
        assert right.get_legend() is None


@pytest.mark.parametrize("layout, axis, value, text", [
    ('multiline', 'y',  1.234,  '1.23'),
    ('xy',        'y',  1.234,  '1.2340'),
    ('dual_y',    'y2', 1.234,  '1.2340'),
])
def test_layout_tick_format(eis_dataset, layout, axis, value, text):
    """刻度格式：多线图 y 两位小数；xy 的 y、双 Y 轴的右轴四位小数。"""
    _, left, right = draw_layout(eis_dataset, layout)
    target = {'x': left.xaxis, 'y': left.yaxis, 'y2': right.yaxis if right else None}[axis]
    assert target.get_major_formatter()(value, 0) == text


@pytest.mark.parametrize("layout, side, value", [
    ('multiline', 'right', 0.75),
    ('xy',        'left',  0.15),
    ('dual_y',    'right', 0.85),
    ('dual_y',    'top',   0.85),     # 上边给图外上方的图例让位
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


@pytest.mark.parametrize("layout, top, right", [
    ('multiline', False, False),      # 默认无框（用户定）
    ('xy',        False, False),
    ('dual_y',    True,  True),       # 双 Y 轴：左右各有一根轴，画完整的框（用户定）
])
def test_layout_frame(eis_dataset, layout, top, right):
    """边框（FrameStyle）：多线、xy 只有左边和下边；双 Y 轴画完整的框，右边是右轴自己的（蓝色）轴线。"""
    _, left, right_ax = draw_layout(eis_dataset, layout)
    assert left.spines['top'].get_visible() == top
    if right_ax is None:
        assert left.spines['right'].get_visible() == right
    else:
        assert right_ax.spines['right'].get_visible()
        assert to_rgba(right_ax.spines['right'].get_edgecolor()) == to_rgba('blue')
        assert not right_ax.spines['left'].get_visible()          # 不盖住左轴的红色轴线


def test_global_styles_override_preset(eis_dataset):
    """
    DataPlotter 里写的全局样式盖过版式预设（库默认 < 预设 < 全局）：
    多线图预设无框、图例在图外右侧；全局写了 top=True、position='upper left' 就照全局画，没写的（拖动）仍用预设。
    """
    from plotlib.plot_spec import FrameStyle

    ax = DataPlotter(eis_dataset, frame=FrameStyle(top=True), legend=LegendStyle(position='upper left')) \
        .plot_multiline().figures['main'].axes['left']
    assert ax.spines['top'].get_visible() and not ax.spines['right'].get_visible()
    legend = ax.get_legend()
    assert legend._loc == 2 and legend.get_draggable()        # 2 = 'upper left'；拖动来自预设


def test_axes_formatter_keeps_preset_tick_format(eis_dataset):
    """
    轴工厂只改写了的：只把 X 轴改成对数，Y 轴仍是多线图预设的两位小数。
    回归（样式对象化时修）：工厂曾总是调用 set_yscale('linear')，把预设的刻度格式重置成自动格式。
    多线图预设不给 X 轴写格式（X 轴常改成对数轴，两位小数会把 1e-3 写成 0.00），对数轴用 matplotlib 默认的 10 的幂。
    """
    from matplotlib.ticker import LogFormatterSciNotation

    from plotlib.formatters import make_axes_formatter

    ax = DataPlotter(eis_dataset).plot_multiline(
        axes_formatter=make_axes_formatter(x=AxisStyle(scale='log'))).figures['main'].axes['left']
    assert ax.get_xscale() == 'log'
    assert isinstance(ax.xaxis.get_major_formatter(), LogFormatterSciNotation)
    assert ax.yaxis.get_major_formatter()(1.234, 0) == '1.23'


def test_layout_dual_y_legend(eis_dataset):
    """
    双 Y 轴图例（2026-11-20，参照用户的 Origin 图）：左右两条线都进图例（红、蓝），每条写自己的单位，
    图例标题是样品名；放在绘图区上方、右边与绘图区对齐，整个在画布内。渲染后才知道位置，先 draw。
    """
    drawn, left, right = draw_layout(eis_dataset, 'dual_y')
    assert right is not None
    drawn.fig.canvas.draw()
    legend = left.get_legend()

    assert right.get_legend() is None                       # 仍只有一个图例，建在左轴上
    assert legend.get_title().get_text() == 'S0'
    assert [t.get_text() for t in legend.get_texts()] == ["Zs'(ohm)", "Zs''(ohm)"]
    assert [to_rgba(h.get_color()) for h in legend.legend_handles] == [to_rgba('red'), to_rgba('blue')]
    box, plot_area = legend.get_window_extent(), left.get_window_extent()
    assert box.y0 >= plot_area.y1                           # 在绘图区上方
    assert box.x1 == pytest.approx(plot_area.x1, abs=2)     # 右边对齐
    assert box.y1 <= drawn.fig.bbox.y1                      # 没有超出画布


def test_dual_y_legend_follows_right_lines_and_keeps_legend_formatter(eis_dataset):
    """
    图例里有右线：右轴的 lines_formatter 改了线色，图例跟着变；左轴 legend_formatter 设的字号、图例标题不能被重建冲掉。
    所以各轴的轴、线回调都执行完、图例按需重建一次之后，才调用图例回调。
    """
    from plotlib.formatters import make_legend_formatter, make_lines_formatter

    drawn = DataPlotter(eis_dataset).plot_dual_y(
        right=(FREQ, ZS_IM),
        right_lines_formatter=make_lines_formatter(LineStyle(color='green')),
        legend_formatter=make_legend_formatter(LegendStyle(font_size=7))).figures[0]
    legend = drawn.axes['left'].get_legend()

    assert [h.get_color() for h in legend.legend_handles] == ['red', 'green']
    assert [t.get_fontsize() for t in legend.get_texts()] == [7, 7]
    assert legend.get_title().get_text() == 'S0'


# ══════════════════════════════════════════════
# 刻度 TickStyle（2026-11-20）：DataPlotter(ticks=...) 全局，axes formatter 的 ticks 单轴覆盖。渲染后断言
# ══════════════════════════════════════════════
def drawn_ticks(drawn, side='left', axis='x'):
    """渲染后取一根轴的 (主刻度, 次刻度位置, 次刻度文字)。"""
    drawn.fig.canvas.draw()
    target = getattr(drawn.axes[side], f'{axis}axis')
    labels = [t.get_text() for t in target.get_minorticklabels() if t.get_text()]
    return target.get_major_ticks(), list(target.get_minorticklocs()), labels


def test_ticks_default(eis_dataset):
    """默认：主刻度 6 × 3 磅、朝外；线性轴也显示次刻度（3 磅长），次刻度不写文字。"""
    major, minor_locs, minor_labels = drawn_ticks(DataPlotter(eis_dataset).plot_multiline().figures['main'])
    assert {(t.tick1line.get_markersize(), t.tick1line.get_markeredgewidth()) for t in major} == {(6, 3)}
    assert minor_locs
    assert minor_labels == []


def test_ticks_global_settings(eis_dataset):
    """DataPlotter(ticks=...) 只写要改的，其余沿用默认：主刻度长 10（宽仍 3），刻度文字 12 磅 serif。"""
    from plotlib.plot_spec import TickStyle

    drawn = DataPlotter(eis_dataset, ticks=TickStyle(length=10, label_size=12, label_font='serif')) \
        .plot_multiline().figures['main']
    major, _, _ = drawn_ticks(drawn)
    assert {(t.tick1line.get_markersize(), t.tick1line.get_markeredgewidth()) for t in major} == {(10, 3)}
    label = drawn.axes['left'].xaxis.get_ticklabels()[0]
    assert label.get_fontsize() == 12 and label.get_fontfamily() == ['serif']


def test_ticks_local_minor_on_log_axis_overrides_global(eis_dataset):
    """
    全局关掉次刻度、单根轴改成对数并写 minor=True：这根轴显示次刻度（单轴 formatter 盖过全局）。
    回归（1.0 发布前复审）：对数轴要显示次刻度时只「保留默认定位器」，它仍算默认值，后端补全局设置时又被关掉。
    """
    from plotlib.formatters import make_axes_formatter
    from plotlib.plot_spec import TickStyle

    drawn = DataPlotter(eis_dataset, ticks=TickStyle(minor=False)).plot_multiline(
        axes_formatter=make_axes_formatter(x=AxisStyle(scale='log'), ticks=TickStyle(minor=True))).figures['main']
    assert drawn_ticks(drawn, axis='x')[1] != []          # 对数轴
    assert drawn_ticks(drawn, axis='y')[1] != []          # 轴工厂的 ticks 管这根轴的 X、Y 两个方向（线性轴本来就没问题）


def test_ticks_minor_switch_survives_scale_change(eis_dataset):
    """
    关掉次刻度后，轴工厂把 X 轴改成对数也不会冒出次刻度：
    改刻度类型时 matplotlib 会把次刻度的定位器重置成默认值，后端在用户回调之后补上全局设置（只补还是默认值的）。
    """
    from plotlib.formatters import make_axes_formatter
    from plotlib.plot_spec import TickStyle

    drawn = DataPlotter(eis_dataset, ticks=TickStyle(minor=False)).plot_multiline(
        axes_formatter=make_axes_formatter(x=AxisStyle(scale='log'))).figures['main']
    assert drawn_ticks(drawn, axis='x')[1] == []
    assert drawn_ticks(drawn, axis='y')[1] == []


@pytest.mark.parametrize("minor_labels, check", [
    ('none',  lambda labels: labels == []),
    ('short', lambda labels: labels and set(labels) <= set('23456789')),     # 对数轴只写首位数字：2、3 … 9
    ('full',  lambda labels: len(labels) >= 8),                              # 每个次刻度都写完整数值
])
def test_minor_labels_on_log_axis(eis_dataset, minor_labels, check):
    """次刻度文字（对数轴，频率 1 ~ 100）：none 不写；short 只写首位数字；full 写完整数值。"""
    from plotlib.formatters import make_axes_formatter
    from plotlib.plot_spec import TickStyle

    drawn = DataPlotter(eis_dataset, ticks=TickStyle(minor_labels=minor_labels)).plot_multiline(
        axes_formatter=make_axes_formatter(x=AxisStyle(scale='log'))).figures['main']
    labels = drawn_ticks(drawn, axis='x')[2]
    assert check(labels), labels


def test_minor_labels_style_matplotlib_only(eis_dataset):
    """
    matplotlib 的次刻度文字可以单独设字号（Plotly 不行，见 test_plotly_backend.py）；线性轴上 full 也能写文字。
    线性轴上的 short 不写（首位数字只在对数轴上有意义，与 Plotly 一致；曾等同 full，画出来每个次刻度都标数、挤成一片）。
    """
    from plotlib.plot_spec import TickStyle

    drawn = DataPlotter(eis_dataset, ticks=TickStyle(minor_labels='full', minor_label_size=8)) \
        .plot_multiline().figures['main']
    _, _, labels = drawn_ticks(drawn, axis='y')
    assert labels
    sizes = {t.get_fontsize() for t in drawn.axes['left'].yaxis.get_minorticklabels() if t.get_text()}
    assert sizes == {8}

    short = DataPlotter(eis_dataset, ticks=TickStyle(minor_labels='short')).plot_multiline().figures['main']
    assert drawn_ticks(short, axis='y')[2] == []


def test_appearance_dpi(eis_dataset):
    """dpi 是显式的外观参数（默认 100，与 matplotlib 默认相同）：matplotlib 设成 figure.dpi；DataPlotter 有同名参数。"""
    from plotlib.backends.matplotlib_backend import MatplotlibBackend
    from plotlib.plot_spec import Appearance

    assert Appearance().dpi == 100
    assert MatplotlibBackend(Appearance(dpi=150), cmap=None).rc_params['figure.dpi'] == 150
    fig = DataPlotter(eis_dataset, dpi=150).plot_multiline().figures['main'].fig
    assert fig.dpi == 150
