"""
Plotly 后端（STRUCTURE_REVIEW 6.7）：只读绘图计划，负责全部 Plotly 的事。与 matplotlib 后端逐段对应：

  - 翻译：外观 → 模板（__init__）、颜色（_curve_color）、线型 / 标记（_native_style）；
          通用的换算（磅 → 像素、英寸 → 像素、图例位置、刻度格式）在翻译层 style.translate_*；
  - 渲染：建图、画线、按排版预设排版、用户回调、负对数刻度；
  - 交互：滑块（add_slider，画完之后可选，只有 Plotly 有）。
不认识 DataSet、Group、DataPlotter；输入是 FigureSpec，输出是 DrawnFigure。

Plotly 没有轴对象，坐标轴是 layout 里的一段配置：DrawnFigure.axes 放配置里的轴名
{'left': 'yaxis', 'right': 'yaxis2'}（两根轴共用 'xaxis'），用 fig.layout[轴名] 读写。
"""
from collections.abc import Callable
from typing import Any, Literal, cast

import plotly.colors as plyc
import plotly.graph_objects as go

from ..layouts import LAYOUTS, LayoutPreset
from ..plot_spec import Appearance, AxesFormatter, CurveSpec, DrawnFigure, FigureSpec
from ..style import (translate_color, translate_figsize, translate_legend, translate_linestyle, translate_marker,
                     translate_points, translate_tick_format)

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
        """翻译外观：Appearance（后端无关，磅）→ Plotly 模板（像素，按 appearance.dpi 换算）；解析色带名。"""
        self.dpi = appearance.dpi
        px = lambda points: translate_points(points, self.dpi, 'plotly')      # noqa: E731  磅 → 像素
        # 自定义虚线的段长按线宽换算成像素：模板线宽和换算用同一个值
        self.line_width = px(appearance.line_width)
        self.template = self._create_template(appearance, px)
        self.cmap = plyc.get_colorscale('Plasma' if cmap is None else cmap)

    # ========================================================================
    # 公开接口：按一张计划画一张图（与 MatplotlibBackend.draw 同一签名）
    # ========================================================================

    def draw(self, spec: FigureSpec, figsize: tuple,
             formatters: dict[str, AxesFormatter] | None = None,
             figure_formatter: Callable[[Any, dict[str, Any]], Any] | None = None) -> DrawnFigure:
        """
        按一张 FigureSpec 画一个 go.Figure，返回 DrawnFigure。
        formatters：按轴分组的用户回调，Plotly 的回调都收 fig；figure_formatter(fig, axes)，axes 是配置里的轴名。
        """
        formatters = formatters or {}
        if spec.layout not in LAYOUTS:
            raise ValueError(f"不支持的绘图版式: '{spec.layout}'，可选：{', '.join(LAYOUTS)}")
        return self._draw(spec, figsize, formatters, figure_formatter)

    def _draw(self, spec: FigureSpec, figsize: tuple,
              formatters: dict[str, AxesFormatter], figure_formatter) -> DrawnFigure:
        """
        三种版式共用的画法（对照 MatplotlibBackend._draw）。顺序：建图 → 画线（右线挂 y2）→ 按排版预设排版
        → 各轴用户回调 → 整图回调 → 负对数刻度。
        """
        preset = LAYOUTS[spec.layout]
        width, height = translate_figsize(figsize, self.dpi, 'plotly')
        fig = go.Figure(layout=dict(template=self.template, width=width, height=height))
        axes = {'left': _Y_AXIS['left']}
        if any(curve.axis == 'right' for curve in spec.curves):
            axes['right'] = _Y_AXIS['right']

        artists = []    # 与 spec.curves 一一对应
        for curve in spec.curves:
            color = self._curve_color(curve, preset)
            # 线和点都写上颜色，否则点会用 Plotly 默认配色；柱状图（go.Bar）没有 line 属性，只写 marker
            colors = {'marker': dict(color=color)} if curve.kind == 'bar' else \
                     {'line': dict(color=color), 'marker': dict(color=color)}
            # 右线挂右轴；与 matplotlib 一致，右轴的线不进图例
            placement = {'yaxis': _TRACE_Y['right'], 'showlegend': False} if curve.axis == 'right' else {}
            artist = self._plot_data(fig, curve.x, curve.y, curve.kind, name=curve.label, **colors, **placement)
            if curve.kind == 'line' and (line_style := self._native_style(curve.style)):
                artist.update(**line_style)     # 对照 matplotlib 的 artist.set(...)；颜色上面已给
            artists.append(artist)

        self._apply_layout(fig, axes, spec, preset)
        for axis in axes:                       # Plotly 的回调都收 fig；按轴分组只是和 matplotlib 保持同一接口
            fm = formatters.get(axis, AxesFormatter())
            for callback in (fm.axes, fm.lines, fm.legend):
                if callback is not None:
                    callback(fig)
        if figure_formatter is not None:
            figure_formatter(fig, axes)
        self._apply_neglog_formatter(fig, axes, spec)

        return DrawnFigure(spec=spec, fig=fig, axes=axes, artists=artists)

    # ========================================================================
    # 翻译：计划里的标准写法 / 色带位置 → Plotly 原生值（对照 matplotlib 后端）
    # ========================================================================

    def _curve_color(self, curve: CurveSpec, preset: LayoutPreset) -> str | None:
        """
        一条线的最终颜色（颜色一次赋值；对照 MatplotlibBackend._curve_color）。优先级：
        分组写的颜色 > 色带位置 > 排版预设里这根轴的颜色 > Plotly 默认配色（返回 None）。
        """
        # translate_color / sample_colorscale 的返回类型标注较宽（含 matplotlib 用的元组），到 Plotly 实际总是字符串
        if 'color' in curve.style:
            return cast(str, translate_color(curve.style['color'], 'plotly'))
        if curve.color_position is not None:
            return cast(str, plyc.sample_colorscale(self.cmap, [curve.color_position])[0])
        if axis_color := preset.axis_colors.get('y' if curve.axis == 'left' else 'y2'):
            return cast(str, translate_color(axis_color, 'plotly'))
        return None

    def _native_style(self, style: dict) -> dict:
        """
        分组写了的线型、标记（标准写法）→ trace 属性，交给 trace.update(...)。颜色画线时已给。
        写了 marker 时折线要改成 'lines+markers' 才显示点（matplotlib 不需要这一步）。
        """
        native = {}
        if 'linestyle' in style:
            native['line_dash'] = translate_linestyle(style['linestyle'], 'plotly', linewidth=self.line_width)
        if 'marker' in style:
            native['marker_symbol'] = translate_marker(style['marker'], 'plotly')
            native['mode'] = 'lines+markers'
        return native

    # ========================================================================
    # 渲染：画线
    # ========================================================================

    @staticmethod
    def _plot_data(fig: go.Figure, x, y, plot_kind: str = 'line', **kwargs):
        """按 plot_kind 添加一条图形，返回 Figure 中实际保存的 trace。"""
        match plot_kind:
            case 'line':
                trace = go.Scatter(x=x, y=y, mode='lines', **kwargs)
            case 'scatter':
                trace = go.Scatter(x=x, y=y, mode='markers', **kwargs)
            case 'bar':
                trace = go.Bar(x=x, y=y, **kwargs)
            case _:
                raise ValueError(f"不支持的 plot_kind: '{plot_kind}'")
        fig.add_trace(trace)
        return fig.data[-1]

    # ========================================================================
    # 渲染：按排版预设排版（对照 MatplotlibBackend._apply_layout）
    # ========================================================================

    @staticmethod
    def _apply_layout(fig: go.Figure, axes: dict, spec: FigureSpec, preset: LayoutPreset):
        """
        按排版预设设置图例、轴标题、刻度格式、轴着色（值的翻译在翻译层 style.translate_*）。
        预设里的 margins 不用：Plotly 会自动给图外的图例留边；legend_draggable 不用：Plotly 的图例不能拖动。
        """
        fig.update_layout(
            legend=translate_legend(preset.legend, 'plotly'),
            xaxis_title_text=spec.x_unit,
            yaxis_title_text=spec.y_unit,
        )
        if 'right' in axes:
            # 右轴叠在左轴上、放在右侧，与左轴共用 X 轴（对应 matplotlib 的 twinx）
            fig.update_layout(yaxis2=dict(overlaying='y', side='right', title_text=spec.y2_unit))

        for axis_name, fmt in preset.tick_formats.items():
            fig.update_layout({_LAYOUT_AXIS[axis_name]: dict(tickformat=translate_tick_format(fmt, 'plotly'))})

        # 轴着色：标题、刻度（线和文字）、轴线同色
        for axis_name, color in preset.axis_colors.items():
            native = translate_color(color, 'plotly')
            fig.update_layout({_LAYOUT_AXIS[axis_name]: dict(
                title_font_color=native, tickfont_color=native, tickcolor=native, linecolor=native)})

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
        字号、线宽、刻度宽来自 Appearance（磅 → 像素）；颜色、刻度长度、网格等是 Plotly 一侧的固定风格。
        模板里的 xaxis / yaxis 设置对所有 X / Y 轴生效（含右轴 yaxis2）。
        """
        font_size = px(appearance.font_size)
        axis_width = px(appearance.axis_width)
        tick_width = px(appearance.tick_width)
        axis_style = dict(
            title_font_size=font_size,
            title_font_weight=appearance.font_weight,
            showline=True, linewidth=axis_width, linecolor='black', mirror=False,
            ticks='outside', tickwidth=tick_width, ticklen=6, tickcolor='black',
            minor_ticks='outside', minor_tickwidth=tick_width, minor_ticklen=3, minor_showgrid=False,
            # 对数轴 10^n 之间的 2、5 等标签：默认是小号数字，与主标签大小不一致，不显示。
            minorloglabels='none',
            showgrid=False, zeroline=False, automargin=True,
        )
        line_width = px(appearance.line_width)
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
                legend_font_size=px(appearance.legend_font_size),
                legend_borderwidth=0,
                legend_bgcolor='rgba(0,0,0,0)',
            ),
            data=dict(
                # 列表中的一项是一套默认样式，不是图中的第一条曲线；不指定颜色，让不同样品保留各自的配色。
                scatter=[go.Scatter(
                    line_width=line_width,
                    line_dash=translate_linestyle(appearance.linestyle, 'plotly', linewidth=line_width),
                    marker_size=8,
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
                   slider_formatter: Callable[[go.layout.Slider], object] | None = None) -> go.Figure:
        """
        给一张图加控制曲线显示的滑块，原地修改并返回这张图。
        mode：'single' 每档只显示当前曲线；'cumulative' 每档显示第一条到当前曲线。
        slider_formatter：接收安装后的 Slider 并原地修改，在默认外观之后执行。
        """
        if mode not in ('single', 'cumulative'):
            raise ValueError(f"不支持的 mode: '{mode}'")
        # Plotly 的 data 类型标注较宽，在此明确它是 trace 元组；cast 不复制对象
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)
        if not traces:
            raise RuntimeError("图中没有曲线，无法添加滑块")
        for i, trace in enumerate(traces):
            trace.visible = (i == 0)

        visible = {
            'single':     lambda i: [i == j for j in range(len(traces))],
            'cumulative': lambda i: [j <= i for j in range(len(traces))],
        }[mode]
        steps = [dict(method='update', label=trace.name or str(i),
                      args=[{'visible': visible(i)}, {'title': {'text': trace.name or str(i)}}])
                 for i, trace in enumerate(traces)]

        # 初始标题与第 0 档一致；否则拖动前没有标题
        fig.update_layout(sliders=[go.layout.Slider(active=0, steps=steps)], title_text=steps[0]['label'])
        # 操作安装后的 Slider；Plotly 可能复制传入的原始对象
        installed = cast(tuple[go.layout.Slider, ...], cast(go.Layout, fig.layout).sliders)[0]
        labels = [cast(str, step['label']) for step in steps]
        self._apply_slider_format(installed, show_labels=self._slider_labels_fit(fig, labels))
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

    def _apply_slider_format(self, slider: go.layout.Slider, show_labels: bool = True):
        """原地设置整个滑块的默认外观。show_labels 为 False 时档位标签透明（仍占位），名称由当前值和标题显示。"""
        slider.update(
            # 当前值：轨道左上方显示当前曲线名
            currentvalue_prefix='Trace: ', currentvalue_font_size=20, currentvalue_font_color='black',
            currentvalue_xanchor='left', currentvalue_offset=14,
            # 档位标签与刻度：细刻度，避免一排粗黑线
            font_size=self._SLIDER_FONT_SIZE, font_color='black' if show_labels else 'rgba(0,0,0,0)',
            ticklen=5, tickwidth=1, tickcolor='#555555', minorticklen=3,
            # 位置：与绘图区等宽；pad_t 让出 X 轴刻度文字和轴标题的高度
            x=0, xanchor='left', len=1, lenmode='fraction', pad_t=110, pad_b=10, pad_l=0, pad_r=0,
            # 轨道与拖动块：浅灰细边框
            bgcolor='#f2f2f2', activebgcolor='#bdbdbd', bordercolor='#9e9e9e', borderwidth=1,
        )
