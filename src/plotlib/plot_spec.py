"""
绘图计划、样式配置和渲染结果的数据类型。

`LineSpec`、`ScatterSpec`、`BarSpec` 描述一条折线、一组散点、柱状图的一个系列及其所属坐标轴，
画法由类型决定（共同的基类 `CurveBase`）。
`FigureSpec` 描述整张图的版式、曲线和轴信息。
后端接收绘图计划、外观配置和格式化回调，返回 `DrawnFigure`。
"""
from collections.abc import Callable
from dataclasses import dataclass, field, fields, replace
from typing import Any, Literal, Self

import numpy as np

type CurveKind = Literal['line', 'scatter']      # 一个图层的画法
type Axis = Literal['left', 'right']
type Members = Literal['all', 'group', 'sample']     # DataPlotter.plot 的分图方式
type BarDimension = Literal['sample', 'group', 'channel']  # 柱状图的类别维度和系列维度
type BarMode = Literal['group', 'stack']        # 并排、堆叠
type Layout = Literal['multiline', 'xy', 'dual_y', 'bars']
type ColorScale = Literal['linear', 'log']      # 颜色条的刻度类型


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
        ``DataPlotter(lines=...)`` 的颜色由样品配色确定。
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


@dataclass(frozen=True)
class BarStyle(StyleLayer):
    """
    控制柱状图系列的填充、描边、纹理和误差棒外观。

    通过 ``DataPlotter.plot_bars(styles=...)`` 为全部系列或指定系列设置样式。
    描边和误差棒的线宽以磅为单位。柱宽由 ``plot_bars`` 的 *width* 参数指定。

    Parameters
    ----------
    color : str or tuple of int, optional
        填充色，写法同 `LineStyle` 的 ``color``。不写时按系列配色。
    edge_color : str or tuple of int, optional
        描边色；纹理也用这个颜色。
    edge_width : float, optional
        描边宽度（磅），可以为 0。
    hatch : str, optional
        纹理：``'slash'``、``'backslash'``、``'vertical'``、``'horizontal'``、``'cross'``、``'x'``、``'dot'``，
        ``'none'`` 表示清除纹理。纹理密度采用各后端的原生默认值。
    error_color : str or tuple of int, optional
        误差棒颜色。
    error_width : float, optional
        误差棒线宽（磅）。
    capsize : float, optional
        误差棒端帽半长（磅），可以为 0。当一个系列中有可见柱缺少误差时，整个系列省略端帽，
        避免 Plotly 将缺失值画成零误差的横线。

    Notes
    -----
    分组配置里，柱状图读取 ``color``、``hatch`` 两个字段。

    Examples
    --------
    黑白图：白色填充、黑色描边，用纹理区分系列：

    >>> plotter.plot_bars([1, 2], styles={1: BarStyle(color='white', edge_color='black', hatch='slash'),
    ...                                   2: BarStyle(color='white', edge_color='black', hatch='dot')})
    """
    color: str | tuple | None = None        # 填充色
    edge_color: str | tuple | None = None   # 描边色，纹理也用它
    edge_width: float | None = None         # 描边宽度（磅），可以为 0
    hatch: str | None = None                # 纹理词；'none' 清除
    error_color: str | tuple | None = None  # 误差棒颜色
    error_width: float | None = None        # 误差棒线宽（磅）
    capsize: float | None = None            # 端帽半长（磅），可以为 0


