"""
验证 DataPlotter.plot_bars 的入口校验、结果查询和失败回滚。

两个后端检查柱位、堆叠基线、误差棒、类别刻度、样式、回调及图例。绘图计划由 test_plot_plan.py 验证。
Plotly 的柱子位置由 Plotly.js 自己排，用 Kaleido 渲染成 SVG 后按像素核对。
"""
import re
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import plotly.colors as plyc
import pytest
from conftest import bar_data
from matplotlib.colors import to_rgba

from plotlib.dataset import DataSet
from plotlib.formatters import combine_formatters, make_bar_formatter
from plotlib.group import Group
from plotlib.plot_spec import AxesFormatter, BarMode, BarStyle
from plotlib.plotter import DataPlotter

BACKENDS = ('matplotlib', 'plotly')


def stack_data() -> DataSet:
    """
    两个样品、每格一个值，含负数、缺数据和误差通道：

        通道 0 A    S0: 1     S1: -2
        通道 1 B    S0: 3     S1: NaN       （缺数据）
        通道 2 C    S0: -4    S1: -3
        通道 3 dA   S0: 0.5   S1: NaN       （A 的误差，S1 缺）
        通道 4 dC   S0: 0.3   S1: 0.2       （C 的误差）
    """
    nan = np.nan
    units = ['A', 'B', 'C', 'dA', 'dC']
    data = DataSet().form_array(np.array([[1, 3, -4, 0.5, 0.3]]), ['S0'] * 5, units, 0, repeat_times=5)
    data.expandata(DataSet().form_array(np.array([[-2, nan, -3, nan, 0.2]]), ['S1'] * 5, units, 1, repeat_times=5))
    return data


def mpl_geometry(drawn) -> list[list[str]]:
    """每个系列每根柱的「中心/底部/高度」（matplotlib），缺数据的柱写成「中心/-/nan」。"""
    return [[f"{r.get_x() + r.get_width() / 2:.2f}/-/nan" if np.isnan(r.get_height()) else
             f"{r.get_x() + r.get_width() / 2:.2f}/{r.get_y():.2f}/{r.get_height():.2f}" for r in container.patches]
            for container in drawn.artists]


def svg_traces(fig) -> list[dict]:
    """
    用 Kaleido 把 Plotly 图渲染成 SVG，按 trace 取出实际画出的柱和误差棒（像素）：
    ``bars`` 是每根柱的 (中心, 宽度)，缺数据的柱是 None；``caps`` 是每条误差棒端帽的横线长度。
    """
    pytest.importorskip('kaleido')
    svg = fig.to_image(format='svg').decode()
    traces = []
    for chunk in svg.split('<g class="trace bars"')[1:]:
        bars = []
        for d in re.findall(r'<g class="point"><path d="([^"]*)"', chunk):
            numbers = [float(v) for v in re.findall(r'-?\d+(?:\.\d+)?', d)]
            bars.append(None if d == 'M0,0Z' else ((numbers[0] + numbers[3]) / 2, numbers[3] - numbers[0]))
        caps = [float(h) for d in re.findall(r'class="yerror" d="([^"]*)"', chunk) for h in re.findall(r'h(-?[\d.]+)', d)]
        traces.append({'bars': bars, 'caps': caps})
    legend_patterns = len(re.findall(r'class="legendundefined pattern_filled"', svg))
    return [*traces, {'legend_patterns': legend_patterns}]


