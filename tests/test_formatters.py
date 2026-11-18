"""
测试对象：src/plotlib/formatters.py —— 格式化器工厂

make_xxx_formatter(...) 返回一个函数，交给 DataPlotter 的 axes_formatter /
lines_formatter / legend_formatter 参数使用。测试直接在一张空图上调用它，再检查属性。
"""
import matplotlib.pyplot as plt
import pytest
from matplotlib.colors import to_rgba
from matplotlib.ticker import ScalarFormatter

from plotlib.formatters import (
    combine_formatters,
    make_axes_formatter,
    make_legend_formatter,
    make_lines_formatter,
)
from plotlib.plotter import DataPlotter


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
    """线型、标记、颜色用标准写法（style.py），由工厂翻译成 matplotlib 的原生值。"""
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(linewidth=5, linecolor='#ff0000', linestyle='dash',
                         linemarker='circle', linemarkersize=9)([line])

    assert line.get_linewidth() == 5
    assert line.get_color() == '#ff0000'
    assert line.get_linestyle() == '--'
    assert (line.get_marker(), line.get_markersize()) == ('o', 9)


def test_lines_rgb_color(fig_ax):
    """RGB 写法 0~255，翻译成 matplotlib 的 0~1。"""
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(linecolor=(255, 0, 0))([line])
    assert to_rgba(line.get_color()) == (1.0, 0.0, 0.0, 1.0)


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("kwargs", [
    dict(linestyle='--'),
    dict(linemarker='o'),
    dict(linecolor='tab:red'),
], ids=['mpl_linestyle', 'mpl_marker', 'mpl_color'])
def test_lines_rejects_non_standard(backend, kwargs):
    """后端写法不是标准写法：创建 formatter 时就报错（两个后端一样），不等到画图。"""
    if backend == "plotly":
        pytest.importorskip("plotly.graph_objects")
    with pytest.raises(ValueError):
        make_lines_formatter(backend=backend, **kwargs)


def test_plotly_lines_style():
    """Plotly：标准写法翻译成 Plotly 的原生值；自定义虚线按线宽换算成像素。"""
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    make_lines_formatter(backend="plotly", linestyle='dashdot', linemarker='triangle-up',
                         linecolor=(255, 0, 0))(fig)
    trace = fig.data[0]
    assert trace.line.dash == 'dashdot'
    assert trace.marker.symbol == 'triangle-up'
    assert trace.line.color == 'rgb(255,0,0)'

    make_lines_formatter(backend="plotly", linewidth=3, linestyle=(3, 5))(fig)
    assert fig.data[0].line.dash == '9px,15px'


def test_lines_custom_formations(fig_ax):
    _, ax = fig_ax
    line = ax.get_lines()[0]
    # 显式给 marker：不给时会触发下面 test_lines_without_marker 记录的 bug
    make_lines_formatter(linemarker='circle',
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


@pytest.mark.parametrize("axis, kwargs, expected", [
    # 只给一侧：用 autorangeoptions，另一侧自动；对数轴边界取 log10
    ("xaxis", dict(xlim_left=0.001, xscale_type='log'),
     dict(autorange=True, autorangeoptions={'minallowed': -3.0})),
    ("xaxis", dict(xlim_right=5), dict(autorange=True, autorangeoptions={'maxallowed': 5})),
    ("yaxis", dict(ylim_bottom=-2), dict(autorange=True, autorangeoptions={'minallowed': -2})),
    ("yaxis", dict(ylim_top=100, yscale_type='log'),
     dict(autorange=True, autorangeoptions={'maxallowed': 2.0})),
    # 两侧都给：固定 range
    ("xaxis", dict(xlim_left=1, xlim_right=1000, xscale_type='log'),
     dict(range=[0.0, 3.0], autorange=False)),
    ("yaxis", dict(ylim_bottom=-1, ylim_top=1), dict(range=[-1, 1], autorange=False)),
])
def test_plotly_axis_bounds(axis, kwargs, expected):
    """
    回归：只给一侧时曾用 autorange="min"/"max"。
    Plotly.js 在 automargin 扩边重绘时会把它重置为完全自动，边界失效。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    make_axes_formatter(backend="plotly", **kwargs)(fig)
    layout = fig.to_dict()["layout"]
    assert {k: layout[axis][k] for k in expected} == expected
    assert layout[axis].get("autorange") not in ("min", "max")
    # 只设置了一根轴的边界，另一根轴不应被写入范围设置
    other = layout["yaxis" if axis == "xaxis" else "xaxis"]
    assert not {"range", "autorangeoptions"} & other.keys()


@pytest.mark.render
@pytest.mark.parametrize("axis, kwargs, expected", [
    # expected = (低端, 高端)；None 表示该端自动，只检查它覆盖了数据
    ("xaxis", dict(xscale_type='log', xlim_left=5), (5, None)),
    ("xaxis", dict(xscale_type='log', xlim_left=0.1), (0.1, None)),   # 边界在数据之外也照用
    ("xaxis", dict(xscale_type='log', xlim_right=50), (None, 50)),
    ("yaxis", dict(ylim_bottom=15), (15, None)),
    ("yaxis", dict(ylim_top=60), (None, 60)),
    ("yaxis", dict(ylim_bottom=0, ylim_top=100), (0, 100)),
])
def test_plotly_axis_bounds_after_render(eis_dataset, render, axis, kwargs, expected):
    """
    断言 Plotly.js 实际渲染出的范围，而不是 JSON 里的设置。
    使用真实模板：模板开了 automargin，正是它的扩边重绘曾让单侧边界失效。
    """
    from plotlib.interactive import InteractivePlotter

    plot = InteractivePlotter(eis_dataset, plotdataRowNum_x=0, plotdataRowNum_y=1)
    fig = plot.plot_plotly_object(
        figure_formatter=make_axes_formatter(backend="plotly", **kwargs)).asset
    full_axis = render(fig).layout[axis]
    low, high = (10 ** v if full_axis.type == "log" else v for v in full_axis.range)

    data_min, data_max = {"xaxis": (1, 100), "yaxis": (10, 90)}[axis]   # eis_dataset 的数据范围
    want_low, want_high = expected
    if want_low is None:
        assert low <= data_min
    else:
        assert low == pytest.approx(want_low)
    if want_high is None:
        assert high >= data_max
    else:
        assert high == pytest.approx(want_high)


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