@dataclass(frozen=True)
class ColorbarStyle(StyleLayer):
    """
    配置散点颜色条的色带、数值范围、刻度类型和标题。

    在 `ScatterMap` 中指定颜色通道，通过 ``DataPlotter.plot(colorbar=...)`` 配置共享的颜色条。
    如需调整具体刻度或位置，可在 *figure_formatter* 中使用后端原生接口。

    Parameters
    ----------
    cmap : str, optional
        两个后端均支持 ``'viridis'``、``'plasma'``、``'inferno'``、``'magma'`` 和 ``'cividis'``。
    limits : tuple of (float or None), optional
        颜色范围 ``(下限, 上限)``。设为 ``None`` 的端点从可绘制点的最小值或最大值推导。
        指定的端点和自动推导的端点均须在 ``[-1e300, 1e300]`` 内，此检查在等值范围自动扩展前完成。
        超出颜色范围的点使用对应端点的颜色。
    scale : {'linear', 'log'}, optional
        刻度类型。``'log'`` 要求颜色值和 *limits* 都为正。
    title : str, optional
        默认使用颜色通道的列标题。传入空字符串 ``''`` 可隐藏颜色条标题。

    Notes
    -----
    默认使用线性的 ``'viridis'`` 色带。同一张图中，Matplotlib 的散点共用 ``Normalize`` 或 ``LogNorm``，
    Plotly 的散点共用 ``coloraxis``。Plotly 对数色标按 log10 着色，刻度按原值标注，悬停显示原始数值。
    ``FigureSpec.colorbar`` 保存解析后的色带、范围、刻度类型和标题。

    Matplotlib 在每次渲染时根据可见的右轴和图例定位颜色条。右边距在建图时预留一次。
    整图回调扩大右侧内容后，可调用 ``fig.tight_layout()`` 重新分配边距。自行定位颜色条时，
    请先调用 ``axes['colorbar'].ax.set_axes_locator(None)``。
    Plotly 根据右轴和图例估算间距，并考虑各页的图例标题。需要扩大间距时，可在 *figure_formatter* 中调整
    ``fig.layout.coloraxis.colorbar.xpad``。

    Examples
    --------
    >>> plotter.plot(Layer(0, 1, kind='scatter', mapping=ScatterMap(color=3)),
    ...              colorbar=ColorbarStyle(cmap='magma', scale='log'))
    """
    cmap: str | None = None                                 # 色带词名
    limits: tuple[float | None, float | None] | None = None     # (下, 上)，None 端自动
    scale: ColorScale | None = None                         # 'linear' | 'log'
    title: str | None = None                                # None 使用颜色通道的列标题，'' 隐藏标题


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
        是否显示次刻度。Matplotlib 的 ``'symlog'`` 和 ``'logit'`` 轴在关闭次刻度后，可重新设置轴类型以恢复原生定位器。
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
# 显式设置散点的尺寸和描边，使其独立于后端的全局折线样式。
DEFAULT_SCATTER = ScatterStyle(marker='circle', size=6, filled=True, edge_width=1)
# 默认隐藏描边、纹理和端帽。描边颜色为黑色，供启用纹理时使用。误差棒为黑色。
DEFAULT_BARS = BarStyle(edge_color='black', edge_width=0, hatch='none',
                        error_color='black', error_width=2, capsize=0)
