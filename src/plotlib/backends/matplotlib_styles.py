"""
将原生样式参数应用到 Matplotlib 坐标轴和图例。

渲染后端和格式化回调共用这些函数。

Notes
-----
轴类型变更会保留 ``tick_params`` 中的刻度尺寸、朝向和文字样式，但会重置定位器和格式器。
因此建轴时先调用 `apply_tick_params`，回调完成后再调用 ``apply_minor(only_defaults=True)``。
该调用通过 ``isDefault_minloc`` 和 ``isDefault_minfmt`` 识别仍使用默认设置的轴。
"""
import math

from matplotlib.ticker import (AutoMinorLocator, FuncFormatter, LogFormatterSciNotation, LogLocator,
                               NullFormatter, NullLocator, ScalarFormatter)


def is_twin(ax) -> bool:
    """判断是否为双 Y 轴图的右侧 Axes，其共用的 X 轴不可见。"""
    return not ax.xaxis.get_visible()


def apply_axis(ax, letter: str, native: dict) -> None:
    """
    将已转换的 `AxisStyle` 参数应用到指定方向的轴。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        坐标轴。
    letter : {'x', 'y'}
        改哪个方向。
    native : dict
        ``style.translate_axis_style(..., 'matplotlib')`` 的结果。

    Notes
    -----
    指定轴类型时，先更新刻度类型，再应用范围和格式。对数轴的主刻度位于 10 的整数次幂。
    范围中的 None 表示自动计算相应边界。两端均为 None 时，后续添加绘图对象也会触发自动缩放。
    """
    axis = ax.xaxis if letter == 'x' else ax.yaxis
    if 'scale' in native:
        (ax.set_xscale if letter == 'x' else ax.set_yscale)(native['scale'])
        if native['scale'] == 'log':
            axis.set_major_locator(LogLocator(base=10))
    if 'limits' in native:
        low, high = native['limits']
        if low is None or high is None:
            # 启用自动缩放，从数据重新计算未指定的边界。
            ax.autoscale(enable=True, axis=letter)
        if low is None and high is None:
            pass        # 保持自动缩放，以便后续绘图对象也参与范围计算。
        elif letter == 'x':
            ax.set_xlim(left=low, right=high)
        else:
            ax.set_ylim(bottom=low, top=high)
    if 'formatter' in native:
        axis.set_major_formatter(FuncFormatter(native['formatter']))
    if 'color' in native:
        color = native['color']
        axis.label.set_color(color)
        ax.tick_params(axis=letter, which='both', labelcolor=color, color=color)
        spine = 'bottom' if letter == 'x' else ('right' if is_twin(ax) else 'left')
        ax.spines[spine].set_color(color)


def apply_frame(ax, native: dict) -> None:
    """
    应用已转换的轴线宽度和上、右边框设置。

    双 Y 轴的右轴（twin）自己的右边就是右轴的轴线，总是画，只跟着上边的设置；
    它的左边、下边与左轴重合，不画，免得盖住左轴着色的轴线。
    """
    if 'linewidth' in native:
        for spine in ax.spines.values():
            spine.set_linewidth(native['linewidth'])
    if is_twin(ax):
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        if 'top' in native:
            ax.spines['top'].set_visible(native['top'])
        return
    if 'top' in native:
        ax.spines['top'].set_visible(native['top'])
    if 'right' in native:
        ax.spines['right'].set_visible(native['right'])


def legend_kwargs(native: dict) -> dict:
    """
    建图例时传给 ``ax.legend`` 的参数：去掉 ``draggable`` （建好后另设），图例标题用与正文相同的字号。
    """
    kwargs = {key: value for key, value in native.items() if key != 'draggable'}
    if 'fontsize' in kwargs:
        kwargs['title_fontsize'] = kwargs['fontsize']
    return kwargs


