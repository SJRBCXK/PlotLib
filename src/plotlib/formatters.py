"""
格式化回调的工厂函数：参数是样式对象，按 *backend* 返回 matplotlib 或 Plotly 的回调。

- `make_axes_formatter`：坐标轴（刻度类型、范围、刻度格式、着色、边框、刻度）；
- `make_lines_formatter`：线条（线宽、颜色、线型、标记）；
- `make_legend_formatter`：图例（位置、字号、边框、拖动）；
- `combine_formatters`：把几个同一种的回调合成一个。

生成的回调交给 `~plotlib.plotter.DataPlotter` 绘图方法的 ``axes_formatter``、``lines_formatter``、
``legend_formatter`` 参数，由后端逐轴调用。

Notes
-----
- **只改写了的字段。** 样式对象里没写的字段（None）不改，沿用 ``DataPlotter(...)`` 的全局设置和版式预设，
  所以不会覆盖按样品分配的颜色或预设的刻度格式。刻度类型也一样：没写 ``scale`` 就不改刻度类型。
- **单位。** 线宽、标记大小、字号、刻度长短都是磅；Plotly 按这张图的 dpi 换成像素
  （后端把 dpi 记在 ``fig.layout.meta['dpi']``）。
- **按轴调用。** 回调只拿到这根轴自己的东西，两个后端的调用形状见 `~plotlib.plotter.DataPlotter` 的说明。
  X 轴左右共用：右轴回调里的 ``x`` 设置也作用在共用的 X 轴上（与 matplotlib 的 ``twinx`` 一样）；
  边框和刻度在右轴回调里只改右侧。要一次改整张图，用绘图方法的 ``figure_formatter``。
- **创建时就报错。** 只收标准写法（如 ``'dash'``、``'circle'``、``'red'``）；后端写法（如 ``'--'``、``'o'``）
  以及后端做不到的设置（Plotly 的 ``scaler``、``'symlog'``、次刻度文字的字号、图例拖动）在创建回调时就报错，
  不等到画图。
- **custom。** ``custom`` 里的自定义回调直接拿各后端的原生对象，不做翻译。

Examples
--------
>>> from plotlib import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle
>>> axes_fmt = make_axes_formatter(
...     x=AxisStyle(scale='log', limits=(0.001, None), format='{x:.0e}'),
...     y=AxisStyle(limits=(None, 0.002)),
...     frame=FrameStyle(top=True),
...     ticks=TickStyle(length=10),
...     custom=[lambda ax, fig: ax.grid(True)],
... )
>>> lines_fmt = make_lines_formatter(LineStyle(width=2, linestyle='dash'))
>>> legend_fmt = make_legend_formatter(LegendStyle(font_size=12, position='upper left'))
>>> plotter.plot_multiline(axes_formatter=axes_fmt, lines_formatter=lines_fmt, legend_formatter=legend_fmt)

Plotly 写法相同，只加 ``backend='plotly'``。
"""
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, overload

from matplotlib.lines import Line2D

if TYPE_CHECKING:
    # 仅用于类型提示；只用 matplotlib 时不需要安装 Plotly。
    import plotly.graph_objects as go
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.legend import Legend

from .backends.matplotlib_styles import apply_axis, apply_frame, apply_legend, apply_minor, apply_tick_params
from .backends.plotly_styles import apply_axis as apply_plotly_axis
from .backends.plotly_styles import apply_frame as apply_plotly_frame
from .backends.plotly_styles import apply_ticks as apply_plotly_ticks
from .backends.plotly_styles import figure_dpi
from .plot_spec import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle
from .style import (Backend, check_axis_style, check_backend, check_frame, check_legend_style, check_line_style,
                    check_ticks, translate_axis_style, translate_frame, translate_legend_style, translate_line_style,
                    translate_ticks)

# 各 backend 返回的回调类型；入口函数用 overload 按 backend 选择其一。
type MplAxesFormatter = Callable[[Axes, Figure], None]
type MplLinesFormatter = Callable[[Iterable[Line2D]], None]
type MplLegendFormatter = Callable[[Iterable[Legend]], None]
type PlotlyAxesFormatter = Callable[[str, go.Figure], None]            # (轴名, fig)
type PlotlyLinesFormatter = Callable[[Iterable[Any]], None]            # 这根轴的 trace 列表
type PlotlyLegendFormatter = Callable[[Iterable[go.layout.Legend]], None]


