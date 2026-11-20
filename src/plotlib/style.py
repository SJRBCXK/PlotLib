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
刻度（TickStyle，2026-11-20）也在这里：check_ticks / translate_ticks。
"""
import math
import re
from collections.abc import Callable
from numbers import Integral, Real
from typing import Any, Literal, overload

# matplotlib 的 CSS4_COLORS 与 Plotly 内置颜色名是同一套 148 个 CSS 标准名，
# 所以颜色名不用翻译，这里只借它的名字表做校验。
from matplotlib.colors import CSS4_COLORS

from .plot_spec import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle

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


# LineStyle（颜色之外）对每种画法有哪些字段看得见（两个后端共用）：散点没有线，柱状图没有线和标记。
# 颜色对三种画法都生效，由后端单独处理（6.5 颜色一次赋值）。
STYLE_FIELDS_BY_KIND: dict[str, tuple[str, ...]] = {
    'line': ('width', 'linestyle', 'marker', 'marker_size'),
    'scatter': ('marker', 'marker_size'),
    'bar': (),
}


def _check_positive(name: str, value, allow_zero: bool = False) -> None:
    """长度、宽度、字号：要写数字（磅），且大于 0（间距类可以为 0）。None 表示不改，不检查。"""
    if value is None:
        return
    if not _is_number(value):
        raise TypeError(f"{name} 要写数字（磅），实际是 {value!r}")
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} 要大于 0{'（可以为 0）' if allow_zero else ''}，实际是 {value!r}")


def _check_switch(name: str, value) -> None:
    if value is not None and not isinstance(value, bool):
        raise TypeError(f"{name} 是开关，要写 True / False，实际是 {value!r}")


# ══════════════════════════════════════════════
# 线（LineStyle，2026-11-20 样式对象化）
# ══════════════════════════════════════════════
def check_line_style(style: LineStyle) -> None:
    """校验 LineStyle 写了的字段（颜色、线型、标记用上面的标准写法）。"""
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
    LineStyle → 各后端原生值，只含写了的字段：
      matplotlib：Line2D 的属性 {'linewidth', 'color', 'linestyle', 'marker', 'markersize'}（磅，dpi 不用）；
      Plotly：    trace 的扁平写法 {'line_width', 'line_color', 'line_dash', 'marker_symbol', 'marker_size', 'marker_color'}，
                  可直接交给 go.Scatter(...) / trace.update(...)；磅按 dpi 换成像素；点跟着线色。
    自定义虚线的段长是线宽的倍数：Plotly 要像素，按这里写的线宽换算，没写时用 dash_width（已是像素，一般是全局线宽）。
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


def only_fields(style: LineStyle, names: tuple[str, ...]) -> LineStyle:
    """只留 names 里的字段，其余置 None（按画法取看得见的字段，见 STYLE_FIELDS_BY_KIND）。"""
    return type(style)(**{name: getattr(style, name) for name in names})


# ══════════════════════════════════════════════
# 排版与尺寸的翻译（STRUCTURE_REVIEW 6.7）：通用的换算都放在这一层，两个后端只管应用结果
# ══════════════════════════════════════════════

def _inside(loc: str, x: float, y: float, xanchor: str, yanchor: str) -> dict[str, dict]:
    """图内的位置：matplotlib 直接用 loc 词；Plotly 用相对绘图区的坐标，离边 0.02。"""
    return {'matplotlib': {'loc': loc}, 'plotly': {'x': x, 'y': y, 'xanchor': xanchor, 'yanchor': yanchor}}


# 图例位置（LegendStyle.position 的写法；排版预设、全局、图例工厂共用这一张表，样式对象化起统一）→ 各后端参数
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
    # matplotlib 自动找空位；Plotly 不会，按右上角
    'best':          {'matplotlib': {'loc': 'best'}, 'plotly': _inside('', 0.98, 0.98, 'right', 'top')['plotly']},
    'outside right': {'matplotlib': {'loc': 'center left', 'bbox_to_anchor': (1, 0.5)},       # 图外右侧，竖直居中
                      'plotly':     {'x': 1.02, 'y': 0.5, 'xanchor': 'left', 'yanchor': 'middle'}},
    # 图外上方、右边与绘图区对齐（双 Y 轴，2026-11-20 参照 Origin 图）：图例的右下角钉在绘图区右上角稍上方；
    # matplotlib 默认在图例与锚点之间留 borderaxespad 的空隙，设 0 才能右边对齐
    'outside top right': {'matplotlib': {'loc': 'lower right', 'bbox_to_anchor': (1, 1.02), 'borderaxespad': 0},
                          'plotly':     {'x': 1, 'y': 1.02, 'xanchor': 'right', 'yanchor': 'bottom'}},
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


# ══════════════════════════════════════════════
# 轴、边框、图例（AxisStyle / FrameStyle / LegendStyle，2026-11-20 样式对象化）
# ══════════════════════════════════════════════
_SCALES = ('linear', 'log', 'symlog', 'logit')
_PLOTLY_SCALES = ('linear', 'log')


def check_axis_style(style: AxisStyle, backend: Backend) -> None:
    """校验 AxisStyle；Plotly 做不到的（symlog / logit、显示值缩放）报错，不悄悄忽略。"""
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
        translate_tick_format(style.format, 'matplotlib')      # 格式写错先报错（Plotly 另外检查能不能对应）
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


def translate_axis_style(style: AxisStyle, backend: Backend, letter: Literal['x', 'y']) -> dict:
    """
    AxisStyle → 各后端原生值，只含写了的字段。letter 是这根轴的方向（只给了 scaler、没给 format 时按 '{x:g}' 显示）。
      matplotlib：{'scale', 'limits', 'formatter'（格式函数，或 None 不改）, 'color'}，由 backends/matplotlib_styles.py 应用；
      Plotly：    轴配置 {'type', 'range' / 'autorange' / 'autorangeoptions', 'tickformat', 轴着色}，可直接 update_layout。
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
        low, high = (math.log10(v) if style.scale == 'log' and v is not None else v for v in style.limits)
        if low is not None and high is not None:
            native.update(range=[low, high], autorange=False)
        elif low is not None or high is not None:
            # 只给一侧时用 minallowed / maxallowed：自动范围照常计算，给定的一侧直接作为边界。不用 autorange="min"/"max"：
            # Plotly.js 在 automargin 扩边重绘时会把它重置成完全自动，边界失效
            native['autorange'] = True
            native['autorangeoptions'] = {'minallowed': low} if low is not None else {'maxallowed': high}
    if color is not None:
        native.update(title_font_color=color, tickfont_color=color, tickcolor=color, linecolor=color)
    return native


