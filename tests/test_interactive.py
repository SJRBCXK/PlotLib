"""交互绘图的数据、状态和滑块规则；不打开浏览器。"""
from typing import Any, cast

import numpy as np
import pytest

pytest.importorskip("plotly")
import plotly.graph_objects as go

from src.dataset import DataSet
from src.interactive import InteractivePlotter


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


def test_plot_data_and_repeated_calls(eis_dataset):
    plot = InteractivePlotter(None, eis_dataset, plotdataRowNum_x=0, plotdataRowNum_y=1)
    assert plot.plot_plotly_object() is plot
    first = _asset(plot)
    assert len(_traces(first)) == len(plot.plot_artists) == 3
    for i, trace in enumerate(_traces(first)):
        np.testing.assert_array_equal(trace.x, [1, 10, 100])
        np.testing.assert_array_equal(trace.y, np.array([10, 20, 30]) * (i + 1))
        assert trace.name == f"S{i}"
    assert _layout(first)['xaxis']['title']['text'] == 'Frequency(Hz)'
    assert _layout(first)['yaxis']['title']['text'] == "Zs'(ohm)"

    plot.plot_plotly_object()
    assert plot.asset is not first
    assert len(plot.plot_artists) == 3
    assert all(a is b for a, b in zip(plot.plot_artists, _traces(_asset(plot))))


@pytest.mark.parametrize("mode, expected", [
    ("single", [[True, False, False], [False, True, False], [False, False, True]]),
    ("cumulative", [[True, False, False], [True, True, False], [True, True, True]]),
])
def test_slider_steps(eis_dataset, mode, expected):
    plot = InteractivePlotter(None, eis_dataset).plot_plotly_object()
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
    plot = InteractivePlotter(None, eis_dataset).plot_plotly_object()
    fig = plot.add_slider(slider_formatter=lambda s: s.update(currentvalue_prefix="G: "))
    layout = _layout(fig)
    slider = layout['sliders'][0]
    assert layout['title']['text'] == 'S0'
    assert slider['font']['color'] == 'black'
    assert slider['borderwidth'] == 1
    assert slider['currentvalue']['prefix'] == 'G: '


def test_slider_hides_crowded_labels(eis_dataset):
    """33 条长名称（如 piezo 数据）会互相压住，默认隐藏档位标签。"""
    plot = InteractivePlotter(None, eis_dataset)
    plot.asset = go.Figure(layout=dict(template=plot._create_template()))
    for i in range(33):
        plot.asset.add_scatter(x=[0, 1], y=[0, i], name=f'Mg10-back-1mm-relax-{i}')
    slider = _layout(plot.add_slider())['sliders'][0]
    assert slider['font']['color'] == 'rgba(0,0,0,0)'
    assert slider['currentvalue']['font']['color'] == 'black'


def test_slider_requires_figure(eis_dataset):
    with pytest.raises(RuntimeError, match='请先调用绘图方法'):
        InteractivePlotter(None, eis_dataset).add_slider()


def test_slider_rejects_empty_figure(eis_dataset):
    plot = InteractivePlotter(None, eis_dataset)
    plot.asset = go.Figure()
    with pytest.raises(RuntimeError, match='图中没有曲线'):
        plot.add_slider()


def test_invalid_mode_does_not_change_visibility(eis_dataset):
    plot = InteractivePlotter(None, eis_dataset).plot_plotly_object()
    before = _asset(plot).to_json()
    with pytest.raises(ValueError, match='不支持的 mode'):
        # 故意传入非法值，检验运行时校验；类型检查器的报错是预期的。
        plot.add_slider('typo')  # pyright: ignore[reportArgumentType]
    assert _asset(plot).to_json() == before


def test_empty_dataset_has_clear_error():
    with pytest.raises(RuntimeError, match='数据集为空'):
        InteractivePlotter(None, DataSet()).plot_plotly_object()