# ══════════════════════════════════════════════
# 坐标轴：x / y（AxisStyle）、边框（FrameStyle）、刻度（TickStyle）
# ══════════════════════════════════════════════
@overload
def make_axes_formatter(x: AxisStyle | None = ..., y: AxisStyle | None = ..., frame: FrameStyle | None = ...,
                        ticks: TickStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                        backend: Literal["matplotlib"] = ...) -> MplAxesFormatter: ...
@overload
def make_axes_formatter(x: AxisStyle | None = ..., y: AxisStyle | None = ..., frame: FrameStyle | None = ...,
                        ticks: TickStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                        backend: Literal["plotly"]) -> PlotlyAxesFormatter: ...
@overload
def make_axes_formatter(x: AxisStyle | None = ..., y: AxisStyle | None = ..., frame: FrameStyle | None = ...,
                        ticks: TickStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                        backend: Backend) -> MplAxesFormatter | PlotlyAxesFormatter: ...
def make_axes_formatter(x: AxisStyle | None = None, y: AxisStyle | None = None, frame: FrameStyle | None = None,
                        ticks: TickStyle | None = None, custom: Iterable[Callable] | None = None, *,
                        backend: Backend = "matplotlib") -> MplAxesFormatter | PlotlyAxesFormatter:
    """
    创建坐标轴回调，把样式对象应用到一根轴上。

    只修改样式对象里写了的字段；没写的沿用 ``DataPlotter`` 的全局设置和版式预设。

    Parameters
    ----------
    x, y : AxisStyle, optional
        X、Y 方向的刻度类型、范围、刻度格式、显示值缩放和着色。
    frame : FrameStyle, optional
        这根轴的边框。左轴的回调改 X、Y 两根轴线和上、右两条边；右轴的回调只改右侧。
    ticks : TickStyle, optional
        这根轴的刻度（X、Y 两个方向）。右轴的回调只改右侧的 Y 轴。
    custom : iterable of callable, optional
        自定义回调，在上面的设置之后依次调用：matplotlib 以 ``(ax, fig)`` 调用，
        Plotly 以 ``(轴名, fig)`` 调用。直接拿原生对象，不做翻译。
    backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
        回调作用的后端。

    Returns
    -------
    callable
        matplotlib：``formatter(ax, fig)``；Plotly：``formatter(axis_name, fig)``，
        *axis_name* 是 layout 里的轴名（``'yaxis'`` / ``'yaxis2'``），由后端传入。

    Raises
    ------
    TypeError, ValueError
        样式对象写法不对，或这个后端做不到（如 Plotly 的 ``scaler``、``'symlog'``、次刻度文字的字号）。
        创建时就报错。

    See Also
    --------
    combine_formatters : 把几个坐标轴回调合成一个。

    Notes
    -----
    ``limits`` 永远写数据值。刻度类型和范围可以分在几个回调里设，先后顺序不影响结果：
    这次写了 ``limits`` 时整体替换上一次的范围（写 None 的一端恢复自动）；
    只改 ``scale`` 时，已有的范围按新的刻度类型换算。

    Examples
    --------
    >>> fmt = make_axes_formatter(x=AxisStyle(scale='log', limits=(1, 1e5)),
    ...                           y=AxisStyle(format='{y:.1e}'),
    ...                           ticks=TickStyle(minor_labels='short'))
    >>> DataPlotter(data).plot_multiline(axes_formatter=fmt)

    双 Y 轴只改右轴：

    >>> right = make_axes_formatter(y=AxisStyle(limits=(0, 10)))
    >>> DataPlotter(data).plot_dual_y(right_axes_formatter=right)
    """
    check_backend(backend)
    # 写错或后端做不到的，创建时就报错（不等到画图）
    for style in (x, y):
        if style is not None:
            check_axis_style(style, backend)
    if frame is not None:
        check_frame(frame)
    if ticks is not None:
        check_ticks(ticks, backend)
    custom = list(custom or ())

    if backend == "matplotlib":
        x_native = None if x is None else translate_axis_style(x, backend, 'x')
        y_native = None if y is None else translate_axis_style(y, backend, 'y')
        frame_native = None if frame is None else translate_frame(frame, backend)
        tick_native = None if ticks is None else translate_ticks(ticks, backend)

        def formatter(ax, fig, *_args, **_kwargs):
            _ = _args, _kwargs  # 标记为有意未使用
            if x_native is not None:
                apply_axis(ax, 'x', x_native)
            if y_native is not None:
                apply_axis(ax, 'y', y_native)
            if frame_native is not None:
                apply_frame(ax, frame_native)
            # 刻度放在改刻度类型之后：改类型会重置次刻度；这里照改，后端的全局补设就不会再动它
            if tick_native is not None:
                apply_tick_params(ax, tick_native)
                apply_minor(ax, tick_native, only_defaults=False)
            for func in custom:
                func(ax, fig)

        return formatter

    def plotly_formatter(axis: str, fig: go.Figure):
        """
        *axis* 是这根轴在 layout 里的名字（``'yaxis'`` / ``'yaxis2'``），由后端传入；X 轴左右共用 ``'xaxis'``。
        样式对象在应用时才翻译（`plotlib.backends.plotly_styles`）：磅按这张图的 dpi 换算，
        对数轴的边界按轴的实际类型换算。
        """
        if x is not None:
            apply_plotly_axis(fig, 'xaxis', x, 'x')
        if y is not None:
            apply_plotly_axis(fig, axis, y, 'y')
        if frame is not None:
            apply_plotly_frame(fig, axis, frame)
        if ticks is not None:
            apply_plotly_ticks(fig, axis, ticks)
        for func in custom:
            func(axis, fig)

    return plotly_formatter


