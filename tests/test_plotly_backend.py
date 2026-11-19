"""
测试对象：src/plotlib/backends/plotly_backend.py 的 PlotlyBackend（STRUCTURE_REVIEW 6.7）

与 matplotlib 后端同一个接口：draw(计划, figsize, formatters, figure_formatter) -> DrawnFigure，
DataPlotter(backend='plotly') 的四种绘图方法结果形状与 matplotlib 相同（figures = {key: DrawnFigure}）。
分组规则在 test_plot_plan.py；翻译（字号、尺寸、图例位置、刻度格式）在 test_style.py；
这里只测 Plotly 把计划画对、把排版预设和外观应用上。

Plotly 没有轴对象：DrawnFigure.axes 放 Plotly 配置里的轴名 {'left': 'yaxis', 'right': 'yaxis2'}（两根轴共用 'xaxis'）。
"""
from typing import Any, cast

import numpy as np
import pytest

pytest.importorskip("plotly")
import plotly.colors as plyc
import plotly.graph_objects as go

from plotlib.group import Group
from plotlib.plot_spec import Appearance, CurveSpec, FigureSpec
from plotlib.plotter import DataPlotter

FREQ, ZS_RE, ZS_IM = 0, 1, 2
PLASMA = plyc.get_colorscale('Plasma')


def plasma(position: float) -> str:
    return cast(str, plyc.sample_colorscale(PLASMA, [position])[0])


def layout(fig: go.Figure) -> dict[str, Any]:
    """以普通字典读取 layout（只含显式设置的属性）；Plotly 的属性类型标注过宽，读字典更省事。"""
    return cast(dict[str, Any], fig.to_dict()['layout'])


def plotly_backend(**appearance):
    from plotlib.backends.plotly_backend import PlotlyBackend
    return PlotlyBackend(Appearance(**appearance), cmap=None)


# ══════════════════════════════════════════════
# 后端只读计划（与 test_plotter.py 的 test_backend_draws_only_from_plan 同一形状）
# ══════════════════════════════════════════════
def test_backend_draws_only_from_plan():
    spec = FigureSpec(key='hand', x_unit='X(u)', y_unit='Y(u)', curves=[
        CurveSpec(sample_idx=7, x=np.array([0, 1, 2]), y=np.array([3, 4, 5]), label='手写一',
                  group_name=None, color_position=None, style={'color': (255, 0, 0)}),
        CurveSpec(sample_idx=8, x=np.array([0, 1, 2]), y=np.array([6, 7, 8]), label='手写二',
                  group_name=None, color_position=0.5, style={}),
    ])
    drawn = plotly_backend().draw(spec, figsize=(6, 4))

    assert drawn.spec is spec
    assert isinstance(drawn.fig, go.Figure)
    first, second = drawn.artist(7), drawn.artist(8)
    np.testing.assert_array_equal(first.y, [3, 4, 5])
    assert first.name == '手写一'
    assert first.line.color == 'rgb(255,0,0)'                  # 计划写的颜色
    assert second.line.color == plasma(0.5)                    # 计划给的色带位置
    lay = layout(drawn.fig)
    assert lay['xaxis']['title']['text'] == 'X(u)'
    assert (lay['width'], lay['height']) == (600, 400)          # figsize × dpi（默认 100）
    assert drawn.axes == {'left': 'yaxis'}


@pytest.mark.parametrize("method, keys, axes", [
    ('plot_multiline',   ['main'],    {'left': 'yaxis'}),
    ('plot_groups',  ['A', 'B'],  {'left': 'yaxis'}),
    ('plot_xy',  [0, 1, 2],   {'left': 'yaxis'}),
    ('plot_dual_y', [0, 1, 2],   {'left': 'yaxis', 'right': 'yaxis2'}),
])
def test_dataplotter_with_plotly_backend(eis_dataset, method, keys, axes):
    """DataPlotter(backend='plotly')：四种方法都能画，结果形状与 matplotlib 相同。"""
    groups = Group(eis_dataset, {'A': {'num': [0, 1]}, 'B': {'num': [1, 2]}})
    plotter = DataPlotter(eis_dataset, groups=groups, backend='plotly')
    match method:
        case 'plot_multiline':   plotter.plot_multiline()
        case 'plot_groups':  plotter.plot_groups()
        case 'plot_xy':  plotter.plot_xy(channel_x=ZS_RE, channel_y=ZS_IM)
        case 'plot_dual_y': plotter.plot_dual_y(right=(FREQ, ZS_IM))

    assert plotter.backend.name == 'plotly'
    assert list(plotter.figures) == keys
    for drawn in plotter.figures.values():
        assert isinstance(drawn.fig, go.Figure)
        assert len(drawn.artists) == len(drawn.spec.curves) == len(cast(tuple, cast(go.Figure, drawn.fig).data))
        assert drawn.axes == axes


