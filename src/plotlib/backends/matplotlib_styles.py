"""
matplotlib 的样式应用：把翻译层 ``style.translate_*(..., 'matplotlib')`` 的结果用到坐标轴和图例上。

后端（版式预设与全局设置）和 `plotlib.formatters` （单轴覆盖）共用这些函数，所以单独成一个模块；
只导入 ``matplotlib.ticker``，不导入 pyplot。

- 轴（`AxisStyle`）：`apply_axis`；
- 边框（`FrameStyle`）：`apply_frame`；
- 图例（`LegendStyle`）：`legend_kwargs` （建图例时）、`apply_legend` （改已有的图例）；
- 刻度（`TickStyle`）：`apply_tick_params`、`apply_minor`。

Notes
-----
matplotlib 的刻度设置存放在两个地方，行为不同：

- 线的长短粗细、朝向，文字的字体、字号、间距存在 ``Axis`` 的 ``tick_params`` 里，改刻度类型
  （``set_xscale``）后仍然保留；
- 次刻度显不显示（定位器）、次刻度写什么（格式器）在改刻度类型时会被重置成新类型的默认值，
  matplotlib 用 ``isDefault_minloc`` / ``isDefault_minfmt`` 标记「还是默认值、没被改过」。

所以全局刻度设置分两步：建轴时 `apply_tick_params`；用户回调之后再 ``apply_minor(only_defaults=True)``，
只补还是默认值的那些，不会覆盖单轴 formatter 里的设置（单轴用 ``only_defaults=False``，设过就不再是默认值）。
"""
import math

from matplotlib.ticker import (AutoMinorLocator, FuncFormatter, LogFormatterSciNotation, LogLocator,
                               NullFormatter, NullLocator, ScalarFormatter)


def is_twin(ax) -> bool:
    """是否为双 Y 轴的右轴（``twinx`` 建的）：它的 X 轴是隐藏的，与左轴共用。"""
    return not ax.xaxis.get_visible()


def apply_axis(ax, letter: str, native: dict) -> None:
    """
    把翻译好的 `AxisStyle` 用到一个方向的轴上：刻度类型、范围、刻度格式、着色。只改写了的。

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
    没写刻度类型时不调用 ``set_xscale`` / ``set_yscale``：调用会把已有的刻度格式
    （如版式预设的两位小数）重置成默认。改成对数轴时主刻度只放在 10 的整数次幂上。
    着色时轴标题、刻度、刻度文字和这一侧的轴线（双 Y 轴右轴是右边）用同一颜色。
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
    把翻译好的 `FrameStyle` 用到坐标轴上：轴线宽，上边、右边画不画。

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
    把翻译好的 `LegendStyle` 用到已有的图例上（图例回调用）：位置、字号（含标题）、边框、拖动。只改写了的。
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
    """把翻译好的 `TickStyle` 里线的长短粗细、朝向和文字设置用到看得见的轴上（主、次刻度各一组 ``tick_params``）。"""
    for axis in visible_axes(ax):
        if 'major' in native:
            axis.set_tick_params(which='major', **native['major'])
        if 'minor' in native:
            axis.set_tick_params(which='minor', **native['minor'])


def apply_minor(ax, native: dict, only_defaults: bool) -> None:
    """
    设置次刻度显不显示、写什么。

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        坐标轴。
    native : dict
        ``style.translate_ticks(..., 'matplotlib')`` 的结果，用其中的 ``minor_visible`` 和 ``minor_labels``。
    only_defaults : bool
        True：只改还是默认值的定位器和格式器（全局设置，在用户回调之后补）；
        False：照改（单轴 formatter），改过之后就不再算默认值。

    Notes
    -----
    对数轴显示次刻度时在 2 ~ 9 倍处，线性轴自动细分。对数轴也显式装上定位器，
    否则它仍算默认值，单轴写的 ``minor=True`` 会被全局的 ``minor=False`` 关掉。
    """
    for axis in visible_axes(ax):
        log = axis.get_scale() == 'log'
        if 'minor_visible' in native and (axis.isDefault_minloc or not only_defaults):
            if not native['minor_visible']:
                axis.set_minor_locator(NullLocator())
            elif not log:
                axis.set_minor_locator(AutoMinorLocator())
            else:
                # 对数轴：显式装上对数次刻度（2 ~ 9 倍处，与对数轴默认的一样）。只「保留默认的」不行——它仍算默认值，
                # 后端在回调之后补全局设置时会把单轴写的 minor=True 关掉（1.0 发布前复审）
                axis.set_minor_locator(LogLocator(base=axis.get_transform().base, subs='auto'))
        if 'minor_labels' in native and (axis.isDefault_minfmt or not only_defaults):
            axis.set_minor_formatter(_minor_formatter(native['minor_labels'], log))


def _minor_formatter(minor_labels: str, log: bool):
    """
    把次刻度文字的写法换成格式器。

    ``'short'`` （只写 2、5 这样的首位数字）只在对数轴上有意义，线性轴上不写，与 Plotly 一致；
    线性轴每个次刻度都标数会挤成一片。``'full'`` 在线性轴上也写完整数值（只有 matplotlib 能做）。
    """
    if minor_labels == 'none' or (minor_labels == 'short' and not log):
        return NullFormatter()
    if minor_labels == 'short':
        return FuncFormatter(lambda value, _pos: f"{value / 10 ** math.floor(math.log10(value)):.0f}")
    if log:
        # labelOnlyBase=False 且阈值无穷大：不管跨几个数量级，每个次刻度都写完整数值
        return LogFormatterSciNotation(labelOnlyBase=False, minor_thresholds=(math.inf, math.inf))
    return ScalarFormatter()
