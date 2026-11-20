"""
Plotly 后端（STRUCTURE_REVIEW 6.7）：只读绘图计划，负责全部 Plotly 的事。与 matplotlib 后端逐段对应：

  - 翻译：外观 → 模板（__init__）、颜色（_curve_color）、线型 / 标记（_native_style）；
          通用的换算（磅 → 像素、英寸 → 像素、图例位置、刻度格式）在翻译层 style.translate_*；
  - 渲染：建图、画线、按排版预设排版、用户回调、负对数刻度；
  - 多页（6.8）：draw_pages 把一次计划的多张 FigureSpec 画进同一个 Figure，每张一页；
  - 交互：滑块（画完之后可选，只有 Plotly 有）：add_slider 一条线一档，add_page_slider 一页一档。
不认识 DataSet、Group、DataPlotter；输入是 FigureSpec，输出是 DrawnFigure。

Plotly 没有轴对象，坐标轴是 layout 里的一段配置：DrawnFigure.axes 放配置里的轴名
{'left': 'yaxis', 'right': 'yaxis2'}（两根轴共用 'xaxis'），用 fig.layout[轴名] 读写。
"""
from collections.abc import Callable
from typing import Any, Literal, cast

import plotly.colors as plyc
import plotly.graph_objects as go

from ..layouts import LAYOUTS, NO_LEGEND_MESSAGE, LayoutPreset, resolve_frame, resolve_legend
from ..plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, DEFAULT_TICKS, Appearance, AxesFormatter,
                         CurveSpec, DrawnFigure, FigureSpec)
from ..style import (STYLE_FIELDS_BY_KIND, only_fields, translate_axis_style, translate_color, translate_figsize,
                     translate_frame, translate_legend_style, translate_line_style, translate_points,
                     translate_ticks)

# 滑块模式：single 每档只显示一条曲线；cumulative 每档累加显示到当前曲线
type SliderMode = Literal['single', 'cumulative']

# 线挂的轴（CurveSpec.axis）→ Plotly 配置里的纵轴名、trace 上的 yaxis 引用
_Y_AXIS = {'left': 'yaxis', 'right': 'yaxis2'}
_TRACE_Y = {'left': 'y', 'right': 'y2'}
# 排版预设 / 计划里的轴名（'x'、'y'、'y2'）→ Plotly 配置里的轴名
_LAYOUT_AXIS = {'x': 'xaxis', 'y': 'yaxis', 'y2': 'yaxis2'}