# ══════════════════════════════════════════════
# 双 Y 轴：右轴是 layout 里的 yaxis2，右线挂到 y2；左红右蓝来自排版预设
# ══════════════════════════════════════════════
def test_dual_y(eis_dataset):
    drawn = DataPlotter(eis_dataset, backend='plotly').plot_dual_y(
        right=(FREQ, ZS_IM)).figures[0]
    left, right = drawn.artist(0), drawn.artist(0, 'right')
    lay = layout(drawn.fig)

    assert lay['yaxis2']['overlaying'] == 'y' and lay['yaxis2']['side'] == 'right'
    assert right.yaxis == 'y2' and left.yaxis in (None, 'y')
    assert right.showlegend is False                           # 与 matplotlib 一致：右线不进图例
    assert (left.line.color, right.line.color) == ('red', 'blue')
    assert lay['yaxis']['title']['font']['color'] == 'red'
    assert lay['yaxis2']['title']['font']['color'] == 'blue'
    assert lay['yaxis2']['title']['text'] == "Zs''(ohm)"
    assert lay['yaxis2']['tickformat'] == '.4f'                # 预设：右轴四位小数


# ══════════════════════════════════════════════
# 排版预设与外观：翻译后应用到 layout / 模板
# ══════════════════════════════════════════════
def test_layout_preset_applied(eis_dataset):
    """多线图：图例在图外右侧、坐标两位小数；xy：纵轴四位小数、图例在右下角。"""
    multi = layout(DataPlotter(eis_dataset, backend='plotly').plot_multiline().figures['main'].fig)
    assert multi['legend']['x'] == 1.02 and multi['legend']['xanchor'] == 'left'
    assert multi['xaxis']['tickformat'] == '.2f' and multi['yaxis']['tickformat'] == '.2f'

    xy = layout(DataPlotter(eis_dataset, backend='plotly').plot_xy(
        channel_x=ZS_RE, channel_y=ZS_IM).figures[0].fig)
    assert xy['yaxis']['tickformat'] == '.4f' and 'tickformat' not in xy['xaxis']
    assert xy['legend']['xanchor'] == 'right' and xy['legend']['yanchor'] == 'bottom'


def test_appearance_in_template():
    """外观按显式 dpi 换成像素：字号 22 磅 → 22 × 100 / 72 像素；dpi 加倍，像素也加倍。"""
    def template_layout(**appearance) -> dict[str, Any]:
        return plotly_backend(**appearance).template.to_plotly_json()['layout']

    assert template_layout()['font']['size'] == pytest.approx(22 * 100 / 72)
    assert template_layout()['legend']['font']['size'] == pytest.approx(10 * 100 / 72)
    assert template_layout(dpi=200)['font']['size'] == pytest.approx(22 * 200 / 72)


def test_neglog_tickprefix(eis_dataset):
    """负对数：数据在计划里已取绝对值，Plotly 给对应的轴加负号前缀。"""
    lay = layout(DataPlotter(eis_dataset, backend='plotly', channel_x=FREQ, channel_y=ZS_IM)
                 .plot_multiline(neglog_y=True).figures['main'].fig)
    assert lay['yaxis']['tickprefix'] == '-'
    assert 'tickprefix' not in lay['xaxis']


# ══════════════════════════════════════════════
# 回调：Plotly 的回调都收 fig；整图回调收 (fig, axes)，axes 是 Plotly 配置里的轴名
# ══════════════════════════════════════════════
def test_formatters_receive_figure(eis_dataset):
    received = {}
    drawn = DataPlotter(eis_dataset, backend='plotly').plot_multiline(
        axes_formatter=lambda fig: received.setdefault('axes', fig),
        lines_formatter=lambda fig: received.setdefault('lines', fig),
        legend_formatter=lambda fig: received.setdefault('legend', fig),
    ).figures['main']
    assert received == {'axes': drawn.fig, 'lines': drawn.fig, 'legend': drawn.fig}


def test_figure_formatter_gets_axis_names(eis_dataset):
    """双 Y 轴的整图回调：axes 是 {'left': 'yaxis', 'right': 'yaxis2'}，用它改右轴配置。"""
    def color_right_title(fig, axes):
        fig.layout[axes['right']].title.text = '右轴'
    drawn = DataPlotter(eis_dataset, backend='plotly').plot_dual_y(
        right=(FREQ, ZS_IM), figure_formatter=color_right_title,
    ).figures[0]
    assert layout(drawn.fig)['yaxis2']['title']['text'] == '右轴'


