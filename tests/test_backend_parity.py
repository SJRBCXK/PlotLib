"""
两个后端的对照：DataPlotter(backend='matplotlib') 与 DataPlotter(backend='plotly')

同一个入口、同一份绘图计划（plan.plan_*），换后端只换「怎么画」，所以：
  - 构造时对分组参数的约定相同（plan.resolve_groups，与后端无关）；
  - 同一绘图计划在两个后端生成相同的图数、曲线条数、顺序、标签和数据。
颜色不在这里比：两个库的色带实现不同，各自「位置 → 颜色」在 test_plotter.py / test_plotly_backend.py 里测。

数据来自 conftest.py 的 eis_dataset：3 个样品；配置里样品 1 同时属于 A、B 两组。
"""
import numpy as np
import pytest

pytest.importorskip("plotly")

from plotlib.formatters import (combine_formatters, make_axes_formatter, make_legend_formatter,
                                make_lines_formatter)
from plotlib.group import Group
from plotlib.plot_spec import AxesFormatter, AxisStyle, Layer, LegendStyle, LineStyle
from plotlib.plotter import DataPlotter

from conftest import EIS_UNITS

BACKENDS = pytest.mark.parametrize("backend", ['matplotlib', 'plotly'])
FREQ, ZS_RE, ZS_IM = 0, 1, 2


def overlap_config():
    """样品 1 同时属于 A、B 两组；只有 A 写了线型。与 test_plot_plan.py 相同。"""
    return {
        'A': {'num': [0, 1], 'linestyle': 'dash'},
        'B': {'num': [1, 2]},
    }


def assert_same_curves(traces, lines):
    """Plotly 的 trace 与 matplotlib 的 Line2D 一一对应：条数、顺序、标签、数据。"""
    assert len(traces) == len(lines)
    for trace, line in zip(traces, lines):
        assert trace.name == line.get_label()
        np.testing.assert_array_equal(trace.x, line.get_xdata())
        np.testing.assert_array_equal(trace.y, line.get_ydata())


# ══════════════════════════════════════════════
# 构造：分组参数只接受建在同一数据集上的 Group（两个后端一样）
# （分组配置本身的校验在 test_group.py）
# ══════════════════════════════════════════════
@BACKENDS
def test_groups_must_be_group_object(eis_dataset, backend):
    """传字典 → TypeError，提示先用 Group 包装（类型标注只在编辑器里提醒，运行时要自己检查）。"""
    with pytest.raises(TypeError, match="Group"):
        DataPlotter(eis_dataset, groups={'A': {'num': [0, 1]}}, backend=backend)  # pyright: ignore[reportArgumentType]


@BACKENDS
def test_groups_from_other_dataset_raises(eis_dataset, sparse_dataset, backend):
    """一个绘图器只对应一个数据集：Group 必须建在绘图器的数据集上。"""
    with pytest.raises(ValueError):
        DataPlotter(eis_dataset, groups=Group(sparse_dataset, {'A': {'num': [0, 5]}}), backend=backend)


@BACKENDS
def test_default_groups_is_empty_group(eis_dataset, backend):
    """不传分组时是建在本数据集上的空 Group：后续代码总是面对一个 Group，不用判断 None。"""
    plotter = DataPlotter(eis_dataset, backend=backend)
    assert isinstance(plotter.groups, Group)
    assert plotter.groups.names == []
    assert plotter.groups.dataset is eis_dataset


# ══════════════════════════════════════════════
# 同一个 Group、同一个入口，换后端：画出的东西一致
# ══════════════════════════════════════════════
@BACKENDS
@pytest.mark.parametrize("draw, keys, axes", [
    (lambda p: p.plot(), ['main'], {'left'}),
    (lambda p: p.plot(by='group'), ['A', 'B'], {'left'}),
    (lambda p: p.plot(Layer(ZS_RE, ZS_IM), by='sample'), [0, 1, 2], {'left'}),
    (lambda p: p.plot([Layer(0, 1), Layer(FREQ, ZS_IM, side='right')], by='sample'), [0, 1, 2], {'left', 'right'}),
], ids=['multiline', 'groups', 'xy', 'dual_y'])
def test_result_shape_is_uniform(eis_dataset, backend, draw, keys, axes):
    """
    两个后端、四种方法的结果同一形状：figures 的键是计划的 key；每张图（Plotly 是每页）是 DrawnFigure，
    线与 spec.curves 一一对应；axes 单轴图为 {'left'}，双 Y 轴图为 {'left', 'right'}。
    （2026-11-20 由 test_plotter / test_plotly_backend 各一条合并；Plotly 多页共用一个 Figure 见 test_pages_share_one_figure）
    """
    from plotlib.plot_spec import DrawnFigure

    plotter = draw(DataPlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()), backend=backend))
    assert plotter.backend.name == backend
    assert list(plotter.figures) == keys
    for key, drawn in plotter.figures.items():
        assert isinstance(drawn, DrawnFigure) and drawn.spec.key == key
        assert len(drawn.artists) == len(drawn.spec.curves)
        assert set(drawn.axes) == axes


