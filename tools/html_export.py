"""把画好的 Plotly Figure 导出成“随窗口等比缩放”的 HTML 页面（用于 PPT 等嵌入场景）。

这是画图之后的后处理，与 Plotly 模板（图的外观与尺寸）相互独立：
导出只“装框”，对 Figure 只读，不修改图，也不修改模板。

页面由三个零件拼成，只靠三处接头相连：

    外壳（tools/templates/ppt_fit_shell.html）：关滚动条 + 缩放脚本
      └─ #fit-canvas  画框，逻辑尺寸 W × H            ← 接头①：W、H 由图的尺寸算出
           ├─ 图表零件：fig.to_html(full_html=False)  ← 接头②：侧边面板通过 .plotly-graph-div 找到图
           └─ 侧边面板（可选，由调用方传入的 HTML 片段）
      缩放脚本通过 #fit-canvas 找到画框              ← 接头③：外壳内部，已写好

用法：
    from tools.html_export import write_fit_html
    write_fit_html(fig, "output.html", side_html=panel_html, title="压电极化测试")
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
    """读取图的固定像素尺寸 (宽, 高)：先看 layout，再看 layout.template。

    缩放外壳需要知道“原画”多大；没有固定尺寸的图会随容器自适应，无法按固定逻辑尺寸缩放。
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
    """拼出完整页面并返回 HTML 字符串，不写文件。参数含义见 write_fit_html。"""
    plot_width, plot_height = figure_size(fig)

    # 默认关闭 responsive：图保持固定尺寸，只由外壳整体缩放，避免 Plotly 跟随容器重排。
    plot_config = {"responsive": False, **(config or {})}
    plot_html = fig.to_html(
        full_html=False, include_plotlyjs=include_plotlyjs, config=plot_config,
    )

    # 接头①：画框尺寸 = 图 + (间距 + 面板)，高度取图的高度；面板在画框内垂直居中
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
    """导出可随窗口等比缩放的 HTML 文件，返回写出的路径。

    Args:
        fig: 已画好的 Figure，必须有固定的 width / height（layout 或模板中设置）。
        path: 输出文件路径。
        side_html: 可选的右侧面板 HTML 片段（可含自己的 <style>、<script>）；面板脚本可用 document.querySelector(".plotly-graph-div") 找到图。
        side_width: 面板宽度（逻辑像素）。
        gap: 图与面板之间的间距（逻辑像素）。
        title: 网页标题。
        include_plotlyjs: True 把 Plotly.js 内嵌进文件（约 4.5 MB，离线可用，适合 PPT）；"cdn" 改为联网加载。
        config: 额外的 Plotly config，会覆盖默认的 {"responsive": False}。

    Returns:
        写出的文件路径。

    Raises:
        ValueError: 图没有固定的 width / height。
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
