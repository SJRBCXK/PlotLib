"""PlotLib - 科学数据绘图库。"""
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    # 仅供类型检查和编辑器补全；运行时由下面的 __getattr__ 按需导入。
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
    # InteractivePlotter 不放进 __all__：没装 Plotly 时 `from plotlib import *` 会因它失败。
]


def __getattr__(name: str):
    """首次访问 plotlib.InteractivePlotter 时才导入，让 Plotly 保持为可选依赖。"""
    if name == 'InteractivePlotter':
        try:
            from .interactive import InteractivePlotter
        except ModuleNotFoundError as exc:
            raise ImportError(
                'InteractivePlotter 需要 Plotly，请安装可选依赖：pip install -e ".[interactive]"'
            ) from exc
        return InteractivePlotter
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
