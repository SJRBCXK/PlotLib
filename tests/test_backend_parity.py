"""
两个绘图器的对照：DataPlotter（matplotlib）与 InteractivePlotter（Plotly）

两个绘图器读同一份绘图计划（plot_common.plan_figures），所以：
  - 构造时对分组参数的约定相同（plot_common.resolve_groups 共用）；
  - 同一个 Group 交给两个后端，画出的曲线条数、顺序、标签、数据一致（BACKEND_PLAN 第 3 步的验收）。
颜色不在这里比：两个库的色带实现不同，各自「位置 → 颜色」在 test_plotter.py / test_interactive.py 里测。

数据来自 conftest.py 的 eis_dataset：3 个样品；配置里样品 1 同时属于 A、B 两组。
"""
import numpy as np
import pytest

pytest.importorskip("plotly")

from plotlib.group import Group
from plotlib.interactive import InteractivePlotter
from plotlib.plotter import DataPlotter

PLOTTERS = pytest.mark.parametrize("Plotter", [DataPlotter, InteractivePlotter], ids=['matplotlib', 'plotly'])


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
# 构造：分组参数只接受建在同一数据集上的 Group
# （分组配置本身的校验在 test_group.py）
# ══════════════════════════════════════════════
@PLOTTERS
def test_groups_must_be_group_object(eis_dataset, Plotter):
    """传字典 → TypeError，提示先用 Group 包装（类型标注只在编辑器里提醒，运行时要自己检查）。"""
    with pytest.raises(TypeError, match="Group"):
        Plotter(eis_dataset, groups={'A': {'num': [0, 1]}})


@PLOTTERS
def test_groups_from_other_dataset_raises(eis_dataset, sparse_dataset, Plotter):
    """一个绘图器只对应一个数据集：Group 必须建在绘图器的数据集上。"""
    with pytest.raises(ValueError):
        Plotter(eis_dataset, groups=Group(sparse_dataset, {'A': {'num': [0, 5]}}))


@PLOTTERS
def test_default_groups_is_empty_group(eis_dataset, Plotter):
    """不传分组时是建在本数据集上的空 Group：后续代码总是面对一个 Group，不用判断 None。"""
    plotter = Plotter(eis_dataset)
    assert isinstance(plotter.groups, Group)
    assert plotter.groups.names == []
    assert plotter.groups.dataset is eis_dataset


# ══════════════════════════════════════════════
# 同一个 Group 交给两个后端
# ══════════════════════════════════════════════
def test_merge_mode_same_curves(eis_dataset):
    """合并模式：一张图，重叠的样品 1 只画一次，所以两边都是 3 条，且顺序、标签、数据一致。"""
    groups = Group(eis_dataset, overlap_config())
    mpl = DataPlotter(eis_dataset, groups=groups).group_plotter(merge_groups=True)
    plot = InteractivePlotter(eis_dataset, groups=groups)
    plot.plot_plotly_group(merge_groups=True)

    lines = list(mpl.axesset['main']['artists'].values())
    assert len(lines) == 3
    assert_same_curves(plot.plot_artists, lines)


def test_separate_mode_same_pages(eis_dataset):
    """分离模式：Plotly 的每一页与 matplotlib 对应分组那张图一致（步骤 6.4）。"""
    groups = Group(eis_dataset, overlap_config())
    mpl = DataPlotter(eis_dataset, groups=groups).group_plotter(merge_groups=False)
    plot = InteractivePlotter(eis_dataset, groups=groups)
    plot.plot_plotly_group(merge_groups=False)

    assert list(plot.pages) == list(mpl.axesset) == ['A', 'B']
    for key, page in plot.pages.items():
        lines = mpl.axesset[key]['artists']
        assert list(page) == list(lines)                  # 同样的样品号、同样的顺序
        assert_same_curves(list(page.values()), list(lines.values()))
