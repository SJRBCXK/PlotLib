"""
绘图格式化器工厂模块

同一套格式参数，通过 backend 选择返回 matplotlib 或 Plotly 的格式回调。

使用方式（matplotlib，默认 backend）:
    axes_fmt = make_axes_formatter(
        xlim_left=0, xlim_right=10,
        custom_formation=[lambda ax, fig: ax.grid(True)],
    )
    lines_fmt = make_lines_formatter(linewidth=2, linestyle='--')
    legend_fmt = make_legend_formatter(legend_fontsize=12)

    plotter.plot_objects(
        axes_formatter=axes_fmt,
        lines_formatter=lines_fmt,
        legend_formatter=legend_fmt,
    )

使用方式（Plotly）:
    axes_fmt = make_axes_formatter(backend="plotly", xscale_type="log")
    lines_fmt = make_lines_formatter(backend="plotly", linestyle="--")
    legend_fmt = make_legend_formatter(backend="plotly", legend_fontsize=18)

    interactive_plot.plot_plotly_object(
        figure_formatter=combine_formatters(axes_fmt, lines_fmt, legend_fmt),
    )

注意事项:
    - 刻度格式、线条与图例参数默认为 None，表示保持原样；只修改明确传入的设置，
      因此不会覆盖绘图器按组分配的颜色，也不会覆盖自动刻度格式。
      坐标轴的尺度（默认 'linear'）、刻度线宽和 hide_spines 仍总会应用。
    - matplotlib 回调：轴 (ax, fig)、线条 (lines)、图例 (legends)。
      Plotly 回调：三者都接收 Figure，可组合后交给 figure_formatter。
    - 自定义回调使用各 backend 的原生对象，不自动翻译：
      轴为 (ax, fig) 或 (fig)，线为 Line2D 或 Scatter，图例为 Legend 或 layout.Legend。
    - Plotly 刻度格式支持 {x:.Nf}、{x:.Ne}、{x:.Ng}、{x:.N%}；
      暂不支持显示值缩放 xscaler/yscaler，以及 symlog/logit。
    - Plotly 图例拖动属于显示配置，需要时使用
      fig.show(config={"edits": {"legendPosition": True}})。
"""
import math
import re
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Literal, cast, overload

from matplotlib.ticker import FuncFormatter, LogLocator

if TYPE_CHECKING:
    # 仅用于类型提示；只用 matplotlib 时不需要安装 Plotly。
    import plotly.graph_objects as go
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from matplotlib.legend import Legend
    from matplotlib.lines import Line2D

type Backend = Literal["matplotlib", "plotly"]

# 各 backend 返回的回调类型；入口函数用 overload 按 backend 选择其一。
type MplAxesFormatter = Callable[[Axes, Figure], None]
type MplLinesFormatter = Callable[[Iterable[Line2D]], None]
type MplLegendFormatter = Callable[[Iterable[Legend]], None]
type PlotlyFormatter = Callable[[go.Figure], None]


def _check_backend(backend: Backend) -> None:
    if backend not in ("matplotlib", "plotly"):
        raise ValueError(f"不支持的 backend: {backend!r}")


