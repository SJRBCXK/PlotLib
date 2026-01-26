"""科学数据绘图模块。"""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from . import processor as DataProcessor
from .dataset import DataSet

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
    plot_lines()
        标准多线图，所有数据组绘制在同一坐标系。
    group_plotter()
        分组绘图，支持合并或分离模式。
    subplotter_yy()
        Y-Y 关系图，绘制两个变量的相关性（如 Nyquist 图）。
    subplotter_xyy()
        X-YY 双轴图，共享 X 轴的双 Y 轴显示。

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
    >>> plotter.plot_lines(NegLogScale_y=True)
    >>> plt.show()
    """

    def __init__(
        self,
        input_dataset: DataSet,
        plot_data_groups: dict | None = None,
        cmap=None,
        font_family: str = 'Arial',
        font_size: int = 22,
        font_weight: str = 'bold',
        axis_lw: int = 3,
        plot_lw: int = 3,
        plot_style: str = '-',
        plotrange: int | None = None,
        plotdataRowNum_x: int = dataRowNum_unit1,
        plotdataRowNum_y: int = dataRowNum_unit2,
        legend_fontsize: int = 10,
        ticker_width: int = 3,
        num_datagroups: int | None = None
    ):
        """
        初始化绘图器。

        Parameters
        ----------
        input_dataset : DataSet
            输入数据集，包含 data、names、units 等属性。
        plot_data_groups : dict, optional
            分组配置，格式：{'组名': {'num': [索引列表], 'linestyle': '-'}, ...}
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
            X 轴数据的组内列索引。
        plotdataRowNum_y : int
            Y 轴数据的组内列索引。
        legend_fontsize : int
            图例字体大小。
        ticker_width : int
            刻度线宽度。
        num_datagroups : int, optional
            数据组数量，None 则从 dataset 自动获取。
        """

        # 从 dataset 中获取数据组数量（如果未提供）
        if num_datagroups is None:
            num_datagroups = input_dataset.num_datagroups

        # 处理默认参数（避免可变默认参数问题）
        if plot_data_groups is None:
            plot_data_groups = {}
        if cmap is None:
            cmap = plt.cm.plasma  # type: ignore

        # 存储样式设置为 rcParams 字典（用于 plt.rc_context）
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

        # 绑定数据集属性
        self.dataset: DataSet = input_dataset
        self.groups_config = plot_data_groups
        self.data = self.dataset.data
        self.units = self.dataset.units
        self.names = self.dataset.names
        self.groups_idx = self.dataset.groups_idx
        self.group_local_idx = self.dataset.group_local_idx
        self.column = self.dataset.column
        self.line_objects: list = []
        self.plotrange = plotrange
        self.plotdataRowNum_x = plotdataRowNum_x
        self.plotdataRowNum_y = plotdataRowNum_y
        self.cmap = cmap
        self.num_datagroups = num_datagroups

        # 计算每组列数
        self.COLUMNS_PER_DATASET = int(self.dataset.data.shape[1] / self.num_datagroups)
        self.DATASET_FRACTION = self.num_datagroups / self.dataset.data.shape[1]

    # ========================================================================
    # 绘图方法
    # ========================================================================

    def plot_lines(self,
                   axes_formatter=None,
                   lines_formatter=None,
                   legend_formatter=None,
                   NegLogScale_x: bool = False,
                   NegLogScale_y: bool = False) -> 'DataPlotter':
        """
        绘制多线图。

        将所有数据组绘制在同一坐标系中，每组一条线。

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

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
        """
        with plt.rc_context(self.rc_params):
            self.fig, self.ax = plt.subplots(figsize=(10, 8))

            if self.data is None or self.column is None:
                raise RuntimeError("未加载数据")
            
            

            # Use all data points if plotrange not specified
            if self.plotrange is None:
                self.plotrange = self.data.shape[0]

            # Initialize storage for Line2D objects (for future style modifications)
            self.line_objects = []

            with plt.rc_context(self.rc_params):
                for i in sorted(set(self.groups_idx)):
                    
                    Row_x,_,x_unit = self._get_column_data(
                    group_idx=i, 
                    group_local_idx=self.plotdataRowNum_x,
                    plotrange=self.plotrange)#type: ignore
                    
                    Row_y, y_label, y_unit = self._get_column_data(
                    group_idx=i, 
                    group_local_idx=self.plotdataRowNum_y, 
                    plotrange=self.plotrange)#type: ignore


                    # Get color from colormap (evenly distributed)
                    colors = self.cmap(i / self.num_datagroups)

                    if NegLogScale_x:
                        Row_x = np.abs(Row_x)
                    if NegLogScale_y:
                        Row_y = np.abs(Row_y)

                    line = self.ax.plot(
                    Row_x,
                    Row_y,
                    color=colors,
                    label=y_label  # 直接绑定标签到线条对象
                    )[0]

                    # Store Line2D object for later modification
                    self.line_objects.append(line)


                self._default_plot_formatter(self.ax, self.fig, x_aixlabel=x_unit, y_aixlabel=y_unit)
            
                self._apply_optional_formatters(
                    ax = self.ax, fig = self.fig, lines = self.line_objects, legends = [self.ax.get_legend()],
                    axes_formatter = axes_formatter,
                    lines_formatter = lines_formatter,
                    legend_formatter = legend_formatter
                )   
                
                self._apply_neglog_formatter(self.ax, NegLogScale_x, NegLogScale_y)

        return self
    



    def _get_column_data(self, group_idx: int, group_local_idx: int, plotrange: int):
        """根据组索引和组内索引获取列数据。"""
        for column in self.column:
            if column['group_idx'] == group_idx and column['group_local_idx'] == group_local_idx:
                return column['data'][0:plotrange], column['name'], column['unit']
        raise RuntimeError("未找到对应的列数据")

    # ========================================================================
    # 内部格式化方法
    # ========================================================================

    def _default_plot_formatter(self, ax, fig, group_name=None, x_aixlabel=None, y_aixlabel=None):
        """应用默认绘图格式。"""
        self._set_plot_legends(ax, fig)
        self._configure_xaxis(ax, fig, x_aixlabel=x_aixlabel)
        self._configure_yaxis(ax, fig, y_aixlabel=y_aixlabel)
        self._configure_lines(ax, fig, group_name)
        self._configure_figures(ax, fig)

    def _set_plot_legends(self, ax, fig, draggable=True, loc='center left',
                          bbox_to_anchor=(1, 0.5), **kwargs):
        """配置图例样式。"""
        with plt.rc_context(self.rc_params):
            leg = ax.legend(loc=loc, bbox_to_anchor=bbox_to_anchor, **kwargs)
            if draggable:
                leg.set_draggable(True)



    def _configure_xaxis(self, ax, fig, x_aixlabel=None):  # noqa: ARG002
        """配置 X 轴样式。"""
        with plt.rc_context(self.rc_params):
            ax.set_xlabel(x_aixlabel)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:.2f}'))
            ax.xaxis.set_tick_params(which='both', width=3, direction='out')

    def _configure_yaxis(self, ax, fig, y_aixlabel=None):  # noqa: ARG002
        """配置 Y 轴样式。"""
        with plt.rc_context(self.rc_params):
            ax.set_ylabel(y_aixlabel)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.2f}"))
        ax.tick_params(axis='y', which='both', width=3, direction='out')

    def _configure_lines(self, ax, fig, group_name=None, **kwargs):  # noqa: ARG002
        """配置线条样式。"""
        default_lw = self.rc_params.get('lines.linewidth', 3)
        if group_name is None:
            for line in ax.get_lines():
                line.set_linewidth(default_lw)
        elif group_name in self.groups_config:
            group_config = self.groups_config[group_name]
            indices = group_config.get('num', [])
            for i in indices:
                line = self.groups_config[group_name]['members_datasets'][i]['line']
                line.set_linewidth(default_lw)

    def _configure_figures(self, ax, fig):  # noqa: ARG002
        """配置图形布局。"""
        fig.subplots_adjust(right=0.75)

    def group_plotter(self,
                      NegLogScale_x: bool = False,
                      NegLogScale_y: bool = False,
                      axes_formatter=None,
                      lines_formatter=None,
                      legend_formatter=None,
                      merge_groups: bool = False) -> 'DataPlotter':
        """
        分组绘图。

        根据 groups_config 配置将数据分组绘制，支持合并或分离模式。

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

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
        """
        if self.data is None or self.column is None:
            raise RuntimeError("数据为空")

        if self.plotrange is None:
            self.plotrange = self.data.shape[0]

        # Initialize fig and ax variables for type checking
        fig = None
        ax = None

        if merge_groups:
            with plt.rc_context(self.rc_params):
                fig, ax = plt.subplots(figsize=(16,12))
                self.fig, self.ax = fig, ax

        if not self.groups_config:
            if merge_groups and fig is not None:
                plt.close(fig)
            self.plot_lines(axes_formatter=axes_formatter,
                            lines_formatter=lines_formatter,
                            legend_formatter=legend_formatter)

            return self

        else:
            for group_name, group_config in self.groups_config.items():
                if 'num' not in group_config:
                    continue
                indices = group_config['num']

                # 初始化分组结构：分离配置和数据集
                self.groups_config[group_name]['members_datasets'] = {}
                self.groups_config[group_name]['axes'] = {}

                if not merge_groups:
                    with plt.rc_context(self.rc_params):
                        fig, ax = plt.subplots(figsize=(16,12))

                # Ensure ax is not None for type checking
                if ax is None:
                    raise RuntimeError("ax is None - this should not happen")

                with plt.rc_context(self.rc_params):
                    for i in indices:

                        colors = self.cmap(i / self.num_datagroups)

                        # 将数据集信息存储在 datasets 子字典中
                        self.groups_config[group_name]['members_datasets'][i] = {}
                        
                        Row_x,_,x_unit = self._get_column_data(
                        group_idx=i,
                        group_local_idx=self.plotdataRowNum_x,
                        plotrange=self.plotrange
                        )#type: ignore
                       
                        Row_y, y_label, y_unit = self._get_column_data(
                        group_idx=i,
                        group_local_idx=self.plotdataRowNum_y,
                        plotrange=self.plotrange
                        )#type: ignore

                        if NegLogScale_x:
                            Row_x = np.abs(Row_x)
                        if NegLogScale_y:
                            Row_y = np.abs(Row_y)

                        line = ax.plot(
                            Row_x,
                            Row_y,
                            color=colors,
                            label= y_label  # 直接绑定标签到线条对象
                        )[0]

                        if merge_groups:
                            colors = self.cmap(indices[0]/self.num_datagroups)
                            line.set_linestyle(group_config.get('linestyle', '-'))
                            line.set_color(colors)

                        self.groups_config[group_name]['members_datasets'][i]['legend'] = y_label
                        self.groups_config[group_name]['members_datasets'][i]['line'] = line

                # 只在分离模式下格式化（merge模式会在循环外统一格式化）
                if not merge_groups and fig is not None:
                    self._default_plot_formatter(ax, fig, 
                    group_name=group_name, x_aixlabel=x_unit, y_aixlabel=y_unit)

                    lines_objects = [
                        self.groups_config[group_name]['members_datasets'][i]['line']
                        for i in indices
                    ]

                    self._apply_optional_formatters(
                        ax = ax, fig = fig, lines = lines_objects, legends = [ax.get_legend()],
                        axes_formatter = axes_formatter,
                        lines_formatter = lines_formatter,
                        legend_formatter = legend_formatter
                    )

                    self._apply_neglog_formatter(ax, NegLogScale_x, NegLogScale_y)

                    self.groups_config[group_name]['axes']['ax'] = ax
                    self.groups_config[group_name]['axes']['fig'] = fig

            if merge_groups:
                # Ensure self.ax and self.fig are defined
                if not hasattr(self, 'ax') or self.ax is None or not hasattr(self, 'fig') or self.fig is None:
                    raise RuntimeError("self.ax or self.fig is not defined in merge_groups mode")

                self._default_plot_formatter(self.ax, self.fig, x_aixlabel=x_unit, y_aixlabel=y_unit)

                self._apply_optional_formatters(
                    ax = self.ax, fig = self.fig, lines = self.ax.get_lines(), legends = [self.ax.get_legend()],
                    axes_formatter = axes_formatter,
                    lines_formatter = lines_formatter,
                    legend_formatter = legend_formatter
                )

                self._apply_neglog_formatter(self.ax, NegLogScale_x, NegLogScale_y)

        return self

    # ========================================================================
    # 子图方法
    # ========================================================================

    def subplotter_yy(self,
                      axes_formatter=None,
                      lines_formatter=None,
                      legend_formatter=None,
                      NegLogScale_Y1: bool = False,
                      NegLogScale_Y2: bool = False,
                      plotdataRowNum_Y1: int = dataRowNum_unit2,
                      plotdataRowNum_Y2: int = dataRowNum_unit4) -> 'DataPlotter':
        """
        绘制 Y-Y 关系图。

        为每个数据组创建独立的 Y-Y 图，用于展示两个变量的相关性（如 Nyquist 图）。

        Parameters
        ----------
        axes_formatter : callable, optional
            坐标轴格式化函数。
        lines_formatter : callable, optional
            线条格式化函数。
        legend_formatter : callable, optional
            图例格式化函数。
        NegLogScale_Y1 : bool
            是否对 Y1 轴（X 方向）应用负对数刻度。
        NegLogScale_Y2 : bool
            是否对 Y2 轴（Y 方向）应用负对数刻度。
        plotdataRowNum_Y1 : int
            Y1 数据的组内列索引。
        plotdataRowNum_Y2 : int
            Y2 数据的组内列索引。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
        """
        if self.data is None:
            raise RuntimeError("先调用load(file_path)加载数据")

        self.plotdataRowNum_Y1 = plotdataRowNum_Y1
        self.plotdataRowNum_Y2 = plotdataRowNum_Y2

        if self.plotrange is None:
            self.plotrange = self.data.shape[0]

        self.subplotyy_axesset = {}

        with plt.rc_context(self.rc_params):
            for i in sorted(set(self.groups_idx)):
                # Create new figure for each dataset
                fig, ax = plt.subplots(figsize=(12, 8))

                # Calculate column indices
                Row_Y1, Y1_label, Y1_unit = self._get_column_data(
                    group_idx=i,
                    group_local_idx=self.plotdataRowNum_Y1,
                    plotrange=self.plotrange
                )  # type: ignore
                
                Row_Y2, Y2_label, Y2_unit = self._get_column_data(
                    group_idx=i,
                    group_local_idx=self.plotdataRowNum_Y2,
                    plotrange=self.plotrange
                )  # type: ignore


                self.subplotyy_axesset[Y1_label] = {}

                if NegLogScale_Y1:
                    Row_Y1 = np.abs(Row_Y1)

                if NegLogScale_Y2:
                    Row_Y2 = np.abs(Row_Y2)

                line = ax.plot(
                    Row_Y1,
                    Row_Y2,
                    label=Y1_label  # 直接绑定标签到线条对象
                )[0]

                self._default_yy_formatter(ax, fig, x_aixlabel=Y1_unit, y_aixlabel=Y2_unit)

                self._apply_optional_formatters(
                    ax = ax, fig = fig, lines = [line], legends= [ax.get_legend()],
                    axes_formatter = axes_formatter,
                    lines_formatter = lines_formatter,
                    legend_formatter = legend_formatter
                )

                self._apply_neglog_formatter(ax, NegLogScale_Y1, NegLogScale_Y2)

                self.subplotyy_axesset[Y1_label]['line'] = line
                self.subplotyy_axesset[Y1_label]['ax'] = ax
                self.subplotyy_axesset[Y1_label]['fig'] = fig

        return self

    def _default_yy_formatter(self, ax, fig, x_aixlabel=None, y_aixlabel=None):
        """Y-Y 子图默认格式化。"""
        ax.legend(loc='lower right')
        ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.4f}"))
        ax.set_xlabel(x_aixlabel)
        ax.set_ylabel(y_aixlabel)
        fig.subplots_adjust(left=0.15)

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
                       custom_formatter=None,
                       plotdataRowNum_X1: int = dataRowNum_unit1,
                       plotdataRowNum_Y1: int = dataRowNum_unit2,
                       plotdataRowNum_X2: int = dataRowNum_unit3,
                       plotdataRowNum_Y2: int = dataRowNum_unit4) -> 'DataPlotter':
        """
        绘制 X-YY 双轴图。

        为每个数据组创建共享 X 轴的双 Y 轴图，用于显示不同量纲的变量（如位移和电压）。

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
        custom_formatter : callable, optional
            自定义格式化函数，签名 (ax1, ax2, fig) -> None。
        plotdataRowNum_X1 : int
            X1 数据的组内列索引。
        plotdataRowNum_Y1 : int
            Y1 数据的组内列索引。
        plotdataRowNum_X2 : int
            X2 数据的组内列索引。
        plotdataRowNum_Y2 : int
            Y2 数据的组内列索引。

        Returns
        -------
        DataPlotter
            返回 self 以支持链式调用。
        """
        if self.data is None:
            raise RuntimeError("先调用load(file_path)加载数据")

        self.plotdataRowNum_X1 = plotdataRowNum_X1
        self.plotdataRowNum_Y1 = plotdataRowNum_Y1
        self.plotdataRowNum_X2 = plotdataRowNum_X2
        self.plotdataRowNum_Y2 = plotdataRowNum_Y2

        self.subplotxyy_axesset = {}

        if self.plotrange is None:
            self.plotrange = self.data.shape[0]

        with plt.rc_context(self.rc_params):
            for i in sorted(set(self.groups_idx)):
                # Create new figure for each dataset
                fig, ax1 = plt.subplots(figsize=(12, 8))

                # Calculate column indices first
                Row_X1, X1_label, X1_unit = self._get_column_data(
                    group_idx=i,
                    group_local_idx=self.plotdataRowNum_X1,
                    plotrange=self.plotrange
                )  # type: ignore
                Row_Y1, Y1_label, Y1_unit = self._get_column_data(
                    group_idx=i,
                    group_local_idx=self.plotdataRowNum_Y1,
                    plotrange=self.plotrange
                )  # type: ignore
                Row_X2, X2_label, X2_unit = self._get_column_data(
                    group_idx=i,
                    group_local_idx=self.plotdataRowNum_X2,
                    plotrange=self.plotrange
                )  # type: ignore
                Row_Y2, Y2_label, Y2_unit = self._get_column_data(
                    group_idx=i,
                    group_local_idx=self.plotdataRowNum_Y2,
                    plotrange=self.plotrange
                )  # type: ignore


                # Use col_X1 to create dictionary key
                self.subplotxyy_axesset[Y1_label] = {}



                if NegLogScale_X1:
                    Row_X1 = np.abs(Row_X1)
                if NegLogScale_Y1:
                    Row_Y1 = np.abs(Row_Y1)
                if NegLogScale_X2:
                    Row_X2 = np.abs(Row_X2)
                if NegLogScale_Y2:
                    Row_Y2 = np.abs(Row_Y2)

                # Plot displacement on left y-axis (red)
                line_Y1 = ax1.plot(
                    Row_X1,
                    Row_Y1,
                    color='red',
                    label=Y1_label
                )[0]

                # Create second y-axis for voltage (blue)
                ax2 = ax1.twinx()
                line_Y2 = ax2.plot(
                    Row_X2,
                    Row_Y2,
                    color='blue',
                    label=Y2_label
                )[0]

                self._default_xyy_formatter(ax1, ax2, fig,
                X1_aixlabel = X1_unit, Y1_aixlabel = Y1_unit, Y2_aixlabel = Y2_unit)

                self._apply_optional_formatters(
                    ax = ax1, fig = fig, lines = [line_Y1], legends = [ax1.get_legend()],
                    axes_formatter = axes_formatter_ax1,
                    lines_formatter = lines_formatter_ax1,
                    legend_formatter = legend_formatter_ax1,
                )
                self._apply_optional_formatters(
                    ax = ax2, fig = fig, lines = [line_Y2], legends = [ax2.get_legend()],
                    axes_formatter = axes_formatter_ax2,
                    lines_formatter = lines_formatter_ax2,
                    legend_formatter = legend_formatter_ax2,
                )
                if custom_formatter is not None:
                    custom_formatter(ax1, ax2, fig)

                self._apply_neglog_formatter(ax1, NegLogScale_X1, NegLogScale_Y1)
                self._apply_neglog_formatter(ax2, NegLogScale_X2, NegLogScale_Y2)

                self.subplotxyy_axesset[Y1_label]['line_Y1'] = line_Y1
                self.subplotxyy_axesset[Y1_label]['line_Y2'] = line_Y2
                self.subplotxyy_axesset[Y1_label]['ax1'] = ax1
                self.subplotxyy_axesset[Y1_label]['ax2'] = ax2
                self.subplotxyy_axesset[Y1_label]['fig'] = fig
        return self

    def _default_xyy_formatter(self, ax1, ax2, fig,
                               X1_aixlabel=None, Y1_aixlabel=None, Y2_aixlabel=None):
        """X-YY 双轴图默认格式化。"""
        ax1.legend(loc='lower right')
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.4f}"))
        ax1.set_xlabel(X1_aixlabel)  # type: ignore
        ax1.set_ylabel(Y1_aixlabel, color='red')  # type: ignore
        ax2.set_ylabel(Y2_aixlabel, color='blue')  # type: ignore
        ax1.tick_params(axis='y', labelcolor='red', color='red')
        ax2.tick_params(axis='y', labelcolor='blue', color='blue')
        ax1.spines['left'].set_color('red')
        ax2.spines['right'].set_color('blue')
        fig.subplots_adjust(right=0.85)

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _apply_neglog_formatter(self, ax, NegLogScale_x: bool, NegLogScale_y: bool):
        """为坐标轴添加负号前缀（用于负对数刻度显示）。"""
        if NegLogScale_x:
            original_formatter = ax.xaxis.get_major_formatter()
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda x, pos: f"-{original_formatter(x, pos)}"))
        if NegLogScale_y:
            original_formatter = ax.yaxis.get_major_formatter()
            ax.yaxis.set_major_formatter(
                FuncFormatter(lambda y, pos: f"-{original_formatter(y, pos)}"))
        return ax

    def _apply_optional_formatters(self, ax, fig, lines, legends,
                                   axes_formatter, lines_formatter, legend_formatter):
        """应用用户自定义格式化器。"""
        if axes_formatter is not None:
            axes_formatter(ax, fig)
        if lines_formatter is not None:
            lines_formatter(lines)
            self._set_plot_legends(ax, fig)
        if legend_formatter is not None:
            legend_formatter(legends)

