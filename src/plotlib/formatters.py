"""
绘图格式化器工厂（2026-11-20 样式对象化）：参数是样式对象（plot_spec.py），按 backend 返回 matplotlib 或 Plotly 的回调。

使用方式（matplotlib，默认 backend；Plotly 加 backend='plotly'，写法相同）:
    from plotlib import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle

    axes_fmt = make_axes_formatter(
        x=AxisStyle(scale='log', limits=(0.001, None), format='{x:.0e}'),
        y=AxisStyle(limits=(None, 0.002)),
        frame=FrameStyle(top=True),          # 这根轴的边框
        ticks=TickStyle(length=10),          # 这根轴的刻度
        custom=[lambda ax, fig: ax.grid(True)],
    )
    lines_fmt = make_lines_formatter(LineStyle(width=2, linestyle='dash'))
    legend_fmt = make_legend_formatter(LegendStyle(font_size=12, position='upper left'))

    plotter.plot_multiline(axes_formatter=axes_fmt, lines_formatter=lines_fmt, legend_formatter=legend_fmt)
    # 同一种回调可以用 combine_formatters 合成一个（两个后端都可以）

注意事项:
    - 样式对象里没写的字段（None）不改：沿用 DataPlotter(...) 的全局设置和版式预设（不会覆盖按样品分配的颜色、
      预设的刻度格式）。刻度类型也一样，没写就不调用 set_*scale（以前总是调用，会冲掉预设的刻度格式）。
    - 单位：线宽、标记大小、字号、刻度长短都是磅；Plotly 按这张图的 dpi 换成像素（后端记在 fig.layout.meta['dpi']）。
    - 回调由后端按轴调用，只拿到这根轴自己的东西（第三方审查 E 起，两个后端形状对应）：
        matplotlib：轴 (ax, fig)、线条 (这根轴的 Line2D 列表)、图例 (legends)；
        Plotly：    轴 (轴名, fig)，如 ('yaxis2', fig)、线条 (这根轴的 trace 列表)、图例 ([fig.layout.legend])。
      X 轴左右共用：右轴回调里的 x 设置也作用在共用的 X 轴上（与 matplotlib twinx 一样）；
      边框、刻度在右轴回调里只改右侧（右轴自己的轴线、Y 轴）。要一次改整张图，用绘图方法的 figure_formatter(fig, axes)。
    - 写法只收 style.py 的标准写法（如 'dash'、'circle'、'red'）；后端写法（如 '--'、'o'）在创建 formatter 时就报错，
      后端做不到的设置（Plotly 的 scaler、symlog / logit、次刻度文字的字号、图例拖动）也在创建时报错。
    - custom 里的自定义回调用各 backend 的原生对象，不自动翻译：
      轴为 (ax, fig) 或 (轴名, fig)，线为 Line2D 或 Scatter，图例为 Legend 或 layout.Legend。
    - Plotly 刻度格式支持 {x:.Nf}、{x:.Ne}、{x:.Ng}、{x:.N%}。
    - Plotly 图例拖动属于显示配置，需要时使用 fig.show(config={"edits": {"legendPosition": True}})。
"""
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, cast, overload

from matplotlib.lines import Line2D

if TYPE_CHECKING:
    # 仅用于类型提示；只用 matplotlib 时不需要安装 Plotly。
    import plotly.graph_objects as go
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.legend import Legend

from .backends.matplotlib_styles import apply_axis, apply_frame, apply_legend, apply_minor, apply_tick_params
from .plot_spec import Appearance, AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle
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


def _figure_dpi(fig) -> float:
    """这张图的 dpi：后端画图时记在 fig.layout.meta['dpi']；不是后端画的图（或拿不到图）用默认 dpi。"""
    meta = None if fig is None else cast("go.Layout", fig.layout).meta
    return meta.get('dpi', Appearance().dpi) if isinstance(meta, dict) else Appearance().dpi


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
    坐标轴回调。x、y 各一个 AxisStyle（刻度类型、范围、刻度格式、换算、着色）；frame、ticks 改这根轴的边框和刻度。
    都只改写了的字段，没给的沿用全局与预设。custom：自定义回调列表，matplotlib 以 (ax, fig) 调用，Plotly 以 (轴名, fig) 调用。
    返回：matplotlib formatter(ax, fig)；Plotly formatter(轴名, fig)。
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

    x_native = None if x is None else translate_axis_style(x, backend, 'x')
    y_native = None if y is None else translate_axis_style(y, backend, 'y')

    def plotly_formatter(axis: str, fig: go.Figure):
        """axis 是这根轴在 layout 里的名字（'yaxis' / 'yaxis2'），由后端按轴传入；X 轴左右共用 'xaxis'。"""
        if x_native is not None:
            fig.update_layout(xaxis=x_native)
        if y_native is not None:
            fig.update_layout({axis: y_native})
        if frame is not None:
            _apply_plotly_frame(fig, axis, translate_frame(frame, 'plotly', _figure_dpi(fig)))
        if ticks is not None:
            _apply_plotly_ticks(fig, axis, ticks)
        for func in custom:
            func(axis, fig)

    return plotly_formatter


