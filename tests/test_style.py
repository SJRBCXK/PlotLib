"""
测试对象：src/plotlib/style.py —— 公共样式词汇与后端翻译（STRUCTURE_REVIEW 步骤 4.3）

约定：程序入口只接受一套标准写法（与后端无关），不认识就报错，也不替用户改写；
      翻译只发生在后端：translate_* 把标准写法换成 matplotlib / Plotly 的原生值。

标准写法：
  线型  'solid'、'dash'、'dot'、'dashdot'；
        或自定义虚线 (实线长, 空白长, ...)：正数、偶数个，单位是线宽的倍数
  标记  'circle'、'square'、'triangle-up'、'triangle-down'、'diamond'、'cross'、'x'
  颜色  CSS 颜色名（W3C 标准的 148 个，大小写都行，如 'red'、'lightblue'）；
        六位色号 '#rrggbb'（大小写都行）；或 RGB 三个 0~255 的整数（tuple / list）
        注意 CSS 标准里 'green' 是 #008000（深绿），纯绿 #00ff00 叫 'lime'。
        matplotlib 的 CSS4_COLORS 与 Plotly 的颜色名是同一套 148 个，颜色名两个后端都直接认。

check_* 只校验：合法时什么都不返回，不合法时类型错报 TypeError、值错报 ValueError。
"""
from typing import Any

import pytest

from plotlib.style import (check_color, check_linestyle, check_marker,
                           translate_color, translate_linestyle, translate_marker)


# ══════════════════════════════════════════════
# 校验：合法写法不报错
# ══════════════════════════════════════════════
@pytest.mark.parametrize("value", ['solid', 'dash', 'dot', 'dashdot', (3, 5), [3, 5], (2, 1.5, 0.5, 1.5)],
                         ids=['solid', 'dash', 'dot', 'dashdot', 'tuple', 'list', 'four_segments'])
def test_check_linestyle_accepts_standard(value):
    check_linestyle(value)


@pytest.mark.parametrize("value", ['circle', 'square', 'triangle-up', 'triangle-down', 'diamond', 'cross', 'x'])
def test_check_marker_accepts_standard(value):
    check_marker(value)


@pytest.mark.parametrize("value", ['red', 'Red', 'lightblue', 'grey',
                                   '#ff0000', '#FF0000', (255, 0, 0), [0, 128, 255]],
                         ids=['name', 'name_capital', 'name_long', 'name_grey',
                              'hex', 'hex_upper', 'rgb_tuple', 'rgb_list'])
def test_check_color_accepts_standard(value):
    check_color(value)


# ══════════════════════════════════════════════
# 校验：非标准写法报错（包括各后端自己的写法，如 '--'、'o'）
# ══════════════════════════════════════════════
@pytest.mark.parametrize("value, error", [
    ('--',          ValueError),    # matplotlib 的写法，不是标准写法
    ('dashed',      ValueError),    # matplotlib 的单词，标准词是 'dash'
    (5,             TypeError),
    (None,          TypeError),
    ((3,),          ValueError),    # 段数必须是偶数（实线、空白成对）
    ((),            ValueError),
    ((3, -5),       ValueError),    # 段长必须为正
    ((3, 0),        ValueError),
    ((0, (3, 5)),   TypeError),     # matplotlib 原生写法：元素必须是数字，改写成 (3, 5)
    (('3', '5'),    TypeError),
], ids=['mpl_symbol', 'mpl_word', 'int', 'None', 'odd', 'empty', 'negative', 'zero',
        'mpl_tuple', 'str_elements'])
def test_check_linestyle_rejects(value, error):
    with pytest.raises(error):
        check_linestyle(value)


def test_check_linestyle_message_lists_words():
    """报错信息列出可用的标准词，用户不用去翻文档。"""
    with pytest.raises(ValueError, match="solid.*dash.*dot.*dashdot"):
        check_linestyle('--')


@pytest.mark.parametrize("value, error", [
    ('o',  ValueError),     # matplotlib 的写法
    ('p',  ValueError),     # 不在词汇表里
    (1,    TypeError),
    (None, TypeError),
], ids=['mpl_symbol', 'unknown', 'int', 'None'])
def test_check_marker_rejects(value, error):
    with pytest.raises(error):
        check_marker(value)


