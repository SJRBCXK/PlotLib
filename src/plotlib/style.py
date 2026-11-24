"""
校验跨后端样式并转换为 Matplotlib 和 Plotly 参数。

分组、全局样式和格式化器使用同一套取值。渲染后端负责转换为绘图库的原生参数。

样式取值
--------
线型
    ``'solid'``、``'dash'``、``'dot'``、``'dashdot'``；或自定义虚线 ``(实线长, 空白长, ...)``：
    正数、偶数个，单位是线宽的倍数。
标记
    ``'circle'``、``'square'``、``'triangle-up'``、``'triangle-down'``、``'diamond'``、``'cross'``、``'x'``。
颜色
    CSS 颜色名（W3C 标准的 148 个，不区分大小写）；六位色号 ``'#rrggbb'``；三个 0~255 的整数 ``(r, g, b)``。
纹理（柱状图）
    ``'slash'``、``'backslash'``、``'vertical'``、``'horizontal'``、``'cross'``、``'x'``、``'dot'``；
    ``'none'`` 清除纹理。纹理颜色跟随描边色，疏密用各后端的原生默认。

Notes
-----
``check_*`` 校验类型和取值，成功时返回 ``None``，失败时引发 `TypeError` 或 `ValueError`。
``translate_*`` 返回目标后端参数。Matplotlib 使用磅，Plotly 使用 ``磅 × dpi / 72`` 换算为像素。
"""
import math
import re
from collections.abc import Callable
from numbers import Integral, Real
from typing import Any, Literal, overload

# 使用 Matplotlib 的颜色表校验两个后端共用的 CSS 颜色名。
from matplotlib.colors import CSS4_COLORS
from matplotlib.markers import MarkerStyle

from .plot_spec import AxisStyle, BarStyle, FrameStyle, LegendStyle, LineStyle, ScatterStyle, TickStyle

type Backend = Literal["matplotlib", "plotly"]

# 通用样式名称及其对应的后端原生值。
LINESTYLES: dict[str, dict[str, str]] = {
    'solid':   {'matplotlib': '-',  'plotly': 'solid'},
    'dash':    {'matplotlib': '--', 'plotly': 'dash'},
    'dot':     {'matplotlib': ':',  'plotly': 'dot'},
    'dashdot': {'matplotlib': '-.', 'plotly': 'dashdot'},
}

# 注意：'cross'、'x' 在 matplotlib 是细线，在 Plotly 是实心图形，外观略有不同。
MARKERS: dict[str, dict[str, str]] = {
    'circle':        {'matplotlib': 'o', 'plotly': 'circle'},
    'square':        {'matplotlib': 's', 'plotly': 'square'},
    'triangle-up':   {'matplotlib': '^', 'plotly': 'triangle-up'},
    'triangle-down': {'matplotlib': 'v', 'plotly': 'triangle-down'},
    'diamond':       {'matplotlib': 'D', 'plotly': 'diamond'},
    'cross':         {'matplotlib': '+', 'plotly': 'cross'},
    'x':             {'matplotlib': 'x', 'plotly': 'x'},
}

# 柱状图的纹理：两个后端都能渲染的 7 种（matplotlib 3.10、Plotly 7 实测），'none' 表示清除纹理。
# 纹理颜色跟随描边色（edge_color）；疏密用各后端的原生默认，两边不完全一样。
HATCHES: dict[str, dict[str, str]] = {
    'slash':      {'matplotlib': '/',  'plotly': '/'},
    'backslash':  {'matplotlib': '\\', 'plotly': '\\'},
    'vertical':   {'matplotlib': '|',  'plotly': '|'},
    'horizontal': {'matplotlib': '-',  'plotly': '-'},
    'cross':      {'matplotlib': '+',  'plotly': '+'},
    'x':          {'matplotlib': 'x',  'plotly': 'x'},
    'dot':        {'matplotlib': '.',  'plotly': '.'},
    'none':       {'matplotlib': '',   'plotly': ''},
}

_HEX_COLOR = re.compile(r'#[0-9a-fA-F]{6}')
_SEQUENCES = (tuple, list)

# Plotly 的默认线宽（像素）：自定义虚线换算成像素时，没给线宽就用它。
PLOTLY_DEFAULT_LINEWIDTH = 2


def check_backend(backend) -> None:
    """
    校验后端名。

    Raises
    ------
    ValueError
        *backend* 不是 ``'matplotlib'`` 或 ``'plotly'``。
    """
    if backend not in ("matplotlib", "plotly"):
        raise ValueError(f"不支持的 backend: {backend!r}，可用 'matplotlib'、'plotly'")


def _words(table) -> str:
    """把可用的词列成报错信息里的一串：``'solid'、'dash'``。"""
    return '、'.join(f"'{word}'" for word in table)


def _is_number(x) -> bool:
    """
    判断是否为实数，排除布尔值。
    """
    return isinstance(x, Real) and not isinstance(x, bool)


