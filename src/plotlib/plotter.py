"""
科学数据绘图模块：DataPlotter 是唯一的绘图入口（STRUCTURE_REVIEW 6.6；2026-11-20 统一命名）。

只做三件事：生成绘图计划（plan.plan_*）→ 交给后端画（backends，backend.draw）→ 存结果（self.figures）。
这里不碰任何绘图库；画图的代码全在 backends/。
命名与计划层、Appearance、GLOSSARY 一致：通道 channel_*、负对数 neglog_*、方法名「plot_ + 版式」。
"""
from collections.abc import Callable
from typing import Any

from .backends import get_backend
from .dataset import DataSet
from .group import Group
from .plan import plan_dual_y_figures, plan_multiline_figures, plan_xy_figures, resolve_groups
from .plot_spec import Appearance, AxesFormatter, CurveKind, DrawnFigure, FigureSpec

# 整图回调：整张图画完、各轴回调之后调用一次，拿到图和全部坐标轴 {'left': ..., 'right': ...}
type FigureFormatter = Callable[[Any, dict[str, Any]], Any]


class DataPlotter:
    """
    科学数据绘图器：一个入口、两个后端（matplotlib 静态图 / Plotly 交互图）。

    绘图方法（方法名 = plot_ + 版式；都先生成绘图计划，再交给后端画）
    --------
    plot_multiline()
        多线图：所有样品画在同一坐标系，每个样品一条线。
    plot_groups()
        分组绘图：分离模式每组一张图，合并模式所有分组一张图。
    plot_xy()
        x-y 单线图：每个样品一张图，画两个通道的关系（如 Nyquist 图）。
    plot_dual_y()
        双 Y 轴图：每个样品一张图，左右两根 Y 轴共用 X 轴。

    绘图结果统一存入 self.figures = {计划的 key: DrawnFigure}（每次调用前清空），取线用 figures[key].artist(样品号)。

    格式化
    ------
    所有绘图方法支持三类按轴的回调和一个整图回调（matplotlib 收原生对象，Plotly 都收 fig）：

    - axes_formatter(ax, fig)     : 坐标轴（Plotly：axes_formatter(fig)）
    - lines_formatter(lines)      : 线条（Plotly：lines_formatter(fig)）
    - legend_formatter(legends)   : 图例（Plotly：legend_formatter(fig)）
    - figure_formatter(fig, axes) : 整图，axes = {'left': ..., 'right': ...}（Plotly 是配置里的轴名）

    顺序：默认排版 → 各轴回调 → 整图回调 → 负对数刻度。

    使用示例
    --------
    >>> plotter = DataPlotter(dataset, channel_x=0, channel_y=1)
    >>> plotter.plot_multiline(neglog_y=True)
    >>> import matplotlib.pyplot as plt; plt.show()
    """

    def __init__(
        self,
        dataset: DataSet,
        groups: Group | None = None,
        cmap: str | None = None,
        font_family: str = 'Arial',
        font_size: int = 22,
        font_weight: str = 'bold',
        line_width: float = 3,
        axis_width: float = 3,
        linestyle: str | tuple = 'solid',
        plotrange: int | None = None,
        channel_x: int = 0,
        channel_y: int = 1,
        legend_font_size: int = 10,
        tick_width: float = 3,
        figsize: tuple[float, float] | None = None,
        dpi: float = 100,
        backend: str = 'matplotlib',
    ):
        """
        初始化绘图器。

        Parameters
        ----------
        dataset : DataSet
            要画的数据集。
        groups : Group, optional
            分组对象，包含各组的样品号及配置；必须建在 dataset 上。
            不接受字典：请先用 Group(dataset, config) 创建。None 表示不分组。
        cmap : str, optional
            色带名，由后端解析（matplotlib 默认 'plasma'）。
        font_family, font_size, font_weight :
            字体、字号（磅）、字重。
        line_width, axis_width, tick_width :
            线宽、坐标轴线宽、刻度线宽（磅）。
        linestyle : str or tuple
            默认线型，标准写法（style.py）：'solid'、'dash'、'dot'、'dashdot'，
            或自定义虚线 (实线长, 空白长, ...)。分组没写 linestyle 时也用它。
        plotrange : int, optional
            绘制的数据点数，None 表示全部。
        channel_x, channel_y : int
            X、Y 轴数据的通道号（样品内的列序号）。plot_xy 不传通道时也用它们。
        legend_font_size : int
            图例字号（磅）。
        figsize : tuple, optional
            图尺寸（宽, 高），单位英寸，对本绘图器的所有绘图方法生效。
            None 时各方法用各自的默认值：plot_multiline 为 (10, 8)，plot_groups 为 (16, 12)，
            plot_xy、plot_dual_y 为 (12, 8)。
        dpi : float
            渲染分辨率（每英寸像素数，默认 100）。后端按它把字号、线宽（磅）和 figsize（英寸）换成实际大小。
        backend : str
            绘图后端：'matplotlib'（默认，静态图）或 'plotly'（交互图）。
        """
        groups = resolve_groups(groups, dataset)

        # 外观参数打包成后端无关的 Appearance，由后端翻译（matplotlib → rc_params，Plotly → 模板）；
        # 非标准写法的 linestyle 在这里创建后端时就报错
        appearance = Appearance(font_family=font_family, font_size=font_size, font_weight=font_weight,
                                line_width=line_width, axis_width=axis_width, linestyle=linestyle,
                                legend_font_size=legend_font_size, tick_width=tick_width, dpi=dpi)
        self.backend = get_backend(backend, appearance, cmap)

        self.dataset: DataSet = dataset
        self.groups = groups  # 只读：通过 names / sample_ids / options 读取，不修改
        # 绘图结果：{计划的 key: DrawnFigure}，四种绘图方法同一形状
        self.figures: dict[str | int, DrawnFigure] = {}
        self.plotrange = plotrange
        self.channel_x = channel_x
        self.channel_y = channel_y
        self.figsize = figsize  # None：各绘图方法用自己的默认尺寸

    # ========================================================================
    # 交给后端：入口里唯一和后端打交道的地方
    # ========================================================================

    def _render(self, specs: list[FigureSpec], figsize: tuple,
                formatters: dict[str, AxesFormatter],
                figure_formatter: FigureFormatter | None = None) -> DataPlotter:
        """
        把计划逐张交给后端画，结果存进 self.figures = {计划的 key: DrawnFigure}（每次调用前清空）。
        画图的事（建图、画线、排版、formatter、neglog）全在后端：self.backend.draw。
        """
        self.figures = {spec.key: self.backend.draw(spec, figsize, formatters, figure_formatter)
                        for spec in specs}
        return self

    # ========================================================================
    # 交互：画完之后的可选操作（只有支持它的后端有）
    # ========================================================================

    def add_slider(self, mode: str = 'cumulative', slider_formatter=None):
        """
        给刚画好的图加控制曲线显示的滑块，返回这张图（Plotly 的 go.Figure，可直接交给 html_export）。

        只有 Plotly 后端有滑块（BACKEND_PLAN 原则 3：滑块是画完之后的可选交互）；
        只能用于只有一张图的结果（plot_multiline、合并模式的 plot_groups）。
        mode：'single' 每档只显示当前曲线；'cumulative'（默认）每档显示第一条到当前曲线。
        slider_formatter：接收安装后的 Slider 并原地修改，在默认外观之后执行。
        """
        # 不是每个后端都有滑块：按「有没有这个能力」判断，而不是按后端名字（以后加别的交互后端也适用）
        add_slider = getattr(self.backend, 'add_slider', None)
        if add_slider is None:
            raise NotImplementedError(f"滑块只有 Plotly 后端有，当前后端是 {self.backend.name!r}；"
                                      f"请用 DataPlotter(..., backend='plotly')")
        if not self.figures:
            raise RuntimeError("请先调用绘图方法，再添加滑块")
        if len(self.figures) != 1:
            raise RuntimeError(f"滑块只能加在一张图上，当前有 {len(self.figures)} 张"
                               f"（xy、双 Y 轴、分组分离模式会画出多张图；按组翻页见 STRUCTURE_REVIEW 6.8）")
        [drawn] = self.figures.values()
        return add_slider(drawn.fig, mode, slider_formatter)

    # ========================================================================
    # 绘图方法：计划 → 打包回调 → _render
    # ========================================================================

    def plot_multiline(self,
                       axes_formatter=None,
                       lines_formatter=None,
                       legend_formatter=None,
                       neglog_x: bool = False,
                       neglog_y: bool = False,
                       plot_kind: CurveKind = 'line',
                       figure_formatter: FigureFormatter | None = None,
                       ) -> DataPlotter:
        """
        多线图：所有样品画在同一坐标系，每个样品一条线（原 plot_objects）。

        Parameters
        ----------
        axes_formatter, lines_formatter, legend_formatter : callable, optional
            用户回调，见类说明。
        neglog_x, neglog_y : bool
            负对数：数据取绝对值后画，刻度文字补负号。
        plot_kind : str
            画法：'line' / 'scatter' / 'bar'。
        figure_formatter : callable, optional
            整图回调 (fig, axes)。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。figures = {'main': DrawnFigure}
        """
        # 不分组（groups=None）：一张 'main' 图，全部样品；不看 self.groups
        specs = plan_multiline_figures(self.dataset, None, self.channel_x, self.channel_y,
                                       plotrange=self.plotrange, neglog_x=neglog_x, neglog_y=neglog_y,
                                       kind=plot_kind)
        formatters = {'left': AxesFormatter(axes_formatter, lines_formatter, legend_formatter)}
        return self._render(specs, self.figsize or (10, 8), formatters, figure_formatter)

    def plot_groups(self,
                    neglog_x: bool = False,
                    neglog_y: bool = False,
                    axes_formatter=None,
                    lines_formatter=None,
                    legend_formatter=None,
                    merge_groups: bool = False,
                    plot_kind: CurveKind = 'line',
                    figure_formatter: FigureFormatter | None = None,
                    ) -> DataPlotter:
        """
        分组绘图：按 self.groups（Group 对象）分组画（原 group_plotter）。

        Parameters
        ----------
        merge_groups : bool
            True：所有组合并到一张图；False：每组单独一张图。
            合并模式下，被多个组引用的样品只画一次，使用第一个包含它的组的样式。
        其余参数同 plot_multiline。

        分组样式
        --------
        分组配置里写了 linestyle / marker / color 就应用（两种模式一样）；linestyle / marker 仅 plot_kind='line'，
        color 对所有 plot_kind 生效，写了时这组所有样品都用它。没写时：线型用 linestyle；
        颜色在分离模式按样品配色，合并模式统一为组首色。优先级：默认样式 < 分组样式 < lines_formatter。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
            分离模式：figures = {组名: DrawnFigure}；合并模式：figures = {'main': DrawnFigure}
        """
        if not self.groups.names:
            return self.plot_multiline(
                plot_kind=plot_kind, neglog_x=neglog_x, neglog_y=neglog_y,
                axes_formatter=axes_formatter, lines_formatter=lines_formatter,
                legend_formatter=legend_formatter, figure_formatter=figure_formatter,
            )

        # 分组规则（去重、先到先得、组首色、样式归属）都在计划里；合并模式的计划只有一张 'main' 图，
        # 所以两种模式走同一个 _render
        specs = plan_multiline_figures(self.dataset, self.groups, self.channel_x, self.channel_y,
                                       merge_groups=merge_groups, plotrange=self.plotrange,
                                       neglog_x=neglog_x, neglog_y=neglog_y, kind=plot_kind)
        formatters = {'left': AxesFormatter(axes_formatter, lines_formatter, legend_formatter)}
        return self._render(specs, self.figsize or (16, 12), formatters, figure_formatter)

    def plot_xy(self,
                axes_formatter=None,
                lines_formatter=None,
                legend_formatter=None,
                plot_kind: CurveKind = 'line',
                neglog_x: bool = False,
                neglog_y: bool = False,
                channel_x: int | None = None,
                channel_y: int | None = None,
                figure_formatter: FigureFormatter | None = None,
                ) -> DataPlotter:
        """
        x-y 单线图：每个样品一张图、一条线，画两个通道的关系（如 Nyquist 图：Zs' 对 Zs''；原 subplotter_yy / subplotter_xy）。
        一张图只有一条线，不按样品换色，用后端默认色。

        Parameters
        ----------
        channel_x, channel_y : int, optional
            横轴、纵轴的通道号；不传时用构造时的 channel_x、channel_y。
        其余参数同 plot_multiline。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。figures = {样品号: DrawnFigure}；取线用 figures[样品号].artist(样品号)
        """
        specs = plan_xy_figures(self.dataset,
                                self.channel_x if channel_x is None else channel_x,
                                self.channel_y if channel_y is None else channel_y,
                                plotrange=self.plotrange, neglog_x=neglog_x, neglog_y=neglog_y, kind=plot_kind)
        formatters = {'left': AxesFormatter(axes_formatter, lines_formatter, legend_formatter)}
        return self._render(specs, self.figsize or (12, 8), formatters, figure_formatter)

    def plot_dual_y(self,
                    left: tuple[int, int] = (0, 1),
                    right: tuple[int, int] = (2, 3),
                    axes_formatter=None,
                    lines_formatter=None,
                    legend_formatter=None,
                    right_axes_formatter=None,
                    right_lines_formatter=None,
                    right_legend_formatter=None,
                    neglog_x: bool = False,
                    neglog_y: bool = False,
                    neglog_x2: bool = False,
                    neglog_y2: bool = False,
                    plot_kinds: tuple[CurveKind, CurveKind] = ('line', 'line'),
                    figure_formatter: FigureFormatter | None = None,
                    ) -> DataPlotter:
        """
        双 Y 轴图：每个样品一张图，左线挂左轴、右线挂右轴，共用 X 轴（原 subplotter_xyy）。
        左红右蓝（排版预设）；X 轴标题取左侧 X 通道的单位。

        Parameters
        ----------
        left, right : (int, int)
            左线、右线的 (X 通道, Y 通道)。
        axes_formatter, lines_formatter, legend_formatter : callable, optional
            左轴的回调；right_axes_formatter 等是右轴的回调。
        neglog_x, neglog_y, neglog_x2, neglog_y2 : bool
            左线的 X、Y 与右线的 X、Y 是否按负对数画（右线的 X 与左轴共用，只取绝对值）。
        plot_kinds : (str, str)
            左线、右线的画法。
        figure_formatter : callable, optional
            整图回调 (fig, axes)，axes = {'left': 左轴, 'right': 右轴}，可同时调整两根轴。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。figures = {样品号: DrawnFigure}；
            左线 figures[样品号].artist(样品号)，右线 .artist(样品号, 'right')；坐标轴 .axes['left'] / .axes['right']
        """
        specs = plan_dual_y_figures(
            self.dataset, left=left, right=right, plotrange=self.plotrange,
            neglog_x=neglog_x, neglog_y=neglog_y, neglog_x2=neglog_x2, neglog_y2=neglog_y2,
            kinds=plot_kinds,
        )
        # 每根轴一组回调
        formatters = {
            'left':  AxesFormatter(axes_formatter, lines_formatter, legend_formatter),
            'right': AxesFormatter(right_axes_formatter, right_lines_formatter, right_legend_formatter),
        }
        return self._render(specs, self.figsize or (12, 8), formatters, figure_formatter)
