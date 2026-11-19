"""
测试对象：src/plotlib/interactive.py 按绘图计划画图（STRUCTURE_REVIEW 步骤 6.3）

Plotly 一侧和 matplotlib 一样只读计划（plot_common.plan_figures），不读 Group：
  - plot_plotly_object：不分组的计划（一张 'main' 图）；
  - plot_plotly_group：带分组的合并模式计划；空分组退回 plot_plotly_object。
分组规则（去重、先到先得、组首色、样式归属）在 test_plot_plan.py 里测过，这里只测「Plotly 照计划画对了」，
以及同一个 Group 交给两个后端时曲线一致（BACKEND_PLAN 第 3 步的验收）。

数据来自 conftest.py 的 eis_dataset：3 个样品，色带位置 0、1/3、2/3。
"""
from typing import cast

import numpy as np
import pytest

pytest.importorskip("plotly")
import plotly.colors as plyc
import plotly.graph_objects as go

from plotlib.group import Group
from plotlib.interactive import InteractivePlotter
from plotlib.plot_common import plan_figures
from plotlib.plotter import DataPlotter

PLASMA = plyc.get_colorscale('Plasma')


def plasma(position: float) -> str:
    """色带位置 → Plotly 颜色字符串（与 InteractivePlotter 默认色带相同）。"""
    return plyc.sample_colorscale(PLASMA, [position])[0]


def overlap_config():
    """样品 1 同时属于 A、B 两组；只有 A 写了线型。与 test_plot_plan.py 相同。"""
    return {
        'A': {'num': [0, 1], 'linestyle': 'dash'},
        'B': {'num': [1, 2]},
    }


def traces(plot: InteractivePlotter) -> tuple[go.Scatter, ...]:
    """取出已绘制 Figure 的 trace；测试图里只有 Scatter，cast 不改变运行时对象。"""
    assert plot.asset is not None
    return cast(tuple[go.Scatter, ...], plot.asset.data)


def plot_group(dataset, config) -> InteractivePlotter:
    """按配置建 Group（每次新建：Group 会原地格式化传入的配置），画合并模式的分组图。"""
    plot = InteractivePlotter(dataset, groups=Group(dataset, config))
    plot.plot_plotly_group()
    return plot


# ──────────────────────────────────────────────
# 6.3a：不分组也按计划画（回归保护，改前改后都应通过）
# ──────────────────────────────────────────────
def test_plot_object_follows_plan(eis_dataset):
    """每条 trace 与不分组计划的曲线一一对应：顺序、名字、数据。"""
    [spec] = plan_figures(eis_dataset, None, 0, 1)
    plot = InteractivePlotter(eis_dataset).plot_plotly_object()

    assert len(traces(plot)) == len(spec.curves)
    for trace, curve in zip(traces(plot), spec.curves):
        assert trace.name == curve.label
        np.testing.assert_array_equal(trace.x, curve.x)
        np.testing.assert_array_equal(trace.y, curve.y)


# ──────────────────────────────────────────────
# 6.3b：分组入口（合并模式）
# ──────────────────────────────────────────────
def test_group_matches_matplotlib_merge(eis_dataset):
    """
    同一个 Group 交给两个后端：曲线条数、顺序、标签、数据都一致。
    重叠的样品 1 只画一次，所以是 3 条而不是 4 条。
    """
    groups = Group(eis_dataset, overlap_config())
    mpl = DataPlotter(eis_dataset, groups=groups).group_plotter(merge_groups=True)
    lines = list(mpl.axesset['main']['artists'].values())
    plot = InteractivePlotter(eis_dataset, groups=groups)
    plot.plot_plotly_group()

    assert len(traces(plot)) == len(lines) == 3
    for trace, line in zip(traces(plot), lines):
        assert trace.name == line.get_label()
        np.testing.assert_array_equal(trace.x, line.get_xdata())
        np.testing.assert_array_equal(trace.y, line.get_ydata())


def test_group_head_color(eis_dataset):
    """
    同组的线统一用组首色：样品 0、1 归 A（组首 0，位置 0）；
    样品 2 归 B，B 的组首是样品 1（位置 1/3），即使样品 1 已归 A。
    """
    plot = plot_group(eis_dataset, overlap_config())
    assert [t.line.color for t in traces(plot)] == [plasma(0), plasma(0), plasma(1/3)]


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
    trace = traces(plot)[0]
    for path, value in expected.items():
        obj = trace
        for attr in path.split('.'):
            obj = getattr(obj, attr)
        assert obj == value, path


def test_group_marker_color_follows_line(eis_dataset):
    """写了 marker 时，点的颜色与线一致（都是组首色），不会落回 Plotly 的默认配色。"""
    plot = plot_group(eis_dataset, {'A': {'num': [0, 1], 'marker': 'square'}})
    for trace in traces(plot):
        assert trace.marker.color == trace.line.color == plasma(0)


def test_empty_groups_falls_back_to_plot_object(eis_dataset):
    """不分组时 plot_plotly_group 与 plot_plotly_object 画出相同的曲线。"""
    grouped = InteractivePlotter(eis_dataset)
    assert grouped.plot_plotly_group() is grouped
    plain = InteractivePlotter(eis_dataset).plot_plotly_object()

    assert [t.name for t in traces(grouped)] == [t.name for t in traces(plain)]
    assert [t.line.color for t in traces(grouped)] == [t.line.color for t in traces(plain)]


def test_group_figure_formatter(eis_dataset):
    """figure_formatter 在默认格式之后调用一次，收到的就是保存下来的 Figure。"""
    received = []
    plot = InteractivePlotter(eis_dataset, groups=Group(eis_dataset, overlap_config()))
    plot.plot_plotly_group(figure_formatter=received.append)

    assert len(received) == 1
    assert received[0] is plot.asset
