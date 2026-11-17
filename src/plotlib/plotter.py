"""科学数据绘图模块。"""
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from .dataset import DataSet
from .group import Group
from .plot_common import color_positions

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
        plot_style: str = '-',
        plotrange: int | None = None,
        plotdataRowNum_x: int = dataRowNum_unit1,
        plotdataRowNum_y: int = dataRowNum_unit2,
        legend_fontsize: int = 10,
        ticker_width: int = 3,
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
        plot_style : str
            线条样式。
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
        """
        # 一个绘图器只对应一个数据集和一个 Group，三种情况：
        if groups is None:
            # 不分组：用空 Group，后面的代码总是面对一个 Group，不用判断 None
            groups = Group(input_dataset, {})
        elif not isinstance(groups, Group):
            # 类型标注只在编辑器里提醒，运行时要自己检查，才能给出清楚的报错
            raise TypeError(
                f"groups 必须是 Group 对象，实际是 {type(groups).__name__}；"
                "请先用 Group(input_dataset, config) 创建。"
            )
        elif groups.dataset is not input_dataset:
            # 用 is 判断「是不是同一个对象」：内容相同的两个数据集也不算
            raise ValueError("groups 是基于另一个数据集创建的；请基于绘图用的数据集创建 Group。")

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
            'lines.linestyle': plot_style,
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
        self.plot_artists: list = []
        self.axesset: dict = {}
        self.plotrange = plotrange
        self.plotdataRowNum_x = plotdataRowNum_x
        self.plotdataRowNum_y = plotdataRowNum_y
        self.cmap = resolved_cmap
        # 样品号 → 色带位置，按整个数据集排名一次：
        # 样品号不连续也不越界，且同一样品在分组绘图的各张图里颜色一致
        self.color_positions = color_positions(self.sample_idx)

    # ========================================================================
    # 数据与绘制
    # ========================================================================

    def _ensure_ready(self):
        """确保绘图所需的数据已加载，并补全 plotrange。"""
        if self.data is None or self.column is None:
            raise RuntimeError("未加载数据")
        if self.plotrange is None:
            self.plotrange = self.data.shape[0]
        

    def _get_data(self, sample_idx: int, channel_x: int, channel_y: int,
                  neglog_x: bool = False, neglog_y: bool = False):
        """取出一个样品的 X、Y 两列，返回 (x, y, x_label, y_label, x_unit, y_unit)。"""
        Row_x, x_label, x_unit = self._get_column_data(sample_idx, channel_x, self.plotrange)
        Row_y, y_label, y_unit = self._get_column_data(sample_idx, channel_y, self.plotrange)

        if neglog_x:
            Row_x = np.abs(Row_x)
        if neglog_y:
            Row_y = np.abs(Row_y)

        return Row_x, Row_y, x_label, y_label, x_unit, y_unit

    def _get_column_data(self, sample_idx: int, channel_idx: int, plotrange: int | None):
        """根据样品号和通道号获取列数据，返回 (data, name, unit)。"""
        for column in self.column:
            if column['sample_idx'] == sample_idx and column['channel_idx'] == channel_idx:
                return column['data'][0:plotrange], column['name'], column['unit']
        raise RuntimeError("未找到对应的列数据")

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

    def _default_plot_formatter(self, ax, fig, plot_kind='line', group_name=None, artists=None,
                                apply_linestyle=False, x_axislabel=None, y_axislabel=None):
        """应用默认绘图格式。"""
        # 先配置线条再建图例：图例句柄保存的是创建时的线条样式
        if plot_kind == 'line':
            self._configure_lines(ax, group_name, artists, apply_linestyle)
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

    def _configure_lines(self, ax, group_name=None, artists=None, apply_linestyle=False):
        """
        配置线条样式。

        group_name 为 None 时处理 ax 上的全部线条；
        否则按 self.groups 中该分组的样品号和选项处理本组线条，artists 为 {样品号: artist}。
        apply_linestyle 为 True 时应用分组选项中的 linestyle。
        """
        default_lw = self.rc_params.get('lines.linewidth', 3)
        if group_name is None:
            for line in ax.get_lines():
                line.set_linewidth(default_lw)
        elif group_name in self.groups.names:
            if artists is None:
                raise ValueError("按组配置线条时必须传入 artists")
            options = self.groups.options(group_name)    # 每个分组取一次，循环里重复用
            for sample in self.groups.sample_ids(group_name):
                artist = artists[sample]
                artist.set_linewidth(default_lw)
                if apply_linestyle and 'linestyle' in options:  # 未配置时保留 rc 中的 plot_style
                    artist.set_linestyle(options['linestyle'])

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
        """
        self._ensure_ready()

        with plt.rc_context(self.rc_params):
            fig, ax = plt.subplots(figsize=(10, 8))
            self.plot_artists = []

            for i in sorted(set(self.sample_idx)):
                Row_x, Row_y, _, y_label, x_unit, y_unit = self._get_data(
                    sample_idx=i,
                    channel_x=self.plotdataRowNum_x,
                    channel_y=self.plotdataRowNum_y,
                    neglog_x=NegLogScale_x,
                    neglog_y=NegLogScale_y
                )
                artist = self._plot_data(
                    ax, Row_x, Row_y, plot_kind,
                    color=self.cmap(self.color_positions[i]),
                    label=y_label
                )
                self.plot_artists.append(artist)

            self._default_plot_formatter(ax, fig, plot_kind=plot_kind,
                                         x_axislabel=x_unit, y_axislabel=y_unit)
            self._apply_optional_formatters(
                ax=ax, fig=fig, lines=self.plot_artists, legends=[ax.get_legend()],
                axes_formatter=axes_formatter,
                lines_formatter=lines_formatter,
                legend_formatter=legend_formatter
            )
            self._apply_neglog_formatter(ax, NegLogScale_x, NegLogScale_y)

            self.axesset = {'main': {'ax': ax, 'fig': fig, 'artists': self.plot_artists}}

        return self

    def group_plotter(self,
                      NegLogScale_x: bool = False,
                      NegLogScale_y: bool = False,
                      axes_formatter=None,
                      lines_formatter=None,
                      legend_formatter=None,
                      merge_groups: bool = False,
                      plot_kind: str = 'line',
                      apply_group_linestyle: bool = False
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
        apply_group_linestyle : bool
            分离模式下是否应用各分组选项中的 linestyle（仅 plot_kind='line'）。
            合并模式始终应用组线型以区分各组，不受此参数影响。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
            分离模式：axesset = {组名: {'ax', 'fig', 'artists': {样品号: artist}}}
            合并模式：axesset = {'main': {'ax', 'fig', 'artists': {样品号: artist}}}
        """
        self._ensure_ready()

        if not self.groups.names:
            return self.plot_objects(axes_formatter=axes_formatter,
                                     lines_formatter=lines_formatter,
                                     legend_formatter=legend_formatter,
                                     NegLogScale_x=NegLogScale_x,
                                     NegLogScale_y=NegLogScale_y,
                                     plot_kind=plot_kind)

        # 分组配置在创建 Group 时已全部校验，这里不会因配置有误而留下残缺图窗

        # Initialize variables for type checking
        fig = None
        ax = None
        x_unit = y_unit = None

        self.axesset = {}
        merged_artists = {}  # merge 模式：所有组的 {样品号: artist}

        if merge_groups:
            with plt.rc_context(self.rc_params):
                fig, ax = plt.subplots(figsize=(16, 12))

        with plt.rc_context(self.rc_params):
            for group_name in self.groups:
                sample_ids = self.groups.sample_ids(group_name)
                options = self.groups.options(group_name)
                artists = {}  # {样品号: artist}

                if not merge_groups:
                    fig, ax = plt.subplots(figsize=(16, 12))

                # Ensure ax is not None for type checking
                if ax is None:
                    raise RuntimeError("ax is None - this should not happen")

                for sample in sample_ids:
                    # 合并模式：同一样品被多个组引用时只画一次（重画只会得到完全重合的线），
                    # 沿用第一个包含它的组的样式
                    if merge_groups and sample in merged_artists:
                        continue
                    Row_x, Row_y, _, y_label, x_unit, y_unit = self._get_data(
                        sample_idx=sample,
                        channel_x=self.plotdataRowNum_x,
                        channel_y=self.plotdataRowNum_y,
                        neglog_x=NegLogScale_x,
                        neglog_y=NegLogScale_y
                    )
                    artist = self._plot_data(
                        ax, Row_x, Row_y, plot_kind,
                        color=self.cmap(self.color_positions[sample]),
                        label=y_label
                    )

                    # 合并模式：同组统一为组首色 + 组线型（bar 无对应方法，保留各自颜色）
                    if merge_groups:
                        if hasattr(artist, 'set_linestyle'):
                            artist.set_linestyle(options.get('linestyle', '-'))  # type: ignore[union-attr]
                        if hasattr(artist, 'set_color'):
                            artist.set_color(self.cmap(self.color_positions[sample_ids[0]]))  # type: ignore[union-attr]

                    artists[sample] = artist

                merged_artists.update(artists)

                # 只在分离模式下格式化（merge模式会在循环外统一格式化）
                if not merge_groups and fig is not None:
                    self._default_plot_formatter(ax, fig, plot_kind=plot_kind,
                                                 group_name=group_name, artists=artists,
                                                 apply_linestyle=apply_group_linestyle,
                                                 x_axislabel=x_unit, y_axislabel=y_unit)
                    self._apply_optional_formatters(
                        ax=ax, fig=fig, lines=list(artists.values()), legends=[ax.get_legend()],
                        axes_formatter=axes_formatter,
                        lines_formatter=lines_formatter,
                        legend_formatter=legend_formatter
                    )
                    self._apply_neglog_formatter(ax, NegLogScale_x, NegLogScale_y)

                    self.axesset[group_name] = {'ax': ax, 'fig': fig, 'artists': artists}

            if merge_groups:
                if ax is None or fig is None:
                    raise RuntimeError("ax or fig is not defined in merge_groups mode")

                self._default_plot_formatter(ax, fig, plot_kind=plot_kind,
                                             x_axislabel=x_unit, y_axislabel=y_unit)
                self._apply_optional_formatters(
                    ax=ax, fig=fig, lines=list(merged_artists.values()), legends=[ax.get_legend()],
                    axes_formatter=axes_formatter,
                    lines_formatter=lines_formatter,
                    legend_formatter=legend_formatter
                )
                self._apply_neglog_formatter(ax, NegLogScale_x, NegLogScale_y)

                self.axesset = {'main': {'ax': ax, 'fig': fig, 'artists': merged_artists}}

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
        self._ensure_ready()
        self.axesset = {}

        with plt.rc_context(self.rc_params):
            for i in sorted(set(self.sample_idx)):
                fig, ax = plt.subplots(figsize=(12, 8))

                Row_Y1, Row_Y2, Y1_label, _, Y1_unit, Y2_unit = self._get_data(
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
        self._ensure_ready()
        self.axesset = {}

        with plt.rc_context(self.rc_params):
            for i in sorted(set(self.sample_idx)):
                fig, ax1 = plt.subplots(figsize=(12, 8))

                Row_X1, Row_Y1, _, Y1_label, X1_unit, Y1_unit = self._get_data(
                    sample_idx=i,
                    channel_x=plotdataRowNum_X1,
                    channel_y=plotdataRowNum_Y1,
                    neglog_x=NegLogScale_X1,
                    neglog_y=NegLogScale_Y1
                )
                Row_X2, Row_Y2, _, Y2_label, _, Y2_unit = self._get_data(
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
