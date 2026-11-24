"""
从样式对象创建 Matplotlib 或 Plotly 格式化回调。

- `make_axes_formatter`：坐标轴（刻度类型、范围、刻度格式、着色、边框、刻度）；
- `make_lines_formatter`：折线（线宽、颜色、线型、标记）；
- `make_scatter_formatter`：散点（颜色、标记、大小）；
- `make_bar_formatter`：柱状图（填充、描边、纹理、误差棒）；
- `make_legend_formatter`：图例（位置、字号、边框、拖动）；
- `combine_formatters`：按顺序组合相同类型的回调。

生成的回调放进 `~plotlib.plot_spec.AxesFormatter` 的 ``axes``、``lines``、``scatter``、``bars``、``legend`` 字段，
交给绘图方法的 *formatters*，由后端逐轴调用。线条回调只收折线，散点回调只收散点，柱状图回调只收柱状图的系列。

Notes
-----
未指定的字段保留原有样式。线宽、标记大小、字号和刻度尺寸均以磅为单位，
Plotly 使用 ``fig.layout.meta['dpi']`` 换算为像素。

按轴回调的签名见 `~plotlib.plotter.DataPlotter`。双 Y 轴图共用 X 轴，因此右侧回调中的
``x`` 设置也会更新共用轴。右侧的边框和刻度设置只作用于右侧。
图形级的修改可通过 ``figure_formatter`` 完成。

工厂在创建回调时校验样式取值和后端支持情况。``custom`` 中的回调在应用样式后接收后端原生对象。

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
>>> plotter.plot(formatters=AxesFormatter(axes=axes_fmt, lines=lines_fmt, legend=legend_fmt))

Plotly 写法相同，只加 ``backend='plotly'``。
"""
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, overload

from matplotlib.lines import Line2D
from matplotlib.markers import MarkerStyle

if TYPE_CHECKING:
    # 仅用于类型提示；只用 matplotlib 时不需要安装 Plotly。
    import plotly.graph_objects as go
    from matplotlib.axes import Axes
    from matplotlib.collections import PathCollection
    from matplotlib.container import BarContainer
    from matplotlib.figure import Figure
    from matplotlib.legend import Legend

from .backends.matplotlib_styles import apply_axis, apply_frame, apply_legend, apply_minor, apply_tick_params
from .backends.plotly_styles import apply_axis as apply_plotly_axis
from .backends.plotly_styles import apply_frame as apply_plotly_frame
from .backends.plotly_styles import apply_ticks as apply_plotly_ticks
from .backends.plotly_styles import figure_dpi
from .plot_spec import AxisStyle, BarStyle, FrameStyle, LegendStyle, LineStyle, ScatterStyle, TickStyle
from .style import (HOLLOW_FILL, Backend, check_axis_style, check_backend, check_bar_style, check_frame,
                    check_legend_style, check_line_style, check_scatter_style, check_ticks, remember_fill,
                    remembered_fill, translate_axis_style, translate_bar_style, translate_color, translate_frame,
                    translate_legend_style, translate_line_style, translate_scatter_style, translate_ticks)