# ══════════════════════════════════════════════
# 4. 入口校验：都在汇总和画图之前报错
# ══════════════════════════════════════════════
def test_bar_entry_checks():
    """写错的维度、通道、柱宽、汇总、误差、回调，以及柱状图后接滑块，都明确报错；报错时汇总函数没执行、不留图窗。"""
    data = bar_data()
    groups = Group(data, {'G1': {'num': [3, 0]}})
    plotter = DataPlotter(data, groups=groups)
    no_groups = DataPlotter(data)
    negative = bar_data()
    negative.data[0, 3] = -1                       # 样品 3 的误差通道第 1 行写成负数
    infinite = bar_data()
    infinite.data[0, 0] = np.inf                   # 样品 3 的 F 第 1 行是无穷大
    opposite = bar_data()
    opposite.data[0:2, 0] = [np.inf, -np.inf]      # 均值会先变成 NaN，不能被当成缺数据跳过
    calls = []

    def counting(values):
        calls.append(1)
        return values[0]

    cases = [
        (lambda: plotter.plot_bars(0, x='channel', series='channel'), "x 和 series"),
        (lambda: plotter.plot_bars(0, x='samples'), "'sample'、'group'、'channel'"),        # pyright: ignore[reportArgumentType]
        (lambda: no_groups.plot_bars(0, x='group', reduce='mean'), '要有分组'),
        (lambda: plotter.plot_bars([0, 0], reduce='mean'), '重复'),
        (lambda: plotter.plot_bars(0, reduce='mean', width=float('nan')), 'width'),
        (lambda: plotter.plot_bars(0, reduce='mean', width=1.5), 'width'),
        (lambda: plotter.plot_bars(0, mode='overlay', reduce='mean'), 'mode'),              # pyright: ignore[reportArgumentType]
        (lambda: plotter.plot_bars(0), '3 个有效值'),                                        # 样品 3 的 F 有 3 行，没写 reduce
        (lambda: plotter.plot_bars(1, reduce='max', errors='std'), "reduce='mean'"),
        (lambda: plotter.plot_bars(0, x='group', reduce='mean', errors={0: 3}), '误差字典'),
        (lambda: DataPlotter(negative).plot_bars(0, reduce='first', errors={0: 3}), '负数'),
        (lambda: plotter.plot_bars(0, reduce='first', errors={1: 3}), '不在 channels'),
        (lambda: DataPlotter(infinite).plot_bars(0, reduce='first'), r'S3.*F\(N\).*无穷'),   # NaN 才表示缺数据
        (lambda: DataPlotter(opposite).plot_bars(0, reduce='mean'), r'S3.*F\(N\).*无穷'),
        (lambda: plotter.plot_bars(0, reduce='mean', errors='std', ), '没有一根柱'),  # 改 plotrange 见下
        (lambda: plotter.plot_bars(0, reduce=counting, formatters={'right': AxesFormatter()}), '左轴'),
        (lambda: plotter.plot_bars(0, reduce=counting, formatters=AxesFormatter(lines=print)), 'lines'),
        (lambda: plotter.plot_bars(0, reduce=counting, formatters=AxesFormatter(scatter=print)), 'scatter'),
        (lambda: plotter.plot_bars(0, reduce=counting, styles={9: BarStyle()}), 'styles'),
        (lambda: plotter.plot(formatters=AxesFormatter(bars=print)), 'bars'),
    ]
    one_row = DataPlotter(data, plotrange=1)       # 每格只取 1 行：算不出标准差，没有一根柱有误差棒
    cases[14] = (lambda: one_row.plot_bars(0, reduce='mean', errors='std'), '没有一根柱')
    for call, message in cases:
        with pytest.raises(ValueError, match=message):
            call()
    assert calls == []                              # 回调、样式写错时，汇总函数一次都没执行
    assert plt.get_fignums() == []

    # 柱状图不支持滑块：两个入口都明确报错（滑块按样品切换曲线，柱状图的系列不是样品）
    plotly = DataPlotter(data, backend='plotly').plot_bars(0, reduce='mean')
    for add in (plotly.add_slider, plotly.add_page_slider):
        with pytest.raises(RuntimeError, match='柱状图'):
            add()


# ══════════════════════════════════════════════
# 6. matplotlib：并排偏移、缺数据保留位置、堆叠底部、误差棒位置
# ══════════════════════════════════════════════
def test_bar_missing_and_stack():
    """
    3 个系列（A、B、C）、width=0.6：并排时每根宽 0.2，偏移 -0.2、0、0.2；S1 的 B 缺数据，位置保留、不画。
    堆叠时正负分开叠：S0 的 B 叠在 A（1）上，C（-4）从 0 往下；S1 的 C（-3）叠在 A（-2）下面，B 缺数据不参与累加。
    误差棒画在每段远离 0 的一端：A 在 S0 的顶端是 1；C 在 S1 的底端是 -2 + -3 = -5。
    """
    plotter = DataPlotter(stack_data())
    group = plotter.plot_bars([0, 1, 2], width=0.6).figures['main']
    assert mpl_geometry(group) == [['-0.20/0.00/1.00', '0.80/0.00/-2.00'],
                                   ['0.00/0.00/3.00', '1.00/-/nan'],
                                   ['0.20/0.00/-4.00', '1.20/0.00/-3.00']]
    assert [r.get_width() for r in group.artists[0].patches] == pytest.approx([0.2, 0.2])

    stack = plotter.plot_bars([0, 1, 2], mode='stack', width=0.6, errors={0: 3, 2: 4}).figures['main']
    assert mpl_geometry(stack) == [['0.00/0.00/1.00', '1.00/0.00/-2.00'],
                                   ['0.00/1.00/3.00', '1.00/-/nan'],
                                   ['0.00/0.00/-4.00', '1.00/-2.00/-3.00']]
    assert [r.get_width() for r in stack.artists[0].patches] == pytest.approx([0.6, 0.6])

    def error_segments(container):
        return [np.round(segment, 2).tolist() for segment in container.errorbar.lines[2][0].get_segments()
                if len(segment)]
    assert error_segments(stack.artists[0]) == [[[0.0, 0.5], [0.0, 1.5]]]               # S1 缺误差，不画
    assert error_segments(stack.artists[2]) == [[[0.0, -4.3], [0.0, -3.7]], [[1.0, -5.2], [1.0, -4.8]]]
    assert stack.artists[1].errorbar is None                                              # B 没写误差通道