def _apply_plotly_frame(fig: go.Figure, axis: str, frame: dict) -> None:
    """
    单轴的边框（Plotly，对照 matplotlib_styles.apply_frame）：左轴回调改 X、Y 两根轴的线宽，上边 = X 轴镜像、右边 = Y 轴镜像；
    右轴回调只改右轴的线宽，上边照改，右边就是右轴自己的轴线。有右轴时左 Y 轴不镜像（否则会叠在右轴上）。
    """
    layout = cast(Any, fig.layout)
    left = axis == 'yaxis'
    if 'linewidth' in frame:
        for name in (['xaxis', axis] if left else [axis]):
            fig.update_layout({name: dict(linewidth=frame['linewidth'])})
    if 'top' in frame:
        fig.update_layout(xaxis_mirror=frame['top'])
    if 'right' in frame and left:
        fig.update_layout(yaxis_mirror=frame['right'] and layout.yaxis2.overlaying is None)


def _apply_plotly_ticks(fig: go.Figure, axis: str, ticks: TickStyle) -> None:
    """
    单轴的刻度（Plotly）：磅按这张图的 dpi 换成像素。
    左轴回调连 X 轴一起改（对应 matplotlib 左轴的 x、y）；右轴回调只改自己的 Y 轴（X 轴左右共用，归左轴）。
    """
    native = translate_ticks(ticks, 'plotly', _figure_dpi(fig))
    for target in (['xaxis', axis] if axis == 'yaxis' else [axis]):
        settings = dict(native)
        # Plotly 的 minor.ticks 同时管次刻度的显示和朝向：只改朝向（没写 minor）时，不能把关掉的次刻度打开
        if ticks.minor is None and 'ticks' in settings.get('minor', {}) and not _minor_ticks_shown(fig, target):
            settings['minor'] = {k: v for k, v in settings['minor'].items() if k != 'ticks'}
        fig.update_layout({target: settings})


def _minor_ticks_shown(fig: go.Figure, axis: str) -> bool:
    """这根轴现在显不显示次刻度：轴上写了就看轴上的，没写看模板（模板只有 xaxis / yaxis 两套，yaxis2 用 yaxis 的）。"""
    # layout[轴名] 的类型标注过宽（Plotly 按名字动态取子对象），按 Any 读
    layout = cast(Any, fig.layout)
    value = layout[axis].minor.ticks
    if value is None:
        template_axis = 'xaxis' if axis.startswith('x') else 'yaxis'
        value = layout.template.layout[template_axis].minor.ticks
    return bool(value)


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
    线条回调：把 LineStyle 写了的字段改到这根轴的每条线上（颜色会覆盖按样品分配的颜色，通常只在单条线时用；
    线和点一起改色，纯散点看得见的是点）。custom：自定义回调列表，以单条 Line2D 或 Scatter 调用。
    返回：matplotlib formatter(lines)；Plotly formatter(traces)，只改其中的 Scatter。
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
            native = translate_line_style(style, 'plotly', _figure_dpi(trace.figure))
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
    图例回调：把 LegendStyle 写了的字段改到图例上（位置写法见 style.LEGEND_POSITIONS，与排版预设同一套）。
    custom：自定义回调列表，以 matplotlib Legend 或 Plotly layout.Legend 调用。
    返回：matplotlib formatter(legends)；Plotly formatter(legends)，legends 是 [fig.layout.legend]。
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
            legend.update(translate_legend_style(style, 'plotly', _figure_dpi(legend.figure)))
            for func in custom:
                func(legend)

    return plotly_formatter


def combine_formatters(*formatters: Callable[..., Any] | None) -> Callable[..., None]:
    """把同一种回调合成一个，按传入顺序依次调用、参数原样转交；None 会被跳过。两个后端通用。

    Args:
        formatters: 同一种的回调，如几个 make_axes_formatter(...) 的结果，或参数形状相同的自定义函数。

    Returns:
        合成的回调，交给对应的参数（几个轴回调合成后交给 axes_formatter，依此类推）。

    Example:
        fmt = combine_formatters(make_axes_formatter(x=AxisStyle(scale='log')), my_axes_tweak)
        DataPlotter(data).plot_multiline(axes_formatter=fmt)
    （第三方审查 E 以前 Plotly 的回调都收 fig，可以把轴、线、图例回调合成一个；现在三种回调参数不同，只合并同一种。）
    """
    active = [f for f in formatters if f is not None]

    def combined(*args, **kwargs) -> None:
        for formatter in active:
            formatter(*args, **kwargs)

    return combined
