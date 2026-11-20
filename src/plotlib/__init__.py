"""PlotLib - 科学数据绘图库。"""
from .dataset import DataSet
from .dataloader import Dataloader
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

