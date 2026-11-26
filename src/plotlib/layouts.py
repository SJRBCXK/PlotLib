"""
定义 Matplotlib 和 Plotly 共用的版式预设。

`LAYOUTS` 定义各版式的图例、边框、轴样式和边距。图例和边框按库默认值、版式预设、
``DataPlotter`` 全局设置的顺序合并，后者覆盖前者。
"""
from dataclasses import dataclass, field

from .plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, Appearance, AxisStyle, FrameStyle, Layout, LegendStyle)


@dataclass(frozen=True)
class LayoutPreset:
    """
    一种版式的默认排版。

    Parameters
    ----------
    legend : LegendStyle, default: LegendStyle()
        整图图例，包含所有坐标轴上的绘图对象。
    frame : FrameStyle, default: FrameStyle()
        上边框和右边框的样式。
    axes : dict
        ``{轴名: AxisStyle}``，各轴的刻度格式和着色。轴名 ``'x'``、``'y'`` 是左轴的横轴和纵轴，``'y2'`` 是双 Y 轴的右轴。
        轴颜色应用于轴标题、刻度和轴线，以及该轴上未单独指定颜色的曲线。
    margins : dict
        Matplotlib 绘图区边界在画布中的相对位置，例如 ``{'right': 0.75}``。
        Plotly 自动为图外图例预留空间。
    """
    legend: LegendStyle = LegendStyle()
    frame: FrameStyle = FrameStyle()
    axes: dict[str, AxisStyle] = field(default_factory=dict)
    margins: dict[str, float] = field(default_factory=dict)


# 两个后端均通过左轴回调配置整图图例。
NO_LEGEND_MESSAGE = ("这根轴没有单独的图例：一张图只有一个图例，归左轴；"
                     "图例回调请放在左侧（AxesFormatter(legend=...) 给 'left'，不要给 'right'）")


# Matplotlib 的 multiline 和 xy 版式按默认图尺寸、字号和 Y 轴标签格式预留固定左边距。
# 自定义图尺寸或使用较长的刻度标签时，可缩短标签格式或扩大左边距。
LAYOUTS: dict[Layout, LayoutPreset] = {
    # X 轴由后端自动选择标签格式，保留对数轴上较小的数值。
    'multiline': LayoutPreset(
        legend=LegendStyle(position='outside right', draggable=True),
        axes={'y': AxisStyle(format='{y:.2f}')},
        margins={'left': 0.18, 'right': 0.75},
    ),
    'xy': LayoutPreset(
        legend=LegendStyle(position='lower right'),
        axes={'y': AxisStyle(format='{y:.4f}')},
        margins={'left': 0.18},
    ),
    # 双 Y 轴的颜色区分对应曲线，顶部为图外图例预留空间。
    'dual_y': LayoutPreset(
        legend=LegendStyle(position='outside top right'),
        frame=FrameStyle(top=True, right=True),
        axes={'y': AxisStyle(color='red'), 'y2': AxisStyle(format='{y:.4f}', color='blue')},
        margins={'right': 0.85, 'top': 0.85},
    ),
    # 柱状图沿用默认图例样式。后端为类别轴设置刻度。
    'bars': LayoutPreset(),
}


def resolve_legend(preset: LayoutPreset, appearance: Appearance) -> LegendStyle:
    """
    按库默认值、版式预设、全局设置的顺序合并图例样式。

    Parameters
    ----------
    preset : LayoutPreset
        这张图所用版式的预设。
    appearance : Appearance
        ``DataPlotter`` 的全局外观设置。

    Returns
    -------
    LegendStyle
        合并后的图例样式。
    """
    return DEFAULT_LEGEND.updated(preset.legend).updated(appearance.legend)


def resolve_frame(preset: LayoutPreset, appearance: Appearance) -> FrameStyle:
    """
    按库默认值、版式预设、全局设置的顺序合并边框样式。

    Parameters
    ----------
    preset : LayoutPreset
        这张图所用版式的预设。
    appearance : Appearance
        ``DataPlotter`` 的全局外观设置。

    Returns
    -------
    FrameStyle
        合并后的边框样式。
    """
    return DEFAULT_FRAME.updated(preset.frame).updated(appearance.frame)
