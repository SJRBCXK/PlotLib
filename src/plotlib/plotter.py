"""
批量绘图的公共接口。

`DataPlotter` 将数据选择和分组转换为绘图计划，由所选后端渲染。
绘图结果保存在 ``DataPlotter.figures``。
"""
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from .backends import get_backend
from .dataset import DataSet
from .group import Group
from .layouts import NO_LEGEND_MESSAGE
from .plan import BarErrors, plan_bars, plan_figures, resolve_groups
from .plot_spec import (Appearance, AxesFormatter, BarDimension, BarMode, BarStyle, ColorbarStyle, DrawnFigure,
                        FigureSpec,
                        FrameStyle, Layer, LegendStyle, LineStyle, Members, TickStyle)
from .processor import Reduction

# 整图回调在各轴回调之后接收图形和坐标轴映射。
type FigureFormatter = Callable[[Any, dict[str, Any]], Any]


class DataPlotter:
    """
    使用 Matplotlib 或 Plotly 绘制多样品科学数据。

    曲线类的图都用 `plot`，由两样东西组合：

    - *by*：哪些样品进哪张图。``'all'`` 全部样品一张，``'group'`` 按分组（分开或合并），``'sample'`` 每个样品一张；
    - *layers*：每个样品画哪几条。一个 `~plotlib.plot_spec.Layer` 写取哪两个通道、画成折线还是散点、挂左轴还是右轴。

    每次绘图会更新 ``figures``。绘图方法返回 ``self``，支持链式调用。

    Attributes
    ----------
    figures : dict
        最近一次绘图的结果，格式为 ``{图键: DrawnFigure}``。
        可用 ``figures[key].artist(样品号)`` 获取指定样品的绘图对象。
    dataset : DataSet
        绘图用的数据集。
    groups : Group
        分组；不分组时是空 `Group`。
    backend : MatplotlibBackend or PlotlyBackend
        实际画图的后端对象。

    Notes
    -----
    坐标轴、曲线和图例回调按轴打包成 `~plotlib.plot_spec.AxesFormatter`，可用整图回调访问图形及其全部坐标轴。

    - ``axes`` 在 Matplotlib 中接收 ``(ax, fig)``，在 Plotly 中接收 ``(轴名, fig)``，例如 ``('yaxis2', fig)``。
    - ``lines`` 接收当前轴上的折线列表（Matplotlib 的 ``Line2D`` 或 Plotly 的 trace）。
    - ``scatter`` 接收当前轴上的散点列表（Matplotlib 的 ``PathCollection`` 或 Plotly 的 trace）。
    - ``bars`` 接收各个柱状图系列（Matplotlib 的 ``BarContainer`` 或 Plotly 的柱状 trace）。
    - ``legend`` 在 Matplotlib 中接收 ``[Legend]``，在 Plotly 中接收 ``[fig.layout.legend]``。
    - ``figure_formatter``：``(fig, axes)``，``axes`` 在 matplotlib 是 ``{'left': ax, ...}``，
      在 Plotly 是 ``{'left': 'yaxis', ...}``。

    图例回调配置整张图的图例，只能放在左侧。
    图例按绘图计划生成，每条曲线或每个柱状图系列对应一个条目。只有一个条目时也显示图例。
    空样品名和以 ``'_'`` 开头的样品名均保留。Matplotlib 的双 Y 轴图先列左轴，再列右轴。
    回调将标签设为 ``None``，或将标签改为以 ``'_'`` 开头的名称（如 ``'_nolegend_'``）时，Matplotlib 略去该条目。
    线条、散点或柱状图回调触发图例重建时，参考线等由回调添加的带标签对象排在计划条目之后。
    后端先应用默认版式，再运行各轴回调和整图回调，最后处理负对数刻度。

    ``frame``、``legend`` 和 ``ticks`` 设置各绘图方法的全局外观，``lines`` 设置折线外观。
    `plotlib.formatters` 提供坐标轴、折线、散点、柱状图和图例的回调工厂。

    See Also
    --------
    plotlib.formatters : 生成格式化回调的工厂函数。
    plotlib.plot_spec.DrawnFigure : 每张图的结果。

    Examples
    --------
    >>> plotter = DataPlotter(dataset, channel_x=0, channel_y=1)
    >>> plotter.plot(Layer(neglog_y=True))
    >>> import matplotlib.pyplot as plt
    >>> plt.show()

    换成 Plotly 交互图，只改 ``backend``：

    >>> fig = DataPlotter(dataset, backend='plotly').plot().add_slider()
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
            X、Y 数据的通道号（样品内的列序号）。`plot` 的图层没写通道时用它们。
        figsize : tuple of (float, float), optional
            图尺寸 ``(宽, 高)``，单位为英寸。默认值按 `plot` 的 *by*：
            ``'all'`` 为 (10, 8)，``'group'`` 为 (16, 12)，``'sample'`` 为 (12, 8)。
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
            *groups* 引用了不同的数据集，*lines* 指定了全局颜色，或样式设置无效或超出后端的支持范围
            （如 Plotly 设置次刻度文字的字号）；*backend* 不认识。
        ImportError
            选了 Plotly 后端但没有安装 Plotly。

        Notes
        -----
        全局样式覆盖库默认值和版式预设中与其对应的字段。
        """
        groups = resolve_groups(groups, dataset)

        if lines is not None and lines.color is not None:
            raise ValueError("lines 不收颜色：颜色按样品配色（cmap）；统一颜色请用分组配置的 color 或 make_lines_formatter")
        # 保存显式外观设置，后端负责校验并合并各层样式。
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
        渲染绘图计划并将结果保存到 ``self.figures``，返回 ``self``。

        支持 ``draw_pages`` 的后端在同一个 Figure 中渲染多页。其他后端为每项计划创建一张图。

        全部渲染成功后才替换 ``self.figures``。逐图渲染时，若某张图失败，
        通过后端提供的 ``close`` 方法关闭本次调用中已完成的图。
        """
        draw_pages = getattr(self.backend, 'draw_pages', None)
        if draw_pages is not None and len(specs) > 1:
            drawn = draw_pages(specs, figsize, formatters, figure_formatter)
        else:
            drawn = []
            try:
                for spec in specs:
                    drawn.append(self.backend.draw(spec, figsize, formatters, figure_formatter))
            except BaseException:
                if (close := getattr(self.backend, 'close', None)) is not None:
                    for page in drawn:
                        close(page)
                raise
        self.figures = {page.spec.key: page for page in drawn}
        return self

    # ========================================================================
    # 交互：画完之后的可选操作（只有支持它的后端有）
    # ========================================================================

    def add_slider(self, mode: str = 'cumulative', slider_formatter=None):
        """
        为单页 Plotly 图添加曲线滑块，每个档位对应一条曲线。

        滑块只控制绘图计划中的曲线。通过 ``figure_formatter`` 添加的参考线保留自身的可见性。
        多页图使用 `add_page_slider`。

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
        >>> fig = DataPlotter(data, backend='plotly').plot().add_slider(mode='single')
        """
        add_slider = self._slider_method('add_slider')
        if len(self.figures) != 1:
            raise RuntimeError(f"当前结果有 {len(self.figures)} 页，曲线滑块只能加在一页图上；"
                               f"按页翻请用 add_page_slider()")
        [drawn] = self.figures.values()
        return add_slider(drawn.fig, mode, slider_formatter, curves=drawn.artists)

    def add_page_slider(self, mode: str = 'single', slider_formatter=None):
        """
        为多页 Plotly 图添加翻页滑块，每个档位对应一页。

        档位标签为组名或样品名。切换页时更新图标题和图例标题。
        各页之外的轨迹（例如整图回调添加的参考线）保留自身的可见性。

        Parameters
        ----------
        mode : {'single', 'cumulative'}, default: 'single'
            ``'single'``：每档只显示当前页；``'cumulative'``：每档显示第一页到当前页。
        slider_formatter : callable, optional
            ``slider_formatter(slider)``，接收安装好的滑块并原地修改，在默认外观之后执行。
            当前值默认无前缀。

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
        >>> fig = DataPlotter(data, backend='plotly').plot(by='sample').add_page_slider()
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
        if any(drawn.spec.layout == 'bars' for drawn in self.figures.values()):
            raise RuntimeError("柱状图不支持滑块：滑块按样品切换曲线，柱状图的系列不一定是样品")
        return method

    # ========================================================================
    # 绘图方法：计划 → 打包回调 → _render
    # ========================================================================

    _DEFAULT_FIGSIZE = {'all': (10, 8), 'group': (16, 12), 'sample': (12, 8)}

    def plot(self,
             layers: Layer | Sequence[Layer] | None = None,
             by: Members = 'all',
             merge_groups: bool = False,
             formatters: AxesFormatter | dict[str, AxesFormatter] | None = None,
             figure_formatter: FigureFormatter | None = None,
             legend_title: str | None = 'auto',
             colorbar: ColorbarStyle | None = None,
             ) -> DataPlotter:
        """
        绘制折线和散点图。*by* 指定样品的分图方式，*layers* 指定每个图层的通道、画法和 Y 轴。

        Parameters
        ----------
        layers : Layer or list of Layer, optional
            图层及其顺序。省略的通道取构造时的 *channel_x*、*channel_y*。
            默认使用 ``Layer()``，在左轴绘制折线。
        by : {'all', 'group', 'sample'}, default: 'all'
            ``'all'``：全部样品一张图，不看分组；``'group'``：按 ``self.groups`` 画（没有分组时报错）；
            ``'sample'``：每个样品一张图，不看分组。
        merge_groups : bool, default: False
            ``by='group'`` 时：False 每个分组一张图，True 所有分组合并到一张图（重复样品只画一次）。
        formatters : AxesFormatter or dict, optional
            按轴的回调。一个 `~plotlib.plot_spec.AxesFormatter` 作用于左轴；
            可用 ``{'left': AxesFormatter(...), 'right': AxesFormatter(...)}`` 分别配置左右轴。
            回调签名见类说明。左右两侧共享 X 轴，任一侧的坐标轴回调都可调整该轴。
            画图前检查：轴名只能是 ``'left'``、``'right'``，没有右侧图层时不能给 ``'right'``，图例回调只能放在左侧。
        figure_formatter : callable, optional
            在各轴回调之后调用一次 ``figure_formatter(fig, axes)``。颜色映射图可通过 ``axes['colorbar']`` 访问颜色条。
        legend_title : str or None, default: 'auto'
            图例标题，``'{name}'`` 换成每张图自己的名字：``by='sample'`` 是样品名，分组分离时是组名
            （只有一个样品或一个分组、只画出一张图时也替换）；``'all'`` 和合并模式的图没有自己的名字，原样保留。
            ``'auto'``：一个样品画多层时是样品名，否则不加；None 表示不加。
        colorbar : ColorbarStyle, optional
            为 ``ScatterMap(color=...)`` 配置色带、范围、刻度类型和标题。
            默认使用线性的 ``'viridis'`` 色带，范围取自可绘制数据，标题取自颜色通道的列标题。

        Returns
        -------
        DataPlotter
            ``self``，可以链式调用。``figures`` 的键：``'all'`` 和合并模式是 ``'main'``，分离模式是组名，
            ``'sample'`` 是样品号。``figures[key].artist(样品号, 轴)`` 取这根轴上该样品的第一个图层，
            同一轴多层时用 ``figures[key].artists``，同一样品各层的顺序与 *layers* 一致。

        Raises
        ------
        ValueError
            分图方式、图层配置或负对数设置无效，具体规则见 `~plotlib.plan.plan_figures`。
            回调的轴名无效、右轴回调没有对应图层，或图例回调配置在右侧时也会报错。
            校验在渲染前进行。

        Notes
        -----
        ``'all'``、``'group'`` 和 ``'sample'`` 的默认尺寸分别为 (10, 8)、(16, 12) 和 (12, 8) 英寸。
        构造时指定 *figsize* 可覆盖默认尺寸。
        版式按图层和 *by*：有右侧图层用双 Y 轴版式（左红右蓝），``'sample'`` 用单图版式，其余用多线版式。

        Examples
        --------
        全部样品一张图，Y 轴对数：

        >>> plotter = DataPlotter(data, channel_x=0, channel_y=1)
        >>> plotter.plot(formatters=AxesFormatter(axes=make_axes_formatter(y=AxisStyle(scale='log'))))

        按分组画散点，每组一张：

        >>> DataPlotter(data, groups=groups).plot(Layer(kind='scatter'), by='group')

        每个样品一张 Nyquist 图（Zs' 对 Zs''，Zs'' 为负）：

        >>> plotter.plot(Layer(1, 2, neglog_y=True), by='sample')

        每个样品一张双 Y 轴图，左轴实测点、右轴另一个量：

        >>> plotter.plot([Layer(0, 1, kind='scatter'), Layer(0, 2, side='right')], by='sample')

        散点按通道 3 着色、按通道 4 定大小，颜色条用对数刻度：

        >>> plotter.plot(Layer(0, 1, kind='scatter', mapping=ScatterMap(color=3, size=4)),
        ...              colorbar=ColorbarStyle(scale='log'))
        """
        if layers is None:
            layers = [Layer()]
        elif isinstance(layers, Layer):
            layers = [layers]
        # 图层未指定的通道沿用构造参数。
        layers = [replace(layer, x=self.channel_x if layer.x is None else layer.x,
                          y=self.channel_y if layer.y is None else layer.y) for layer in layers]
        specs = plan_figures(self.dataset, self.groups if by == 'group' else None, layers, by=by,
                             merge_groups=merge_groups, plotrange=self.plotrange, legend_title=legend_title,
                             colorbar=colorbar)
        if formatters is None:
            formatters = {}
        elif isinstance(formatters, AxesFormatter):
            formatters = {'left': formatters}
        _check_formatters(formatters, has_right=any(layer.side == 'right' for layer in layers))
        figsize = self.figsize or self._DEFAULT_FIGSIZE[by]
        return self._render(specs, figsize, formatters, figure_formatter)

    def plot_bars(self,
                  channels: int | Sequence[int] | None = None,
                  x: BarDimension = 'sample',
                  series: BarDimension = 'channel',
                  reduce: Reduction | None = None,
                  errors: BarErrors = None,
                  mode: BarMode = 'group',
                  width: float = 0.8,
                  styles: BarStyle | Mapping[int, BarStyle] | Mapping[str, BarStyle] | None = None,
                  formatters: AxesFormatter | dict[str, AxesFormatter] | None = None,
                  figure_formatter: FigureFormatter | None = None,
                  legend_title: str | None = 'auto',
                  ) -> DataPlotter:
        """
        在 X 轴上排列类别，在每个类别内并排或堆叠各系列。

        类别和系列中，恰有一维为通道（``'channel'``），另一维为样品或分组。
        *reduce* 将每个类别与系列组合对应的数据汇总成一个柱高。省略时，每个组合至多允许一个有效值。

        Parameters
        ----------
        channels : int or list of int, optional
            按指定顺序绘制的通道号，须互不重复。省略时使用构造时的 *channel_y*。
        x, series : {'sample', 'group', 'channel'}, default: 'sample', 'channel'
            类别（X 轴）和系列（图例）使用的维度。``'sample'`` 使用全部样品，按样品号排序。
            ``'group'`` 使用 ``self.groups`` 中的分组，缺少分组时引发 ``ValueError``。
        reduce : str, callable or None, default: None
            每列跨行汇总为柱高的方法，取值见 `~plotlib.processor.DataTransformer.Reduce`。
            ``None`` 要求每格至多有一个有效值。分组时先汇总各样品，再对组内结果取均值。
            构造参数 *plotrange* 指定纳入计算的前若干行。
        errors : {'std', 'sem'}, dict or None, default: None
            对称误差棒。``'std'`` 和 ``'sem'`` 分别表示标准差和标准误差。
            分组时以组内各样品的汇总值为输入，按样品绘制时以同一列的多行数据为输入，且要求 ``reduce='mean'``。
            按样品绘制还可用 ``{值通道: 误差通道}`` 指定误差来源。误差按原始行与柱高对齐，误差传递由调用方负责。
        mode : {'group', 'stack'}, default: 'group'
            并排或堆叠。堆叠时正负值分别累加，误差棒以每段远离零的一端为中心。
            调用方须确保叠加的通道单位相同，且数值可相加。Plotly 的堆叠图带误差棒时禁用图例的单击和双击显隐操作，
            因为误差棒的位置在渲染前已确定。
        width : float, default: 0.8
            单个类别的总柱宽占类别间距的比例，取值范围为 ``(0, 1]``。
        styles : BarStyle or dict, optional
            一个 `~plotlib.plot_spec.BarStyle` 用于全部系列；``{系列键: BarStyle}`` 逐个系列指定，优先于分组配置的
            ``color``、``hatch``。请通过此参数配置误差棒端帽半长 ``capsize``，Matplotlib 在绘制时创建端帽。
        formatters : AxesFormatter or dict, optional
            仅支持左轴回调 ``AxesFormatter(axes=..., bars=..., legend=...)``。``bars`` 接收各系列对应的绘图对象，
            即 Matplotlib 的 ``BarContainer`` 或 Plotly 的 trace。配置 ``lines``、``scatter`` 或 ``'right'`` 会引发 ``ValueError``。
        figure_formatter : callable, optional
            整图回调 ``figure_formatter(fig, axes)``，在各轴回调之后调用一次（如添加第二套图例）。
        legend_title : str or None, default: 'auto'
            图例标题；``'auto'`` 和 None 都不加。

        Returns
        -------
        DataPlotter
            ``self``。结果是一张 ``figures['main']``；``figures['main'].artist(key)`` 按系列的键取：
            样品号、原数据集里的通道号或组名。

        Raises
        ------
        ValueError
            维度、通道、柱宽、汇总、误差、样式或回调配置无效，或数据不符合汇总要求。
            具体规则见 `~plotlib.plan.plan_bars`。校验参数和汇总结果后才开始渲染。

        Notes
        -----
        - 样品系列使用样品色。分组系列使用配置中的颜色，省略时采用组内首个样品的颜色。通道系列按 *channels* 的顺序从色带取色。
        - Y 轴标题取自单个通道的列标题，或多个通道共用的列标题。标题不一致时留空，可通过轴回调另行设置。
        - 数据全为 NaN 的位置保留柱位，并省略柱形。
        - 默认图尺寸为 (10, 8) 英寸。柱状图不支持滑块。

        Examples
        --------
        每个样品一组柱，比较它的几项指标（每格取均值，误差棒是多行之间的标准差）：

        >>> plotter.plot_bars([1, 2, 3], reduce='mean', errors='std')

        每个单位一组柱，比较各组（组内跨样品取平均，误差棒是组内的标准误差）：

        >>> DataPlotter(data, groups=groups).plot_bars([1, 2], x='channel', series='group', reduce='max', errors='sem')

        黑白图，用纹理区分通道：

        >>> plotter.plot_bars([1, 2], styles={1: BarStyle(color='white', edge_color='black', edge_width=1, hatch='slash'),
        ...                                   2: BarStyle(color='white', edge_color='black', edge_width=1, hatch='dot')})
        """
        if formatters is None:
            formatters = {}
        elif isinstance(formatters, AxesFormatter):
            formatters = {'left': formatters}
        _check_formatters(formatters, has_right=False, bars=True)      # 先校验回调配置，再汇总数据。
        spec = plan_bars(self.dataset, self.groups if 'group' in (x, series) else None,
                         self.channel_y if channels is None else channels, x=x, series=series, reduce=reduce,
                         errors=errors, mode=mode, width=width, styles=styles, plotrange=self.plotrange,
                         legend_title=legend_title)
        return self._render([spec], self.figsize or (10, 8), formatters, figure_formatter)