def test_check_marker_message_lists_words():
    with pytest.raises(ValueError, match="circle"):
        check_marker('o')


@pytest.mark.parametrize("value, error", [
    ('tab:red',     ValueError),    # matplotlib 特有的写法
    ('r',           ValueError),    # matplotlib 的单字母
    ('C0',          ValueError),    # matplotlib 的色环编号
    ('reddish',     ValueError),    # 不在 CSS 颜色名里
    ('#f00',        ValueError),    # 只收六位色号
    ('ff0000',      ValueError),    # 缺 '#'
    ('#gg0000',     ValueError),    # 不是十六进制
    ((256, 0, 0),   ValueError),    # 超出 0~255
    ((-1, 0, 0),    ValueError),
    ((255, 0),      ValueError),    # 必须正好三个
    ((1.0, 0, 0),   TypeError),     # matplotlib 的 0~1 写法：元素必须是整数
    (5,             TypeError),
    (None,          TypeError),
], ids=['mpl_tab', 'mpl_letter', 'mpl_cycle', 'unknown_name', 'short_hex', 'no_hash', 'not_hex',
        'over_255', 'negative', 'two_values', 'float', 'int', 'None'])
def test_check_color_rejects(value, error):
    with pytest.raises(error):
        check_color(value)


# ══════════════════════════════════════════════
# 翻译：标准写法 → 各后端原生值
# ══════════════════════════════════════════════
@pytest.mark.parametrize("value, matplotlib, plotly", [
    ('solid',   '-',  'solid'),
    ('dash',    '--', 'dash'),
    ('dot',     ':',  'dot'),
    ('dashdot', '-.', 'dashdot'),
])
def test_translate_linestyle_words(value, matplotlib, plotly):
    assert translate_linestyle(value, 'matplotlib') == matplotlib
    assert translate_linestyle(value, 'plotly') == plotly


def test_translate_custom_dash():
    """
    自定义虚线的段长是线宽的倍数：
    matplotlib 补上偏移量 0（它按线宽自动缩放）；Plotly 要像素，段长 × 线宽。
    """
    assert translate_linestyle((3, 5), 'matplotlib') == (0, (3, 5))
    assert translate_linestyle([3, 5], 'matplotlib') == (0, (3, 5))
    assert translate_linestyle((3, 5), 'plotly', linewidth=3) == '9px,15px'
    assert translate_linestyle((1.5, 2), 'plotly', linewidth=2) == '3px,4px'


@pytest.mark.parametrize("value, matplotlib, plotly", [
    ('circle',        'o', 'circle'),
    ('square',        's', 'square'),
    ('triangle-up',   '^', 'triangle-up'),
    ('triangle-down', 'v', 'triangle-down'),
    ('diamond',       'D', 'diamond'),
    ('cross',         '+', 'cross'),
    ('x',             'x', 'x'),
])
def test_translate_marker(value, matplotlib, plotly):
    assert translate_marker(value, 'matplotlib') == matplotlib
    assert translate_marker(value, 'plotly') == plotly


@pytest.mark.parametrize("value, matplotlib, plotly", [
    ('red',        'red',              'red'),             # 颜色名、色号两个后端都认，原样使用
    ('Red',        'Red',              'Red'),
    ('#ff0000',    '#ff0000',          '#ff0000'),
    ('#FF0000',    '#FF0000',          '#FF0000'),
    ((255, 0, 0),  (1.0, 0.0, 0.0),    'rgb(255,0,0)'),    # matplotlib 要 0~1
    ([0, 51, 255], (0.0, 0.2, 1.0),    'rgb(0,51,255)'),
], ids=['name', 'name_capital', 'hex', 'hex_upper', 'rgb_tuple', 'rgb_list'])
def test_translate_color(value, matplotlib, plotly):
    result = translate_color(value, 'matplotlib')
    if isinstance(matplotlib, tuple):
        assert result == pytest.approx(matplotlib)     # 浮点数：近似相等
    else:
        assert result == matplotlib
    assert translate_color(value, 'plotly') == plotly


@pytest.mark.parametrize("translate, value", [
    (translate_linestyle, '--'),
    (translate_marker,    'o'),
    (translate_color,     'tab:red'),
], ids=['linestyle', 'marker', 'color'])
def test_translate_rejects_non_standard(translate, value):
    """翻译前先校验：后端写法不能绕过标准写法直接传进来（formatter 工厂也走这条路）。"""
    with pytest.raises(ValueError):
        translate(value, 'matplotlib')