# ══════════════════════════════════════════════
# 校验
# ══════════════════════════════════════════════
def check_linestyle(value) -> None:
    """
    校验线型：标准词之一，或自定义虚线 ``(实线长, 空白长, ...)``。

    Raises
    ------
    TypeError
        类型不对，或自定义虚线里有非数字。
    ValueError
        不认识的线型词；自定义虚线不是正偶数个，或有段长不大于 0。
    """
    if isinstance(value, str):
        if value not in LINESTYLES:
            raise ValueError(f"不支持的线型 {value!r}，可用 {_words(LINESTYLES)}，"
                             f"或自定义虚线 (实线长, 空白长, ...)")
        return
    if isinstance(value, _SEQUENCES):
        if not all(_is_number(x) for x in value):
            raise TypeError(f"自定义虚线 {value!r} 的元素必须是数字，如 (3, 5)")
        if len(value) == 0 or len(value) % 2 != 0:
            raise ValueError(f"自定义虚线 {value!r} 必须是成对的 (实线长, 空白长, ...)，个数为正偶数")
        if not all(x > 0 for x in value):
            raise ValueError(f"自定义虚线 {value!r} 的每段长度必须大于 0")
        return
    raise TypeError(f"线型 {value!r} 的类型不支持：应为 {_words(LINESTYLES)} 之一，"
                    f"或自定义虚线 (实线长, 空白长, ...)")


def check_marker(value) -> None:
    """
    校验标记：必须是标准词之一（见模块说明）。

    Raises
    ------
    TypeError
        不是字符串。
    ValueError
        不认识的标记词。
    """
    if not isinstance(value, str):
        raise TypeError(f"标记 {value!r} 的类型不支持：应为 {_words(MARKERS)} 之一")
    if value not in MARKERS:
        raise ValueError(f"不支持的标记 {value!r}，可用 {_words(MARKERS)}")


def check_color(value) -> None:
    """
    校验颜色：CSS 颜色名（不区分大小写）、``'#rrggbb'``，或三个 0~255 的整数。

    Raises
    ------
    TypeError
        类型不对，或 RGB 里有非整数。
    ValueError
        不认识的颜色名或色号；RGB 不是正好三个数，或超出 0~255。
    """
    if isinstance(value, str):
        if _HEX_COLOR.fullmatch(value) or value.lower() in CSS4_COLORS:
            return
        raise ValueError(f"不支持的颜色 {value!r}：应为 CSS 颜色名（如 'red'）、"
                         f"六位色号 '#rrggbb'，或 RGB 三个 0~255 的整数")
    if isinstance(value, _SEQUENCES):
        if len(value) != 3:
            raise ValueError(f"RGB 颜色 {value!r} 必须正好三个整数")
        if not all(_is_number(x) and isinstance(x, Integral) for x in value):
            raise TypeError(f"RGB 颜色 {value!r} 的元素必须是 0~255 的整数")
        if not all(0 <= x <= 255 for x in value):
            raise ValueError(f"RGB 颜色 {value!r} 的元素必须在 0~255 之间")
        return
    raise TypeError(f"颜色 {value!r} 的类型不支持：应为 CSS 颜色名、'#rrggbb' 或 RGB 元组")


def check_hatch(value) -> None:
    """
    校验柱状图纹理：必须是标准词之一（见 ``HATCHES``），``'none'`` 表示清除。

    Raises
    ------
    TypeError
        不是字符串。
    ValueError
        不认识的纹理词。
    """
    if not isinstance(value, str):
        raise TypeError(f"纹理 {value!r} 的类型不支持：应为 {_words(HATCHES)} 之一")
    if value not in HATCHES:
        raise ValueError(f"不支持的纹理 {value!r}，可用 {_words(HATCHES)}"
                         f"（后端写法如 '/'、'///' 请改用标准词，疏密用后端默认）")


# ══════════════════════════════════════════════
# 翻译：标准写法 → 后端原生值
# ══════════════════════════════════════════════
def translate_linestyle(value, backend: Backend, linewidth=None):
    """
    把标准线型翻译成后端的原生写法。

    Parameters
    ----------
    value : str or tuple of float
        标准线型词，或自定义虚线 ``(实线长, 空白长, ...)`` （单位是线宽的倍数）。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    linewidth : float, optional
        Plotly 换算自定义虚线时用的线宽（像素）；不给时用 Plotly 的默认线宽 2。

    Returns
    -------
    str or tuple
        标准词：matplotlib 为 ``'-'``、``'--'`` 等，Plotly 为 ``'solid'``、``'dash'`` 等。
        自定义虚线：matplotlib 为 ``(0, (段长, ...))``，由 matplotlib 自己按线宽缩放；
        Plotly 为 ``'9px,15px'`` 这样的像素字符串（段长 × *linewidth*）。
    """
    check_backend(backend)
    check_linestyle(value)
    if isinstance(value, str):
        return LINESTYLES[value][backend]
    if backend == 'matplotlib':
        return (0, tuple(value))
    width = PLOTLY_DEFAULT_LINEWIDTH if linewidth is None else linewidth
    return ','.join(f"{x * width:g}px" for x in value)


def translate_marker(value, backend: Backend) -> str:
    """把标准标记词翻译成后端的原生写法（如 ``'circle'`` → matplotlib 的 ``'o'``）。"""
    check_backend(backend)
    check_marker(value)
    return MARKERS[value][backend]


def translate_color(value, backend: Backend):
    """
    把标准颜色翻译成后端的原生写法。

    颜色名和色号两个后端都认，原样返回；RGB 整数在 matplotlib 换成 0~1 的浮点元组，
    在 Plotly 写成 ``'rgb(r,g,b)'``。
    """
    check_backend(backend)
    check_color(value)
    if isinstance(value, str):
        return value
    if backend == 'matplotlib':
        return tuple(x / 255 for x in value)
    return f"rgb({value[0]},{value[1]},{value[2]})"


