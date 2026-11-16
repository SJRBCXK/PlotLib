from pathlib import Path

from plotlib.dataloader import Dataloader
from plotlib.interactive import InteractivePlotter
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

axes_fmt = make_axes_formatter(backend = backend, xlim_left = 0.001, ylim_top = 0.002, xscale_type = 'log')






data = Dataloader(
    DATASET_FRACTION = INPUT_DATASET_FRACTION,
    COLUMNS_PER_DATASET = INPUT_COLUMNS_PER_DATASET
).load_data()




interactive_plot = InteractivePlotter(plot_data_group=None,
                                    input_dataset=data, 
                                    plotrange=300, 
                                    plotdataRowNum_x=dataRowNum_unit3,
                                    plotdataRowNum_y=dataRowNum_unit5,
                                    )  # Replace 'None' with the appropriate group if needed
fig = interactive_plot.plot_plotly_object(figure_formatter=axes_fmt).add_slider(mode="cumulative")

# 导出可随窗口等比缩放的页面（PPT 中嵌入不会出现滚动条），右侧附压缩示意图
OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)
write_fit_html(
    fig, OUTPUT_HTML,
    side_html=PANEL_HTML.read_text(encoding="utf-8"),
    title="压电极化测试",
)
