"""
将绘图计划渲染为 Matplotlib 静态图。

多线图、X-Y 图、双 Y 轴图和柱状图共用渲染流程。绘图计划确定数据及轴归属，版式预设提供轴和图例的默认样式。
柱状图的位置由这里按系列序号算（并排偏移、堆叠底部）。
"""
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_agg import RendererAgg
from matplotlib.ticker import Formatter, NullFormatter, NullLocator
from matplotlib.transforms import Bbox

from ..layouts import LAYOUTS, NO_LEGEND_MESSAGE, LayoutPreset, resolve_frame, resolve_legend
from ..plot_spec import (DEFAULT_BARS, DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, DEFAULT_SCATTER, DEFAULT_TICKS,
                         Appearance, AxesFormatter, BarSpec,
                         CurveBase, DrawnFigure, FigureSpec, LineSpec, ScatterSpec)
from ..style import (is_line_marker, mark_mapped, remember_fill, translate_axis_style, translate_bar_style,
                     translate_color, translate_colorbar, translate_frame, translate_legend_style, translate_line_style,
                     translate_scatter_style, translate_ticks)
from .bar_layout import stack_bottoms
from .matplotlib_styles import apply_axis, apply_frame, apply_minor, apply_tick_params, legend_kwargs


class MatplotlibBackend:
    """
    为每个绘图计划生成一个 Matplotlib Figure。

    ``DataPlotter(backend='matplotlib')`` 通过 `plotlib.backends.get_backend` 创建该后端。

    Parameters
    ----------
    appearance : Appearance
        全局外观。
    cmap : str, optional
        色带名；None 用 ``'plasma'``。

    Attributes
    ----------
    name : str
        ``'matplotlib'``。
    rc_params : dict
        画每张图时用 ``plt.rc_context`` 生效的 rc 参数（字体、字号、线宽、图例字号等）。
    ticks : dict
        翻译好的全局刻度设置。
    cmap : matplotlib.colors.Colormap
        按样品配色用的色带。
    """

    name = 'matplotlib'

    def __init__(self, appearance: Appearance, cmap: str | None = None):
        """
        根据全局外观生成 rc 参数和刻度设置，并解析色带名称。

        渲染时，边框和图例样式还会合并版式预设。
        """
        self.appearance = appearance
        lines = DEFAULT_LINES.updated(appearance.lines)
        legend = DEFAULT_LEGEND.updated(appearance.legend)
        self.rc_params = {
            'font.family': appearance.font_family,
            'font.size': appearance.font_size,
            'font.weight': appearance.font_weight,
            'axes.labelweight': appearance.font_weight,
            'axes.labelsize': appearance.font_size,
            # 线（LineStyle）：全局的线宽、线型、标记大小；颜色按样品配色，不在全局设
            **{f'lines.{key}': value for key, value in translate_line_style(lines, 'matplotlib').items()},
            'axes.linewidth': DEFAULT_FRAME.updated(appearance.frame).width,
            'legend.fontsize': legend.font_size,
            'legend.title_fontsize': legend.font_size,      # 不设时图例标题用正文字号（22），比图例大一截
            'legend.frameon': legend.frame,
            'figure.dpi': appearance.dpi,
        }
        # 刻度（TickStyle）：翻译成 tick_params 等，画每张图时用到坐标轴上（见 matplotlib_styles.py）
        self.ticks = translate_ticks(DEFAULT_TICKS.updated(appearance.ticks), 'matplotlib', appearance.dpi)
        self.cmap = plt.get_cmap('plasma' if cmap is None else cmap)

    # ========================================================================
    # 公开接口：按一张计划画一张图
    # ========================================================================

    def draw(self, spec: FigureSpec, figsize: tuple,
             formatters: dict[str, AxesFormatter] | None = None,
             figure_formatter: Callable[[Any, dict[str, Any]], Any] | None = None) -> DrawnFigure:
        """
        按一张计划画一张图。

        Parameters
        ----------
        spec : FigureSpec
            这张图的计划。
        figsize : tuple of (float, float)
            图尺寸（英寸）。
        formatters : dict, optional
            按轴分组的用户回调 ``{'left': AxesFormatter(...), 'right': ...}``；没给的轴不调用。
        figure_formatter : callable, optional
            ``figure_formatter(fig, axes)``，整张图画完、各轴回调之后调用一次，
            ``axes = {'left': ax}``，双 Y 轴再有 ``'right'``。

        Returns
        -------
        DrawnFigure
            这张图的结果。

        Raises
        ------
        ValueError
            计划里的版式或画法不认识；或给右轴配了图例回调。

        Notes
        -----
        整段画法在 ``plt.rc_context`` 里执行，字号、线宽、默认线型等外观靠它生效，不改全局的 rc 设置。
        """
        formatters = formatters or {}       # 为本次调用初始化回调映射。
        if spec.layout not in LAYOUTS:
            raise ValueError(f"不支持的绘图版式: '{spec.layout}'，可选：{', '.join(LAYOUTS)}")

        with plt.rc_context(self.rc_params):
            return self._draw(spec, figsize, formatters, figure_formatter)

    @staticmethod
    def close(drawn: DrawnFigure) -> None:
        """
        关闭已渲染的图，并将其从 pyplot 的图窗列表移除。
        """
        plt.close(drawn.fig)

    def _draw(self, spec: FigureSpec, figsize: tuple,
              formatters: dict[str, AxesFormatter], figure_formatter) -> DrawnFigure:
        """
        创建图形和坐标轴，绘制曲线并应用版式及回调。

        全局次刻度设置在回调之后应用于仍使用默认定位器或格式器的轴。
        最后处理负对数刻度标签。
        """
        preset = LAYOUTS[spec.layout]
        legend = translate_legend_style(resolve_legend(preset, self.appearance), 'matplotlib')
        frame = translate_frame(resolve_frame(preset, self.appearance), 'matplotlib')

        fig, ax = plt.subplots(figsize=figsize)
        try:
            return self._draw_on(fig, ax, spec, preset, legend, frame, formatters, figure_formatter)
        except BaseException:
            plt.close(fig)      # 释放本次渲染失败的图窗。
            raise

    def _draw_on(self, fig, ax, spec: FigureSpec, preset: LayoutPreset, legend: dict, frame: dict,
                 formatters: dict[str, AxesFormatter], figure_formatter) -> DrawnFigure:
        """在已有 Figure 上绘制曲线，应用版式和格式化回调。"""
        axes = {'left': ax}
        if any(curve.axis == 'right' for curve in spec.curves):
            axes['right'] = ax.twinx()          # 右轴：与左轴共用 X 轴
        for axis_ax in axes.values():
            apply_tick_params(axis_ax, self.ticks)      # 全局刻度的线和文字：存在 Axis 上，改刻度类型后仍保留
            apply_frame(axis_ax, frame)

        artists = []    # 与 spec.curves 一一对应
        bottoms = stack_bottoms([curve for curve in spec.curves if isinstance(curve, BarSpec)])
        # 同图的映射散点共用颜色归一化对象和色带。
        colormap = None if spec.colorbar is None else translate_colorbar(spec.colorbar, 'matplotlib')
        for curve in spec.curves:
            artist = self._draw_curve(axes[curve.axis], curve, preset, bottoms.get(id(curve)), colormap)
            # 恢复计划中的空标签。Matplotlib 会为未命名的对象生成内部标签，
            # 图例重建时则读取对象的当前标签。
            if artist.get_label() != curve.label:
                artist.set_label(curve.label)
            artists.append(artist)
        bars = [curve for curve in spec.curves if isinstance(curve, BarSpec)]
        if bars:
            self._apply_categories(axes['left'], bars[0].categories)
        # 图例条目按计划显式给出：一条曲线（一个系列）一项，先左轴、后右轴，各侧按绘制顺序；规则见 _make_legend
        order = sorted(range(len(spec.curves)), key=lambda i: spec.curves[i].axis != 'left')
        entries = [(artists[i], spec.curves[i].label) for i in order]

        self._apply_layout(fig, axes, spec, preset, legend, entries)
        self._apply_optional_formatters(fig, axes, spec, spec.curves, artists, formatters, legend, entries)
        # 根据轴回调后的布局放置颜色条，再将颜色条传给整图回调。
        shown = dict(axes)
        if spec.colorbar is not None:
            shown['colorbar'] = self._add_colorbar(fig, axes, spec, artists)
        self._apply_figure_formatter(fig, shown, figure_formatter)
        # 改变轴类型会重置次刻度。回调完成后仅补充仍采用默认值的设置。
        for axis_ax in axes.values():
            apply_minor(axis_ax, self.ticks, only_defaults=True)

        # 共用的 X 轴只在左侧包装一次格式器。
        self._apply_neglog_formatter(axes['left'], 'x' in spec.neglog, 'y' in spec.neglog)
        if 'right' in axes:
            self._apply_neglog_formatter(axes['right'], False, 'y2' in spec.neglog)

        return DrawnFigure(spec=spec, fig=fig, axes=shown, artists=artists)

    # 颜色条的尺寸（磅）：离右侧内容（右轴、图外图例）的间距、色条宽度
    _COLORBAR_GAP_PT = 8
    _COLORBAR_WIDTH_PT = 14
    # 占图宽的比例：颜色条的文字离图右边留的距离；腾位置时绘图区宽度的下限
    _FIGURE_EDGE = 0.02
    _MIN_AXES_WIDTH = 0.25

    def _add_colorbar(self, fig, axes: dict, spec: FigureSpec, artists: list):
        """
        给颜色映射的散点加颜色条，返回 ``Colorbar`` 对象。

        颜色条是左轴的子轴。定位器在绘制时读取可见右轴和图例的实际边界，间距和条宽以磅计。
        初始右边距由 `_make_room` 预留。``tight_layout`` 与紧边界导出均会计入颜色条。
        自行定位时可用 ``colorbar.ax.set_axes_locator(None)`` 停用定位器。
        """
        assert spec.colorbar is not None and spec.colorbar.title is not None
        mappable = next(artist for curve, artist in zip(spec.curves, artists)
                        if isinstance(curve, ScatterSpec) and curve.colors is not None)
        cax = axes['left'].inset_axes([1, 0, 0.05, 1])
        cax.set_axes_locator(lambda _cax, renderer: self._locate_colorbar(fig, axes, renderer))
        colorbar = fig.colorbar(mappable, cax=cax)
        colorbar.set_label(spec.colorbar.title)
        self._make_room(fig, axes, colorbar)
        return colorbar

    def _locate_colorbar(self, fig, axes: dict, renderer):
        """
        将颜色条放在可见右轴和图例之外，高度与左轴相同。
        """
        box = axes['left'].get_window_extent(renderer)
        edges = [box.x1]
        if 'right' in axes and axes['right'].get_visible():
            if (right := axes['right'].get_tightbbox(renderer)) is not None:
                edges.append(right.x1)
        if (legend := axes['left'].get_legend()) is not None and legend.get_visible():
            edges.append(legend.get_window_extent(renderer).x1)
        x0 = max(edges) + self._COLORBAR_GAP_PT * fig.dpi / 72
        width = self._COLORBAR_WIDTH_PT * fig.dpi / 72
        return fig.transSubfigure.inverted().transform_bbox(Bbox.from_extents(x0, box.y0, x0 + width, box.y1))

    def _make_room(self, fig, axes: dict, colorbar) -> None:
        """
        在整图回调前，根据颜色条及其文字的边界预留右边距。

        ``subplots_adjust`` 同时调整共享位置的左右轴。此次调整为绘图区保留最小宽度，右侧内容过宽时颜色条可能出界。
        整图回调扩大右侧内容后，可用 ``fig.tight_layout()`` 重新分配空间。该布局由 Matplotlib 决定绘图区宽度。
        """
        renderer = _measuring_renderer(fig)
        right = colorbar.ax.get_tightbbox(renderer).x1
        shift = (fig.bbox.x1 * (1 - self._FIGURE_EDGE) - right) / fig.bbox.width
        box = axes['left'].get_position()
        fig.subplots_adjust(right=box.x0 + max(box.width + shift, self._MIN_AXES_WIDTH))

    # ========================================================================
    # 曲线颜色和样式
    # ========================================================================

    def _curve_color(self, curve: LineSpec | ScatterSpec | BarSpec, preset: LayoutPreset) -> dict:
        """
        算出一条线的最终颜色，写成画线参数 ``{'color': ...}``。

        优先级：分组写的颜色 > 色带位置 > 版式预设里这根轴的颜色（双 Y 轴左红右蓝）> matplotlib 默认色
        （返回空字典）。颜色在画的时候一次给出，所以对折线、散点都生效，画完不再覆盖。
        """
        if curve.style.color is not None:
            return {'color': translate_color(curve.style.color, 'matplotlib')}
        if curve.color_position is not None:
            return {'color': self.cmap(curve.color_position)}
        axis_style = preset.axes.get(self._Y_AXIS_NAME[curve.axis])
        if axis_style is not None and axis_style.color is not None:
            return {'color': translate_color(axis_style.color, 'matplotlib')}
        return {}

    # ========================================================================
    # 渲染：画线
    # ========================================================================

    def _draw_curve(self, ax, curve: CurveBase, preset: LayoutPreset, bottom: np.ndarray | None = None,
                    colormap: dict | None = None):
        """
        按曲线的类型画出来，返回画出的对象：`LineSpec` → ``Line2D``，`ScatterSpec` → ``PathCollection``，
        `BarSpec` → ``BarContainer``。

        颜色由 ``_curve_color`` 一次给出（样式里写的颜色已算在里面），其余样式按画法翻译
        （如 ``LineStyle(linestyle='dash')`` → ``{'linestyle': '--'}``，散点大小换成面积 ``s``）。
        *bottom* 是堆叠柱状图这个系列的底部（见 `stack_bottoms`）。
        映射散点：大小映射的 ``s`` 是每个点直径的平方；颜色映射按 *colormap* （这张图共用的 ``cmap``、``norm``）着色，
        描边跟随逐点的填充色（``edgecolors='face'``）。

        Raises
        ------
        ValueError
            不认识的曲线类型。
        """
        match curve:
            case LineSpec():
                native = translate_line_style(replace(curve.style, color=None), 'matplotlib')
                return ax.plot(curve.x, curve.y, label=curve.label, **self._curve_color(curve, preset), **native)[0]
            case ScatterSpec():
                # 先套库默认（大小、描边都写明），全局折线样式（rc 的 lines.*）就漏不到散点上
                style = DEFAULT_SCATTER.updated(replace(curve.style, color=None))
                mapped = curve.colors is not None and colormap is not None
                color = None if mapped else self._curve_color(curve, preset).get('color')
                native = translate_scatter_style(style, 'matplotlib', fallback_color=color)
                if curve.sizes is not None:
                    native['s'] = np.square(curve.sizes)
                if curve.colors is not None and colormap is not None:
                    native.update(c=curve.colors, edgecolors='face', **colormap)
                # 线形标记（x、cross）传 edgecolors 会警告：先不传，画完再用 setter 补上，
                # 对象的状态（填充、描边分开）就和其他标记一样，之后的散点回调不用区分
                edge = native.pop('edgecolors', None) if is_line_marker(style.marker) else None
                points = ax.scatter(curve.x, curve.y, label=curve.label, **native)
                if edge is not None:
                    points.set_edgecolor(edge)
                remember_fill(points, color)
                mark_mapped(points, sizes=curve.sizes is not None, colors=mapped)
                return points
            case BarSpec():
                return self._draw_bars(ax, curve, preset, bottom)
            case _:
                raise ValueError(f"不支持的画法：{type(curve).__name__}（可用 LineSpec、ScatterSpec、BarSpec）")

    def _draw_bars(self, ax, bar: BarSpec, preset: LayoutPreset, bottom: np.ndarray | None):
        """
        画柱状图的一个系列，返回 ``BarContainer`` （误差棒在它的 ``errorbar`` 上）。

        类别 *k* 对应 X = *k*。并排时每根柱宽为 ``width / 系列数``，第 *i* 个系列偏移 ``(i - (n - 1) / 2) × 每根柱宽``。
        堆叠时使用完整柱宽，基线由 `stack_bottoms` 计算。误差棒以柱的末端为中心，``caps=False`` 时省略端帽。
        """
        style = DEFAULT_BARS.updated(replace(bar.style, color=None))
        if not bar.caps:
            style = replace(style, capsize=0)
        native = translate_bar_style(style, 'matplotlib')
        errors = {key: native.pop(key) for key in ('ecolor', 'elinewidth', 'capsize')}
        count = len(bar.heights)
        if bar.mode == 'group':
            width = bar.width / bar.series_count
            x = np.arange(count) + (bar.series_index - (bar.series_count - 1) / 2) * width
        else:
            width, x = bar.width, np.arange(count, dtype=float)
        if bar.errors is not None:
            # 端帽线宽（capthick）与竖线一致，与 make_bar_formatter 改 error_width 时的效果相同
            native.update(yerr=bar.errors, capsize=errors['capsize'],
                          error_kw=dict(ecolor=errors['ecolor'], elinewidth=errors['elinewidth'],
                                        capthick=errors['elinewidth']))
        return ax.bar(x, bar.heights, width, bottom=bottom, label=bar.label,
                      **native, **self._curve_color(bar, preset))

    @staticmethod
    def _apply_categories(ax, categories: list[str]):
        """柱状图的类别刻度：数字位置 0、1、2 …… 配类别文字（同名类别也分开）；X 轴是类别轴，不画次刻度。"""
        ax.set_xticks(range(len(categories)), categories)
        ax.xaxis.set_minor_locator(NullLocator())

    # ========================================================================
    # 版式应用
    # ========================================================================

    _Y_AXIS_NAME = {'left': 'y', 'right': 'y2'}     # 线挂的轴（CurveBase.axis）→ 预设里的纵轴名

    def _apply_layout(self, fig, axes: dict, spec: FigureSpec, preset: LayoutPreset, legend: dict,
                      entries: list[tuple[Any, str]]):
        """
        按版式预设设置图例、轴标题、轴样式和边距。

        *legend* 为合并后转换得到的 Matplotlib 图例参数；*entries* 见 `_make_legend`。
        """
        left = axes['left']

        # 图例：一张图一个，建在左轴上，收所有轴上的线（双 Y 轴左右两条都在）；标题来自计划
        self._make_legend(axes, legend, spec.legend_title, entries)

        left.set_xlabel(spec.x_unit)
        left.set_ylabel(spec.y_unit)
        if 'right' in axes:
            axes['right'].set_ylabel(spec.y2_unit)

        # 各轴（AxisStyle）：刻度格式、着色（标题、刻度、轴线同色）；预设没列的轴保留 matplotlib 默认
        for axis_name, axis_style in preset.axes.items():
            axis_ax, letter = self._axis(axes, axis_name)
            apply_axis(axis_ax, letter, translate_axis_style(axis_style, 'matplotlib', letter))

        if preset.margins:
            fig.subplots_adjust(**preset.margins)

    @staticmethod
    def _make_legend(axes: dict, legend: dict, title: str | None, entries: list[tuple[Any, str]]):
        """
        在左轴创建整图图例。*entries* 按左轴、右轴的顺序提供 ``(绘图对象, 计划标签)``。

        计划条目使用对象的当前标签，保留原有的空标签和以下划线开头的标签。标签为 ``None`` 时略去该项，
        回调将标签改为以下划线开头的名称时也略去该项。随后按 Matplotlib 的规则收集参考线等额外对象。

        图例句柄保存创建时的样式。线条、散点和柱状图回调执行后，用相同的版式参数重建图例。
        """
        handles, labels = [], []
        for artist, planned in entries:
            label = artist.get_label()
            if label is None or (label.startswith('_') and label != planned):
                continue
            handles.append(artist)
            labels.append(label)
        planned_ids = {id(artist) for artist, _ in entries}
        for ax in axes.values():
            for handle, label in zip(*ax.get_legend_handles_labels()):
                if id(handle) not in planned_ids:
                    handles.append(handle)
                    labels.append(label)
        made = axes['left'].legend(handles, labels, title=title, **legend_kwargs(legend))
        if legend.get('draggable'):
            made.set_draggable(True)
        return made

    @staticmethod
    def _axis(axes: dict, axis_name: str):
        """把预设里的轴名换成 ``(坐标轴, 方向)``：``'x'``、``'y'`` 在左轴上，``'y2'`` 是右轴的纵轴。"""
        match axis_name:
            case 'x':
                return axes['left'], 'x'
            case 'y':
                return axes['left'], 'y'
            case 'y2':
                return axes['right'], 'y'
            case _:
                raise ValueError(f"排版预设里不支持的轴名: '{axis_name}'，可选：'x'、'y'、'y2'")

    # ========================================================================
    # 渲染：用户 formatter & 负对数刻度
    # ========================================================================

    def _apply_optional_formatters(self, fig, axes: dict, spec: FigureSpec, curves: Sequence[CurveBase],
                                   artists: list, formatters: dict[str, AxesFormatter], legend: dict,
                                   entries: list[tuple[Any, str]]):
        """
        执行坐标轴、线条、散点和图例回调。

        线条回调只收这根轴上的折线，散点回调只收这根轴上的散点，两者互不干扰。
        图例句柄保存的是创建时的曲线样式。应用曲线回调后重建图例，再执行整图图例回调。

        Raises
        ------
        ValueError
            给左轴以外的轴配了图例回调。
        """
        fms = {axis: formatters.get(axis, AxesFormatter()) for axis in axes}
        for axis, ax in axes.items():
            fm = fms[axis]
            if fm.axes is not None:
                fm.axes(ax, fig)
            if fm.lines is not None:
                fm.lines(_artists_of(LineSpec, axis, curves, artists))
            if fm.scatter is not None:
                fm.scatter(_artists_of(ScatterSpec, axis, curves, artists))
            if fm.bars is not None:
                fm.bars(_artists_of(BarSpec, axis, curves, artists))

        # 使用原始图例参数重建，避免重复转换锚点，或从曲线复制坐标变换。
        restyled = any(fm.lines is not None or fm.scatter is not None or fm.bars is not None for fm in fms.values())
        if restyled and axes['left'].get_legend() is not None:
            self._make_legend(axes, legend, spec.legend_title, entries)

        for axis, fm in fms.items():
            if fm.legend is not None:
                made = axes[axis].get_legend()
                if made is None:
                    raise ValueError(NO_LEGEND_MESSAGE)
                fm.legend([made])

    @staticmethod
    def _apply_figure_formatter(fig, axes: dict, figure_formatter):
        """在各轴回调完成后，将图形及其坐标轴传给整图回调。"""
        if figure_formatter is not None:
            figure_formatter(fig, axes)

    @staticmethod
    def _apply_neglog_formatter(ax, neglog_x: bool, neglog_y: bool):
        """
        为负对数轴的主、次刻度标签添加负号。

        用包装器保留各轴原有的数值格式。绘图计划已将相应数据转换为绝对值。
        """
        for on, axis in ((neglog_x, ax.xaxis), (neglog_y, ax.yaxis)):
            if not on:
                continue
            axis.set_major_formatter(_NegativeFormatter(axis.get_major_formatter()))
            if not isinstance(axis.get_minor_formatter(), NullFormatter):
                axis.set_minor_formatter(_NegativeFormatter(axis.get_minor_formatter()))
        return ax


