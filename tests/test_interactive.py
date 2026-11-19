"""
测试对象：src/plotlib/interactive.py 的 InteractivePlotter —— 不打开浏览器。

分层（2026-11-19 整理）：分组规则只在 test_plot_plan.py 测；这里只测 Plotly 把计划画对
（位置 → 颜色、样式翻译、按组分页）和它独有的功能（模板、两种滑块）。
与 matplotlib 的对照、两个绘图器共同的构造约定在 test_backend_parity.py。

数据来自 conftest.py 的 eis_dataset：3 个样品，色带位置 0、1/3、2/3。
"""
from typing import Any, cast

import numpy as np
import pytest

pytest.importorskip("plotly")
import plotly.colors as plyc
import plotly.graph_objects as go

from plotlib.dataset import DataSet
from plotlib.group import Group
from plotlib.interactive import InteractivePlotter
from plotlib.plot_common import plan_figures

PLASMA = plyc.get_colorscale('Plasma')      # InteractivePlotter 默认色带


def _traces(fig: go.Figure) -> tuple[go.Scatter, ...]:
    """Plotly 对 fig.data 的类型标注过宽；测试图里只有 Scatter。cast 不改变运行时对象。"""
    return cast(tuple[go.Scatter, ...], fig.data)


def _layout(fig: go.Figure) -> dict[str, Any]:
    """以普通字典读取 layout（只含显式设置的属性）。

    Plotly 给 Layout 各层属性标注的是宽泛联合类型，逐层访问会被检查器误报；
    断言只关心最终值，读字典即可。
    """
    return cast(dict[str, Any], fig.to_dict()["layout"])


def _asset(plot: InteractivePlotter) -> go.Figure:
    """取出已绘制的 Figure，并让类型检查器知道它不是 None。"""
    assert plot.asset is not None
    return plot.asset


def plasma(position: float) -> str:
    """色带位置 → Plotly 颜色字符串（与 InteractivePlotter 默认色带相同）。"""
    return cast(str, plyc.sample_colorscale(PLASMA, [position])[0])


def overlap_config():
    """样品 1 同时属于 A、B 两组；只有 A 写了线型。与 test_plot_plan.py 相同。"""
    return {
        'A': {'num': [0, 1], 'linestyle': 'dash'},
        'B': {'num': [1, 2]},
    }


def plot_group(dataset, config, merge_groups=False) -> InteractivePlotter:
    """按配置建 Group（每次新建：Group 会原地格式化传入的配置）并画分组图。"""
    plot = InteractivePlotter(dataset, groups=Group(dataset, config))
    plot.plot_plotly_group(merge_groups=merge_groups)
    return plot


def page_samples(plot: InteractivePlotter) -> dict[str, list[int]]:
    """{页名: [样品号]}：每一页画了哪些样品（按画线顺序）。"""
    return {key: list(page) for key, page in plot.pages.items()}


# ══════════════════════════════════════════════
# plot_plotly_object：不分组的计划（一张 'main' 图）
# ══════════════════════════════════════════════
def test_plot_data_and_repeated_calls(eis_dataset):
    """每条 trace 与不分组计划的曲线一一对应（顺序、名字、数据）；坐标轴标题是单位；重复调用生成新的 Figure。"""
    plot = InteractivePlotter(eis_dataset, plotdataRowNum_x=0, plotdataRowNum_y=1)
    assert plot.plot_plotly_object() is plot
    first = _asset(plot)
    [spec] = plan_figures(eis_dataset, None, 0, 1)
    assert len(_traces(first)) == len(plot.plot_artists) == len(spec.curves) == 3
    for trace, curve in zip(_traces(first), spec.curves):
        assert trace.name == curve.label
        np.testing.assert_array_equal(trace.x, curve.x)
        np.testing.assert_array_equal(trace.y, curve.y)
    assert _layout(first)['xaxis']['title']['text'] == 'Frequency(Hz)'
    assert _layout(first)['yaxis']['title']['text'] == "Zs'(ohm)"

    plot.plot_plotly_object()
    assert plot.asset is not first
    assert len(plot.plot_artists) == 3
    assert all(a is b for a, b in zip(plot.plot_artists, _traces(_asset(plot))))


def test_sparse_sample_ids_colors(sparse_dataset):
    """
    样品号 0、5、9：计划给的位置 0、1/3、2/3 换成 Plasma 色带上的颜色（位置怎么算见 test_plot_common.py）。
    回归：曾把样品号当作颜色列表的下标，画到样品 5 时 IndexError。
    """
    fig = _asset(InteractivePlotter(sparse_dataset).plot_plotly_object())
    assert [trace.line.color for trace in _traces(fig)] == [plasma(p) for p in (0, 1/3, 2/3)]


# ══════════════════════════════════════════════
# plot_plotly_group：把计划画对（分组规则本身在 test_plot_plan.py）
# ══════════════════════════════════════════════
def test_merge_mode_group_head_color(eis_dataset):
    """
    合并模式按计划的位置上色：样品 0、1 归 A（组首 0，位置 0）；
    样品 2 归 B，B 的组首是样品 1（位置 1/3）。
    """
    plot = plot_group(eis_dataset, overlap_config(), merge_groups=True)
    assert [t.line.color for t in _traces(_asset(plot))] == [plasma(0), plasma(0), plasma(1/3)]


