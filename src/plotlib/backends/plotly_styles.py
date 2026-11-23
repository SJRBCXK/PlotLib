"""
Plotly 的样式应用，与 `plotlib.backends.matplotlib_styles` 对应：后端（版式预设）和 `plotlib.formatters`
（单轴覆盖）共用。本模块不导入 plotly，只用 Figure 上的属性，所以只装 matplotlib 时也能导入。

- 轴（`AxisStyle`）：`apply_axis`；
- 边框（`FrameStyle`）：`apply_frame`；
- 刻度（`TickStyle`）：`apply_ticks`；对数轴写了刻度格式时让次刻度文字设置仍生效：`apply_log_format`；
- `figure_dpi`：读出一张图的 dpi。

Notes
-----
与 matplotlib 不同，这里的函数都接收样式对象本身、应用时才翻译，因为翻译要看这张图当时的状态：

- 磅换像素要用这张图的 dpi（后端画图时记在 ``fig.layout.meta['dpi']``）；
- Plotly 对数轴的边界（``range``、单侧的 ``minallowed`` / ``maxallowed``）要写 log10，而 ``limits`` 永远写数据值，
  刻度类型又可能在别的回调里设过，所以要看这根轴「应用后」是不是对数轴；
- 只改刻度朝向时，不能把已经关掉的次刻度打开，要看轴上现在显不显示。

matplotlib 的值不随图变（磅就是磅，边界本来就是数据值），所以那边先翻译好再应用。

Plotly 没有轴对象，参数 *axis* 是配置里的轴名（``'xaxis'``、``'yaxis'``、``'yaxis2'``）。X 轴左右共用，归左轴：
左轴（``'yaxis'``）的边框、刻度连 X 轴一起改，右轴（``'yaxis2'``）只改自己。
"""
import math
from typing import Any, Literal, cast

from ..plot_spec import Appearance, AxisStyle, FrameStyle, TickStyle
from ..style import MINOR_LABELS, translate_axis_style, translate_frame, translate_ticks


def figure_dpi(fig) -> float:
    """
    读出一张图的 dpi：后端画图时记在 ``fig.layout.meta['dpi']``；
    不是后端画的图（或 *fig* 为 None）用默认的 100。
    """
    meta = None if fig is None else fig.layout.meta
    return meta.get('dpi', Appearance().dpi) if isinstance(meta, dict) else Appearance().dpi


# ══════════════════════════════════════════════
# 轴（AxisStyle）
# ══════════════════════════════════════════════
def apply_axis(fig, axis: str, style: AxisStyle, letter: Literal['x', 'y']) -> None:
    """
    把 `AxisStyle` 用到 Plotly 的一根轴上。只改写了的。

    Parameters
    ----------
    fig : `plotly.graph_objects.Figure`
        图。
    axis : str
        layout 里的轴名，如 ``'xaxis'``、``'yaxis2'``。
    style : AxisStyle
        要应用的轴样式。
    letter : {'x', 'y'}
        这根轴的方向。

    Raises
    ------
    ValueError
        对数轴的边界不大于 0（包括只改刻度类型时，轴上已有的边界换算不了）。

    Notes
    -----
    写了 ``limits`` 时，按这根轴应用后的刻度类型换算，并整体替换上一次的范围：写 None 的一端恢复自动，
    上一次的固定范围和单侧边界都不残留。只改刻度类型（线性 ↔ 对数）时，轴上已有的边界按新类型换算。
    所以刻度类型和范围分几个回调设、先设哪个，结果都一样。
    """
    fig.update_layout({axis: {}})           # 轴还没写进配置时（如单独测试回调的空图没有 yaxis2）先建出来，否则按名字读会报错
    current = cast(Any, fig.layout)[axis]
    was_log = current.type == 'log'         # 没设过类型（None）时 Plotly 自动判断，不会判成对数轴
    is_log = was_log if style.scale is None else style.scale == 'log'
    native = translate_axis_style(style, 'plotly', letter, log=is_log)
    if style.limits is not None:
        # 这次写了范围：两端都换成这次的（写 None 的一端恢复自动），上一次的固定范围、单侧边界都不残留；
        # 旧边界会被替换，也就不必换算（先 (-1, 30) 再 log + (1, 30) 曾因换算 -1 报错，1.0 发布前复审）
        native = {'range': None, 'autorange': True} | native
        native['autorangeoptions'] = {'minallowed': None, 'maxallowed': None} | native.get('autorangeoptions', {})
    elif is_log != was_log:
        # 只改刻度类型：轴上已写的边界按新类型换算
        _convert_bounds(current, _to_log if is_log else _from_log)
    fig.update_layout({axis: native})


def _convert_bounds(axis, convert) -> None:
    """轴上已写的边界（两侧的 range、单侧的 minallowed / maxallowed）逐个换算；没写的不动。"""
    if axis.range is not None:
        axis.range = [None if value is None else convert(value) for value in axis.range]
    options = axis.autorangeoptions
    for key in ('minallowed', 'maxallowed'):
        if options[key] is not None:
            options[key] = convert(options[key])


def _to_log(value: float) -> float:
    """数据值 → Plotly 对数轴的坐标（log10）；不大于 0 时报错。"""
    if value <= 0:
        raise ValueError("对数轴边界必须大于 0")
    return math.log10(value)


def _from_log(value: float) -> float:
    """Plotly 对数轴的坐标（log10）→ 数据值。"""
    return 10 ** value


