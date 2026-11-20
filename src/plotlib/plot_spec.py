"""
绘图约定（STRUCTURE_REVIEW 6.4 ~ 6.7；2026-11-20 从 plot_common.py 拆出）：入口、计划、后端之间传递的数据类型。

  - 样式对象（2026-11-20 样式对象化）：LineStyle、AxisStyle、FrameStyle、LegendStyle、TickStyle，以及各自的库默认值 DEFAULT_*；
  - CurveSpec / FigureSpec：计划（画什么），由 plan.py 生成，交给后端；
  - DrawnFigure：后端画完交回的结果；
  - Appearance、AxesFormatter：随计划一起交给后端的配置（冻结，创建后不可改）。

不含任何规则、不导入任何绘图库。后端只依赖这里（以及 layouts.py、style.py），不依赖 plan.py 的规则。

分层：属于「一条线」的放 CurveSpec，属于「一张图」的放 FigureSpec。
左右轴跨两层——「这条线挂在哪根轴上」是线的属性（CurveSpec.axis），
「那根轴的单位、刻度」是图的属性（FigureSpec.y2_unit、neglog）。
"""
from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace
from typing import Any, Literal, Self

import numpy as np

type CurveKind = Literal['line', 'scatter', 'bar']
type Axis = Literal['left', 'right']
type Layout = Literal['multiline', 'xy', 'dual_y']


# ══════════════════════════════════════════════
# 样式对象（2026-11-20，用户提出「格式参数再加一层抽象」）
#
# 一个主题一个冻结 dataclass，用标准写法（style.py 的词汇），长度、宽度、字号的单位是磅；
# 由翻译层 style.translate_* 换成各后端原生值（Plotly 按 dpi 把磅换成像素）。
# 字段为 None 表示「不改，沿用上一层」，用 updated 一层层叠加：
#     库默认 DEFAULT_* < 版式预设（layouts.py）< DataPlotter(...) 全局 < 分组样式 < 单轴 formatter
# 用户明确写的盖过库的默认安排：全局写了就对所有版式生效，不会被某个版式的预设悄悄盖掉。
# ══════════════════════════════════════════════
class StyleLayer:
    """样式对象的公共部分：在这一层上叠加另一层。"""

    def updated(self, other: Self | None) -> Self:
        """other 写了的字段（不是 None）覆盖，没写的沿用这一层；other 为 None 时原样返回。"""
        if other is None:
            return self
        return replace(self, **{f.name: getattr(other, f.name) for f in fields(other)   # type: ignore[arg-type]
                                if getattr(other, f.name) is not None})


@dataclass(frozen=True)
class LineStyle(StyleLayer):
    """
    线（原 DataPlotter 的 line_width / linestyle、线条工厂的 linewidth / linecolor / linestyle / linemarker / linemarkersize、
    分组样式三个字段，合成一个）。用在：DataPlotter(lines=...) 全局、分组配置、make_lines_formatter(LineStyle(...))。
    不是每种画法都看得见每个字段：style.STYLE_FIELDS_BY_KIND（折线全有，散点只有标记，柱状图都没有；颜色另算，三种都有）。
    """
    width: float | None = None          # 线宽（磅）
    color: str | tuple | None = None    # 颜色：CSS 颜色名、'#rrggbb'、RGB 三个 0~255 的整数
    linestyle: str | tuple | None = None    # 'solid'、'dash'、'dot'、'dashdot'，或自定义虚线 (实线长, 空白长, ...)
    marker: str | None = None           # 'circle'、'square'、'triangle-up'、'triangle-down'、'diamond'、'cross'、'x'
    marker_size: float | None = None    # 标记大小（磅）


type AxisScale = Literal['linear', 'log', 'symlog', 'logit']    # 'symlog'、'logit' 只有 matplotlib


@dataclass(frozen=True)
class AxisStyle(StyleLayer):
    """
    一个方向的轴（原轴工厂的 xlim_* / ylim_*、xscale_type / yscale_type、x_format / y_format、xscaler / yscaler，
    以及排版预设的刻度格式、轴着色）。x、y、右侧 y 各用一个：make_axes_formatter(x=AxisStyle(...), y=AxisStyle(...))。
    """
    scale: AxisScale | None = None      # 刻度类型；None 不改（不会重置已有的刻度格式）
    limits: tuple[float | None, float | None] | None = None    # (下限, 上限)，某一侧写 None 表示那一侧自动
    format: str | None = None           # 刻度文字格式，如 '{x:.2f}'、'{y:.1e}'
    scaler: float | None = None         # 刻度文字显示值 = 刻度值 × scaler，不改数据（只有 matplotlib）
    color: str | tuple | None = None    # 轴着色：轴标题、刻度、轴线同色（双 Y 轴左红右蓝）