class PlotlyBackend:

    name = 'plotly'

    def __init__(self, appearance: Appearance, cmap: str | None = None):
        """
        翻译外观：Appearance（后端无关，磅）→ Plotly 模板（像素，按 appearance.dpi 换算）；解析色带名。
        样式对象按「库默认 < 用户在 DataPlotter 写的那一层」叠加；跟版式有关的（边框的上 / 右边、图例位置）
        还要叠上版式预设，在画每张图时处理（对照 matplotlib 后端）。
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
        按一张 FigureSpec 画一个 go.Figure，返回 DrawnFigure（就是只有一页的 draw_pages）。
        formatters：按轴分组的用户回调 {'left': AxesFormatter(...), 'right': ...}，形状与 matplotlib 对应：
            axes (轴名, fig)、lines (这根轴的 trace 列表)、legend ([fig.layout.legend]，只有左轴有)。
        figure_formatter(fig, axes)：整图回调，axes 是全部轴名 {'left': 'yaxis', 'right': 'yaxis2'}。
        """
        return self.draw_pages([spec], figsize, formatters, figure_formatter)[0]

    def draw_pages(self, specs: list[FigureSpec], figsize: tuple,
                   formatters: dict[str, AxesFormatter] | None = None,
                   figure_formatter: Callable[[Any, dict[str, Any]], Any] | None = None) -> list[DrawnFigure]:
        """
        把一次计划的多张 FigureSpec 画进同一个 go.Figure，每张是一页（6.8；matplotlib 没有这个方法，仍一张计划一张图）。
        刚画完只显示第一页，用 add_page_slider 翻页。返回每页一个 DrawnFigure：fig、axes 共用，artists 只有这一页的 trace。

        各页来自同一次计划，单位、版式、neglog 相同，所以一个 Figure 只有一套轴：
        排版按第一页（图例标题也是第一页的，翻页时换），回调对整个 Figure 只调一次，线回调拿到这根轴上所有页的 trace。
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

        return [DrawnFigure(spec=spec, fig=fig, axes=axes, artists=page_artists)
                for spec, page_artists in zip(specs, pages)]

    def _draw_curve(self, fig: go.Figure, curve: CurveSpec, preset: LayoutPreset):
        """画一条线，返回 Figure 里实际保存的 trace（对照 MatplotlibBackend._draw 里画线的那一段）。"""
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
        一条线的最终颜色（颜色一次赋值；对照 MatplotlibBackend._curve_color）。优先级：
        分组写的颜色 > 色带位置 > 排版预设里这根轴的颜色 > Plotly 默认配色（返回 None）。
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
        分组写了的样式（LineStyle 标准写法）→ trace 属性，画线时一次给出（对照 MatplotlibBackend._native_style）。颜色另给。
        只取这种画法看得见的字段（style.STYLE_FIELDS_BY_KIND）：折线全取，散点只取标记，柱状图都不取。
        折线写了 marker 时要改成 'lines+markers' 才显示点（matplotlib 不需要这一步）；散点本来就是 'markers'。
        """
        fields = STYLE_FIELDS_BY_KIND.get(curve.kind, ())     # 画法写错时由 _plot_data 报错
        native = translate_line_style(only_fields(curve.style, fields), 'plotly', self.dpi, dash_width=self.line_width)
        if 'marker_symbol' in native and curve.kind == 'line':
            native['mode'] = 'lines+markers'
        return native

    # ========================================================================
    # 渲染：画线
    # ========================================================================

    @staticmethod
    def _plot_data(fig: go.Figure, x, y, plot_kind: str = 'line', **kwargs):
        """按 plot_kind 添加一条图形，返回 Figure 中实际保存的 trace。kwargs 里给了 mode 时以它为准。"""
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
        按排版预设设置图例、轴标题、各轴（刻度格式、着色）、边框（值的翻译在翻译层 style.translate_*）。
        图例、边框按「库默认 < 预设 < DataPlotter 全局」叠加（layouts.resolve_*，对照 matplotlib 后端）。
        预设里的 margins 不用：Plotly 会自动给图外的图例留边；图例的 draggable 不用：Plotly 的拖动是显示时的设置。
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

        # 各轴（AxisStyle）：刻度格式、着色（标题、刻度、轴线同色）
        for axis_name, axis_style in preset.axes.items():
            letter = 'x' if axis_name == 'x' else 'y'
            fig.update_layout({_LAYOUT_AXIS[axis_name]: translate_axis_style(axis_style, 'plotly', letter)})

        self._apply_frame(fig, axes, translate_frame(resolve_frame(preset, self.appearance), 'plotly', self.dpi))

    @staticmethod
    def _apply_frame(fig: go.Figure, axes: dict, frame: dict):
        """
        边框（对照 matplotlib 的 spines）：上边 = X 轴的镜像线，右边 = 左 Y 轴的镜像线。
        有右轴时右边就是右轴自己的轴线，左 Y 轴不再镜像（否则左轴着色的镜像线会叠在右轴上）。
        """
        names = ['xaxis', 'yaxis'] + (['yaxis2'] if 'right' in axes else [])
        if 'linewidth' in frame:
            for name in names:
                fig.update_layout({name: dict(linewidth=frame['linewidth'])})
        if 'top' in frame:
            fig.update_layout(xaxis_mirror=frame['top'])
        if 'right' in frame:
            fig.update_layout(yaxis_mirror=frame['right'] and 'right' not in axes)

    # ========================================================================
    # 渲染：用户 formatter & 负对数刻度（对照 matplotlib 后端）
    # ========================================================================

    @staticmethod
    def _apply_optional_formatters(fig: go.Figure, axes: dict, curves: list[CurveSpec], artists: list,
                                   formatters: dict[str, AxesFormatter]):
        """
        应用各轴的用户回调，形状与 matplotlib 对应：axes (轴名, fig)、lines (这根轴的 trace)、legend (图例列表)。
        与 matplotlib 同样分两遍：先各轴的轴、线回调，最后图例回调（一张图一个图例，归左轴；其他轴配了 → 报错）。
        Plotly 的图例跟着 trace 的样式自动更新，线改了样式不用像 matplotlib 那样重建图例。
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
        """整图回调：各轴回调之后调用一次，拿到图和全部轴名（三种版式都支持）。"""
        if figure_formatter is not None:
            figure_formatter(fig, axes)

    @staticmethod
    def _apply_neglog_formatter(fig: go.Figure, axes: dict, spec: FigureSpec):
        """负对数刻度：数据在计划里已取绝对值，这里给对应的轴加负号前缀。'x2'（上轴）Plotly 这里还没有，跳过。"""
        existing = {'x', 'y'} | ({'y2'} if 'right' in axes else set())
        for axis_name in spec.neglog & existing:
            fig.update_layout({_LAYOUT_AXIS[axis_name]: dict(tickprefix='-')})

    # ========================================================================
    # 外观：模板（由已删除的 InteractivePlotter 搬来；字号、线宽改为读 Appearance，按 dpi 换成像素）
    # ========================================================================

    @staticmethod
    def _create_template(appearance: Appearance, px) -> go.layout.Template:
        """
        通用外观模板：layout 管字体、坐标轴和图例；data 管各类 trace 的默认外观。
        字号、线宽、刻度（TickStyle）来自 Appearance（磅 → 像素，翻译在 style.translate_ticks）；颜色、网格等是 Plotly 一侧的固定风格。
        模板里的 xaxis / yaxis 设置对所有 X / Y 轴生效（含右轴 yaxis2）。
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
            # 轴线宽（FrameStyle）；上 / 右边框跟版式有关，画每张图时设 mirror（_apply_frame）
            showline=True, linecolor='black', mirror=False,
            linewidth=translate_frame(DEFAULT_FRAME.updated(appearance.frame), 'plotly', appearance.dpi)['linewidth'],
            tickcolor='black',
            showgrid=False, zeroline=False, automargin=True,
            **ticks,
        )
        line = translate_line_style(lines, 'plotly', appearance.dpi)
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
                    marker_symbol=line.get('marker_symbol', 'circle'),
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
                   slider_formatter: Callable[[go.layout.Slider], object] | None = None) -> go.Figure:
        """
        曲线滑块：一条线一档，原地修改并返回这张图。拖动时标题换成当前曲线名。
        mode：'single' 每档只显示当前曲线；'cumulative' 每档显示第一条到当前曲线。
        slider_formatter：接收安装后的 Slider 并原地修改，在默认外观之后执行。
        """
        # Plotly 的 data 类型标注较宽，在此明确它是 trace 元组；cast 不复制对象
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)
        if not traces:
            raise RuntimeError("图中没有曲线，无法添加滑块")
        names = [cast(str, trace.name) or str(i) for i, trace in enumerate(traces)]
        steps = [(name, [i], {'title.text': name}) for i, name in enumerate(names)]
        return self._install_slider(fig, steps, mode, 'Trace: ', slider_formatter)

    def add_page_slider(self, pages: list[DrawnFigure], mode: SliderMode = 'single',
                        slider_formatter: Callable[[go.layout.Slider], object] | None = None) -> go.Figure:
        """
        翻页滑块（6.8）：draw_pages 画出的多页图，一页一档，原地修改并返回这个 Figure。
        档位标签是每页的名字（FigureSpec.name：组名 / 样品名）；翻页时标题、图例标题换成这一页的。
        mode 与曲线滑块相同（用户要求）：'single' 每档只显示当前页；'cumulative' 每档显示第一页到当前页。
        当前值默认不加前缀（组名、样品名都可能出现）；要加用 slider_formatter。
        """
        fig = cast(go.Figure, pages[0].fig)
        position = {id(trace): i for i, trace in enumerate(cast(tuple, fig.data))}     # trace → 在 fig.data 里的位置
        steps = []
        for page in pages:
            label = page.spec.name if page.spec.name is not None else str(page.spec.key)
            steps.append((label, [position[id(artist)] for artist in page.artists],
                          {'title.text': label, 'legend.title.text': page.spec.legend_title or ''}))
        return self._install_slider(fig, steps, mode, '', slider_formatter)

    def _install_slider(self, fig: go.Figure, steps: list[tuple[str, list[int], dict]], mode: SliderMode,
                        prefix: str, slider_formatter) -> go.Figure:
        """
        两种滑块共用：steps 是每一档的 (标签, 这一档的 trace 在 fig.data 里的位置, 翻到这一档时改的 layout)。
        曲线滑块一档一条 trace，翻页滑块一档一页的 trace——其余（显隐、默认外观、formatter）完全一样。
        layout 的改动用带点的路径（如 'legend.title.text'）：只改这一项，不会把图例位置等其他设置冲掉。
        """
        if mode not in ('single', 'cumulative'):
            raise ValueError(f"不支持的 mode: '{mode}'")       # 先校验再改图：写错时图保持原样
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)

        def visible(step: int) -> list[bool]:
            """第 step 档显示哪些 trace：single 只有这一档的，cumulative 是第 0 ~ step 档的。"""
            shown = steps[step][1] if mode == 'single' else [i for _, idx, _ in steps[:step + 1] for i in idx]
            return [i in shown for i in range(len(traces))]

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
        粗略估计档位标签能否并排放下（不重叠）。Plotly 自带的标签抽稀对长标签不可靠，会互相压住，所以由这里预判。
        宽度按「字号 × 0.65 × 字符数」估算（粗体 Arial），只用于决定显示或隐藏。
        """
        if len(labels) <= 1:
            return True
        width = cast(float, cast(go.Layout, fig.layout).width or 700)
        spacing = width * 0.9 / (len(labels) - 1)
        return self._SLIDER_FONT_SIZE * 0.65 * max(len(label) for label in labels) <= spacing

    def _apply_slider_format(self, slider: go.layout.Slider, prefix: str, show_labels: bool = True):
        """
        原地设置整个滑块的默认外观。prefix 是当前值前的文字（曲线滑块 'Trace: '，翻页滑块不加）。
        show_labels 为 False 时档位标签透明（仍占位），名称由当前值和标题显示。
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
