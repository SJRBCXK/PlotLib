"""
测试对象：src/plotlib/formatters.py —— 格式化器工厂

make_xxx_formatter(...) 返回一个函数，交给 DataPlotter 的 axes_formatter /
lines_formatter / legend_formatter 参数使用。测试直接在一张空图上调用它，再检查属性。
2026-11-20 样式对象化：参数是样式对象（AxisStyle、FrameStyle、LineStyle、LegendStyle、TickStyle），没写的字段不改。
"""
import math
from typing import Any

import matplotlib.pyplot as plt
import pytest
from matplotlib.colors import to_rgba
from matplotlib.ticker import FuncFormatter, ScalarFormatter

from plotlib.formatters import (
    combine_formatters,
    make_axes_formatter,
    make_legend_formatter,
    make_lines_formatter,
)
from plotlib.plot_spec import AxesFormatter, AxisStyle, FrameStyle, LegendStyle, LineStyle
from plotlib.plotter import DataPlotter

PX = 100 / 72       # 默认 dpi 100 时 1 磅的像素数（Plotly 的线宽、字号按它换算；不是后端画的图用默认 dpi）


@pytest.fixture
def fig_ax():
    fig, ax = plt.subplots()
    ax.plot([1, 10, 100], [1, 2, 3], label='a')
    return fig, ax


# ══════════════════════════════════════════════
# axes formatter
# ══════════════════════════════════════════════
def test_axes_defaults_change_nothing(fig_ax):
    """
    什么都不给：什么都不改——刻度类型、已有的刻度格式（如排版预设的两位小数）、边框都保持原样。
    回归（样式对象化时修）：以前刻度类型默认 'linear' 且总是调用 set_*scale，会把已有的刻度格式重置；边框默认隐藏上 / 右边。
    """
    fig, ax = fig_ax
    preset_format = FuncFormatter(lambda v, _: f"{v:.2f}")
    ax.yaxis.set_major_formatter(preset_format)
    make_axes_formatter()(ax, fig)

    assert ax.get_xscale() == ax.get_yscale() == 'linear'
    assert ax.yaxis.get_major_formatter() is preset_format
    assert isinstance(ax.xaxis.get_major_formatter(), ScalarFormatter)
    assert ax.spines['top'].get_visible() and ax.spines['right'].get_visible()


def test_axes_scaler_without_format(fig_ax):
    """只给 scaler 时仍要换算显示值，按 '{x:g}' 输出。"""
    fig, ax = fig_ax
    make_axes_formatter(x=AxisStyle(scaler=1000))(ax, fig)
    assert ax.xaxis.get_major_formatter()(0.002, 0) == '2'


def test_axes_scale_and_limits(fig_ax):
    fig, ax = fig_ax
    make_axes_formatter(
        x=AxisStyle(scale='log', limits=(1, 1000)),
        y=AxisStyle(scale='log', limits=(0.5, 5)),
    )(ax, fig)

    assert ax.get_xscale() == ax.get_yscale() == 'log'
    assert ax.get_xlim() == (1, 1000)
    assert ax.get_ylim() == (0.5, 5)


def test_axes_tick_format_and_scaler(fig_ax):
    """刻度文字 = format(刻度值 × scaler)，用于换算单位（如 s → ms）。"""
    fig, ax = fig_ax
    make_axes_formatter(
        x=AxisStyle(format='{x:.0f}', scaler=1000),
        y=AxisStyle(format='{y:.1e}'),
    )(ax, fig)

    assert ax.xaxis.get_major_formatter()(2.0, 0) == '2000'
    assert ax.yaxis.get_major_formatter()(2.0, 0) == '2.0e+00'


def test_axes_frame(fig_ax):
    """FrameStyle：上 / 右边画不画、轴线宽，只改写了的。"""
    fig, ax = fig_ax
    make_axes_formatter(frame=FrameStyle(top=False, width=5))(ax, fig)
    assert not ax.spines['top'].get_visible()
    assert ax.spines['right'].get_visible()                 # 没写 right：不改
    assert {spine.get_linewidth() for spine in ax.spines.values()} == {5}


def test_axes_custom_receives_ax_and_fig(fig_ax):
    """custom 里的函数以 (ax, fig) 调用（原 custom_formation，样式对象化时统一叫 custom）。"""
    fig, ax = fig_ax
    calls = []
    make_axes_formatter(custom=[lambda a, f: calls.append((a, f))])(ax, fig)
    assert calls == [(ax, fig)]


