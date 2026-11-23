"""
matplotlib 后端：只读绘图计划，负责全部与 matplotlib 有关的事。

代码分两段：

- **翻译**：外观、色带位置、标准写法 → matplotlib 原生值（``__init__`` 的 rc 参数、``_curve_color``、
  ``_native_style``）；
- **渲染**：建图、画线、按版式预设排版、调用用户回调、负对数刻度。

三种版式（多线、xy、双 Y 轴）走同一段画法 ``_draw``，差别全在计划（线挂哪根轴）和版式预设里。
"""
from collections.abc import Callable
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.ticker import Formatter, NullFormatter

from ..layouts import LAYOUTS, NO_LEGEND_MESSAGE, LayoutPreset, resolve_frame, resolve_legend
from ..plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, DEFAULT_TICKS, Appearance, AxesFormatter,
                         CurveSpec, DrawnFigure, FigureSpec)
from ..style import (STYLE_FIELDS_BY_KIND, only_fields, translate_axis_style, translate_color, translate_frame,
                     translate_legend_style, translate_line_style, translate_ticks)
from .matplotlib_styles import apply_axis, apply_frame, apply_minor, apply_tick_params, legend_kwargs


class MatplotlibBackend:
    """
    matplotlib 后端：一张计划画一张静态图。

    一般不直接使用，由 ``DataPlotter(backend='matplotlib')`` 通过 `plotlib.backends.get_backend` 创建。

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
        把外观翻译成 rc 参数和刻度设置，并解析色带名。

        样式对象按「库默认 < 用户在 DataPlotter 写的那一层」叠加；与版式有关的设置（上 / 右边框、
        图例位置）还要叠上版式预设，在画每张图时处理（见 ``_draw`` 开头）。
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
        formatters = formatters or {}       # 不在参数里写 ={}：可变默认值会被所有调用共用
        if spec.layout not in LAYOUTS:
            raise ValueError(f"不支持的绘图版式: '{spec.layout}'，可选：{', '.join(LAYOUTS)}")

        with plt.rc_context(self.rc_params):
            return self._draw(spec, figsize, formatters, figure_formatter)

    def _draw(self, spec: FigureSpec, figsize: tuple,
              formatters: dict[str, AxesFormatter], figure_formatter) -> DrawnFigure:
        """
        三种版式共用的画法，顺序是：

        1. 建图，有挂右轴的线就 ``twinx``；全局刻度、边框用到每根轴上；
        2. 画线，颜色和分组样式在画的时候一次给出；
        3. 按版式预设排版（图例、轴标题、各轴格式、边距）；
        4. 各轴的用户回调，然后整图回调；
        5. 补全局的次刻度设置（只补还是默认值的，不覆盖用户回调）；
        6. 负对数刻度补负号（左轴看 x、y，右轴看 y2）。
        """
        preset = LAYOUTS[spec.layout]
        # 跟版式有关的样式：库默认 < 版式预设 < DataPlotter 全局（叠加顺序只写在 layouts.resolve_*）
        legend = translate_legend_style(resolve_legend(preset, self.appearance), 'matplotlib')
        frame = translate_frame(resolve_frame(preset, self.appearance), 'matplotlib')

        fig, ax = plt.subplots(figsize=figsize)
        axes = {'left': ax}
        if any(curve.axis == 'right' for curve in spec.curves):
            axes['right'] = ax.twinx()          # 右轴：与左轴共用 X 轴
        for axis_ax in axes.values():
            apply_tick_params(axis_ax, self.ticks)      # 全局刻度的线和文字：存在 Axis 上，改刻度类型后仍保留
            apply_frame(axis_ax, frame)

        artists = []    # 与 spec.curves 一一对应
        for curve in spec.curves:
            # 颜色、分组样式（线型、标记）都在画的时候一次给出：散点的标记画完就改不了
            artist = self._plot_data(axes[curve.axis], curve.x, curve.y, curve.kind, label=curve.label,
                                     **self._curve_color(curve, preset), **self._native_style(curve))
            artists.append(artist)

        self._apply_layout(fig, axes, spec, preset, legend)
        self._apply_optional_formatters(fig, axes, spec, spec.curves, artists, formatters, legend)
        self._apply_figure_formatter(fig, axes, figure_formatter)
        # 次刻度显不显示、写什么：用户回调可能改了刻度类型（会重置次刻度），所以放在回调之后，只补还是默认值的
        for axis_ax in axes.values():
            apply_minor(axis_ax, self.ticks, only_defaults=True)

        # 右轴与左轴共用 X 轴（twinx），X 的负号只在左轴加一次；'x2' 是上轴（还没有），与 Plotly 一样跳过
        self._apply_neglog_formatter(axes['left'], 'x' in spec.neglog, 'y' in spec.neglog)
        if 'right' in axes:
            self._apply_neglog_formatter(axes['right'], False, 'y2' in spec.neglog)

        return DrawnFigure(spec=spec, fig=fig, axes=axes, artists=artists)

    # ========================================================================
    # 翻译：计划里的标准写法 / 色带位置 → matplotlib 原生值
    # ========================================================================

    def _curve_color(self, curve: CurveSpec, preset: LayoutPreset) -> dict:
        """
        算出一条线的最终颜色，写成画线参数 ``{'color': ...}``。

        优先级：分组写的颜色 > 色带位置 > 版式预设里这根轴的颜色（双 Y 轴左红右蓝）> matplotlib 默认色
        （返回空字典）。颜色在画线时一次给出，所以对折线、散点、柱状图都生效，画完不再覆盖。
        """
        if curve.style.color is not None:
            return {'color': translate_color(curve.style.color, 'matplotlib')}
        if curve.color_position is not None:
            return {'color': self.cmap(curve.color_position)}
        axis_style = preset.axes.get(self._Y_AXIS_NAME[curve.axis])
        if axis_style is not None and axis_style.color is not None:
            return {'color': translate_color(axis_style.color, 'matplotlib')}
        return {}

    @staticmethod
    def _native_style(curve: CurveSpec) -> dict:
        """
        把计划里的分组样式翻译成 matplotlib 的画线参数，如 ``LineStyle(linestyle='dash')`` → ``{'linestyle': '--'}``。

        只取这种画法看得见的字段（``style.STYLE_FIELDS_BY_KIND``）：折线全取，散点只取标记，柱状图都不取。
        散点的标记大小参数叫 ``s`` （磅的平方），这里一并换算。颜色不在这里，由 ``_curve_color`` 给出。
        """
        fields = STYLE_FIELDS_BY_KIND.get(curve.kind, ())     # 画法写错时由 _plot_data 报错
        native = translate_line_style(only_fields(curve.style, fields), 'matplotlib')
        if curve.kind == 'scatter':     # 散点的标记大小参数叫 s（磅的平方）
            if 'markersize' in native:
                native['s'] = native.pop('markersize') ** 2
        return native

    # ========================================================================
    # 渲染：画线
    # ========================================================================

    def _plot_data(self, ax, x, y, plot_kind='line', **kwargs):
        """
        按画法画一组数据，返回画出的对象：折线 ``Line2D``、散点 ``PathCollection``、柱状图 ``BarContainer``。

        Raises
        ------
        ValueError
            不认识的画法。
        """
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

    def _apply_layout(self, fig, axes: dict, spec: FigureSpec, preset: LayoutPreset, legend: dict):
        """
        按版式预设排版：图例、轴标题、各轴的刻度格式和着色、边距。

        *legend* 是这张图图例的原生参数，已按「库默认 < 预设 < 全局」叠加并翻译好；边框在建轴时已设。
        预设里没有列出的轴保留 matplotlib 默认。
        """
        left = axes['left']

        # 图例：一张图一个，建在左轴上，收所有轴上的线（双 Y 轴左右两条都在）；标题来自计划
        self._make_legend(axes, legend, spec.legend_title)

        # 轴标题：单位属于图（计划 6.4 起）
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
    def _make_legend(axes: dict, legend: dict, title: str | None):
        """
        建图例并返回它：一张图一个，建在左轴上，收所有轴上的线（左轴的线在前）。

        ``ax.legend()`` 默认只收自己这根轴的线，所以右轴（``twinx``）的线要手动收进来。
        排版时建一次；用户的线条回调改了样式后，再按同样的参数重建一次（图例句柄是建图例时的样式快照）。
        """
        handles, labels = [], []
        for ax in axes.values():
            ax_handles, ax_labels = ax.get_legend_handles_labels()
            handles += ax_handles
            labels += ax_labels
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

    def _apply_optional_formatters(self, fig, axes: dict, spec: FigureSpec, curves: list[CurveSpec],
                                   artists: list, formatters: dict[str, AxesFormatter], legend: dict):
        """
        按轴调用用户回调，分三步：

        1. 每根轴的坐标轴回调 ``(ax, fig)``、线条回调（只有挂在这根轴上的线）；
        2. 有线条回调改过样式，就按版式预设重建一次图例（图例句柄是建图例时的样式快照）；
        3. 图例回调：一张图一个图例，归左轴；给其他轴配了图例回调就报错。

        图例回调放在最后：图例里有所有轴的线，右轴的线条回调触发的重建不会冲掉图例回调的设置。

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
                fm.lines([artist for curve, artist in zip(curves, artists) if curve.axis == axis])

        # 重建而不是改旧图例：不复制旧图例的锚点（get_bbox_to_anchor() 已是像素坐标，再传给 legend() 会被换算第二次，
        # 图例移到画布外，第三方审查 D）；也不把线的样式 update_from 到句柄上（会连坐标变换一起复制，句柄画错位置）
        if any(fm.lines is not None for fm in fms.values()) and axes['left'].get_legend() is not None:
            self._make_legend(axes, legend, spec.legend_title)

        for axis, fm in fms.items():
            if fm.legend is not None:
                made = axes[axis].get_legend()      # 不叫 legend：那是参数名（图例的原生参数字典），别混用
                if made is None:
                    raise ValueError(NO_LEGEND_MESSAGE)
                fm.legend([made])

    @staticmethod
    def _apply_figure_formatter(fig, axes: dict, figure_formatter):
        """整图回调：各轴回调之后调用一次，拿到图和全部坐标轴（三种版式都支持）。"""
        if figure_formatter is not None:
            figure_formatter(fig, axes)

    @staticmethod
    def _apply_neglog_formatter(ax, neglog_x: bool, neglog_y: bool):
        """
        负对数：给刻度文字补上负号（数据在计划里已取绝对值）。

        每个方向包装自己原来的格式器，保留原有的小数位等格式；次刻度写了文字的也一起包装。
        """
        for on, axis in ((neglog_x, ax.xaxis), (neglog_y, ax.yaxis)):
            if not on:
                continue
            axis.set_major_formatter(_NegativeFormatter(axis.get_major_formatter()))
            if not isinstance(axis.get_minor_formatter(), NullFormatter):
                axis.set_minor_formatter(_NegativeFormatter(axis.get_minor_formatter()))
        return ax