# ══════════════════════════════════════════════
# 7. Plotly：barmode、间距，以及 Kaleido 实际渲染出的柱位置、端帽、图例纹理
# ══════════════════════════════════════════════
def test_bar_plotly_layout_and_render():
    """
    并排用 'group'、堆叠用 'relative'（正负分开叠），bargap = 1 - width、bargroupgap = 0。
    实际渲染（同一组数据）：相邻类别间距为 D 时每根柱宽 0.2D，B、C 相对 A 偏移 0.2D、0.4D；S1 的 B 缺数据，
    C 仍在原位。A 在 S1 缺误差：这个系列不画端帽（Plotly 会在缺误差处画横杠）；C 误差完整，端帽照画。
    回调改了纹理，图例色块也跟着带纹理。
    """
    plotter = DataPlotter(stack_data(), backend='plotly')
    modes: list[tuple[BarMode, str]] = [('group', 'group'), ('stack', 'relative')]
    for mode, barmode in modes:
        layout = plotter.plot_bars([0, 1, 2], mode=mode, width=0.6).figures['main'].fig.layout
        assert (layout.barmode, layout.bargap, layout.bargroupgap) == (barmode, pytest.approx(0.4), 0)

    hatch = make_bar_formatter(BarStyle(hatch='x'), backend='plotly')
    fig = plotter.plot_bars([0, 1, 2], width=0.6, errors={0: 3, 2: 4}, styles=BarStyle(capsize=3),
                            formatters=AxesFormatter(bars=hatch)).figures['main'].fig
    a, b, c, legend = svg_traces(fig)
    spacing = a['bars'][1][0] - a['bars'][0][0]
    assert a['bars'][0][1] == pytest.approx(0.2 * spacing, abs=0.5)
    assert b['bars'][0][0] - a['bars'][0][0] == pytest.approx(0.2 * spacing, abs=0.5)
    assert b['bars'][1] is None                                                           # 缺数据：不画
    assert c['bars'][1][0] - a['bars'][1][0] == pytest.approx(0.4 * spacing, abs=0.5)    # 位置保留
    assert a['caps'] and all(h == 0 for h in a['caps'])                                   # 缺误差的系列没有横杠
    assert c['caps'] and all(h > 0 for h in c['caps'])
    assert legend['legend_patterns'] == 3

    # 堆叠：下段 A = 3 ± 2（1～5，向上伸进 B），上段 B = 1 ± 2（末端 4，2～6，向下伸进 A）。
    # Plotly 把每个 trace 的柱和误差棒画在一组里，调层次只能顾一头；误差棒要整体画在所有柱之上
    # （实际 SVG 里两条误差棒都在最后一组柱之后），两个方向都不被遮住
    both_ways = DataSet().form_array(np.array([[3, 1, 2, 2]]), ['S0'] * 4, ['A', 'B', 'dA', 'dB'], 0, repeat_times=4)
    stacked = DataPlotter(both_ways, backend='plotly').plot_bars([0, 1], mode='stack', errors={0: 2, 1: 3})
    svg = stacked.figures['main'].fig.to_image(format='svg').decode()
    assert svg.count('class="yerror"') == 2
    assert svg.find('class="yerror"') > svg.rfind('<g class="trace bars"')
    error_y = [trace.error_y for trace in stacked.figures['main'].fig.data if trace.type == 'scatter']
    assert [list(e.array) for e in error_y] == [[2], [2]]                   # 位置是每段的末端：3、4
    assert [list(t.y) for t in stacked.figures['main'].fig.data if t.type == 'scatter'] == [[3], [4]]
    # 误差棒的位置是画的时候算好的：点图例隐藏一段后 Plotly 会重新堆叠，误差棒却留在原处。
    # 仅带误差棒的堆叠图禁用图例的单击和双击显隐。
    legend = stacked.figures['main'].fig.layout.legend
    assert (legend.itemclick, legend.itemdoubleclick) == (False, False)
    plain = DataPlotter(both_ways, backend='plotly').plot_bars([0, 1], mode='stack').figures['main'].fig.layout.legend
    assert (plain.itemclick, plain.itemdoubleclick) == (None, None)


