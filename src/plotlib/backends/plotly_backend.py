"""
Plotly 后端：只读绘图计划，负责全部与 Plotly 有关的事。代码与 matplotlib 后端逐段对应：

- **翻译**：外观 → 模板（``__init__``）、颜色（``_curve_color``）、线型和标记（``_native_style``）；
  磅 → 像素、英寸 → 像素、图例位置、刻度格式这些通用换算在翻译层 `plotlib.style`；
- **渲染**：建图、画线、按版式预设排版、调用用户回调、负对数刻度；
- **多页**：`PlotlyBackend.draw_pages` 把一次计划的多张图画进同一个 Figure，每张一页；
- **交互**：画完之后可选的滑块，`PlotlyBackend.add_slider` 一条线一档，`PlotlyBackend.add_page_slider` 一页一档。

Notes
-----
Plotly 没有轴对象，坐标轴是 layout 里的一段配置。所以 ``DrawnFigure.axes`` 存的是配置里的轴名
``{'left': 'yaxis', 'right': 'yaxis2'}`` （两根 Y 轴共用 ``'xaxis'``），用 ``fig.layout[轴名]`` 读写。
"""
from collections.abc import Callable
from dataclasses import replace
from typing import Any, Literal, cast

import plotly.colors as plyc
import plotly.graph_objects as go

from ..layouts import LAYOUTS, NO_LEGEND_MESSAGE, LayoutPreset, resolve_frame, resolve_legend
from ..plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, DEFAULT_TICKS, Appearance, AxesFormatter,
                         CurveSpec, DrawnFigure, FigureSpec, LineStyle)
from ..style import (STYLE_FIELDS_BY_KIND, only_fields, translate_color, translate_figsize, translate_frame,
                     translate_legend_style, translate_line_style, translate_points, translate_ticks)
from .plotly_styles import apply_axis, apply_frame, apply_log_format

# 滑块模式：single 每档只显示一条曲线；cumulative 每档累加显示到当前曲线
type SliderMode = Literal['single', 'cumulative']

# 线挂的轴（CurveSpec.axis）→ Plotly 配置里的纵轴名、trace 上的 yaxis 引用
_Y_AXIS = {'left': 'yaxis', 'right': 'yaxis2'}
_TRACE_Y = {'left': 'y', 'right': 'y2'}
# 排版预设 / 计划里的轴名（'x'、'y'、'y2'）→ Plotly 配置里的轴名
_LAYOUT_AXIS = {'x': 'xaxis', 'y': 'yaxis', 'y2': 'yaxis2'}


