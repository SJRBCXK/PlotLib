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