@pytest.mark.parametrize("draw", [
    lambda p: p.plot(),
    lambda p: p.plot(by='group', merge_groups=True),
    lambda p: p.plot(by='group', merge_groups=False),
    lambda p: p.plot(Layer(ZS_RE, ZS_IM), by='sample'),
    lambda p: p.plot([Layer(0, 1), Layer(FREQ, ZS_IM, side='right')], by='sample'),
], ids=['objects', 'merge', 'separate', 'xy', 'dual_y'])
def test_same_figures_and_curves(eis_dataset, draw):
    """
    图的 key 相同，每张图（Plotly 是每页）的曲线条数、顺序、标签、数据相同（去重、先到先得等规则本身在 test_plot_plan.py）。
    按页比较，不比原生 Figure 的个数：多张计划时 matplotlib 是多张图，Plotly 是一个 Figure 多页（6.8）。
    """
    groups = Group(eis_dataset, overlap_config())
    mpl = draw(DataPlotter(eis_dataset, groups=groups, channel_x=FREQ, channel_y=ZS_RE))
    ply = draw(DataPlotter(eis_dataset, groups=groups, channel_x=FREQ, channel_y=ZS_RE,
                           backend='plotly'))

    assert list(ply.figures) == list(mpl.figures)
    for key, drawn in mpl.figures.items():
        assert_same_curves(ply.figures[key].artists, drawn.artists)


# ══════════════════════════════════════════════
# 按轴回调的作用范围
# 两个后端回调形状对应：axes (ax | 轴名, fig)、lines (这根轴的线)、legend (图例列表)
# ══════════════════════════════════════════════
@BACKENDS
def test_right_formatters_only_touch_right_axis(eis_dataset, backend):
    """
    只给右轴配范围和线色：右轴、右线变；左轴范围仍自动、左线仍是预设的红。
    回归：Plotly 的按轴回调曾都只收 fig，工厂改了全部 Y 轴和全部线（左右一起变成 -5~0、绿色）。
    """
    drawn = DataPlotter(eis_dataset, backend=backend).plot(
        [Layer(FREQ, ZS_RE), Layer(FREQ, ZS_IM, side='right')],
        by='sample',
        formatters={
            'right': AxesFormatter(axes=make_axes_formatter(y=AxisStyle(limits=(-5, 0)), backend=backend),
                                   lines=make_lines_formatter(LineStyle(color='green'), backend=backend)),
        },
    ).figures[0]
    left, right = drawn.artist(0), drawn.artist(0, 'right')

    if backend == 'matplotlib':
        assert drawn.axes['right'].get_ylim() == (-5, 0)
        low, high = drawn.axes['left'].get_ylim()
        assert low <= 10 and high >= 30                 # 左轴仍按自己的数据（Zs' 10~30）自动
        assert (left.get_color(), right.get_color()) == ('red', 'green')
    else:
        lay = drawn.fig.to_dict()['layout']
        assert lay['yaxis2']['range'] == [-5, 0]
        assert 'range' not in lay['yaxis']
        assert (left.line.color, right.line.color) == ('red', 'green')