@pytest.mark.parametrize("translate, value", [
    (translate_linestyle, 'dash'),
    (translate_marker,    'circle'),
    (translate_color,     '#ff0000'),
], ids=['linestyle', 'marker', 'color'])
def test_translate_unknown_backend_raises(translate, value):
    with pytest.raises(ValueError, match="backend"):
        translate(value, 'svg')


# ──────────────────────────────────────────────
# 排版与尺寸的翻译（STRUCTURE_REVIEW 6.7）：通用的翻译放在这一层，后端只管应用
# ──────────────────────────────────────────────
def test_translate_tick_format():
    """刻度格式（与 make_axes_formatter 同一写法）：matplotlib 得到格式函数，Plotly 得到 d3 格式。"""
    from plotlib.style import translate_tick_format

    assert translate_tick_format('{x:.2f}', 'matplotlib')(1.234, 0) == '1.23'
    assert translate_tick_format('{y:.4f}', 'matplotlib')(1.234, 0) == '1.2340'
    assert translate_tick_format('{y:.4f}', 'plotly') == '.4f'
    assert translate_tick_format('{x:.1e}', 'plotly') == '.1e'
    with pytest.raises(ValueError, match='Plotly 暂不支持此刻度格式'):
        translate_tick_format('{x:,.2f}', 'plotly')


@pytest.mark.parametrize("position, matplotlib, plotly", [
    ('outside right', {'loc': 'center left', 'bbox_to_anchor': (1, 0.5)},
                      {'x': 1.02, 'y': 0.5, 'xanchor': 'left', 'yanchor': 'middle'}),
    ('lower right',   {'loc': 'lower right'},
                      {'x': 0.98, 'y': 0.02, 'xanchor': 'right', 'yanchor': 'bottom'}),
    # 图外上方、右边与绘图区对齐（双 Y 轴，2026-11-20 参照 Origin 图）
    ('outside top right', {'loc': 'lower right', 'bbox_to_anchor': (1, 1.02), 'borderaxespad': 0},
                          {'x': 1, 'y': 1.02, 'xanchor': 'right', 'yanchor': 'bottom'}),
])
def test_translate_legend(position, matplotlib, plotly):
    """图例位置（排版预设的写法）→ matplotlib 的 legend 参数 / Plotly 的 layout.legend。"""
    from plotlib.style import translate_legend

    assert translate_legend(position, 'matplotlib') == matplotlib
    assert translate_legend(position, 'plotly') == plotly
    with pytest.raises(ValueError):
        translate_legend('upper middle', 'plotly')


def test_translate_points_and_figsize():
    """
    以磅为单位的量（字号、线宽）、以英寸为单位的 figsize 按显式的 dpi 换成后端单位：
    matplotlib 本来就用磅和英寸，原样返回；Plotly 用像素：磅 × dpi / 72、英寸 × dpi。
    """
    from plotlib.style import translate_figsize, translate_points

    assert translate_points(22, 100, 'matplotlib') == 22
    assert translate_points(72, 100, 'plotly') == pytest.approx(100)
    assert translate_points(22, 200, 'plotly') == pytest.approx(22 * 200 / 72)
    assert translate_figsize((10, 8), 100, 'matplotlib') == (10, 8)
    assert translate_figsize((10, 8), 100, 'plotly') == (1000, 800)
    assert translate_figsize((6, 4), 150, 'plotly') == (900, 600)


# ══════════════════════════════════════════════
# 刻度 TickStyle（2026-11-20 用户提出：主 / 次刻度的长短、显示、文字都能精调）
#   标准写法：长度、宽度、字号、间距用磅；None 表示不改（沿用上一层）。翻译后只出现写了的字段
# ══════════════════════════════════════════════
PX = 100 / 72       # dpi 100 时 1 磅的像素数


