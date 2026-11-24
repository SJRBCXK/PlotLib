"""
将坐标轴、边框和刻度样式应用到 Plotly Figure。

渲染后端和格式化回调共用这些函数。换算尺寸时读取图形 DPI，换算边界时使用应用样式后的轴类型。

双 Y 轴图共用 X 轴。左侧的边框和刻度设置可同时更新 X 轴与左 Y 轴，右侧仅更新右 Y 轴。
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
    将 `AxisStyle` 中显式指定的字段应用到 Plotly 坐标轴。

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
    指定 ``limits`` 时，按应用后的轴类型换算并替换原有边界，值为 ``None`` 的一侧自动计算。
    仅变更轴类型时，将现有边界换算为新轴类型的坐标。
    """
    fig.update_layout({axis: {}})           # 确保布局中存在该轴。
    current = cast(Any, fig.layout)[axis]
    was_log = current.type == 'log'
    is_log = was_log if style.scale is None else style.scale == 'log'
    native = translate_axis_style(style, 'plotly', letter, log=is_log)
    if style.limits is not None:
        # 清除旧边界后应用新值，避免转换即将被替换的边界。
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
    将 `FrameStyle` 中显式指定的字段应用到坐标轴。

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
    应用 `TickStyle` 中显式指定的刻度样式，按图形 DPI 将磅换算为像素。

    左轴（``'yaxis'``）连 X 轴一起改，右轴只改自己的 Y 轴。只写了朝向、没写 ``minor`` 时，
    不会把已经关掉的次刻度重新打开。
    """
    native = translate_ticks(ticks, 'plotly', figure_dpi(fig))
    for target in (['xaxis', axis] if axis == 'yaxis' else [axis]):
        settings = dict(native)
        # minor.ticks 同时控制朝向和可见性，更新朝向时保留显式隐藏状态。
        if ticks.minor is None and 'ticks' in settings.get('minor', {}) and not _minor_ticks_shown(fig, target):
            settings['minor'] = {k: v for k, v in settings['minor'].items() if k != 'ticks'}
        fig.update_layout({target: settings})


def apply_log_format(fig, axis: str) -> None:
    """
    处理对数轴显式格式与次刻度标签模式的组合。

    图形和轴回调全部执行后调用。

    Parameters
    ----------
    fig : `plotly.graph_objects.Figure`
        图。
    axis : str
        layout 里的轴名，如 ``'xaxis'``、``'yaxis2'``。

    Raises
    ------
    ValueError
        对数轴同时使用显式刻度格式和 ``minor_labels='short'``。

    Notes
    -----
    非空的 ``tickformat`` 优先于 Plotly 的 ``minorloglabels``。空字符串使用原生刻度格式。
    显式格式与 ``'none'`` 同时使用时，如果未指定 ``dtick`` 或 ``tickmode``，
    默认将主刻度放在 10 的整数次幂处。放大的区间如果不包含这些位置，可能没有主刻度标签。
    """
    current = cast(Any, fig.layout)[axis]
    if current.type != 'log' or not current.tickformat:
        return
    labels = _effective(fig, axis, lambda a: a.minorloglabels)
    if labels == MINOR_LABELS['short']:
        raise ValueError(f"Plotly 的对数轴 {axis} 写了刻度格式（tickformat）后，每个刻度都按格式写完整数值，"
                         f"做不到次刻度写小号数字（minor_labels='short'）；请去掉格式，或改用 'none' / 'full'")
    if labels == MINOR_LABELS['none'] and current.dtick is None and current.tickmode is None:
        current.dtick = 1


def _effective(fig, axis: str, read):
    """
    通过 *read* 读取显式轴设置，未设置时从图形模板取值。
    右侧 Y 轴继承模板的 ``yaxis`` 设置。
    """
    # layout[轴名] 的类型标注过宽（Plotly 按名字动态取子对象），按 Any 读
    layout = cast(Any, fig.layout)
    value = read(layout[axis])
    if value is None:
        value = read(layout.template.layout['xaxis' if axis.startswith('x') else 'yaxis'])
    return value


def _minor_ticks_shown(fig, axis: str) -> bool:
    """返回按轴设置和模板解析出的次刻度可见性。"""
    return bool(_effective(fig, axis, lambda a: a.minor.ticks))
