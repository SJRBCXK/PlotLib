"""
版式预设：每种版式（`FigureSpec.layout`）的默认排版，用样式对象写成数据。

三种版式的差别（图例位置、刻度格式、边框、双 Y 轴左红右蓝、边距）全部写在 `LAYOUTS` 里，
两个后端读同一份预设、各自翻译，后端本身只有一段画法。

Notes
-----
样式的叠加顺序只在本模块的 ``resolve_*`` 函数里写一次::

    库默认 DEFAULT_* < 版式预设（LAYOUTS）< DataPlotter(...) 全局 < 分组样式 < 用户 formatter

用户在 ``DataPlotter`` 里明确写的设置盖过预设：全局写了就对所有版式生效。
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
        图例。一张图只有一个图例，建在左轴上，收所有轴上的线。
    frame : FrameStyle, default: FrameStyle()
        边框：画不画上边、右边。
    axes : dict
        ``{轴名: AxisStyle}``，各轴的刻度格式和着色。轴名 ``'x'``、``'y'`` 是左轴的横轴和纵轴，``'y2'`` 是双 Y 轴的右轴。
        着色时轴标题、刻度和轴线同色；挂在这根轴上、又没有其他颜色来源的线也用这个颜色。
    margins : dict
        ``{边: 比例}``，绘图区边界占画布的比例，如 ``{'right': 0.75}`` （给图外的图例让位）。
        只有 matplotlib 使用，Plotly 会自动给图外的图例留边。
    """
    legend: LegendStyle = LegendStyle()     # 图例：一张图一个，建在左轴上，收所有轴上的线
    frame: FrameStyle = FrameStyle()        # 边框：画不画上 / 右边
    axes: dict[str, AxisStyle] = field(default_factory=dict)   # 轴名 → 刻度格式、轴着色（着色时轴标题、刻度、轴线同色；
                                                               #   挂在这根轴上、又没有别的颜色来源的线也用它）
    margins: dict[str, float] = field(default_factory=dict)    # 绘图区边界占画布的比例，如 {'right': 0.75}（给图外图例让位）


# 一张图只有一个图例，归左轴（两个后端一样）：给其他轴配图例回调时，两个后端报同一条错（第三方审查 E，用户定报错）
NO_LEGEND_MESSAGE = ("这根轴没有单独的图例：一张图只有一个图例，归左轴；"
                     "图例格式请交给 legend_formatter（双 Y 轴不要用 right_legend_formatter）")


LAYOUTS: dict[Layout, LayoutPreset] = {
    # 多线图：线多，图例放图外右侧、可拖动；纵轴两位小数；无框（默认）。
    # 横轴不写格式，交给后端自动：横轴常改成对数轴（频率），两位小数会把 1e-3 写成 0.00
    'multiline': LayoutPreset(
        legend=LegendStyle(position='outside right', draggable=True),
        axes={'y': AxisStyle(format='{y:.2f}')},
        margins={'right': 0.75},
    ),
    # x-y 单线图：只有一条线，图例放图内右下角；纵轴四位小数；无框（默认）
    'xy': LayoutPreset(
        legend=LegendStyle(position='lower right'),
        axes={'y': AxisStyle(format='{y:.4f}')},
        margins={'left': 0.15},
    ),
    # 双 Y 轴图：左红右蓝，轴和线同色，一眼看出哪条线读哪根轴；右轴四位小数。
    # 图例（2026-11-20 参照 Origin 图）：放图外上方、右对齐，两条线都在里面；上边给图例让位。
    # 完整的框（用户定：左右各有一根轴，不封口太难看）
    'dual_y': LayoutPreset(
        legend=LegendStyle(position='outside top right'),
        frame=FrameStyle(top=True, right=True),
        axes={'y': AxisStyle(color='red'), 'y2': AxisStyle(format='{y:.4f}', color='blue')},
        margins={'right': 0.85, 'top': 0.85},
    ),
}


def resolve_legend(preset: LayoutPreset, appearance: Appearance) -> LegendStyle:
    """
    算出一张图最终的图例样式：库默认 < 版式预设 < DataPlotter 全局。

    Parameters
    ----------
    preset : LayoutPreset
        这张图所用版式的预设。
    appearance : Appearance
        用户在 ``DataPlotter(...)`` 里写的外观。

    Returns
    -------
    LegendStyle
        每个字段都有值的图例样式（库默认值保证不缺字段）。
    """
    return DEFAULT_LEGEND.updated(preset.legend).updated(appearance.legend)


def resolve_frame(preset: LayoutPreset, appearance: Appearance) -> FrameStyle:
    """
    算出一张图最终的边框样式：库默认 < 版式预设 < DataPlotter 全局。

    Parameters
    ----------
    preset : LayoutPreset
        这张图所用版式的预设。
    appearance : Appearance
        用户在 ``DataPlotter(...)`` 里写的外观。

    Returns
    -------
    FrameStyle
        每个字段都有值的边框样式。
    """
    return DEFAULT_FRAME.updated(preset.frame).updated(appearance.frame)
