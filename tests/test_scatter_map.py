"""
验证散点第三通道映射（ScatterMap）和颜色条（ColorbarStyle）在两个后端的画法、回调和结果。

计划层（范围、直径、去掉 NaN 点、入口校验）由 test_plot_plan.py 验证，这里核对后端照着计划画：
- 颜色：matplotlib 各样品共用一个 norm，Plotly 各 trace 指向共享的 coloraxis；描边跟随填充的逐点颜色；
- 大小：matplotlib 的 s 是直径²，Plotly 的 size 是直径换成像素；
- 对数色标：matplotlib 用 LogNorm；Plotly 按 log10 着色、颜色条刻度写成 10 的幂、悬停显示原值；
- 颜色条不压右 Y 轴和图例（Kaleido 实际渲染成 SVG 后按像素核对）。

数据见 conftest 的 map_data：同时映射大小（通道 2）和颜色（通道 3）时，样品 0 画 1 个点（颜色 3、直径 16），
样品 3 画 2 个点（颜色 1、2，直径 4、√136），颜色范围 (1, 3)。
"""
import re
import warnings

import matplotlib.pyplot as plt
import numpy as np
import plotly.colors as plyc
import pytest
from conftest import map_data
from matplotlib.colorbar import Colorbar
from matplotlib.colors import LogNorm, Normalize, to_rgba

from plotlib.dataset import DataSet
from plotlib.formatters import combine_formatters, make_legend_formatter, make_scatter_formatter
from plotlib.group import Group
from plotlib.plot_spec import AxesFormatter, ColorbarStyle, Layer, LegendStyle, ScatterMap, ScatterStyle
from plotlib.plotter import DataPlotter
from plotlib.style import Backend

BACKENDS: tuple[Backend, ...] = ('matplotlib', 'plotly')
PX = 100 / 72           # dpi 100 时 1 磅的像素数
SIZE, COLOR = 2, 3      # map_data 的大小通道、颜色通道
BOTH = Layer(kind='scatter', mapping=ScatterMap(size=SIZE, color=COLOR))
# 每个样品（按样品号排序）画出的点：颜色值、直径（磅）
COLORS = [[3], [1, 2]]
DIAMETERS = [[16], [4, np.sqrt(136)]]


def plotter(backend: Backend, data: DataSet | None = None) -> DataPlotter:
    return DataPlotter(map_data() if data is None else data, channel_x=0, channel_y=1, backend=backend)


def mpl_faces(points) -> np.ndarray:
    """matplotlib 的逐点填充色：颜色映射在绘制时才算出，先画一次再读。"""
    points.figure.canvas.draw()
    return points.get_facecolor()


def plotly_svg(fig) -> str:
    """用 Kaleido 把 Plotly 图渲染成 SVG 文本。"""
    pytest.importorskip('kaleido')
    with warnings.catch_warnings():
        # 别的测试已启动常驻的 Kaleido 服务（conftest 的 render）时，Plotly 提示渲染参数被忽略；不影响结果
        warnings.filterwarnings('ignore', message='The kopts argument is ignored', category=UserWarning)
        return fig.to_image(format='svg').decode()


def svg_right_side(fig) -> tuple[float, float, float | None]:
    """
    用 Kaleido 把 Plotly 图渲染成 SVG，取出右侧几样东西的位置（像素）：
    ``(色条左边缘, 图例右边缘, 右 Y 轴标题的右边缘)``；标题旋转 90°，x 是中心，加半个字号；没有右轴时为 None。
    色条取渐变色块本身（``cbfill``），不取颜色条的背景框：背景框包含 ``xpad`` 留出的空白。
    """
    svg = plotly_svg(fig)
    colorbar = re.search(r'class="cbcoloraxis colorbar" transform="translate\(([-\d.]+),', svg)
    background = re.search(r'class="cbfill[^"]*"[^>]*? x="([-\d.]+)"', svg)
    legend = re.search(r'<g class="legend"[^>]*transform="translate\(([-\d.]+),[^"]*"[^>]*>'
                       r'<rect class="bg"[^>]*?width="([\d.]+)"', svg)
    title = re.search(r'class="y2title"[^>]*? x="([-\d.]+)"[^>]*?font-size: ([\d.]+)px', svg)
    assert colorbar and background and legend
    return (float(colorbar[1]) + float(background[1]), float(legend[1]) + float(legend[2]),
            float(title[1]) + float(title[2]) / 2 if title else None)


