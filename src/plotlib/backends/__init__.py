"""
绘图后端（STRUCTURE_REVIEW 6.6、6.7）：每个后端只读绘图计划，输入 FigureSpec、输出 DrawnFigure。

DataPlotter 按名字取后端：DataPlotter(dataset, backend='matplotlib')。
各后端在用到时才导入：Plotly 是可选依赖，没装也要能用 matplotlib。
"""
from ..plot_spec import Appearance

BACKENDS = ('matplotlib', 'plotly')


def get_backend(name: str, appearance: Appearance, cmap: str | None):
    """按名字创建后端；外观、色带名交给后端自己翻译。"""
    if name == 'matplotlib':
        from .matplotlib_backend import MatplotlibBackend
        return MatplotlibBackend(appearance, cmap)
    if name == 'plotly':
        try:
            from .plotly_backend import PlotlyBackend
        except ImportError as error:
            raise ImportError('Plotly 后端需要 Plotly，请安装可选依赖：pip install -e ".[interactive]"') from error
        return PlotlyBackend(appearance, cmap)
    raise ValueError(f"不支持的 backend: {name!r}，可选：{', '.join(repr(b) for b in BACKENDS)}")