@BACKENDS
def test_formatters_checked_before_drawing(eis_dataset, backend):
    """
    渲染前校验回调配置：轴名写错、给不存在的右轴配回调、给右轴配图例回调（一张图只有一个图例，归左轴），
    都明确报错，而且任何回调都还没执行、没有留下图窗。
    回归：轴名写错或单轴图配了右侧时曾静默忽略；右侧图例曾在左侧回调执行之后才报错。
    """
    import matplotlib.pyplot as plt

    calls = []
    left = AxesFormatter(axes=lambda *_args: calls.append('left axes'))
    single, dual = [Layer(0, 1)], [Layer(0, 1), Layer(FREQ, ZS_IM, side='right')]
    cases = [
        (single, {'left': left, 'rigth': AxesFormatter()}, "'left'、'right'"),
        (single, {'left': left, 'right': AxesFormatter(axes=lambda *_args: None)}, '右侧图层'),
        (dual, {'left': left, 'right': AxesFormatter(legend=make_legend_formatter(LegendStyle(font_size=8),
                                                                                  backend=backend))}, '左侧'),
    ]
    before = plt.get_fignums()
    for layers, formatters, message in cases:
        with pytest.raises(ValueError, match=message):
            DataPlotter(eis_dataset, backend=backend).plot(layers, by='sample', formatters=formatters)
    assert calls == [] and plt.get_fignums() == before


@BACKENDS
def test_axes_formatter_keeps_tick_width(eis_dataset, backend):
    """
    轴工厂没给 ticks 时不改刻度，仍是构造时的全局设置（DataPlotter(ticks=TickStyle(width=5))，原 tick_width 参数）。
    回归：两个工厂曾写死刻度宽 3。matplotlib 渲染后才确定全部刻度，所以先 draw 再看。
    """
    from plotlib.plot_spec import TickStyle

    log_x = make_axes_formatter(x=AxisStyle(scale='log'), backend=backend)
    drawn = DataPlotter(eis_dataset, ticks=TickStyle(width=5), backend=backend).plot(
        formatters=AxesFormatter(axes=log_x)).figures['main']

    if backend == 'matplotlib':
        drawn.fig.canvas.draw()
        ax = drawn.axes['left']
        ticks = ax.xaxis.get_major_ticks() + ax.yaxis.get_major_ticks()
        assert {t.tick1line.get_markeredgewidth() for t in ticks} == {5}
    else:
        lay = drawn.fig.to_dict()['layout']
        assert 'tickwidth' not in lay['xaxis'] and 'tickwidth' not in lay['yaxis']
        assert lay['template']['layout']['xaxis']['tickwidth'] == pytest.approx(5 * 100 / 72)


@BACKENDS
def test_axes_formatter_ticks_only_touch_its_axis(eis_dataset, backend):
    """
    单轴覆盖：右轴回调里的 ticks 只改右侧 Y 轴（主刻度长 12、关掉次刻度），左轴仍是全局默认（长 6、有次刻度）。
    Plotly 的磅按这张图的 dpi 换算（后端把 dpi 记在 fig.layout.meta 里，工厂画图时读）。
    """
    from plotlib.plot_spec import TickStyle

    right_ticks = make_axes_formatter(ticks=TickStyle(length=12, minor=False), backend=backend)
    drawn = DataPlotter(eis_dataset, dpi=200, backend=backend).plot(
        [Layer(0, 1), Layer(FREQ, ZS_IM, side='right')],
        by='sample',
        formatters={'right': AxesFormatter(axes=right_ticks)},
    ).figures[0]

    if backend == 'matplotlib':
        drawn.fig.canvas.draw()
        left, right = drawn.axes['left'].yaxis, drawn.axes['right'].yaxis
        assert {t.tick1line.get_markersize() for t in right.get_major_ticks()} == {12}
        assert list(right.get_minorticklocs()) == []
        assert {t.tick1line.get_markersize() for t in left.get_major_ticks()} == {6}
        assert list(left.get_minorticklocs())
    else:
        lay = drawn.fig.to_dict()['layout']
        assert lay['yaxis2']['ticklen'] == pytest.approx(12 * 200 / 72)
        assert lay['yaxis2']['minor']['ticks'] == ''
        assert 'ticklen' not in lay['yaxis'] and 'ticklen' not in lay['xaxis']


@BACKENDS
def test_combine_formatters_same_kind(eis_dataset, backend):
    """combine_formatters 合并同一种回调（两个后端通用）：依次调用、跳过 None、参数原样转交。"""
    counts = []
    fmt = combine_formatters(make_lines_formatter(LineStyle(width=5), backend=backend), None,
                             lambda lines: counts.append(len(lines)))
    drawn = DataPlotter(eis_dataset, backend=backend).plot(formatters=AxesFormatter(lines=fmt)).figures['main']

    # 线宽 5 磅：matplotlib 就是 5，Plotly 按 dpi 100 换成像素（样式对象化起两个后端都用磅）
    widths = [a.get_linewidth() if backend == 'matplotlib' else a.line.width for a in drawn.artists]
    assert widths == pytest.approx([5 if backend == 'matplotlib' else 5 * 100 / 72] * 3)
    assert counts == [3]


