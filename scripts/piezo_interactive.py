from pathlib import Path

from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.plot_spec import AxisStyle, TickStyle
from plotlib.html_export import write_fit_html

# 右侧压缩示意图面板（含 rev 翻转规则），导出时拼进页面
PANEL_HTML = Path(__file__).parent / "assets" / "piezo_panel.html"
# 导出的页面写到当前目录下的 output/（已加入 .gitignore）
OUTPUT_HTML = Path("output") / "output.html"


COLUMNS_PER_SAMPLE = 6  # 每个样品的列数（含 1 列标识）


dataRowNum_unit1 = 0  # Time for displacement
dataRowNum_unit2 = 1  # Force
dataRowNum_unit3 = 2  # Displacement
dataRowNum_unit4 = 3  # Time for voltage
dataRowNum_unit5 = 4  # Voltage


backend = "plotly"

# X 轴（频率）用对数轴、刻度文字写成科学计数法；次刻度不写文字（Plotly 下主刻度只放在整数量级，
# 跨很多数量级嫌挤时可在 custom 里设 fig.update_xaxes(dtick=2)，见 AxisStyle.format 的说明）
axes_fmt = make_axes_formatter(
    x=AxisStyle(scale='log', limits=(0.001, None), format='{x:.0e}'),
    y=AxisStyle(limits=(None, 0.002)),
    ticks=TickStyle(minor_labels='none'),
    backend=backend,

)






data = Dataloader(columns_per_sample=COLUMNS_PER_SAMPLE).load_data()




interactive_plot = DataPlotter(dataset=data,
                               plotrange=300,
                               channel_x=dataRowNum_unit3,
                               channel_y=dataRowNum_unit5,
                               backend=backend,
                               )
fig = interactive_plot.plot_multiline(axes_formatter=axes_fmt).add_slider(mode="cumulative")

# 导出可随窗口等比缩放的页面（PPT 中嵌入不会出现滚动条），右侧附压缩示意图
OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
write_fit_html(
    fig, OUTPUT_HTML,
    side_html=PANEL_HTML.read_text(encoding="utf-8"),
    title="压电极化测试",
)