def _check_positive(name: str, value, allow_zero: bool = False) -> None:
    """
    校验长度、宽度、字号这类量：要写数字（磅）且大于 0；*allow_zero* 为 True 时可以为 0（间距类）。
    None 表示「不改」，不检查。
    """
    if value is None:
        return
    if not _is_number(value):
        raise TypeError(f"{name} 要写数字（磅），实际是 {value!r}")
    if not math.isfinite(value):        # NaN 和任何数比较都是 False，不单独查会漏过去
        raise ValueError(f"{name} 要写有限的数字，实际是 {value!r}")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} 要大于 0{'（可以为 0）' if allow_zero else ''}，实际是 {value!r}")


def _check_switch(name: str, value) -> None:
    """校验开关：只收 True / False；None 表示「不改」。"""
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{name} 是开关，要写 True / False，实际是 {value!r}")


# ══════════════════════════════════════════════
# 曲线样式
# ══════════════════════════════════════════════
def check_line_style(style: LineStyle) -> None:
    """
    校验 `LineStyle` 的正数尺寸和通用样式取值。

    Raises
    ------
    TypeError, ValueError
        某个字段写错，信息里带字段名和写错的值。
    """
    _check_positive('width', style.width)
    _check_positive('marker_size', style.marker_size)
    if style.color is not None:
        check_color(style.color)
    if style.linestyle is not None:
        check_linestyle(style.linestyle)
    if style.marker is not None:
        check_marker(style.marker)


def translate_line_style(style: LineStyle, backend: Backend, dpi: float | None = None,
                         dash_width: float | None = None) -> dict:
    """
    把 `LineStyle` 翻译成后端的画线参数，只含写了的字段。

    Parameters
    ----------
    style : LineStyle
        要翻译的线样式。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    dpi : float, optional
        Plotly 把磅换成像素用的分辨率；Plotly 必填，matplotlib 不用。
    dash_width : float, optional
        Plotly 换算自定义虚线段长用的线宽（像素）。*style* 自己写了 ``width`` 时用它，
        没写时用 *dash_width* （一般是全局线宽）。

    Returns
    -------
    dict
        matplotlib：``Line2D`` 的属性 ``linewidth``、``color``、``linestyle``、``marker``、``markersize``。
        Plotly：trace 的扁平写法 ``line_width``、``line_color``、``line_dash``、``marker_symbol``、
        ``marker_size``、``marker_color`` （点与线同色），可直接交给 ``go.Scatter(...)`` 或 ``trace.update(...)``。

    Raises
    ------
    ValueError
        后端是 Plotly 却没给 *dpi*；或某个字段写错。
    """
    check_backend(backend)
    check_line_style(style)
    if backend == 'matplotlib':
        native = {
            'linewidth': style.width,
            'color': None if style.color is None else translate_color(style.color, backend),
            'linestyle': None if style.linestyle is None else translate_linestyle(style.linestyle, backend),
            'marker': None if style.marker is None else translate_marker(style.marker, backend),
            'markersize': style.marker_size,
        }
        return {key: value for key, value in native.items() if value is not None}

    if dpi is None:
        raise ValueError("Plotly 的线宽、标记大小要按 dpi 把磅换成像素，请传入 dpi")
    width = None if style.width is None else translate_points(style.width, dpi, backend)
    color = None if style.color is None else translate_color(style.color, backend)
    native = {
        'line_width': width,
        'line_color': color,
        'line_dash': None if style.linestyle is None else
                     translate_linestyle(style.linestyle, backend, linewidth=width if width is not None else dash_width),
        'marker_symbol': None if style.marker is None else translate_marker(style.marker, backend),
        'marker_size': None if style.marker_size is None else translate_points(style.marker_size, dpi, backend),
        'marker_color': color,
    }
    return {key: value for key, value in native.items() if value is not None}


def check_scatter_style(style: ScatterStyle) -> None:
    """
    校验 `ScatterStyle` 的标记大小和通用样式取值。

    Raises
    ------
    TypeError, ValueError
        某个字段写错，信息里带字段名和写错的值。
    """
    _check_positive('size', style.size)
    _check_positive('edge_width', style.edge_width, allow_zero=True)
    _check_switch('filled', style.filled)
    for name in ('color', 'edge_color'):
        if (value := getattr(style, name)) is not None:
            check_color(value)
    if style.marker is not None:
        check_marker(style.marker)
    if style.alpha is not None:
        if not _is_number(style.alpha):
            raise TypeError(f"alpha 要写 0 ~ 1 的数字，实际是 {style.alpha!r}")
        if not 0 <= style.alpha <= 1:       # NaN 也不满足
            raise ValueError(f"alpha 要在 0 ~ 1 之间，实际是 {style.alpha!r}")


def check_bar_style(style: BarStyle) -> None:
    """
    校验 `BarStyle` 的宽度、颜色和纹理。

    Raises
    ------
    TypeError, ValueError
        某个字段写错，信息里带字段名和写错的值。
    """
    _check_positive('edge_width', style.edge_width, allow_zero=True)
    _check_positive('error_width', style.error_width)
    _check_positive('capsize', style.capsize, allow_zero=True)
    for name in ('color', 'edge_color', 'error_color'):
        if (value := getattr(style, name)) is not None:
            check_color(value)
    if style.hatch is not None:
        check_hatch(style.hatch)