def test_tick_style_defaults():
    """全局默认（DEFAULT_TICKS）：朝外、主刻度 6 × 3 磅、显示次刻度 3 × 3 磅、次刻度不写文字；文字字体字号沿用外观。"""
    from plotlib.plot_spec import DEFAULT_TICKS, Appearance, TickStyle

    assert DEFAULT_TICKS == TickStyle(direction='out', length=6, width=3, minor=True,
                                      minor_length=3, minor_width=3, minor_labels='none')
    # Appearance 存的是用户写的那一层（样式对象化起），库默认由后端叠加
    assert Appearance().ticks == TickStyle()
    assert TickStyle().length is None                   # 单独创建时全是 None：只写要改的


# ══════════════════════════════════════════════
# 样式对象化（2026-11-20）：LineStyle / AxisStyle / FrameStyle / LegendStyle 与 TickStyle 同一套做法
# ══════════════════════════════════════════════
def test_style_defaults_and_layers():
    """
    库默认：线宽 3 实线、标记 6 磅；默认无框（用户定）、轴线宽 3；图例字号 10、无边框、不能拖动。
    Appearance 只存用户写的那一层（全是 None），叠加时没写的字段沿用下一层。
    """
    from plotlib.plot_spec import (DEFAULT_FRAME, DEFAULT_LEGEND, DEFAULT_LINES, Appearance, FrameStyle,
                                   LegendStyle, LineStyle)

    assert DEFAULT_LINES == LineStyle(width=3, linestyle='solid', marker_size=6)
    assert DEFAULT_FRAME == FrameStyle(width=3, top=False, right=False)
    assert (DEFAULT_LEGEND.font_size, DEFAULT_LEGEND.frame, DEFAULT_LEGEND.draggable) == (10, False, False)
    appearance = Appearance()
    assert (appearance.lines, appearance.frame, appearance.legend) == (LineStyle(), FrameStyle(), LegendStyle())
    assert DEFAULT_FRAME.updated(FrameStyle(top=True)) == FrameStyle(width=3, top=True, right=False)


def test_layers_order_preset_below_global():
    """
    叠加顺序（layouts.resolve_*）：库默认 < 版式预设 < DataPlotter 全局。
    多线图预设的图例在图外右侧、可拖动；全局写了 position 就盖过预设，没写的（拖动）仍用预设，字号用库默认。
    双 Y 轴预设画完整的框；全局写了 top=False 就盖过它。
    """
    from plotlib.layouts import LAYOUTS, resolve_frame, resolve_legend
    from plotlib.plot_spec import Appearance, FrameStyle, LegendStyle

    legend = resolve_legend(LAYOUTS['multiline'], Appearance(legend=LegendStyle(position='upper left')))
    assert (legend.position, legend.draggable, legend.font_size) == ('upper left', True, 10)
    assert resolve_legend(LAYOUTS['multiline'], Appearance()).position == 'outside right'

    assert resolve_frame(LAYOUTS['dual_y'], Appearance()) == FrameStyle(width=3, top=True, right=True)
    assert resolve_frame(LAYOUTS['multiline'], Appearance()) == FrameStyle(width=3, top=False, right=False)
    assert resolve_frame(LAYOUTS['dual_y'], Appearance(frame=FrameStyle(top=False))).top is False


def test_translate_line_style():
    """
    LineStyle → matplotlib 的 Line2D 属性 / Plotly 的扁平写法（磅 → 像素，点跟着线色）；只出现写了的字段。
    自定义虚线：Plotly 按写了的线宽换算，没写时用 dash_width（全局线宽的像素值）。
    """
    from plotlib.plot_spec import LineStyle
    from plotlib.style import translate_line_style

    style = LineStyle(width=2, color='red', linestyle='dash', marker='circle', marker_size=6)
    assert translate_line_style(style, 'matplotlib') == {
        'linewidth': 2, 'color': 'red', 'linestyle': '--', 'marker': 'o', 'markersize': 6}
    native = translate_line_style(style, 'plotly', dpi=100)
    assert (native['line_color'], native['marker_color'], native['line_dash'], native['marker_symbol']) == \
        ('red', 'red', 'dash', 'circle')
    assert (native['line_width'], native['marker_size']) == pytest.approx((2 * PX, 6 * PX))
    assert translate_line_style(LineStyle(), 'plotly', dpi=100) == {}
    assert translate_line_style(LineStyle(linestyle=(3, 5)), 'plotly', dpi=100, dash_width=2)['line_dash'] == '6px,10px'
    with pytest.raises(ValueError):
        translate_line_style(LineStyle(marker='o'), 'matplotlib')          # 后端写法