def test_axes_formatter_works_with_plotter(eis_dataset):
    """集成：作为 axes_formatter 交给 DataPlotter（eis_bode.py 的用法）。"""
    fmt = make_axes_formatter(x=AxisStyle(scale='log', format='{x:.1e}'))
    ax = DataPlotter(eis_dataset).plot(formatters=AxesFormatter(axes=fmt)).figures['main'].axes['left']
    assert ax.get_xscale() == 'log'


# ══════════════════════════════════════════════
# lines formatter
# ══════════════════════════════════════════════
def test_lines_style(fig_ax):
    """线型、标记、颜色用标准写法（style.py），由工厂翻译成 matplotlib 的原生值。"""
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(
        LineStyle(width=5, color='#ff0000', linestyle='dash', marker='circle', marker_size=9),
    )([line])

    assert line.get_linewidth() == 5
    assert line.get_color() == '#ff0000'
    assert line.get_linestyle() == '--'
    assert (line.get_marker(), line.get_markersize()) == ('o', 9)


def test_lines_rgb_color(fig_ax):
    """RGB 写法 0~255，翻译成 matplotlib 的 0~1。"""
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(LineStyle(color=(255, 0, 0)))([line])
    assert to_rgba(line.get_color()) == (1.0, 0.0, 0.0, 1.0)


@pytest.mark.parametrize("backend", ["matplotlib", "plotly"])
@pytest.mark.parametrize("kwargs", [
    dict(linestyle='--'),
    dict(marker='o'),
    dict(color='tab:red'),
], ids=['mpl_linestyle', 'mpl_marker', 'mpl_color'])
def test_lines_rejects_non_standard(backend, kwargs):
    """后端写法不是标准写法：创建 formatter 时就报错（两个后端一样），不等到画图。"""
    if backend == "plotly":
        pytest.importorskip("plotly.graph_objects")
    with pytest.raises(ValueError):
        make_lines_formatter(LineStyle(**kwargs), backend=backend)


def test_plotly_lines_style():
    """Plotly：标准写法翻译成 Plotly 的原生值；线宽按 dpi 从磅换成像素，自定义虚线按换算后的线宽算像素。"""
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    trace = fig.data[0]
    make_lines_formatter(
        LineStyle(linestyle='dashdot', marker='triangle-up', color=(255, 0, 0)),
        backend="plotly",
    )([trace])         # 与 matplotlib 一样收线的列表
    assert trace.line.dash == 'dashdot'
    assert trace.marker.symbol == 'triangle-up'
    assert trace.line.color == 'rgb(255,0,0)'

    make_lines_formatter(LineStyle(width=3, linestyle=(3, 5)), backend="plotly")([trace])
    assert trace.line.width == pytest.approx(3 * PX)
    assert trace.line.dash == f"{3 * 3 * PX:g}px,{5 * 3 * PX:g}px"


def test_plotly_lines_color_on_markers_only_trace():
    """
    纯散点（mode='markers'）看得见的是点：LineStyle 的 color 同时改点的颜色（与 matplotlib 的 set_color 一样，点跟着线色）。
    散点颜色回调更新可见标记的颜色。
    """
    go = pytest.importorskip("plotly.graph_objects")
    trace = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], mode='markers', marker_color='blue')).data[0]
    make_lines_formatter(LineStyle(color='green'), backend="plotly")([trace])
    assert trace.marker.color == 'green'
    assert trace.mode == 'markers'


def test_lines_custom_formations(fig_ax):
    _, ax = fig_ax
    line = ax.get_lines()[0]
    # 显式给 marker：不给时会触发下面 test_lines_without_marker 记录的 bug
    make_lines_formatter(LineStyle(marker='circle'), custom=[lambda ln: ln.set_alpha(0.3)])([line])
    assert line.get_alpha() == 0.3


def test_lines_without_marker(fig_ax):
    """
    没写 marker 时不改 marker（保持默认无标记）。
    回归：曾无条件调用 set_marker(None)，matplotlib 3.10 下直接报错。
    """
    _, ax = fig_ax
    line = ax.get_lines()[0]
    make_lines_formatter(LineStyle(color='red'))([line])
    assert line.get_color() == 'red'
    assert line.get_marker() == 'None'


