"""
绘图计划、样式配置和渲染结果的数据类型。

`LineSpec`、`ScatterSpec` 描述一条折线、一组散点及其所属坐标轴，画法由类型决定（共同的基类 `CurveBase`）。
`FigureSpec` 描述整张图的版式、曲线和轴信息。
后端接收绘图计划、外观配置和格式化回调，返回 `DrawnFigure`。
"""
from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace
from typing import Any, Literal, Self

import numpy as np

type CurveKind = Literal['line', 'scatter']      # 双 Y 轴每一侧的画法
type Axis = Literal['left', 'right']
type Layout = Literal['multiline', 'xy', 'dual_y']


# ══════════════════════════════════════════════
# 样式对象
# ══════════════════════════════════════════════
class StyleLayer:
    """
    样式对象的公共基类，提供 `updated` 合并方法。

    未指定字段为 ``None``，表示沿用较低优先级的值。样式按以下顺序合并::

        库默认 DEFAULT_* < 版式预设（layouts）< DataPlotter 全局 < 分组样式 < 单轴 formatter
    """

    def updated(self, other: Self | None) -> Self:
        """
        返回在本层之上叠加 *other* 之后的新样式对象。

        Parameters
        ----------
        other : 同类样式对象 or None
            优先级更高的样式。仅覆盖其中值非 ``None`` 的字段。
            *other* 为 ``None`` 时返回当前对象。

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
    折线的样式。

    可用于全局线条设置、分组样式和 `~plotlib.formatters.make_lines_formatter`。
    长度单位为磅，取值见 `plotlib.style`。散点用 `ScatterStyle`。

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
    分组配置里，折线读取 ``linestyle``、``marker``、``color`` 三个字段。

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


@dataclass(frozen=True)
class ScatterStyle(StyleLayer):
    """
    定义散点的颜色、标记和描边。

    可传给 `~plotlib.formatters.make_scatter_formatter`。标记大小和描边宽度以磅为单位。

    Parameters
    ----------
    color : str or tuple of int, optional
        接受 CSS 颜色名、``'#rrggbb'`` 或三个 0–255 的整数 ``(r, g, b)``。
        用于实心标记的填充和默认描边。绘图时省略此项可沿用样品配色。
    marker : str, optional
        标记形状，可选值同 `LineStyle` 的 ``marker``。
    size : float, optional
        标记大小（磅），与 `LineStyle` 的 ``marker_size`` 同一量度（标记的直径）。
    filled : bool, optional
        为真时填充标记，为假时仅绘制描边。格式化现有散点时，
        仅指定 ``filled=True`` 可恢复空心标记之前的填充色。单独指定 ``color`` 也会应用填充色。
    edge_color : str or tuple of int, optional
        描边颜色，写法同 ``color``。
    edge_width : float, optional
        描边宽度（磅），可以为 0。
    alpha : float, optional
        不透明度，0（全透明）~ 1（不透明）。

    Notes
    -----
    所有字段两个后端都支持：matplotlib 对应 ``scatter`` 的 ``facecolors``、``edgecolors``、``linewidths``、
    ``s``、``marker``、``alpha``；Plotly 对应 ``marker`` 的 ``color``、``line.color``、``line.width``、
    ``size``、``symbol``、``opacity``。库默认见 ``DEFAULT_SCATTER``，不受全局折线样式影响。

    分组配置可通过 ``marker`` 和 ``color`` 指定散点样式。

    Examples
    --------
    >>> make_scatter_formatter(ScatterStyle(color='black', marker='square', size=8))
    >>> make_scatter_formatter(ScatterStyle(filled=False, edge_width=1.5))      # 空心点
    """
    color: str | tuple | None = None    # 颜色：CSS 颜色名、'#rrggbb'、RGB 三个 0~255 的整数
    marker: str | None = None           # 标记形状，同 LineStyle.marker
    size: float | None = None           # 标记大小（磅）
    filled: bool | None = None          # True 实心；False 空心（只画描边）
    edge_color: str | tuple | None = None   # 默认沿用 color 作为描边色
    edge_width: float | None = None     # 描边宽度（磅），可以为 0
    alpha: float | None = None          # 不透明度 0 ~ 1


type AxisScale = Literal['linear', 'log', 'symlog', 'logit']    # 'symlog'、'logit' 只有 matplotlib


@dataclass(frozen=True)
class AxisStyle(StyleLayer):
    """
    单个方向的坐标轴样式。

    X、Y 轴分别通过 ``make_axes_formatter(x=..., y=...)`` 设置。
    版式预设也使用该对象定义各轴的默认格式和颜色。

    Parameters
    ----------
    scale : {'linear', 'log', 'symlog', 'logit'}, optional
        刻度类型。``'symlog'``、``'logit'`` 只有 matplotlib 支持。
        未指定时保留当前轴类型。
    limits : tuple of (float or None, float or None), optional
        数据坐标中的 ``(下限, 上限)``。某侧为 ``None`` 时自动计算该侧边界。
        对数轴的显式边界必须大于 0。
    format : str, optional
        刻度文字格式，Python 格式字符串，用 ``x`` 或 ``y`` 作变量名，如 ``'{x:.2f}'``、``'{y:.1e}'``。
        Plotly 支持 ``.Nf``、``.Ne``、``.Ng`` 和 ``.N%``，其中 ``N`` 为精度。
        对数轴使用显式格式且隐藏次刻度标签时，PlotLib 默认每个数量级放置一个主刻度。
        可在 ``custom`` 回调中指定主刻度间距，例如用 ``fig.update_xaxes(dtick=2)`` 改为每两个数量级一个。
    scaler : float, optional
        仅 Matplotlib 支持。刻度显示值等于刻度值乘以 *scaler*，数据值保持原样。
    color : str or tuple of int, optional
        应用于轴标题、刻度和轴线的颜色。

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
    right: bool | None = None


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