@pytest.mark.parametrize("style, expected", [
    ({'linestyle': 'dash'},     {'line.dash': 'dash'}),
    ({'linestyle': (3, 5)},     {'line.dash': '9px,15px'}),           # 段长 × 线宽 3
    ({'marker': 'square'},      {'marker.symbol': 'square', 'mode': 'lines+markers'}),
    ({'color': (255, 0, 0)},    {'line.color': 'rgb(255,0,0)'}),
    ({},                        {'mode': 'lines'}),                   # 没写样式：只画线
], ids=['dash', 'custom-dash', 'marker', 'rgb-color', 'no-style'])
def test_group_style_translated(eis_dataset, style, expected):
    """分组写了的样式按 Plotly 写法放到 trace 上（标准写法 → style.translate_*(v, 'plotly')）。"""
    plot = plot_group(eis_dataset, {'A': {'num': [0, 1], **style}})
    trace = _traces(_asset(plot))[0]
    for path, value in expected.items():
        obj = trace
        for attr in path.split('.'):
            obj = getattr(obj, attr)
        assert obj == value, path


def test_group_marker_color_follows_line(eis_dataset):
    """写了 marker 时，点的颜色与线一致（都是样品色），不会落回 Plotly 的默认配色。"""
    plot = plot_group(eis_dataset, {'A': {'num': [0, 1], 'marker': 'square'}})
    for trace in _traces(_asset(plot)):
        props = trace.to_plotly_json()      # 读字典：Plotly 给 marker 标注的类型过宽，属性访问会被检查器误报
        assert props['marker']['color'] == props['line']['color']


def test_empty_groups_falls_back_to_plot_object(eis_dataset):
    """不分组时 plot_plotly_group 与 plot_plotly_object 画出相同的曲线。"""
    grouped = InteractivePlotter(eis_dataset)
    assert grouped.plot_plotly_group() is grouped
    plain = InteractivePlotter(eis_dataset).plot_plotly_object()

    assert [t.name for t in _traces(_asset(grouped))] == [t.name for t in _traces(_asset(plain))]
    assert [t.line.color for t in _traces(_asset(grouped))] == [t.line.color for t in _traces(_asset(plain))]


def test_group_figure_formatter(eis_dataset):
    """figure_formatter 在默认格式之后调用一次，收到的就是保存下来的 Figure。"""
    received = []
    plot = InteractivePlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()))
    plot.plot_plotly_group(figure_formatter=received.append)

    assert len(received) == 1
    assert received[0] is plot.asset


# ──────────────────────────────────────────────
# 分离模式 = 一张图按组翻页，每页是计划里的一张 FigureSpec（步骤 6.4）
# ──────────────────────────────────────────────
def test_separate_is_default(eis_dataset):
    """不传 merge_groups 就是分离模式：每组一页，重叠的样品 1 在两页各画一次，共 4 条。"""
    plot = InteractivePlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()))
    assert plot.plot_plotly_group() is plot

    assert len(_traces(_asset(plot))) == len(plot.plot_artists) == 4
    assert page_samples(plot) == {'A': [0, 1], 'B': [1, 2]}


def test_same_sample_styled_per_page(eis_dataset):
    """样品 1 在 A 页用 A 的线型（dash），在 B 页没有分组线型（B 没写）。"""
    plot = plot_group(eis_dataset, overlap_config())
    assert plot.pages['A'][1].line.dash == 'dash'
    assert plot.pages['B'][1].line.dash is None


def test_separate_colors_by_sample(eis_dataset):
    """分离模式按样品上色（不是组首色）：B 页的样品 1、2 分别取位置 1/3、2/3。"""
    page_b = plot_group(eis_dataset, overlap_config()).pages['B']
    assert [page_b[1].line.color, page_b[2].line.color] == [plasma(1/3), plasma(2/3)]


def test_only_first_page_visible(eis_dataset):
    """刚画完只显示第一页，否则同一样品的几条线叠在一起；翻页用 add_group_slider。"""
    plot = plot_group(eis_dataset, overlap_config())
    assert [t.visible for t in plot.pages['A'].values()] == [True, True]
    assert [t.visible for t in plot.pages['B'].values()] == [False, False]


def test_template_hides_minor_log_labels(eis_dataset):
    """对数轴 10^n 之间默认显示小号 2、5 标签，大小不一致，模板默认关闭。"""
    fig = _asset(InteractivePlotter(eis_dataset).plot_plotly_object())
    template_layout = _layout(fig)['template']['layout']
    assert template_layout['xaxis']['minorloglabels'] == 'none'
    assert template_layout['yaxis']['minorloglabels'] == 'none'


