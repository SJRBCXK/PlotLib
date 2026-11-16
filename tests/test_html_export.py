"""tools/html_export.py：把 Figure 拼进可缩放的网页外壳；只检查拼出的页面结构，不打开浏览器。"""
import re

import pytest

go = pytest.importorskip("plotly.graph_objects")

from tools.html_export import build_fit_html, figure_size, write_fit_html


def make_fig(**layout):
    return go.Figure(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], name="S0"), layout=layout)


def canvas_size(page: str) -> tuple[int, int]:
    match = re.search(r'id="fit-canvas" data-fit-width="(\d+)" data-fit-height="(\d+)"', page)
    assert match, "页面里没有画框 #fit-canvas"
    return int(match.group(1)), int(match.group(2))


def test_figure_size_from_layout_or_template():
    assert figure_size(make_fig(width=956, height=720)) == (956, 720)
    template = go.layout.Template(layout=dict(width=1200, height=800))
    assert figure_size(make_fig(template=template)) == (1200, 800)
    # layout 显式设置时优先于模板
    assert figure_size(make_fig(template=template, width=500)) == (500, 800)


def test_figure_without_fixed_size_raises():
    with pytest.raises(ValueError, match="固定的 width 和 height"):
        build_fit_html(make_fig(template=go.layout.Template()), include_plotlyjs="cdn")


def test_page_without_side_panel():
    page = build_fit_html(make_fig(width=956, height=720), include_plotlyjs="cdn")
    assert canvas_size(page) == (956, 720)
    assert 'class="plotly-graph-div"' in page
    assert 'id="fit-side"' not in page
    assert "overflow: hidden" in page                  # 不出现滚动条
    assert '"responsive": false' in page               # 图保持固定尺寸，只由外壳缩放


def test_page_with_side_panel():
    side = '<aside id="my-panel">面板</aside>'
    page = build_fit_html(make_fig(width=956, height=720), side_html=side,
                          side_width=300, gap=24, title="压电 <测试>", include_plotlyjs="cdn")
    assert canvas_size(page) == (956 + 24 + 300, 720)
    # 面板在图之后、位于画框内部
    assert page.index('class="plotly-graph-div"') < page.index(side) < page.index("</main>")
    assert "<title>压电 &lt;测试&gt;</title>" in page   # 标题经过转义


def test_no_leftover_placeholders():
    """模板里的占位符必须全部填上；Plotly 自身的 JS 不含 ${...}，可直接检查。"""
    page = build_fit_html(make_fig(width=956, height=720), side_html="<p>x</p>", include_plotlyjs="cdn")
    assert not re.search(r"\$\{?[a-z_]+\}?", page.split("<body>")[0])
    for placeholder in ("${canvas_width}", "${canvas_height}", "$plot_html", "$side_block", "$title"):
        assert placeholder not in page


def test_user_config_overrides_default():
    page = build_fit_html(make_fig(width=956, height=720), include_plotlyjs="cdn",
                          config={"displayModeBar": False})
    assert '"displayModeBar": false' in page
    assert '"responsive": false' in page


def test_write_does_not_modify_figure(tmp_path):
    fig = make_fig(width=956, height=720)
    before = fig.to_json()
    path = write_fit_html(fig, tmp_path / "out.html", side_html="<p>x</p>", include_plotlyjs="cdn")
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert fig.to_json() == before


def test_works_with_interactive_plotter_template(eis_dataset):
    """集成：InteractivePlotter 的模板尺寸（1200 × 800）直接决定画框尺寸。"""
    from src.interactive import InteractivePlotter

    fig = InteractivePlotter(None, eis_dataset).plot_plotly_object().add_slider()
    page = build_fit_html(fig, side_html="<p>x</p>", include_plotlyjs="cdn")
    assert canvas_size(page) == (1200 + 24 + 300, 800)