class _NegativeFormatter(Formatter):
    """
    负对数刻度的格式器：在原格式器的文字前加负号。

    Parameters
    ----------
    inner : matplotlib.ticker.Formatter
        原来的格式器，负号后面的文字由它生成。

    Notes
    -----
    不能只包装调用本身（``FuncFormatter(lambda x, pos: '-' + inner(x, pos))``）：matplotlib 画刻度前
    先把这一轮的刻度位置交给格式器（``set_locs``），默认的 ``ScalarFormatter`` 靠它决定小数位，
    收不到就输出空字符串，渲染出来只剩一个负号。所以刻度位置、所属的轴、偏移文字都转交给原格式器。
    """

    def __init__(self, inner: Formatter):
        self.inner = inner

    def __call__(self, x, pos=None):
        """原格式器的文字前加负号。"""
        return f"-{self.inner(x, pos)}"

    def set_locs(self, locs):
        """把这一轮的刻度位置转交给原格式器（它靠这个决定小数位）。"""
        self.inner.set_locs(locs)

    def set_axis(self, axis):
        """自己和原格式器都记下所属的轴。"""
        super().set_axis(axis)
        self.inner.set_axis(axis)

    def get_offset(self):
        """偏移文字（如 ``1e3``）由原格式器给出。"""
        return self.inner.get_offset()
