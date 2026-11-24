"""
将绘图计划渲染为 Plotly 交互图，并提供曲线滑块和翻页滑块。

`PlotlyBackend.draw_pages` 在同一个 Figure 中渲染多张图，每页对应一份绘图计划。
``DrawnFigure.axes`` 保存布局中的轴名，例如 ``{'left': 'yaxis', 'right': 'yaxis2'}``，
可通过 ``fig.layout[轴名]`` 访问。
"""
from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any, Literal, cast

import plotly.colors as plyc
import plotly.graph_objects as go

from ..layouts import LAYOUTS, NO_LEGEND_MESSAGE, LayoutPreset, resolve_frame, resolve_legend
from ..plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, DEFAULT_SCATTER, DEFAULT_TICKS, Appearance,
                         AxesFormatter,
                         CurveBase, DrawnFigure, FigureSpec, LineSpec, LineStyle, ScatterSpec)
from ..style import (remember_fill, translate_color, translate_figsize, translate_frame, translate_legend_style,
                     translate_line_style, translate_points, translate_scatter_style, translate_ticks)
from .plotly_styles import apply_axis, apply_frame, apply_log_format

# 滑块模式：single 每档只显示一条曲线；cumulative 每档累加显示到当前曲线
type SliderMode = Literal['single', 'cumulative']

# 线挂的轴（CurveBase.axis）→ Plotly 配置里的纵轴名、trace 上的 yaxis 引用
_Y_AXIS = {'left': 'yaxis', 'right': 'yaxis2'}
_TRACE_Y = {'left': 'y', 'right': 'y2'}
# 排版预设 / 计划里的轴名（'x'、'y'、'y2'）→ Plotly 配置里的轴名
_LAYOUT_AXIS = {'x': 'xaxis', 'y': 'yaxis', 'y2': 'yaxis2'}


def _artists_of(spec_type: type, axis: str, curves: Sequence[CurveBase], artists: list) -> list:
    """这根轴上某种画法（*spec_type*，如 `LineSpec`）的 trace，按绘制顺序（与 matplotlib 后端的同名函数一致）。"""
    return [artist for curve, artist in zip(curves, artists) if curve.axis == axis and isinstance(curve, spec_type)]