# ══════════════════════════════════════════════
# 3. 两个后端照着计划画
# ══════════════════════════════════════════════
def test_scatter_map_backends():
    """
    颜色：matplotlib 各点颜色 = cmap(norm(值))，各样品共用同一个 norm，描边跟随填充；
    Plotly 各 trace 的 marker 和描边都指向共享的 coloraxis，色带、cmin / cmax、颜色条标题照计划，悬停显示原值。
    大小：matplotlib s = 直径²，Plotly size = 直径 × dpi / 72。
    对数色标：matplotlib 用 LogNorm；Plotly 按 log10 着色，颜色条刻度在整数次幂处、写成 10 的幂。
    颜色值全部相同又没写 limits 时，两个后端都画成色带中间的颜色。
    """
    viridis = plt.get_cmap('viridis')

    # matplotlib
    drawn = plotter('matplotlib').plot(BOTH).figures['main']
    colorbar = drawn.axes['colorbar']
    assert (colorbar.norm.vmin, colorbar.norm.vmax) == (1, 3)
    assert (colorbar.cmap.name, colorbar.ax.get_ylabel()) == ('viridis', 'T(K)')
    for points, values, diameters in zip(drawn.artists, COLORS, DIAMETERS):
        assert points.norm is colorbar.norm                                     # 各样品共用一个 norm
        expected = viridis(Normalize(1, 3)(values))
        np.testing.assert_allclose(mpl_faces(points), expected)
        np.testing.assert_allclose(points.get_edgecolor(), expected)            # 描边跟随填充
        np.testing.assert_allclose(points.get_sizes(), np.square(diameters))

    # Plotly
    fig = plotter('plotly').plot(BOTH).figures['main'].fig
    axis = fig.layout.coloraxis
    assert (axis.cmin, axis.cmax, axis.colorbar.title.text) == (1, 3, 'T(K)')
    assert [(round(at, 9), hue) for at, hue in axis.colorscale] == \
        [(round(at, 9), hue) for at, hue in plyc.get_colorscale('Viridis')]
    for trace, values, diameters in zip(fig.data, COLORS, DIAMETERS):
        assert (trace.marker.coloraxis, trace.marker.line.coloraxis) == ('coloraxis', 'coloraxis')
        assert list(trace.marker.color) == list(trace.marker.line.color) == values
        assert list(trace.marker.size) == pytest.approx([d * PX for d in diameters])
        assert np.ravel(trace.customdata).tolist() == values and '%{customdata' in trace.hovertemplate

    # 对数色标：颜色 [1, 10, 1000]
    decades = DataSet().form_array(np.array([[1, 1, 1], [2, 2, 10], [3, 3, 1000]]), ['S0'] * 3,
                                   ['x', 'y', 'f(Hz)'], 0, repeat_times=3)
    log = Layer(kind='scatter', mapping=ScatterMap(color=2))
    drawn = plotter('matplotlib', decades).plot(log, colorbar=ColorbarStyle(scale='log')).figures['main']
    assert isinstance(drawn.axes['colorbar'].norm, LogNorm)
    np.testing.assert_allclose(mpl_faces(drawn.artists[0]), viridis([0, 1 / 3, 1]))
    fig = plotter('plotly', decades).plot(log, colorbar=ColorbarStyle(scale='log')).figures['main'].fig
    axis, trace = fig.layout.coloraxis, fig.data[0]
    assert (axis.cmin, axis.cmax) == pytest.approx((0, 3))
    assert list(trace.marker.color) == pytest.approx([0, 1, 3])
    assert list(axis.colorbar.tickvals) == [0, 1, 2, 3]
    assert list(axis.colorbar.ticktext) == [f'10<sup>{n}</sup>' for n in range(4)]
    assert np.ravel(trace.customdata).tolist() == [1, 10, 1000]                 # 悬停显示原值，不是 log10

    # 颜色值全部相同：都画成中间色
    flat = DataSet().form_array(np.array([[1, 1, 5], [2, 2, 5]]), ['S0'] * 3, ['x', 'y', 'T(K)'], 0, repeat_times=3)
    same = Layer(kind='scatter', mapping=ScatterMap(color=2))
    points = plotter('matplotlib', flat).plot(same).figures['main'].artists[0]
    np.testing.assert_allclose(mpl_faces(points), viridis([0.5, 0.5]))
    axis = plotter('plotly', flat).plot(same).figures['main'].fig.layout.coloraxis
    assert axis.cmin < axis.cmax and (axis.cmin + axis.cmax) / 2 == pytest.approx(5)

    # 极端数据配手动 limits：超出范围的点取端点颜色，matplotlib 绘制时不发溢出警告（复验：norm 不截断时会溢出）
    extreme = DataSet().form_array(np.array([[1, 1, -1.5e308], [2, 2, 0], [3, 3, 1.5e308]]), ['S0'] * 3,
                                   ['x', 'y', 'T(K)'], 0, repeat_times=3)
    points = plotter('matplotlib', extreme).plot(
        Layer(kind='scatter', mapping=ScatterMap(color=2)), colorbar=ColorbarStyle(limits=(-1, 1))).figures['main'].artists[0]
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        np.testing.assert_allclose(mpl_faces(points), viridis([0, 0.5, 1]))

    # 颜色条标题写 '' 时，悬停仍用颜色通道的列标题标明数值（复审：曾显示无标签的「: 数值」）
    trace = plotter('plotly').plot(BOTH, colorbar=ColorbarStyle(title='')).figures['main'].fig.data[0]
    assert 'T(K): %{customdata' in trace.hovertemplate
    # 列标题和颜色条标题都是空的：只显示数值，不留一个孤零零的冒号
    untitled = map_data()
    untitled.units = ['x(mm)', 'y(mm)', 'E(%)', ''] * 2
    trace = plotter('plotly', untitled).plot(BOTH, colorbar=ColorbarStyle(title='')).figures['main'].fig.data[0]
    assert '<br>%{customdata' in trace.hovertemplate and ': %{customdata' not in trace.hovertemplate


