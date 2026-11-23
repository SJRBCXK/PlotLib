"""
根据 `~plotlib.plot_spec.FigureSpec` 渲染图形并返回 `~plotlib.plot_spec.DrawnFigure`。

`~plotlib.backends.matplotlib_backend.MatplotlibBackend` 渲染静态图，
`~plotlib.backends.plotly_backend.PlotlyBackend` 渲染交互图并提供分页和滑块。
两个后端共用绘图计划和版式预设。
"""
from ..plot_spec import Appearance

BACKENDS = ('matplotlib', 'plotly')


def get_backend(name: str, appearance: Appearance, cmap: str | None):
    """
    按名称创建绘图后端。

    后端按需导入。Plotly 是可选依赖。

    Parameters
    ----------
    name : {'matplotlib', 'plotly'}
        后端名。
    appearance : Appearance
        全局外观。Matplotlib 使用 rc 参数，Plotly 使用图形模板。
    cmap : str or None
        色带名称。``None`` 使用 ``'plasma'``。

    Returns
    -------
    MatplotlibBackend or PlotlyBackend

    Raises
    ------
    ValueError
        后端名称无效，或外观设置超出所选后端的支持范围。
    ImportError
        无法导入 Plotly 后端。
    """
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