# ══════════════════════════════════════════════
# 画法：散点、柱状图也按计划上色（6.5 颜色一次赋值；Plotly 的这部分 6.7 补测）
# ══════════════════════════════════════════════
@pytest.mark.parametrize("plot_kind, trace_type, mode", [
    ('scatter', go.Scatter, 'markers'),
    ('bar',     go.Bar,     None),
])
def test_plot_kind_and_group_color(eis_dataset, plot_kind, trace_type, mode):
    groups = Group(eis_dataset, {'A': {'num': [0, 1], 'color': (255, 0, 0)}})
    trace = DataPlotter(eis_dataset, groups=groups, backend='plotly') \
        .plot_groups(plot_kind=plot_kind).figures['A'].artist(0)
    assert isinstance(trace, trace_type)
    assert trace.marker.color == 'rgb(255,0,0)'
    if mode is not None:
        assert trace.mode == mode


# ══════════════════════════════════════════════
# 由 test_interactive.py 迁来（6.7b 删除 InteractivePlotter）：同样的期望，换成 DataPlotter(backend='plotly')
# ══════════════════════════════════════════════
def plotly_plotter(dataset, config=None, **kwargs) -> DataPlotter:
    """Plotly 后端的绘图器；config 给了就建 Group（每次新建：Group 会原地格式化传入的配置）。"""
    groups = Group(dataset, config) if config is not None else None
    return DataPlotter(dataset, groups=groups, backend='plotly', **kwargs)


def traces_of(plotter: DataPlotter, key='main') -> tuple:
    return tuple(plotter.figures[key].artists)


def test_plot_data_and_repeated_calls(eis_dataset):
    """每条 trace 与不分组计划的曲线一一对应（顺序、名字、数据）；坐标轴标题是单位；重复调用生成新的 Figure。"""
    plotter = plotly_plotter(eis_dataset, channel_x=FREQ, channel_y=ZS_RE)
    first = plotter.plot_multiline().figures['main']
    for trace, curve in zip(first.artists, first.spec.curves):
        assert trace.name == curve.label
        np.testing.assert_array_equal(trace.x, curve.x)
        np.testing.assert_array_equal(trace.y, curve.y)
    assert layout(first.fig)['yaxis']['title']['text'] == "Zs'(ohm)"

    second = plotter.plot_multiline().figures['main']
    assert second.fig is not first.fig
    assert all(a is b for a, b in zip(second.artists, cast(go.Figure, second.fig).data))


def test_sparse_sample_ids_colors(sparse_dataset):
    """
    样品号 0、5、9：计划给的位置 0、1/3、2/3 换成 Plasma 色带上的颜色。
    回归：曾把样品号当作颜色列表的下标，画到样品 5 时 IndexError。
    """
    plotter = plotly_plotter(sparse_dataset).plot_multiline()
    assert [t.line.color for t in traces_of(plotter)] == [plasma(p) for p in (0, 1/3, 2/3)]


def test_merge_mode_group_head_color(eis_dataset):
    """合并模式按计划的位置上色：样品 0、1 归 A（位置 0），样品 2 归 B、用 B 的组首样品 1 的位置 1/3。"""
    config = {'A': {'num': [0, 1], 'linestyle': 'dash'}, 'B': {'num': [1, 2]}}
    plotter = plotly_plotter(eis_dataset, config).plot_groups(merge_groups=True)
    assert [t.line.color for t in traces_of(plotter)] == [plasma(0), plasma(0), plasma(1/3)]


LINE_PX = 3 * 100 / 72      # 默认线宽 3 磅，dpi 100 → 像素；自定义虚线的段长按它换算


@pytest.mark.parametrize("style, expected", [
    ({'linestyle': 'dash'},     {'line.dash': 'dash'}),
    ({'linestyle': (3, 5)},     {'line.dash': f"{3 * LINE_PX:g}px,{5 * LINE_PX:g}px"}),
    ({'marker': 'square'},      {'marker.symbol': 'square', 'mode': 'lines+markers'}),
    ({'color': (255, 0, 0)},    {'line.color': 'rgb(255,0,0)'}),
    ({},                        {'mode': 'lines'}),
], ids=['dash', 'custom-dash', 'marker', 'rgb-color', 'no-style'])
def test_group_style_translated(eis_dataset, style, expected):
    """分组写了的样式按 Plotly 写法放到 trace 上（标准写法 → style.translate_*(v, 'plotly')）。"""
    trace = plotly_plotter(eis_dataset, {'A': {'num': [0, 1], **style}}).plot_groups().figures['A'].artist(0)
    for path, value in expected.items():
        obj = trace
        for attr in path.split('.'):
            obj = getattr(obj, attr)
        assert obj == value, path