# ══════════════════════════════════════════════
# 8. 类别刻度：同名不合并，X 轴没有次刻度
# ══════════════════════════════════════════════
def test_bar_category_ticks():
    """两个样品同名：两个后端都用数字位置 + 刻度文字，两根柱分开画（Plotly 的类别轴会把同名合到一格）。"""
    data = DataSet().form_array(np.array([[1.0]]), ['S'], ['F(N)'], 0)
    data.expandata(DataSet().form_array(np.array([[2.0]]), ['S'], ['F(N)'], 1))

    drawn = DataPlotter(data).plot_bars(0).figures['main']
    ax = drawn.axes['left']
    drawn.fig.canvas.draw()
    assert list(ax.get_xticks()) == [0, 1]
    assert [label.get_text() for label in ax.get_xticklabels()] == ['S', 'S']
    assert len(ax.xaxis.get_minorticklocs()) == 0 and len(ax.yaxis.get_minorticklocs()) > 0
    assert ax.get_xlabel() == ''

    fig = DataPlotter(data, backend='plotly').plot_bars(0).figures['main'].fig
    assert (tuple(fig.layout.xaxis.tickvals), tuple(fig.layout.xaxis.ticktext)) == ((0, 1), ('S', 'S'))
    assert tuple(fig.data[0].x) == (0, 1)
    assert fig.layout.xaxis.minor.ticks == ''
    assert not fig.layout.xaxis.title.text


# ══════════════════════════════════════════════
# 9. 颜色、样式、纹理
# ══════════════════════════════════════════════
def mpl_face(container):
    return tuple(container.patches[0].get_facecolor())


def test_bar_styles():
    """
    默认颜色按计划里的色带位置（系列是通道、样品、分组三种）；分组写的颜色、纹理在系列是分组时生效；
    styles 的填充、描边、纹理两个后端都生效，纹理颜色跟随描边色，图例色块也带纹理；'none' 清除纹理。
    """
    data = bar_data()
    groups = Group(data, {'G1': {'num': [3, 0], 'hatch': 'dot'}, 'G2': {'num': [0], 'color': 'red'}})
    for backend in BACKENDS:
        plotter = DataPlotter(data, groups=groups, backend=backend)
        cmap: Any = plotter.backend.cmap          # matplotlib 是 Colormap，Plotly 是色带列表
        layouts: list[dict[str, Any]] = [dict(), dict(x='channel', series='sample'), dict(x='channel', series='group')]
        for kwargs in layouts:
            drawn = plotter.plot_bars([1, 0], reduce='mean', **kwargs).figures['main']
            for bar, artist in zip(drawn.spec.curves, drawn.artists):
                if bar.style.color == 'red':                    # G2 写了颜色
                    expected = 'red'
                elif backend == 'matplotlib':
                    expected = cmap(bar.color_position)
                else:
                    expected = plyc.sample_colorscale(cmap, [bar.color_position])[0]
                if backend == 'matplotlib':
                    assert mpl_face(artist) == to_rgba(expected), kwargs
                else:
                    assert artist.marker.color == expected, kwargs
            if kwargs.get('series') == 'group':                 # G1 写了纹理 'dot'
                hatches = ([artist.patches[0].get_hatch() for artist in drawn.artists] if backend == 'matplotlib'
                           else [artist.marker.pattern.shape for artist in drawn.artists])
                assert hatches[0] == '.' and not hatches[1]

        black_white = BarStyle(color='white', edge_color='red', edge_width=2, hatch='slash')
        drawn = plotter.plot_bars([1, 0], reduce='mean', styles={1: black_white, 0: BarStyle(hatch='none')}
                                  ).figures['main']
        styled, cleared = drawn.artists
        if backend == 'matplotlib':
            patch = styled.patches[0]
            assert (patch.get_facecolor(), patch.get_edgecolor()) == (to_rgba('white'), to_rgba('red'))
            assert (patch.get_linewidth(), patch.get_hatch()) == (2, '/')
            assert not cleared.patches[0].get_hatch()
            handles = drawn.axes['left'].get_legend().legend_handles
            assert [handle.get_hatch() for handle in handles][0] == '/'         # 图例色块带纹理
        else:
            marker = styled.marker
            assert (marker.color, marker.line.color, marker.line.width) == ('white', 'red', pytest.approx(2 * 100 / 72))
            assert (marker.pattern.shape, marker.pattern.fgcolor, marker.pattern.fillmode) == ('/', 'red', 'overlay')
            assert cleared.marker.pattern.shape == ''

    # 误差棒线宽在画的时候也作用到端帽上（与回调一致）：竖线、端帽都是 4 磅
    drawn = DataPlotter(data).plot_bars(0, reduce='first', errors={0: 3},
                                        styles=BarStyle(error_width=4, capsize=3)).figures['main']
    _, caplines, barlines = drawn.artists[0].errorbar.lines
    assert barlines[0].get_linewidth()[0] == 4 and [cap.get_markeredgewidth() for cap in caplines] == [4, 4]


