"""
matplotlib 的样式应用（2026-11-20）：把翻译层 style.translate_*(..., 'matplotlib') 的结果用到坐标轴、图例上。
后端（预设与全局）和 formatters 的工厂（单轴覆盖）共用，所以单独成一个文件；只导入 matplotlib.ticker，不导入 pyplot。

轴（AxisStyle）：apply_axis；边框（FrameStyle）：apply_frame；图例（LegendStyle）：apply_legend（改已有的图例）。

刻度（TickStyle）：matplotlib 的刻度分两类，存放的地方不同：
  - 线的长短粗细、朝向、文字字体字号间距：tick_params，存在 Axis 上，改刻度类型（set_xscale）后仍然保留；
  - 次刻度显不显示（定位器）、次刻度写什么（格式器）：改刻度类型时会被重置成新类型的默认值，
    matplotlib 用 isDefault_minloc / isDefault_minfmt 标记「还是默认值、没被人改过」。
所以全局设置分两步：建轴时 apply_tick_params；用户回调之后 apply_minor(only_defaults=True) 只补还是默认值的，
不会覆盖单轴 formatter 里的设置（那里 only_defaults=False，设了就标记成非默认）。
"""
import math

from matplotlib.ticker import (AutoMinorLocator, FuncFormatter, LogFormatterSciNotation, LogLocator,
                               NullFormatter, NullLocator, ScalarFormatter)


def is_twin(ax) -> bool:
    """双 Y 轴的右轴（twinx 建的）：它的 X 轴是隐藏的，和左轴共用。"""
    return not ax.xaxis.get_visible()


def apply_axis(ax, letter: str, native: dict) -> None:
    """
    一个方向的轴（AxisStyle 翻译后）：刻度类型、范围、刻度格式、着色。只改写了的。
    刻度类型没写就不调用 set_*scale——调用会把已有的刻度格式（如排版预设的两位小数）重置成默认
    （样式对象化以前轴工厂总是调用，曾把预设格式冲掉）。
    """
    axis = ax.xaxis if letter == 'x' else ax.yaxis
    if 'scale' in native:
        (ax.set_xscale if letter == 'x' else ax.set_yscale)(native['scale'])
        if native['scale'] == 'log':
            axis.set_major_locator(LogLocator(base=10))
    if 'limits' in native:
        low, high = native['limits']
        if letter == 'x':
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
    边框（FrameStyle 翻译后）：轴线宽、上 / 右边画不画。双 Y 轴的右轴（twin）自己的右边是右轴的轴线，总是画，
    只跟着上边设置；它的左边、下边与左轴重合，不画（免得盖住左轴着色的轴线）。
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
    """建图例时传给 ax.legend 的参数（图例标题同字号）；拖动建好后另设。"""
    kwargs = {key: value for key, value in native.items() if key != 'draggable'}
    if 'fontsize' in kwargs:
        kwargs['title_fontsize'] = kwargs['fontsize']
    return kwargs


def apply_legend(legend, native: dict) -> None:
    """改已有的图例（LegendStyle 翻译后，图例回调用）：位置、字号（含标题）、边框、拖动。只改写了的。"""
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
    """一个 Axes 上看得见的 Axis。双 Y 轴的右轴（twinx）的 X 轴是隐藏的，而且与左轴共用刻度定位器，不能碰。"""
    return [axis for axis in (ax.xaxis, ax.yaxis) if axis.get_visible()]


def apply_tick_params(ax, native: dict) -> None:
    """线的长短粗细、朝向、文字（主 / 次刻度各一组 tick_params）。"""
    for axis in visible_axes(ax):
        if 'major' in native:
            axis.set_tick_params(which='major', **native['major'])
        if 'minor' in native:
            axis.set_tick_params(which='minor', **native['minor'])


def apply_minor(ax, native: dict, only_defaults: bool) -> None:
    """
    次刻度显不显示、写什么。only_defaults=True 时只改还是默认值的（全局设置，在用户回调之后补）；
    False 时照改（单轴 formatter）。
    """
    for axis in visible_axes(ax):
        log = axis.get_scale() == 'log'
        if 'minor_visible' in native and (axis.isDefault_minloc or not only_defaults):
            if not native['minor_visible']:
                axis.set_minor_locator(NullLocator())
            elif not log:
                axis.set_minor_locator(AutoMinorLocator())
            # 对数轴要显示次刻度时保留对数轴默认的次刻度定位器（2 ~ 9 倍处）
        if 'minor_labels' in native and (axis.isDefault_minfmt or not only_defaults):
            axis.set_minor_formatter(_minor_formatter(native['minor_labels'], log))


def _minor_formatter(minor_labels: str, log: bool):
    """
    次刻度写什么 → 格式器。'short'（2、5 这样的首位数字）只在对数轴上有意义，线性轴上不写——与 Plotly 一致
    （曾让线性轴的 'short' 等同 'full'，实际画出来每个次刻度都标数，挤成一片，改掉）。'full' 线性轴也写（只有 matplotlib 能做）。
    """
    if minor_labels == 'none' or (minor_labels == 'short' and not log):
        return NullFormatter()
    if minor_labels == 'short':
        return FuncFormatter(lambda value, _pos: f"{value / 10 ** math.floor(math.log10(value)):.0f}")
    if log:
        # labelOnlyBase=False 且阈值无穷大：不管跨几个数量级，每个次刻度都写完整数值
        return LogFormatterSciNotation(labelOnlyBase=False, minor_thresholds=(math.inf, math.inf))
    return ScalarFormatter()