# ══════════════════════════════════════════════
# 线（LineStyle）
# ══════════════════════════════════════════════
@overload
def make_lines_formatter(style: LineStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                         backend: Literal["matplotlib"] = ...) -> MplLinesFormatter: ...
@overload
def make_lines_formatter(style: LineStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                         backend: Literal["plotly"]) -> PlotlyLinesFormatter: ...
@overload
def make_lines_formatter(style: LineStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                         backend: Backend) -> MplLinesFormatter | PlotlyLinesFormatter: ...
def make_lines_formatter(style: LineStyle | None = None, custom: Iterable[Callable] | None = None, *,
                         backend: Backend = "matplotlib") -> MplLinesFormatter | PlotlyLinesFormatter:
    """
    创建线条回调，把 `LineStyle` 写了的字段改到这根轴的每一条线上。

    Parameters
    ----------
    style : LineStyle, optional
        要改的线宽、颜色、线型、标记、标记大小；没写的字段不改。不给时什么都不改（只跑 *custom*）。
    custom : iterable of callable, optional
        自定义回调，对每条线依次调用：matplotlib 收 ``Line2D`` 等曲线对象，Plotly 收 trace。
    backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
        回调作用的后端。

    Returns
    -------
    callable
        ``formatter(lines)``，*lines* 是这根轴上的线（Plotly 是 trace）组成的列表。

    Raises
    ------
    TypeError, ValueError
        *style* 写法不对，创建时就报错。

    Notes
    -----
    - 写了 ``color`` 会覆盖按样品分配的颜色，所有线变成同一颜色，通常只在一根轴只有一条线时使用。
      线和标记一起改色。
    - Plotly 里给纯线条写了 ``marker`` 时，会把绘制模式改成「线 + 点」，标记才看得见。
    - 散点只有颜色、标记会生效；柱状图的格式化尚未独立出来：Plotly 跳过柱状图，
      matplotlib 给柱状图改颜色目前会报错。

    Examples
    --------
    >>> fmt = make_lines_formatter(LineStyle(width=1.5, linestyle='dash', marker='circle'))
    >>> DataPlotter(data).plot_xy(lines_formatter=fmt)
    """
    check_backend(backend)
    style = style or LineStyle()
    check_line_style(style)            # 非标准写法创建时就报错
    custom = list(custom or ())

    if backend == "matplotlib":
        native = translate_line_style(style, backend)

        def formatter(lines, *_args, **_kwargs):
            _ = _args, _kwargs
            for line in lines:
                if isinstance(line, Line2D):
                    line.set(**native)
                elif 'color' in native:         # 散点、柱：只有颜色看得见
                    line.set_color(native['color'])
                for func in custom:
                    func(line)

        return formatter

    def plotly_formatter(traces):
        import plotly.graph_objects as go

        for trace in traces:
            if not isinstance(trace, go.Scatter):
                continue
            # trace.figure 是它所在的图：按这张图的 dpi 把磅换成像素
            native = translate_line_style(style, 'plotly', figure_dpi(trace.figure))
            trace.update(**native)      # update 合并嵌套属性，没写的保持不变
            # 写了标记时，让纯线条也显示标记
            mode = str(trace.mode or "lines")
            if style.marker is not None and "markers" not in mode:
                trace.mode = mode + "+markers"
            for func in custom:
                func(trace)

    return plotly_formatter