def translate_bar_style(style: BarStyle, backend: Backend, dpi: float | None = None) -> dict:
    """
    将 `BarStyle` 中显式指定的字段转换为后端参数。

    纹理沿用描边色。在 Plotly 中，``edge_color`` 同时设置 ``marker_pattern_fgcolor``。
    ``hatch='none'`` 转换为空字符串，用于清除纹理。

    Parameters
    ----------
    style : BarStyle
        要翻译的样式。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    dpi : float, optional
        Plotly 把磅换成像素用的分辨率；Plotly 必填，matplotlib 不用。

    Returns
    -------
    dict
        matplotlib：``ax.bar`` 的 ``color``、``edgecolor``、``linewidth``、``hatch``，误差棒的 ``ecolor``、
        ``elinewidth``、``capsize`` （都是磅）。Plotly：trace 的扁平写法 ``marker_color``、``marker_line_color``、
        ``marker_line_width``、``marker_pattern_shape``、``marker_pattern_fgcolor``、``error_y_color``、
        ``error_y_thickness``、``error_y_width`` （像素；``error_y_width`` 与 matplotlib 的 ``capsize`` 一样是端帽的半长）。

    Raises
    ------
    ValueError
        后端是 Plotly 却没给 *dpi*；或某个字段写错。
    """
    check_backend(backend)
    check_bar_style(style)

    def color(value):
        return None if value is None else translate_color(value, backend)

    hatch = None if style.hatch is None else HATCHES[style.hatch][backend]
    if backend == 'matplotlib':
        native = {'color': color(style.color), 'edgecolor': color(style.edge_color), 'linewidth': style.edge_width,
                  'hatch': hatch, 'ecolor': color(style.error_color), 'elinewidth': style.error_width,
                  'capsize': style.capsize}
        return {key: value for key, value in native.items() if value is not None}

    if dpi is None:
        raise ValueError("Plotly 的描边、误差棒宽度要按 dpi 把磅换成像素，请传入 dpi")

    def px(points):
        return None if points is None else translate_points(points, dpi, backend)

    native = {'marker_color': color(style.color), 'marker_line_color': color(style.edge_color),
              'marker_line_width': px(style.edge_width), 'marker_pattern_shape': hatch,
              'marker_pattern_fgcolor': color(style.edge_color),
              'error_y_color': color(style.error_color), 'error_y_thickness': px(style.error_width),
              'error_y_width': px(style.capsize)}
    return {key: value for key, value in native.items() if value is not None}


# 空心散点的填充（透明）在各后端的写法
HOLLOW_FILL: dict[str, str] = {'matplotlib': 'none', 'plotly': 'rgba(0,0,0,0)'}


def translate_scatter_style(style: ScatterStyle, backend: Backend, dpi: float | None = None,
                            fallback_color=None) -> dict:
    """
    将 `ScatterStyle` 转换成后端使用的散点参数。

    Parameters
    ----------
    style : ScatterStyle
        要翻译的散点样式。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    dpi : float, optional
        Plotly 把磅换成像素用的分辨率；Plotly 必填，matplotlib 不用。
    fallback_color : optional
        未指定 ``color`` 时使用的颜色，格式应符合目标后端的要求。

    Returns
    -------
    dict
        matplotlib：``ax.scatter`` 的参数 ``facecolors``、``edgecolors``、``linewidths``、``s`` （面积，大小²）、
        ``marker``、``alpha``。Plotly：trace 的扁平写法 ``marker_color``、``marker_line_color``、
        ``marker_line_width``、``marker_size`` （像素）、``marker_symbol``、``marker_opacity``，
        可直接交给 ``go.Scatter(...)`` 或 ``trace.update(...)``。

    Raises
    ------
    ValueError
        后端是 Plotly 却没给 *dpi*；或某个字段写错。

    Notes
    -----
    空心标记使用透明填充。描边优先采用 ``edge_color``，默认沿用标记颜色。
    """
    check_backend(backend)
    check_scatter_style(style)
    color = fallback_color if style.color is None else translate_color(style.color, backend)
    edge = color if style.edge_color is None else translate_color(style.edge_color, backend)
    fill = HOLLOW_FILL[backend] if style.filled is False else color
    marker = None if style.marker is None else translate_marker(style.marker, backend)
    if backend == 'matplotlib':
        native = {'facecolors': fill, 'edgecolors': edge, 'marker': marker,
                  's': None if style.size is None else style.size ** 2,
                  'linewidths': style.edge_width, 'alpha': style.alpha}
    else:
        if dpi is None:
            raise ValueError("Plotly 的标记大小要按 dpi 把磅换成像素，请传入 dpi")
        px = lambda points: None if points is None else translate_points(points, dpi, backend)   # noqa: E731
        native = {'marker_color': fill, 'marker_line_color': edge, 'marker_symbol': marker,
                  'marker_size': px(style.size), 'marker_line_width': px(style.edge_width),
                  'marker_opacity': style.alpha}
    return {key: value for key, value in native.items() if value is not None}


# 缓存标记的填充色，供空心标记恢复填充时使用。
_FILL_ATTR = '_plotlib_fill'


def remember_fill(artist, color) -> None:
    """
    把一组散点的填充色（后端写法）记在画出的对象上；*color* 为 None 时不记。

    后端画散点时调用一次，散点回调改了 ``color`` 时再更新。
    """
    if color is not None:
        setattr(artist, _FILL_ATTR, color)


def remembered_fill(artist, default=None):
    """
    取出 `remember_fill` 记下的填充色；没记过时返回 *default*。
    """
    return getattr(artist, _FILL_ATTR, default)