type TickDirection = Literal['out', 'in']          # 两个后端均支持朝内或朝外。
type MinorLabels = Literal['none', 'short', 'full']


@dataclass(frozen=True)
class TickStyle(StyleLayer):
    """
    主、次刻度线及标签的样式。

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
        ``'none'`` 隐藏标签，``'short'`` 在对数轴显示首位数字，``'full'`` 显示完整数值。
        线性轴上，Matplotlib 可用 ``'full'`` 显示标签，``'short'`` 时隐藏标签。
        Plotly 仅对数轴支持次刻度标签，且显式 ``AxisStyle.format`` 与 ``'short'`` 同时使用会引发
        ``ValueError``。
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
# 散点的库默认：大小、描边都明确写出，画的时候总是带上，所以不受全局折线样式（matplotlib 的 rc、Plotly 模板）影响
DEFAULT_SCATTER = ScatterStyle(marker='circle', size=6, filled=True, edge_width=1)
DEFAULT_FRAME = FrameStyle(width=3, top=False, right=False)
DEFAULT_LEGEND = LegendStyle(position='upper right', font_size=10, frame=False, draggable=False)
# 默认显示主刻度和次刻度线，并隐藏次刻度标签。
DEFAULT_TICKS = TickStyle(direction='out', length=6, width=3, minor=True,
                          minor_length=3, minor_width=3, minor_labels='none')


# ══════════════════════════════════════════════
# 计划与结果
# ══════════════════════════════════════════════
@dataclass(kw_only=True)
class CurveBase:
    """
    图里一项内容（一条折线、一组散点）共有的信息：图例、分组、配色和所在的轴。

    画法由子类的类型决定（`LineSpec`、`ScatterSpec`），后端按类型选择画法；直接用基类画会报错。
    所有字段只能按关键字给出。

    Parameters
    ----------
    label : str
        图例文字：一般是样品名；双 Y 轴图是这条线的单位（样品名在图例标题里）。
    group_name : str or None
        所属分组名；不分组时为 None。
    color_position : float or None
        默认颜色在色带上的位置（0 ~ 1）；合并模式下已换成组首样品的位置。
        None 表示不按色带取色（用版式预设的轴颜色或后端默认色）。
    axis : {'left', 'right'}, default: 'left'
        挂在哪根 Y 轴上；只有双 Y 轴图有 ``'right'``。
    """
    label: str                  # 图例文字：样品名；双 Y 轴是这条线的单位（样品名在图例标题里）
    group_name: str | None      # 不分组时为 None
    color_position: float | None    # 默认颜色在色带上的位置（合并模式已换成组首位置）；None：用后端默认色
    axis: Axis = 'left'         # 挂在哪根 Y 轴上；只有双 Y 轴图有 'right'


@dataclass(kw_only=True)
class LineSpec(CurveBase):
    """
    一条折线：一个样品的 X、Y 两列数据。其余字段见 `CurveBase`。

    Parameters
    ----------
    sample_idx : int
        这条线所属的样品号。
    x, y : numpy.ndarray
        已取好的数据（负对数时已取绝对值，``plotrange`` 已截断）。
    style : LineStyle, default: LineStyle()
        分组写了的样式（线型、标记、颜色）；没写的字段为 None。
    """
    sample_idx: int
    x: np.ndarray
    y: np.ndarray
    style: LineStyle = field(default_factory=LineStyle)     # 分组写了的样式；没写的字段为 None


@dataclass(kw_only=True)
class ScatterSpec(CurveBase):
    """
    一组散点：一个样品的 X、Y 两列数据。其余字段见 `CurveBase`。

    Parameters
    ----------
    sample_idx : int
        这组散点所属的样品号。
    x, y : numpy.ndarray
        已取好的数据（负对数时已取绝对值，``plotrange`` 已截断）。
    style : ScatterStyle, default: ScatterStyle()
        分组指定的标记形状和颜色。
    """
    sample_idx: int
    x: np.ndarray
    y: np.ndarray
    style: ScatterStyle = field(default_factory=ScatterStyle)


# 计划里能出现的曲线（按画法列举；加新画法时在这里加上它的 spec 类型）
type Curve = LineSpec | ScatterSpec


@dataclass
class FigureSpec:
    """
    绘图计划里的一张图：有哪些线、轴的单位、哪些轴补负号、用哪套版式。

    Parameters
    ----------
    key : str or int
        这张图在结果字典 ``DataPlotter.figures`` 里的键：分组名或 ``'main'``；
        xy 图、双 Y 轴图是样品号。
    curves : list of LineSpec or ScatterSpec
        曲线列表，按绘制及图例顺序排列。
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
        样品名或组名。多线图和合并分组图为 ``None``。
        Plotly 使用该名称作为翻页滑块的档位标签。
    """
    key: str | int              # 分组名或 'main'；xy、双 Y 轴图是样品号
    curves: list[Curve]
    x_unit: str                 # 轴标题：同一通道的单位在各样品间一致，所以属于图，不属于线
    y_unit: str
    y2_unit: str | None = None  # 右轴单位；只有双 Y 轴图有
    neglog: frozenset[str] = frozenset()    # 哪些轴的刻度补负号：'x'、'y'、'x2'（上轴，拼图时用）、'y2'
    layout: Layout = 'multiline'
    legend_title: str | None = None
    name: str | None = None


@dataclass
class DrawnFigure:
    """
    `FigureSpec` 对应的渲染结果。

    两个后端、四种绘图方法交回的结果形状相同，`~plotlib.plotter.DataPlotter` 把它们存成
    ``figures = {spec.key: DrawnFigure}``。

    Parameters
    ----------
    spec : FigureSpec
        渲染该图所用的绘图计划。
    fig : `matplotlib.figure.Figure` or `plotly.graph_objects.Figure`
        原生的图对象。Plotly 画多张计划时，各页共用同一个 Figure。
    axes : dict
        ``{'left': 左轴}``，双 Y 轴图再有 ``'right'``。matplotlib 是 Axes 对象；
        Plotly 没有轴对象，是 layout 里的轴名（``'yaxis'``、``'yaxis2'``）。
    artists : list
        画出的曲线对象（折线 ``Line2D``、散点 ``PathCollection``，Plotly 都是 trace），
        与 ``spec.curves`` 一一对应、顺序相同。

    See Also
    --------
    DrawnFigure.artist : 按样品号取线。
    """
    spec: FigureSpec
    fig: Any
    axes: dict[str, Any]
    artists: list               # 曲线对象（Line2D / PathCollection / trace）

    def artist(self, sample_idx: int, axis: Axis = 'left'):
        """
        返回指定样品在指定轴上的绘图对象。

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
            # 基类不带样品号（以后的柱状图一组柱不一定是一个样品），按有没有这个字段取
            if getattr(curve, 'sample_idx', None) == sample_idx and curve.axis == axis:
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
        ``DataPlotter`` 的显式样式。未指定的字段为 ``None``。
    dpi : float, default: 100
        渲染分辨率（每英寸像素数）。后端用它把磅、英寸换成像素。

    Notes
    -----
    渲染时，后端合并库默认值、版式预设和显式设置。
    显式设置的优先级最高。
    """
    font_family: str = 'Arial'
    font_size: int = 22
    font_weight: str = 'bold'
    lines: LineStyle = LineStyle()
    frame: FrameStyle = FrameStyle()
    legend: LegendStyle = LegendStyle()
    ticks: TickStyle = TickStyle()
    dpi: float = 100


@dataclass(frozen=True)
class AxesFormatter:
    """
    指定坐标轴的样式回调。未提供的回调为 ``None``。

    后端按轴接收 ``{'left': AxesFormatter(...), 'right': AxesFormatter(...)}``，
    并传入各轴的原生对象。

    Parameters
    ----------
    axes : callable, optional
        坐标轴回调。matplotlib 以 ``(ax, fig)`` 调用，Plotly 以 ``(轴名, fig)`` 调用。
    lines : callable, optional
        线条回调，以这根轴上的折线（Plotly 是 trace）组成的列表调用；散点不在其中。
    legend : callable, optional
        图例回调，以图例列表调用。一张图只有一个图例，归左轴；给其他轴配了会报错。
    scatter : callable, optional
        散点回调，以这根轴上的散点（matplotlib 是 ``PathCollection``，Plotly 是 trace）组成的列表调用。
    """
    axes: Callable[..., Any] | None = None
    lines: Callable[..., Any] | None = None
    legend: Callable[..., Any] | None = None
    scatter: Callable[..., Any] | None = None