def apply_legend(legend, native: dict) -> None:
    """
    更新已有图例的位置、字号、边框和拖动设置。
    """
    if 'loc' in native:
        legend.set_loc(native['loc'])
        legend.set_bbox_to_anchor(native.get('bbox_to_anchor'))
        legend.borderaxespad = native.get('borderaxespad', legend.borderaxespad)
    if 'fontsize' in native:
        # Legend 没有 set_fontsize，字号要逐个设到图例文字上
        for text in [*legend.get_texts(), legend.get_title()]:
            text.set_fontsize(native['fontsize'])
    if 'frameon' in native:
        legend.set_frame_on(native['frameon'])
    if 'draggable' in native:
        legend.set_draggable(native['draggable'])


def visible_axes(ax) -> list:
    """
    一个 Axes 上看得见的 Axis。双 Y 轴右轴（``twinx``）的 X 轴是隐藏的，而且与左轴共用刻度定位器，不能改。
    """
    return [axis for axis in (ax.xaxis, ax.yaxis) if axis.get_visible()]


def apply_tick_params(ax, native: dict) -> None:
    """对可见轴分别设置主、次刻度的尺寸、朝向和标签样式。"""
    for axis in visible_axes(ax):
        if 'major' in native:
            axis.set_tick_params(which='major', **native['major'])
        if 'minor' in native:
            axis.set_tick_params(which='minor', **native['minor'])


def apply_minor(ax, native: dict, only_defaults: bool) -> None:
    """
    设置次刻度的定位器和标签格式器。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        坐标轴。
    native : dict
        ``style.translate_ticks(..., 'matplotlib')`` 的结果，用其中的 ``minor_visible`` 和 ``minor_labels``。
    only_defaults : bool
        为 ``True`` 时，只更新仍使用默认值的定位器或格式器。
        为 ``False`` 时，应用显式参数并清除相应的默认标记。

    Notes
    -----
    线性轴细分主刻度间隔，对数轴使用对数定位器。其他刻度类型优先使用自身的次刻度定位器。
    """
    for axis in visible_axes(ax):
        scale = axis.get_scale()
        log = scale == 'log'
        if 'minor_visible' in native and (axis.isDefault_minloc or not only_defaults):
            if not native['minor_visible']:
                axis.set_minor_locator(NullLocator())
            elif scale == 'linear':
                axis.set_minor_locator(AutoMinorLocator())
            elif log:
                axis.set_minor_locator(LogLocator(base=axis.get_transform().base, subs='auto'))
            else:
                axis.set_minor_locator(_scale_minor_locator(axis))
        if 'minor_labels' in native and (axis.isDefault_minfmt or not only_defaults):
            axis.set_minor_formatter(_minor_formatter(native['minor_labels'], log))


def _scale_minor_locator(axis):
    """
    获取当前刻度类型的默认次刻度定位器，并保留轴上已有的主刻度定位器及标签格式器。

    由刻度类型生成定位器，以保留底数、线性区宽度等参数。默认定位器为空时使用线性细分。
    """
    keep = (axis.get_major_locator(), axis.get_major_formatter(), axis.get_minor_formatter(),
            axis.isDefault_majloc, axis.isDefault_majfmt, axis.isDefault_minfmt)
    axis._scale.set_default_locators_and_formatters(axis)
    locator = axis.get_minor_locator()
    axis.set_major_locator(keep[0])
    axis.set_major_formatter(keep[1])
    axis.set_minor_formatter(keep[2])
    axis.isDefault_majloc, axis.isDefault_majfmt, axis.isDefault_minfmt = keep[3:]
    return AutoMinorLocator() if isinstance(locator, NullLocator) else locator


def _minor_formatter(minor_labels: str, log: bool):
    """
    按轴类型和标签模式创建次刻度格式器。

    ``'short'`` 在对数轴上显示首位数字，在线性轴上隐藏标签。``'full'`` 在两种轴上都显示完整数值。
    """
    if minor_labels == 'none' or (minor_labels == 'short' and not log):
        return NullFormatter()
    if minor_labels == 'short':
        return FuncFormatter(lambda value, _pos: f"{value / 10 ** math.floor(math.log10(value)):.0f}")
    if log:
        return LogFormatterSciNotation(labelOnlyBase=False, minor_thresholds=(math.inf, math.inf))
    return ScalarFormatter()