def is_line_marker(marker: str | None) -> bool:
    """
    *marker* （通用写法）在 matplotlib 里是不是线形标记（``'x'``、``'cross'``）。

    线形标记没有填充，matplotlib 用填充色画笔画、不接受 ``edgecolors``。
    """
    return marker is not None and not MarkerStyle(translate_marker(marker, 'matplotlib')).is_filled()


# ══════════════════════════════════════════════
# 版式和尺寸转换
# ══════════════════════════════════════════════

def _inside(loc: str, x: float, y: float, xanchor: str, yanchor: str) -> dict[str, dict]:
    """
    生成图内图例的后端参数。Matplotlib 使用 *loc*，Plotly 使用相对绘图区的坐标和锚点。
    """
    return {'matplotlib': {'loc': loc}, 'plotly': {'x': x, 'y': y, 'xanchor': xanchor, 'yanchor': yanchor}}


# 将 LegendStyle.position 的通用取值映射到后端参数。
LEGEND_POSITIONS: dict[str, dict[str, dict]] = {
    'upper right':   _inside('upper right', 0.98, 0.98, 'right', 'top'),
    'upper left':    _inside('upper left', 0.02, 0.98, 'left', 'top'),
    'lower right':   _inside('lower right', 0.98, 0.02, 'right', 'bottom'),
    'lower left':    _inside('lower left', 0.02, 0.02, 'left', 'bottom'),
    'upper center':  _inside('upper center', 0.5, 0.98, 'center', 'top'),
    'lower center':  _inside('lower center', 0.5, 0.02, 'center', 'bottom'),
    'center left':   _inside('center left', 0.02, 0.5, 'left', 'middle'),
    'center right':  _inside('center right', 0.98, 0.5, 'right', 'middle'),
    'center':        _inside('center', 0.5, 0.5, 'center', 'middle'),
    # 'best' 在 Plotly 中映射为右上角。
    'best':          {'matplotlib': {'loc': 'best'}, 'plotly': _inside('', 0.98, 0.98, 'right', 'top')['plotly']},
    'outside right': {'matplotlib': {'loc': 'center left', 'bbox_to_anchor': (1, 0.5)},       # 图外右侧，竖直居中
                      'plotly':     {'x': 1.02, 'y': 0.5, 'xanchor': 'left', 'yanchor': 'middle'}},
    # 图例右边缘与绘图区右边缘对齐。Matplotlib 需取消默认的锚点间距。
    'outside top right': {'matplotlib': {'loc': 'lower right', 'bbox_to_anchor': (1, 1.02), 'borderaxespad': 0},
                          'plotly':     {'x': 1, 'y': 1.02, 'xanchor': 'right', 'yanchor': 'bottom'}},
}

# 刻度格式（AxisStyle.format）的写法：'{x:.2f}'、'{y:.1e}'
_TICK_FORMAT = re.compile(r"\{([xy]):([^}]*)\}")
_PLOTLY_TICK_FORMAT = re.compile(r"\{[xy]:(\.\d+[feg%])\}")    # Plotly（d3）能直接对应的只有这几种


def translate_legend(position: str, backend: Backend) -> dict:
    """
    把图例位置翻译成后端参数。

    Parameters
    ----------
    position : str
        ``LEGEND_POSITIONS`` 里的位置词，如 ``'upper right'``、``'outside right'``。
    backend : {'matplotlib', 'plotly'}
        目标后端。

    Returns
    -------
    dict
        matplotlib：交给 ``ax.legend(**参数)`` 的 ``loc`` （图外位置还有 ``bbox_to_anchor`` 等）；
        Plotly：``layout.legend`` 的 ``x``、``y``、``xanchor``、``yanchor``。返回的是副本，可以放心修改。

    Raises
    ------
    ValueError
        不认识的位置词。
    """
    check_backend(backend)
    if position not in LEGEND_POSITIONS:
        raise ValueError(f"不支持的图例位置 {position!r}，可用 {_words(LEGEND_POSITIONS)}")
    return dict(LEGEND_POSITIONS[position][backend])


@overload
def translate_tick_format(fmt: str, backend: Literal['matplotlib']) -> Callable[[Any, Any], str]: ...
@overload
def translate_tick_format(fmt: str, backend: Literal['plotly']) -> str: ...
def translate_tick_format(fmt: str, backend: Backend) -> Callable[[Any, Any], str] | str:
    """
    把刻度格式（如 ``'{x:.2f}'``）翻译成后端的格式器。

    Parameters
    ----------
    fmt : str
        Python 格式字符串，用 ``x`` 或 ``y`` 作变量名，如 ``'{x:.2f}'``、``'{y:.1e}'``。
    backend : {'matplotlib', 'plotly'}
        目标后端。

    Returns
    -------
    callable or str
        matplotlib：格式函数 ``f(值, 位置) -> 文字``，交给 ``set_major_formatter``；
        Plotly：d3 格式字符串，如 ``'.2f'``，交给 ``tickformat``。

    Raises
    ------
    ValueError
        *fmt* 缺少 ``{x:...}`` 或 ``{y:...}``，或格式超出目标后端的支持范围。
    """
    check_backend(backend)
    if (match := _TICK_FORMAT.search(fmt)) is None:
        raise ValueError(f"刻度格式 {fmt!r} 里要有 {{x:...}} 或 {{y:...}}，如 '{{x:.2f}}'")
    if backend == 'matplotlib':
        key = match.group(1)
        try:
            # 先试一次：格式写错（如 '{x:.2q}'）在这里报，不拖到渲染（canvas.draw / 保存图片）时才报
            fmt.format(**{key: 1.0})
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ValueError(f"刻度格式 {fmt!r} 写错了：{exc}") from exc
        return lambda value, _pos: fmt.format(**{key: value})
    if (plotly_match := _PLOTLY_TICK_FORMAT.fullmatch(fmt)) is None:
        raise ValueError(f"Plotly 暂不支持此刻度格式: {fmt!r}")
    return plotly_match.group(1)