DEFAULT_COLORBAR = ColorbarStyle(cmap='viridis', scale='linear')
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
    sizes : numpy.ndarray or None, default: None
        大小映射：每个点的直径（磅），已按共用范围算好；None 表示不映射大小。
    colors : numpy.ndarray or None, default: None
        颜色映射：每个点的原始数值，按 ``FigureSpec.colorbar`` 的色带和范围着色；None 表示不映射颜色。
    color_unit : str or None, default: None
        颜色通道的列标题，悬停时标明颜色值（颜色条标题可能写成 ``''``）；None 表示不映射颜色。
    """
    sample_idx: int
    x: np.ndarray
    y: np.ndarray
    style: ScatterStyle = field(default_factory=ScatterStyle)
    sizes: np.ndarray | None = None     # 每个点的直径（磅）
    colors: np.ndarray | None = None    # 每个点的颜色值（原始数值）
    color_unit: str | None = None       # 颜色通道的列标题（悬停用）


@dataclass(kw_only=True)
class BarSpec(CurveBase):
    """
    描述一个柱状图系列，每个类别对应一个柱高。公共字段见 `CurveBase`。

    后端根据系列顺序和绘制模式确定柱子位置。Plotly 使用原生 ``barmode``，Matplotlib 计算并排偏移和堆叠基线。

    Parameters
    ----------
    key : int or str
        系列的键：样品号、通道号（原数据集里的）或组名。``DrawnFigure.artist(key)`` 按它取。
    categories : list of str
        各类别的刻度文字（样品名、组名或通道列标题），同一张图的各系列相同。
    heights : numpy.ndarray
        每个类别的汇总柱高。NaN 表示缺失，保留位置并省略柱形。
    errors : numpy.ndarray or None, default: None
        每根柱的对称误差；NaN 表示这根柱没有误差棒。None 表示这个系列不画误差棒。
    caps : bool, default: True
        False 表示这个系列有柱子缺误差，不画端帽。
    series_index, series_count : int
        系列序号和系列总数，用来算并排时的偏移。
    mode : {'group', 'stack'}
        并排或堆叠。
    width : float
        单个类别的总柱宽占类别间距的比例。
    style : BarStyle, default: BarStyle()
        由分组配置和 ``styles`` 合并得到的系列样式。未指定的字段为 ``None``。
    """
    key: int | str
    categories: list[str]
    heights: np.ndarray
    errors: np.ndarray | None = None
    caps: bool = True
    series_index: int
    series_count: int
    mode: BarMode
    width: float
    style: BarStyle = field(default_factory=BarStyle)


# 绘图计划支持的绘图对象类型。
type Curve = LineSpec | ScatterSpec | BarSpec


@dataclass(frozen=True)
class ScatterMap:
    """
    将同一行的通道值映射到散点的颜色或大小。

    通过 ``Layer(kind='scatter', mapping=...)`` 配置。一次 ``DataPlotter.plot`` 的各张图使用相同的颜色范围，
    每个大小映射图层在各张图中也使用相同的大小范围。

    Parameters
    ----------
    color : int, optional
        决定颜色的通道号；颜色条的外观见 `ColorbarStyle`。一次绘图只能有一个颜色映射层。
    size : int, optional
        决定大小的通道号。*color*、*size* 至少写一个。
    size_range : tuple of float, default: (4, 16)
        最小、最大点的直径（磅），都是有限正数，下限不大于上限。

    Notes
    -----
    - 映射值与点的面积呈线性关系。映射值全部相等时，使用面积范围的中点。
    - X 或 Y 非有限，或映射值为 NaN 时，整行从绘图和范围计算中排除。映射值为无穷大或复数时会报错。
      若回调将坐标轴设为对数刻度，应先筛掉该轴上非正的坐标，否则这些点仍参与范围计算。
    - 颜色映射决定点色，分组的 ``marker`` 仍可用于区分样品。`make_scatter_formatter` 禁止为颜色映射层指定
      ``color`` 或 ``filled=False``，也禁止为大小映射层指定固定 ``size``。
    - 图例按样品列出。颜色与数值的对应关系见颜色条，可用 *figure_formatter* 自定义大小图例。
    - ``neglog_x`` 和 ``neglog_y`` 只变换对应的坐标值。

    Examples
    --------
    Nyquist 图按频率（通道 0）着色，对数色标：

    >>> plotter.plot(Layer(1, 2, kind='scatter', mapping=ScatterMap(color=0)),
    ...              colorbar=ColorbarStyle(scale='log'))

    气泡图：点的大小表示通道 3：

    >>> plotter.plot(Layer(0, 1, kind='scatter', mapping=ScatterMap(size=3, size_range=(4, 20))))
    """
    color: int | None = None                        # 决定颜色的通道号
    size: int | None = None                         # 决定大小的通道号
    size_range: tuple[float, float] = (4, 16)       # 最小、最大直径（磅）


@dataclass(frozen=True)
class Layer:
    """
    一个图层：图里的每个样品各画一条的「配方」，写取哪两个通道、画成什么、挂哪根 Y 轴。

    只写数据和画法，不写外观：颜色、线型、标签由分组、版式预设和回调决定。

    Parameters
    ----------
    x, y : int, optional
        X、Y 的通道号（样品内的列序号）；不写时用 `~plotlib.plotter.DataPlotter` 构造时的 *channel_x*、*channel_y*。
    kind : {'line', 'scatter'}, default: 'line'
        画成折线还是散点。
    side : {'left', 'right'}, default: 'left'
        挂在左 Y 轴还是右 Y 轴；两侧共用 X 轴。
    neglog_x, neglog_y : bool, default: False
        负对数：这一层的数据取绝对值，所在轴的刻度补负号。同一根轴上的图层要写得一致；
        共用的 X 轴的负号由左侧图层决定，右侧图层的 *neglog_x* 只把自己的数据取绝对值。
    mapping : ScatterMap, optional
        第三通道映射：用另一个通道决定点的颜色或大小，只有散点能写（见 `ScatterMap`）。

    Examples
    --------
    实测点和拟合线（拟合结果存成通道 3）画在同一张图里，每个样品一张：

    >>> plotter.plot([Layer(0, 1, kind='scatter'), Layer(0, 3)], by='sample')
    """
    x: int | None = None
    y: int | None = None
    kind: CurveKind = 'line'
    side: Axis = 'left'
    neglog_x: bool = False
    neglog_y: bool = False
    mapping: ScatterMap | None = None


@dataclass
class FigureSpec:
    """
    绘图计划里的一张图：有哪些线、轴的单位、哪些轴补负号、用哪套版式。

    Parameters
    ----------
    key : str or int
        这张图在结果字典 ``DataPlotter.figures`` 里的键：分组名或 ``'main'``；
        xy 图、双 Y 轴图是样品号。
    curves : list of LineSpec, ScatterSpec or BarSpec
        曲线列表（柱状图是各个系列），按绘制顺序排列（``DrawnFigure.artists`` 与它一一对应）。图例顺序：Plotly 与此相同；
        matplotlib 的图例先列左轴的曲线、再列右轴的，左右图层交错时与绘制顺序不同。
    x_unit, y_unit : str
        X 轴和左 Y 轴的标题，通常来自通道的列标题。
    y2_unit : str or None, default: None
        右 Y 轴的标题；只有双 Y 轴图有。
    neglog : frozenset of str, default: frozenset()
        哪些轴的刻度文字要补负号（负对数）：``'x'``、``'y'``、``'y2'``，
        以及预留给上轴的 ``'x2'``。
    layout : {'multiline', 'xy', 'dual_y', 'bars'}, default: 'multiline'
        按哪套版式预设排版（见 `plotlib.layouts.LAYOUTS`）。
    legend_title : str or None, default: None
        图例标题，已是最终文字（``'{name}'`` 已替换）；None 表示不加标题。
    name : str or None, default: None
        样品名或组名。多线图和合并分组图为 ``None``。
        Plotly 使用该名称作为翻页滑块的档位标签。
    colorbar : ColorbarStyle or None, default: None
        颜色条：色带、算好的范围、刻度类型、最终标题；只有颜色映射的图有。
        一次绘图的各张图共用同一个范围。
    """
    key: str | int              # 分组名或 'main'；xy、双 Y 轴图是样品号
    curves: list[Curve]
    x_unit: str                 # X 轴标题
    y_unit: str
    y2_unit: str | None = None  # 右轴单位；只有双 Y 轴图有
    neglog: frozenset[str] = frozenset()    # 哪些轴的刻度补负号：'x'、'y'、'x2'（上轴，拼图时用）、'y2'
    layout: Layout = 'multiline'
    legend_title: str | None = None
    name: str | None = None
    colorbar: ColorbarStyle | None = None   # 颜色映射的颜色条（范围已算好）；没有颜色映射为 None


@dataclass
class DrawnFigure:
    """
    `FigureSpec` 对应的渲染结果。

    `~plotlib.plotter.DataPlotter` 按绘图计划的键保存结果，形式为 ``figures = {spec.key: DrawnFigure}``。

    Parameters
    ----------
    spec : FigureSpec
        渲染该图所用的绘图计划。
    fig : `matplotlib.figure.Figure` or `plotly.graph_objects.Figure`
        原生的图对象。Plotly 画多张计划时，各页共用同一个 Figure。
    axes : dict
        ``'left'`` 对应左轴，双 Y 轴图提供 ``'right'``。Matplotlib 保存 ``Axes`` 对象，Plotly 保存布局中的轴名。
        颜色映射图还提供 ``'colorbar'``，对应 Matplotlib 的 ``Colorbar`` 对象或 Plotly 的 ``'coloraxis'``。
    artists : list
        画出的对象（折线 ``Line2D``、散点 ``PathCollection``、柱状图的一个系列 ``BarContainer``，
        Plotly 都是 trace），与 ``spec.curves`` 一一对应、顺序相同。

    See Also
    --------
    DrawnFigure.artist : 按样品号取线。
    """
    spec: FigureSpec
    fig: Any
    axes: dict[str, Any]
    artists: list               # 曲线对象（Line2D / PathCollection / trace）

    def artist(self, key: int | str | None = None, axis: Axis = 'left', *, sample_idx: int | None = None):
        """
        返回指定样品（柱状图是指定系列）在指定轴上的绘图对象。

        ``artists`` 不按样品号作键，因为双 Y 轴图里同一样品有左右两条线，所以要同时给出轴。

        Parameters
        ----------
        key : int or str
            曲线图是样品号；柱状图是系列的键（样品号、原数据集里的通道号或组名，一张图里只有一种）。
        axis : {'left', 'right'}, default: 'left'
            线挂在哪根 Y 轴上。
        sample_idx : int, optional
            *key* 的兼容参数，仅接受关键字传参，如 ``artist(sample_idx=0)``。

        Returns
        -------
        绘图对象
            ``artists`` 里对应的那一项（类型见类说明）。

        Raises
        ------
        KeyError
            这张图里没有这个样品（系列）挂在这根轴上的对象。
        TypeError
            必须且只能提供 *key* 或 *sample_idx* 中的一个。

        Examples
        --------
        >>> plotter.plot([Layer(0, 1), Layer(2, 3, side='right')], by='sample')
        >>> plotter.figures[0].artist(0, 'right')     # 样品 0 的右线
        >>> plotter.plot_bars([1, 2]).figures['main'].artist(2)      # 通道 2 那个系列
        """
        if (key is None) == (sample_idx is None):
            raise TypeError("artist() 要写一个键：artist(key) 或 artist(sample_idx=...)，不能都写或都不写")
        key = sample_idx if key is None else key
        for curve, artist in zip(self.spec.curves, self.artists):
            own_key = curve.key if isinstance(curve, BarSpec) else curve.sample_idx
            if own_key == key and curve.axis == axis:
                return artist
        raise KeyError(f"图 {self.spec.key!r} 里没有 {key!r} 挂在 {axis} 轴上的对象")


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
    bars : callable, optional
        仅用于 ``plot_bars``，接收柱状图系列列表。Matplotlib 提供 ``BarContainer``，可通过 ``errorbar`` 访问误差棒。
        Plotly 提供柱状 trace。并排时误差棒在 ``error_y`` 中，堆叠时由单独的散点 trace 绘制。
        `~plotlib.formatters.make_bar_formatter` 支持调整两种排列方式的误差棒样式。
    """
    axes: Callable[..., Any] | None = None
    lines: Callable[..., Any] | None = None
    legend: Callable[..., Any] | None = None
    scatter: Callable[..., Any] | None = None
    bars: Callable[..., Any] | None = None