class AxesFormatterFactory:
    """坐标轴格式化器工厂类"""

    @staticmethod
    def create(
        xlim_left=None,
        xlim_right=None,
        ylim_bottom=None,
        ylim_top=None,
        xscale_type='linear',
        yscale_type='linear',
        xscaler=1.0,
        yscaler=1.0,
        x_format=None,
        y_format=None,
        hide_spines=True,
        custom_formation=None,
        *,
        backend: Backend = "matplotlib",
    ):
        """
        创建坐标轴格式回调。

        参数:
            xlim_left / xlim_right: X 轴左右边界（数据值），None 表示自动。
            ylim_bottom / ylim_top: Y 轴上下边界（数据值），None 表示自动。
            xscale_type / yscale_type: 'linear' 或 'log'（matplotlib 另支持 symlog/logit）。
            xscaler / yscaler: 刻度文字显示值 = 刻度值 × scaler，不修改数据（仅 matplotlib）。
            x_format / y_format: 刻度数字格式，如 '{x:.2f}'、'{y:.1e}'；None 表示不改，
                保留 backend 的自动刻度（matplotlib 给了 scaler 时按 '{x:g}' 显示）。
            hide_spines: True 隐藏上/右边框；False 显示四周边框。
            custom_formation: 自定义回调列表，matplotlib 以 (ax, fig) 调用，Plotly 以 (fig) 调用。
            backend: 'matplotlib' 或 'plotly'，只能以关键字传入。

        返回:
            matplotlib: formatter(ax, fig)；Plotly: formatter(fig)。
        """
        _check_backend(backend)

        if backend == "matplotlib":
            def tick_formatter(fmt, key, scaler):
                """返回刻度文字格式器；不需要改时返回 None，保留 matplotlib 默认。"""
                if fmt is None and scaler == 1:
                    return None
                text_fmt: str = fmt or '{' + key + ':g}'
                return FuncFormatter(lambda v, _: text_fmt.format(**{key: v * scaler}))

            x_tick_formatter = tick_formatter(x_format, 'x', xscaler)
            y_tick_formatter = tick_formatter(y_format, 'y', yscaler)

            def formatter(ax, fig, *_args, **_kwargs):
                _ = _args, _kwargs  # 标记为有意未使用

                # X 轴
                ax.set_xscale(xscale_type)
                if xscale_type == 'log':
                    ax.xaxis.set_major_locator(LogLocator(base=10))
                if xlim_left is not None:
                    ax.set_xlim(left=xlim_left)
                if xlim_right is not None:
                    ax.set_xlim(right=xlim_right)
                if x_tick_formatter is not None:
                    ax.xaxis.set_major_formatter(x_tick_formatter)
                ax.xaxis.set_tick_params(which='both', width=3, direction='out')

                # Y 轴
                ax.set_yscale(yscale_type)
                if yscale_type == 'log':
                    ax.yaxis.set_major_locator(LogLocator(base=10))
                if ylim_bottom is not None:
                    ax.set_ylim(bottom=ylim_bottom)
                if ylim_top is not None:
                    ax.set_ylim(top=ylim_top)
                if y_tick_formatter is not None:
                    ax.yaxis.set_major_formatter(y_tick_formatter)
                ax.tick_params(axis='y', which='both', width=3, direction='out')

                # 隐藏上/右边框
                if hide_spines:
                    ax.spines['right'].set_visible(False)
                    ax.spines['top'].set_visible(False)

                for func in custom_formation or ():
                    func(ax, fig)

            return formatter

        # ── Plotly：创建回调前先校验，转换不了的设置立即报错 ──
        # Plotly 没有 Python FuncFormatter，只翻译可直接对应的数字格式。
        # None 表示不设置 tickformat，保留 Plotly 自动格式。
        tick_formats: list[str | None] = []
        for fmt in (x_format, y_format):
            if fmt is None:
                tick_formats.append(None)
                continue
            match = re.fullmatch(r"\{[xy]:(\.\d+[feg%])\}", fmt)
            if match is None:
                raise ValueError(f"Plotly 暂不支持此刻度格式: {fmt!r}")
            tick_formats.append(match.group(1))
        if xscaler != 1 or yscaler != 1:
            raise ValueError("Plotly 暂不支持显示值缩放 xscaler/yscaler；不会修改原始数据替代")
        if xscale_type not in ("linear", "log") or yscale_type not in ("linear", "log"):
            raise ValueError("Plotly 公共轴格式目前只支持 linear 和 log")

        axis_settings = []
        for scale, bounds, tick_format in (
            (xscale_type, (xlim_left, xlim_right), tick_formats[0]),
            (yscale_type, (ylim_bottom, ylim_top), tick_formats[1]),
        ):
            if scale == "log" and any(v is not None and v <= 0 for v in bounds):
                raise ValueError("对数轴边界必须大于 0")

            options: dict = dict(
                type=scale,
                tickwidth=3,
                ticks="outside",
                # hide_spines=False 时镜像轴线，对应 matplotlib 的上/右边框。
                mirror=not hide_spines,
            )
            if tick_format is not None:
                options["tickformat"] = tick_format
            if any(v is not None for v in bounds):
                # 公共输入使用数据值；Plotly 对数轴的 range 使用 log10。
                options["range"] = [
                    math.log10(v) if scale == "log" and v is not None else v
                    for v in bounds
                ]
                # 只给一侧边界时，另一侧保持自动。
                options["autorange"] = (
                    "min" if bounds[0] is None else
                    "max" if bounds[1] is None else False
                )
            axis_settings.append(options)

        def plotly_formatter(fig: go.Figure):
            fig.update_xaxes(axis_settings[0])
            fig.update_yaxes(axis_settings[1])
            for func in custom_formation or ():
                func(fig)

        return plotly_formatter