def test_translate_axis_style():
    """
    AxisStyle → matplotlib（刻度类型、范围、格式函数、着色）/ Plotly 轴配置；Plotly 做不到的（scaler、symlog）报错。
    """
    from plotlib.plot_spec import AxisStyle
    from plotlib.style import translate_axis_style

    mpl = translate_axis_style(AxisStyle(scale='log', limits=(1, None), format='{x:.1f}', scaler=10, color='red'),
                               'matplotlib', 'x')
    assert (mpl['scale'], mpl['limits'], mpl['color']) == ('log', (1, None), 'red')
    assert mpl['formatter'](2.0, 0) == '20.0'                              # 显示值 = 刻度值 × scaler
    assert translate_axis_style(AxisStyle(scaler=1000), 'matplotlib', 'y')['formatter'](0.002, 0) == '2'
    assert translate_axis_style(AxisStyle(), 'matplotlib', 'x') == {}

    ply = translate_axis_style(AxisStyle(scale='log', limits=(1, 1000), format='{y:.2f}', color='blue'), 'plotly', 'y')
    assert (ply['type'], ply['tickformat'], ply['range'], ply['autorange']) == ('log', '.2f', [0.0, 3.0], False)
    assert ply['linecolor'] == ply['tickcolor'] == 'blue'
    for bad in (AxisStyle(scaler=10), AxisStyle(scale='symlog')):
        with pytest.raises(ValueError, match='Plotly'):
            translate_axis_style(bad, 'plotly', 'x')
    with pytest.raises(ValueError, match='大于 0'):
        translate_axis_style(AxisStyle(scale='log', limits=(0, 10)), 'matplotlib', 'x')


def test_translate_frame_and_legend_style():
    """FrameStyle → 线宽与上 / 右边开关（Plotly 线宽按 dpi 换算）；LegendStyle → 两个后端的图例参数（位置同一张表）。"""
    from plotlib.plot_spec import FrameStyle, LegendStyle
    from plotlib.style import LEGEND_POSITIONS, translate_frame, translate_legend_style

    assert translate_frame(FrameStyle(width=2, top=True), 'matplotlib') == {'linewidth': 2, 'top': True}
    assert translate_frame(FrameStyle(width=2), 'plotly', dpi=100)['linewidth'] == pytest.approx(2 * PX)

    legend = LegendStyle(position='upper left', font_size=12, frame=True, draggable=True)
    assert translate_legend_style(legend, 'matplotlib') == {
        'loc': 'upper left', 'fontsize': 12, 'frameon': True, 'draggable': True}
    ply = translate_legend_style(legend, 'plotly', dpi=100)
    assert (ply['x'], ply['xanchor'], ply['borderwidth'], ply['bgcolor']) == (0.02, 'left', 1, 'white')
    assert ply['font']['size'] == pytest.approx(12 * PX) and 'draggable' not in ply
    # 排版预设、全局、图例工厂共用一张位置表：图内 9 个 + 'best' + 图外 2 个
    assert {'upper left', 'lower right', 'outside right', 'outside top right', 'best'} <= set(LEGEND_POSITIONS)
    with pytest.raises(ValueError, match='图例位置'):
        translate_legend_style(LegendStyle(position='middle'), 'matplotlib')


def test_tick_style_updated():
    """在一层设置上叠加另一层：后者写了的字段覆盖，没写（None）的沿用前者。"""
    from plotlib.plot_spec import DEFAULT_TICKS, TickStyle

    merged = DEFAULT_TICKS.updated(TickStyle(length=10, minor=False))
    assert (merged.length, merged.minor, merged.width, merged.direction) == (10, False, 3, 'out')
    assert DEFAULT_TICKS.updated(None) == DEFAULT_TICKS