# ══════════════════════════════════════════════
# legend formatter
# ══════════════════════════════════════════════
def test_legend_formatter(fig_ax):
    """回归：曾调用不存在的 Legend.set_fontsize，一调用就崩。"""
    _, ax = fig_ax
    legend = ax.legend()
    make_legend_formatter(
        LegendStyle(font_size=7, position='upper left', frame=True, draggable=False),
    )([legend])
    assert [t.get_fontsize() for t in legend.get_texts()] == [7]
    assert legend.get_frame_on()
    assert not legend.get_draggable()
    assert legend._loc == 2          # 'upper left' 的内部编号（matplotlib 无公开 getter）


def test_plotly_axes_keeps_auto_tickformat():
    """Plotly 默认不写 tickformat；显式传入时才翻译成 d3 格式。"""
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    make_axes_formatter(backend="plotly")('yaxis', fig)
    assert fig.layout.xaxis.tickformat is None
    assert fig.layout.yaxis.tickformat is None

    make_axes_formatter(x=AxisStyle(format='{x:.1e}'), backend="plotly")('yaxis', fig)
    assert fig.layout.xaxis.tickformat == '.1e'
    assert fig.layout.yaxis.tickformat is None


def test_plotly_axes_formatter_targets_given_axis():
    """
    Plotly 的轴回调以 (轴名, fig) 调用（对应 matplotlib 的 (ax, fig)）：Y 轴设置只写到这根轴，
    X 轴设置写到左右共用的 xaxis（对应 matplotlib twinx 共用 X 轴）；custom 同样收 (轴名, fig)。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    calls = []
    make_axes_formatter(
        x=AxisStyle(limits=(1, 2)),
        y=AxisStyle(limits=(0, 1)),
        backend="plotly",
        custom=[lambda axis, f: calls.append((axis, f))],
    )('yaxis2', fig)

    lay = fig.to_dict()["layout"]
    assert lay['yaxis2']['range'] == [0, 1]
    assert 'range' not in lay.get('yaxis', {})
    assert lay['xaxis']['range'] == [1, 2]
    assert len(calls) == 1 and calls[0][0] == 'yaxis2' and calls[0][1] is fig


def test_plotly_legend_formatter():
    """
    Plotly 的图例回调与 matplotlib 一样收图例列表：[fig.layout.legend]。字号按 dpi 从磅换成像素；
    位置与排版预设同一套写法（图内离边 0.02）。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4], name='a'))
    make_legend_formatter(
        LegendStyle(font_size=11, position='upper left'),
        backend="plotly",
    )([fig.layout.legend])
    assert fig.layout.legend.font.size == pytest.approx(11 * PX)
    assert (fig.layout.legend.x, fig.layout.legend.xanchor) == (0.02, 'left')


def test_plotly_legend_draggable_rejected():
    """Plotly 的图例拖动是显示时的设置：图例回调里写 draggable=True → 创建时报错，提示怎么设。"""
    pytest.importorskip("plotly.graph_objects")
    with pytest.raises(ValueError, match='legendPosition'):
        make_legend_formatter(LegendStyle(draggable=True), backend="plotly")


@pytest.mark.parametrize("axis, kwargs, expected", [
    # 只给一侧：用 autorangeoptions，另一侧自动；对数轴边界取 log10
    ("xaxis", dict(x=AxisStyle(scale='log', limits=(0.001, None))),
     dict(autorange=True, autorangeoptions={'minallowed': -3.0})),
    ("xaxis", dict(x=AxisStyle(limits=(None, 5))), dict(autorange=True, autorangeoptions={'maxallowed': 5})),
    ("yaxis", dict(y=AxisStyle(limits=(-2, None))), dict(autorange=True, autorangeoptions={'minallowed': -2})),
    ("yaxis", dict(y=AxisStyle(scale='log', limits=(None, 100))),
     dict(autorange=True, autorangeoptions={'maxallowed': 2.0})),
    # 两侧都给：固定 range
    ("xaxis", dict(x=AxisStyle(scale='log', limits=(1, 1000))), dict(range=[0.0, 3.0], autorange=False)),
    ("yaxis", dict(y=AxisStyle(limits=(-1, 1))), dict(range=[-1, 1], autorange=False)),
])
def test_plotly_axis_bounds(axis, kwargs, expected):
    """
    回归：只给一侧时曾用 autorange="min"/"max"。
    Plotly.js 在 automargin 扩边重绘时会把它重置为完全自动，边界失效。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    make_axes_formatter(backend="plotly", **kwargs)('yaxis', fig)
    layout = fig.to_dict()["layout"]
    assert {k: layout[axis][k] for k in expected} == expected
    assert layout[axis].get("autorange") not in ("min", "max")
    # 只设置了一根轴的边界，另一根轴不应被写入范围设置（样式对象化起没写的轴根本不写）
    other = layout.get("yaxis" if axis == "xaxis" else "xaxis", {})
    assert not {"range", "autorangeoptions"} & other.keys()


def test_plotly_frame_on_single_axis_figure():
    """
    单轴图上用轴工厂画完整的框：上边 = X 轴镜像，右边 = Y 轴镜像（没有右轴，左 Y 轴自己镜像）。
    回归：判断「有没有叠加的右轴」时直接读 fig.layout.yaxis2，没有右轴的图上抛 AttributeError
    （2026-11-20 把 Plotly 的样式应用挪进 backends/plotly_styles.py 时发现）。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    make_axes_formatter(frame=FrameStyle(top=True, right=True), backend="plotly")('yaxis', fig)
    assert fig.layout.xaxis.mirror is True and fig.layout.yaxis.mirror is True