@BACKENDS
def test_group_marker_applies_to_scatter(eis_dataset, backend):
    """散点图应用所属分组的标记样式。"""
    groups = Group(eis_dataset, {'A': {'num': [0, 1], 'marker': 'square'}})
    artist = DataPlotter(eis_dataset, groups=groups, backend=backend).plot(
        Layer(kind='scatter'),
        by='group',
    ).figures['A'].artist(0)

    if backend == 'matplotlib':
        from matplotlib.markers import MarkerStyle
        square = MarkerStyle('s')
        expected = square.get_path().transformed(square.get_transform())
        np.testing.assert_allclose(np.asarray(artist.get_paths()[0].vertices), np.asarray(expected.vertices))
    else:
        assert artist.marker.symbol == 'square'
        assert artist.mode == 'markers'                 # 散点不因为写了 marker 变成「线 + 点」


@BACKENDS
def test_scatter_follows_group_rules(eis_dataset, backend):
    """
    散点图层与折线共用分组规则（4.3）：by='all' 画全部样品；by='group' 时分离模式每组一张图，
    合并模式一张图、重复样品只画一次。画出来的是散点（不是线），数据、标签与计划一致。
    """
    def points(artist):
        if backend == 'matplotlib':
            from matplotlib.collections import PathCollection
            assert isinstance(artist, PathCollection)
            x, y = np.asarray(artist.get_offsets()).T
            return x.tolist(), y.tolist(), artist.get_label()
        assert artist.mode == 'markers'
        return list(artist.x), list(artist.y), artist.name

    plotter = DataPlotter(eis_dataset, channel_x=FREQ, channel_y=ZS_RE, backend=backend)
    assert [points(a) for a in plotter.plot(Layer(kind='scatter')).figures['main'].artists] == \
        [([1, 10, 100], [10 * k, 20 * k, 30 * k], f'S{k - 1}') for k in (1, 2, 3)]

    grouped = DataPlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()), backend=backend)
    assert list(grouped.plot(Layer(kind='scatter'), by='group').figures) == ['A', 'B']
    merged = grouped.plot(Layer(kind='scatter'), by='group', merge_groups=True).figures['main']
    assert [points(a)[2] for a in merged.artists] == ['S0', 'S1', 'S2']


@BACKENDS
def test_line_and_scatter_formatters_are_separate(eis_dataset, backend):
    """
    线条和散点回调分别作用于对应的绘图对象。双 Y 轴左边折线、右边散点：
    左轴的线条回调改了线宽；右轴的线条回调（绿色）碰不到右边的散点，散点仍是预设的蓝。
    散点图层的散点回调改散点的颜色和大小。
    """
    from plotlib.formatters import make_scatter_formatter
    from plotlib.plot_spec import ScatterStyle

    drawn = DataPlotter(eis_dataset, backend=backend).plot(
        [Layer(FREQ, ZS_RE), Layer(FREQ, ZS_IM, kind='scatter', side='right')],
        by='sample',
        formatters={
            'left': AxesFormatter(lines=make_lines_formatter(LineStyle(width=4), backend=backend)),
            'right': AxesFormatter(lines=make_lines_formatter(LineStyle(color='green'), backend=backend)),
        },
    ).figures[0]
    line, dots = drawn.artist(0), drawn.artist(0, 'right')
    scatter = DataPlotter(eis_dataset, backend=backend).plot(
        Layer(kind='scatter'),
        formatters=AxesFormatter(scatter=make_scatter_formatter(ScatterStyle(color='black', size=9), backend=backend)),
    ).figures['main'].artist(0)

    if backend == 'matplotlib':
        from matplotlib.colors import to_rgba
        assert line.get_linewidth() == 4
        assert tuple(dots.get_facecolor()[0]) == to_rgba('blue')
        assert (tuple(scatter.get_facecolor()[0]), scatter.get_sizes().tolist()) == (to_rgba('black'), [81])
    else:
        assert line.line.width == pytest.approx(4 * 100 / 72)
        assert (dots.mode, dots.marker.color) == ('markers', 'blue')
        assert (scatter.marker.color, scatter.marker.size) == ('black', pytest.approx(9 * 100 / 72))


