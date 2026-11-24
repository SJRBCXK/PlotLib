"""
多样品实验数据处理和批量绘图。

PlotLib 按样品和通道组织数据，并通过共同的绘图接口生成 Matplotlib 静态图或 Plotly 交互图。
主要接口包括：

- `Dataloader`：读取按样品排列的数据文件，得到 `DataSet`；
- `DataSet`：按「样品 × 通道」组织的数据容器；
- `DataProcessLayer`：按样品、列名、单位选列；
- `DataTransformer`：逐样品计算（自定义函数、范数、每列汇总成一个值）；
- `Group`：样品分组，用于分组绘图和逐分组计算（含组内汇总）；
- `DataPlotter`：`plot` 画曲线类的图（全部样品、按分组、每样品一张；折线、散点；单 / 双 Y 轴），`Layer` 写每层画什么；
  `plot_bars` 画柱状图（类别 × 系列，并排或堆叠，误差棒）；
- `LineStyle`、`ScatterStyle`、`BarStyle`、`AxisStyle`、`FrameStyle`、`LegendStyle`、`TickStyle`：
  折线、散点、柱状图、坐标轴、边框、图例、刻度的样式；
- `make_axes_formatter`、`make_lines_formatter`、`make_scatter_formatter`、`make_bar_formatter`、`make_legend_formatter`：
  单根轴、折线、散点、柱状图、图例的格式化回调。

Examples
--------
>>> from plotlib import Dataloader, DataPlotter, AxesFormatter, AxisStyle, make_axes_formatter
>>> data = Dataloader(columns_per_sample=4).load_data('eis.csv')
>>> fmt = make_axes_formatter(x=AxisStyle(scale='log'))
>>> DataPlotter(data, channel_x=0, channel_y=1).plot(formatters=AxesFormatter(axes=fmt))
"""
from .dataset import DataSet
from .dataloader import Dataloader, NoFileSelected
from .processor import DataProcessLayer, DataTransformer
from .plotter import DataPlotter
from .formatters import (
    combine_formatters,
    make_axes_formatter,
    make_bar_formatter,
    make_legend_formatter,
    make_lines_formatter,
    make_scatter_formatter,
)
from .group import Group
from .plan import color_positions
from .plot_spec import (AxesFormatter, AxisStyle, BarStyle, FrameStyle, Layer, LegendStyle, LineStyle, ScatterStyle,
                        TickStyle)

__all__ = [
    'DataSet',
    'Dataloader',
    'NoFileSelected',
    'DataProcessLayer',
    'DataTransformer',
    'DataPlotter',
    'make_axes_formatter',
    'make_lines_formatter',
    'make_scatter_formatter',
    'make_bar_formatter',
    'make_legend_formatter',
    'combine_formatters',
    'Group',
    # 绘图的图层与按轴回调
    'Layer',
    'AxesFormatter',
    # 公共样式对象
    'AxisStyle',
    'FrameStyle',
    'LegendStyle',
    'LineStyle',
    'ScatterStyle',
    'BarStyle',
    'TickStyle',
]