class LinesFormatterFactory:
    """线条格式化器工厂类"""

    @staticmethod
    def create(
        linewidth=None,
        linecolor=None,
        linestyle=None,
        linemarker=None,
        linemarkersize=None,
        custom_formations=None,
        *,
        backend: Backend = "matplotlib",
    ):
        """
        创建线条格式回调；参数为 None 时保持原样。

        参数:
            linewidth: 线宽。
            linecolor: 颜色；会覆盖所有曲线的按组配色，通常只在单条曲线时使用。
            linestyle: '-'、'--'、':'、'-.'。
            linemarker: 标记，如 'o'、's'、'^'、'v'、'D'、'+'、'x'。
            linemarkersize: 标记大小。
            custom_formations: 自定义回调列表，以单条 Line2D 或 Scatter 调用。
            backend: 'matplotlib' 或 'plotly'，只能以关键字传入。

        返回:
            matplotlib: formatter(lines)；Plotly: formatter(fig)，只修改 Scatter。
        """
        _check_backend(backend)

        if backend == "matplotlib":
            def formatter(lines, *_args, **_kwargs):
                _ = _args, _kwargs

                for line in lines:
                    if linewidth is not None:
                        line.set_linewidth(linewidth)
                    if linecolor is not None:
                        line.set_color(linecolor)
                    if linestyle is not None:
                        line.set_linestyle(linestyle)
                    # 未指定 marker 时不动它：set_marker(None) 在 matplotlib 3.10 会报错
                    if linemarker is not None:
                        line.set_marker(linemarker)
                    if linemarkersize is not None:
                        line.set_markersize(linemarkersize)
                    for func in custom_formations or ():
                        func(line)

            return formatter

        # ── Plotly ──
        import plotly.graph_objects as go

        dashes = {"-": "solid", "--": "dash", ":": "dot", "-.": "dashdot"}
        markers = {"o": "circle", "s": "square", "^": "triangle-up",
                   "v": "triangle-down", "D": "diamond", "+": "cross", "x": "x"}
        if linestyle is not None and linestyle not in dashes:
            raise ValueError(f"Plotly 暂不支持此公共线型: {linestyle!r}")
        if linemarker is not None and linemarker not in markers:
            raise ValueError(f"Plotly 暂不支持此公共标记: {linemarker!r}")

        line_options = {}
        if linewidth is not None:
            line_options["width"] = linewidth
        if linecolor is not None:
            line_options["color"] = linecolor
        if linestyle is not None:
            line_options["dash"] = dashes[linestyle]

        marker_options = {}
        if linemarker is not None:
            marker_options["symbol"] = markers[linemarker]
        if linemarkersize is not None:
            marker_options["size"] = linemarkersize

        def plotly_formatter(fig: go.Figure):
            for trace in fig.data:
                if not isinstance(trace, go.Scatter):
                    continue
                # update 合并嵌套属性，未传入的颜色等保持不变。
                if line_options:
                    trace.update(line=line_options)
                if marker_options:
                    trace.update(marker=marker_options)
                # 指定标记时，让纯线条也显示标记。
                mode = str(trace.mode or "lines")
                if linemarker is not None and "markers" not in mode:
                    trace.mode = mode + "+markers"
                for func in custom_formations or ():
                    func(trace)

        return plotly_formatter