@BACKENDS
def test_layers_and_formatter_scope(eis_dataset, backend):
    """
    按样品绘制多个图层时，每页 artists 的顺序与 layers 一致，artist(样品号, 轴) 是这根轴上的第一层；
    线条、散点回调只收到对应轴、对应画法的对象；X 轴两侧共用，右侧坐标轴回调改 X 也作用在它上面。
    """
    from plotlib.formatters import make_axes_formatter

    received: dict[str, list] = {}

    def record(name):
        return lambda objects, *_args: received.setdefault(name, []).extend(objects)

    layers = [Layer(FREQ, ZS_RE, kind='scatter'), Layer(FREQ, ZS_RE), Layer(FREQ, ZS_IM, side='right')]
    formatters = {'left': AxesFormatter(lines=record('left lines'), scatter=record('left scatter')),
                  'right': AxesFormatter(axes=make_axes_formatter(x=AxisStyle(limits=(2, 50)), backend=backend),
                                         lines=record('right lines'), scatter=record('right scatter'))}
    pages = DataPlotter(eis_dataset, backend=backend).plot(layers, by='sample', formatters=formatters).figures

    assert list(pages) == [0, 1, 2]
    for k, page in pages.items():
        assert isinstance(k, int)
        dots, line, right = page.artists
        assert page.artist(k) is dots and page.artist(k, 'right') is right
        if backend == 'matplotlib':
            from matplotlib.collections import PathCollection
            from matplotlib.lines import Line2D
            assert (type(dots), type(line), type(right)) == (PathCollection, Line2D, Line2D)
            assert page.axes['left'].get_xlim() == (2, 50)
        else:
            assert (dots.mode, line.mode, right.mode) == ('markers', 'lines', 'lines')
            assert tuple(page.fig.layout.xaxis.range) == (2, 50)

    ids = lambda objects: sorted(map(id, objects))          # noqa: E731
    assert ids(received['left scatter']) == ids(p.artists[0] for p in pages.values())
    assert ids(received['left lines']) == ids(p.artists[1] for p in pages.values())
    assert ids(received['right lines']) == ids(p.artists[2] for p in pages.values())
    assert received.get('right scatter', []) == []          # 右侧没有散点：收到空列表（或不调用）


@BACKENDS
def test_scatter_defaults_and_hollow(eis_dataset, backend):
    """
    散点按库默认 DEFAULT_SCATTER 画（大小 6 磅、描边 1 磅），不受全局折线样式影响；
    散点回调写 filled=False 变成空心：填充透明，描边保留原来的颜色。
    回归（复审）：LineStyle(marker_size=24) 曾让默认散点直径变成 4 倍，matplotlib 里 LineStyle.width 还会改 x 形散点的笔画。
    """
    from plotlib.formatters import make_scatter_formatter
    from plotlib.plot_spec import ScatterStyle

    plotter = DataPlotter(eis_dataset, backend=backend, lines=LineStyle(width=5, marker_size=24))
    plain = plotter.plot(Layer(kind='scatter')).figures['main'].artist(0)
    hollow = plotter.plot(
        Layer(kind='scatter'),
        formatters=AxesFormatter(scatter=make_scatter_formatter(ScatterStyle(filled=False), backend=backend)),
    ).figures['main'].artist(0)

    if backend == 'matplotlib':
        assert (plain.get_sizes().tolist(), plain.get_linewidths().tolist()) == ([36], [1])
        face = hollow.get_facecolor()
        assert len(face) == 0 or face[0][3] == 0                                 # 填充透明（'none' 读回来是空数组）
        np.testing.assert_allclose(hollow.get_edgecolor()[0], plain.get_facecolor()[0])
    else:
        px = 100 / 72
        assert (plain.marker.size, plain.marker.line.width) == (pytest.approx(6 * px), pytest.approx(px))
        assert (hollow.marker.color, hollow.marker.line.color) == ('rgba(0,0,0,0)', plain.marker.color)