# ══════════════════════════════════════════════
# 10. 回调：原生回调与 make_bar_formatter 先后组合
# ══════════════════════════════════════════════
def test_bar_formatter_combinations():
    """
    先原生回调改填充色，再 make_bar_formatter 改纹理、描边：没写的填充色保持原生回调改的；
    再写 hatch='none' 清除纹理，描边保持；误差棒的颜色、线宽；磅按 dpi 换成像素；图例跟着更新。
    端帽长度在画之前定（matplotlib 画完不能补端帽），写在回调里报错。
    """
    with pytest.raises(ValueError, match='capsize'):
        make_bar_formatter(BarStyle(capsize=4))

    data = stack_data()
    def native_matplotlib(containers):
        for container in containers:
            for patch in container.patches:
                patch.set_facecolor('blue')

    def native_plotly(traces):
        for trace in traces:
            trace.update(marker_color='blue')

    for backend in BACKENDS:
        native = native_matplotlib if backend == 'matplotlib' else native_plotly
        steps = [native,
                 make_bar_formatter(BarStyle(hatch='x', edge_color='green', edge_width=1.44), backend=backend),
                 make_bar_formatter(BarStyle(error_color='red', error_width=3), backend=backend)]
        drawn = DataPlotter(data, backend=backend).plot_bars(
            [0, 2], errors={0: 3, 2: 4}, formatters=AxesFormatter(bars=combine_formatters(*steps))).figures['main']
        if backend == 'matplotlib':
            patch = drawn.artists[0].patches[0]
            assert (patch.get_facecolor(), patch.get_edgecolor()) == (to_rgba('blue'), to_rgba('green'))
            assert (patch.get_hatch(), patch.get_linewidth()) == ('x', 1.44)
            errors = drawn.artists[0].errorbar.lines[2][0]
            assert (tuple(errors.get_color()[0]), errors.get_linewidth()[0]) == (to_rgba('red'), 3)
            handles = drawn.axes['left'].get_legend().legend_handles
            assert [handle.get_hatch() for handle in handles] == ['x', 'x']          # 图例按回调后的样式重建
        else:
            marker = drawn.artists[0].marker
            assert (marker.color, marker.line.color, marker.line.width) == ('blue', 'green', pytest.approx(2.0))
            assert (marker.pattern.shape, marker.pattern.fgcolor) == ('x', 'green')
            error_y = drawn.artists[0].error_y
            assert (error_y.color, error_y.thickness) == ('red', pytest.approx(3 * 100 / 72))

        # 回调改了系列名，图例跟着改（matplotlib 重建图例时读对象当前的标签）
        rename = make_bar_formatter(custom=[(lambda c: c.set_label('X')) if backend == 'matplotlib'
                                            else (lambda t: t.update(name='X'))], backend=backend)
        drawn = DataPlotter(data, backend=backend).plot_bars(
            [0, 2], formatters=AxesFormatter(bars=rename)).figures['main']
        if backend == 'matplotlib':
            assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == ['X', 'X']
        else:
            assert [trace.name for trace in drawn.fig.data] == ['X', 'X']

        # 柱状图回调更新堆叠图中独立误差棒 trace 的样式。
        if backend == 'plotly':
            fig = DataPlotter(data, backend=backend).plot_bars(
                [0, 2], mode='stack', errors={0: 3, 2: 4}, formatters=AxesFormatter(bars=steps[2])).figures['main'].fig
            assert {(t.error_y.color, round(t.error_y.thickness, 3)) for t in fig.data if t.type == 'scatter'} == \
                {('red', round(3 * 100 / 72, 3))}

        clear = make_bar_formatter(BarStyle(hatch='none'), backend=backend)
        drawn = DataPlotter(data, backend=backend).plot_bars(
            [0, 2], formatters=AxesFormatter(bars=combine_formatters(steps[1], clear))).figures['main']
        if backend == 'matplotlib':
            patch = drawn.artists[0].patches[0]
            assert not patch.get_hatch() and patch.get_edgecolor() == to_rgba('green')
        else:
            marker = drawn.artists[0].marker
            assert (marker.pattern.shape, marker.line.color) == ('', 'green')


