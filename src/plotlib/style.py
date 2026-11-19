"""
公共样式词汇与后端翻译（STRUCTURE_REVIEW 步骤 4.3）。

约定：程序入口（分组配置、formatter 工厂、DataPlotter 的 linestyle）只接受一套标准写法，
不认识就报错，也不替用户改写；翻译只在后端发生：translate_* 把标准写法换成各后端的原生值。

标准写法：
    线型  'solid'、'dash'、'dot'、'dashdot'；
          或自定义虚线 (实线长, 空白长, ...)：正数、偶数个，单位是线宽的倍数
    标记  'circle'、'square'、'triangle-up'、'triangle-down'、'diamond'、'cross'、'x'
    颜色  CSS 颜色名（W3C 标准 148 个，不区分大小写）；六位色号 '#rrggbb'；RGB 三个 0~255 的整数

check_*      只校验：合法时返回 None；类型错报 TypeError，值错报 ValueError，信息里带写错的值。
translate_*  先校验，再翻译成指定后端的原生值。

这一层就是「翻译层」（6.7 起）：除了线型 / 标记 / 颜色，排版预设的图例位置、刻度格式，
以及按显式 dpi 的单位换算（磅 → 像素、英寸 → 像素）也在这里；两个后端只调用 translate_* 再应用结果。
"""
import re
from collections.abc import Callable
from numbers import Integral, Real
from typing import Any, Literal, overload

# matplotlib 的 CSS4_COLORS 与 Plotly 内置颜色名是同一套 148 个 CSS 标准名，
# 所以颜色名不用翻译，这里只借它的名字表做校验。
from matplotlib.colors import CSS4_COLORS

type Backend = Literal["matplotlib", "plotly"]

# 标准词 → 各后端原生值。加新词：在这里加一行，两个后端各写一个原生值。
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

_HEX_COLOR = re.compile(r'#[0-9a-fA-F]{6}')
_SEQUENCES = (tuple, list)

# Plotly 的默认线宽（像素）：自定义虚线换算成像素时，没给线宽就用它。
PLOTLY_DEFAULT_LINEWIDTH = 2


def check_backend(backend) -> None:
    if backend not in ("matplotlib", "plotly"):
        raise ValueError(f"不支持的 backend: {backend!r}，可用 'matplotlib'、'plotly'")


def _words(table) -> str:
    return '、'.join(f"'{word}'" for word in table)


def _is_number(x) -> bool:
    """bool 也是 int 的子类，但 True / False 当段长或颜色分量多半是写错了，不接受。"""
    return isinstance(x, Real) and not isinstance(x, bool)


# ══════════════════════════════════════════════
# 校验
# ══════════════════════════════════════════════
def check_linestyle(value) -> None:
    """标准词之一，或自定义虚线 (实线长, 空白长, ...)。"""
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
    if not isinstance(value, str):
        raise TypeError(f"标记 {value!r} 的类型不支持：应为 {_words(MARKERS)} 之一")
    if value not in MARKERS:
        raise ValueError(f"不支持的标记 {value!r}，可用 {_words(MARKERS)}")


def check_color(value) -> None:
    """CSS 颜色名（不区分大小写）、'#rrggbb'，或 RGB 三个 0~255 的整数。"""
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


# ══════════════════════════════════════════════
# 翻译：标准写法 → 后端原生值
# ══════════════════════════════════════════════
def translate_linestyle(value, backend: Backend, linewidth=None):
    """
    自定义虚线的段长是线宽的倍数：
    matplotlib 补偏移量 0，返回 (0, (段长, ...))，它自己按线宽缩放；
    Plotly 要像素：段长 × linewidth（未给时用 Plotly 默认线宽 2），返回 '9px,15px' 这样的字符串。
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
    check_backend(backend)
    check_marker(value)
    return MARKERS[value][backend]


def translate_color(value, backend: Backend):
    """颜色名和色号两个后端都认，原样返回；RGB 到 matplotlib 换成 0~1，到 Plotly 写成 'rgb(r,g,b)'。"""
    check_backend(backend)
    check_color(value)
    if isinstance(value, str):
        return value
    if backend == 'matplotlib':
        return tuple(x / 255 for x in value)
    return f"rgb({value[0]},{value[1]},{value[2]})"


# ══════════════════════════════════════════════
# 排版与尺寸的翻译（STRUCTURE_REVIEW 6.7）：通用的换算都放在这一层，两个后端只管应用结果
# ══════════════════════════════════════════════

# 图例位置（排版预设 layouts.LayoutPreset.legend 的写法）→ 各后端参数
LEGEND_POSITIONS: dict[str, dict[str, dict]] = {
    'outside right': {'matplotlib': {'loc': 'center left', 'bbox_to_anchor': (1, 0.5)},       # 图外右侧，竖直居中
                      'plotly':     {'x': 1.02, 'y': 0.5, 'xanchor': 'left', 'yanchor': 'middle'}},
    'lower right':   {'matplotlib': {'loc': 'lower right'},                                    # 图内右下角
                      'plotly':     {'x': 0.98, 'y': 0.02, 'xanchor': 'right', 'yanchor': 'bottom'}},
}

# 刻度格式的写法与 make_axes_formatter 的 x_format / y_format 相同：'{x:.2f}'、'{y:.1e}'
_TICK_FORMAT = re.compile(r"\{([xy]):([^}]*)\}")
_PLOTLY_TICK_FORMAT = re.compile(r"\{[xy]:(\.\d+[feg%])\}")    # Plotly（d3）能直接对应的只有这几种


def translate_legend(position: str, backend: Backend) -> dict:
    """图例位置 → matplotlib 的 ax.legend(**参数) / Plotly 的 layout.legend。"""
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
    刻度格式 '{x:.2f}' → matplotlib：格式函数 f(值, 位置) -> 文字（交给 set_major_formatter）；
                      → Plotly：d3 格式 '.2f'（交给 tickformat）。Plotly 对应不了的格式报错，不悄悄忽略。
    """
    check_backend(backend)
    if (match := _TICK_FORMAT.search(fmt)) is None:
        raise ValueError(f"刻度格式 {fmt!r} 里要有 {{x:...}} 或 {{y:...}}，如 '{{x:.2f}}'")
    if backend == 'matplotlib':
        key = match.group(1)
        return lambda value, _pos: fmt.format(**{key: value})
    if (plotly_match := _PLOTLY_TICK_FORMAT.fullmatch(fmt)) is None:
        raise ValueError(f"Plotly 暂不支持此刻度格式: {fmt!r}")
    return plotly_match.group(1)


def translate_points(value: float, dpi: float, backend: Backend) -> float:
    """以磅（1/72 英寸）为单位的量（字号、线宽）→ 后端单位：matplotlib 本来就用磅；Plotly 用像素 = 磅 × dpi / 72。"""
    check_backend(backend)
    return value if backend == 'matplotlib' else value * dpi / 72


def translate_figsize(size: tuple[float, float], dpi: float, backend: Backend) -> tuple:
    """以英寸为单位的图尺寸 → 后端单位：matplotlib 本来就用英寸；Plotly 用像素 = 英寸 × dpi。"""
    check_backend(backend)
    width, height = size
    return (width, height) if backend == 'matplotlib' else (round(width * dpi), round(height * dpi))