class PlotlyBackend:
    """
    Plotly 后端：画交互图，多张计划画成一个 Figure 的多页，并提供滑块。

    一般不直接使用，由 ``DataPlotter(backend='plotly')`` 通过 `plotlib.backends.get_backend` 创建。

    Parameters
    ----------
    appearance : Appearance
        全局外观，翻译成 Plotly 模板。
    cmap : str, optional
        Plotly 色带名；None 用 ``'Plasma'``。

    Attributes
    ----------
    name : str
        ``'plotly'``。
    dpi : float
        把磅、英寸换成像素用的分辨率，也记在每张图的 ``fig.layout.meta['dpi']`` 里。
    template : `plotly.graph_objects.layout.Template`
        所有图共用的外观模板（字体、轴线、刻度、图例、默认线宽）。
    line_width : float
        全局线宽（像素），换算自定义虚线的段长用。
    """

    name = 'plotly'

    def __init__(self, appearance: Appearance, cmap: str | None = None):
        """
        把外观翻译成 Plotly 模板（磅按 ``appearance.dpi`` 换成像素），并解析色带名。

        样式对象按「库默认 < 用户在 DataPlotter 写的那一层」叠加；与版式有关的设置（上 / 右边框、
        图例位置）还要叠上版式预设，在画每张图时处理。
        """
        self.appearance = appearance
        self.dpi = appearance.dpi
        px = lambda points: translate_points(points, self.dpi, 'plotly')      # noqa: E731  磅 → 像素
        # 自定义虚线的段长按线宽换算成像素：模板线宽和换算用同一个值
        self.line_width = px(DEFAULT_LINES.updated(appearance.lines).width)
        self.template = self._create_template(appearance, px)
        self.cmap = plyc.get_colorscale('Plasma' if cmap is None else cmap)

    # ========================================================================
    # 公开接口：按一张计划画一张图（与 MatplotlibBackend.draw 同一签名）；多张计划画成一个 Figure 多页（6.8）
    # ========================================================================

    def draw(self, spec: FigureSpec, figsize: tuple,
             formatters: dict[str, AxesFormatter] | None = None,
             figure_formatter: Callable[[Any, dict[str, Any]], Any] | None = None) -> DrawnFigure:
        """
        按一张计划画一个 Figure，即只有一页的 `draw_pages`。

        Parameters
        ----------
        spec : FigureSpec
            这张图的计划。
        figsize : tuple of (float, float)
            图尺寸（英寸），按 dpi 换成像素。
        formatters : dict, optional
            按轴分组的用户回调，调用形状与 matplotlib 对应：坐标轴 ``(轴名, fig)``、
            线条（这根轴的 trace 列表）、图例 ``[fig.layout.legend]`` （只有左轴有）。
        figure_formatter : callable, optional
            ``figure_formatter(fig, axes)``，``axes`` 是全部轴名 ``{'left': 'yaxis', 'right': 'yaxis2'}``。

        Returns
        -------
        DrawnFigure
            这张图的结果。
        """
        return self.draw_pages([spec], figsize, formatters, figure_formatter)[0]

    def draw_pages(self, specs: list[FigureSpec], figsize: tuple,
                   formatters: dict[str, AxesFormatter] | None = None,
                   figure_formatter: Callable[[Any, dict[str, Any]], Any] | None = None) -> list[DrawnFigure]:
        """
        把一次计划的多张图画进同一个 Figure，每张是一页。刚画完只显示第一页，用 `add_page_slider` 翻页。

        matplotlib 后端没有这个方法，仍是一张计划一张图；``DataPlotter`` 按「后端有没有这个方法」选择。

        Parameters
        ----------
        specs : list of FigureSpec
            同一次计划生成的多张图。
        figsize, formatters, figure_formatter
            同 `draw`。

        Returns
        -------
        list of DrawnFigure
            每页一个，``fig`` 和 ``axes`` 各页共用，``artists`` 只有这一页的 trace。

        Raises
        ------
        ValueError
            计划里的版式或画法不认识；或给右轴配了图例回调。

        Notes
        -----
        各页来自同一次计划，单位、版式、负对数设置都相同，所以一个 Figure 只有一套轴：
        排版按第一页（图例标题也是第一页的，翻页时再换）；回调对整个 Figure 只调用一次，
        线条回调拿到这根轴上所有页的 trace。
        """
        formatters = formatters or {}
        for spec in specs:
            if spec.layout not in LAYOUTS:
                raise ValueError(f"不支持的绘图版式: '{spec.layout}'，可选：{', '.join(LAYOUTS)}")

        first = specs[0]
        preset = LAYOUTS[first.layout]
        width, height = translate_figsize(figsize, self.dpi, 'plotly')
        # meta 是 Plotly 留给用户放自定义数据的字段，不影响画面：记下 dpi，单轴 formatter 的刻度（磅）按它换成像素
        fig = go.Figure(layout=dict(template=self.template, width=width, height=height, meta={'dpi': self.dpi}))
        axes = {'left': _Y_AXIS['left']}
        if any(curve.axis == 'right' for spec in specs for curve in spec.curves):
            axes['right'] = _Y_AXIS['right']

        pages = []      # 每页的 trace，与这页的 spec.curves 一一对应
        for page, spec in enumerate(specs):
            artists = [self._draw_curve(fig, curve, preset) for curve in spec.curves]
            for artist in artists:
                artist.visible = (page == 0)        # 刚画完只显示第一页
            pages.append(artists)

        curves = [curve for spec in specs for curve in spec.curves]
        artists = [artist for page_artists in pages for artist in page_artists]
        self._apply_layout(fig, axes, first, preset)
        self._apply_optional_formatters(fig, axes, curves, artists, formatters)
        self._apply_figure_formatter(fig, axes, figure_formatter)
        self._apply_neglog_formatter(fig, axes, first)
        # 最后看各轴的最终设置：对数轴写了刻度格式时，让「次刻度不写文字」仍然生效（用户自己设了刻度间距就不动）
        for axis_name in ('xaxis', *axes.values()):
            apply_log_format(fig, axis_name)

        return [DrawnFigure(spec=spec, fig=fig, axes=axes, artists=page_artists)
                for spec, page_artists in zip(specs, pages)]

    def _draw_curve(self, fig: go.Figure, curve: CurveSpec, preset: LayoutPreset):
        """
        画一条线，返回 Figure 里实际保存的 trace。颜色、分组样式、所在的轴在画的时候一次给出。
        """
        color = self._curve_color(curve, preset)
        # 线和点都写上颜色，否则点会用 Plotly 默认配色；柱状图（go.Bar）没有 line 属性，只写 marker
        colors = {'marker': dict(color=color)} if curve.kind == 'bar' else \
                 {'line': dict(color=color), 'marker': dict(color=color)}
        # 右线挂右轴（也进图例，与 matplotlib 一致）
        placement = {'yaxis': _TRACE_Y['right']} if curve.axis == 'right' else {}
        # 颜色、分组样式（线型、标记）都在画的时候一次给出（对照 matplotlib 后端）
        return self._plot_data(fig, curve.x, curve.y, curve.kind, name=curve.label,
                               **colors, **placement, **self._native_style(curve))

    # ========================================================================
    # 翻译：计划里的标准写法 / 色带位置 → Plotly 原生值（对照 matplotlib 后端）
    # ========================================================================

    def _curve_color(self, curve: CurveSpec, preset: LayoutPreset) -> str | None:
        """
        算出一条线的最终颜色。

        优先级：分组写的颜色 > 色带位置 > 版式预设里这根轴的颜色 > Plotly 默认配色（返回 None）。
        与 matplotlib 后端的同名方法一致。
        """
        # translate_color / sample_colorscale 的返回类型标注较宽（含 matplotlib 用的元组），到 Plotly 实际总是字符串
        if curve.style.color is not None:
            return cast(str, translate_color(curve.style.color, 'plotly'))
        if curve.color_position is not None:
            return cast(str, plyc.sample_colorscale(self.cmap, [curve.color_position])[0])
        axis_style = preset.axes.get('y' if curve.axis == 'left' else 'y2')
        if axis_style is not None and axis_style.color is not None:
            return cast(str, translate_color(axis_style.color, 'plotly'))
        return None

    def _native_style(self, curve: CurveSpec) -> dict:
        """
        把分组样式翻译成 trace 属性，画线时一次给出；颜色另由 ``_curve_color`` 给出。

        只取这种画法看得见的字段（``style.STYLE_FIELDS_BY_KIND``）：折线全取，散点只取标记，柱状图都不取。
        折线的标记按「DataPlotter 全局 < 分组」叠加；有标记时绘制模式改成 ``'lines+markers'``，
        标记才显示（matplotlib 不需要这一步）。散点本来就是 ``'markers'``。
        """
        fields = STYLE_FIELDS_BY_KIND.get(curve.kind, ())     # 画法写错时由 _plot_data 报错
        style = curve.style
        if curve.kind == 'line':
            # DataPlotter 全局的 marker 只给折线，分组写的盖过它（对照 matplotlib 的 rc lines.marker：只管 plot，不管 scatter）。
            # 不放进模板：模板的标记同时作用于散点（55576fb 复审 2）
            style = LineStyle(marker=self.appearance.lines.marker).updated(style)
        native = translate_line_style(only_fields(style, fields), 'plotly', self.dpi, dash_width=self.line_width)
        if 'marker_symbol' in native and curve.kind == 'line':
            native['mode'] = 'lines+markers'
        return native

    # ========================================================================
    # 渲染：画线
    # ========================================================================

    @staticmethod
    def _plot_data(fig: go.Figure, x, y, plot_kind: str = 'line', **kwargs):
        """
        按画法往 Figure 里加一条 trace（折线、散点是 ``go.Scatter``，柱状图是 ``go.Bar``），
        返回 Figure 里实际保存的那一个（``fig.data[-1]``，不是传入前的对象）。*kwargs* 里给了 ``mode`` 时以它为准。

        Raises
        ------
        ValueError
            不认识的画法。
        """
        match plot_kind:
            case 'line':
                trace = go.Scatter(x=x, y=y, **({'mode': 'lines'} | kwargs))
            case 'scatter':
                trace = go.Scatter(x=x, y=y, **({'mode': 'markers'} | kwargs))
            case 'bar':
                trace = go.Bar(x=x, y=y, **kwargs)
            case _:
                raise ValueError(f"不支持的 plot_kind: '{plot_kind}'")
        fig.add_trace(trace)
        return fig.data[-1]

    # ========================================================================
    # 渲染：按排版预设排版（对照 MatplotlibBackend._apply_layout）
    # ========================================================================

    def _apply_layout(self, fig: go.Figure, axes: dict, spec: FigureSpec, preset: LayoutPreset):
        """
        按版式预设排版：图例、轴标题、右轴、各轴的刻度格式和着色、边框。

        图例和边框按「库默认 < 预设 < DataPlotter 全局」叠加。预设里的 ``margins`` 不用，
        Plotly 会自动给图外的图例留边；图例的 ``draggable`` 也不用，Plotly 的拖动是显示时的设置。
        """
        legend = translate_legend_style(resolve_legend(preset, self.appearance), 'plotly', self.dpi)
        fig.update_layout(legend=legend, xaxis_title_text=spec.x_unit, yaxis_title_text=spec.y_unit)
        if spec.legend_title is not None:
            fig.update_layout(legend_title_text=spec.legend_title)
        if 'right' in axes:
            # 右轴叠在左轴上、放在右侧，与左轴共用 X 轴（对应 matplotlib 的 twinx）。
            # tickmode='auto'：右轴按自己的数据选整齐的刻度。Plotly 对叠加的轴默认 'sync'（刻度位置对齐左轴），
            # 刻度值会变成 1.0007、0.9022 这样不整齐的数（2026-11-20 渲染时发现）；matplotlib 的 twinx 也是各算各的
            fig.update_layout(yaxis2=dict(overlaying='y', side='right', title_text=spec.y2_unit, tickmode='auto'))

        # 各轴（AxisStyle）：刻度格式、着色（标题、刻度、轴线同色）；与轴工厂同一个应用函数（plotly_styles，对照 matplotlib_styles）
        for axis_name, axis_style in preset.axes.items():
            apply_axis(fig, _LAYOUT_AXIS[axis_name], axis_style, 'x' if axis_name == 'x' else 'y')

        # 边框（FrameStyle）：逐根轴应用，与轴工厂同一个函数（对照 matplotlib 后端逐个 ax 调 apply_frame）。
        # 右轴要在这之前建好：左轴看到有叠加的右轴才不镜像右边
        frame = resolve_frame(preset, self.appearance)
        for axis_name in axes.values():
            apply_frame(fig, axis_name, frame)

    # ========================================================================
    # 渲染：用户 formatter & 负对数刻度（对照 matplotlib 后端）
    # ========================================================================

    @staticmethod
    def _apply_optional_formatters(fig: go.Figure, axes: dict, curves: list[CurveSpec], artists: list,
                                   formatters: dict[str, AxesFormatter]):
        """
        按轴调用用户回调，调用形状与 matplotlib 对应：坐标轴 ``(轴名, fig)``、线条（这根轴的 trace）、
        图例 ``[fig.layout.legend]``。

        先调用各轴的坐标轴、线条回调，最后调用图例回调。一张图一个图例，归左轴；给其他轴配了图例回调就报错。
        Plotly 的图例跟着 trace 的样式自动更新，不用像 matplotlib 那样重建。

        Raises
        ------
        ValueError
            给左轴以外的轴配了图例回调。
        """
        fms = {axis: formatters.get(axis, AxesFormatter()) for axis in axes}
        for axis, axis_name in axes.items():
            fm = fms[axis]
            if fm.axes is not None:
                fm.axes(axis_name, fig)
            if fm.lines is not None:
                fm.lines([artist for curve, artist in zip(curves, artists) if curve.axis == axis])

        for axis, fm in fms.items():
            if fm.legend is not None:
                if axis != 'left':
                    raise ValueError(NO_LEGEND_MESSAGE)
                # fig.layout 的类型标注过宽，cast 后才认得 legend
                fm.legend([cast(go.Layout, fig.layout).legend])

    @staticmethod
    def _apply_figure_formatter(fig: go.Figure, axes: dict, figure_formatter):
        """调用整图回调：在各轴回调之后调用一次，传入图和全部轴名。"""
        if figure_formatter is not None:
            figure_formatter(fig, axes)

    @staticmethod
    def _apply_neglog_formatter(fig: go.Figure, axes: dict, spec: FigureSpec):
        """
        负对数：给对应的轴加负号前缀 ``tickprefix='-'`` （数据在计划里已取绝对值）。
        上轴 ``'x2'`` 目前还没有，跳过。
        """
        existing = {'x', 'y'} | ({'y2'} if 'right' in axes else set())
        for axis_name in spec.neglog & existing:
            fig.update_layout({_LAYOUT_AXIS[axis_name]: dict(tickprefix='-')})

    # ========================================================================
    # 外观：模板（由已删除的 InteractivePlotter 搬来；字号、线宽改为读 Appearance，按 dpi 换成像素）
    # ========================================================================

    @staticmethod
    def _create_template(appearance: Appearance, px) -> go.layout.Template:
        """
        生成所有图共用的外观模板：``layout`` 管字体、坐标轴和图例，``data`` 管各类 trace 的默认外观。

        字号、线宽、刻度来自 *appearance* （磅按 *px* 换成像素）；白底、黑色轴线、不画网格是固定风格。
        模板里的 ``xaxis`` / ``yaxis`` 对所有 X / Y 轴生效，包括右轴 ``yaxis2``。
        """
        font_size = px(appearance.font_size)
        # 样式对象：库默认 < 用户在 DataPlotter 写的那一层（版式预设在画每张图时再叠）
        lines = DEFAULT_LINES.updated(appearance.lines)
        legend = DEFAULT_LEGEND.updated(appearance.legend)
        # 刻度：朝向、长短粗细、次刻度开关、刻度文字、对数轴次刻度写什么（默认 'none'：小号数字与主刻度文字大小不一致）
        ticks = translate_ticks(DEFAULT_TICKS.updated(appearance.ticks), 'plotly', appearance.dpi)
        ticks['minor'] = {**ticks.get('minor', {}), 'showgrid': False}
        axis_style = dict(
            title_font_size=font_size,
            title_font_weight=appearance.font_weight,
            # 轴线宽（FrameStyle）；上 / 右边框跟版式有关，画每张图时设 mirror（_apply_layout 里的 plotly_styles.apply_frame）
            showline=True, linecolor='black', mirror=False,
            linewidth=translate_frame(DEFAULT_FRAME.updated(appearance.frame), 'plotly', appearance.dpi)['linewidth'],
            tickcolor='black',
            showgrid=False, zeroline=False, automargin=True,
            **ticks,
        )
        # 全局 marker 不进模板（这里的默认样式也作用于散点，散点固定用圆点）；折线的标记在 _native_style 里逐条给
        line = translate_line_style(replace(lines, marker=None), 'plotly', appearance.dpi)
        return go.layout.Template(
            layout=go.Layout(
                font_family=appearance.font_family,
                font_size=font_size,
                font_color='black',
                font_weight=appearance.font_weight,
                paper_bgcolor='white',
                plot_bgcolor='white',
                # 顶部留出标题位置；滑块会把标题改成当前曲线名。
                margin=dict(l=40, r=40, t=80, b=40),
                title_x=0.5,
                title_xanchor='center',
                title_font_size=font_size,
                xaxis=axis_style,
                yaxis=axis_style,
                legend=translate_legend_style(legend, 'plotly', appearance.dpi),
            ),
            data=dict(
                # 列表中的一项是一套默认样式，不是图中的第一条曲线；不指定颜色，让不同样品保留各自的配色。
                scatter=[go.Scatter(
                    **line,             # 线宽、线型、标记大小（LineStyle，磅 → 像素）
                    marker_symbol='circle',
                    connectgaps=False,
                )],
                bar=[go.Bar(marker_line_width=0)],
            ),
        )

    # ========================================================================
    # 交互：滑块（画完之后的可选交互，只有 Plotly 有；由已删除的 InteractivePlotter 搬来）
    # ========================================================================

    _SLIDER_FONT_SIZE = 16  # 滑块档位标签字号（像素）；也用于估算标签是否放得下

    def add_slider(self, fig: go.Figure, mode: SliderMode = 'cumulative',
                   slider_formatter: Callable[[go.layout.Slider], object] | None = None,
                   curves: list | None = None) -> go.Figure:
        """
        给一页图加曲线滑块：一条线一档，拖动时标题换成当前曲线名。原地修改并返回这张图。

        Parameters
        ----------
        fig : `plotly.graph_objects.Figure`
            要加滑块的图。
        mode : {'cumulative', 'single'}, default: 'cumulative'
            ``'cumulative'``：每档显示第一条到当前这条线；``'single'``：每档只显示当前这条线。
        slider_formatter : callable, optional
            接收安装好的滑块并原地修改，在默认外观之后执行。
        curves : list of trace, optional
            参与滑动的 trace（``DataPlotter`` 传入计划画出的 ``DrawnFigure.artists``）。其余 trace
            （如整图回调加的参考线）不分档，每档保持原来的显隐。不传时图里每条 trace 一档。

        Returns
        -------
        `plotly.graph_objects.Figure`
            传入的 *fig*。重复调用只保留一个滑块。

        Raises
        ------
        RuntimeError
            图里没有可以滑动的曲线。
        ValueError
            *mode* 写错（检查在改图之前，图保持原样）。
        """
        # Plotly 的 data 类型标注较宽，在此明确它是 trace 元组；cast 不复制对象
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)
        indices = list(range(len(traces))) if curves is None else self._positions(fig, curves)
        if not indices:
            raise RuntimeError("图中没有曲线，无法添加滑块")
        names = [cast(str, traces[i].name) or str(i) for i in indices]
        steps = [(name, [i], {'title.text': name}) for i, name in zip(indices, names)]
        return self._install_slider(fig, steps, mode, 'Trace: ', slider_formatter)

    def add_page_slider(self, pages: list[DrawnFigure], mode: SliderMode = 'single',
                        slider_formatter: Callable[[go.layout.Slider], object] | None = None) -> go.Figure:
        """
        给 `draw_pages` 画出的多页图加翻页滑块：一页一档。原地修改并返回各页共用的 Figure。

        Parameters
        ----------
        pages : list of DrawnFigure
            `draw_pages` 的结果。
        mode : {'single', 'cumulative'}, default: 'single'
            ``'single'``：每档只显示当前页；``'cumulative'``：每档显示第一页到当前页。
        slider_formatter : callable, optional
            接收安装好的滑块并原地修改，在默认外观之后执行。

        Returns
        -------
        `plotly.graph_objects.Figure`
            各页共用的 Figure。

        Notes
        -----
        档位标签是每页的名字（``FigureSpec.name``，组名或样品名），没有名字时用 key。
        翻页时标题和图例标题换成这一页的。组名、样品名都可能出现，所以当前值默认不加前缀。
        """
        fig = cast(go.Figure, pages[0].fig)
        steps = []
        for page in pages:
            label = page.spec.name if page.spec.name is not None else str(page.spec.key)
            steps.append((label, self._positions(fig, page.artists),
                          {'title.text': label, 'legend.title.text': page.spec.legend_title or ''}))
        return self._install_slider(fig, steps, mode, '', slider_formatter)

    @staticmethod
    def _positions(fig: go.Figure, artists: list) -> list[int]:
        """这些 trace 在 ``fig.data`` 里的位置；滑块的 ``visible`` 列表按位置对应每条 trace。"""
        position = {id(trace): i for i, trace in enumerate(cast(tuple, fig.data))}
        return [position[id(artist)] for artist in artists]

    def _install_slider(self, fig: go.Figure, steps: list[tuple[str, list[int], dict]], mode: SliderMode,
                        prefix: str, slider_formatter) -> go.Figure:
        """
        两种滑块共用的安装过程。

        Parameters
        ----------
        fig : `plotly.graph_objects.Figure`
            要加滑块的图。
        steps : list of (str, list of int, dict)
            每一档的 ``(标签, 这一档的 trace 在 fig.data 里的位置, 翻到这一档时改的 layout)``。
            曲线滑块一档一条 trace，翻页滑块一档一页的 trace；其余过程完全一样。
        mode : {'single', 'cumulative'}
            每档只显示这一档的 trace，还是显示第 0 档到这一档的。
        prefix : str
            当前值前面的文字。
        slider_formatter : callable or None
            用户对滑块的最后修改。

        Notes
        -----
        不在任何一档里的 trace（整图回调加的参考线等）每档都保持原来的显隐，包括 ``'legendonly'``。
        layout 的改动用带点的路径（如 ``'legend.title.text'``），只改这一项，不会冲掉图例位置等其他设置。
        """
        if mode not in ('single', 'cumulative'):
            raise ValueError(f"不支持的 mode: '{mode}'")       # 先校验再改图：写错时图保持原样
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)
        managed = {i for _, idx, _ in steps for i in idx}
        # 不归滑块管的 trace 原来的显隐：没设过（None）就是显示；'legendonly' 照原样保留
        kept = [True if trace.visible is None else trace.visible for trace in traces]

        def visible(step: int) -> list:
            """第 step 档各 trace 的显隐：single 只显示这一档的，cumulative 显示第 0 ~ step 档的；不归滑块管的保持原样。"""
            shown = steps[step][1] if mode == 'single' else [i for _, idx, _ in steps[:step + 1] for i in idx]
            return [i in shown if i in managed else kept[i] for i in range(len(traces))]

        for trace, shown in zip(traces, visible(0)):
            trace.visible = shown
        slider_steps = [dict(method='update', label=label, args=[{'visible': visible(k)}, layout_update])
                        for k, (label, _, layout_update) in enumerate(steps)]

        # 初始停在第 0 档：标题等与第 0 档一致，否则拖动前没有标题
        fig.update_layout(sliders=[go.layout.Slider(active=0, steps=slider_steps)])
        for path, value in steps[0][2].items():
            fig.layout[path] = value
        # 操作安装后的 Slider；Plotly 可能复制传入的原始对象
        installed = cast(tuple[go.layout.Slider, ...], cast(go.Layout, fig.layout).sliders)[0]
        labels = [label for label, _, _ in steps]
        self._apply_slider_format(installed, prefix, show_labels=self._slider_labels_fit(fig, labels))
        if slider_formatter is not None:
            slider_formatter(installed)
        return fig

    def _slider_labels_fit(self, fig: go.Figure, labels: list[str]) -> bool:
        """
        粗略估计档位标签能否并排放下而不重叠。

        Plotly 自带的标签抽稀对长标签不可靠，标签会互相压住，所以由这里预判。宽度按
        「字号 × 0.65 × 字符数」估算（粗体 Arial），只用于决定显示还是隐藏。
        """
        if len(labels) <= 1:
            return True
        width = cast(float, cast(go.Layout, fig.layout).width or 700)
        spacing = width * 0.9 / (len(labels) - 1)
        return self._SLIDER_FONT_SIZE * 0.65 * max(len(label) for label in labels) <= spacing

    def _apply_slider_format(self, slider: go.layout.Slider, prefix: str, show_labels: bool = True):
        """
        原地设置滑块的默认外观。

        *prefix* 是当前值前的文字（曲线滑块为 ``'Trace: '``，翻页滑块不加）。*show_labels* 为 False 时
        档位标签透明（仍占位置），名字由当前值和标题显示。
        """
        slider.update(
            # 当前值：轨道左上方显示当前曲线名 / 页名
            currentvalue_prefix=prefix, currentvalue_font_size=20, currentvalue_font_color='black',
            currentvalue_xanchor='left', currentvalue_offset=14,
            # 档位标签与刻度：细刻度，避免一排粗黑线
            font_size=self._SLIDER_FONT_SIZE, font_color='black' if show_labels else 'rgba(0,0,0,0)',
            ticklen=5, tickwidth=1, tickcolor='#555555', minorticklen=3,
            # 位置：与绘图区等宽；pad_t 让出 X 轴刻度文字和轴标题的高度
            x=0, xanchor='left', len=1, lenmode='fraction', pad_t=110, pad_b=10, pad_l=0, pad_r=0,
            # 轨道与拖动块：浅灰细边框
            bgcolor='#f2f2f2', activebgcolor='#bdbdbd', bordercolor='#9e9e9e', borderwidth=1,
        )
