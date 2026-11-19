"""
测试对象：src/plotlib/plotter.py 的 DataPlotter

思路（Step 5）：不看图、不比像素，而是检查 matplotlib 对象的属性。
DataPlotter 把画出的东西都存在 self.axesset 里，测试就从这里取：
  - 线的数据        line.get_xdata() / get_ydata()
  - 线型、颜色      line.get_linestyle() / get_color()
  - 坐标轴标题      ax.get_xlabel() / get_ylabel()
  - 图例文字        [t.get_text() for t in ax.get_legend().get_texts()]
  - 当前打开的图窗  plt.get_fignums()

后端在 conftest.py 里切到了 Agg（不弹窗），每个测试结束自动 plt.close('all')。

分层（2026-11-19 整理）：分组规则（去重、先到先得、组首色、样式归属、色带位置）只在 test_plot_plan.py 测；
这里只测 matplotlib 把计划画对（每张 FigureSpec 一张图、位置 → 颜色、样式翻译）和它独有的功能
（formatter、图例、plot_style、figsize、负对数刻度、Y-Y / 双 Y 轴）。与 Plotly 的对照在 test_backend_parity.py。

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
# plot_objects：所有样品画在同一张图
# ══════════════════════════════════════════════
def test_plot_objects_one_line_per_sample(eis_dataset):
    plotter = DataPlotter(eis_dataset, plotdataRowNum_x=FREQ, plotdataRowNum_y=ZS_RE)
    plotter.plot_objects()

    assert list(plotter.axesset) == ['main']
    assert len(plotter.axesset['main']['artists']) == 3
    assert len(plt.get_fignums()) == 1


def test_plot_objects_labels(eis_dataset):
    """坐标轴标题取单位，图例取样品名。"""
    ax = DataPlotter(eis_dataset, plotdataRowNum_x=FREQ, plotdataRowNum_y=ZS_RE) \
        .plot_objects().axesset['main']['ax']

    assert ax.get_xlabel() == 'Frequency(Hz)'
    assert ax.get_ylabel() == "Zs'(ohm)"
    assert legend_texts(ax) == ['S0', 'S1', 'S2']


def test_plotrange_limits_points(eis_dataset):
    plotter = DataPlotter(eis_dataset, plotrange=2).plot_objects()
    for line in plotter.axesset['main']['artists']:
        assert len(line.get_xdata()) == 2


def test_neglog_y(eis_dataset):
    """负对数：数据取绝对值后画，刻度文字再补回负号。Zs'' 全为负数，正好用来测。"""
    plotter = DataPlotter(eis_dataset, plotdataRowNum_x=FREQ, plotdataRowNum_y=ZS_IM)
    plotter.plot_objects(NegLogScale_y=True)
    m = plotter.axesset['main']

    np.testing.assert_array_equal(m['artists'][0].get_ydata(), [1, 2, 3])
    assert m['ax'].yaxis.get_major_formatter()(2.0, 0) == '-2.00'


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
    plotter = DataPlotter(eis_dataset, plotdataRowNum_x=FREQ, plotdataRowNum_y=ZS_RE) \
        .plot_objects(plot_kind=plot_kind)

    for k, artist in enumerate(plotter.axesset['main']['artists']):
        assert isinstance(artist, artist_type)
        x, y = artist_xy(artist)
        np.testing.assert_allclose(x, [1, 10, 100]) 
        np.testing.assert_allclose(y, np.array([10, 20, 30]) * (k + 1))


def test_unknown_plot_kind_raises(eis_dataset):
    with pytest.raises(ValueError, match="不支持的 plot_kind: 'pie'"):
        DataPlotter(eis_dataset).plot_objects(plot_kind='pie')


@pytest.mark.parametrize("figsize, expected_objects, expected_groups", [
    (None,   (10, 8), (16, 12)),     # 不传：各方法用自己的默认尺寸（与以前相同）
    ((6, 4), (6, 4),  (6, 4)),       # 传了：所有绘图方法都用它
], ids=['default', 'override'])
def test_figsize(eis_dataset, figsize, expected_objects, expected_groups):
    """figsize 是构造参数（步骤 6.2 用户新增），None 时保持各方法原来的尺寸。"""
    plotter = DataPlotter(eis_dataset, groups=Group(eis_dataset, {'A': {'num': [0, 1]}}), figsize=figsize)
    assert tuple(plotter.plot_objects().axesset['main']['fig'].get_size_inches()) == expected_objects
    assert tuple(plotter.group_plotter().axesset['A']['fig'].get_size_inches()) == expected_groups


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

    m = DataPlotter(eis_dataset).plot_objects(
        axes_formatter=axes_formatter,
        lines_formatter=lines_formatter,
        legend_formatter=legend_formatter,
    ).axesset['main']

    assert received['axes'] == (m['ax'], m['fig'])
    assert received['lines'] == m['artists']
    assert received['legends'] == [m['ax'].get_legend()]


def test_legend_follows_lines_formatter(eis_dataset):
    """
    回归测试：图例句柄是「创建时」的线条样式快照。
    lines_formatter 改了线型后必须重建图例，否则图例还是实线、和图对不上。
    """
    def dashed(lines):
        for line in lines:
            line.set_linestyle('--')

    ax = DataPlotter(eis_dataset).plot_objects(lines_formatter=dashed).axesset['main']['ax']
    assert [h.get_linestyle() for h in ax.get_legend().legend_handles] == ['--'] * 3


# ══════════════════════════════════════════════
# group_plotter：把计划画对（分组规则本身在 test_plot_plan.py；
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
    """计划里每张 FigureSpec 画成一张 matplotlib 图：axesset 的键是 FigureSpec.key，artists 以样品号为键。"""
    plotter = DataPlotter(eis_dataset, groups=make_groups(eis_dataset)).group_plotter(merge_groups=merge)

    assert {key: list(entry['artists']) for key, entry in plotter.axesset.items()} == expected
    assert len(plt.get_fignums()) == len(expected)


@pytest.mark.parametrize("style, expected", [
    ({'linestyle': 'dash'},  {'linestyle': '--'}),
    ({'marker': 'circle'},   {'marker': 'o'}),
    ({'color': (255, 0, 0)}, {'color': (1.0, 0.0, 0.0, 1.0)}),
    ({'color': '#00ff00'},   {'color': (0.0, 1.0, 0.0, 1.0)}),
    ({},                     {'linestyle': '-', 'marker': 'None'}),   # 没写：plot_style 默认实线、无标记
], ids=['dash', 'marker', 'rgb', 'hex', 'no-style'])
def test_group_style_translated(eis_dataset, style, expected):
    """
    分组写了的样式翻译成 matplotlib 原生值、应用到这组的线上（标准写法 → style.translate_*(v, 'matplotlib')）。
    哪种模式下哪条线用谁的样式是计划的规则（test_plot_plan.py），这里只用分离模式。
    自定义虚线的翻译见 test_style.py（matplotlib 的 get_linestyle 对任何虚线都返回 '--'，看不出段长）。
    """
    groups = Group(eis_dataset, {'A': {'num': [0, 1], **style}})
    lines = DataPlotter(eis_dataset, groups=groups).group_plotter().axesset['A']['artists'].values()
    getters = {
        'linestyle': lambda line: line.get_linestyle(),
        'marker':    lambda line: line.get_marker(),
        'color':     lambda line: to_rgba(line.get_color()),
    }
    for line in lines:
        for field, value in expected.items():
            assert getters[field](line) == value, field


@pytest.mark.parametrize("plot_style, expected", [
    ('solid', '-'),
    ('dot',   ':'),
])
def test_group_without_linestyle_uses_plot_style(eis_dataset, plot_style, expected):
    """分组没写线型时用绘图器的 plot_style（经 rc_context 生效）。"""
    groups = Group(eis_dataset, {'A': {'num': [0, 1]}})
    plotter = DataPlotter(eis_dataset, groups=groups, plot_style=plot_style).group_plotter()
    assert all(a.get_linestyle() == expected for a in plotter.axesset['A']['artists'].values())


def test_plot_style_default_and_standard_words(eis_dataset):
    """plot_style 也是线型入口：默认 'solid'，接受标准词，后端写法 '-' 不再接受。"""
    lines = DataPlotter(eis_dataset).plot_objects().axesset['main']['artists']
    assert all(line.get_linestyle() == '-' for line in lines)

    lines = DataPlotter(eis_dataset, plot_style='dash').plot_objects().axesset['main']['artists']
    assert all(line.get_linestyle() == '--' for line in lines)

    with pytest.raises(ValueError):
        DataPlotter(eis_dataset, plot_style='-')


def test_lines_formatter_overrides_group_style(eis_dataset):
    """优先级：默认样式 < 分组样式 < 用户 formatter（formatter 最后执行）。"""
    from plotlib.formatters import make_lines_formatter
    plotter = DataPlotter(eis_dataset, groups=make_groups(eis_dataset)).group_plotter(
        lines_formatter=make_lines_formatter(linestyle='dashdot'))
    for entry in plotter.axesset.values():
        assert all(a.get_linestyle() == '-.' for a in entry['artists'].values())


def test_group_without_config_falls_back_to_plot_objects(eis_dataset):
    plotter = DataPlotter(eis_dataset).group_plotter()
    assert list(plotter.axesset) == ['main']
    assert len(plotter.axesset['main']['artists']) == 3


# ══════════════════════════════════════════════
# subplotter_yy：每个样品一张 Y-Y 图（如 Nyquist：Zs' vs Zs''）
# ══════════════════════════════════════════════
def test_subplotter_yy(eis_dataset):
    plotter = DataPlotter(eis_dataset).subplotter_yy(
        plotdataRowNum_Y1=ZS_RE, plotdataRowNum_Y2=ZS_IM)

    assert list(plotter.axesset) == [0, 1, 2]           # 以样品号为键
    s1 = plotter.axesset[1]
    np.testing.assert_array_equal(s1['artist'].get_xdata(), [20, 40, 60])
    np.testing.assert_array_equal(s1['artist'].get_ydata(), [-2, -4, -6])
    assert s1['ax'].get_xlabel() == "Zs'(ohm)"
    assert s1['ax'].get_ylabel() == "Zs''(ohm)"


# ══════════════════════════════════════════════
# subplotter_xyy：每个样品一张双 Y 轴图
# ══════════════════════════════════════════════
def test_subplotter_xyy(eis_dataset):
    # 两侧故意用不同的 X 列：用同一列的话，右轴错用左轴的 X 也看不出来
    plotter = DataPlotter(eis_dataset).subplotter_xyy(
        plotdataRowNum_X1=FREQ, plotdataRowNum_Y1=ZS_RE,
        plotdataRowNum_X2=ZS_RE, plotdataRowNum_Y2=ZS_IM)

    assert list(plotter.axesset) == [0, 1, 2]
    s0 = plotter.axesset[0]
    np.testing.assert_array_equal(s0['artist_Y1'].get_xdata(), [1, 10, 100])
    np.testing.assert_array_equal(s0['artist_Y1'].get_ydata(), [10, 20, 30])
    np.testing.assert_array_equal(s0['artist_Y2'].get_xdata(), [10, 20, 30])
    np.testing.assert_array_equal(s0['artist_Y2'].get_ydata(), [-1, -2, -3])
    assert s0['artist_Y1'].get_color() == 'red'
    assert s0['artist_Y2'].get_color() == 'blue'
    assert s0['ax2'].get_shared_x_axes().joined(s0['ax1'], s0['ax2'])   # 共享 X 轴
    assert len(plt.get_fignums()) == 3                                  # twinx 不新建图窗


def test_subplotter_xyy_custom_formatter(eis_dataset):
    received = []
    DataPlotter(eis_dataset).subplotter_xyy(
        plotdataRowNum_X2=FREQ, plotdataRowNum_Y2=ZS_IM,
        custom_formatter=lambda ax1, ax2, fig: received.append((ax1, ax2, fig)))
    assert len(received) == 3                                           # 每个样品调用一次


# ══════════════════════════════════════════════
# 配色：计划给的色带位置 → matplotlib 颜色（位置怎么算见 test_plot_common.py、test_plot_plan.py）
# sparse_dataset 的样品号是 0、5、9
# ══════════════════════════════════════════════
PLASMA = plt.get_cmap('plasma')       # DataPlotter 默认色带


def test_sparse_sample_ids_colors(sparse_dataset):
    """
    三条线依次取色带 0、1/3、2/3 处的颜色。
    回归：曾用「样品号 ÷ 样品数」，5/3、9/3 都超过 1 被截断，样品 5 和 9 同色且不报错。
    """
    lines = DataPlotter(sparse_dataset).plot_objects().axesset['main']['artists']
    np.testing.assert_allclose([to_rgba(line.get_color()) for line in lines],
                               [PLASMA(p) for p in (0, 1/3, 2/3)])


def test_bar_colors_follow_plan(sparse_dataset):
    """
    柱状图也按计划的位置上色：合并模式下样品 5、9 都是组首（样品 5）的位置 1/3（步骤 6.2 用户选 A 的行为变化）。
    以前 BarContainer 没有 set_color，合并模式下柱子各用各的样品色。
    """
    groups = Group(sparse_dataset, {'A': {'num': [5, 9]}})
    plotter = DataPlotter(sparse_dataset, groups=groups).group_plotter(merge_groups=True, plot_kind='bar')
    for sample in (5, 9):
        for bar in plotter.axesset['main']['artists'][sample]:   # BarContainer 里每根柱子是一个矩形
            np.testing.assert_allclose(bar.get_facecolor(), PLASMA(1/3))


# ══════════════════════════════════════════════
# 负对数刻度（取绝对值在计划里；刻度文字补负号是 matplotlib 的事）
# ══════════════════════════════════════════════
def test_neglog_x(eis_dataset):
    """X 轴负对数：用 Zs''（全负）当 X。"""
    plotter = DataPlotter(eis_dataset, plotdataRowNum_x=ZS_IM, plotdataRowNum_y=ZS_RE)
    m = plotter.plot_objects(NegLogScale_x=True).axesset['main']

    np.testing.assert_array_equal(m['artists'][0].get_xdata(), [1, 2, 3])
    assert m['ax'].xaxis.get_major_formatter()(2.0, 0) == '-2.00'


def test_neglog_both_axes_keep_their_own_format(eis_dataset):
    """
    两轴同时负对数时各用各的格式。两轴格式故意设成不同，否则看不出区别。
    回归：X、Y 的 lambda 曾共用一个变量（闭包晚绑定），X 轴用上了 Y 轴的格式。
    """
    from plotlib.formatters import make_axes_formatter

    fmt = make_axes_formatter(x_format='{x:.1f}', y_format='{y:.3f}')
    ax = DataPlotter(eis_dataset, plotdataRowNum_x=ZS_IM, plotdataRowNum_y=ZS_IM).plot_objects(
        axes_formatter=fmt, NegLogScale_x=True, NegLogScale_y=True).axesset['main']['ax']

    assert ax.xaxis.get_major_formatter()(2.0, 0) == '-2.0'
    assert ax.yaxis.get_major_formatter()(2.0, 0) == '-2.000'