# 各 backend 返回的回调类型；入口函数用 overload 按 backend 选择其一。
type MplAxesFormatter = Callable[[Axes, Figure], None]
type MplLinesFormatter = Callable[[Iterable[Line2D]], None]
type MplScatterFormatter = Callable[[Iterable[PathCollection]], None]
type MplLegendFormatter = Callable[[Iterable[Legend]], None]
type PlotlyAxesFormatter = Callable[[str, go.Figure], None]            # (轴名, fig)
type PlotlyLinesFormatter = Callable[[Iterable[Any]], None]            # 这根轴的折线 trace 列表
type PlotlyScatterFormatter = Callable[[Iterable[Any]], None]          # 这根轴的散点 trace 列表
type PlotlyLegendFormatter = Callable[[Iterable[go.layout.Legend]], None]
type MplBarsFormatter = Callable[[Iterable[BarContainer]], None]
type PlotlyBarsFormatter = Callable[[Iterable[Any]], None]            # 各系列的 trace 列表


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
    创建应用坐标轴样式的回调。回调只更新显式指定的字段。

    Parameters
    ----------
    x, y : AxisStyle, optional
        X、Y 方向的刻度类型、范围、刻度格式、显示值缩放和着色。
    frame : FrameStyle, optional
        这根轴的边框。左轴的回调改 X、Y 两根轴线和上、右两条边；右轴的回调只改右侧。
    ticks : TickStyle, optional
        这根轴的刻度（X、Y 两个方向）。右轴的回调只改右侧的 Y 轴。
    custom : iterable of callable, optional
        样式应用后按顺序执行的回调。Matplotlib 传入 ``(ax, fig)``，
        Plotly 传入 ``(轴名, fig)``。
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
        样式参数无效，或所选后端不支持该设置。

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
    >>> DataPlotter(data).plot(formatters=AxesFormatter(axes=fmt))

    双 Y 轴只改右轴：

    >>> right = make_axes_formatter(y=AxisStyle(limits=(0, 10)))
    >>> DataPlotter(data).plot([Layer(0, 1), Layer(2, 3, side='right')], by='sample',
    ...                        formatters={'right': AxesFormatter(axes=right)})
    """
    check_backend(backend)
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
            # 轴类型变更会重置次刻度，因此在变更后应用刻度样式。
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
    创建线条回调，把 `LineStyle` 写了的字段改到这根轴的每一条折线上。

    Parameters
    ----------
    style : LineStyle, optional
        折线样式。省略时只执行 *custom*。
    custom : iterable of callable, optional
        自定义回调，对每条线依次调用：matplotlib 收 ``Line2D``，Plotly 收 trace。
    backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
        回调作用的后端。

    Returns
    -------
    callable
        ``formatter(lines)``，*lines* 是这根轴上的折线（Plotly 是 trace）组成的列表；散点不在其中。

    Raises
    ------
    TypeError, ValueError
        *style* 含无效字段值。

    Notes
    -----
    - ``color`` 统一设置该轴上折线的颜色，包括线条和标记。
    - 对 Plotly 折线设置 ``marker`` 会启用带标记的折线模式。
    - 散点用 `make_scatter_formatter`；同一根轴上有折线和散点时，两个回调各改各的。

    Examples
    --------
    >>> fmt = make_lines_formatter(LineStyle(width=1.5, linestyle='dash', marker='circle'))
    >>> DataPlotter(data).plot(by='sample', formatters=AxesFormatter(lines=fmt))
    """
    check_backend(backend)
    style = style or LineStyle()
    check_line_style(style)
    custom = list(custom or ())

    if backend == "matplotlib":
        native = translate_line_style(style, backend)

        def formatter(lines, *_args, **_kwargs):
            _ = _args, _kwargs
            for line in lines:
                line.set(**native)
                for func in custom:
                    func(line)

        return formatter

    def plotly_formatter(traces):
        for trace in traces:
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
# 散点（ScatterStyle）
# ══════════════════════════════════════════════
@overload
def make_scatter_formatter(style: ScatterStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                           backend: Literal["matplotlib"] = ...) -> MplScatterFormatter: ...
@overload
def make_scatter_formatter(style: ScatterStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                           backend: Literal["plotly"]) -> PlotlyScatterFormatter: ...
@overload
def make_scatter_formatter(style: ScatterStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                           backend: Backend) -> MplScatterFormatter | PlotlyScatterFormatter: ...
def make_scatter_formatter(style: ScatterStyle | None = None, custom: Iterable[Callable] | None = None, *,
                           backend: Backend = "matplotlib") -> MplScatterFormatter | PlotlyScatterFormatter:
    """
    创建按轴应用 `ScatterStyle` 的散点格式化回调。

    Parameters
    ----------
    style : ScatterStyle, optional
        应用于该轴各组散点的样式。省略时仅执行 *custom*。
    custom : iterable of callable, optional
        应用样式后，按给定顺序对每组散点调用。Matplotlib 回调接收 ``PathCollection``，
        Plotly 回调接收 trace。
    backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
        回调作用的后端。

    Returns
    -------
    callable
        ``formatter(scatters)``，其中 *scatters* 是该轴上各组散点对象的列表。

    Raises
    ------
    TypeError, ValueError
        *style* 含无效字段值。

    Examples
    --------
    >>> fmt = make_scatter_formatter(ScatterStyle(color='black', marker='square', size=8))
    >>> DataPlotter(data).plot(Layer(kind='scatter'), formatters=AxesFormatter(scatter=fmt))
    """
    check_backend(backend)
    style = style or ScatterStyle()
    check_scatter_style(style)
    custom = list(custom or ())
    color = None if style.color is None else translate_color(style.color, backend)
    refill = style.filled is True and style.color is None

    def fill_of(artist, native: dict, key: str, current_fill, current_edge) -> dict:
        """
        记录当前填充色或显式指定的颜色，供空心散点恢复填充。

        仅指定 ``filled=True`` 时，空心散点优先恢复记录的填充色，其次使用当前描边色。
        """
        remember_fill(artist, current_fill)
        remember_fill(artist, color)
        if refill and current_fill is None:
            return {**native, key: remembered_fill(artist, current_edge)}
        return native

    if backend == "matplotlib":
        base = translate_scatter_style(style, backend)

        def formatter(scatters, *_args, **_kwargs):
            _ = _args, _kwargs
            for points in scatters:
                # 保留完整的 RGBA 数组，供恢复逐点配色。无可见填充时视为空心。
                faces, edges = points.get_facecolor(), points.get_edgecolor()
                current_fill = faces.copy() if len(faces) and (faces[:, 3] > 0).any() else None
                native = fill_of(points, base, 'facecolors', current_fill, edges.copy() if len(edges) else None)
                # 通过 PathCollection 的 setter 应用已转换的属性。
                setters = {'facecolors': points.set_facecolor, 'edgecolors': points.set_edgecolor,
                           'linewidths': points.set_linewidth, 'alpha': points.set_alpha,
                           's': lambda area: points.set_sizes([area])}
                for key, value in native.items():
                    if key in setters:
                        setters[key](value)
                if 'marker' in native:
                    marker = MarkerStyle(native['marker'])
                    points.set_paths([marker.get_path().transformed(marker.get_transform())])
                for func in custom:
                    func(points)

        return formatter

    def plotly_formatter(traces):
        for trace in traces:
            # 使用所属 Figure 的 DPI 将磅换算为像素。
            native = translate_scatter_style(style, 'plotly', figure_dpi(trace.figure))
            # 仅将字符串与透明填充值比较，逐点颜色数组作为整体保留。
            fill = trace.marker.color
            hollow = fill is None or (isinstance(fill, str) and fill == HOLLOW_FILL['plotly'])
            current_fill = None if hollow else fill
            trace.update(**fill_of(trace, native, 'marker_color', current_fill, trace.marker.line.color))
            for func in custom:
                func(trace)

    return plotly_formatter


