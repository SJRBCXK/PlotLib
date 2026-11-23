"""
绘图后端：每个后端只读绘图计划，输入 `~plotlib.plot_spec.FigureSpec`，输出 `~plotlib.plot_spec.DrawnFigure`。

- `~plotlib.backends.matplotlib_backend.MatplotlibBackend`：静态图；
- `~plotlib.backends.plotly_backend.PlotlyBackend`：交互图，另有多页和滑块。

后端不认识 `DataSet`、`Group` 和 `DataPlotter`，只依赖 `plotlib.plot_spec`、`plotlib.layouts` 和
`plotlib.style`。两个后端的代码逐段对应，读懂一个，另一个就能对照着读。
"""
from ..plot_spec import Appearance

BACKENDS = ('matplotlib', 'plotly')


def get_backend(name: str, appearance: Appearance, cmap: str | None):
    """
    按名字创建后端。

    各后端在用到时才导入：Plotly 是可选依赖，没装也能用 matplotlib。

    Parameters
    ----------
    name : {'matplotlib', 'plotly'}
        后端名。
    appearance : Appearance
        全局外观，由后端自己翻译（matplotlib 翻译成 rc 参数，Plotly 翻译成模板）。
    cmap : str or None
        色带名；None 用 ``'plasma'``。

    Returns
    -------
    MatplotlibBackend or PlotlyBackend

    Raises
    ------
    ValueError
        不认识的后端名；或外观里有这个后端做不到的设置。
    ImportError
        选了 Plotly 但没有安装 Plotly，提示安装可选依赖。
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
