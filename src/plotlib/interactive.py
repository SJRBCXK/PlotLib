"""交互绘图学习模块：先迁移 DataPlotter 的数据侧结构。"""
from collections.abc import Callable
from typing import Literal, Self, cast

import plotly.graph_objects as go
from .group import Group
from .dataset import DataSet
from .plot_common import color_positions, get_xy_data, resolve_groups
import plotly.colors as plyc

# 滑块模式：single 每档只显示一条曲线；cumulative 每档累加显示到当前曲线。
# Literal 让编辑器补全可选值、标出错误输入；运行时仍由 add_slider 校验。
type SliderMode = Literal["single", "cumulative"]




class InteractivePlotter:
    """沿用 DataPlotter 的数据准备方式，绘图与格式化部分逐步手动迁移。"""

    _SLIDER_FONT_SIZE = 16  # 滑块档位标签字号；也用于估算标签是否放得下

    def __init__(
        self,
        input_dataset: DataSet,
        plotrange: int | None = None,
        plotdataRowNum_x: int = 0,
        plotdataRowNum_y: int = 1,
        cmap: str | None = None,
        groups: Group | None = None,
    ):
        """初始化数据侧状态，不创建图形、不配置样式。

        plotrange 为 None 时使用全部行；X/Y 索引均为通道号（样品内的列序号）。
        groups 与 DataPlotter 的约定相同：只接受基于 input_dataset 创建的 Group 对象，
        None 表示不分组（空 Group）。目前只保存，分组绘图见 STRUCTURE_REVIEW 步骤 6.3。
        """
        # 三种情况的检查与 DataPlotter 共用（plot_common.resolve_groups）
        groups = resolve_groups(groups, input_dataset)

        resolved_cmap = plyc.get_colorscale('Plasma' if cmap is None else cmap)
        

        # 数据与选择设置：与 DataPlotter 保持对应，方便后续比较和合并。
        self.dataset: DataSet = input_dataset
        self.groups = groups  # 只读：通过 names / sample_ids / linestyle 等接口读取，不修改
        self.data = self.dataset.data
        self.sample_idx = self.dataset.sample_idx
        self.column = self.dataset.column
        # 与 DataPlotter 共用同一套「样品号 → 色带位置」，两个后端的配色一致
        self.color_positions = color_positions(self.sample_idx)
        self.plotrange = plotrange
        self.plotdataRowNum_x = plotdataRowNum_x
        self.plotdataRowNum_y = plotdataRowNum_y
        self.template: go.layout.Template | None = None
        self.cmap = resolved_cmap
        # 只预留结果容器；此处不实现绘图或格式化。
        self.plot_artists: list = []
        self.axesset: dict = {}
        self.asset: go.Figure | None = None

    # 取数（按样品号 + 通道号取 X、Y）与 DataPlotter 共用：plot_common.get_xy_data

    def _get_color(self, sample: int):
        """返回样品在色带上对应位置的颜色（只取这一个位置）。"""
        return plyc.sample_colorscale(self.cmap, [self.color_positions[sample]])[0]

    

    # 外观：模板提供通用默认值，layout 配置本次图，不照搬“线 / 轴 / 图”分类。
    def _create_template(self) -> go.layout.Template:
        """创建通用外观模板，不设置轴标题文字、数据范围或滑块。

        layout 管字体、坐标轴和图例；data 管各类 trace 的默认外观。
        创建 Figure 时通过 layout.template 应用，不修改全局默认模板。
        图或 trace 上显式设置的属性会覆盖这里的默认值。
        """
        template = go.layout.Template(
            layout=go.Layout(
                # 全局字体、背景与边距。
                font_family="Arial",
                font_size=24,
                font_color="black",
                font_weight="bold",
                paper_bgcolor="white",
                plot_bgcolor="white",
                # 顶部留出标题位置；滑块会把标题改成当前曲线名。
                margin=dict(l=40, r=40, t=80, b=40),
                title_x=0.5,
                title_xanchor="center",
                title_font_size=24,

                # X 轴：下划线表示属性层级，如 xaxis.title.font.size。
                xaxis_title_font_size=24,
                xaxis_title_font_weight="bold",
                xaxis_showline=True,
                xaxis_linewidth=3,
                xaxis_linecolor="black",
                xaxis_mirror=False,
                xaxis_ticks="outside",
                xaxis_tickwidth=3,
                xaxis_ticklen=6,
                xaxis_tickcolor="black",
                xaxis_minor_ticks="outside",
                xaxis_minor_tickwidth=3,
                xaxis_minor_ticklen=3,
                xaxis_minor_showgrid=False,
                # 对数轴 10^n 之间的 2、5 等标签：默认是小号数字，与主标签大小不一致，不显示。
                xaxis_minorloglabels="none",
                xaxis_showgrid=False,
                xaxis_zeroline=False,
                xaxis_automargin=True,

                # Y 轴。
                yaxis_title_font_size=24,
                yaxis_title_font_weight="bold",
                yaxis_showline=True,
                yaxis_linewidth=3,
                yaxis_linecolor="black",
                yaxis_mirror=False,
                yaxis_ticks="outside",
                yaxis_tickwidth=3,
                yaxis_ticklen=6,
                yaxis_tickcolor="black",
                yaxis_minor_ticks="outside",
                yaxis_minor_tickwidth=3,
                yaxis_minor_ticklen=3,
                yaxis_minor_showgrid=False,
                yaxis_minorloglabels="none",
                yaxis_showgrid=False,
                yaxis_zeroline=False,
                yaxis_automargin=True,

                # 图例。
                legend_font_size=18,
                legend_borderwidth=0,
                legend_bgcolor="rgba(0,0,0,0)",

                #画布
                width=1200,
                height=800,

            ),
            data=dict(
                # 列表中的一项是一套默认样式，不是图中的第一条曲线。
                # 不指定颜色，让不同样品保留各自的配色。
                scatter=[
                    go.Scatter(
                        line_width=3,
                        line_dash="solid",
                        marker_size=8,
                        marker_symbol="circle",
                        connectgaps=False,
                    ),
                ],
                bar=[
                    go.Bar(marker_line_width=0),
                ],
            ),
        )
        self.template = template
        return template

    def _apply_layout(self, fig: go.Figure, x_unit: str, y_unit: str, **layout_options):
        """设置轴标题，以及需要时的尺度、范围；不取数、不添加曲线或滑块。"""
        fig.update_layout(
            xaxis_title= x_unit,
            yaxis_title= y_unit,
        )

        fig.update_layout(**layout_options)

    def _slider_labels_fit(self, fig: go.Figure, labels: list[str], font_size: float) -> bool:
        """粗略估计档位标签能否并排放下（不重叠）。

        Plotly 自带的标签抽稀对长标签不可靠，会互相压住，所以由这里预判。
        宽度按“字号 × 0.65 × 字符数”估算（粗体 Arial），只用于决定显示或隐藏。
        """
        if len(labels) <= 1:
            return True
        # Plotly 属性的类型标注过宽，cast 只告诉检查器实际类型，不改变运行时对象。
        layout = cast(go.Layout, fig.layout)
        template_layout = cast(go.Layout, self.template.layout) if self.template else None
        width = cast(
            float,
            layout.width or (template_layout.width if template_layout else None) or 700,
        )
        spacing = width * 0.9 / (len(labels) - 1)
        return font_size * 0.65 * max(len(label) for label in labels) <= spacing

    def _apply_slider_format(
        self,
        slider: go.layout.Slider,
        show_labels: bool = True,
        **slider_options,
    ):
        """原地设置整个滑块的默认外观，再应用用户覆盖。

        show_labels 为 False 时档位标签透明（仍占位），名称由当前值和标题显示。
        """
        slider.update(
            # 当前值：轨道左上方显示当前曲线名。
            currentvalue_prefix="Trace: ",
            currentvalue_font_size=20,
            currentvalue_font_color="black",
            currentvalue_xanchor="left",
            currentvalue_offset=14,

            # 档位标签与刻度：细刻度，避免一排粗黑线。
            font_size=self._SLIDER_FONT_SIZE,
            font_color="black" if show_labels else "rgba(0,0,0,0)",
            ticklen=5,
            tickwidth=1,
            tickcolor="#555555",
            minorticklen=3,

            # 位置：与绘图区等宽；pad_t 让出 X 轴刻度文字和轴标题的高度。
            x=0,
            xanchor="left",
            len=1,
            lenmode="fraction",
            pad_t=110,
            pad_b=10,
            pad_l=0,
            pad_r=0,

            # 轨道与拖动块：浅灰细边框。
            bgcolor="#f2f2f2",
            activebgcolor="#bdbdbd",
            bordercolor="#9e9e9e",
            borderwidth=1,
        )

        slider.update(**slider_options)

        return slider



    def _plot_data_plotly(
        self,
        fig: go.Figure,
        x,
        y,
        plot_kind: str = "line",
        **kwargs,
    ):
        """按 plot_kind 添加一条图形，返回 Figure 中实际保存的 trace。"""
        match plot_kind:
            case "line":
                trace = go.Scatter(x=x, y=y, mode="lines", **kwargs)
            case "scatter":
                trace = go.Scatter(x=x, y=y, mode="markers", **kwargs)
            case "bar":
                trace = go.Bar(x=x, y=y, **kwargs)
            case _:
                raise ValueError(f"不支持的 plot_kind: '{plot_kind}'")

        fig.add_trace(trace)
        return fig.data[-1]


 

    def plot_plotly_object(
        self,
        figure_formatter: Callable[[go.Figure], object] | None = None,
    ) -> Self:
        """把数据集中每个样品绘制为一条曲线，全部可见。

        Args:
            figure_formatter: 可选格式回调，接收 Figure 并原地修改；在默认格式之后执行，可覆盖默认值。例如 make_axes_formatter(backend="plotly", xscale_type="log")。

        Returns:
            self，可继续链式调用 add_slider()；Figure 保存在 self.asset。

        Example:
            fig = plot.plot_plotly_object(figure_formatter=fmt).add_slider("single")
            fig.show()
        """
        # 流程：
        # ① 检查数据。
        # ② 用 _create_template() 的模板创建 Figure。
        # ③ 遍历样品号，用 get_xy_data() 取 X/Y 和标签、单位。
        # ④ 用 _plot_data_plotly() 添加曲线，同时传入 name 等身份信息。
        # ⑤ 用 _apply_layout() 设置本次图；各样品的轴单位应一致。
        # ⑥ 应用可选的用户格式回调，保存到 self.asset 并返回 self。不在这里 show()。
        sample_ids = sorted(set(self.sample_idx))
        if not sample_ids or self.data.size == 0:
            raise RuntimeError("数据集为空，无法绘图")
        fig = go.Figure(
            layout = dict(template=self._create_template())
        )
        artists = []

        for i in sample_ids:
            Row_x, Row_y, _, y_label, x_unit, y_unit = get_xy_data(self.dataset, plotrange=self.plotrange,
                    sample_idx=i,
                    channel_x=self.plotdataRowNum_x,
                    channel_y=self.plotdataRowNum_y,
                )

            color = self._get_color(i)
            
            artist = self._plot_data_plotly(
                fig, Row_x, Row_y, name=y_label, line=dict(color=color))
            artists.append(artist)

        self._apply_layout(fig, x_unit, y_unit)
        # 用户回调原地修改 Figure，覆盖默认格式。
        if figure_formatter is not None:
            figure_formatter(fig)

        self.plot_artists = artists
        self.asset = fig
        return self





    def add_slider(
        self,
        mode: SliderMode = "cumulative",
        slider_formatter: Callable[[go.layout.Slider], object] | None = None,
    ) -> go.Figure:
        """给当前图添加控制曲线显示的滑块；需先调用 plot_plotly_object()。

        Args:
            mode: "single" 每档只显示当前曲线（逐条查看）；"cumulative" 每档显示第一条到当前曲线（观察累加变化）。默认 "cumulative"。
            slider_formatter: 可选格式回调，接收 Figure 中实际保存的 Slider 并原地修改；在默认滑块外观之后执行。例如 lambda s: s.update(currentvalue_prefix="Group: ")。档位标签放不下时默认隐藏，可用 lambda s: s.update(font_color="black") 强制显示。

        Returns:
            添加滑块后的 Figure（即 self.asset）。

        Raises:
            RuntimeError: 尚未绘图，或图中没有曲线。
            ValueError: mode 不是 "single" 或 "cumulative"。
        """
        fig = self.asset
        if fig is None:
            raise RuntimeError("请先调用绘图方法，再添加滑块")
        if mode not in ("single", "cumulative"):
            raise ValueError(f"不支持的 mode: '{mode}'")

        # 当前绘图入口只创建 Scatter / Bar。Plotly 的 data 类型标注较宽，
        # 在此明确它是 trace 元组；cast 不复制对象，也不改变运行时数据。
        traces = cast(tuple[go.Scatter | go.Bar, ...], fig.data)
        if not traces:
            raise RuntimeError("图中没有曲线，无法添加滑块")
        for i, trace in enumerate(traces):
            trace.visible = (i == 0)

        steps = []

        match mode:
            case "single":
                for i, trace in enumerate(traces):
                    step = dict(
                        method="update",
                        label=trace.name or str(i),
                        args=[{"visible": [i == j for j in range(len(traces))]},
                              {"title": {"text": trace.name or str(i)}}],
                    )
                    steps.append(step)
            case "cumulative":
                for i, trace in enumerate(traces):
                    step = dict(
                        method="update",
                        label=trace.name or str(i),
                        args=[{"visible": [j <= i for j in range(len(traces))]},
                              {"title": { "text": trace.name or str(i)}}],
                    )
                    steps.append(step)

        # steps 描述各档位的行为；formatter 操作的是整个 Slider，不是 step。
        slider = go.layout.Slider(
            active=0,
            steps=steps,
        )
        # 初始标题与第 0 档一致；否则拖动前没有标题。
        fig.update_layout(sliders=[slider], title_text=steps[0]["label"])
        labels = [step["label"] for step in steps]
        # 操作安装后的 Slider；Plotly 可能复制传入的原始对象。
        sliders = cast(tuple[go.layout.Slider, ...], cast(go.Layout, fig.layout).sliders)
        installed = sliders[0]
        self._apply_slider_format(
            installed,
            show_labels=self._slider_labels_fit(fig, labels, self._SLIDER_FONT_SIZE),
        )
        if slider_formatter is not None:
            slider_formatter(installed)
        self.asset = fig
        
        return self.asset