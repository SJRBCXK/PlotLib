"""
测试对象：src/formatters.py —— 格式化器工厂

make_xxx_formatter(...) 返回一个函数，交给 DataPlotter 的 axes_formatter /
lines_formatter / legend_formatter 参数使用。测试直接在一张空图上调用它，再检查属性。
"""
import matplotlib.pyplot as plt
import pytest
from matplotlib.ticker import ScalarFormatter

from src.formatters import (
    combine_formatters,
    make_axes_formatter,
    make_legend_formatter,
    make_lines_formatter,
)
from src.plotter import DataPlotter


@pytest.fixture
def fig_ax():
    fig, ax = plt.subplots()
    ax.plot([1, 10, 100], [1, 2, 3], label='a')
    return fig, ax


# ══════════════════════════════════════════════
# axes formatter
# ══════════════════════════════════════════════
def test_axes_defaults(fig_ax):
    """不传 x_format/y_format 时不替换刻度格式器，保留 matplotlib 自动刻度。"""
    fig, ax = fig_ax
    make_axes_formatter()(ax, fig)

    assert ax.get_xscale() == ax.get_yscale() == 'linear'
    # set_xscale 会重建默认格式器，所以只检查类型，不比较对象身份。
    assert isinstance(ax.xaxis.get_major_formatter(), ScalarFormatter)
    assert isinstance(ax.yaxis.get_major_formatter(), ScalarFormatter)
    assert not ax.spines['top'].get_visible()
    assert not ax.spines['right'].get_visible()


def test_axes_scaler_without_format(fig_ax):
    """只给 scaler 时仍要换算显示值，按 '{x:g}' 输出。"""
    fig, ax = fig_ax
    make_axes_formatter(xscaler=1000)(ax, fig)
    assert ax.xaxis.get_major_formatter()(0.002, 0) == '2'


def test_axes_scale_and_limits(fig_ax):
    fig, ax = fig_ax
    make_axes_formatter(xscale_type='log', yscale_type='log',
                        xlim_left=1, xlim_right=1000, ylim_bottom=0.5, ylim_top=5)(ax, fig)

    assert ax.get_xscale() == ax.get_yscale() == 'log'
    assert ax.get_xlim() == (1, 1000)
    assert ax.get_ylim() == (0.5, 5)


def test_axes_tick_format_and_scaler(fig_ax):
    """刻度文字 = format(刻度值 × scaler)，用于换算单位（如 s → ms）。"""
    fig, ax = fig_ax
    make_axes_formatter(xscaler=1000, x_format='{x:.0f}', y_format='{y:.1e}')(ax, fig)

    assert ax.xaxis.get_major_formatter()(2.0, 0) == '2000'
    assert ax.yaxis.get_major_formatter()(2.0, 0) == '2.0e+00'


def test_axes_keep_spines(fig_ax):
    fig, ax = fig_ax
    make_axes_formatter(hide_spines=False)(ax, fig)
    assert ax.spines['top'].get_visible()


def test_axes_custom_formation_receives_ax_and_fig(fig_ax):
    """
    custom_formation 里的函数以 (ax, fig) 调用。
    注意：模块文档示例写的是 lambda ax: ...（单参数），按文档写会 TypeError。
    """
    fig, ax = fig_ax
    calls = []
    make_axes_formatter(custom_formation=[lambda a, f: calls.append((a, f))])(ax, fig)
    assert calls == [(ax, fig)]


def test_axes_formatter_works_with_plotter(eis_dataset):
    """集成：作为 axes_formatter 交给 DataPlotter（eis_bode.py 的用法）。"""
    fmt = make_axes_formatter(xscale_type='log', x_format='{x:.1e}')
    ax = DataPlotter(eis_dataset).plot_objects(axes_formatter=fmt).axesset['main']['ax']
    assert ax.get_xscale() == 'log'


# ══════════════════════════════════════════════
# lines formatter
# ══════════════════════════════════════════════
def test_lines_style(fig_ax):
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(linewidth=5, linecolor='red', linestyle='--',
                         linemarker='o', linemarkersize=9)([line])

    assert line.get_linewidth() == 5
    assert line.get_color() == 'red'
    assert line.get_linestyle() == '--'
    assert (line.get_marker(), line.get_markersize()) == ('o', 9)


def test_lines_custom_formations(fig_ax):
    _, ax = fig_ax
    line = ax.get_lines()[0]
    # 显式给 marker：不给时会触发下面 test_lines_without_marker 记录的 bug
    make_lines_formatter(linemarker='o',
                         custom_formations=[lambda ln: ln.set_alpha(0.3)])([line])
    assert line.get_alpha() == 0.3


def test_lines_without_marker(fig_ax):
    """
    不传 linemarker 时不改 marker（保持默认无标记）。
    回归：曾无条件调用 set_marker(None)，matplotlib 3.10 下直接报错。
    """
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(linecolor='red')([line])
    assert line.get_color() == 'red'
    assert line.get_marker() == 'None'


# ══════════════════════════════════════════════
# legend formatter
# ══════════════════════════════════════════════
def test_legend_formatter(fig_ax):
    """回归：曾调用不存在的 Legend.set_fontsize，一调用就崩。"""
    _, ax = fig_ax
    legend = ax.legend()
    make_legend_formatter(legend_fontsize=7, legend_location='upper left',
                          legend_frameon=True, legend_draggable=False)([legend])
    assert [t.get_fontsize() for t in legend.get_texts()] == [7]
    assert legend.get_frame_on()
    assert not legend.get_draggable()
    assert legend._loc == 2          # 'upper left' 的内部编号（matplotlib 无公开 getter）


def test_plotly_axes_keeps_auto_tickformat():
    """Plotly 默认不写 tickformat；显式传入时才翻译成 d3 格式。"""
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    make_axes_formatter(backend="plotly")(fig)
    assert fig.layout.xaxis.tickformat is None
    assert fig.layout.yaxis.tickformat is None

    make_axes_formatter(backend="plotly", x_format='{x:.1e}')(fig)
    assert fig.layout.xaxis.tickformat == '.1e'
    assert fig.layout.yaxis.tickformat is None


def test_combine_formatters_runs_in_order_and_skips_none():
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], name='a'))
    calls = []
    fmt = combine_formatters(
        make_lines_formatter(backend="plotly", linewidth=5),
        None,
        make_legend_formatter(backend="plotly", legend_fontsize=11),
        lambda f: calls.append(f),
    )
    fmt(fig)
    assert fig.data[0].line.width == 5
    assert fig.layout.legend.font.size == 11
    assert calls == [fig]


def test_legend_formatter_works_with_plotter(eis_dataset):
    """集成：作为 legend_formatter 交给 DataPlotter——修复前这条路径从没跑通过。"""
    ax = DataPlotter(eis_dataset).plot_objects(
        legend_formatter=make_legend_formatter(legend_fontsize=7)).axesset['main']['ax']
    assert all(t.get_fontsize() == 7 for t in ax.get_legend().get_texts())
