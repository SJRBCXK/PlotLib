"""
两个后端的对照：DataPlotter(backend='matplotlib') 与 DataPlotter(backend='plotly')

同一个入口、同一份绘图计划（plan.plan_*），换后端只换「怎么画」，所以：
  - 构造时对分组参数的约定相同（plan.resolve_groups，与后端无关）；
  - 同一个 Group 交给两个后端，四种绘图方法画出的图数、曲线条数、顺序、标签、数据一致（BACKEND_PLAN 第 3、4 步的验收）。
颜色不在这里比：两个库的色带实现不同，各自「位置 → 颜色」在 test_plotter.py / test_plotly_backend.py 里测。

数据来自 conftest.py 的 eis_dataset：3 个样品；配置里样品 1 同时属于 A、B 两组。
"""
import numpy as np
import pytest

pytest.importorskip("plotly")

from plotlib.group import Group
from plotlib.plotter import DataPlotter

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
@pytest.mark.parametrize("draw", [
    lambda p: p.plot_multiline(),
    lambda p: p.plot_groups(merge_groups=True),
    lambda p: p.plot_groups(merge_groups=False),
    lambda p: p.plot_xy(channel_x=ZS_RE, channel_y=ZS_IM),
    lambda p: p.plot_dual_y(right=(FREQ, ZS_IM)),
], ids=['objects', 'merge', 'separate', 'xy', 'dual_y'])
def test_same_figures_and_curves(eis_dataset, draw):
    """
    图的 key 相同，每张图的曲线条数、顺序、标签、数据相同（去重、先到先得等规则本身在 test_plot_plan.py）。
    分离模式每组一张图：Plotly 在 6.8 前也是每组一个 Figure。
    """
    groups = Group(eis_dataset, overlap_config())
    mpl = draw(DataPlotter(eis_dataset, groups=groups, channel_x=FREQ, channel_y=ZS_RE))
    ply = draw(DataPlotter(eis_dataset, groups=groups, channel_x=FREQ, channel_y=ZS_RE,
                           backend='plotly'))

    assert list(ply.figures) == list(mpl.figures)
    for key, drawn in mpl.figures.items():
        assert_same_curves(ply.figures[key].artists, drawn.artists)


@BACKENDS
def test_backend_rejects_unknown_layout_and_kind(backend):
    """计划里的版式、画法写错时，两个后端都明确报错，不悄悄画成别的（BACKEND_PLAN 原则 5）。"""
    from plotlib.backends import get_backend
    from plotlib.plot_spec import Appearance, CurveSpec, FigureSpec

    drawer = get_backend(backend, Appearance(), None)

    def one_curve(kind='line') -> CurveSpec:
        return CurveSpec(sample_idx=0, x=np.array([0, 1]), y=np.array([0, 1]), label='S0',
                         group_name=None, color_position=None, style={}, kind=kind)  # pyright: ignore[reportArgumentType]

    with pytest.raises(ValueError, match='版式'):
        drawer.draw(FigureSpec(key='k', x_unit='', y_unit='', curves=[one_curve()],
                               layout='pie'), figsize=(4, 3))  # pyright: ignore[reportArgumentType]  故意写错
    with pytest.raises(ValueError, match='plot_kind'):
        drawer.draw(FigureSpec(key='k', x_unit='', y_unit='', curves=[one_curve('pie')]),  # pyright: ignore[reportArgumentType]
                    figsize=(4, 3))