# ══════════════════════════════════════════════
# 坐标轴、边框和图例
# ══════════════════════════════════════════════
_SCALES = ('linear', 'log', 'symlog', 'logit')
_PLOTLY_SCALES = ('linear', 'log')


def check_axis_style(style: AxisStyle, backend: Backend) -> None:
    """
    校验 `AxisStyle` 的字段值及后端兼容性。

    Raises
    ------
    TypeError
        ``limits`` 不是两个数字（或 None），``scaler`` 不是数字，颜色类型不对。
    ValueError
        轴类型或格式无效，对数轴边界非正，或目标后端不支持相应设置。
    """
    check_backend(backend)
    if style.scale is not None and style.scale not in _SCALES:
        raise ValueError(f"不支持的刻度类型 {style.scale!r}，可用 {_words(_SCALES)}")
    if style.limits is not None:
        if not (isinstance(style.limits, _SEQUENCES) and len(style.limits) == 2):
            raise TypeError(f"limits 要写 (下限, 上限)，某一侧不限写 None，实际是 {style.limits!r}")
        for value in style.limits:
            if value is not None and not _is_number(value):
                raise TypeError(f"limits 里要写数字或 None，实际是 {value!r}")
        if style.scale == 'log' and any(v is not None and v <= 0 for v in style.limits):
            raise ValueError("对数轴边界必须大于 0")
    if style.format is not None:
        translate_tick_format(style.format, 'matplotlib')
    if style.scaler is not None and not _is_number(style.scaler):
        raise TypeError(f"scaler 要写数字，实际是 {style.scaler!r}")
    if style.color is not None:
        check_color(style.color)
    if backend == 'plotly':
        if style.scale is not None and style.scale not in _PLOTLY_SCALES:
            raise ValueError(f"Plotly 的刻度类型只支持 {_words(_PLOTLY_SCALES)}，实际是 {style.scale!r}")
        if style.scaler is not None and style.scaler != 1:
            raise ValueError("Plotly 暂不支持显示值缩放 scaler；不会修改原始数据替代")
        if style.format is not None:
            translate_tick_format(style.format, 'plotly')


def translate_axis_style(style: AxisStyle, backend: Backend, letter: Literal['x', 'y'],
                         log: bool | None = None) -> dict:
    """
    把 `AxisStyle` 翻译成后端的轴设置，只含写了的字段。

    Parameters
    ----------
    style : AxisStyle
        要翻译的轴样式。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    letter : {'x', 'y'}
        这根轴的方向。只写了 ``scaler``、没写 ``format`` 时，按 ``'{x:g}'`` 或 ``'{y:g}'`` 显示。
    log : bool, optional
        应用样式后是否为对数轴，仅用于 Plotly。省略时根据 ``style.scale`` 判断。

    Returns
    -------
    dict
        matplotlib：``scale``、``limits``、``formatter`` （格式函数）、``color``，
        由 `plotlib.backends.matplotlib_styles.apply_axis` 应用；
        Plotly：轴配置 ``type``、``range`` / ``autorange`` / ``autorangeoptions``、``tickformat`` 和着色属性，
        可直接交给 ``fig.update_layout``。

    Notes
    -----
    ``limits`` 使用数据坐标。Plotly 对数轴使用以 10 为底的对数坐标。
    应用样式的函数传入当前轴类型，以正确换算单独设置的坐标边界。
    """
    check_axis_style(style, backend)
    color = None if style.color is None else translate_color(style.color, backend)
    if backend == 'matplotlib':
        native: dict = {'scale': style.scale, 'limits': style.limits, 'color': color}
        scaler = 1 if style.scaler is None else style.scaler
        if style.format is not None or scaler != 1:
            text_format = translate_tick_format(style.format or '{' + letter + ':g}', backend)
            native['formatter'] = lambda value, pos: text_format(value * scaler, pos)
        return {key: value for key, value in native.items() if value is not None}

    native = {}
    if style.scale is not None:
        native['type'] = style.scale
    if style.format is not None:
        native['tickformat'] = translate_tick_format(style.format, backend)
    if style.limits is not None:
        # 公共输入用数据值；Plotly 对数轴的边界用 log10
        log = style.scale == 'log' if log is None else log
        if log and any(v is not None and v <= 0 for v in style.limits):
            raise ValueError("对数轴边界必须大于 0")
        low, high = (math.log10(v) if log and v is not None else v for v in style.limits)
        if low is not None and high is not None:
            native.update(range=[low, high], autorange=False)
        elif low is not None or high is not None:
            # 用 minallowed 或 maxallowed 保留显式边界，避免自动调整边距时重置。
            native['autorange'] = True
            native['autorangeoptions'] = {'minallowed': low} if low is not None else {'maxallowed': high}
    if color is not None:
        native.update(title_font_color=color, tickfont_color=color, tickcolor=color, linecolor=color)
    return native


def check_frame(frame: FrameStyle) -> None:
    """校验 `FrameStyle`：线宽为正数，``top`` / ``right`` 为开关。"""
    _check_positive('width', frame.width)
    _check_switch('top', frame.top)
    _check_switch('right', frame.right)