def check_frame(frame: FrameStyle) -> None:
    _check_positive('width', frame.width)
    _check_switch('top', frame.top)
    _check_switch('right', frame.right)


def translate_frame(frame: FrameStyle, backend: Backend, dpi: float | None = None) -> dict:
    """
    FrameStyle → {'linewidth': 轴线宽, 'top': 画不画上边框, 'right': 画不画右边框}，只含写了的字段；
    线宽 matplotlib 用磅，Plotly 按 dpi 换成像素。上 / 右边框怎么画由后端决定（matplotlib 的 spines，Plotly 的 mirror）。
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
    """校验 LegendStyle。draggable 只在单独检查用户写的图例回调时才拦（见 formatters），预设里写了 Plotly 直接不用。"""
    check_backend(backend)
    if legend.position is not None and legend.position not in LEGEND_POSITIONS:
        raise ValueError(f"不支持的图例位置 {legend.position!r}，可用 {_words(LEGEND_POSITIONS)}")
    _check_positive('font_size', legend.font_size)
    _check_switch('frame', legend.frame)
    _check_switch('draggable', legend.draggable)


def translate_legend_style(legend: LegendStyle, backend: Backend, dpi: float | None = None) -> dict:
    """
    LegendStyle → 各后端原生值，只含写了的字段：
      matplotlib：{'loc', 'bbox_to_anchor', 'borderaxespad', 'fontsize', 'frameon', 'draggable'}（建图例时传前几项，拖动另设）；
      Plotly：    layout.legend {'x', 'y', 'xanchor', 'yanchor', 'font': {'size'}, 'borderwidth', 'bordercolor', 'bgcolor'}；
                  字号按 dpi 换成像素；draggable 不翻译（Plotly 的拖动是显示时的设置）。
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
    """以磅（1/72 英寸）为单位的量（字号、线宽）→ 后端单位：matplotlib 本来就用磅；Plotly 用像素 = 磅 × dpi / 72。"""
    check_backend(backend)
    return value if backend == 'matplotlib' else value * dpi / 72


def translate_figsize(size: tuple[float, float], dpi: float, backend: Backend) -> tuple:
    """以英寸为单位的图尺寸 → 后端单位：matplotlib 本来就用英寸；Plotly 用像素 = 英寸 × dpi。"""
    check_backend(backend)
    width, height = size
    return (width, height) if backend == 'matplotlib' else (round(width * dpi), round(height * dpi))


# ══════════════════════════════════════════════
# 刻度（2026-11-20）：TickStyle（plot_spec.py）→ 各后端原生值。只翻译写了的字段（None 表示不改）
# ══════════════════════════════════════════════
TICK_DIRECTIONS: dict[str, dict[str, str]] = {
    'out': {'matplotlib': 'out', 'plotly': 'outside'},
    'in':  {'matplotlib': 'in',  'plotly': 'inside'},
}
# 次刻度写什么 → Plotly 的 minorloglabels（matplotlib 由后端按刻度类型选格式器，见 backends/matplotlib_ticks.py）
MINOR_LABELS: dict[str, str] = {'none': 'none', 'short': 'small digits', 'full': 'complete'}

_TICK_SIZES = ('length', 'width', 'minor_length', 'minor_width', 'label_size', 'minor_label_size')   # 必须 > 0
_TICK_PADS = ('label_pad', 'minor_label_pad')                                                          # 可以为 0
_TICK_FONTS = ('label_font', 'minor_label_font')
# Plotly 的次刻度没有文字属性：这几项只有 matplotlib 能做（用户定：Plotly 报错，不悄悄忽略）
_MATPLOTLIB_ONLY_TICKS = ('minor_label_font', 'minor_label_size', 'minor_label_pad')


def check_ticks(ticks: TickStyle, backend: Backend) -> None:
    """校验 TickStyle：写法、类型、取值，以及这个后端做不做得到。合法时返回 None。"""
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
    TickStyle → 各后端原生值，只含写了的字段：
      matplotlib：{'major': tick_params 参数, 'minor': tick_params 参数, 'minor_visible': 开关, 'minor_labels': 写法}；
                  次刻度文字没单独写字体 / 字号 / 间距时与主刻度相同。matplotlib 本来就用磅，dpi 不用。
      Plotly：    轴配置 {'ticks', 'ticklen', 'tickwidth', 'minor': {...}, 'tickfont': {...}, 'ticklabelstandoff', 'minorloglabels'}，
                  磅按 dpi 换成像素。Plotly 的 minor.ticks 同时管次刻度的显示和朝向：关掉时为 ''。
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
        native['ticklabelstandoff'] = px(ticks.label_pad)
    if ticks.minor_labels is not None:
        native['minorloglabels'] = MINOR_LABELS[ticks.minor_labels]
    return native