@pytest.mark.parametrize("steps, expected", [
    # 两侧：Plotly 对数轴的 range 用 log10
    ([AxisStyle(scale='log', limits=(10, 1000))], dict(type='log', range=(1, 3))),
    ([AxisStyle(scale='log'), AxisStyle(limits=(10, 1000))], dict(type='log', range=(1, 3))),
    ([AxisStyle(limits=(10, 1000)), AxisStyle(scale='log')], dict(type='log', range=(1, 3))),
    ([AxisStyle(scale='log', limits=(10, 1000)), AxisStyle(scale='linear')], dict(type='linear', range=(10, 1000))),
    # 单侧：autorangeoptions 的边界也用 log10
    ([AxisStyle(scale='log'), AxisStyle(limits=(10, None))], dict(type='log', minallowed=1)),
    ([AxisStyle(limits=(None, 1000)), AxisStyle(scale='log')], dict(type='log', maxallowed=3)),
], ids=['together', 'scale_first', 'limits_first', 'back_to_linear', 'one_side_scale_first', 'one_side_limits_first'])
def test_plotly_log_limits_any_order(steps, expected):
    """
    limits 永远写数据值，与 matplotlib 相同：刻度类型和范围分几个回调设、先设哪个，结果都一样（55576fb 复审 3）。
    回归：先设对数、再单独设 (10, 1000)，range 写成 [10, 1000]，被 Plotly 当成 10^10 ~ 10^1000；
    反过来先设范围再改对数，已写的范围也没跟着换算。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    combine_formatters(*(make_axes_formatter(x=step, backend="plotly") for step in steps))('yaxis', fig)

    xaxis = fig.layout.xaxis
    assert xaxis.type == expected['type']
    if 'range' in expected:
        assert list(xaxis.range) == pytest.approx(expected['range'])
    for key in ('minallowed', 'maxallowed'):
        if key in expected:
            assert xaxis.autorangeoptions[key] == pytest.approx(expected[key])


@pytest.mark.parametrize("steps, expected", [
    # 先线性范围、再改对数并给新范围：旧边界 -1 不必换算（会被替换），直接用新的
    ([AxisStyle(limits=(-1, 30)), AxisStyle(scale='log', limits=(1, 30))],
     dict(type='log', range=(0, math.log10(30)), autorange=False, minallowed=None, maxallowed=None)),
    # 单侧换单侧：上一次的下界不残留
    ([AxisStyle(limits=(5, None)), AxisStyle(limits=(None, 30))],
     dict(range=None, autorange=True, minallowed=None, maxallowed=30)),
    # 两侧换单侧：上一次的固定范围不残留
    ([AxisStyle(limits=(5, 30)), AxisStyle(limits=(None, 30))],
     dict(range=None, autorange=True, minallowed=None, maxallowed=30)),
    # 单侧换两侧：上一次的单侧边界不残留
    ([AxisStyle(limits=(None, 30)), AxisStyle(limits=(5, 30))],
     dict(range=(5, 30), autorange=False, minallowed=None, maxallowed=None)),
], ids=['linear_to_log', 'one_side_to_other', 'both_to_one_side', 'one_side_to_both'])
def test_plotly_limits_replace_previous(steps, expected):
    """
    这次写了 limits：两端一起换成这次的（写 None 的一端恢复自动），上一次的范围、单侧边界都不残留；
    只改刻度类型（没写 limits）时才换算已有的边界（见 test_plotly_log_limits_any_order）。
    回归（1.0 发布前复审）：先 (-1, 30) 再 log + (1, 30) 曾报「边界必须大于 0」；单侧边界曾残留。
    """
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[2, 20], y=[1, 2]))
    combine_formatters(*(make_axes_formatter(x=step, backend="plotly") for step in steps))('yaxis', fig)

    xaxis = fig.layout.xaxis
    if 'type' in expected:
        assert xaxis.type == expected['type']
    assert (None if xaxis.range is None else list(xaxis.range)) == \
        (None if expected['range'] is None else pytest.approx(list(expected['range'])))
    assert xaxis.autorange == expected['autorange']
    assert (xaxis.autorangeoptions.minallowed, xaxis.autorangeoptions.maxallowed) == \
        (expected['minallowed'], expected['maxallowed'])


@pytest.mark.render
def test_plotly_one_side_limit_after_other_side_render(eis_dataset, render):
    """先限下界、再只限上界：渲染出的下界恢复自动（覆盖数据），上界就是这次写的。"""
    from plotlib.plotter import DataPlotter

    axes_fmt = combine_formatters(make_axes_formatter(x=AxisStyle(limits=(50, None)), backend="plotly"),
                                  make_axes_formatter(x=AxisStyle(limits=(None, 80)), backend="plotly"))
    fig = DataPlotter(eis_dataset, channel_x=0, channel_y=1, backend='plotly').plot(
        formatters=AxesFormatter(axes=axes_fmt),
    ).figures['main'].fig
    low, high = render(fig).layout.xaxis.range
    assert low <= 1 and high == pytest.approx(80)       # eis_dataset 的频率是 1 ~ 100


@pytest.mark.parametrize("steps", [
    [AxisStyle(scale='log'), AxisStyle(limits=(0, 10))],
    [AxisStyle(limits=(-1, 10)), AxisStyle(scale='log')],
], ids=['limits_after_log', 'log_after_limits'])
def test_plotly_log_limits_must_be_positive(steps):
    """分步设置时，对数轴的边界同样必须大于 0：在应用时报错（创建时还不知道这根轴会是对数轴）。"""
    go = pytest.importorskip("plotly.graph_objects")
    fig = go.Figure(go.Scatter(x=[1, 2], y=[3, 4]))
    formatter = combine_formatters(*(make_axes_formatter(x=step, backend="plotly") for step in steps))
    with pytest.raises(ValueError, match='大于 0'):
        formatter('yaxis', fig)


@pytest.mark.render
def test_plotly_log_limits_in_steps_after_render(eis_dataset, render):
    """分步设置对数轴范围，Plotly.js 实际渲染出的范围就是写的数据值（复审 3 用 Kaleido 发现的就是这个）。"""
    from plotlib.plotter import DataPlotter

    axes_fmt = combine_formatters(make_axes_formatter(x=AxisStyle(scale='log'), backend="plotly"),
                                  make_axes_formatter(x=AxisStyle(limits=(0.5, 500)), backend="plotly"))
    fig = DataPlotter(eis_dataset, channel_x=0, channel_y=1, backend='plotly').plot(
        formatters=AxesFormatter(axes=axes_fmt),
    ).figures['main'].fig
    full_axis = render(fig).layout.xaxis
    assert [10 ** v for v in full_axis.range] == pytest.approx([0.5, 500])


@pytest.mark.render
@pytest.mark.parametrize("axis, kwargs, expected", [
    # expected = (低端, 高端)；None 表示该端自动，只检查它覆盖了数据
    ("xaxis", dict(x=AxisStyle(scale='log', limits=(5, None))), (5, None)),
    ("xaxis", dict(x=AxisStyle(scale='log', limits=(0.1, None))), (0.1, None)),   # 边界在数据之外也照用
    ("xaxis", dict(x=AxisStyle(scale='log', limits=(None, 50))), (None, 50)),
    ("yaxis", dict(y=AxisStyle(limits=(15, None))), (15, None)),
    ("yaxis", dict(y=AxisStyle(limits=(None, 60))), (None, 60)),
    ("yaxis", dict(y=AxisStyle(limits=(0, 100))), (0, 100)),
])
def test_plotly_axis_bounds_after_render(eis_dataset, render, axis, kwargs, expected):
    """
    断言 Plotly.js 实际渲染出的范围，而不是 JSON 里的设置。
    使用真实模板：模板开了 automargin，正是它的扩边重绘曾让单侧边界失效。
    """
    from plotlib.plotter import DataPlotter

    plot = DataPlotter(eis_dataset, channel_x=0, channel_y=1, backend='plotly')
    fig = plot.plot(formatters=AxesFormatter(axes=make_axes_formatter(backend="plotly", **kwargs))).figures['main'].fig
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


def test_combine_formatters_runs_in_order_and_skips_none(fig_ax):
    """按传入顺序调用、跳过 None，每个都收到同样的参数（两个后端通用；接入绘图器的对照在 test_backend_parity.py）。"""
    fig, ax = fig_ax
    calls = []
    combine_formatters(lambda a, f: calls.append(('first', a, f)), None,
                       lambda a, f: calls.append(('second', a, f)))(ax, fig)
    assert calls == [('first', ax, fig), ('second', ax, fig)]


def test_legend_formatter_works_with_plotter(eis_dataset):
    """集成：作为 legend_formatter 交给 DataPlotter——修复前这条路径从没跑通过。"""
    ax = DataPlotter(eis_dataset).plot(formatters=AxesFormatter(legend=make_legend_formatter(
            LegendStyle(font_size=7),
        ))).figures['main'].axes['left']
    assert all(t.get_fontsize() == 7 for t in ax.get_legend().get_texts())


# ══════════════════════════════════════════════
# 自动范围与刻度渲染
# ══════════════════════════════════════════════
def test_one_side_limit_autoscales_other_side():
    """matplotlib：先 limits=(2, 4) 再 (None, 15)，下界按数据重新算（与 Plotly 一致），不留旧的 2；两端都 None 时保持自动。"""
    fig, ax = plt.subplots()
    ax.plot([0.1, 20], [0, 1])
    combine_formatters(make_axes_formatter(x=AxisStyle(limits=(2, 4))),
                       make_axes_formatter(x=AxisStyle(limits=(None, 15))))(ax, fig)
    low, high = ax.get_xlim()
    assert low <= 0.1 and high == 15

    # 两端都写 None：交回自动范围，之后新加的曲线也能撑开范围
    fig, ax = plt.subplots()
    ax.plot([1.9, 4.1], [0, 1])
    make_axes_formatter(x=AxisStyle(limits=(None, None)))(ax, fig)
    ax.plot([20, 40], [0, 1])
    assert ax.get_xlim()[1] >= 40


def test_minor_ticks_keep_scale_locator():
    """
    matplotlib：开次刻度时 logit、symlog 轴保留 ``set_xscale`` 装好的原生次刻度定位器，不换成线性细分。
    （库不改动这类轴的定位器，不借用 matplotlib 的私有接口取刻度类型的默认定位器。）
    """
    from matplotlib.ticker import LogitLocator, SymmetricalLogLocator

    from plotlib.backends.matplotlib_styles import apply_minor

    for scale, locator in (('logit', LogitLocator), ('symlog', SymmetricalLogLocator)):
        fig, ax = plt.subplots()
        ax.plot([0.001, 0.5], [0.001, 0.5])
        ax.set_xscale(scale)
        apply_minor(ax, {'minor_visible': True}, only_defaults=False)
        assert isinstance(ax.xaxis.get_minor_locator(), locator), scale


def test_negative_labels_on_linear_axis():
    """
    负对数轴的标签包装在线性轴上：标签 + 偏移 = 刻度值取负，不出现双负号、偏移的符号也一起翻转。
    数据在 1e6 附近、范围很窄，ScalarFormatter 会用偏移文字。
    """
    from plotlib.backends.matplotlib_backend import _NegativeFormatter

    fig, ax = plt.subplots()
    ax.plot([1e6 - 3, 1e6 + 3], [0, 1])
    ax.xaxis.set_major_formatter(_NegativeFormatter(ax.xaxis.get_major_formatter()))
    fig.canvas.draw()
    number = lambda text: float(text.replace('−', '-') or 0)         # noqa: E731
    offset = number(ax.xaxis.get_offset_text().get_text())
    for tick, label in zip(ax.get_xticks(), ax.get_xticklabels()):
        if label.get_text():
            assert number(label.get_text()) + offset == pytest.approx(-tick), label.get_text()


def test_plotly_cleared_tickformat_is_not_explicit():
    """Plotly：tickformat 设成 '' 等于没写格式，minor_labels='short' 不算冲突。"""
    import plotly.graph_objects as go

    from plotlib.backends.plotly_styles import apply_log_format

    fig = go.Figure(layout=dict(xaxis=dict(type='log', tickformat='', minorloglabels='small digits')))
    apply_log_format(fig, 'xaxis')                          # 不报格式冲突
    layout: Any = fig.layout
    assert layout.xaxis.dtick is None