@pytest.mark.parametrize("mode, expected", [
    ("single", [[True, False, False], [False, True, False], [False, False, True]]),
    ("cumulative", [[True, False, False], [True, True, False], [True, True, True]]),
])
def test_slider_steps(eis_dataset, mode, expected):
    plot = InteractivePlotter(eis_dataset).plot_plotly_object()
    fig = plot.add_slider(mode)
    assert fig is plot.asset
    assert [trace.visible for trace in _traces(fig)] == expected[0]
    slider = _layout(fig)['sliders'][0]
    assert slider['active'] == 0
    assert len(slider['steps']) == 3
    for i, step in enumerate(slider['steps']):
        assert step['method'] == 'update'
        assert list(step['args'][0]['visible']) == expected[i]
        assert step['label'] == f'S{i}'
        assert step['args'][1]['title']['text'] == f'S{i}'
    fig.to_json()
    plot.add_slider(mode)
    assert len(_layout(fig)['sliders']) == 1


def test_slider_default_look(eis_dataset):
    """初始标题等于第 0 档；短标签放得下时可见；用户回调可覆盖默认值。"""
    plot = InteractivePlotter(eis_dataset).plot_plotly_object()
    fig = plot.add_slider(slider_formatter=lambda s: s.update(currentvalue_prefix="G: "))
    layout = _layout(fig)
    slider = layout['sliders'][0]
    assert layout['title']['text'] == 'S0'
    assert slider['font']['color'] == 'black'
    assert slider['borderwidth'] == 1
    assert slider['currentvalue']['prefix'] == 'G: '


def test_slider_hides_crowded_labels(eis_dataset):
    """33 条长名称（如 piezo 数据）会互相压住，默认隐藏档位标签。"""
    plot = InteractivePlotter(eis_dataset)
    plot.asset = go.Figure(layout=dict(template=plot._create_template()))
    for i in range(33):
        plot.asset.add_scatter(x=[0, 1], y=[0, i], name=f'Mg10-back-1mm-relax-{i}')
    slider = _layout(plot.add_slider())['sliders'][0]
    assert slider['font']['color'] == 'rgba(0,0,0,0)'
    assert slider['currentvalue']['font']['color'] == 'black'


def test_slider_requires_figure(eis_dataset):
    with pytest.raises(RuntimeError, match='请先调用绘图方法'):
        InteractivePlotter(eis_dataset).add_slider()


def test_slider_rejects_empty_figure(eis_dataset):
    plot = InteractivePlotter(eis_dataset)
    plot.asset = go.Figure()
    with pytest.raises(RuntimeError, match='图中没有曲线'):
        plot.add_slider()


def test_invalid_mode_does_not_change_visibility(eis_dataset):
    plot = InteractivePlotter(eis_dataset).plot_plotly_object()
    before = _asset(plot).to_json()
    with pytest.raises(ValueError, match='不支持的 mode'):
        # 故意传入非法值，检验运行时校验；类型检查器的报错是预期的。
        plot.add_slider('typo')  # pyright: ignore[reportArgumentType]
    assert _asset(plot).to_json() == before


# ──────────────────────────────────────────────
# 分组滑块：按页翻（步骤 6.4；与按曲线的 add_slider 是两个方法）
# ──────────────────────────────────────────────
def test_group_slider_steps(eis_dataset):
    """每档一页：档位标签和标题是组名，只显示这一页的 trace；当前值前缀是 'Group: '。"""
    plot = plot_group(eis_dataset, overlap_config())
    received = []
    fig = plot.add_group_slider(slider_formatter=received.append)

    assert fig is plot.asset
    layout = _layout(fig)
    slider = layout['sliders'][0]
    assert [step['label'] for step in slider['steps']] == ['A', 'B']
    assert [step['args'][1]['title']['text'] for step in slider['steps']] == ['A', 'B']
    # trace 顺序：A 页 [0, 1]，B 页 [1, 2]
    assert [list(step['args'][0]['visible']) for step in slider['steps']] == [
        [True, True, False, False],
        [False, False, True, True],
    ]
    assert slider['currentvalue']['prefix'] == 'Group: '
    assert layout['title']['text'] == 'A'
    assert len(received) == 1


def test_curve_slider_rejects_pages(eis_dataset):
    """多页的图上按曲线滑动没有意义（会跨页逐条显示）→ 提示改用 add_group_slider。"""
    plot = plot_group(eis_dataset, overlap_config())
    with pytest.raises(RuntimeError, match='add_group_slider'):
        plot.add_slider()


@pytest.mark.parametrize("draw", [
    lambda plot: plot.plot_plotly_object(),
    lambda plot: plot.plot_plotly_group(merge_groups=True),
], ids=['object', 'merge'])
def test_group_slider_rejects_single_page(eis_dataset, draw):
    """只有一页的图翻不了页 → 提示改用 add_slider。"""
    plot = InteractivePlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()))
    draw(plot)
    with pytest.raises(RuntimeError, match='add_slider'):
        plot.add_group_slider()


def test_empty_dataset_has_clear_error():
    with pytest.raises(RuntimeError, match='数据集为空'):
        InteractivePlotter(DataSet()).plot_plotly_object()
