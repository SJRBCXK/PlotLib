"""
绘图约定（STRUCTURE_REVIEW 6.4 ~ 6.7；2026-11-20 从 plot_common.py 拆出）：入口、计划、后端之间传递的数据类型。

  - CurveSpec / FigureSpec：计划（画什么），由 plan.py 生成，交给后端；
  - DrawnFigure：后端画完交回的结果；
  - Appearance、AxesFormatter：随计划一起交给后端的配置（冻结，创建后不可改）。

不含任何规则、不导入任何绘图库。后端只依赖这里（以及 layouts.py、style.py），不依赖 plan.py 的规则。

分层：属于「一条线」的放 CurveSpec，属于「一张图」的放 FigureSpec。
左右轴跨两层——「这条线挂在哪根轴上」是线的属性（CurveSpec.axis），
「那根轴的单位、刻度」是图的属性（FigureSpec.y2_unit、neglog）。
"""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

type CurveKind = Literal['line', 'scatter', 'bar']
type Axis = Literal['left', 'right']
type Layout = Literal['multiline', 'xy', 'dual_y']


@dataclass
class CurveSpec:
    """一条线。颜色存色带位置、样式存标准写法，翻译成具体颜色值 / 原生写法是后端的事。"""
    sample_idx: int
    x: np.ndarray
    y: np.ndarray
    label: str                  # 图例文字，现在是样品名
    group_name: str | None      # 不分组时为 None
    color_position: float | None    # 默认颜色在色带上的位置（合并模式已换成组首位置）；None：用后端默认色
    style: dict                 # 分组写了的样式（标准写法）；没写的不出现
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


@dataclass
class DrawnFigure:
    """
    按一张 FigureSpec 画出的结果（STRUCTURE_REVIEW 6.5）。两个后端、四种绘图方法同一形状，
    绘图器把它们存成 {spec.key: DrawnFigure}。

    artists 与 spec.curves 一一对应、顺序相同（不按样品号作键：双 Y 轴图里同一样品有左右两条线）；
    按样品号取线用 artist(样品号, 轴)。
    """
    spec: FigureSpec            # 这张图的计划：画了什么都能查到
    fig: Any                    # matplotlib 的 Figure；Plotly 分离模式下各页共用同一个 Figure（6.8）
    axes: dict[str, Any]        # {'left': ax}，双 Y 轴再有 'right'；Plotly 没有轴对象（6.7 定）
    artists: list               # 曲线对象（Line2D / PathCollection / BarContainer / trace）

    def artist(self, sample_idx: int, axis: Axis = 'left'):
        """这张图里样品 sample_idx 挂在 axis 轴上的那条线；没有则 KeyError。"""
        for curve, artist in zip(self.spec.curves, self.artists):
            if curve.sample_idx == sample_idx and curve.axis == axis:
                return artist
        raise KeyError(f"图 {self.spec.key!r} 里没有样品 {sample_idx} 挂在 {axis} 轴上的线")

@dataclass(frozen=True)
class Appearance:
    """
    外观（STRUCTURE_REVIEW 6.6）：后端无关的全局设置，创建后不可改；由各后端翻译（matplotlib → rc_params，Plotly → 模板）。
    字号、线宽、刻度宽的单位是磅（1/72 英寸）；dpi 是每英寸像素数，后端用它把磅、英寸换成像素（style.translate_points / translate_figsize）。
    """
    font_family: str = 'Arial'
    font_size: int = 22
    font_weight: str = 'bold'
    line_width: float = 3
    axis_width: float = 3
    linestyle: str|tuple = 'solid'
    legend_font_size: int = 10
    tick_width: float = 3
    dpi: float = 100            # 显式的渲染分辨率（6.7）；100 也是 matplotlib 的默认值


@dataclass(frozen=True)
class AxesFormatter:
    """一根轴上的一组用户回调（STRUCTURE_REVIEW 6.6）；没给的是 None。按轴组成 {'left': ..., 'right': ...} 交给后端。"""
    axes: Callable[..., Any] | None = None
    lines: Callable[..., Any] | None = None
    legend: Callable[..., Any] | None = None
