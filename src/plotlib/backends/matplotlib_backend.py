"""
matplotlib 后端（STRUCTURE_REVIEW 6.6）：只读绘图计划，负责全部 matplotlib 的事。

分两段：
  - 翻译：标准写法 / 色带位置 / 外观 → matplotlib 原生值（__init__ 的 rc_params、_curve_color、_native_style）；
  - 渲染：建图、画线、按排版预设排版（layouts.py）、用户 formatter、负对数刻度。
不认识 DataSet、Group、DataPlotter；输入是 FigureSpec，输出是 DrawnFigure。
三种版式（多线、xy、双 Y 轴）走同一段画法（_draw），差别全在计划（线挂哪根轴）和排版预设里。
"""
from collections.abc import Callable
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from ..layouts import LAYOUTS, LayoutPreset
from ..plot_spec import Appearance, AxesFormatter, CurveSpec, DrawnFigure, FigureSpec
from ..style import (translate_color, translate_legend, translate_linestyle, translate_marker,
                     translate_tick_format)


class MatplotlibBackend:

    name = 'matplotlib'

    def __init__(self, appearance: Appearance, cmap: str | None = None):
        """翻译外观：Appearance（后端无关）→ rc_params（绘图时由 rc_context 生效）；解析色带名。"""
        self.rc_params = {
            'font.family': appearance.font_family,
            'font.size': appearance.font_size,
            'font.weight': appearance.font_weight,
            'lines.linewidth': appearance.line_width,
            'axes.linewidth': appearance.axis_width,
            'axes.labelweight': appearance.font_weight,
            'axes.labelsize': appearance.font_size,
            'lines.linestyle': translate_linestyle(appearance.linestyle, 'matplotlib'),
            'legend.fontsize': appearance.legend_font_size,
            'xtick.major.width': appearance.tick_width,
            'ytick.major.width': appearance.tick_width,
            'xtick.minor.width': appearance.tick_width,
            'ytick.minor.width': appearance.tick_width,
            'legend.frameon': False,
            'figure.dpi': appearance.dpi,
        }
        self.cmap = plt.get_cmap('plasma' if cmap is None else cmap)

    # ========================================================================
    # 公开接口：按一张计划画一张图
    # ========================================================================

    def draw(self, spec: FigureSpec, figsize: tuple,
             formatters: dict[str, AxesFormatter] | None = None,
             figure_formatter: Callable[[Any, dict[str, Any]], Any] | None = None) -> DrawnFigure:
        """
        按一张 FigureSpec 画一张图，返回 DrawnFigure。后端唯一的公开方法。

        formatters：按轴分组的用户回调 {'left': AxesFormatter(...), 'right': ...}，没给的轴不调用。
        figure_formatter(fig, axes)：整张图画完、各轴回调之后调用一次，拿到图和全部坐标轴
            （axes = {'left': ax}，双 Y 轴再有 'right'）；三种版式都支持。
        整段在 rc_context 里执行：字号、线宽、默认线型等外观靠它生效。
        """
        formatters = formatters or {}       # 不在参数里写 ={}：可变默认值会被所有调用共用
        if spec.layout not in LAYOUTS:
            raise ValueError(f"不支持的绘图版式: '{spec.layout}'，可选：{', '.join(LAYOUTS)}")

        with plt.rc_context(self.rc_params):
            return self._draw(spec, figsize, formatters, figure_formatter)

    def _draw(self, spec: FigureSpec, figsize: tuple,
              formatters: dict[str, AxesFormatter], figure_formatter) -> DrawnFigure:
        """
        三种版式共用的画法。顺序：建图（有挂右轴的线就 twinx）→ 画线 → 按排版预设排版
        → 各轴用户回调 → 整图回调 → 负对数刻度（左轴看 x、y，右轴看 x2、y2）。
        """
        preset = LAYOUTS[spec.layout]
        fig, ax = plt.subplots(figsize=figsize)
        axes = {'left': ax}
        if any(curve.axis == 'right' for curve in spec.curves):
            axes['right'] = ax.twinx()          # 右轴：与左轴共用 X 轴

        artists = []    # 与 spec.curves 一一对应
        for curve in spec.curves:
            artist = self._plot_data(axes[curve.axis], curve.x, curve.y, curve.kind,
                                     label=curve.label, **self._curve_color(curve, preset))
            # 分组线型、标记：写了就应用（scatter / bar 暂不支持，见 STRUCTURE_REVIEW 4.3 的遗留问题）；颜色上面已给
            if curve.kind == 'line' and (line_style := self._native_style(curve.style)):
                artist.set(**line_style)  # type: ignore[union-attr]
            artists.append(artist)

        self._apply_layout(fig, axes, spec, preset)
        for axis, axis_ax in axes.items():      # 每根轴用自己那一组回调，只拿到挂在这根轴上的线
            lines = [artist for curve, artist in zip(spec.curves, artists) if curve.axis == axis]
            self._apply_optional_formatters(axis_ax, fig, lines, [axis_ax.get_legend()],
                                            formatters.get(axis, AxesFormatter()))
        self._apply_figure_formatter(fig, axes, figure_formatter)

        self._apply_neglog_formatter(axes['left'], 'x' in spec.neglog, 'y' in spec.neglog)
        if 'right' in axes:
            self._apply_neglog_formatter(axes['right'], 'x2' in spec.neglog, 'y2' in spec.neglog)

        return DrawnFigure(spec=spec, fig=fig, axes=axes, artists=artists)

    # ========================================================================
    # 翻译：计划里的标准写法 / 色带位置 → matplotlib 原生值
    # ========================================================================

    def _curve_color(self, curve: CurveSpec, preset: LayoutPreset) -> dict:
        """
        一条线的最终颜色，写成画线参数（颜色一次赋值，6.5 用户定的方案 B）。优先级：
        分组写的颜色 > 色带位置 > 排版预设里这根轴的颜色（双 Y 轴左红右蓝，6.6b）> matplotlib 默认色（返回 {}）。
        画的时候就给出，所以对所有画法（折线 / 散点 / 柱）都生效，画完不再覆盖颜色。
        """
        if 'color' in curve.style:
            return {'color': translate_color(curve.style['color'], 'matplotlib')}
        if curve.color_position is not None:
            return {'color': self.cmap(curve.color_position)}
        if axis_color := preset.axis_colors.get(self._Y_AXIS_NAME[curve.axis]):
            return {'color': translate_color(axis_color, 'matplotlib')}
        return {}

    @staticmethod
    def _native_style(style: dict) -> dict:
        """
        把计划里样式的线型、标记（CurveSpec.style，标准写法）翻译成 matplotlib 原生值：
        {'linestyle': 'dash'} → {'linestyle': '--'}。没写的字段本来就不在字典里。
        颜色不在这里：画线时已由 _curve_color 一次给出（6.5），画完不再覆盖。
        后端只读计划、不读 Group：样式在生成计划时已从 Group 取出，这里只负责翻译。
        """
        translators = {'linestyle': translate_linestyle, 'marker': translate_marker}
        return {field: translators[field](value, 'matplotlib')
                for field, value in style.items() if field in translators}

    # ========================================================================
    # 渲染：画线
    # ========================================================================

    def _plot_data(self, ax, x, y, plot_kind='line', **kwargs):
        """按 plot_kind 绘制一组数据，返回对应的 artist。"""
        match plot_kind:
            case 'line':
                return ax.plot(x, y, **kwargs)[0]
            case 'scatter':
                return ax.scatter(x, y, **kwargs)
            case 'bar':
                return ax.bar(x, y, **kwargs)
            case _:
                raise ValueError(f"不支持的 plot_kind: '{plot_kind}'")

    # ========================================================================
    # 渲染：按排版预设排版（layouts.py；以前是三个写死的 _default_*_formatter）
    # ========================================================================

    _Y_AXIS_NAME = {'left': 'y', 'right': 'y2'}     # 线挂的轴（CurveSpec.axis）→ 预设里的纵轴名

    def _apply_layout(self, fig, axes: dict, spec: FigureSpec, preset: LayoutPreset):
        """按排版预设设置图例、轴标题、刻度格式、轴着色、边距（值的翻译在翻译层 style.translate_*）。"""
        left = axes['left']

        # 图例：只放在左轴上（双 Y 轴也一样，右轴的线不进图例）
        legend = left.legend(**translate_legend(preset.legend, 'matplotlib'))
        if preset.legend_draggable:
            legend.set_draggable(True)

        # 轴标题：单位属于图（计划 6.4 起）
        left.set_xlabel(spec.x_unit)
        left.set_ylabel(spec.y_unit)
        if 'right' in axes:
            axes['right'].set_ylabel(spec.y2_unit)

        # 刻度格式：预设没列的轴保留 matplotlib 默认
        for axis_name, fmt in preset.tick_formats.items():
            self._axis(axes, axis_name).set_major_formatter(FuncFormatter(translate_tick_format(fmt, 'matplotlib')))

        # 轴着色：标题、刻度（线和文字）、轴线同色
        for axis_name, color in preset.axis_colors.items():
            native = translate_color(color, 'matplotlib')
            side = 'left' if axis_name == 'y' else 'right'
            axis_ax = axes[side]
            axis_ax.yaxis.label.set_color(native)
            axis_ax.tick_params(axis='y', labelcolor=native, color=native)
            axis_ax.spines[side].set_color(native)

        if preset.margins:
            fig.subplots_adjust(**preset.margins)

    @staticmethod
    def _axis(axes: dict, axis_name: str):
        """预设里的轴名 → matplotlib 的 Axis 对象：'x'、'y' 在左轴上，'y2' 是右轴的纵轴。"""
        match axis_name:
            case 'x':
                return axes['left'].xaxis
            case 'y':
                return axes['left'].yaxis
            case 'y2':
                return axes['right'].yaxis
            case _:
                raise ValueError(f"排版预设里不支持的轴名: '{axis_name}'，可选：'x'、'y'、'y2'")

    # ========================================================================
    # 渲染：用户 formatter & 负对数刻度
    # ========================================================================

    def _apply_optional_formatters(self, ax, fig, lines, legends, fm: AxesFormatter):
        """应用一根轴的用户回调（fm 是这根轴的一组：axes / lines / legend，没给的是 None）。"""
        if fm.axes is not None:
            fm.axes(ax, fig)
        if fm.lines is not None:
            fm.lines(lines)
            # 图例句柄是创建时的样式快照，线条样式变更后需重建图例
            legends = [self._refresh_legend(ax)]
        if fm.legend is not None:
            fm.legend(legends)

    @staticmethod
    def _apply_figure_formatter(fig, axes: dict, figure_formatter):
        """整图回调：各轴回调之后调用一次，拿到图和全部坐标轴（三种版式都支持）。"""
        if figure_formatter is not None:
            figure_formatter(fig, axes)

    def _refresh_legend(self, ax):
        """按原图例的位置和拖拽设置重建图例；原本无图例则不新建。"""
        old = ax.get_legend()
        if old is None:
            return None
        # matplotlib 未提供 loc 的公开 getter，只能读取 _loc
        new = ax.legend(loc=old._loc, bbox_to_anchor=old.get_bbox_to_anchor())
        new.set_draggable(old.get_draggable())
        return new

    def _apply_neglog_formatter(self, ax, neglog_x: bool, neglog_y: bool):
        """为坐标轴添加负号前缀（用于负对数刻度显示）。"""
        # 两轴必须用各自的变量：lambda 在绘图时才执行，若共用一个变量，
        # X 轴的 lambda 会读到后来被 Y 分支覆盖的 Y 轴格式器（闭包晚绑定）
        if neglog_x:
            x_formatter = ax.xaxis.get_major_formatter()
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda x, pos: f"-{x_formatter(x, pos)}"))
        if neglog_y:
            y_formatter = ax.yaxis.get_major_formatter()
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda y, pos: f"-{y_formatter(y, pos)}"))
        return ax