def test_scatter_map_colorbar_placement():
    """
    颜色条不压住右 Y 轴和图例：单 Y 轴（多线版式的图例在图外右侧，正是颜色条默认的位置）和
    双 Y 轴（颜色映射在左侧、右侧另有图层）都核对。
    matplotlib 先画一次再比较边界框；Plotly 用 Kaleido 实际渲染（默认位置会和图例、右轴刻度、标题重叠）。

    复审补充的场景：
    - Plotly 的图例回调放大字号、或把图例移到图外右侧：颜色条的间距要按回调之后的图例算；
    - matplotlib 的整图回调调用 ``fig.tight_layout()`` （脚本里常见）：小图、双 Y 轴都不能重叠，颜色条不出界；
    - 右侧内容放不下（6×4 英寸加 28 磅图例）：绘图区宽度有下限，不会算成负数。
    """
    color = Layer(0, 1, kind='scatter', mapping=ScatterMap(color=COLOR))
    right = Layer(0, SIZE, side='right')

    def mpl_check(drawn, packed: bool):
        """颜色条不压右侧的东西；*packed*：没有别的布局时，颜色条靠到图的右边、间距不浪费。"""
        drawn.fig.canvas.draw()
        renderer = drawn.fig.canvas.get_renderer()
        colorbar_left = drawn.axes['colorbar'].ax.get_window_extent(renderer).x0
        edges = [drawn.axes['left'].get_legend().get_window_extent(renderer).x1]
        if 'right' in drawn.axes:
            edges.append(drawn.axes['right'].get_tightbbox(renderer).x1)
            # 双 Y 轴的两根轴共用位置（只缩一次）
            assert drawn.axes['right'].get_position().bounds == drawn.axes['left'].get_position().bounds
        assert max(edges) <= colorbar_left
        assert colorbar_left - max(edges) < 0.05 * drawn.fig.bbox.width      # 让开但不浪费：间距不超过图宽的 5%
        # 颜色条（含刻度文字和标题）不出界；没有别的布局时靠到图的右边（多线版式给图外图例预留的 25% 右边距不空着）
        spare = drawn.fig.bbox.width - drawn.axes['colorbar'].ax.get_tightbbox(renderer).x1
        assert spare >= 0 and (not packed or spare < 0.05 * drawn.fig.bbox.width)

    def tight(fig, axes):
        fig.tight_layout()

    mpl_check(plotter('matplotlib').plot(color).figures['main'], packed=True)
    mpl_check(plotter('matplotlib').plot([color, right], by='sample').figures[3], packed=True)
    small = DataPlotter(map_data(), channel_x=0, channel_y=1, figsize=(6, 4))
    mpl_check(small.plot(color, figure_formatter=tight).figures['main'], packed=False)
    mpl_check(plotter('matplotlib').plot([color, right], by='sample', figure_formatter=tight).figures[3], packed=False)

    # 回调把右轴隐藏（复验：隐藏轴的 get_tightbbox() 是 None，定位器曾报错）：右轴回调里、整图回调里都能画
    def hide(ax, fig):
        ax.set_visible(False)

    hidden = plotter('matplotlib').plot([color, right], by='sample',
                                        formatters={'right': AxesFormatter(axes=hide)}).figures[3]
    hidden.fig.canvas.draw()
    hidden = plotter('matplotlib').plot([color, right], by='sample',
                                        figure_formatter=lambda fig, axes: axes['right'].set_visible(False)).figures[3]
    hidden.fig.canvas.draw()

    # 放不下：绘图区宽度不小于图宽的 25%（颜色条可以出界，但图还在）
    crowded = DataPlotter(map_data(), channel_x=0, channel_y=1, figsize=(6, 4), legend=LegendStyle(font_size=28))
    drawn = crowded.plot(color).figures['main']
    drawn.fig.canvas.draw()
    assert drawn.axes['left'].get_window_extent(drawn.fig.canvas.get_renderer()).width >= 0.25 * drawn.fig.bbox.width

    colorbar_left, legend_right, _ = svg_right_side(plotter('plotly').plot(color).figures['main'].fig)
    assert legend_right <= colorbar_left
    colorbar_left, legend_right, y2_right = svg_right_side(
        plotter('plotly').plot([color, right], by='sample').figures[3].fig)
    assert y2_right is not None and y2_right <= colorbar_left
    assert legend_right <= colorbar_left

    # Plotly 的图例回调：长样品名 + 16 磅字号；双 Y 轴把图例移到图外右侧
    named = map_data()
    named.names = ['Control sample'] * 4 + ['Treatment sample'] * 4
    bigger = AxesFormatter(legend=make_legend_formatter(LegendStyle(font_size=16), backend='plotly'))
    fig = plotter('plotly', named).plot(color, formatters=bigger).figures['main'].fig
    colorbar_left, legend_right, _ = svg_right_side(fig)
    assert legend_right <= colorbar_left
    moved = AxesFormatter(legend=make_legend_formatter(LegendStyle(position='outside right'), backend='plotly'))
    fig = plotter('plotly', named).plot([color, right], by='sample', formatters=moved).figures[3].fig
    colorbar_left, legend_right, y2_right = svg_right_side(fig)
    assert legend_right <= colorbar_left and y2_right is not None and y2_right <= colorbar_left

    # Plotly 翻页：图例标题按页换成组名（复验：只按第一页的短标题估算，翻到长组名那页图例越过色条 222 像素）
    data = map_data()
    long_name = 'Thermally conditioned sample batch'
    groups = Group(data, {'A': {'num': [3]}, long_name: {'num': [0]}})
    figures = DataPlotter(data, groups=groups, channel_x=0, channel_y=1, backend='plotly').plot(
        color, by='group', legend_title='{name}').figures
    fig = figures['A'].fig
    for trace in fig.data:                                          # 翻到第二页（同 add_page_slider 的一档）
        trace.visible = any(trace is artist for artist in figures[long_name].artists)
    fig.update_layout(legend_title_text=long_name)
    colorbar_left, legend_right, _ = svg_right_side(fig)
    assert legend_right <= colorbar_left