@dataclass(frozen=True)
class FrameStyle(StyleLayer):
    """
    边框（原 DataPlotter 的 axis_width、轴工厂的 hide_spines）。左边和下边的轴线总是有的；
    top / right 管上、右两条边：默认不画（用户定），双 Y 轴的预设画完整的框（左右各有一根轴，不封口太难看）。
    """
    width: float | None = None          # 轴线宽（磅）
    top: bool | None = None             # 画不画上边框
    right: bool | None = None           # 画不画右边框（双 Y 轴的右轴自己有轴线，不受它影响）


@dataclass(frozen=True)
class LegendStyle(StyleLayer):
    """
    图例（原 DataPlotter 的 legend_font_size、图例工厂的 legend_*、排版预设的图例位置和能否拖动）。
    position 的写法见 style.LEGEND_POSITIONS（图内 'upper left' 等，图外 'outside right'、'outside top right'）。
    """
    position: str | None = None
    font_size: float | None = None      # 字号（磅）；图例标题同字号
    frame: bool | None = None           # 有没有边框（和白色底）
    draggable: bool | None = None       # 能不能用鼠标拖动（只有 matplotlib 的交互窗口；Plotly 在显示时设置）


type TickDirection = Literal['out', 'in']          # Plotly 没有跨在轴线两侧的刻度，标准写法只有这两种
type MinorLabels = Literal['none', 'short', 'full']


@dataclass(frozen=True)
class TickStyle(StyleLayer):
    """
    刻度（2026-11-20 用户提出）：主 / 次刻度的线和文字（原 tick_width 并入 width）。
    用在：DataPlotter(ticks=...) 全局、make_axes_formatter(ticks=...) 单根轴。

    minor_labels：次刻度写什么——'none' 不写；'short' 对数轴只写首位数字（2、5，Plotly 的 'small digits'），
        线性轴上不写；'full' 写完整数值。Plotly 只有对数轴的次刻度能写文字，线性轴上的 'full' 只有 matplotlib 生效。
    minor_label_*：次刻度文字单独的字体、字号、间距（不写时与主刻度文字相同）；只有 matplotlib 支持，Plotly 报错。
    """
    direction: TickDirection | None = None      # 朝外 / 朝内（主、次刻度一起）
    length: float | None = None                 # 主刻度长
    width: float | None = None                  # 主刻度宽
    minor: bool | None = None                   # 是否显示次刻度
    minor_length: float | None = None
    minor_width: float | None = None
    label_font: str | None = None               # 刻度文字的字体；不写时沿用外观的 font_family
    label_size: float | None = None             # 刻度文字的字号；不写时沿用外观的 font_size
    label_pad: float | None = None              # 刻度文字离刻度线的距离
    minor_labels: MinorLabels | None = None
    minor_label_font: str | None = None
    minor_label_size: float | None = None
    minor_label_pad: float | None = None


# 库默认值（最底下一层）
DEFAULT_LINES = LineStyle(width=3, linestyle='solid', marker_size=6)
DEFAULT_FRAME = FrameStyle(width=3, top=False, right=False)                 # 默认无框（用户定）
DEFAULT_LEGEND = LegendStyle(position='upper right', font_size=10, frame=False, draggable=False)
# 刻度：朝外，主刻度 6 × 3 磅，显示次刻度 3 × 3 磅（用户定：默认显示，可关），次刻度不写文字
DEFAULT_TICKS = TickStyle(direction='out', length=6, width=3, minor=True,
                          minor_length=3, minor_width=3, minor_labels='none')


# ══════════════════════════════════════════════
# 计划与结果
# ══════════════════════════════════════════════
@dataclass
class CurveSpec:
    """一条线。颜色存色带位置、样式存标准写法（LineStyle），翻译成具体颜色值 / 原生写法是后端的事。"""
    sample_idx: int
    x: np.ndarray
    y: np.ndarray
    label: str                  # 图例文字：样品名；双 Y 轴是这条线的单位（样品名在图例标题里）
    group_name: str | None      # 不分组时为 None
    color_position: float | None    # 默认颜色在色带上的位置（合并模式已换成组首位置）；None：用后端默认色
    style: LineStyle = field(default_factory=LineStyle)     # 分组写了的样式；没写的字段为 None
    kind: CurveKind = 'line'    # 画法（原 plot_kind）
    axis: Axis = 'left'         # 挂在哪根 Y 轴上；只有双 Y 轴图有 'right'


