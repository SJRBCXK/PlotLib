"""科学数据绘图模块。"""
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from .dataset import DataSet
from .group import Group
from .plot_common import FigureSpec, color_positions, get_xy_data, plan_figures, resolve_groups
from .style import translate_color, translate_linestyle, translate_marker

# ============================================================================
# 默认列索引常量
# ============================================================================
dataRowNum_unit1 = 0  # X1 轴（如时间）
dataRowNum_unit2 = 1  # Y1 轴（如位移）
dataRowNum_unit3 = 2  # X2 轴（如时间）
dataRowNum_unit4 = 3  # Y2 轴（如电压）


class DataPlotter:
    """
    科学数据绘图器。

    支持多种绘图模式：单图多线、分组绘图、Y-Y 关系图、X-YY 双轴图。
    提供统一的格式化接口和负对数刻度支持。

    绘图方法
    --------
    plot_objects()
        标准多线图，所有样品绘制在同一坐标系。
    group_plotter()
        分组绘图，支持合并或分离模式。
    subplotter_yy()
        Y-Y 关系图，绘制两个变量的相关性（如 Nyquist 图）。
    subplotter_xyy()
        X-YY 双轴图，共享 X 轴的双 Y 轴显示。

    绘图结果统一存入 self.axesset（每次调用前清空）。

    格式化系统
    ----------
    所有绘图方法支持三类可选格式化器：

    - axes_formatter(ax, fig)  : 自定义坐标轴样式
    - lines_formatter(lines)   : 自定义线条样式
    - legend_formatter(legends): 自定义图例样式

    格式化器按以下顺序应用：默认格式 -> 用户格式 -> 负对数格式

    使用示例
    --------
    >>> plotter = DataPlotter(dataset, plotdataRowNum_x=0, plotdataRowNum_y=1)
    >>> plotter.plot_objects(NegLogScale_y=True)
    >>> plt.show()
    """

    def __init__(
        self,
        input_dataset: DataSet,
        groups: Group | None = None,
        cmap : str | None = None,
        font_family: str = 'Arial',
        font_size: int = 22,
        font_weight: str = 'bold',
        plot_lw: int = 3,
        axis_lw: int = 3,
        plot_style: str | tuple = 'solid',
        plotrange: int | None = None,
        plotdataRowNum_x: int = dataRowNum_unit1,
        plotdataRowNum_y: int = dataRowNum_unit2,
        legend_fontsize: int = 10,
        ticker_width: int = 3,
        figsize: tuple[float, float] | None = None,
    ):
        """
        初始化绘图器。

        Parameters
        ----------
        input_dataset : DataSet
            输入数据集，包含 data、names、units 等属性。
        groups : Group, optional
            分组对象，包含各组的样品号及配置；必须建在 input_dataset 上。
            不接受字典：请先用 Group(input_dataset, config) 创建。None 表示不分组。
        cmap : Colormap, optional
            matplotlib 颜色映射，默认 plasma。
        font_family : str
            字体族。
        font_size : int
            字体大小。
        font_weight : str
            字体粗细。
        axis_lw : int
            坐标轴线宽。
        plot_lw : int
            绘图线宽。
        plot_style : str or tuple
            默认线型，标准写法（style.py）：'solid'、'dash'、'dot'、'dashdot'，
            或自定义虚线 (实线长, 空白长, ...)。分组没写 linestyle 时也用它。
        plotrange : int, optional
            绘制的数据点数，None 表示全部。
        plotdataRowNum_x : int
            X 轴数据的通道号（样品内的列序号）。
        plotdataRowNum_y : int
            Y 轴数据的通道号（样品内的列序号）。
        legend_fontsize : int
            图例字体大小。
        ticker_width : int
            刻度线宽度。
        figsize : tuple, optional
            图窗尺寸（宽, 高），单位英寸，对本绘图器的所有绘图方法生效。
            None 时各方法用各自的默认值：plot_objects 为 (10, 8)，group_plotter 为 (16, 12)。
        """
        groups = resolve_groups(groups, input_dataset)

        resolved_cmap = plt.get_cmap('plasma' if cmap is None else cmap)
        
        # 样式设置以 rcParams 字典形式保存，绘图时通过 plt.rc_context 应用
        self.rc_params = {
            'font.family': font_family,
            'font.size': font_size,
            'font.weight': font_weight,
            'axes.linewidth': axis_lw,
            'axes.labelweight': font_weight,
            'axes.labelsize': font_size,
            'lines.linewidth': plot_lw,
            'lines.linestyle': translate_linestyle(plot_style, 'matplotlib'),   # 非标准写法在构造时报错
            'legend.fontsize': legend_fontsize,
            'legend.frameon': False,
            'xtick.major.width': ticker_width,
            'ytick.major.width': ticker_width,
            'xtick.minor.width': ticker_width,
            'ytick.minor.width': ticker_width
        }

        self.dataset: DataSet = input_dataset
        self.groups = groups  # 只读：通过 names / sample_ids / options 读取，不修改
        self.data = self.dataset.data
        self.sample_idx = self.dataset.sample_idx
        self.column = self.dataset.column
        self.axesset: dict = {}
        self.plotrange = plotrange
        self.plotdataRowNum_x = plotdataRowNum_x
        self.plotdataRowNum_y = plotdataRowNum_y
        self.cmap = resolved_cmap
        self.figsize = figsize  # None：各绘图方法用自己的默认尺寸
        # 样品号 → 色带位置，按整个数据集排名一次：
        # 样品号不连续也不越界，且同一样品在分组绘图的各张图里颜色一致
        self.color_positions = color_positions(self.sample_idx)

    # ========================================================================
    # 数据与绘制
    # ========================================================================

    # 取数（按样品号 + 通道号取 X、Y）与 InteractivePlotter 共用：plot_common.get_xy_data

    def _draw_figure(self, spec: FigureSpec, plot_kind: str, figsize: tuple,
                     neglog_x: bool = False, neglog_y: bool = False,
                     axes_formatter=None, lines_formatter=None, legend_formatter=None):
        """
        按一张 FigureSpec 画出一张图，返回 (fig, ax, {样品号: artist})。

        只读计划，不读 Group：画哪些线、颜色（色带位置）、样式都由计划决定（plot_common.plan_figures）。
        顺序：建图 → 画线（色带色）→ 分组样式（仅折线，覆盖色带色和 plot_style）
              → 默认格式 → 用户 formatter（优先级最高）→ 负对数刻度。
        整段在 rc_context 里执行：plot_style、字号等默认值靠它生效。
        neglog 只影响这里的刻度文字；取绝对值已在生成计划时做过。
        """
        with plt.rc_context(self.rc_params):
            fig, ax = plt.subplots(figsize=figsize)
            artists = {}    # {样品号: artist}；样品名可能重复，所以用样品号作键

            for curve in spec.curves:
                artist = self._plot_data(ax, curve.x, curve.y, plot_kind,
                                         color=self.cmap(curve.color_position), label=curve.label)
                # 分组样式：写了就应用（scatter / bar 暂不支持，见 STRUCTURE_REVIEW 4.3 的遗留问题）
                if plot_kind == 'line' and curve.style:
                    artist.set(**self._native_style(curve.style))  # type: ignore[union-attr]
                artists[curve.sample_idx] = artist

            # 同一通道的单位在所有样品里相同（DataSet._channel_units_unify_check），取任意一条即可
            units = spec.curves[-1]
            self._default_plot_formatter(ax, fig, plot_kind=plot_kind,
                                         x_axislabel=units.x_unit, y_axislabel=units.y_unit)
            self._apply_optional_formatters(
                ax=ax, fig=fig, lines=list(artists.values()), legends=[ax.get_legend()],
                axes_formatter=axes_formatter,
                lines_formatter=lines_formatter,
                legend_formatter=legend_formatter
            )
            self._apply_neglog_formatter(ax, neglog_x, neglog_y)

        return fig, ax, artists




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
    # 默认格式化
    # ========================================================================

    def _default_plot_formatter(self, ax, fig, plot_kind='line', x_axislabel=None, y_axislabel=None):
        """应用默认绘图格式。"""
        # 先配置线条再建图例：图例句柄保存的是创建时的线条样式
        if plot_kind == 'line':
            self._configure_lines(ax)
        self._set_plot_legends(ax)
        self._configure_xaxis(ax, x_axislabel)
        self._configure_yaxis(ax, y_axislabel)
        self._configure_figures(fig)

    def _set_plot_legends(self, ax, draggable=True, loc='center left',
                          bbox_to_anchor=(1, 0.5), **kwargs):
        """配置图例样式。"""
        leg = ax.legend(loc=loc, bbox_to_anchor=bbox_to_anchor, **kwargs)
        if draggable:
            leg.set_draggable(True)

    def _configure_xaxis(self, ax, x_axislabel=None):
        """配置 X 轴样式。"""
        ax.set_xlabel(x_axislabel)
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.2f}"))
        ax.xaxis.set_tick_params(which='both', width=self.rc_params['xtick.major.width'], direction='out')

    def _configure_yaxis(self, ax, y_axislabel=None):
        """配置 Y 轴样式。"""
        ax.set_ylabel(y_axislabel)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.2f}"))
        ax.tick_params(axis='y', which='both', width=self.rc_params['ytick.major.width'], direction='out')

    def _configure_lines(self, ax):
        """
        把 ax 上全部线条设为默认线宽。
        （一张图就是计划里的一张 FigureSpec，图上的线就是这张图的全部线，不再需要按分组挑；
          分组的线型、标记、颜色在 _draw_figure 画线时由 _native_style 设置。）
        """
        default_lw = self.rc_params.get('lines.linewidth', 3)
        for line in ax.get_lines():
            line.set_linewidth(default_lw)

    @staticmethod
    def _native_style(style: dict) -> dict:
        """
        把计划里的样式（CurveSpec.style，标准写法）翻译成 matplotlib 原生值：
        {'linestyle': 'dash'} → {'linestyle': '--'}。没写的字段本来就不在字典里。
        后端只读计划、不读 Group：样式在生成计划时已从 Group 取出，这里只负责翻译。
        """
        translators = {'linestyle': translate_linestyle, 'marker': translate_marker, 'color': translate_color}
        return {field: translators[field](value, 'matplotlib') for field, value in style.items()}

    def _configure_figures(self, fig):
        """配置图形布局。"""
        fig.subplots_adjust(right=0.75)

    def _default_yy_formatter(self, ax, fig, x_axislabel=None, y_axislabel=None):
        """Y-Y 子图默认格式化。"""
        ax.legend(loc='lower right')
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.4f}"))
        ax.set_xlabel(x_axislabel)
        ax.set_ylabel(y_axislabel)
        fig.subplots_adjust(left=0.15)

    def _default_xyy_formatter(self, ax1, ax2, fig,
                               X1_axislabel=None, Y1_axislabel=None, Y2_axislabel=None):
        """X-YY 双轴图默认格式化。"""
        ax1.legend(loc='lower right')
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.4f}"))
        ax1.set_xlabel(X1_axislabel)  # type: ignore
        ax1.set_ylabel(Y1_axislabel, color='red')  # type: ignore
        ax2.set_ylabel(Y2_axislabel, color='blue')  # type: ignore
        ax1.tick_params(axis='y', labelcolor='red', color='red')
        ax2.tick_params(axis='y', labelcolor='blue', color='blue')
        ax1.spines['left'].set_color('red')
        ax2.spines['right'].set_color('blue')
        fig.subplots_adjust(right=0.85)

    # ========================================================================
    # 用户格式化 & 负对数格式化
    # ========================================================================

    def _apply_optional_formatters(self, ax, fig, lines, legends,
                                   axes_formatter, lines_formatter, legend_formatter):
        """应用用户自定义格式化器。"""
        if axes_formatter is not None:
            axes_formatter(ax, fig)
        if lines_formatter is not None:
            lines_formatter(lines)
            # 图例句柄是创建时的样式快照，线条样式变更后需重建图例
            legends = [self._refresh_legend(ax)]
        if legend_formatter is not None:
            legend_formatter(legends)

    def _refresh_legend(self, ax):
        """按原图例的位置和拖拽设置重建图例；原本无图例则不新建。"""
        old = ax.get_legend()
        if old is None:
            return None
        # matplotlib 未提供 loc 的公开 getter，只能读取 _loc
        new = ax.legend(loc=old._loc, bbox_to_anchor=old.get_bbox_to_anchor())
        new.set_draggable(old.get_draggable())
        return new

    def _apply_neglog_formatter(self, ax, NegLogScale_x: bool, NegLogScale_y: bool):
        """为坐标轴添加负号前缀（用于负对数刻度显示）。"""
        # 两轴必须用各自的变量：lambda 在绘图时才执行，若共用一个变量，
        # X 轴的 lambda 会读到后来被 Y 分支覆盖的 Y 轴格式器（闭包晚绑定）
        if NegLogScale_x:
            x_formatter = ax.xaxis.get_major_formatter()
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda x, pos: f"-{x_formatter(x, pos)}"))
        if NegLogScale_y:
            y_formatter = ax.yaxis.get_major_formatter()
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda y, pos: f"-{y_formatter(y, pos)}"))
        return ax

    # ========================================================================
    # 绘图方法
    # ========================================================================

    def plot_objects(self,
                     axes_formatter=None,
                     lines_formatter=None,
                     legend_formatter=None,
                     NegLogScale_x: bool = False,
                     NegLogScale_y: bool = False,
                     plot_kind: str = 'line',
                     ) -> DataPlotter:
        """
        绘制多线图。

        将所有样品绘制在同一坐标系中，每个样品一条线。

        Parameters
        ----------
        axes_formatter : callable, optional
            坐标轴格式化函数，签名 (ax, fig) -> None。
        lines_formatter : callable, optional
            线条格式化函数，签名 (lines: list[Line2D]) -> None。
        legend_formatter : callable, optional
            图例格式化函数，签名 (legends: list[Legend]) -> None。
        NegLogScale_x : bool
            是否对 X 轴应用负对数刻度。
        NegLogScale_y : bool
            是否对 Y 轴应用负对数刻度。
        plot_kind : str
            绘图类型：'line' / 'scatter' / 'bar'。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
            axesset = {'main': {'ax', 'fig', 'artists': [artist, ...]}}（artists 是列表，6.5 统一形状）
        """
        # 不分组（groups=None）：一张 'main' 图，全部样品；不看 self.groups
        [spec] = plan_figures(self.dataset, None, self.plotdataRowNum_x, self.plotdataRowNum_y,
                              plotrange=self.plotrange, neglog_x=NegLogScale_x, neglog_y=NegLogScale_y)

        fig, ax, artists = self._draw_figure(
            spec, plot_kind, figsize=self.figsize or (10, 8),
            neglog_x=NegLogScale_x, neglog_y=NegLogScale_y,
            axes_formatter=axes_formatter, lines_formatter=lines_formatter, legend_formatter=legend_formatter,
        )

        self.axesset = {'main': {'ax': ax, 'fig': fig, 'artists': list(artists.values())}}

        return self

    def group_plotter(self,
                      NegLogScale_x: bool = False,
                      NegLogScale_y: bool = False,
                      axes_formatter=None,
                      lines_formatter=None,
                      legend_formatter=None,
                      merge_groups: bool = False,
                      plot_kind: str = 'line',
                      ) -> DataPlotter:
        """
        分组绘图。

        按 self.groups（Group 对象）将数据分组绘制，支持合并或分离模式。

        Parameters
        ----------
        NegLogScale_x : bool
            是否对 X 轴应用负对数刻度。
        NegLogScale_y : bool
            是否对 Y 轴应用负对数刻度。
        axes_formatter : callable, optional
            坐标轴格式化函数。
        lines_formatter : callable, optional
            线条格式化函数。
        legend_formatter : callable, optional
            图例格式化函数。
        merge_groups : bool
            True: 所有组合并到一张图；False: 每组单独一张图。
            合并模式下，被多个组引用的样品只画一次，使用第一个包含它的组的样式。
        plot_kind : str
            绘图类型：'line' / 'scatter' / 'bar'。

        分组样式
        --------
        分组配置里写了 linestyle / marker / color 就应用（两种模式一样，仅 plot_kind='line'）；
        color 写了时这组所有样品都用它。没写时：线型用 plot_style；颜色在分离模式按样品配色，
        合并模式统一为组首色。优先级：默认样式 < 分组样式 < lines_formatter。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
            分离模式：axesset = {组名: {'ax', 'fig', 'artists': {样品号: artist}}}
            合并模式：axesset = {'main': {'ax', 'fig', 'artists': {样品号: artist}}}
        """
        if not self.groups.names:
            return self.plot_objects(
                plot_kind=plot_kind,
                NegLogScale_x=NegLogScale_x,
                NegLogScale_y=NegLogScale_y,
                axes_formatter=axes_formatter,
                lines_formatter=lines_formatter,
                legend_formatter=legend_formatter,
            )

        # 分组规则（去重、先到先得、组首色、样式归属）都在计划里；合并模式的计划只有一张 'main' 图，
        # 所以两种模式走同一个循环
        figures = plan_figures(self.dataset, self.groups, self.plotdataRowNum_x, self.plotdataRowNum_y,
                               merge_groups=merge_groups, plotrange=self.plotrange,
                               neglog_x=NegLogScale_x, neglog_y=NegLogScale_y)
        self.axesset = {}
        for spec in figures:
            fig, ax, artists = self._draw_figure(
                spec, plot_kind, figsize=self.figsize or (16, 12),
                neglog_x=NegLogScale_x, neglog_y=NegLogScale_y,
                axes_formatter=axes_formatter, lines_formatter=lines_formatter, legend_formatter=legend_formatter,
            )
            self.axesset[spec.key] = {'ax': ax, 'fig': fig, 'artists': artists}

        return self

    def subplotter_yy(self,
                      axes_formatter=None,
                      lines_formatter=None,
                      legend_formatter=None,
                      plot_kind: str = 'line',
                      NegLogScale_Y1: bool = False,
                      NegLogScale_Y2: bool = False,
                      plotdataRowNum_Y1: int = dataRowNum_unit2,
                      plotdataRowNum_Y2: int = dataRowNum_unit4) -> DataPlotter:
        """
        绘制 Y-Y 关系图。

        为每个样品创建独立的 Y-Y 图，用于展示两个变量的相关性（如 Nyquist 图）。

        Parameters
        ----------
        axes_formatter : callable, optional
            坐标轴格式化函数。
        lines_formatter : callable, optional
            线条格式化函数。
        legend_formatter : callable, optional
            图例格式化函数。
        plot_kind : str
            绘图类型：'line' / 'scatter' / 'bar'。
        NegLogScale_Y1 : bool
            是否对 Y1 轴（X 方向）应用负对数刻度。
        NegLogScale_Y2 : bool
            是否对 Y2 轴（Y 方向）应用负对数刻度。
        plotdataRowNum_Y1 : int
            Y1 数据的通道号（样品内的列序号）。
        plotdataRowNum_Y2 : int
            Y2 数据的通道号（样品内的列序号）。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
            axesset = {样品号:{'artist', 'ax', 'fig'}}
        """
        self.axesset = {}

        with plt.rc_context(self.rc_params):
            for i in sorted(set(self.sample_idx)):
                fig, ax = plt.subplots(figsize=(12, 8))

                Row_Y1, Row_Y2, Y1_label, _, Y1_unit, Y2_unit = get_xy_data(self.dataset, plotrange=self.plotrange,
                    sample_idx=i,
                    channel_x=plotdataRowNum_Y1,
                    channel_y=plotdataRowNum_Y2,
                    neglog_x=NegLogScale_Y1,
                    neglog_y=NegLogScale_Y2
                )
                artist = self._plot_data(ax, Row_Y1, Row_Y2, plot_kind, label=Y1_label)

                self._default_yy_formatter(ax, fig, x_axislabel=Y1_unit, y_axislabel=Y2_unit)
                self._apply_optional_formatters(
                    ax=ax, fig=fig, lines=[artist], legends=[ax.get_legend()],
                    axes_formatter=axes_formatter,
                    lines_formatter=lines_formatter,
                    legend_formatter=legend_formatter
                )
                self._apply_neglog_formatter(ax, NegLogScale_Y1, NegLogScale_Y2)

                # 以样品号为键：不同样品的列名可能相同，用标签作键会互相覆盖
                self.axesset[i] = {'artist': artist, 'ax': ax, 'fig': fig}

        return self

    def subplotter_xyy(self,
                       axes_formatter_ax1=None,
                       axes_formatter_ax2=None,
                       lines_formatter_ax1=None,
                       lines_formatter_ax2=None,
                       legend_formatter_ax1=None,
                       legend_formatter_ax2=None,
                       NegLogScale_X1: bool = False,
                       NegLogScale_X2: bool = False,
                       NegLogScale_Y1: bool = False,
                       NegLogScale_Y2: bool = False,
                       plot_kind_Y1: str = 'line',
                       plot_kind_Y2: str = 'line',
                       custom_formatter=None,
                       plotdataRowNum_X1: int = dataRowNum_unit1,
                       plotdataRowNum_Y1: int = dataRowNum_unit2,
                       plotdataRowNum_X2: int = dataRowNum_unit3,
                       plotdataRowNum_Y2: int = dataRowNum_unit4) -> DataPlotter:
        """
        绘制 X-YY 双轴图。

        为每个样品创建共享 X 轴的双 Y 轴图，用于显示不同量纲的变量（如位移和电压）。

        Parameters
        ----------
        axes_formatter_ax1 : callable, optional
            左 Y 轴格式化函数。
        axes_formatter_ax2 : callable, optional
            右 Y 轴格式化函数。
        lines_formatter_ax1 : callable, optional
            左 Y 轴线条格式化函数。
        lines_formatter_ax2 : callable, optional
            右 Y 轴线条格式化函数。
        legend_formatter_ax1 : callable, optional
            左 Y 轴图例格式化函数。
        legend_formatter_ax2 : callable, optional
            右 Y 轴图例格式化函数。
        NegLogScale_X1 : bool
            是否对 X1 轴应用负对数刻度。
        NegLogScale_X2 : bool
            是否对 X2 轴应用负对数刻度。
        NegLogScale_Y1 : bool
            是否对 Y1 轴应用负对数刻度。
        NegLogScale_Y2 : bool
            是否对 Y2 轴应用负对数刻度。
        plot_kind_Y1 : str
            左 Y 轴绘图类型：'line' / 'scatter' / 'bar'。
        plot_kind_Y2 : str
            右 Y 轴绘图类型：'line' / 'scatter' / 'bar'。
        custom_formatter : callable, optional
            自定义格式化函数，签名 (ax1, ax2, fig) -> None。
        plotdataRowNum_X1 : int
            X1 数据的通道号（样品内的列序号）。
        plotdataRowNum_Y1 : int
            Y1 数据的通道号（样品内的列序号）。
        plotdataRowNum_X2 : int
            X2 数据的通道号（样品内的列序号）。
        plotdataRowNum_Y2 : int
            Y2 数据的通道号（样品内的列序号）。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
            axesset = {样品号:{'artist_Y1', 'artist_Y2', 'ax1', 'ax2', 'fig'}}
        """
        self.axesset = {}

        with plt.rc_context(self.rc_params):
            for i in sorted(set(self.sample_idx)):
                fig, ax1 = plt.subplots(figsize=(12, 8))

                Row_X1, Row_Y1, _, Y1_label, X1_unit, Y1_unit = get_xy_data(self.dataset, plotrange=self.plotrange,
                    sample_idx=i,
                    channel_x=plotdataRowNum_X1,
                    channel_y=plotdataRowNum_Y1,
                    neglog_x=NegLogScale_X1,
                    neglog_y=NegLogScale_Y1
                )
                Row_X2, Row_Y2, _, Y2_label, _, Y2_unit = get_xy_data(self.dataset, plotrange=self.plotrange,
                    sample_idx=i,
                    channel_x=plotdataRowNum_X2,
                    channel_y=plotdataRowNum_Y2,
                    neglog_x=NegLogScale_X2,
                    neglog_y=NegLogScale_Y2
                )

                # 左轴（红）
                artist_Y1 = self._plot_data(ax1, Row_X1, Row_Y1, plot_kind_Y1,
                                            color='red', label=Y1_label)
                # 右轴（蓝），与左轴共享 X 轴
                ax2 = ax1.twinx()
                artist_Y2 = self._plot_data(ax2, Row_X2, Row_Y2, plot_kind_Y2,
                                            color='blue', label=Y2_label)

                self._default_xyy_formatter(ax1, ax2, fig, X1_axislabel=X1_unit,
                                            Y1_axislabel=Y1_unit, Y2_axislabel=Y2_unit)
                self._apply_optional_formatters(
                    ax=ax1, fig=fig, lines=[artist_Y1], legends=[ax1.get_legend()],
                    axes_formatter=axes_formatter_ax1,
                    lines_formatter=lines_formatter_ax1,
                    legend_formatter=legend_formatter_ax1,
                )
                self._apply_optional_formatters(
                    ax=ax2, fig=fig, lines=[artist_Y2], legends=[ax2.get_legend()],
                    axes_formatter=axes_formatter_ax2,
                    lines_formatter=lines_formatter_ax2,
                    legend_formatter=legend_formatter_ax2,
                )
                if custom_formatter is not None:
                    custom_formatter(ax1, ax2, fig)

                self._apply_neglog_formatter(ax1, NegLogScale_X1, NegLogScale_Y1)
                self._apply_neglog_formatter(ax2, NegLogScale_X2, NegLogScale_Y2)

                # 以样品号为键：不同样品的列名可能相同，用标签作键会互相覆盖
                self.axesset[i] = {'artist_Y1': artist_Y1, 'artist_Y2': artist_Y2,
                                   'ax1': ax1, 'ax2': ax2, 'fig': fig}

        return self
