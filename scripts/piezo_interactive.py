from pathlib import Path

from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.html_export import write_fit_html

# 右侧压缩示意图面板（含 rev 翻转规则），导出时拼进页面
PANEL_HTML = Path(__file__).parent / "assets" / "piezo_panel.html"
# 导出的页面写到当前目录下的 output/（已加入 .gitignore）
OUTPUT_HTML = Path("output") / "output.html"


INPUT_COLUMNS_PER_DATASET = 6  # 每组数据集的列数
INPUT_DATASET_FRACTION = 1/INPUT_COLUMNS_PER_DATASET


dataRowNum_unit1 = 0  # Time for displacement
dataRowNum_unit2 = 1  # Force
dataRowNum_unit3 = 2  # Displacement
dataRowNum_unit4 = 3  # Time for voltage
dataRowNum_unit5 = 4  # Voltage


backend = "plotly"

# 多线图的默认刻度是两位小数（排版预设），对数轴上的 0.001 会显示成 0.00，所以 X 轴写明科学计数法
axes_fmt = make_axes_formatter(backend = backend, xlim_left = 0.001, ylim_top = 0.002, xscale_type = 'log',
                               x_format = '{x:.0e}')






data = Dataloader(
    DATASET_FRACTION = INPUT_DATASET_FRACTION,
    COLUMNS_PER_DATASET = INPUT_COLUMNS_PER_DATASET
).load_data()




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
