"""
PlotLib：多样品实验数据的读取、计算和批量绘图库，同一套代码可输出 matplotlib 静态图或 Plotly 交互图。

典型流程是「读数据 → 选列、计算 → 分组 → 画图」：

- `Dataloader`：读取按样品排列的数据文件，得到 `DataSet`；
- `DataSet`：按「样品 × 通道」组织的数据容器；
- `DataProcessLayer`：按样品、列名、单位选列；
- `DataTransformer`：逐样品计算（自定义函数、范数）；
- `Group`：样品分组，用于分组绘图和逐分组计算；
- `DataPlotter`：唯一的绘图入口，画多线图、分组图、x-y 图、双 Y 轴图；
- `LineStyle`、`AxisStyle`、`FrameStyle`、`LegendStyle`、`TickStyle`：线、坐标轴、边框、图例、刻度的样式；
- `make_axes_formatter`、`make_lines_formatter`、`make_legend_formatter`：单根轴、单条线、图例的格式化回调。

Examples
--------
>>> from plotlib import Dataloader, DataPlotter, AxisStyle, make_axes_formatter
>>> data = Dataloader(columns_per_sample=4).load_data('eis.csv')
>>> fmt = make_axes_formatter(x=AxisStyle(scale='log'))
>>> DataPlotter(data, channel_x=0, channel_y=1).plot_multiline(axes_formatter=fmt)
"""
from .dataset import DataSet
from .dataloader import Dataloader, NoFileSelected
from .processor import DataProcessLayer, DataTransformer
from .plotter import DataPlotter
from .formatters import (
    combine_formatters,
    make_axes_formatter,
    make_legend_formatter,
    make_lines_formatter,
)
from .group import Group
from .plan import color_positions
from .plot_spec import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle

__all__ = [
    'DataSet',
    'Dataloader',
    'NoFileSelected',
    'DataProcessLayer',
    'DataTransformer',
    'DataPlotter',
    'make_axes_formatter',
    'make_lines_formatter',
    'make_legend_formatter',
    'combine_formatters',
    'Group',
    # 样式对象（2026-11-20）
    'AxisStyle',
    'FrameStyle',
    'LegendStyle',
    'LineStyle',
    'TickStyle',
]
# 交互图（Plotly）用 DataPlotter(..., backend='plotly')；Plotly 后端在用到时才导入，没装 Plotly 也能用其余部分。