# ══════════════════════════════════════════════
# 边框（FrameStyle）
# ══════════════════════════════════════════════
def apply_frame(fig, axis: str, frame: FrameStyle) -> None:
    """
    把 `FrameStyle` 用到一根轴上。只改写了的。

    Plotly 的上边框是 X 轴的镜像线，右边框是左 Y 轴的镜像线。左轴（``'yaxis'``）改 X、Y 两根轴的线宽和上、右两边；
    右轴只改自己的线宽和上边，右边就是右轴自己的轴线。有右轴时左 Y 轴不镜像，否则左轴着色的镜像线会叠在右轴上。
    """
    native = translate_frame(frame, 'plotly', figure_dpi(fig))
    left = axis == 'yaxis'
    if 'linewidth' in native:
        for name in (['xaxis', axis] if left else [axis]):
            fig.update_layout({name: dict(linewidth=native['linewidth'])})
    if 'top' in native:
        fig.update_layout(xaxis_mirror=native['top'])
    if 'right' in native and left:
        fig.update_layout(yaxis_mirror=native['right'] and not _has_right_axis(fig))


def _has_right_axis(fig) -> bool:
    """
    图里有没有叠加在左轴上的右轴。没有 ``yaxis2`` 的图上直接读 ``fig.layout.yaxis2`` 会抛 `AttributeError`，
    所以用 `getattr`。
    """
    right = getattr(fig.layout, 'yaxis2', None)
    return right is not None and right.overlaying is not None


# ══════════════════════════════════════════════
# 刻度（TickStyle）
# ══════════════════════════════════════════════
def apply_ticks(fig, axis: str, ticks: TickStyle) -> None:
    """
    把 `TickStyle` 用到一根轴上：磅按这张图的 dpi 换成像素。只改写了的。

    左轴（``'yaxis'``）连 X 轴一起改，右轴只改自己的 Y 轴。只写了朝向、没写 ``minor`` 时，
    不会把已经关掉的次刻度重新打开。
    """
    native = translate_ticks(ticks, 'plotly', figure_dpi(fig))
    for target in (['xaxis', axis] if axis == 'yaxis' else [axis]):
        settings = dict(native)
        # Plotly 的 minor.ticks 同时管次刻度的显示和朝向：只改朝向（没写 minor）时，不能把关掉的次刻度打开
        if ticks.minor is None and 'ticks' in settings.get('minor', {}) and not _minor_ticks_shown(fig, target):
            settings['minor'] = {k: v for k, v in settings['minor'].items() if k != 'ticks'}
        fig.update_layout({target: settings})


def apply_log_format(fig, axis: str) -> None:
    """
    对数轴写了刻度格式时，让次刻度文字的设置仍然生效。画完一张图、所有回调之后由后端调用。

    Parameters
    ----------
    fig : `plotly.graph_objects.Figure`
        图。
    axis : str
        layout 里的轴名，如 ``'xaxis'``、``'yaxis2'``。

    Raises
    ------
    ValueError
        对数轴写了格式，次刻度又要写小号数字（``minor_labels='short'``）。

    Notes
    -----
    Plotly 对数轴跨的数量级不多时，2、5 这些位置也是主刻度（matplotlib 里是次刻度），
    次刻度文字的设置 ``minorloglabels`` 只管它们写不写、怎么写；可一旦写了 ``tickformat``，
    Plotly 就把每个刻度都按格式写成完整数值，``minorloglabels`` 不再起作用。所以：

    - 次刻度不写文字（``'none'``，库默认）：主刻度只放在整数量级（``dtick=1``），2 ~ 9 交给不写文字的次刻度，
      与 matplotlib 一致。轴上已经写了 ``dtick`` 或 ``tickmode`` （比如用 ``custom`` 回调设了每两个量级一个刻度）
      时不改；
    - 次刻度写完整文字（``'full'``）：本来就是每个刻度都按格式写，不用改；
    - 次刻度写小号数字（``'short'``）：带格式的整数量级和小号数字 Plotly 画不到一起，报错。

    代价：放大到一个数量级以内时，``dtick=1`` 的轴上没有主刻度文字。
    """
    current = cast(Any, fig.layout)[axis]
    if current.type != 'log' or current.tickformat is None:
        return
    labels = _effective(fig, axis, lambda a: a.minorloglabels)
    if labels == MINOR_LABELS['short']:
        raise ValueError(f"Plotly 的对数轴 {axis} 写了刻度格式（tickformat）后，每个刻度都按格式写完整数值，"
                         f"做不到次刻度写小号数字（minor_labels='short'）；请去掉格式，或改用 'none' / 'full'")
    if labels == MINOR_LABELS['none'] and current.dtick is None and current.tickmode is None:
        current.dtick = 1


def _effective(fig, axis: str, read):
    """
    读一根轴的某个设置：轴上写了就用轴上的，没写看模板（模板只有 ``xaxis`` / ``yaxis`` 两套，
    ``yaxis2`` 用 ``yaxis`` 的）。*read* 从轴配置里取出这个设置。
    """
    # layout[轴名] 的类型标注过宽（Plotly 按名字动态取子对象），按 Any 读
    layout = cast(Any, fig.layout)
    value = read(layout[axis])
    if value is None:
        value = read(layout.template.layout['xaxis' if axis.startswith('x') else 'yaxis'])
    return value


def _minor_ticks_shown(fig, axis: str) -> bool:
    """这根轴现在显不显示次刻度（轴上没写就看模板）。"""
    return bool(_effective(fig, axis, lambda a: a.minor.ticks))