# ══════════════════════════════════════════════
# 图例（LegendStyle）
# ══════════════════════════════════════════════
@overload
def make_legend_formatter(style: LegendStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                          backend: Literal["matplotlib"] = ...) -> MplLegendFormatter: ...
@overload
def make_legend_formatter(style: LegendStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                          backend: Literal["plotly"]) -> PlotlyLegendFormatter: ...
@overload
def make_legend_formatter(style: LegendStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                          backend: Backend) -> MplLegendFormatter | PlotlyLegendFormatter: ...
def make_legend_formatter(style: LegendStyle | None = None, custom: Iterable[Callable] | None = None, *,
                          backend: Backend = "matplotlib") -> MplLegendFormatter | PlotlyLegendFormatter:
    """
    创建图例回调，把 `LegendStyle` 写了的字段改到图例上。

    一张图只有一个图例，归左轴，所以这个回调只能交给 ``legend_formatter``
    （双 Y 轴的 ``right_legend_formatter`` 会报错）。

    Parameters
    ----------
    style : LegendStyle, optional
        要改的位置、字号、边框、能否拖动；没写的字段不改。位置的写法与版式预设相同，见 `LegendStyle`。
    custom : iterable of callable, optional
        自定义回调，对图例依次调用：matplotlib 收 ``Legend``，Plotly 收 ``fig.layout.legend``。
    backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
        回调作用的后端。

    Returns
    -------
    callable
        ``formatter(legends)``：matplotlib 的 *legends* 是 ``[Legend]``，Plotly 是 ``[fig.layout.legend]``。

    Raises
    ------
    ValueError
        *style* 写法不对；或在 Plotly 后端写了 ``draggable=True``。Plotly 的图例拖动是显示时的设置：
        ``fig.show(config={'edits': {'legendPosition': True}})``。

    Examples
    --------
    >>> fmt = make_legend_formatter(LegendStyle(position='upper left', font_size=12, frame=True))
    >>> DataPlotter(data).plot_multiline(legend_formatter=fmt)
    """
    check_backend(backend)
    style = style or LegendStyle()
    check_legend_style(style, backend)
    if backend == 'plotly' and style.draggable:
        raise ValueError("Plotly 图例拖动请在显示时设置 fig.show(config={'edits': {'legendPosition': True}})")
    custom = list(custom or ())

    if backend == "matplotlib":
        native = translate_legend_style(style, backend)

        def formatter(legends, *_args, **_kwargs):
            _ = _args, _kwargs
            for legend in legends:
                apply_legend(legend, native)
                for func in custom:
                    func(legend)

        return formatter

    def plotly_formatter(legends):
        for legend in legends:
            # legend.figure 是它所在的图：按这张图的 dpi 把字号换成像素
            legend.update(translate_legend_style(style, 'plotly', figure_dpi(legend.figure)))
            for func in custom:
                func(legend)

    return plotly_formatter


def combine_formatters(*formatters: Callable[..., Any] | None) -> Callable[..., None]:
    """
    把几个同一种的回调合成一个：按传入顺序依次调用，参数原样转交。两个后端通用。

    Parameters
    ----------
    *formatters : callable or None
        同一种回调，如几个 `make_axes_formatter` 的结果，或参数形状相同的自定义函数。None 会被跳过，
        方便按条件拼装。三种回调的参数形状不同，只能合并同一种（轴回调和轴回调、线回调和线回调）。

    Returns
    -------
    callable
        合成后的回调，交给对应的参数（几个轴回调合成后交给 ``axes_formatter``，依此类推）。

    Examples
    --------
    >>> fmt = combine_formatters(make_axes_formatter(x=AxisStyle(scale='log')), my_axes_tweak)
    >>> DataPlotter(data).plot_multiline(axes_formatter=fmt)
    """
    active = [f for f in formatters if f is not None]

    def combined(*args, **kwargs) -> None:
        for formatter in active:
            formatter(*args, **kwargs)

    return combined