def test_group_marker_color_follows_line(eis_dataset):
    """写了 marker 时，点的颜色与线一致，不会落回 Plotly 的默认配色。"""
    plotter = plotly_plotter(eis_dataset, {'A': {'num': [0, 1], 'marker': 'square'}}).plot_groups()
    for trace in traces_of(plotter, 'A'):
        props = trace.to_plotly_json()
        assert props['marker']['color'] == props['line']['color']


def test_template_hides_minor_log_labels(eis_dataset):
    """对数轴 10^n 之间默认显示小号 2、5 标签，大小不一致，模板默认关闭。"""
    fig = plotly_plotter(eis_dataset).plot_multiline().figures['main'].fig
    template_layout = layout(fig)['template']['layout']
    assert template_layout['xaxis']['minorloglabels'] == 'none'
    assert template_layout['yaxis']['minorloglabels'] == 'none'


def test_empty_dataset_has_clear_error():
    from plotlib.dataset import DataSet
    with pytest.raises(RuntimeError, match='数据集为空'):
        DataPlotter(DataSet(), backend='plotly').plot_multiline()


# ──────────────────────────────────────────────
# 滑块：DataPlotter.add_slider（6.7b 起；只有 Plotly 后端、只有一张图时可用）
# ──────────────────────────────────────────────
@pytest.mark.parametrize("mode, expected", [
    ("single", [[True, False, False], [False, True, False], [False, False, True]]),
    ("cumulative", [[True, False, False], [True, True, False], [True, True, True]]),
])
def test_slider_steps(eis_dataset, mode, expected):
    plotter = plotly_plotter(eis_dataset).plot_multiline()
    fig = plotter.add_slider(mode)
    assert fig is plotter.figures['main'].fig
    assert [trace.visible for trace in traces_of(plotter)] == expected[0]
    slider = layout(fig)['sliders'][0]
    assert slider['active'] == 0
    assert len(slider['steps']) == 3
    for i, step in enumerate(slider['steps']):
        assert step['method'] == 'update'
        assert list(step['args'][0]['visible']) == expected[i]
        assert step['label'] == f'S{i}'
        assert step['args'][1]['title']['text'] == f'S{i}'
    plotter.add_slider(mode)
    assert len(layout(fig)['sliders']) == 1             # 重复添加只保留一个滑块


def test_slider_default_look(eis_dataset):
    """初始标题等于第 0 档；短标签放得下时可见；用户回调可覆盖默认值。"""
    fig = plotly_plotter(eis_dataset).plot_multiline().add_slider(
        slider_formatter=lambda s: s.update(currentvalue_prefix="G: "))
    lay = layout(fig)
    slider = lay['sliders'][0]
    assert lay['title']['text'] == 'S0'
    assert slider['font']['color'] == 'black'
    assert slider['borderwidth'] == 1
    assert slider['currentvalue']['prefix'] == 'G: '


def test_slider_hides_crowded_labels():
    """33 条长名称（如 piezo 数据）会互相压住，默认隐藏档位标签。"""
    fig = go.Figure(layout=dict(width=1000))
    for i in range(33):
        fig.add_scatter(x=[0, 1], y=[0, i], name=f'Mg10-back-1mm-relax-{i}')
    slider = layout(plotly_backend().add_slider(fig))['sliders'][0]
    assert slider['font']['color'] == 'rgba(0,0,0,0)'
    assert slider['currentvalue']['font']['color'] == 'black'


def test_slider_errors(eis_dataset):
    """未绘图、图中没有曲线、mode 写错（且不改动已有的图）、多张图、matplotlib 后端 → 明确报错。"""
    with pytest.raises(RuntimeError, match='请先调用绘图方法'):
        plotly_plotter(eis_dataset).add_slider()
    with pytest.raises(RuntimeError, match='图中没有曲线'):
        plotly_backend().add_slider(go.Figure())

    plotter = plotly_plotter(eis_dataset).plot_multiline()
    before = cast(go.Figure, plotter.figures['main'].fig).to_json()
    with pytest.raises(ValueError, match='不支持的 mode'):
        plotter.add_slider('typo')
    assert cast(go.Figure, plotter.figures['main'].fig).to_json() == before

    with pytest.raises(RuntimeError, match='一张图'):
        plotly_plotter(eis_dataset).plot_xy(channel_x=ZS_RE, channel_y=ZS_IM).add_slider()
    with pytest.raises(NotImplementedError, match='Plotly'):
        DataPlotter(eis_dataset).plot_multiline().add_slider()