def test_translate_ticks_matplotlib():
    """
    → matplotlib：主 / 次刻度各一组 tick_params 参数，外加次刻度开关、次刻度文字的写法。
    次刻度文字没单独写字号、字体、间距时，跟主刻度文字一样。
    """
    from plotlib.plot_spec import TickStyle
    from plotlib.style import translate_ticks

    native = translate_ticks(TickStyle(direction='in', length=8, width=2, minor=False, minor_length=4,
                                       label_font='Times New Roman', label_size=14, label_pad=5,
                                       minor_labels='short'), 'matplotlib', dpi=100)
    assert native == {
        'major': {'direction': 'in', 'length': 8, 'width': 2, 'labelfontfamily': 'Times New Roman',
                  'labelsize': 14, 'pad': 5},
        'minor': {'direction': 'in', 'length': 4, 'labelfontfamily': 'Times New Roman', 'labelsize': 14, 'pad': 5},
        'minor_visible': False,
        'minor_labels': 'short',
    }
    assert translate_ticks(TickStyle(minor_label_size=9), 'matplotlib', dpi=100) == {'minor': {'labelsize': 9}}
    assert translate_ticks(TickStyle(), 'matplotlib', dpi=100) == {}


def test_translate_ticks_plotly():
    """
    → Plotly 轴配置：磅按 dpi 换成像素；朝向 out / in → 'outside' / 'inside'；
    次刻度关掉 → minor.ticks 为空；次刻度文字 none / short / full → minorloglabels 'none' / 'small digits' / 'complete'。
    """
    from plotlib.plot_spec import TickStyle
    from plotlib.style import translate_ticks

    native = translate_ticks(TickStyle(direction='out', length=6, width=3, minor=True, minor_length=3,
                                       minor_width=2, label_font='Arial', label_size=14, label_pad=5,
                                       minor_labels='short'), 'plotly', dpi=100)
    # pytest.approx 不支持嵌套字典：数值逐项比
    assert set(native) == {'ticks', 'ticklen', 'tickwidth', 'minor', 'tickfont', 'ticklabelstandoff', 'minorloglabels'}
    assert (native['ticks'], native['minorloglabels']) == ('outside', 'small digits')
    assert (native['ticklen'], native['tickwidth'], native['ticklabelstandoff']) == pytest.approx((6 * PX, 3 * PX, 5 * PX))
    assert native['minor']['ticks'] == 'outside'
    assert (native['minor']['ticklen'], native['minor']['tickwidth']) == pytest.approx((3 * PX, 2 * PX))
    assert native['tickfont']['family'] == 'Arial' and native['tickfont']['size'] == pytest.approx(14 * PX)
    assert translate_ticks(TickStyle(minor=False), 'plotly', dpi=100) == {'minor': {'ticks': ''}}
    assert translate_ticks(TickStyle(direction='in'), 'plotly', dpi=100) == {'ticks': 'inside', 'minor': {'ticks': 'inside'}}
    assert translate_ticks(TickStyle(minor_labels='full'), 'plotly', dpi=100) == {'minorloglabels': 'complete'}
    assert translate_ticks(TickStyle(length=6), 'plotly', dpi=200)['ticklen'] == pytest.approx(6 * 200 / 72)


@pytest.mark.parametrize("field", ['minor_label_font', 'minor_label_size', 'minor_label_pad'])
def test_translate_ticks_plotly_rejects_minor_label_style(field):
    """Plotly 的次刻度没有文字属性：单独设次刻度文字的字体 / 字号 / 间距 → 报错说明（用户定：不悄悄忽略）。"""
    from plotlib.plot_spec import TickStyle
    from plotlib.style import translate_ticks

    ticks: Any = TickStyle(**{field: 'Arial' if field == 'minor_label_font' else 9})   # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match='Plotly'):
        translate_ticks(ticks, 'plotly', dpi=100)
    translate_ticks(ticks, 'matplotlib', dpi=100)    # matplotlib 可以


@pytest.mark.parametrize("kwargs, error", [
    (dict(direction='inout'), ValueError),      # Plotly 没有跨在轴线两侧的刻度，标准写法只有 out / in
    (dict(minor_labels='all'), ValueError),
    (dict(length=-1), ValueError),
    (dict(minor_width=0), ValueError),
    (dict(minor='yes'), TypeError),
])
def test_translate_ticks_rejects_bad_values(kwargs, error):
    """非标准写法、非正数长度 → 翻译时报错（两个后端一样）。"""
    from plotlib.plot_spec import TickStyle
    from plotlib.style import translate_ticks

    for backend in ('matplotlib', 'plotly'):
        with pytest.raises(error):
            translate_ticks(TickStyle(**kwargs), backend, dpi=100)