@BACKENDS
def test_scatter_refill_and_line_markers(eis_dataset, backend):
    """
    回归（复审）：
    1. 先 filled=False 再 filled=True（没写 color）要恢复成画图时的填充色，单独写的描边色不变；
    2. matplotlib 的 'x'、'cross' 是线形标记，不能传 edgecolors，否则警告；开启「警告即错误」也要能画，空心时也看得见。
    """
    import warnings

    from matplotlib.colors import to_rgba

    from plotlib.formatters import combine_formatters, make_scatter_formatter
    from plotlib.plot_spec import ScatterStyle

    plotter = DataPlotter(eis_dataset, backend=backend)
    plain = plotter.plot(Layer(kind='scatter')).figures['main'].artist(0)
    fmt = lambda style: make_scatter_formatter(style, backend=backend)      # noqa: E731
    refill = combine_formatters(fmt(ScatterStyle(filled=False, edge_color='black')), fmt(ScatterStyle(filled=True)))
    points = plotter.plot(Layer(kind='scatter'), formatters=AxesFormatter(scatter=refill)).figures['main'].artist(0)
    if backend == 'matplotlib':
        np.testing.assert_allclose(points.get_facecolor()[0], plain.get_facecolor()[0])
        np.testing.assert_allclose(points.get_edgecolor()[0], (0, 0, 0, 1))
    else:
        assert (points.marker.color, points.marker.line.color) == (plain.marker.color, 'black')

    # 原生回调改的填充色也要记住：之后写 filled=True 不能把它换回画图时的颜色（先转空心再转实心也一样）
    red = make_scatter_formatter(custom=[
        (lambda p: p.set_facecolor('red')) if backend == 'matplotlib' else (lambda t: t.update(marker_color='red'))],
        backend=backend)
    for chain in ([red, fmt(ScatterStyle(filled=True))],
                  [red, fmt(ScatterStyle(filled=False)), fmt(ScatterStyle(filled=True))]):
        points = plotter.plot(
            Layer(kind='scatter'),
            formatters=AxesFormatter(scatter=combine_formatters(*chain)),
        ).figures['main'].artist(0)
        if backend == 'matplotlib':
            np.testing.assert_allclose(points.get_facecolor()[0], (1, 0, 0, 1))
        else:
            assert points.marker.color == 'red'

    # 逐点颜色：原生回调写的颜色数组也要整组记住；Plotly 的 marker.color 是数组时其他回调也不能出错
    colors = ['red', 'blue', 'green']
    per_point = make_scatter_formatter(custom=[
        (lambda p: p.set_facecolor(colors)) if backend == 'matplotlib'
        else (lambda t: t.update(marker_color=np.array(colors)))], backend=backend)
    chain = [per_point, fmt(ScatterStyle(filled=False)), fmt(ScatterStyle(filled=True)), fmt(ScatterStyle(alpha=0.5))]
    points = plotter.plot(
        Layer(kind='scatter'),
        formatters=AxesFormatter(scatter=combine_formatters(*chain)),
    ).figures['main'].artist(0)
    if backend == 'matplotlib':
        np.testing.assert_allclose(points.get_facecolor()[:, :3], [to_rgba(c)[:3] for c in colors])
    else:
        assert list(points.marker.color) == colors

    for marker in ('x', 'cross'):
        grouped = DataPlotter(eis_dataset, groups=Group(eis_dataset, {'A': {'num': [0], 'marker': marker}}),
                              backend=backend)
        for filled in (True, False):
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                points = grouped.plot(
                    Layer(kind='scatter'),
                    by='group',
                    formatters=AxesFormatter(scatter=fmt(ScatterStyle(filled=filled))),
                ).figures['A'].artist(0)
            if backend == 'matplotlib':                                     # 线形标记靠描边显示
                assert np.asarray(points.get_edgecolor()).shape == (1, 4) and points.get_edgecolor()[0][3] == 1