# ══════════════════════════════════════════════
# 柱状图（BarStyle）
# ══════════════════════════════════════════════
@overload
def make_bar_formatter(style: BarStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                       backend: Literal["matplotlib"] = ...) -> MplBarsFormatter: ...
@overload
def make_bar_formatter(style: BarStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                       backend: Literal["plotly"]) -> PlotlyBarsFormatter: ...
@overload
def make_bar_formatter(style: BarStyle | None = ..., custom: Iterable[Callable] | None = ..., *,
                       backend: Backend) -> MplBarsFormatter | PlotlyBarsFormatter: ...
def make_bar_formatter(style: BarStyle | None = None, custom: Iterable[Callable] | None = None, *,
                       backend: Backend = "matplotlib") -> MplBarsFormatter | PlotlyBarsFormatter:
    """
    创建将 `BarStyle` 应用于各柱状图系列的回调。

    Parameters
    ----------
    style : BarStyle, optional
        柱状图样式。省略时仅执行 *custom*。端帽半长 ``capsize`` 须在绘制前通过 ``plot_bars(styles=...)`` 设置。
    custom : iterable of callable, optional
        应用样式后，对每个系列依次调用：matplotlib 收 ``BarContainer``，Plotly 收 trace。
    backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
        回调作用的后端。

    Returns
    -------
    callable
        ``formatter(bars)``，*bars* 是各个系列（matplotlib 是 ``BarContainer``，Plotly 是 trace）组成的列表。

    Raises
    ------
    TypeError, ValueError
        *style* 含无效字段值，或指定了 ``capsize``。

    Notes
    -----
    只更新显式指定的字段。纹理颜色随描边色更新，单独设置 ``hatch`` 时沿用当前描边色。
    ``hatch='none'`` 清除纹理。Matplotlib 在回调后重建图例，Plotly 的图例随 trace 自动更新。
    在 Plotly 堆叠图中，回调会将误差棒样式应用到用于绘制误差棒的散点 trace。

    Examples
    --------
    黑白图：

    >>> fmt = make_bar_formatter(BarStyle(color='white', edge_color='black', edge_width=1, hatch='slash'))
    >>> DataPlotter(data).plot_bars([1, 2], formatters=AxesFormatter(bars=fmt))
    """
    check_backend(backend)
    style = style or BarStyle()
    check_bar_style(style)
    if style.capsize is not None:
        raise ValueError("make_bar_formatter 不收 capsize：端帽长度在画之前定，请写在 plot_bars(styles=BarStyle(capsize=...))；"
                         "matplotlib 画好的误差棒没有端帽时不能再补上")
    custom = list(custom or ())

    if backend == "matplotlib":
        native = translate_bar_style(style, backend)
        patch_keys = {'color': 'facecolor', 'edgecolor': 'edgecolor', 'linewidth': 'linewidth', 'hatch': 'hatch'}
        patch_style = {patch_keys[key]: value for key, value in native.items() if key in patch_keys}

        def formatter(containers, *_args, **_kwargs):
            _ = _args, _kwargs
            for container in containers:
                for patch in container.patches:
                    patch.set(**patch_style)
                errorbar = container.errorbar
                if errorbar is not None:
                    _, caplines, barlines = errorbar.lines
                    for line in barlines:           # 误差棒的竖线（LineCollection）
                        if 'ecolor' in native:
                            line.set_color(native['ecolor'])
                        if 'elinewidth' in native:
                            line.set_linewidth(native['elinewidth'])
                    for cap in caplines:            # 端帽（标记 '_' 的 Line2D）
                        if 'ecolor' in native:
                            cap.set(color=native['ecolor'], markeredgecolor=native['ecolor'])
                        if 'elinewidth' in native:
                            cap.set_markeredgewidth(native['elinewidth'])
                for func in custom:
                    func(container)

        return formatter

    def plotly_formatter(traces):
        for trace in traces:
            # 使用所属 Figure 的 DPI 将磅换算为像素。
            native = translate_bar_style(style, 'plotly', figure_dpi(trace.figure))
            if style.hatch is not None and style.edge_color is None:
                native['marker_pattern_fgcolor'] = trace.marker.line.color     # 纹理跟随当前的描边色
            # 堆叠时误差棒在单独的散点 trace 上（画在所有柱之上），误差棒样式改到它那里
            errors_trace = getattr(trace, '_plotlib_errors', None)
            if errors_trace is not None:
                errors_trace.update(**{key: native.pop(key) for key in list(native) if key.startswith('error_y_')})
            trace.update(**native)
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
    创建更新整图图例样式的回调。

    将回调传给绘图方法的 ``legend_formatter``。

    Parameters
    ----------
    style : LegendStyle, optional
        图例的位置、字号、边框和拖动设置。未指定的字段保留原值。
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
        *style* 含无效字段值，或为 Plotly 指定了 ``draggable=True``。
        Plotly 的图例拖动可在显示时通过 ``fig.show(config={'edits': {'legendPosition': True}})`` 配置。

    Examples
    --------
    >>> fmt = make_legend_formatter(LegendStyle(position='upper left', font_size=12, frame=True))
    >>> DataPlotter(data).plot(formatters=AxesFormatter(legend=fmt))
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
    >>> DataPlotter(data).plot(formatters=AxesFormatter(axes=fmt))
    """
    active = [f for f in formatters if f is not None]

    def combined(*args, **kwargs) -> None:
        for formatter in active:
            formatter(*args, **kwargs)

    return combined
