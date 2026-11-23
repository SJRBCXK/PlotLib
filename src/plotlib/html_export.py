"""
将 Plotly Figure 导出为随窗口等比缩放的 HTML 页面。

Notes
-----
页面模板 ``templates/ppt_fit_shell.html`` 将图表和可选侧栏放入固定尺寸的容器，
再根据窗口大小缩放并居中。导出过程仅读取 Figure 的尺寸和 HTML 表示。

Examples
--------
>>> from plotlib.html_export import write_fit_html
>>> fig = DataPlotter(data, backend='plotly').plot_multiline().add_slider()
>>> write_fit_html(fig, "output.html", side_html=panel_html, title="压电极化测试")
"""
from __future__ import annotations

import html
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import plotly.graph_objects as go

SHELL_TEMPLATE = Path(__file__).parent / "templates" / "ppt_fit_shell.html"


def figure_size(fig: go.Figure) -> tuple[int, int]:
    """
    从布局及其模板读取图形的固定像素尺寸 ``(宽, 高)``。

    Raises
    ------
    ValueError
        布局和模板未提供计算所需的宽度或高度。
    """
    layout: dict[str, Any] = fig.layout.to_plotly_json()
    template = layout.get("template") or {}
    template_layout = template.get("layout", {}) if isinstance(template, dict) else {}
    width = layout.get("width") or template_layout.get("width")
    height = layout.get("height") or template_layout.get("height")
    if not (width and height):
        raise ValueError(
            "图需要固定的 width 和 height（在 layout 或 Plotly 模板中设置），才能按固定尺寸缩放"
        )
    return int(width), int(height)


def build_fit_html(
    fig: go.Figure,
    *,
    side_html: str | None = None,
    side_width: int = 300,
    gap: int = 24,
    title: str = "Plotly 图表",
    include_plotlyjs: bool | str = True,
    config: dict | None = None,
) -> str:
    """
    返回完整页面的 HTML 字符串。参数说明见 `write_fit_html`。

    默认关闭 Plotly 的 ``responsive``，由页面容器统一缩放图表和侧栏。
    """
    plot_width, plot_height = figure_size(fig)

    plot_config = {"responsive": False, **(config or {})}
    plot_html = fig.to_html(
        full_html=False, include_plotlyjs=include_plotlyjs, config=plot_config,
    )

    # 侧栏和间距仅在提供侧栏内容时计入容器宽度。
    if side_html:
        canvas_width = plot_width + gap + side_width
        side_block = f'    <div id="fit-side">\n{side_html}\n    </div>'
    else:
        canvas_width, gap, side_block = plot_width, 0, ""

    shell = Template(SHELL_TEMPLATE.read_text(encoding="utf-8"))
    return shell.substitute(
        title=html.escape(title),
        canvas_width=canvas_width,
        canvas_height=plot_height,
        plot_width=plot_width,
        plot_height=plot_height,
        side_width=side_width,
        gap=gap,
        plot_html=plot_html,
        side_block=side_block,
    )


def write_fit_html(
    fig: go.Figure,
    path: str | Path,
    *,
    side_html: str | None = None,
    side_width: int = 300,
    gap: int = 24,
    title: str = "Plotly 图表",
    include_plotlyjs: bool | str = True,
    config: dict | None = None,
) -> Path:
    """
    导出随窗口等比缩放的 HTML 文件。

    Parameters
    ----------
    fig : `plotly.graph_objects.Figure`
        具有固定像素宽度和高度的图形。尺寸可以在布局或 Plotly 模板中设置。
    path : str or Path
        输出文件路径。
    side_html : str, optional
        右侧面板的 HTML 片段，可包含 ``<style>`` 和 ``<script>``。
        面板脚本可通过 ``.plotly-graph-div`` 选择图形。
    side_width : int, default: 300
        面板宽度（逻辑像素）。
    gap : int, default: 24
        图与面板之间的间距（逻辑像素）。
    title : str, default: 'Plotly 图表'
        网页标题。写入时转换为 HTML 文本。
    include_plotlyjs : bool or str, default: True
        ``True`` 将 Plotly.js 内嵌到文件中，支持离线打开。``'cdn'`` 从 CDN 加载。
    config : dict, optional
        传递给 Plotly 的配置，可覆盖默认的 ``{"responsive": False}``。

    Returns
    -------
    Path
        写出的文件路径。

    Raises
    ------
    ValueError
        图没有固定的 width / height。

    Examples
    --------
    >>> fig = DataPlotter(data, backend='plotly').plot_xy().add_page_slider()
    >>> write_fit_html(fig, 'nyquist.html', title='Nyquist')
    """
    path = Path(path)
    page = build_fit_html(
        fig,
        side_html=side_html,
        side_width=side_width,
        gap=gap,
        title=title,
        include_plotlyjs=include_plotlyjs,
        config=config,
    )
    path.write_text(page, encoding="utf-8")
    return path