# ══════════════════════════════════════════════
# 4. 回调
# ══════════════════════════════════════════════
def test_scatter_map_formatters():
    """
    散点回调在颜色映射层上写 color、filled=False，在大小映射层上写 size 报错（会让颜色条或大小失去意义），
    报错时不留图、figures 不变；其余字段（描边色、标记、透明度）照常，映射的颜色不变。
    只映射大小的层可以写 color。原生回调不受限制：先用原生回调改大小，再用回调工厂改描边，大小保持原生回调改的。
    """
    sized = Layer(kind='scatter', mapping=ScatterMap(size=SIZE))
    for backend in BACKENDS:
        def fmt(style, backend: Backend = backend):
            return make_scatter_formatter(style, backend=backend)

        drawer = plotter(backend)
        before, opened = drawer.figures, plt.get_fignums()
        for layer, style, field in [(BOTH, ScatterStyle(color='red'), 'color'),
                                    (BOTH, ScatterStyle(filled=False), 'filled'),
                                    (BOTH, ScatterStyle(size=8), 'size'),
                                    (sized, ScatterStyle(size=8), 'size')]:
            with pytest.raises(ValueError, match=field):
                drawer.plot(layer, formatters=AxesFormatter(scatter=fmt(style)))
            assert drawer.figures is before and plt.get_fignums() == opened, (backend, field)

        # 映射层上改描边、标记、透明度：映射的颜色不变
        others = AxesFormatter(scatter=fmt(ScatterStyle(edge_color='black', marker='square', alpha=0.5)))
        drawn = drawer.plot(BOTH, formatters=others).figures['main']
        if backend == 'matplotlib':
            points = drawn.artists[1]
            mapped = np.asarray(plt.get_cmap('viridis')(Normalize(1, 3)([1, 2])))
            np.testing.assert_allclose(mpl_faces(points)[:, :3], mapped[:, :3])
            assert tuple(points.get_edgecolor()[0][:3]) == (0, 0, 0) and points.get_alpha() == 0.5
        else:
            marker = drawn.artists[1].marker
            assert (list(marker.color), marker.line.color, marker.symbol) == ([1, 2], 'black', 'square')
            assert marker.opacity == 0.5

        # 只映射大小：可以写 color
        drawn = drawer.plot(sized, formatters=AxesFormatter(scatter=fmt(ScatterStyle(color='red')))).figures['main']
        if backend == 'matplotlib':
            assert tuple(drawn.artists[0].get_facecolor()[0]) == to_rgba('red')
        else:
            assert drawn.artists[0].marker.color == 'red'

        # 原生回调改大小 → 回调工厂改描边：大小保持原生回调改的
        def native(scatters):
            for item in scatters:
                if backend == 'matplotlib':
                    item.set_sizes([100])
                else:
                    item.update(marker_size=10)

        chain = combine_formatters(native, fmt(ScatterStyle(edge_color='black')))
        drawn = drawer.plot(BOTH, formatters=AxesFormatter(scatter=chain)).figures['main']
        if backend == 'matplotlib':
            assert drawn.artists[1].get_sizes().tolist() == [100]
        else:
            assert (drawn.artists[1].marker.size, drawn.artists[1].marker.line.color) == (10, 'black')