@dataclass
class FigureSpec:
    """一张图。curves 的顺序就是画线顺序，也就是图例顺序。"""
    key: str | int              # 分组名或 'main'；xy、双 Y 轴图是样品号
    curves: list[CurveSpec]
    x_unit: str                 # 轴标题：同一通道的单位在各样品间一致，所以属于图，不属于线
    y_unit: str
    y2_unit: str | None = None  # 右轴单位；只有双 Y 轴图有
    neglog: frozenset[str] = frozenset()    # 哪些轴的刻度补负号：'x'、'y'、'x2'（上轴，拼图时用）、'y2'
    layout: Layout = 'multiline'   # 按哪套默认排版画（6.6 起由排版预设决定具体设置）
    legend_title: str | None = None     # 图例标题（2026-11-20）；None 不加。计划里已是最终文字，后端照画
    name: str | None = None     # 这张图自己的名字（6.8）：每个样品一张图时是样品名，分离模式是组名，只有一张图时 None；
                                #   legend_title 里的 '{name}' 换成它，Plotly 翻页滑块的档位标签也用它


@dataclass
class DrawnFigure:
    """
    按一张 FigureSpec 画出的结果（STRUCTURE_REVIEW 6.5）。两个后端、四种绘图方法同一形状，
    绘图器把它们存成 {spec.key: DrawnFigure}。

    artists 与 spec.curves 一一对应、顺序相同（不按样品号作键：双 Y 轴图里同一样品有左右两条线）；
    按样品号取线用 artist(样品号, 轴)。
    """
    spec: FigureSpec            # 这张图的计划：画了什么都能查到
    fig: Any                    # matplotlib 的 Figure；Plotly 多张计划时各页共用同一个 Figure（6.8，翻页）
    axes: dict[str, Any]        # {'left': ax}，双 Y 轴再有 'right'；Plotly 没有轴对象（6.7 定）
    artists: list               # 曲线对象（Line2D / PathCollection / BarContainer / trace）

    def artist(self, sample_idx: int, axis: Axis = 'left'):
        """这张图里样品 sample_idx 挂在 axis 轴上的那条线；没有则 KeyError。"""
        for curve, artist in zip(self.spec.curves, self.artists):
            if curve.sample_idx == sample_idx and curve.axis == axis:
                return artist
        raise KeyError(f"图 {self.spec.key!r} 里没有样品 {sample_idx} 挂在 {axis} 轴上的线")


# ══════════════════════════════════════════════
# 随计划交给后端的配置
# ══════════════════════════════════════════════
@dataclass(frozen=True)
class Appearance:
    """
    外观（STRUCTURE_REVIEW 6.6）：后端无关的全局设置，创建后不可改；由各后端翻译（matplotlib → rc_params 等，Plotly → 模板）。
    字号的单位是磅（1/72 英寸）；dpi 是每英寸像素数，后端用它把磅、英寸换成像素（style.translate_points / translate_figsize）。

    lines / frame / legend / ticks 存的是用户在 DataPlotter 里写的那一层（没写的字段为 None），
    后端画图时按「库默认 < 版式预设 < 这一层」叠加（2026-11-20 样式对象化：原 line_width、linestyle、axis_width、
    legend_font_size、tick_width 都并进了这几个对象）。
    """
    font_family: str = 'Arial'
    font_size: int = 22
    font_weight: str = 'bold'
    lines: LineStyle = LineStyle()
    frame: FrameStyle = FrameStyle()
    legend: LegendStyle = LegendStyle()
    ticks: TickStyle = TickStyle()
    dpi: float = 100            # 显式的渲染分辨率（6.7）；100 也是 matplotlib 的默认值


@dataclass(frozen=True)
class AxesFormatter:
    """一根轴上的一组用户回调（STRUCTURE_REVIEW 6.6）；没给的是 None。按轴组成 {'left': ..., 'right': ...} 交给后端。"""
    axes: Callable[..., Any] | None = None
    lines: Callable[..., Any] | None = None
    legend: Callable[..., Any] | None = None
