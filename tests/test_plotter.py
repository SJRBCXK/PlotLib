"""
测试对象：src/plotter.py 的 DataPlotter

思路（Step 5）：不看图、不比像素，而是检查 matplotlib 对象的属性。
DataPlotter 把画出的东西都存在 self.axesset 里，测试就从这里取：
  - 线的数据        line.get_xdata() / get_ydata()
  - 线型、颜色      line.get_linestyle() / get_color()
  - 坐标轴标题      ax.get_xlabel() / get_ylabel()
  - 图例文字        [t.get_text() for t in ax.get_legend().get_texts()]
  - 当前打开的图窗  plt.get_fignums()

后端在 conftest.py 里切到了 Agg（不弹窗），每个测试结束自动 plt.close('all')。

数据来自 eis_dataset：每组 3 列 [Frequency(Hz), Zs'(ohm), Zs''(ohm)]，
S1 = S0 × 2，S2 = S0 × 3。
"""
import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.collections import PathCollection
from matplotlib.container import BarContainer
from matplotlib.lines import Line2D
from numpy.typing import NDArray

from src.plotter import DataPlotter

FREQ, ZS_RE, ZS_IM = 0, 1, 2      # 组内列索引


def legend_texts(ax):
    return [t.get_text() for t in ax.get_legend().get_texts()]


# ══════════════════════════════════════════════
# plot_objects：所有数据组画在同一张图
# ══════════════════════════════════════════════
def test_plot_objects_one_line_per_group(eis_dataset):
    plotter = DataPlotter(eis_dataset, plotdataRowNum_x=FREQ, plotdataRowNum_y=ZS_RE)
    plotter.plot_objects()

    assert list(plotter.axesset) == ['main']
    assert len(plotter.axesset['main']['artists']) == 3
    assert len(plt.get_fignums()) == 1


def test_plot_objects_line_data(eis_dataset):
    """每条线的 x/y 就是对应组的那两列。"""
    plotter = DataPlotter(eis_dataset, plotdataRowNum_x=FREQ, plotdataRowNum_y=ZS_RE).plot_objects()
    lines = plotter.axesset['main']['artists']

    for k, line in enumerate(lines):          # 第 k 组 = S0 × (k+1)
        np.testing.assert_array_equal(line.get_xdata(), [1, 10, 100])
        np.testing.assert_array_equal(line.get_ydata(), np.array([10, 20, 30]) * (k + 1))


def test_plot_objects_labels(eis_dataset):
    """坐标轴标题取单位，图例取组名。"""
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
# group_plotter：按 groups_config 分组
# ══════════════════════════════════════════════
GROUPS = {
    'A': {'num': [0, 1], 'linestyle': '--'},
    'B': {'num': [1, 2], 'linestyle': ':'},     # 数据组 1 被 A、B 共用
}


def test_group_separate_mode_one_figure_per_group(eis_dataset):
    plotter = DataPlotter(eis_dataset, plot_data_groups=GROUPS).group_plotter()

    assert list(plotter.axesset) == ['A', 'B']
    assert list(plotter.axesset['A']['artists']) == [0, 1]   # artists 以数据组索引为键
    assert list(plotter.axesset['B']['artists']) == [1, 2]
    assert len(plt.get_fignums()) == 2


@pytest.mark.parametrize("apply, expected", [
    (True,  {'A': '--', 'B': ':'}),
    (False, {'A': '-',  'B': '-'}),    # 不应用时保留默认 plot_style
], ids=['apply', 'default'])
def test_group_separate_mode_linestyle(eis_dataset, apply, expected):
    plotter = DataPlotter(eis_dataset, plot_data_groups=GROUPS) \
        .group_plotter(apply_group_linestyle=apply)
    for name, style in expected.items():
        assert all(a.get_linestyle() == style for a in plotter.axesset[name]['artists'].values())


def test_group_merge_mode(eis_dataset):
    """
    合并模式：一张图；被多个组共用的数据组只画一次，沿用第一个组（A）的样式；
    同组线条统一为组线型 + 组首色。
    """
    plotter = DataPlotter(eis_dataset, plot_data_groups=GROUPS).group_plotter(merge_groups=True)
    m = plotter.axesset['main']
    artists = m['artists']

    assert len(plt.get_fignums()) == 1
    assert len(m['ax'].get_lines()) == 3                 # 0、1、2 各一条，1 没有重复画
    assert [artists[i].get_linestyle() for i in (0, 1, 2)] == ['--', '--', ':']
    assert artists[0].get_color() == artists[1].get_color()     # 1 跟 A 的组首色
    assert artists[1].get_color() != artists[2].get_color()


def test_group_config_is_not_modified(eis_dataset):
    """groups_config 只读：range 不会被改成 list，也不会被加键。"""
    config = {'A': {'num': range(0, 2), 'linestyle': '--'}}
    DataPlotter(eis_dataset, plot_data_groups=config).group_plotter(merge_groups=True)
    assert config == {'A': {'num': range(0, 2), 'linestyle': '--'}}


def test_group_bad_config_raises_before_any_figure(eis_dataset):
    """配置有误时先报错，不留下画了一半的图窗。"""
    config = {'A': {'num': [0, 1]}, 'B': {'num': []}}      # B 为空
    with pytest.raises(ValueError, match="'B'"):
        DataPlotter(eis_dataset, plot_data_groups=config).group_plotter()
    assert plt.get_fignums() == []


def test_group_without_config_falls_back_to_plot_objects(eis_dataset):
    plotter = DataPlotter(eis_dataset).group_plotter()
    assert list(plotter.axesset) == ['main']
    assert len(plotter.axesset['main']['artists']) == 3


# ══════════════════════════════════════════════
# subplotter_yy：每组一张 Y-Y 图（如 Nyquist：Zs' vs Zs''）
# ══════════════════════════════════════════════
def test_subplotter_yy(eis_dataset):
    plotter = DataPlotter(eis_dataset).subplotter_yy(
        plotdataRowNum_Y1=ZS_RE, plotdataRowNum_Y2=ZS_IM)

    assert list(plotter.axesset) == [0, 1, 2]           # 以数据组索引为键
    s1 = plotter.axesset[1]
    np.testing.assert_array_equal(s1['artist'].get_xdata(), [20, 40, 60])
    np.testing.assert_array_equal(s1['artist'].get_ydata(), [-2, -4, -6])
    assert s1['ax'].get_xlabel() == "Zs'(ohm)"
    assert s1['ax'].get_ylabel() == "Zs''(ohm)"


# ══════════════════════════════════════════════
# subplotter_xyy：每组一张双 Y 轴图
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
    assert len(received) == 3                                           # 每组调用一次


# ══════════════════════════════════════════════
# 边界情况
# ══════════════════════════════════════════════
def test_column_index_out_of_range_raises(eis_dataset):
    """每组只有 3 列，要第 5 列 → 报错，而不是画出空图。"""
    with pytest.raises(RuntimeError, match="未找到对应的列数据"):
        DataPlotter(eis_dataset, plotdataRowNum_y=5).plot_objects()


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
    from src.formatters import make_axes_formatter

    fmt = make_axes_formatter(x_format='{x:.1f}', y_format='{y:.3f}')
    ax = DataPlotter(eis_dataset, plotdataRowNum_x=ZS_IM, plotdataRowNum_y=ZS_IM).plot_objects(
        axes_formatter=fmt, NegLogScale_x=True, NegLogScale_y=True).axesset['main']['ax']

    assert ax.xaxis.get_major_formatter()(2.0, 0) == '-2.0'
    assert ax.yaxis.get_major_formatter()(2.0, 0) == '-2.000'
