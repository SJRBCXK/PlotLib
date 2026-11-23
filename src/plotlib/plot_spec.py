"""
绘图约定：入口（plotter）、计划（plan）和后端（backends）之间传递的数据类型。

本模块包含三类对象：

- **样式对象** `LineStyle`、`AxisStyle`、`FrameStyle`、`LegendStyle`、`TickStyle`，
  以及作为最底层默认值的 `DEFAULT_LINES`、`DEFAULT_FRAME`、`DEFAULT_LEGEND`、`DEFAULT_TICKS`；
- **计划与结果** `CurveSpec` （一条线）、`FigureSpec` （一张图）由 `plan` 生成并交给后端，
  `DrawnFigure` 是后端画完交回的结果；
- **随计划交给后端的配置** `Appearance` （全局外观）、`AxesFormatter` （一根轴上的用户回调）。

这里不含任何绘图规则，也不导入任何绘图库，后端只依赖本模块（以及 `layouts`、`style`）。

Notes
-----
分层原则：属于「一条线」的信息放在 `CurveSpec`，属于「一张图」的信息放在 `FigureSpec`。
左右 Y 轴横跨两层：「这条线挂在哪根轴上」是线的属性（`CurveSpec.axis`），
「那根轴的单位、刻度」是图的属性（`FigureSpec.y2_unit`、`FigureSpec.neglog`）。
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
    """
    样式对象的公共基类，提供「一层叠一层」的合并方法 `updated`。

    样式对象的每个字段默认为 None，表示「这一层不改，沿用下面一层」。
    库按以下顺序逐层叠加，越往后优先级越高::

        库默认 DEFAULT_* < 版式预设（layouts）< DataPlotter 全局 < 分组样式 < 单轴 formatter
    """

    def updated(self, other: Self | None) -> Self:
        """
        返回在本层之上叠加 *other* 之后的新样式对象。

        Parameters
        ----------
        other : 同类样式对象 or None
            上面一层。它写了的字段（不是 None）覆盖本层的值，没写的沿用本层。
            为 None 时原样返回本层。

        Returns
        -------
        同类样式对象
            叠加后的新对象；样式对象是冻结的，本层和 *other* 都不会被修改。

        Examples
        --------
        >>> base = LineStyle(width=3, linestyle='solid')
        >>> base.updated(LineStyle(linestyle='dash'))
        LineStyle(width=3, color=None, linestyle='dash', marker=None, marker_size=None)
        """
        if other is None:
            return self
        return replace(self, **{f.name: getattr(other, f.name) for f in fields(other)   # type: ignore[arg-type]
                                if getattr(other, f.name) is not None})


@dataclass(frozen=True)
class LineStyle(StyleLayer):
    """
    线的样式：线宽、颜色、线型、标记和标记大小。

    用在三处：``DataPlotter(lines=...)`` 对所有图生效；分组配置里的 ``linestyle`` /
    ``marker`` / ``color`` 由计划层装进 `LineStyle`；`~plotlib.formatters.make_lines_formatter`
    改单根轴上的线。所有字段都用标准写法（见 `plotlib.style`），长度单位是磅。

    Parameters
    ----------
    width : float, optional
        线宽（磅）。
    color : str or tuple of int, optional
        颜色：CSS 颜色名（如 ``'red'``）、``'#rrggbb'``，或三个 0~255 的整数 ``(r, g, b)``。
        ``DataPlotter(lines=...)`` 不收颜色，颜色按样品配色。
    linestyle : str or tuple of float, optional
        ``'solid'``、``'dash'``、``'dot'``、``'dashdot'``，或自定义虚线
        ``(实线长, 空白长, ...)`` （正数、偶数个，单位是线宽的倍数）。
    marker : str, optional
        ``'circle'``、``'square'``、``'triangle-up'``、``'triangle-down'``、``'diamond'``、
        ``'cross'``、``'x'``。
    marker_size : float, optional
        标记大小（磅）。

    Notes
    -----
    不是每种画法都看得见每个字段（见 ``style.STYLE_FIELDS_BY_KIND``）：折线全部生效；
    散点只有标记和标记大小；柱状图只有颜色。

    Examples
    --------
    >>> DataPlotter(data, lines=LineStyle(width=2, linestyle='dash'))
    >>> make_lines_formatter(LineStyle(color='red', marker='circle'))
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
    一个方向（X 或 Y）的坐标轴样式：刻度类型、范围、刻度文字格式、显示值缩放和着色。

    X、Y 各用一个对象：``make_axes_formatter(x=AxisStyle(...), y=AxisStyle(...))``；
    版式预设（`plotlib.layouts`）也用它写各轴的默认格式和颜色。

    Parameters
    ----------
    scale : {'linear', 'log', 'symlog', 'logit'}, optional
        刻度类型。``'symlog'``、``'logit'`` 只有 matplotlib 支持。
        不写时不改刻度类型，也就不会冲掉已有的刻度格式。
    limits : tuple of (float or None, float or None), optional
        坐标范围 ``(下限, 上限)``，写数据值（对数轴也一样）；某一侧写 None 表示这一侧自动。
        对数轴的边界必须大于 0。
    format : str, optional
        刻度文字格式，Python 格式字符串，用 ``x`` 或 ``y`` 作变量名，如 ``'{x:.2f}'``、``'{y:.1e}'``。
        Plotly 只支持 ``.Nf``、``.Ne``、``.Ng``、``.N%`` 四种。Plotly 的对数轴写了格式、
        次刻度又不写文字（``TickStyle.minor_labels='none'``，默认）时，主刻度只放在整数量级（``dtick=1``）；
        跨很多数量级嫌挤，可以在 ``custom`` 回调里自己设，如 ``fig.update_xaxes(dtick=2)`` 每两个量级一个。
    scaler : float, optional
        显示值缩放：刻度文字显示「刻度值 × scaler」，不修改数据。只有 matplotlib 支持。
    color : str or tuple of int, optional
        轴着色：轴标题、刻度和轴线用同一颜色（双 Y 轴预设用它做左红右蓝）。

    Examples
    --------
    >>> AxisStyle(scale='log', limits=(0.001, None), format='{x:.0e}')
    >>> AxisStyle(limits=(None, 0.002))
    """
    scale: AxisScale | None = None      # 刻度类型；None 不改（不会重置已有的刻度格式）
    limits: tuple[float | None, float | None] | None = None    # (下限, 上限)，某一侧写 None 表示那一侧自动
    format: str | None = None           # 刻度文字格式，如 '{x:.2f}'、'{y:.1e}'
    scaler: float | None = None         # 刻度文字显示值 = 刻度值 × scaler，不改数据（只有 matplotlib）
    color: str | tuple | None = None    # 轴着色：轴标题、刻度、轴线同色（双 Y 轴左红右蓝）


@dataclass(frozen=True)
class FrameStyle(StyleLayer):
    """
    绘图区边框：轴线宽度，以及上边、右边两条边画不画。

    左边和下边的轴线总是画出。库默认不画上边、右边；双 Y 轴的版式预设画完整的框，
    因为左右各有一根轴，不封口不美观。

    Parameters
    ----------
    width : float, optional
        轴线宽度（磅）。
    top : bool, optional
        是否画上边框。
    right : bool, optional
        是否画右边框。双 Y 轴图的右边就是右轴自己的轴线，不受这个开关影响。

    Examples
    --------
    >>> DataPlotter(data, frame=FrameStyle(width=2, top=True, right=True))
    """
    width: float | None = None          # 轴线宽（磅）
    top: bool | None = None             # 画不画上边框
    right: bool | None = None           # 画不画右边框（双 Y 轴的右轴自己有轴线，不受它影响）


@dataclass(frozen=True)
class LegendStyle(StyleLayer):
    """
    图例样式：位置、字号、边框和能否拖动。

    Parameters
    ----------
    position : str, optional
        图例位置。图内九个位置：``'upper right'``、``'upper left'``、``'lower right'``、
        ``'lower left'``、``'upper center'``、``'lower center'``、``'center left'``、
        ``'center right'``、``'center'``；``'best'`` （matplotlib 自动找空位，Plotly 放右上角）；
        图外两个位置：``'outside right'`` （右侧竖直居中）、``'outside top right'`` （上方右对齐）。
    font_size : float, optional
        字号（磅），图例标题用同一字号。
    frame : bool, optional
        是否画边框（和白色底）。
    draggable : bool, optional
        能否用鼠标拖动，只在 matplotlib 的交互窗口里有效。
        Plotly 的拖动是显示时的设置，见 `~plotlib.formatters.make_legend_formatter`。

    Examples
    --------
    >>> DataPlotter(data, legend=LegendStyle(position='upper left', font_size=12))
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
    刻度样式：主刻度、次刻度的线和文字。

    用在 ``DataPlotter(ticks=...)`` （所有图）和 ``make_axes_formatter(ticks=...)`` （单根轴）。
    长度、宽度、字号、间距的单位都是磅。

    Parameters
    ----------
    direction : {'out', 'in'}, optional
        刻度朝向，主刻度和次刻度一起改。
    length, width : float, optional
        主刻度的长度和宽度。
    minor : bool, optional
        是否显示次刻度。
    minor_length, minor_width : float, optional
        次刻度的长度和宽度。
    label_font : str, optional
        刻度文字的字体；不写时沿用全局字体。
    label_size : float, optional
        刻度文字的字号；不写时沿用全局字号。
    label_pad : float, optional
        刻度文字离刻度线的距离，可以为 0。
    minor_labels : {'none', 'short', 'full'}, optional
        次刻度写什么：``'none'`` 不写；``'short'`` 在对数轴上只写首位数字（如 2、5），
        线性轴上不写；``'full'`` 写完整数值。Plotly 只有对数轴的次刻度能写文字；
        Plotly 的对数轴写了刻度格式（``AxisStyle.format``）时不能用 ``'short'``，画图时报错。
    minor_label_font, minor_label_size, minor_label_pad : optional
        次刻度文字单独的字体、字号和间距；不写时与主刻度文字相同。
        只有 matplotlib 支持，在 Plotly 后端设置会报错。

    Examples
    --------
    >>> DataPlotter(data, ticks=TickStyle(length=8, minor=False))
    >>> make_axes_formatter(x=AxisStyle(scale='log'), ticks=TickStyle(minor_labels='short'))
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
    """
    绘图计划里的一条线：数据、图例文字、颜色来源、样式、画法和所在的轴。

    由 `plotlib.plan` 生成，后端照着画。颜色只存色带上的位置，样式只存标准写法，
    换成具体的颜色值和各绘图库的原生参数是后端的事。

    Parameters
    ----------
    sample_idx : int
        这条线所属的样品号。
    x, y : numpy.ndarray
        已取好的数据（负对数时已取绝对值，``plotrange`` 已截断）。
    label : str
        图例文字：一般是样品名；双 Y 轴图是这条线的单位（样品名在图例标题里）。
    group_name : str or None
        所属分组名；不分组时为 None。
    color_position : float or None
        默认颜色在色带上的位置（0 ~ 1）；合并模式下已换成组首样品的位置。
        None 表示不按色带取色（用版式预设的轴颜色或后端默认色）。
    style : LineStyle, default: LineStyle()
        分组写了的样式；没写的字段为 None。
    kind : {'line', 'scatter', 'bar'}, default: 'line'
        画法。
    axis : {'left', 'right'}, default: 'left'
        挂在哪根 Y 轴上；只有双 Y 轴图有 ``'right'``。
    """
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
    """
    绘图计划里的一张图：有哪些线、轴的单位、哪些轴补负号、用哪套版式。

    Parameters
    ----------
    key : str or int
        这张图在结果字典 ``DataPlotter.figures`` 里的键：分组名或 ``'main'``；
        xy 图、双 Y 轴图是样品号。
    curves : list of CurveSpec
        这张图的线。列表顺序就是画线顺序，也就是图例顺序。
    x_unit, y_unit : str
        X 轴、左 Y 轴的标题（通道单位）。同一通道的单位在各样品间一致，所以属于图而不属于线。
    y2_unit : str or None, default: None
        右 Y 轴的标题；只有双 Y 轴图有。
    neglog : frozenset of str, default: frozenset()
        哪些轴的刻度文字要补负号（负对数）：``'x'``、``'y'``、``'y2'``，
        以及预留给上轴的 ``'x2'``。
    layout : {'multiline', 'xy', 'dual_y'}, default: 'multiline'
        按哪套版式预设排版（见 `plotlib.layouts.LAYOUTS`）。
    legend_title : str or None, default: None
        图例标题，已是最终文字（``'{name}'`` 已替换）；None 表示不加标题。
    name : str or None, default: None
        这张图自己的名字：每个样品一张图时是样品名，分组分离模式是组名，只有一张图时为 None。
        Plotly 翻页滑块的档位标签用它。
    """
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
    按一张 `FigureSpec` 画出的结果。

    两个后端、四种绘图方法交回的结果形状相同，`~plotlib.plotter.DataPlotter` 把它们存成
    ``figures = {spec.key: DrawnFigure}``。

    Parameters
    ----------
    spec : FigureSpec
        这张图的计划，画了什么都能从这里查到。
    fig : `matplotlib.figure.Figure` or `plotly.graph_objects.Figure`
        原生的图对象。Plotly 画多张计划时，各页共用同一个 Figure。
    axes : dict
        ``{'left': 左轴}``，双 Y 轴图再有 ``'right'``。matplotlib 是 Axes 对象；
        Plotly 没有轴对象，是 layout 里的轴名（``'yaxis'``、``'yaxis2'``）。
    artists : list
        画出的曲线对象（``Line2D`` / ``PathCollection`` / ``BarContainer`` / Plotly trace），
        与 ``spec.curves`` 一一对应、顺序相同。

    See Also
    --------
    DrawnFigure.artist : 按样品号取线。
    """
    spec: FigureSpec            # 这张图的计划：画了什么都能查到
    fig: Any                    # matplotlib 的 Figure；Plotly 多张计划时各页共用同一个 Figure（6.8，翻页）
    axes: dict[str, Any]        # {'left': ax}，双 Y 轴再有 'right'；Plotly 没有轴对象（6.7 定）
    artists: list               # 曲线对象（Line2D / PathCollection / BarContainer / trace）

    def artist(self, sample_idx: int, axis: Axis = 'left'):
        """
        取这张图里某个样品挂在某根轴上的那条线。

        ``artists`` 不按样品号作键，因为双 Y 轴图里同一样品有左右两条线，所以要同时给出轴。

        Parameters
        ----------
        sample_idx : int
            样品号。
        axis : {'left', 'right'}, default: 'left'
            线挂在哪根 Y 轴上。

        Returns
        -------
        曲线对象
            ``artists`` 里对应的那一项（类型见类说明）。

        Raises
        ------
        KeyError
            这张图里没有这个样品挂在这根轴上的线。

        Examples
        --------
        >>> plotter.plot_dual_y()
        >>> plotter.figures[0].artist(0, 'right')     # 样品 0 的右线
        """
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
    与后端无关的全局外观，创建后不可修改。

    `~plotlib.plotter.DataPlotter` 把构造参数打包成 `Appearance` 交给后端，由后端翻译：
    matplotlib 翻译成 rc 参数，Plotly 翻译成模板。

    Parameters
    ----------
    font_family : str, default: 'Arial'
        字体。
    font_size : int, default: 22
        字号（磅，1/72 英寸）。
    font_weight : str, default: 'bold'
        字重。
    lines, frame, legend, ticks : 样式对象
        用户在 ``DataPlotter(...)`` 里写的那一层，没写的字段为 None。
    dpi : float, default: 100
        渲染分辨率（每英寸像素数）。后端用它把磅、英寸换成像素。

    Notes
    -----
    这里只存用户写的那一层。库默认值和版式预设由后端在画每张图时按
    「库默认 < 版式预设 < 本层」叠加（见 `plotlib.layouts.resolve_legend`），
    所以用户明确写的设置对所有版式都生效，不会被某个版式的预设盖掉。
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
    """
    一根轴上的一组用户回调；没给的回调为 None。

    绘图器按轴组成 ``{'left': AxesFormatter(...), 'right': AxesFormatter(...)}`` 交给后端，
    后端只把这根轴自己的东西交给对应的回调。

    Parameters
    ----------
    axes : callable, optional
        坐标轴回调。matplotlib 以 ``(ax, fig)`` 调用，Plotly 以 ``(轴名, fig)`` 调用。
    lines : callable, optional
        线条回调，以这根轴上的线（Plotly 是 trace）组成的列表调用。
    legend : callable, optional
        图例回调，以图例列表调用。一张图只有一个图例，归左轴；给其他轴配了会报错。
    """
    axes: Callable[..., Any] | None = None
    lines: Callable[..., Any] | None = None
    legend: Callable[..., Any] | None = None