# ══════════════════════════════════════════════
# 11. Y 轴标题、图例
# ══════════════════════════════════════════════
def test_bar_y_title_and_legend():
    """
    Y 轴标题：一个通道是它的列标题；多个通道列标题相同时沿用，不同时留空。
    图例一个系列一个条目，按系列顺序，文字是列标题；legend_title 写了才有标题。
    """
    data = bar_data()
    for backend in BACKENDS:
        plotter = DataPlotter(data, backend=backend)
        for channels, title in (([0], 'F(N)'), ([0, 2], 'F(N)'), ([0, 1], '')):
            drawn = plotter.plot_bars(channels, reduce='mean').figures['main']
            shown = (drawn.axes['left'].get_ylabel() if backend == 'matplotlib'
                     else drawn.fig.layout.yaxis.title.text or '')
            assert shown == title, (backend, channels)

        for legend_title, expected in (('auto', ''), ('Channel', 'Channel')):
            drawn = plotter.plot_bars([1, 0], reduce='mean', legend_title=legend_title).figures['main']
            if backend == 'matplotlib':
                legend = drawn.axes['left'].get_legend()
                entries = [text.get_text() for text in legend.get_texts()]
                shown = legend.get_title().get_text()
            else:
                entries = [trace.name for trace in drawn.fig.data]
                shown = drawn.fig.layout.legend.title.text or ''
            assert (entries, shown) == (['E(%)', 'F(N)'], expected), backend

    # 图例不漏项：只有一个系列时 Plotly 也显示图例（否则写了 legend_title 也看不到）；
    # 标签以 '_' 开头时 matplotlib 自动收集图例会跳过它，柱状图按系列显式生成图例
    underscored = DataSet().form_array(np.array([[1.0, 2.0]]), ['S0', 'S0'], ['_Pa', 'F(N)'], 0, repeat_times=2)
    drawn = DataPlotter(underscored).plot_bars([0, 1], legend_title='T').figures['main']
    assert [text.get_text() for text in drawn.axes['left'].get_legend().get_texts()] == ['_Pa', 'F(N)']
    fig = DataPlotter(underscored, backend='plotly').plot_bars(0, legend_title='T').figures['main'].fig
    assert fig.layout.showlegend is True and fig.layout.legend.title.text == 'T'


# ══════════════════════════════════════════════
# 12. 取结果、失败后的状态
# ══════════════════════════════════════════════
def test_bar_result_and_failure():
    """artist(key) 按系列的键取（原通道号、样品号）；画失败时关掉这次的图，figures 保持上一次的结果。"""
    plotter = DataPlotter(bar_data())
    drawn = plotter.plot_bars([1, 0], reduce='mean').figures['main']
    assert drawn.artist(1) is drawn.artists[0] and drawn.artist(0) is drawn.artists[1]
    with pytest.raises(KeyError):
        drawn.artist(2)
    by_sample = plotter.plot_bars([1, 0], x='channel', series='sample', reduce='mean').figures['main']
    assert by_sample.artist(3) is by_sample.artists[1]
    curves = DataPlotter(bar_data()).plot().figures['main']
    assert curves.artist(sample_idx=0) is curves.artist(0)          # 曲线图原来的关键字写法仍然可用

    before = plotter.figures
    figures_before = plt.get_fignums()

    def broken(fig, axes):
        raise RuntimeError('figure_formatter 出错')

    with pytest.raises(RuntimeError, match='出错'):
        plotter.plot_bars(0, reduce='mean', figure_formatter=broken)
    assert plotter.figures is before
    assert plt.get_fignums() == figures_before
