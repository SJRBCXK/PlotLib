"""
排版预设（STRUCTURE_REVIEW 6.6b）：每种版式（FigureSpec.layout）的默认排版，用后端无关的写法存成数据。

以前这些设置写死在 matplotlib 后端的三个 _default_*_formatter 里；抽成数据后：
  - 后端只剩一段画法，三种版式的差别全在这里；
  - matplotlib、Plotly 读同一份预设，各自翻译（颜色用 style.py 的标准写法，刻度格式与 make_axes_formatter 相同）。

排版的优先级：外观（Appearance，全局）< 排版预设（按版式）< 分组样式（计划里的 style）< 用户 formatter。
"""
from dataclasses import dataclass, field
from typing import Literal

from .plot_spec import Layout

# 图例位置：'outside right' 图外右侧（竖直居中），'lower right' 图内右下角
type LegendPosition = Literal['outside right', 'lower right']


@dataclass(frozen=True)
class LayoutPreset:
    """一种版式的默认排版。轴名：'x'、'y' 是左轴的横、纵轴，'y2' 是右轴（双 Y 轴）。"""
    legend: LegendPosition                  # 图例位置；图例只放在左轴上
    legend_draggable: bool = False          # 图例能否用鼠标拖动（matplotlib 交互窗口里）
    tick_formats: dict[str, str] = field(default_factory=dict)   # 轴名 → 刻度文字格式，如 {'x': '{x:.2f}'}；没列的轴保留后端默认
    axis_colors: dict[str, str] = field(default_factory=dict)    # 轴名 → 颜色（标准写法）：轴标题、刻度、轴线着色；
                                                                 #   挂在这根轴上、又没有别的颜色来源的线也用它
    margins: dict[str, float] = field(default_factory=dict)      # 绘图区边界占画布的比例，如 {'right': 0.75}（给图外图例让位）


LAYOUTS: dict[Layout, LayoutPreset] = {
    # 多线图：线多，图例放图外右侧；坐标两位小数
    'multiline': LayoutPreset(
        legend='outside right', legend_draggable=True,
        tick_formats={'x': '{x:.2f}', 'y': '{y:.2f}'},
        margins={'right': 0.75},
    ),
    # x-y 单线图：只有一条线，图例放图内右下角；纵轴四位小数
    'xy': LayoutPreset(
        legend='lower right',
        tick_formats={'y': '{y:.4f}'},
        margins={'left': 0.15},
    ),
    # 双 Y 轴图：左红右蓝，轴和线同色，一眼看出哪条线读哪根轴；右轴四位小数
    'dual_y': LayoutPreset(
        legend='lower right',
        tick_formats={'y2': '{y:.4f}'},
        axis_colors={'y': 'red', 'y2': 'blue'},
        margins={'right': 0.85},
    ),
}