# ══════════════════════════════════════════════
# 检查两个后端是否显示计划中的图例标题。
# ══════════════════════════════════════════════
@BACKENDS
@pytest.mark.parametrize("draw, expected", [
    (lambda p: p.plot(), {'main': None}),
    (lambda p: p.plot(legend_title='Samples'), {'main': 'Samples'}),
    (lambda p: p.plot(by='group', legend_title='Group {name}'), {'A': 'Group A', 'B': 'Group B'}),
    (lambda p: p.plot(by='sample', legend_title='{name}'), {0: 'S0', 1: 'S1', 2: 'S2'}),
    (lambda p: p.plot([Layer(0, 1), Layer(FREQ, ZS_IM, side='right')], by='sample'), {0: 'S0', 1: 'S1', 2: 'S2'}),
    (lambda p: p.plot(
        [Layer(0, 1), Layer(FREQ, ZS_IM, side='right')],
        by='sample',
        legend_title=None,
    ), {0: None, 1: None, 2: None}),
], ids=['multiline_default', 'multiline_text', 'groups_name', 'xy_name', 'dual_y_default', 'dual_y_none'])
def test_legend_title_drawn(eis_dataset, backend, draw, expected):
    """
    每张图（Plotly 是每页）的图例标题就是计划写的；没有就不画。
    Plotly 多页共用一个图例：第一页的标题画完就在，其余页的在翻到那一页时换上（读翻页滑块每一档改的图例标题）。
    """
    plotter = draw(DataPlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()), backend=backend))

    if backend == 'matplotlib':
        titles = [drawn.axes['left'].get_legend().get_title().get_text() or None
                  for drawn in plotter.figures.values()]
    elif len(plotter.figures) == 1:
        [drawn] = plotter.figures.values()
        titles = [drawn.fig.layout.legend.title.text]
    else:
        steps = plotter.add_page_slider().layout.sliders[0].steps
        titles = [step.args[1]['legend.title.text'] or None for step in steps]

    assert dict(zip(plotter.figures, titles)) == expected


@BACKENDS
def test_legend_lists_every_curve(eis_dataset, backend):
    """
    图例按计划里的曲线显式生成，一条一项、一项不漏（2026-11-25）：样品名以 '_' 开头或为空时 matplotlib 自动收集会跳过它；
    只有一条曲线时 Plotly 默认不显示图例（写了 legend_title 也看不到）。双 Y 轴先左后右。
    """
    eis_dataset.names[0:3] = ['_S0'] * 3
    eis_dataset.names[3:6] = [''] * 3
    plotter = DataPlotter(eis_dataset, backend=backend)
    left, right = EIS_UNITS[ZS_RE], EIS_UNITS[ZS_IM]
    dual = [Layer(FREQ, ZS_IM, side='right'), Layer(FREQ, ZS_RE)]   # 右侧图层写在前面
    # 期望的图例条目：(matplotlib, Plotly)。双 Y 轴 matplotlib 先左后右，Plotly 按绘制顺序（见 FigureSpec.curves）
    cases = [(lambda: plotter.plot(), (['_S0', '', 'S2'],) * 2),
             (lambda: plotter.plot(by='sample', legend_title='T'), (['_S0'],) * 2),
             (lambda: plotter.plot(dual, by='sample'), ([left, right], [right, left]))]
    for draw, (in_matplotlib, in_plotly) in cases:
        drawn = next(iter(draw().figures.values()))
        if backend == 'matplotlib':
            assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == in_matplotlib
        else:
            assert drawn.fig.layout.showlegend is True
            assert [trace.name for trace in drawn.artists] == in_plotly

    # matplotlib 的惯例照旧（与 adca55c 一致）：回调把名字改成 '_' 开头（如 '_nolegend_'）就不进图例；
    # 坐标轴回调另加的带标签对象（参考线）在回调后重建图例时收进来，排在计划的曲线之后
    if backend == 'matplotlib':
        def add_reference(ax, fig):
            ax.axhline(0, label='ref')

        # 回调把标签设成 None（matplotlib 接受的值）也不列，与旧版一致；不能因为它重建图例时出错
        for hidden in ('_nolegend_', None):
            hide_first = make_lines_formatter(
                custom=[lambda line, hidden=hidden: line.get_label() == '_S0' and line.set_label(hidden)])
            drawn = plotter.plot(formatters=AxesFormatter(axes=add_reference, lines=hide_first)).figures['main']
            assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == ['', 'S2', 'ref']

    # 线条回调改了曲线名，图例跟着改（matplotlib 重建图例时读对象当前的标签）
    rename = make_lines_formatter(custom=[(lambda line: line.set_label('X')) if backend == 'matplotlib'
                                          else (lambda trace: trace.update(name='X'))], backend=backend)
    drawn = plotter.plot(formatters=AxesFormatter(lines=rename)).figures['main']
    if backend == 'matplotlib':
        assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == ['X'] * 3
    else:
        assert [trace.name for trace in drawn.artists] == ['X'] * 3