def translate_frame(frame: FrameStyle, backend: Backend, dpi: float | None = None) -> dict:
    """
    把 `FrameStyle` 翻译成 ``{'linewidth', 'top', 'right'}``，只含写了的字段。

    线宽在 matplotlib 用磅，在 Plotly 按 *dpi* 换成像素。上、右边框具体怎么画由后端决定
    （matplotlib 用 spines，Plotly 用轴的 mirror）。

    Raises
    ------
    ValueError
        后端是 Plotly、写了线宽却没给 *dpi*。
    """
    check_backend(backend)
    check_frame(frame)
    native: dict = {'top': frame.top, 'right': frame.right}
    if frame.width is not None and backend == 'matplotlib':
        native['linewidth'] = frame.width
    elif frame.width is not None:
        if dpi is None:
            raise ValueError("Plotly 的轴线宽要按 dpi 把磅换成像素，请传入 dpi")
        native['linewidth'] = translate_points(frame.width, dpi, backend)
    return {key: value for key, value in native.items() if value is not None}


def check_legend_style(legend: LegendStyle, backend: Backend) -> None:
    """
    校验 `LegendStyle`：位置是 ``LEGEND_POSITIONS`` 里的词，字号为正数，``frame`` / ``draggable`` 为开关。

    Plotly 忽略版式预设中的 ``draggable``。显式图例回调的后端限制由
    `~plotlib.formatters.make_legend_formatter` 校验。
    """
    check_backend(backend)
    if legend.position is not None and legend.position not in LEGEND_POSITIONS:
        raise ValueError(f"不支持的图例位置 {legend.position!r}，可用 {_words(LEGEND_POSITIONS)}")
    _check_positive('font_size', legend.font_size)
    _check_switch('frame', legend.frame)
    _check_switch('draggable', legend.draggable)


def translate_legend_style(legend: LegendStyle, backend: Backend, dpi: float | None = None) -> dict:
    """
    把 `LegendStyle` 翻译成后端的图例参数，只含写了的字段。

    Parameters
    ----------
    legend : LegendStyle
        要翻译的图例样式。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    dpi : float, optional
        Plotly 把字号从磅换成像素用的分辨率；写了字号时 Plotly 必填。

    Returns
    -------
    dict
        matplotlib：``loc``、``bbox_to_anchor``、``borderaxespad``、``fontsize``、``frameon``、``draggable``
        （建图例时传前几项，拖动在建好后另设）；
        Plotly：``layout.legend`` 的 ``x``、``y``、``xanchor``、``yanchor``、``font.size``、
        ``borderwidth``、``bordercolor``、``bgcolor``。``draggable`` 不翻译，Plotly 的拖动是显示时的设置。
    """
    check_legend_style(legend, backend)
    native = {} if legend.position is None else translate_legend(legend.position, backend)
    if backend == 'matplotlib':
        native.update({key: value for key, value in
                       (('fontsize', legend.font_size), ('frameon', legend.frame), ('draggable', legend.draggable))
                       if value is not None})
        return native
    if legend.font_size is not None:
        if dpi is None:
            raise ValueError("Plotly 的图例字号要按 dpi 把磅换成像素，请传入 dpi")
        native['font'] = {'size': translate_points(legend.font_size, dpi, backend)}
    if legend.frame is not None:
        native.update(borderwidth=1 if legend.frame else 0, bordercolor='black',
                      bgcolor='white' if legend.frame else 'rgba(0,0,0,0)')
    return native


def translate_points(value: float, dpi: float, backend: Backend) -> float:
    """
    把以磅（1/72 英寸）为单位的量（字号、线宽、刻度长短）换成后端单位。

    matplotlib 本来就用磅，原样返回；Plotly 用像素：``磅 × dpi / 72``。

    Examples
    --------
    >>> translate_points(22, dpi=100, backend='plotly')
    30.555555555555557
    """
    check_backend(backend)
    return value if backend == 'matplotlib' else value * dpi / 72


def translate_figsize(size: tuple[float, float], dpi: float, backend: Backend) -> tuple:
    """
    把以英寸为单位的图尺寸 ``(宽, 高)`` 换成后端单位。

    matplotlib 本来就用英寸，原样返回；Plotly 用像素：``英寸 × dpi``，取整。

    Examples
    --------
    >>> translate_figsize((10, 8), dpi=100, backend='plotly')
    (1000, 800)
    """
    check_backend(backend)
    width, height = size
    return (width, height) if backend == 'matplotlib' else (round(width * dpi), round(height * dpi))


# ══════════════════════════════════════════════
# 刻度参数转换
# ══════════════════════════════════════════════
TICK_DIRECTIONS: dict[str, dict[str, str]] = {
    'out': {'matplotlib': 'out', 'plotly': 'outside'},
    'in':  {'matplotlib': 'in',  'plotly': 'inside'},
}
# 将次刻度标签模式映射到 Plotly 的 minorloglabels。
MINOR_LABELS: dict[str, str] = {'none': 'none', 'short': 'small digits', 'full': 'complete'}

_TICK_SIZES = ('length', 'width', 'minor_length', 'minor_width', 'label_size', 'minor_label_size')   # 必须 > 0
_TICK_PADS = ('label_pad', 'minor_label_pad')                                                          # 可以为 0
_TICK_FONTS = ('label_font', 'minor_label_font')
# Matplotlib 支持单独设置次刻度标签样式。
_MATPLOTLIB_ONLY_TICKS = ('minor_label_font', 'minor_label_size', 'minor_label_pad')