def _measuring_renderer(fig):
    """
    量文字和边界框用的渲染器：画布自己的（Agg 及交互后端）；SVG、PDF 等画布没有 ``get_renderer``，
    另建一个同尺寸、同 dpi 的 Agg 渲染器来量（只量不画）。
    """
    get_renderer = getattr(fig.canvas, 'get_renderer', None)
    if get_renderer is not None:
        return get_renderer()
    return RendererAgg(fig.bbox.width, fig.bbox.height, fig.dpi)


def _artists_of(spec_type: type, axis: str, curves: Sequence[CurveBase], artists: list) -> list:
    """这根轴上某种画法（*spec_type*，如 `LineSpec`）的曲线对象，按绘制顺序。"""
    return [artist for curve, artist in zip(curves, artists) if curve.axis == axis and isinstance(curve, spec_type)]


class _NegativeFormatter(Formatter):
    """
    为取绝对值后绘制的数据生成带负号的主刻度标签。

    Parameters
    ----------
    inner : matplotlib.ticker.Formatter
        生成原始刻度标签的格式器。

    Notes
    -----
    对数轴使用原格式器处理正值，再为标签添加负号。其他轴将取负后的刻度值传给原格式器。
    包装器向原格式器传递所属轴和刻度位置，使其可以计算标签精度和偏移文字。
    """

    def __init__(self, inner: Formatter):
        self.inner = inner

    def _negate_values(self) -> bool:
        """判断是否直接对传给原格式器的刻度值取负。"""
        get_scale = getattr(self.axis, 'get_scale', None)
        return get_scale is not None and get_scale() != 'log'

    def __call__(self, x, pos=None):
        """刻度值取负后的标签。"""
        if self._negate_values():
            return self.inner(-x, pos)
        return f"-{self.inner(x, pos)}"

    def set_locs(self, locs):
        """按当前轴类型转换刻度位置，并传给原格式器。"""
        self.inner.set_locs([-loc for loc in locs] if self._negate_values() else locs)

    def set_axis(self, axis):
        """为当前格式器和被包装的格式器设置所属轴。"""
        super().set_axis(axis)
        self.inner.set_axis(axis)

    def get_offset(self):
        """偏移文字（如 ``1e3``）由原格式器给出。"""
        return self.inner.get_offset()