# ══════════════════════════════════════════════
# 55576fb 复审的回归（2026-11-20）
# ══════════════════════════════════════════════
@BACKENDS
def test_numeric_sample_names(make_dataset, backend):
    """
    数字样品名（复审 1）：真实 CSV 读进来的 '101'、'102'，双 Y 轴的图例标题就是它们；
    Plotly 翻页滑块、曲线滑块的档位标签也是它们。回归：样品名曾读成 101.0，替换 '{name}'、取标签长度都报 TypeError。
    """
    rows = [[1, 10, -1], [10, 20, -2]]
    ds = make_dataset(EIS_UNITS, {'101': rows, '102': rows})
    plotter = DataPlotter(ds, backend=backend).plot([Layer(0, 1), Layer(FREQ, ZS_IM, side='right')], by='sample')

    if backend == 'matplotlib':
        titles = [drawn.axes['left'].get_legend().get_title().get_text() for drawn in plotter.figures.values()]
    else:
        steps = plotter.add_page_slider().layout.sliders[0].steps
        titles = [step.args[1]['legend.title.text'] for step in steps]
        assert [step.label for step in steps] == ['101', '102']
        curve_steps = DataPlotter(ds, backend=backend).plot().add_slider().layout.sliders[0].steps
        assert [step.label for step in curve_steps] == ['101', '102']
    assert titles == ['101', '102']


@BACKENDS
def test_global_marker(eis_dataset, backend):
    """
    DataPlotter 全局的 marker（复审 2）：折线都带这个标记（Plotly 改成「线 + 点」）；分组写的 marker 盖过全局；
    散点不受影响，仍是圆点（matplotlib 的全局 lines.marker 本来就不管 scatter）。
    回归：Plotly 建模板时重复传 marker_symbol，绘图器建不起来；修好后折线仍是纯线，不显示标记。
    """
    groups = Group(eis_dataset, {'A': {'num': [0], 'marker': 'square'}, 'B': {'num': [1, 2]}})
    plotter = DataPlotter(eis_dataset, groups=groups, backend=backend, lines=LineStyle(marker='diamond'))

    lines = plotter.plot().figures['main'].artists
    grouped = plotter.plot(by='group', merge_groups=True).figures['main']
    scatter = DataPlotter(eis_dataset, backend=backend, lines=LineStyle(marker='diamond')).plot(
        Layer(kind='scatter'),
    ).figures['main'].artist(0)
    if backend == 'matplotlib':
        from matplotlib.markers import MarkerStyle
        assert [line.get_marker() for line in lines] == ['D'] * 3
        assert [grouped.artist(k).get_marker() for k in (0, 1)] == ['s', 'D']
        circle = MarkerStyle('o')
        expected = circle.get_path().transformed(circle.get_transform())
        np.testing.assert_allclose(np.asarray(scatter.get_paths()[0].vertices), np.asarray(expected.vertices))
    else:
        assert [(t.mode, t.marker.symbol) for t in lines] == [('lines+markers', 'diamond')] * 3
        assert [grouped.artist(k).marker.symbol for k in (0, 1)] == ['square', 'diamond']
        # 散点按库默认 DEFAULT_SCATTER 明确写圆点，不靠模板（复审：全局折线样式不能漏到散点上）
        assert (scatter.mode, scatter.marker.symbol) == ('markers', 'circle')


@BACKENDS
def test_backend_rejects_unknown_layout_and_kind(backend):
    """两个后端均拒绝无效的版式和画法。"""
    from plotlib.backends import get_backend
    from plotlib.plot_spec import Appearance, CurveBase, FigureSpec, LineSpec

    drawer = get_backend(backend, Appearance(), None)
    line = LineSpec(sample_idx=0, x=np.array([0, 1]), y=np.array([0, 1]), label='S0',
                    group_name=None, color_position=None)

    with pytest.raises(ValueError, match='版式'):
        drawer.draw(FigureSpec(key='k', x_unit='', y_unit='', curves=[line],
                               layout='pie'), figsize=(4, 3))  # pyright: ignore[reportArgumentType]  故意写错
    with pytest.raises(ValueError, match='画法'):                # 不认识的 spec 类型
        unknown = CurveBase(label='S0', group_name=None, color_position=None)
        drawer.draw(FigureSpec(key='k', x_unit='', y_unit='', curves=[unknown]), figsize=(4, 3))  # pyright: ignore[reportArgumentType]  故意传基类
