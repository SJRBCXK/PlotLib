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
from .interactive import InteractivePlotter

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
    'InteractivePlotter',
]
