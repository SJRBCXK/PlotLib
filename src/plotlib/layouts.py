"""
排版预设（STRUCTURE_REVIEW 6.6b）：每种版式（FigureSpec.layout）的默认排版，用样式对象写（2026-11-20 样式对象化）。

以前这些设置写死在 matplotlib 后端的三个 _default_*_formatter 里；抽成数据后：
  - 后端只剩一段画法，三种版式的差别全在这里；
  - matplotlib、Plotly 读同一份预设，各自翻译（样式对象的写法见 plot_spec.py，翻译在 style.py）。

叠加顺序（resolve_* 是唯一写这个顺序的地方）：
    库默认 DEFAULT_* < 版式预设（这里）< DataPlotter(...) 全局 < 分组样式 < 用户 formatter
用户在 DataPlotter 里明确写的盖过预设：全局写了就对所有版式生效，不会被某个版式悄悄盖掉。
"""
from dataclasses import dataclass, field

from .plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, Appearance, AxisStyle, FrameStyle, Layout, LegendStyle)


@dataclass(frozen=True)
class LayoutPreset:
    """一种版式的默认排版。轴名：'x'、'y' 是左轴的横、纵轴，'y2' 是右轴（双 Y 轴）。"""
    legend: LegendStyle = LegendStyle()     # 图例：一张图一个，建在左轴上，收所有轴上的线
    frame: FrameStyle = FrameStyle()        # 边框：画不画上 / 右边
    axes: dict[str, AxisStyle] = field(default_factory=dict)   # 轴名 → 刻度格式、轴着色（着色时轴标题、刻度、轴线同色；
                                                               #   挂在这根轴上、又没有别的颜色来源的线也用它）
    margins: dict[str, float] = field(default_factory=dict)    # 绘图区边界占画布的比例，如 {'right': 0.75}（给图外图例让位）


# 一张图只有一个图例，归左轴（两个后端一样）：给其他轴配图例回调时，两个后端报同一条错（第三方审查 E，用户定报错）
NO_LEGEND_MESSAGE = ("这根轴没有单独的图例：一张图只有一个图例，归左轴；"
                     "图例格式请交给 legend_formatter（双 Y 轴不要用 right_legend_formatter）")


LAYOUTS: dict[Layout, LayoutPreset] = {
    # 多线图：线多，图例放图外右侧、可拖动；坐标两位小数；无框（默认）
    'multiline': LayoutPreset(
        legend=LegendStyle(position='outside right', draggable=True),
        axes={'x': AxisStyle(format='{x:.2f}'), 'y': AxisStyle(format='{y:.2f}')},
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
    """这张图的图例：库默认 < 版式预设 < DataPlotter 全局。"""
    return DEFAULT_LEGEND.updated(preset.legend).updated(appearance.legend)


def resolve_frame(preset: LayoutPreset, appearance: Appearance) -> FrameStyle:
    """这张图的边框：库默认 < 版式预设 < DataPlotter 全局。"""
    return DEFAULT_FRAME.updated(preset.frame).updated(appearance.frame)
