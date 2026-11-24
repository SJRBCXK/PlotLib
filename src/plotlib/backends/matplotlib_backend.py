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
from matplotlib.ticker import Formatter, NullFormatter, NullLocator

from ..layouts import LAYOUTS, NO_LEGEND_MESSAGE, LayoutPreset, resolve_frame, resolve_legend
from ..plot_spec import (DEFAULT_BARS, DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, DEFAULT_SCATTER, DEFAULT_TICKS,
                         Appearance, AxesFormatter, BarSpec,
                         CurveBase, DrawnFigure, FigureSpec, LineSpec, ScatterSpec)
from ..style import (is_line_marker, remember_fill, translate_axis_style, translate_bar_style, translate_color,
                     translate_frame, translate_legend_style, translate_line_style, translate_scatter_style,
                     translate_ticks)
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
        for curve in spec.curves:
            artist = self._draw_curve(axes[curve.axis], curve, preset, bottoms.get(id(curve)))
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
        self._apply_figure_formatter(fig, axes, figure_formatter)
        # 改变轴类型会重置次刻度。回调完成后仅补充仍采用默认值的设置。
        for axis_ax in axes.values():
            apply_minor(axis_ax, self.ticks, only_defaults=True)

        # 共用的 X 轴只在左侧包装一次格式器。
        self._apply_neglog_formatter(axes['left'], 'x' in spec.neglog, 'y' in spec.neglog)
        if 'right' in axes:
            self._apply_neglog_formatter(axes['right'], False, 'y2' in spec.neglog)

        return DrawnFigure(spec=spec, fig=fig, axes=axes, artists=artists)

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

    def _draw_curve(self, ax, curve: CurveBase, preset: LayoutPreset, bottom: np.ndarray | None = None):
        """
        按曲线的类型画出来，返回画出的对象：`LineSpec` → ``Line2D``，`ScatterSpec` → ``PathCollection``，
        `BarSpec` → ``BarContainer``。

        颜色由 ``_curve_color`` 一次给出（样式里写的颜色已算在里面），其余样式按画法翻译
        （如 ``LineStyle(linestyle='dash')`` → ``{'linestyle': '--'}``，散点大小换成面积 ``s``）。
        *bottom* 是堆叠柱状图这个系列的底部（见 `stack_bottoms`）。

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
                color = self._curve_color(curve, preset).get('color')
                native = translate_scatter_style(style, 'matplotlib', fallback_color=color)
                # 线形标记（x、cross）传 edgecolors 会警告：先不传，画完再用 setter 补上，
                # 对象的状态（填充、描边分开）就和其他标记一样，之后的散点回调不用区分
                edge = native.pop('edgecolors', None) if is_line_marker(style.marker) else None
                points = ax.scatter(curve.x, curve.y, label=curve.label, **native)
                if edge is not None:
                    points.set_edgecolor(edge)
                remember_fill(points, color)
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