class LegendsFormatterFactory:
    """图例格式化器工厂类"""

    @staticmethod
    def create(
        legend_location=None,
        legend_fontsize=None,
        legend_frameon=None,
        legend_draggable=None,
        custom_formations=None,
        *,
        backend: Backend = "matplotlib",
    ):
        """
        创建图例格式回调；参数为 None 时保持原样。

        参数:
            legend_location: 'best'、'upper right'、'lower left'、'center' 等。
                Plotly 不会自动寻找空位，'best' 使用右上角。
            legend_fontsize: 图例字号。
            legend_frameon: True 显示边框和白色背景；False 无边框、透明背景。
            legend_draggable: 是否可拖动（仅 matplotlib；Plotly 见模块说明）。
            custom_formations: 自定义回调列表，以 matplotlib Legend 或 Plotly layout.Legend 调用。
            backend: 'matplotlib' 或 'plotly'，只能以关键字传入。

        返回:
            matplotlib: formatter(legends)；Plotly: formatter(fig)。
        """
        _check_backend(backend)

        if backend == "matplotlib":
            def formatter(legends, *_args, **_kwargs):
                _ = _args, _kwargs

                for legend in legends:
                    # Legend 没有 set_fontsize，字号要逐个设到图例文字上
                    if legend_fontsize is not None:
                        for text in legend.get_texts():
                            text.set_fontsize(legend_fontsize)
                    if legend_frameon is not None:
                        legend.set_frame_on(legend_frameon)  # 方法名是 set_frame_on
                    if legend_draggable is not None:
                        legend.set_draggable(legend_draggable)
                    if legend_location is not None:
                        legend.set_loc(legend_location)
                    for func in custom_formations or ():
                        func(legend)

            return formatter

        # ── Plotly ──
        positions = {
            "best": (1, 1, "right", "top"),
            "upper right": (1, 1, "right", "top"),
            "upper left": (0, 1, "left", "top"),
            "lower right": (1, 0, "right", "bottom"),
            "lower left": (0, 0, "left", "bottom"),
            "center": (0.5, 0.5, "center", "middle"),
            "center left": (0, 0.5, "left", "middle"),
            "center right": (1, 0.5, "right", "middle"),
            "right": (1, 0.5, "right", "middle"),
            "upper center": (0.5, 1, "center", "top"),
            "lower center": (0.5, 0, "center", "bottom"),
        }
        if legend_location is not None and legend_location not in positions:
            raise ValueError(f"Plotly 暂不支持此公共图例位置: {legend_location!r}")
        # Plotly 图例默认不可拖动；开启拖动属于显示配置，不在 Figure 中。
        if legend_draggable:
            raise ValueError(
                "Plotly 图例拖动请在显示时设置 "
                "fig.show(config={'edits': {'legendPosition': True}})"
            )

        legend_options: dict = {}
        if legend_fontsize is not None:
            legend_options["font_size"] = legend_fontsize
        if legend_location is not None:
            x, y, xanchor, yanchor = positions[legend_location]
            legend_options.update(x=x, y=y, xanchor=xanchor, yanchor=yanchor)
        if legend_frameon is not None:
            legend_options.update(
                borderwidth=1 if legend_frameon else 0,
                bordercolor="black",
                bgcolor="white" if legend_frameon else "rgba(0,0,0,0)",
            )

        def plotly_formatter(fig: go.Figure):
            if legend_options:
                fig.update_layout(legend=legend_options)
            # fig.layout 的类型标注过宽；字符串形式避免运行时依赖 TYPE_CHECKING 中的 go。
            layout = cast("go.Layout", fig.layout)
            for func in custom_formations or ():
                func(layout.legend)

        return plotly_formatter


# 公共入口：backend 只能以关键字传入，默认保持现有 matplotlib 行为。
# overload 只服务类型检查：让编辑器按 backend 推断返回的回调签名。
@overload
def make_axes_formatter(
    *, backend: Literal["matplotlib"] = ..., **kwargs
) -> MplAxesFormatter: ...
@overload
def make_axes_formatter(*, backend: Literal["plotly"], **kwargs) -> PlotlyFormatter: ...
def make_axes_formatter(
    *, backend: Backend = "matplotlib", **kwargs
) -> MplAxesFormatter | PlotlyFormatter:
    """创建坐标轴格式回调；参数见 AxesFormatterFactory.create。"""
    return AxesFormatterFactory.create(backend=backend, **kwargs)


@overload
def make_lines_formatter(
    *, backend: Literal["matplotlib"] = ..., **kwargs
) -> MplLinesFormatter: ...
@overload
def make_lines_formatter(*, backend: Literal["plotly"], **kwargs) -> PlotlyFormatter: ...
def make_lines_formatter(
    *, backend: Backend = "matplotlib", **kwargs
) -> MplLinesFormatter | PlotlyFormatter:
    """创建线条格式回调；参数见 LinesFormatterFactory.create。"""
    return LinesFormatterFactory.create(backend=backend, **kwargs)


@overload
def make_legend_formatter(
    *, backend: Literal["matplotlib"] = ..., **kwargs
) -> MplLegendFormatter: ...
@overload
def make_legend_formatter(*, backend: Literal["plotly"], **kwargs) -> PlotlyFormatter: ...
def make_legend_formatter(
    *, backend: Backend = "matplotlib", **kwargs
) -> MplLegendFormatter | PlotlyFormatter:
    """创建图例格式回调；参数见 LegendsFormatterFactory.create。"""
    return LegendsFormatterFactory.create(backend=backend, **kwargs)


def combine_formatters(*formatters: PlotlyFormatter | None) -> PlotlyFormatter:
    """把多个 Plotly 回调合成一个，按传入顺序依次调用；None 会被跳过。

    Args:
        formatters: make_xxx_formatter(backend="plotly") 返回的回调，或任意 fn(fig)。

    Returns:
        formatter(fig)，可直接交给 plot_plotly_object(figure_formatter=...)。

    Example:
        fmt = combine_formatters(axes_fmt, lines_fmt, legend_fmt)
        plot.plot_plotly_object(figure_formatter=fmt)
    """
    active = [f for f in formatters if f is not None]

    def figure_formatter(fig: go.Figure) -> None:
        for formatter in active:
            formatter(fig)

    return figure_formatter