def _check_formatters(formatters: dict[str, AxesFormatter], has_right: bool, bars: bool = False) -> None:
    """在渲染前校验回调配置的轴名、轴是否存在、图例归属及画法。"""
    if unknown := sorted(set(formatters) - {'left', 'right'}):
        raise ValueError(f"formatters 的轴名只能是 'left'、'right'，实际有 {unknown}")
    if 'right' in formatters and bars:
        raise ValueError("柱状图只有左轴：formatters 不能给 'right'")
    if 'right' in formatters and not has_right:
        raise ValueError("formatters 给了 'right'，但没有右侧图层（Layer(..., side='right')），右侧回调不会执行")
    if 'right' in formatters and formatters['right'].legend is not None:
        raise ValueError(NO_LEGEND_MESSAGE)
    for side, fm in formatters.items():
        if bars:
            wrong = [name for name in ('lines', 'scatter') if getattr(fm, name) is not None]
            hint = "柱状图没有折线、散点，请用 AxesFormatter(bars=...)"
        else:
            wrong = ['bars'] if fm.bars is not None else []
            hint = "bars 回调只用于 plot_bars"
        if wrong:
            raise ValueError(f"formatters['{side}'] 写了 {', '.join(wrong)} 回调，这张图里没有对应的对象：{hint}")