# ══════════════════════════════════════════════
# 5. 取结果、分页、失败后的状态
# ══════════════════════════════════════════════
def test_scatter_map_result():
    """
    axes['colorbar']：matplotlib 是 Colorbar 对象，Plotly 是 'coloraxis'；没有颜色映射时没有这一项。
    图例仍是一个样品一条。分组分图时各图颜色范围相同：matplotlib 每张图一个颜色条，
    Plotly 各页在同一个 Figure 里共用一个 coloraxis。画失败时关掉这次的图，figures 保持上一次的结果。
    """
    color = Layer(kind='scatter', mapping=ScatterMap(color=COLOR))
    for backend in BACKENDS:
        drawn = plotter(backend).plot(color).figures['main']
        if backend == 'matplotlib':
            assert isinstance(drawn.axes['colorbar'], Colorbar)
            assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == ['S0', 'S3']
        else:
            assert drawn.axes['colorbar'] == 'coloraxis'
            assert [trace.name for trace in drawn.fig.data] == ['S0', 'S3'] and drawn.fig.layout.showlegend
        assert 'colorbar' not in plotter(backend).plot(Layer(kind='scatter')).figures['main'].axes

    data = map_data()
    groups = Group(data, {'A': {'num': [3]}, 'B': {'num': [0]}})
    figures = DataPlotter(data, groups=groups, channel_x=0, channel_y=1).plot(color, by='group').figures
    assert [(f.axes['colorbar'].norm.vmin, f.axes['colorbar'].norm.vmax) for f in figures.values()] == [(1, 40)] * 2
    figures = DataPlotter(data, groups=groups, channel_x=0, channel_y=1, backend='plotly').plot(color, by='group').figures
    fig = figures['A'].fig
    assert figures['B'].fig is fig
    assert {trace.marker.coloraxis for trace in fig.data} == {'coloraxis'}
    assert 'coloraxis2' not in fig.layout.to_plotly_json()

    # 某个样品的颜色全缺（这一组散点一个点也不画）：图例照样列出它；Plotly 切到只有它的一页时，颜色条和图例都还在
    # （复审：Plotly 不给空 trace 画图例，整页没有颜色数据时也不画颜色条）。按实际渲染核对
    missing = map_data()
    missing.data[0, 7] = np.nan                                     # 样品 0 的颜色通道只剩 NaN
    drawn = plotter('matplotlib', missing).plot(color).figures['main']
    assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == ['S0', 'S3']
    svg = plotly_svg(plotter('plotly', missing).plot(color).figures['main'].fig)
    assert len(re.findall(r'class="traces"', svg)) == 2 and 'cbcoloraxis' in svg
    groups = Group(missing, {'A': {'num': [3]}, 'B': {'num': [0]}})
    figures = DataPlotter(missing, groups=groups, channel_x=0, channel_y=1, backend='plotly').plot(color, by='group').figures
    fig = figures['A'].fig
    for trace in fig.data:                                          # 翻到 B 页（同 add_page_slider 的一档）
        trace.visible = any(trace is artist for artist in figures['B'].artists)
    svg = plotly_svg(fig)
    assert len(re.findall(r'class="traces"', svg)) == 1 and 'cbcoloraxis' in svg
    assert svg.count('class="point"') == 0                          # 占位不画出点

    # matplotlib 直接用 SVG、PDF 后端建图（复审：量文字宽度用的 get_renderer() 只有 Agg 画布有）
    import io
    for backend_name, fmt in (('svg', 'svg'), ('pdf', 'pdf')):
        plt.switch_backend(backend_name)
        try:
            drawn = plotter('matplotlib').plot(color).figures['main']
            drawn.fig.savefig(io.BytesIO(), format=fmt)
        finally:
            plt.switch_backend('Agg')

    drawer = plotter('matplotlib')
    drawer.plot(color)
    before, opened = drawer.figures, plt.get_fignums()

    def broken(fig, axes):
        raise RuntimeError('figure_formatter 出错')

    with pytest.raises(RuntimeError, match='出错'):
        drawer.plot(color, figure_formatter=broken)
    assert drawer.figures is before and plt.get_fignums() == opened