class PlotlyBackend:
    """
    渲染交互图，并在同一个 Figure 中支持多页显示。

    ``DataPlotter(backend='plotly')`` 通过 `plotlib.backends.get_backend` 创建该后端。

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
        根据全局外观创建 Plotly 模板，并解析色带名称。

        渲染时，边框和图例样式还会合并版式预设。
        """
        self.appearance = appearance
        self.dpi = appearance.dpi
        px = lambda points: translate_points(points, self.dpi, 'plotly')      # noqa: E731  磅 → 像素
        # 自定义虚线的段长按线宽换算成像素：模板线宽和换算用同一个值
        self.line_width = px(DEFAULT_LINES.updated(appearance.lines).width)
        self.template = self._create_template(appearance, px)
        self.cmap = plyc.get_colorscale('Plasma' if cmap is None else cmap)

    # ========================================================================
    # 渲染入口
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
        在同一个 Figure 中渲染多张图，每张图对应一页。

        初始显示第一页，可用 `add_page_slider` 切换页面。

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
        各页共用坐标轴、单位、版式和负对数设置。初始化时采用第一页的版式和图例标题。
        回调针对共用 Figure 执行，线条回调接收相应坐标轴上各页的轨迹。
        """
        formatters = formatters or {}
        for spec in specs:
            if spec.layout not in LAYOUTS:
                raise ValueError(f"不支持的绘图版式: '{spec.layout}'，可选：{', '.join(LAYOUTS)}")

        first = specs[0]
        preset = LAYOUTS[first.layout]
        width, height = translate_figsize(figsize, self.dpi, 'plotly')
        # 将 DPI 保存到布局元数据，供格式化回调换算尺寸。
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
        # 根据回调完成后的设置处理对数轴的显式格式与次刻度标签。
        for axis_name in ('xaxis', *axes.values()):
            apply_log_format(fig, axis_name)

        return [DrawnFigure(spec=spec, fig=fig, axes=axes, artists=page_artists)
                for spec, page_artists in zip(specs, pages)]

    def _draw_curve(self, fig: go.Figure, curve: CurveBase, preset: LayoutPreset):
        """
        按曲线的类型往 Figure 里加一条 trace，返回 Figure 里实际保存的那一个（``fig.data[-1]``，不是传入前的对象）。

        颜色、样式、所在的轴在画的时候一次给出（颜色由 ``_curve_color`` 给出，样式里写的颜色已算在里面）：

        - `LineSpec`：``mode='lines'`` 的 ``go.Scatter``。标记按「DataPlotter 全局 < 分组」叠加
          （全局标记只给折线，写进模板会连散点一起改）；有标记时改成 ``'lines+markers'``，标记才显示
          （matplotlib 不需要这一步）。线和点都写上颜色，否则点会用 Plotly 默认配色。
        - `ScatterSpec`：``mode='markers'`` 的 ``go.Scatter``。

        Raises
        ------
        ValueError
            不认识的曲线类型。
        """
        placement = {'yaxis': _TRACE_Y['right']} if curve.axis == 'right' else {}     # 右线挂右轴（也进图例）
        match curve:
            case LineSpec():
                color = self._curve_color(curve, preset)
                style = LineStyle(marker=self.appearance.lines.marker).updated(replace(curve.style, color=None))
                native = translate_line_style(style, 'plotly', self.dpi, dash_width=self.line_width)
                mode = 'lines+markers' if 'marker_symbol' in native else 'lines'
                trace = go.Scatter(x=curve.x, y=curve.y, name=curve.label, mode=mode,
                                   line=dict(color=color), marker=dict(color=color), **placement, **native)
            case ScatterSpec():
                # 先套库默认（大小、描边都写明），模板里的折线样式就漏不到散点上
                style = DEFAULT_SCATTER.updated(replace(curve.style, color=None))
                color = self._curve_color(curve, preset)
                native = translate_scatter_style(style, 'plotly', self.dpi, fallback_color=color)
                trace = go.Scatter(x=curve.x, y=curve.y, name=curve.label, mode='markers', **placement, **native)
                fig.add_trace(trace)
                remember_fill(fig.data[-1], color)      # add_trace 会复制，要记在 Figure 里那一个上
                return fig.data[-1]
            case _:
                raise ValueError(f"不支持的画法：{type(curve).__name__}（可用 LineSpec、ScatterSpec）")
        fig.add_trace(trace)
        return fig.data[-1]

    # ========================================================================
    # 曲线颜色和样式
    # ========================================================================

    def _curve_color(self, curve: LineSpec | ScatterSpec, preset: LayoutPreset) -> str | None:
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

    # ========================================================================
    # 版式应用
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
            # 右轴与左轴共用 X 轴，并独立计算 Y 轴刻度。
            fig.update_layout(yaxis2=dict(overlaying='y', side='right', title_text=spec.y2_unit, tickmode='auto'))

        for axis_name, axis_style in preset.axes.items():
            apply_axis(fig, _LAYOUT_AXIS[axis_name], axis_style, 'x' if axis_name == 'x' else 'y')

        # 先创建右轴，再应用边框，避免左轴同时绘制右边框。
        frame = resolve_frame(preset, self.appearance)
        for axis_name in axes.values():
            apply_frame(fig, axis_name, frame)

    # ========================================================================
    # 格式化回调和负对数刻度
    # ========================================================================

    @staticmethod
    def _apply_optional_formatters(fig: go.Figure, axes: dict, curves: Sequence[CurveBase], artists: list,
                                   formatters: dict[str, AxesFormatter]):
        """
        执行坐标轴、线条和散点回调，再执行整图图例回调。

        线条回调只收这根轴上的折线 trace，散点回调只收散点 trace，两者互不干扰。
        Plotly 会随轨迹样式更新图例。图例回调通过左轴处理。

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
                fm.lines(_artists_of(LineSpec, axis, curves, artists))
            if fm.scatter is not None:
                fm.scatter(_artists_of(ScatterSpec, axis, curves, artists))

        for axis, fm in fms.items():
            if fm.legend is not None:
                if axis != 'left':
                    raise ValueError(NO_LEGEND_MESSAGE)
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
    # Figure 模板
    # ========================================================================

    @staticmethod
    def _create_template(appearance: Appearance, px) -> go.layout.Template:
        """
        生成所有图共用的外观模板：``layout`` 管字体、坐标轴和图例，``data`` 管各类 trace 的默认外观。

        字号、线宽、刻度来自 *appearance* （磅按 *px* 换成像素）；白底、黑色轴线、不画网格是固定风格。
        模板里的 ``xaxis`` / ``yaxis`` 对所有 X / Y 轴生效，包括右轴 ``yaxis2``。
        """
        font_size = px(appearance.font_size)
        # 将全局样式合并到库默认值中。
        lines = DEFAULT_LINES.updated(appearance.lines)
        legend = DEFAULT_LEGEND.updated(appearance.legend)
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
        # 折线标记在创建轨迹时设置，模板保留散点的默认标记。
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
    # 交互滑块
    # ========================================================================

    _SLIDER_FONT_SIZE = 16  # 档位标签的字号，单位为像素。

    def add_slider(self, fig: go.Figure, mode: SliderMode = 'cumulative',
                   slider_formatter: Callable[[go.layout.Slider], object] | None = None,
                   curves: list | None = None) -> go.Figure:
        """
        为单页图添加曲线滑块并返回该图。滑块每档对应一条曲线，并更新图标题。

        Parameters
        ----------
        fig : `plotly.graph_objects.Figure`
            要加滑块的图。
        mode : {'cumulative', 'single'}, default: 'cumulative'
            ``'cumulative'``：每档显示第一条到当前这条线；``'single'``：每档只显示当前这条线。
        slider_formatter : callable, optional
            接收安装好的滑块并原地修改，在默认外观之后执行。
        curves : list of trace, optional
            滑块控制的轨迹。其余轨迹保留自身的可见性。省略时每条轨迹对应一个档位。

        Returns
        -------
        `plotly.graph_objects.Figure`
            传入的 *fig*。重复调用只保留一个滑块。

        Raises
        ------
        RuntimeError
            图里没有可以滑动的曲线。
        ValueError
            *mode* 不是受支持的模式。
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
        未分配到档位的轨迹保留初始可见性，包括 ``'legendonly'``。
        通过 ``'legend.title.text'`` 等属性路径局部更新布局。
        """
        if mode not in ('single', 'cumulative'):
            raise ValueError(f"不支持的 mode: '{mode}'")
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)
        managed = {i for _, idx, _ in steps for i in idx}
        # 保留轨迹的初始可见性，包括 'legendonly' 状态。
        kept = [True if trace.visible is None else trace.visible for trace in traces]

        def visible(step: int) -> list:
            """计算指定档位下各轨迹的可见性。"""
            shown = steps[step][1] if mode == 'single' else [i for _, idx, _ in steps[:step + 1] for i in idx]
            return [i in shown if i in managed else kept[i] for i in range(len(traces))]

        for trace, shown in zip(traces, visible(0)):
            trace.visible = shown
        slider_steps = [dict(method='update', label=label, args=[{'visible': visible(k)}, layout_update])
                        for k, (label, _, layout_update) in enumerate(steps)]

        # 将初始布局设为第一档。
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
        估算滑块档位标签是否有足够空间。

        以最长标签的字符数和字号估算所需宽度，并与相邻档位间距比较。
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