def check_ticks(ticks: TickStyle, backend: Backend) -> None:
    """
    校验 `TickStyle` 的字段类型、取值和后端支持情况。

    Raises
    ------
    TypeError
        长度、字号不是数字，字体不是字符串，开关不是 True / False。
    ValueError
        不认识的朝向或次刻度文字写法；长度、字号不大于 0（间距可以为 0）；
        在 Plotly 后端设置了次刻度文字的字体、字号或间距（Plotly 的次刻度没有这些属性）。
    """
    check_backend(backend)
    if ticks.direction is not None and ticks.direction not in TICK_DIRECTIONS:
        raise ValueError(f"不支持的刻度朝向 {ticks.direction!r}，可用 {_words(TICK_DIRECTIONS)}")
    if ticks.minor_labels is not None and ticks.minor_labels not in MINOR_LABELS:
        raise ValueError(f"不支持的次刻度文字写法 {ticks.minor_labels!r}，可用 {_words(MINOR_LABELS)}")
    _check_switch('minor', ticks.minor)
    for name in _TICK_SIZES:
        _check_positive(name, getattr(ticks, name))
    for name in _TICK_PADS:
        _check_positive(name, getattr(ticks, name), allow_zero=True)
    for name in _TICK_FONTS:
        if (value := getattr(ticks, name)) is not None and not isinstance(value, str):
            raise TypeError(f"{name} 要写字体名，实际是 {value!r}")
    if backend == 'plotly':
        unsupported = [name for name in _MATPLOTLIB_ONLY_TICKS if getattr(ticks, name) is not None]
        if unsupported:
            raise ValueError(f"Plotly 的次刻度没有文字属性，不能单独设置 {'、'.join(unsupported)}；"
                             f"次刻度文字与主刻度文字相同（对数轴的 'short' 由 Plotly 自动画小一号）")


def translate_ticks(ticks: TickStyle, backend: Backend, dpi: float | None = None) -> dict:
    """
    将 `TickStyle` 中显式指定的字段转换为后端刻度参数。

    Parameters
    ----------
    ticks : TickStyle
        要翻译的刻度样式。
    backend : {'matplotlib', 'plotly'}
        目标后端。
    dpi : float, optional
        Plotly 把磅换成像素用的分辨率；Plotly 必填，matplotlib 不用。

    Returns
    -------
    dict
        matplotlib：``{'major': tick_params 参数, 'minor': tick_params 参数, 'minor_visible': 开关,
        'minor_labels': 写法}``，由 `plotlib.backends.matplotlib_styles` 应用；
        次刻度文字没单独写字体、字号、间距时与主刻度相同。

        Plotly：轴配置 ``ticks``、``ticklen``、``tickwidth``、``minor``、``tickfont``、
        ``ticklabelstandoff`` （整数像素）、``minorloglabels``。

    Notes
    -----
    Plotly 的 ``minor.ticks`` 同时决定次刻度显不显示和朝向：关掉次刻度时为 ``''``，
    只写了 ``minor=True`` 时按朝外。
    """
    check_ticks(ticks, backend)
    direction = None if ticks.direction is None else TICK_DIRECTIONS[ticks.direction][backend]

    if backend == 'matplotlib':
        def written(**kwargs) -> dict:
            return {key: value for key, value in kwargs.items() if value is not None}

        native: dict = {
            'major': written(direction=direction, length=ticks.length, width=ticks.width,
                             labelfontfamily=ticks.label_font, labelsize=ticks.label_size, pad=ticks.label_pad),
            'minor': written(direction=direction, length=ticks.minor_length, width=ticks.minor_width,
                             labelfontfamily=ticks.minor_label_font or ticks.label_font,
                             labelsize=ticks.minor_label_size or ticks.label_size,
                             pad=ticks.minor_label_pad if ticks.minor_label_pad is not None else ticks.label_pad),
            'minor_visible': ticks.minor,
            'minor_labels': ticks.minor_labels,
        }
        return {key: value for key, value in native.items() if value not in (None, {})}

    if dpi is None:
        raise ValueError("Plotly 的刻度要按 dpi 把磅换成像素，请传入 dpi")
    px = lambda points: translate_points(points, dpi, 'plotly')     # noqa: E731  磅 → 像素
    native = {}
    if direction is not None:
        native['ticks'] = direction
    if ticks.length is not None:
        native['ticklen'] = px(ticks.length)
    if ticks.width is not None:
        native['tickwidth'] = px(ticks.width)

    minor = {}
    if ticks.minor is False:
        minor['ticks'] = ''
    elif direction is not None or ticks.minor:
        minor['ticks'] = direction or TICK_DIRECTIONS['out']['plotly']     # 只写了 minor=True 时按朝外
    if ticks.minor_length is not None:
        minor['ticklen'] = px(ticks.minor_length)
    if ticks.minor_width is not None:
        minor['tickwidth'] = px(ticks.minor_width)
    if minor:
        native['minor'] = minor

    font = {}
    if ticks.label_font is not None:
        font['family'] = ticks.label_font
    if ticks.label_size is not None:
        font['size'] = px(ticks.label_size)
    if font:
        native['tickfont'] = font
    if ticks.label_pad is not None:
        # Plotly 的 ticklabelstandoff 使用整数像素。
        native['ticklabelstandoff'] = round(px(ticks.label_pad))
    if ticks.minor_labels is not None:
        native['minorloglabels'] = MINOR_LABELS[ticks.minor_labels]
    return native
