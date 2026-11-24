"""
测试对象：src/plotlib/backends/plotly_backend.py 的 PlotlyBackend（docs/WORK_PLAN.md 步骤 6.7）

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
from plotlib.plot_spec import Appearance, FigureSpec, LineSpec, LineStyle
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
        LineSpec(sample_idx=7, x=np.array([0, 1, 2]), y=np.array([3, 4, 5]), label='手写一',
                 group_name=None, color_position=None, style=LineStyle(color=(255, 0, 0))),
        LineSpec(sample_idx=8, x=np.array([0, 1, 2]), y=np.array([6, 7, 8]), label='手写二',
                 group_name=None, color_position=0.5),
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


# ══════════════════════════════════════════════
# 双 Y 轴：右轴是 layout 里的 yaxis2，右线挂到 y2；左红右蓝来自排版预设
# ══════════════════════════════════════════════
def test_dual_y(eis_dataset):
    drawn = DataPlotter(eis_dataset, backend='plotly').plot_dual_y(
        right=(FREQ, ZS_IM)).figures[0]
    left, right = drawn.artist(0), drawn.artist(0, 'right')
    lay = layout(drawn.fig)

    assert lay['yaxis2']['overlaying'] == 'y' and lay['yaxis2']['side'] == 'right'
    # 右轴按自己的数据选整齐的刻度（Plotly 对叠加轴默认 'sync' 对齐左轴，刻度值不整齐；对照 matplotlib twinx）
    assert lay['yaxis2']['tickmode'] == 'auto'
    assert right.yaxis == 'y2' and left.yaxis in (None, 'y')
    # 图例（2026-11-20，参照 Origin 图）：两条线都进图例、各写自己的单位，标题是样品名；图外上方、右对齐
    assert right.showlegend is not False
    assert (left.name, right.name) == ("Zs'(ohm)", "Zs''(ohm)")
    assert lay['legend']['title']['text'] == 'S0'
    assert (lay['legend']['x'], lay['legend']['y']) == (1, 1.02)
    assert (lay['legend']['xanchor'], lay['legend']['yanchor']) == ('right', 'bottom')
    assert (left.line.color, right.line.color) == ('red', 'blue')
    assert lay['yaxis']['title']['font']['color'] == 'red'
    assert lay['yaxis2']['title']['font']['color'] == 'blue'
    assert lay['yaxis2']['title']['text'] == "Zs''(ohm)"
    assert lay['yaxis2']['tickformat'] == '.4f'                # 预设：右轴四位小数


# ══════════════════════════════════════════════
# 排版预设与外观：翻译后应用到 layout / 模板
# ══════════════════════════════════════════════
def test_layout_preset_applied(eis_dataset):
    """多线图：图例在图外右侧、纵轴两位小数（横轴不写格式）；xy：纵轴四位小数、图例在右下角。"""
    multi = layout(DataPlotter(eis_dataset, backend='plotly').plot_multiline().figures['main'].fig)
    assert multi['legend']['x'] == 1.02 and multi['legend']['xanchor'] == 'left'
    assert 'tickformat' not in multi['xaxis'] and multi['yaxis']['tickformat'] == '.2f'

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


def test_ticks_in_template():
    """
    刻度（TickStyle，磅 → 像素）写进模板，所有轴（含右轴）都用：默认朝外、主刻度 6 × 3 磅、显示次刻度 3 × 3 磅、
    对数轴次刻度不写文字；改了的字段照改（只写要改的，其余沿用默认）。
    """
    from plotlib.plot_spec import DEFAULT_TICKS, TickStyle

    px = 100 / 72
    axis = plotly_backend().template.to_plotly_json()['layout']['xaxis']
    assert (axis['ticks'], axis['ticklen'], axis['tickwidth']) == ('outside', pytest.approx(6 * px), pytest.approx(3 * px))
    assert axis['minor']['ticks'] == 'outside'
    assert (axis['minor']['ticklen'], axis['minor']['tickwidth']) == (pytest.approx(3 * px), pytest.approx(3 * px))
    assert axis['minorloglabels'] == 'none'

    # 叠加到默认值上（DataPlotter(ticks=...) 内部就是这样做的）
    custom = plotly_backend(ticks=DEFAULT_TICKS.updated(TickStyle(minor=False, label_size=14, minor_labels='short'))) \
        .template.to_plotly_json()['layout']['xaxis']
    assert custom['minor']['ticks'] == ''
    assert custom['tickfont']['size'] == pytest.approx(14 * px)
    assert custom['minorloglabels'] == 'small digits'
    assert custom['ticklen'] == pytest.approx(6 * px)                # 没写的沿用默认


def test_frame_by_layout(eis_dataset):
    """
    边框（对照 matplotlib）：多线图默认无框（X、Y 都不镜像）；双 Y 轴完整的框：上边 = X 轴镜像，右边是右轴自己的轴线，
    左 Y 轴不镜像（否则左轴的红色镜像线会叠在右轴上）；全局写了 top=True 就盖过多线图的预设。
    """
    from plotlib.plot_spec import FrameStyle

    multi = layout(DataPlotter(eis_dataset, backend='plotly').plot_multiline().figures['main'].fig)
    assert multi['xaxis']['mirror'] is False and multi['yaxis']['mirror'] is False

    dual = layout(DataPlotter(eis_dataset, backend='plotly').plot_dual_y(right=(FREQ, ZS_IM)).figures[0].fig)
    assert dual['xaxis']['mirror'] is True and dual['yaxis']['mirror'] is False

    boxed = layout(DataPlotter(eis_dataset, backend='plotly', frame=FrameStyle(top=True, right=True))
                   .plot_multiline().figures['main'].fig)
    assert boxed['xaxis']['mirror'] is True and boxed['yaxis']['mirror'] is True


def test_global_legend_and_lines_in_template(eis_dataset):
    """全局图例字号、线宽（磅）按 dpi 换成像素写进模板；全局图例位置盖过版式预设。"""
    from plotlib.plot_spec import LegendStyle, LineStyle

    px = 100 / 72
    drawn = DataPlotter(eis_dataset, backend='plotly', lines=LineStyle(width=2), legend=LegendStyle(
        font_size=14, position='upper left')).plot_multiline().figures['main']
    lay = layout(drawn.fig)
    assert lay['template']['data']['scatter'][0]['line']['width'] == pytest.approx(2 * px)
    assert lay['legend']['font']['size'] == pytest.approx(14 * px)
    assert (lay['legend']['x'], lay['legend']['xanchor']) == (0.02, 'left')     # 盖过预设的图外右侧


def test_label_pad_applies_as_whole_pixels(eis_dataset):
    """全局 TickStyle(label_pad=4) 能画：4 磅换成整数像素写进模板（回归，1.0 发布前复审：曾传 5.56 被 Plotly 拒绝）。"""
    from plotlib.plot_spec import TickStyle

    fig = DataPlotter(eis_dataset, backend='plotly', ticks=TickStyle(label_pad=4)).plot_multiline().figures['main'].fig
    assert layout(fig)['template']['layout']['xaxis']['ticklabelstandoff'] == round(4 * 100 / 72)


def test_minor_label_style_rejected_by_plotly(eis_dataset):
    """Plotly 的次刻度没有文字属性：全局或单轴设了次刻度文字的字号 → 创建时就报错（用户定）。"""
    from plotlib.formatters import make_axes_formatter
    from plotlib.plot_spec import TickStyle

    with pytest.raises(ValueError, match='Plotly'):
        DataPlotter(eis_dataset, backend='plotly', ticks=TickStyle(minor_label_size=9))
    with pytest.raises(ValueError, match='Plotly'):
        make_axes_formatter(backend='plotly', ticks=TickStyle(minor_label_size=9))


def test_neglog_tickprefix(eis_dataset):
    """负对数：数据在计划里已取绝对值，Plotly 给对应的轴加负号前缀。"""
    lay = layout(DataPlotter(eis_dataset, backend='plotly', channel_x=FREQ, channel_y=ZS_IM)
                 .plot_multiline(neglog_y=True).figures['main'].fig)
    assert lay['yaxis']['tickprefix'] == '-'
    assert 'tickprefix' not in lay['xaxis']


# ══════════════════════════════════════════════
# 回调：按轴回调拿到这根轴自己的东西（第三方审查 E，做法 2，与 matplotlib 的 (ax, fig) / lines / legends 对应）；
# 整图回调收 (fig, axes)，axes 是 Plotly 配置里的轴名
# ══════════════════════════════════════════════
def test_formatters_receive_own_axis(eis_dataset):
    """
    轴回调 (轴名, fig)：轴名就是 figure_formatter 的 axes 字典里的那一项；
    线回调只拿到挂在这根轴上的 trace；图例回调拿到 [fig.layout.legend]（只有左轴有图例）。
    回归：三种回调曾都只收 fig，不知道自己是替哪根轴调用的。
    """
    received = {}
    plotter = DataPlotter(eis_dataset, backend='plotly').plot_dual_y(
        right=(FREQ, ZS_IM),
        axes_formatter=lambda axis, fig: received.setdefault('left_axes', (axis, fig)),
        right_axes_formatter=lambda axis, fig: received.setdefault('right_axes', (axis, fig)),
        lines_formatter=lambda traces: received.setdefault('left_lines', traces),
        right_lines_formatter=lambda traces: received.setdefault('right_lines', traces),
        legend_formatter=lambda legends: received.setdefault('legends', legends),
    )
    fig = plotter.figures[0].fig            # 三个样品三页，共用一个 Figure（6.8）

    assert received['left_axes'][0] == 'yaxis' and received['left_axes'][1] is fig
    assert received['right_axes'][0] == 'yaxis2' and received['right_axes'][1] is fig
    # 线回调拿到这根轴上所有页的线（多页时回调对整个 Figure 只调一次）；双 Y 轴每页的 key 就是样品号
    pages = [(int(k), page) for k, page in plotter.figures.items()]
    assert [id(t) for t in received['left_lines']] == [id(page.artist(k)) for k, page in pages]
    assert [id(t) for t in received['right_lines']] == [id(page.artist(k, 'right')) for k, page in pages]
    assert len(received['legends']) == 1
    assert received['legends'][0].to_plotly_json() == fig.layout.legend.to_plotly_json()


def test_figure_formatter_gets_axis_names(eis_dataset):
    """双 Y 轴的整图回调：axes 是 {'left': 'yaxis', 'right': 'yaxis2'}，用它改右轴配置。"""
    def color_right_title(fig, axes):
        fig.layout[axes['right']].title.text = '右轴'
    drawn = DataPlotter(eis_dataset, backend='plotly').plot_dual_y(
        right=(FREQ, ZS_IM), figure_formatter=color_right_title,
    ).figures[0]
    assert layout(drawn.fig)['yaxis2']['title']['text'] == '右轴'


# ══════════════════════════════════════════════
# 画法：散点也按计划上色（6.5 颜色一次赋值；柱状图在 plot_bars 测）
# ══════════════════════════════════════════════
def test_scatter_group_color(eis_dataset):
    groups = Group(eis_dataset, {'A': {'num': [0, 1], 'color': (255, 0, 0)}})
    trace = DataPlotter(eis_dataset, groups=groups, backend='plotly').plot_scatter().figures['A'].artist(0)
    assert isinstance(trace, go.Scatter)
    assert (trace.mode, cast(Any, trace).marker.color) == ('markers', 'rgb(255,0,0)')    # marker 的类型标注过宽


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


def test_log_format_keeps_minor_labels_hidden(eis_dataset):
    """
    显式格式绕过 Plotly 的次刻度标签模式。隐藏次刻度标签时，默认只在整数量级标注主刻度。
    手动间距、完整标签、线性轴及自动格式保留原设置。短标签与显式格式同时使用时引发异常。
    """
    from plotlib.formatters import make_axes_formatter
    from plotlib.plot_spec import AxisStyle, TickStyle

    def xaxis(style=AxisStyle(scale='log', format='{x:.0e}'), ticks=None, custom=None) -> dict[str, Any]:
        fmt = make_axes_formatter(x=style, ticks=ticks, custom=custom, backend='plotly')
        return layout(plotly_plotter(eis_dataset).plot_multiline(axes_formatter=fmt).figures['main'].fig)['xaxis']

    assert (xaxis()['tickformat'], xaxis()['dtick']) == ('.0e', 1)
    assert xaxis(custom=[lambda _axis, fig: fig.update_xaxes(dtick=2)])['dtick'] == 2
    for unchanged in (xaxis(ticks=TickStyle(minor_labels='full')), xaxis(AxisStyle(scale='linear', format='{x:.1f}')),
                      xaxis(AxisStyle(scale='log'))):
        assert 'dtick' not in unchanged
    with pytest.raises(ValueError, match="minor_labels='short'"):
        xaxis(ticks=TickStyle(minor_labels='short'))


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
        assert step['args'][1] == {'title.text': f'S{i}'}     # 带点的路径：只改标题文字（6.8 起两种滑块共用）
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

    with pytest.raises(NotImplementedError, match='Plotly'):
        DataPlotter(eis_dataset).plot_multiline().add_slider()


# ══════════════════════════════════════════════
# 翻页（6.8）：多张计划画进同一个 Figure，每张计划一页（每页就是 matplotlib 那张图）；刚画完只显示第一页。
# 凡是画出多张计划的都翻页（分组分离模式、xy、双 Y 轴）：后端只认计划，不认是哪个绘图方法
# ══════════════════════════════════════════════
def overlap_config():
    """样品 1 同时属于 A、B 两组；只有 A 写了线型（与 test_plot_plan.py 相同）。"""
    return {'A': {'num': [0, 1], 'linestyle': 'dash'}, 'B': {'num': [1, 2]}}


def test_pages_share_one_figure(eis_dataset):
    """分组分离模式：两页共用一个 Figure、共 4 条 trace；每页的 artists 只有自己那页的 trace；刚画完只显示第一页。"""
    plotter = plotly_plotter(eis_dataset, overlap_config()).plot_groups()
    a, b = plotter.figures['A'], plotter.figures['B']

    assert a.fig is b.fig
    all_traces = cast(tuple, cast(go.Figure, a.fig).data)
    assert len(all_traces) == 4
    assert [t.name for t in a.artists] == ['S0', 'S1'] and [t.name for t in b.artists] == ['S1', 'S2']
    assert all(any(t is u for u in all_traces) for t in a.artists + b.artists)   # artists 就是图里的 trace
    assert [t.visible for t in a.artists] == [True, True]
    assert [t.visible for t in b.artists] == [False, False]


def test_each_page_matches_its_plan(eis_dataset):
    """同一样品在两页里是两条 trace，各用各组的样式（A 页虚线、B 页实线），颜色按样品（两页同色）。"""
    plotter = plotly_plotter(eis_dataset, overlap_config()).plot_groups()
    in_a, in_b = plotter.figures['A'].artist(1), plotter.figures['B'].artist(1)

    assert in_a is not in_b
    assert in_a.line.dash == 'dash' and in_b.line.dash is None
    assert in_a.line.color == in_b.line.color == plasma(1/3)


@pytest.mark.parametrize("draw, traces_per_page", [
    (lambda p: p.plot_xy(channel_x=ZS_RE, channel_y=ZS_IM), 1),
    (lambda p: p.plot_dual_y(right=(FREQ, ZS_IM)), 2),
], ids=['xy', 'dual_y'])
def test_per_sample_figures_become_pages(eis_dataset, draw, traces_per_page):
    """xy、双 Y 轴每个样品一张计划：在 Plotly 里也是一个 Figure 三页，只显示第一页。"""
    plotter = draw(plotly_plotter(eis_dataset))
    pages = list(plotter.figures.values())

    assert list(plotter.figures) == [0, 1, 2]
    assert all(page.fig is pages[0].fig for page in pages)
    assert len(cast(tuple, cast(go.Figure, pages[0].fig).data)) == 3 * traces_per_page
    assert [all(t.visible for t in page.artists) for page in pages] == [True, False, False]


def test_single_plan_is_not_paged(eis_dataset):
    """只有一张计划（多线图）照旧：所有线都显示，没有滑块。"""
    fig = plotly_plotter(eis_dataset).plot_multiline().figures['main'].fig
    assert all(t.visible is not False for t in cast(tuple, cast(go.Figure, fig).data))
    assert 'sliders' not in layout(fig)


def test_paged_callbacks_called_once(eis_dataset):
    """
    多页共用一套轴：按轴回调对整个 Figure 只调一次，线回调拿到这根轴上所有页的 trace；整图回调也只调一次。
    （各页的轴配置相同——同一次计划画出来的。）
    """
    calls = []
    plotly_plotter(eis_dataset, overlap_config()).plot_groups(
        axes_formatter=lambda axis, fig: calls.append(('axes', axis)),
        lines_formatter=lambda traces: calls.append(('lines', len(traces))),
        figure_formatter=lambda fig, axes: calls.append(('figure', tuple(axes))),
    )
    assert calls == [('axes', 'yaxis'), ('lines', 4), ('figure', ('left',))]


@pytest.mark.parametrize("mode, expected", [
    ('single',     [[True, True, False, False], [False, False, True, True]]),     # 第 i 档只显示第 i 页
    ('cumulative', [[True, True, False, False], [True, True, True, True]]),       # 第 i 档显示第 0 ~ i 页
])
def test_page_slider_modes(eis_dataset, mode, expected):
    """翻页滑块与曲线滑块同一套模式（用户要求），只是一档对应一页的 trace，而不是一条。"""
    fig = plotly_plotter(eis_dataset, overlap_config()).plot_groups().add_page_slider(mode)
    steps = layout(fig)['sliders'][0]['steps']
    assert [list(step['args'][0]['visible']) for step in steps] == expected


def test_page_slider(eis_dataset):
    """
    add_page_slider（默认 'single'）：每页一档，档位标签是每页的名字（这里是组名）；
    翻页时标题和图例标题换成这一页的；当前值默认不加前缀；初始停在第 0 档；重复添加只保留一个；slider_formatter 最后执行。
    """
    plotter = plotly_plotter(eis_dataset, overlap_config()).plot_groups(legend_title='Group {name}')
    fig = plotter.add_page_slider()
    assert fig is plotter.figures['A'].fig

    lay = layout(fig)
    slider = lay['sliders'][0]
    assert slider['active'] == 0
    assert [step['label'] for step in slider['steps']] == ['A', 'B']
    assert [list(step['args'][0]['visible']) for step in slider['steps']] == [
        [True, True, False, False], [False, False, True, True]]
    assert [step['args'][1] for step in slider['steps']] == [
        {'title.text': 'A', 'legend.title.text': 'Group A'},
        {'title.text': 'B', 'legend.title.text': 'Group B'}]
    assert lay['title']['text'] == 'A' and lay['legend']['title']['text'] == 'Group A'
    assert slider['currentvalue'].get('prefix', '') == ''

    plotter.add_page_slider(slider_formatter=lambda s: s.update(currentvalue_prefix='Group: '))
    lay = layout(fig)
    assert len(lay['sliders']) == 1
    assert lay['sliders'][0]['currentvalue']['prefix'] == 'Group: '


def test_page_slider_labels_are_sample_names(eis_dataset):
    """每个样品一页（xy）：档位标签是样品名。"""
    fig = plotly_plotter(eis_dataset).plot_xy(channel_x=ZS_RE, channel_y=ZS_IM).add_page_slider()
    assert [step['label'] for step in layout(fig)['sliders'][0]['steps']] == ['S0', 'S1', 'S2']


def add_reference_lines(fig, axes):
    """整图回调：加两条不属于任何样品的参考线，一条显示、一条只在图例里（visible='legendonly'）。"""
    _ = axes
    fig.add_trace(go.Scatter(x=[1, 100], y=[15, 15], name='ref'))
    fig.add_trace(go.Scatter(x=[1, 100], y=[25, 25], name='ref hidden', visible='legendonly'))


@pytest.mark.parametrize("draw, add, labels", [
    (lambda p: p.plot_xy(channel_x=ZS_RE, channel_y=ZS_IM, figure_formatter=add_reference_lines),
     lambda p: p.add_page_slider(), ['S0', 'S1', 'S2']),
    (lambda p: p.plot_multiline(figure_formatter=add_reference_lines),
     lambda p: p.add_slider('single'), ['S0', 'S1', 'S2']),
], ids=['page_slider', 'curve_slider'])
def test_sliders_keep_shared_traces(eis_dataset, draw, add, labels):
    """
    整图回调加的参考线不属于计划里的任何曲线：两种滑块都不给它分档，每一档都保持它原来的显隐；
    滑动的只有计划登记的曲线（55576fb 复审 4）。
    回归：翻页滑块曾在每一档都把参考线设为隐藏；曲线滑块曾把参考线也当成一档。
    """
    plotter = draw(plotly_plotter(eis_dataset))
    fig = add(plotter)
    steps = layout(fig)['sliders'][0]['steps']
    assert [step['label'] for step in steps] == labels
    assert all(list(step['args'][0]['visible'])[-2:] == [True, 'legendonly'] for step in steps)
    assert fig.data[-2].visible in (None, True) and fig.data[-1].visible == 'legendonly'


def test_two_sliders_misuse(eis_dataset):
    """
    两种滑块用错 → RuntimeError 并提示该用哪个：多页图上用 add_slider（曲线滑块），一页图上用 add_page_slider；
    未绘图 → RuntimeError；matplotlib → NotImplementedError；mode 写错 → ValueError（与 add_slider 相同）。
    """
    with pytest.raises(ValueError, match='不支持的 mode'):
        plotly_plotter(eis_dataset, overlap_config()).plot_groups().add_page_slider('typo')  # pyright: ignore[reportArgumentType]
    with pytest.raises(RuntimeError, match='add_page_slider'):
        plotly_plotter(eis_dataset, overlap_config()).plot_groups().add_slider()
    with pytest.raises(RuntimeError, match='add_slider'):
        plotly_plotter(eis_dataset).plot_multiline().add_page_slider()
    with pytest.raises(RuntimeError, match='请先调用绘图方法'):
        plotly_plotter(eis_dataset).add_page_slider()
    with pytest.raises(NotImplementedError, match='Plotly'):
        DataPlotter(eis_dataset, groups=Group(eis_dataset, overlap_config())).plot_groups().add_page_slider()
