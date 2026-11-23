"""
绘图入口：`DataPlotter` 是用户画图唯一需要的类。

每个绘图方法只做三件事：生成绘图计划（`plotlib.plan`）→ 交给后端画（`plotlib.backends`）→
把结果存进 ``DataPlotter.figures``。本模块不碰任何绘图库，画图的代码全在后端里。
"""
from collections.abc import Callable
from typing import Any

from .backends import get_backend
from .dataset import DataSet
from .group import Group
from .plan import plan_dual_y_figures, plan_multiline_figures, plan_xy_figures, resolve_groups
from .plot_spec import (Appearance, AxesFormatter, CurveKind, DrawnFigure, FigureSpec, FrameStyle, LegendStyle,
                        LineStyle, TickStyle)

# 整图回调：整张图画完、各轴回调之后调用一次，拿到图和全部坐标轴 {'left': ..., 'right': ...}
type FigureFormatter = Callable[[Any, dict[str, Any]], Any]


class DataPlotter:
    """
    科学数据绘图器：一个入口、两个后端（matplotlib 静态图 / Plotly 交互图）。

    四个绘图方法的名字是 ``plot_`` 加版式：

    - `plot_multiline`：所有样品画在同一坐标系，每个样品一条线；
    - `plot_groups`：按分组画，分离模式每组一张图，合并模式所有分组一张图；
    - `plot_xy`：每个样品一张图，画两个通道的关系（如 Nyquist 图）；
    - `plot_dual_y`：每个样品一张图，左右两根 Y 轴共用 X 轴。

    每次调用绘图方法都会清空并重新填写 `figures`：``{计划的 key: DrawnFigure}``，
    四种方法的结果形状相同。绘图方法都返回 ``self``，可以链式调用。

    Attributes
    ----------
    figures : dict
        ``{计划的 key: DrawnFigure}``，最近一次绘图的结果。取线用 ``figures[key].artist(样品号)``。
    dataset : DataSet
        绘图用的数据集。
    groups : Group
        分组；不分组时是空 `Group`。
    backend : MatplotlibBackend or PlotlyBackend
        实际画图的后端对象。

    Notes
    -----
    **格式化回调。** 每个绘图方法都接受三类按轴的回调和一个整图回调。按轴回调由后端逐轴调用，
    只拿到这根轴自己的东西；两个后端的调用形状一一对应：

    - ``axes_formatter``：matplotlib 以 ``(ax, fig)`` 调用，Plotly 以 ``(轴名, fig)`` 调用，如 ``('yaxis2', fig)``；
    - ``lines_formatter``：这根轴上的线组成的列表（matplotlib 是 ``Line2D`` 等，Plotly 是 trace）；
    - ``legend_formatter``：matplotlib 收 ``[Legend]``，Plotly 收 ``[fig.layout.legend]``；
    - ``figure_formatter``：``(fig, axes)``，``axes`` 在 matplotlib 是 ``{'left': ax, ...}``，
      在 Plotly 是 ``{'left': 'yaxis', ...}``。

    一张图只有一个图例，归左轴，所以给双 Y 轴的右轴配图例回调会报错。
    执行顺序：默认排版 → 各轴回调 → 整图回调 → 负对数刻度。

    **样式对象。** ``DataPlotter(lines=, frame=, legend=, ticks=)`` 对所有图生效；单根轴、单条线再用
    `~plotlib.formatters.make_axes_formatter`、`~plotlib.formatters.make_lines_formatter`、
    `~plotlib.formatters.make_legend_formatter` 修改。

    See Also
    --------
    plotlib.formatters : 生成格式化回调的工厂函数。
    plotlib.plot_spec.DrawnFigure : 每张图的结果。

    Examples
    --------
    >>> plotter = DataPlotter(dataset, channel_x=0, channel_y=1)
    >>> plotter.plot_multiline(neglog_y=True)
    >>> import matplotlib.pyplot as plt
    >>> plt.show()

    换成 Plotly 交互图，只改 ``backend``：

    >>> fig = DataPlotter(dataset, backend='plotly').plot_multiline().add_slider()
    """

    def __init__(
        self,
        dataset: DataSet,
        groups: Group | None = None,
        cmap: str | None = None,
        font_family: str = 'Arial',
        font_size: int = 22,
        font_weight: str = 'bold',
        lines: LineStyle | None = None,
        frame: FrameStyle | None = None,
        legend: LegendStyle | None = None,
        ticks: TickStyle | None = None,
        plotrange: int | None = None,
        channel_x: int = 0,
        channel_y: int = 1,
        figsize: tuple[float, float] | None = None,
        dpi: float = 100,
        backend: str = 'matplotlib',
    ):
        """
        创建绘图器。

        Parameters
        ----------
        dataset : DataSet
            要画的数据集。
        groups : Group, optional
            分组对象，必须建在 *dataset* 上。不接受配置字典，请先用 ``Group(dataset, config)`` 创建。
            None 表示不分组。
        cmap : str, optional
            色带名，按样品配色用，由后端解析；不给时用 ``'plasma'``。
        font_family : str, default: 'Arial'
            字体。
        font_size : int, default: 22
            字号（磅）。
        font_weight : str, default: 'bold'
            字重。
        lines : LineStyle, optional
            所有图的线：线宽、线型、标记、标记大小。不收颜色：颜色按样品配色，
            要统一颜色请用分组配置的 ``color`` 或 `~plotlib.formatters.make_lines_formatter`。
        frame : FrameStyle, optional
            所有图的边框，如 ``FrameStyle(top=True)`` 让所有版式都画上边框。
        legend : LegendStyle, optional
            所有图的图例。
        ticks : TickStyle, optional
            所有图的刻度。
        plotrange : int, optional
            每条线只画前 *plotrange* 个数据点；None 画全部。
        channel_x, channel_y : int, default: 0, 1
            X、Y 数据的通道号（样品内的列序号）。`plot_xy` 不传通道时也用它们。
        figsize : tuple of (float, float), optional
            图尺寸 ``(宽, 高)``，单位英寸，对所有绘图方法生效。不给时各方法用自己的默认值：
            `plot_multiline` 为 (10, 8)，`plot_groups` 为 (16, 12)，`plot_xy` 和 `plot_dual_y` 为 (12, 8)。
        dpi : float, default: 100
            渲染分辨率（每英寸像素数）。后端按它把字号、线宽（磅）和 *figsize* （英寸）换成实际大小，
            所以两个后端画出的比例一致。
        backend : {'matplotlib', 'plotly'}, default: 'matplotlib'
            绘图后端：静态图或交互图。

        Raises
        ------
        TypeError
            *groups* 不是 `Group`。
        ValueError
            *groups* 建在别的数据集上；*lines* 写了颜色；样式对象写法不对，或这个后端做不到
            （如 Plotly 设置次刻度文字的字号）；*backend* 不认识。
        ImportError
            选了 Plotly 后端但没有安装 Plotly。

        Notes
        -----
        四个样式对象只写要改的字段，其余沿用库默认值和各版式的预设；这里写了的设置盖过版式预设。
        """
        groups = resolve_groups(groups, dataset)

        if lines is not None and lines.color is not None:
            raise ValueError("lines 不收颜色：颜色按样品配色（cmap）；统一颜色请用分组配置的 color 或 make_lines_formatter")
        # 外观参数打包成后端无关的 Appearance，由后端翻译（matplotlib → rc_params 等，Plotly → 模板）；
        # 存的是用户写的那一层，库默认和版式预设由后端叠加。非标准写法、后端做不到的设置在这里创建后端时就报错
        appearance = Appearance(font_family=font_family, font_size=font_size, font_weight=font_weight,
                                lines=lines or LineStyle(), frame=frame or FrameStyle(),
                                legend=legend or LegendStyle(), ticks=ticks or TickStyle(), dpi=dpi)
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
        把计划交给后端画，结果存进 ``self.figures`` （先清空），返回 ``self``。

        画图的事（建图、画线、排版、回调、负对数刻度）全在后端。多张计划时按后端的能力分两种：
        有 ``draw_pages`` 的后端（Plotly）画成一个 Figure 多页，其余（matplotlib）一张计划一张图。
        判断依据是「后端有没有这个方法」，不看后端的名字。
        """
        draw_pages = getattr(self.backend, 'draw_pages', None)
        if draw_pages is not None and len(specs) > 1:
            drawn = draw_pages(specs, figsize, formatters, figure_formatter)
        else:
            drawn = [self.backend.draw(spec, figsize, formatters, figure_formatter) for spec in specs]
        self.figures = {page.spec.key: page for page in drawn}
        return self

    # ========================================================================
    # 交互：画完之后的可选操作（只有支持它的后端有）
    # ========================================================================

    def add_slider(self, mode: str = 'cumulative', slider_formatter=None):
        """
        给刚画好的一页图加曲线滑块：一条线一档，拖动时只显示选中的线。

        只有 Plotly 后端有滑块，而且只能用于一页图（`plot_multiline`、合并模式的 `plot_groups`）；
        多页图（分组分离模式、`plot_xy`、`plot_dual_y`）请用 `add_page_slider`。
        只给计划画出的曲线分档；``figure_formatter`` 里加的参考线等不分档，每档保持原来的显隐。

        Parameters
        ----------
        mode : {'cumulative', 'single'}, default: 'cumulative'
            ``'cumulative'``：每档显示第一条到当前这条线；``'single'``：每档只显示当前这条线。
        slider_formatter : callable, optional
            ``slider_formatter(slider)``，接收安装好的 ``plotly.graph_objects.layout.Slider`` 并原地修改，
            在默认外观之后执行（如改当前值的前缀）。

        Returns
        -------
        `plotly.graph_objects.Figure`
            加好滑块的图（原地修改），可直接交给 `plotlib.html_export.write_fit_html`。
            重复调用只保留一个滑块。

        Raises
        ------
        NotImplementedError
            当前后端没有滑块（matplotlib）。
        RuntimeError
            还没画图；或当前结果不止一页。

        Examples
        --------
        >>> fig = DataPlotter(data, backend='plotly').plot_multiline().add_slider(mode='single')
        """
        add_slider = self._slider_method('add_slider')
        if len(self.figures) != 1:
            raise RuntimeError(f"当前结果有 {len(self.figures)} 页，曲线滑块只能加在一页图上；"
                               f"按页翻请用 add_page_slider()")
        [drawn] = self.figures.values()
        # 只给计划画出的曲线分档；整图回调加的参考线等不分档、保持原样（55576fb 复审 4）
        return add_slider(drawn.fig, mode, slider_formatter, curves=drawn.artists)

    def add_page_slider(self, mode: str = 'single', slider_formatter=None):
        """
        给多页图加翻页滑块：一页一档。

        分组分离模式、`plot_xy`、`plot_dual_y` 一次画出多张计划，Plotly 把它们画成一个 Figure 的多页，
        刚画完只显示第一页。档位标签是每页的名字（组名或样品名），翻页时标题和图例标题换成这一页的。
        不属于任何一页的 trace（如 ``figure_formatter`` 加的参考线）每档保持原来的显隐。

        Parameters
        ----------
        mode : {'single', 'cumulative'}, default: 'single'
            ``'single'``：每档只显示当前页；``'cumulative'``：每档显示第一页到当前页。
        slider_formatter : callable, optional
            ``slider_formatter(slider)``，接收安装好的滑块并原地修改，在默认外观之后执行。
            当前值默认不加前缀，要加可以在这里设。

        Returns
        -------
        `plotly.graph_objects.Figure`
            加好滑块的图（各页共用的那一个，原地修改）。

        Raises
        ------
        NotImplementedError
            当前后端没有滑块（matplotlib）。
        RuntimeError
            还没画图；或当前结果只有一页（请用 `add_slider`）。

        Examples
        --------
        >>> fig = DataPlotter(data, backend='plotly').plot_xy().add_page_slider()
        """
        add_page_slider = self._slider_method('add_page_slider')
        if len(self.figures) == 1:
            raise RuntimeError("当前结果只有一页，翻页滑块用不上；按曲线滑动请用 add_slider()")
        return add_page_slider(list(self.figures.values()), mode, slider_formatter)

    def _slider_method(self, name: str):
        """两种滑块共用的检查：后端有没有这个方法（不按后端名字判断）、是否已经画过图。返回后端的这个方法。"""
        method = getattr(self.backend, name, None)
        if method is None:
            raise NotImplementedError(f"滑块只有 Plotly 后端有，当前后端是 {self.backend.name!r}；"
                                      f"请用 DataPlotter(..., backend='plotly')")
        if not self.figures:
            raise RuntimeError("请先调用绘图方法，再添加滑块")
        return method

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
                       legend_title: str | None = None,
                       ) -> DataPlotter:
        """
        多线图：所有样品画在同一坐标系，每个样品一条线，颜色按样品在色带上取。

        Parameters
        ----------
        axes_formatter, lines_formatter, legend_formatter : callable, optional
            坐标轴、线条、图例的回调，调用形状见类说明的 Notes。
            一般用 `~plotlib.formatters.make_axes_formatter` 等工厂生成。
        neglog_x, neglog_y : bool, default: False
            负对数：数据取绝对值后画，刻度文字补回负号。适合全为负数、又想用对数轴的数据。
        plot_kind : {'line', 'scatter', 'bar'}, default: 'line'
            画法。
        figure_formatter : callable, optional
            整图回调 ``figure_formatter(fig, axes)``，在各轴回调之后调用一次。
        legend_title : str, optional
            图例标题，默认不加。多线图只有一张图，标题原样使用（``'{name}'`` 不替换）。

        Returns
        -------
        DataPlotter
            ``self``，可以链式调用。结果在 ``figures = {'main': DrawnFigure}``。

        Examples
        --------
        >>> plotter = DataPlotter(data, channel_x=0, channel_y=1)
        >>> plotter.plot_multiline(axes_formatter=make_axes_formatter(x=AxisStyle(scale='log')))
        >>> line = plotter.figures['main'].artist(0)      # 样品 0 的线
        """
        # 不分组（groups=None）：一张 'main' 图，全部样品；不看 self.groups
        specs = plan_multiline_figures(self.dataset, None, self.channel_x, self.channel_y,
                                       plotrange=self.plotrange, neglog_x=neglog_x, neglog_y=neglog_y,
                                       kind=plot_kind, legend_title=legend_title)
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
                    legend_title: str | None = None,
                    ) -> DataPlotter:
        """
        按 ``self.groups`` 分组画多线图。

        没有分组时等同于 `plot_multiline`。

        Parameters
        ----------
        merge_groups : bool, default: False
            False：每个分组单独一张图；True：所有分组合并到一张图。
        neglog_x, neglog_y, axes_formatter, lines_formatter, legend_formatter, plot_kind, figure_formatter
            同 `plot_multiline`。
        legend_title : str, optional
            图例标题，默认不加。分离模式下 ``'{name}'`` 换成组名，如 ``'Group {name}'``。

        Returns
        -------
        DataPlotter
            ``self``，可以链式调用。分离模式 ``figures = {组名: DrawnFigure}``；
            合并模式 ``figures = {'main': DrawnFigure}``。

        Notes
        -----
        **分组样式。** 分组配置里写了 ``linestyle`` / ``marker`` / ``color`` 就应用到这组所有的线上
        （两种模式一样）：``linestyle`` 只对折线生效，``marker`` 对折线和散点生效，``color`` 对所有画法生效。
        优先级：库默认 < 分组样式 < ``lines_formatter``。

        **颜色。** 没写 ``color`` 时，分离模式按样品配色，同一样品在各张图里同色；
        合并模式同组的线统一为组首色（该组写在第一位的样品的颜色）。

        **合并模式的去重。** 被多个分组引用的样品只画一次，归第一个包含它的分组（先到先得），
        用那个分组的样式和颜色。

        Examples
        --------
        >>> groups = Group(data, {'A': {'num': [0, 1], 'linestyle': 'dash'}, 'B': {'num': [2, 3]}})
        >>> DataPlotter(data, groups=groups).plot_groups(merge_groups=True)
        """
        if not self.groups.names:
            return self.plot_multiline(
                plot_kind=plot_kind, neglog_x=neglog_x, neglog_y=neglog_y,
                axes_formatter=axes_formatter, lines_formatter=lines_formatter,
                legend_formatter=legend_formatter, figure_formatter=figure_formatter,
                legend_title=legend_title,
            )

        # 分组规则（去重、先到先得、组首色、样式归属）都在计划里；合并模式的计划只有一张 'main' 图，
        # 所以两种模式走同一个 _render
        specs = plan_multiline_figures(self.dataset, self.groups, self.channel_x, self.channel_y,
                                       merge_groups=merge_groups, plotrange=self.plotrange,
                                       neglog_x=neglog_x, neglog_y=neglog_y, kind=plot_kind,
                                       legend_title=legend_title)
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
                legend_title: str | None = None,
                ) -> DataPlotter:
        """
        x-y 单线图：每个样品一张图、一条线，画两个通道之间的关系（如 Nyquist 图：Zs' 对 Zs''）。

        一张图只有一条线，不按样品换色，用后端默认色。

        Parameters
        ----------
        channel_x, channel_y : int, optional
            横轴、纵轴的通道号；不传时用构造时的 *channel_x*、*channel_y*。
        legend_title : str, optional
            图例标题，默认不加。``'{name}'`` 换成每张图的样品名。
        axes_formatter, lines_formatter, legend_formatter, plot_kind, neglog_x, neglog_y, figure_formatter
            同 `plot_multiline`。

        Returns
        -------
        DataPlotter
            ``self``，可以链式调用。``figures = {样品号: DrawnFigure}``，
            取线用 ``figures[样品号].artist(样品号)``。Plotly 把各样品画成一个 Figure 的多页，
            用 `add_page_slider` 翻页。

        Examples
        --------
        >>> DataPlotter(data).plot_xy(channel_x=1, channel_y=2, neglog_y=True)
        """
        specs = plan_xy_figures(self.dataset,
                                self.channel_x if channel_x is None else channel_x,
                                self.channel_y if channel_y is None else channel_y,
                                plotrange=self.plotrange, neglog_x=neglog_x, neglog_y=neglog_y, kind=plot_kind,
                                legend_title=legend_title)
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
                    legend_title: str | None = '{name}',
                    ) -> DataPlotter:
        """
        双 Y 轴图：每个样品一张图，左线挂左轴、右线挂右轴，共用 X 轴。

        默认左红右蓝、画完整的框；图例在图外上方，两条线都进图例、各写自己的单位，
        图例标题是样品名。

        Parameters
        ----------
        left, right : (int, int)
            左线、右线的 (X 通道, Y 通道)。两条线共用一根 X 轴：X 通道可以不同（如位移、电压各有自己的时间列，
            采样点可以不一样），但必须是同一个物理量、同一个单位（秒和毫秒混用不报错，会按数值直接叠在一起），
            X 轴标题取左侧 X 通道的单位。
        axes_formatter, lines_formatter, legend_formatter : callable, optional
            左轴的回调。图例只有一个（两条线都在里面），归 *legend_formatter*。
        right_axes_formatter, right_lines_formatter : callable, optional
            右轴的回调，只拿到右轴和右线。右轴回调里的 X 轴设置也作用在共用的 X 轴上。
        right_legend_formatter : callable, optional
            不能用：右轴没有单独的图例，给了会报 `ValueError`。
        neglog_x, neglog_y, neglog_x2, neglog_y2 : bool, default: False
            左线的 X、Y 与右线的 X、Y 是否按负对数画。X 轴左右共用，刻度负号只按 *neglog_x* 加一次，
            *neglog_x2* 只对右线的 X 数据取绝对值。
        plot_kinds : tuple of (str, str), default: ('line', 'line')
            左线、右线的画法。
        figure_formatter : callable, optional
            整图回调 ``figure_formatter(fig, axes)``，``axes = {'left': 左轴, 'right': 右轴}``，
            可以同时调整两根轴。
        legend_title : str or None, default: '{name}'
            图例标题，``'{name}'`` 换成样品名；None 表示不加。

        Returns
        -------
        DataPlotter
            ``self``，可以链式调用。``figures = {样品号: DrawnFigure}``；左线用
            ``figures[样品号].artist(样品号)``，右线用 ``.artist(样品号, 'right')``，
            坐标轴在 ``.axes['left']`` / ``.axes['right']``。

        Raises
        ------
        ValueError
            给了 *right_legend_formatter*。

        Examples
        --------
        压电数据：左轴画位移-时间，右轴画电压-时间：

        >>> DataPlotter(data).plot_dual_y(left=(0, 1), right=(2, 3))
        """
        specs = plan_dual_y_figures(
            self.dataset, left=left, right=right, plotrange=self.plotrange,
            neglog_x=neglog_x, neglog_y=neglog_y, neglog_x2=neglog_x2, neglog_y2=neglog_y2,
            kinds=plot_kinds, legend_title=legend_title,
        )
        # 每根轴一组回调
        formatters = {
            'left':  AxesFormatter(axes_formatter, lines_formatter, legend_formatter),
            'right': AxesFormatter(right_axes_formatter, right_lines_formatter, right_legend_formatter),
        }
        return self._render(specs, self.figsize or (12, 8), formatters, figure_formatter)
