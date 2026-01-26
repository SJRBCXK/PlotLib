"""
Piezo 压电数据绘图脚本
用途：绘制压电测试数据的多种图表（D-V, F-V, T-V 关系图及其组合）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))




import matplotlib.pyplot as plt

from src.dataloader import Dataloader
from src.plotter import DataPlotter
from src.formatters import make_axes_formatter, make_lines_formatter, make_legend_formatter

plt.close('all')

# ============================================================
# 数据配置常量
# ============================================================
INPUT_COLUMNS_PER_DATASET = 6  # 每组数据集的列数
INPUT_DATASET_FRACTION = 1/INPUT_COLUMNS_PER_DATASET

# 数据列索引定义（从0开始）
dataRowNum_unit1 = 0  # Time for displacement
dataRowNum_unit2 = 1  # Force
dataRowNum_unit3 = 2  # Displacement
dataRowNum_unit4 = 3  # Time for voltage
dataRowNum_unit5 = 4  # Voltage

# 数据分组配置（用于 group_plotter）
data_groups = {
    '1th': {'num': [0, 1, 2], 'linestyle': "-"},
    '2st': {'num': [7, 8, 9], 'linestyle': "--"}
}

# ============================================================
# 格式化器配置
# ============================================================
# Displacement-Voltage 格式化器
DV_axes_formatter = make_axes_formatter(
    xlim_left=0.0001, yscaler=10, x_format='{x:.1e}', y_format='{y:.1e}'
)
DV_axes_formatter_log = make_axes_formatter(
    xlim_left=0.001, xscale_type='log', yscaler=10, x_format='{x:.1e}', y_format='{y:.1e}'
)

# Force-Voltage 格式化器
FV_axes_formatter = make_axes_formatter(
    xlim_left=0.1, yscaler=10, x_format='{x:.1e}', y_format='{y:.1e}'
)
FV_axes_formatter_log = make_axes_formatter(
    xlim_left=0.1, xscale_type='log', yscaler=10, x_format='{x:.1e}', y_format='{y:.1e}'
)

# Time-Voltage 格式化器
TV_axes_formatter = make_axes_formatter(
    xlim_left=-5, yscaler=10, x_format='{x:.1e}', y_format='{y:.1e}'
)
TV_axes_formatter_zoomed = make_axes_formatter(
    xlim_left=0, xscale_type='linear', yscaler=10, x_format='{x:.1e}', y_format='{y:.1e}'
)

# ============================================================
# 数据加载
# ============================================================
data = Dataloader(
    DATASET_FRACTION = INPUT_DATASET_FRACTION,
    COLUMNS_PER_DATASET = INPUT_COLUMNS_PER_DATASET
).load_data()

# ============================================================
# 绘图部分
# ============================================================
# --- Displacement-Voltage (D-V) 关系图 ---
DV_pltliner = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit3,
    plotdataRowNum_y = dataRowNum_unit5,
).plot_lines(axes_formatter=DV_axes_formatter)

DV_pltliner_log = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit3,
    plotdataRowNum_y = dataRowNum_unit5,
).plot_lines(axes_formatter=DV_axes_formatter_log)

# --- Time-Voltage (T-V) 关系图 ---
TV_Zoomed_pltliner = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit4,
    plotdataRowNum_y = dataRowNum_unit5
).plot_lines(axes_formatter=TV_axes_formatter_zoomed)

TV_pltliner = DataPlotter(
    input_dataset=data,#type: ignore
    plotdataRowNum_x = dataRowNum_unit4,
    plotdataRowNum_y = dataRowNum_unit5
).plot_lines(axes_formatter=TV_axes_formatter)

# --- Force-Voltage (F-V) 关系图 ---
FV_pltliner = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit2,
    plotdataRowNum_y = dataRowNum_unit5
).plot_lines(axes_formatter=FV_axes_formatter)

FV_pltliner_log = DataPlotter(
    input_dataset=data, #type: ignore
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit2,
    plotdataRowNum_y = dataRowNum_unit5
).plot_lines(axes_formatter=FV_axes_formatter_log)

# --- 分组绘图 (Group Plots) ---
DV_pltGliner2 = DataPlotter(
    input_dataset=data,#type: ignore
    plot_data_groups=data_groups,
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit3,
    plotdataRowNum_y = dataRowNum_unit5
).group_plotter(axes_formatter=DV_axes_formatter)

DV_pltGliner2_merged = DataPlotter(
    input_dataset=data,#type: ignore
    plot_data_groups=data_groups,
    plotrange=299,
    plotdataRowNum_x = dataRowNum_unit2,
    plotdataRowNum_y = dataRowNum_unit5
).group_plotter(axes_formatter=DV_axes_formatter, merge_groups=True)

# --- Y-Y 子图（一个Y对另一个Y）---
DV_pltsubsyy = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299
).subplotter_yy(
    plotdataRowNum_Y1=dataRowNum_unit3,
    plotdataRowNum_Y2=dataRowNum_unit5,
)

FV_pltsubsyy = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299
).subplotter_yy(
    plotdataRowNum_Y1=dataRowNum_unit2,
    plotdataRowNum_Y2=dataRowNum_unit5,
)

# --- X-YY 双轴子图（两个Y共享一个X）---
DTV_pltsubsxyy = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299
).subplotter_xyy(
    plotdataRowNum_X1=dataRowNum_unit1,
    plotdataRowNum_Y1=dataRowNum_unit3,
    plotdataRowNum_X2=dataRowNum_unit4,
    plotdataRowNum_Y2=dataRowNum_unit5,
)

FTV_pltsubsxyy = DataPlotter(
    input_dataset=data,#type: ignore
    plotrange=299
).subplotter_xyy(
    plotdataRowNum_X1=dataRowNum_unit1,
    plotdataRowNum_Y1=dataRowNum_unit2,
    plotdataRowNum_X2=dataRowNum_unit4,
    plotdataRowNum_Y2=dataRowNum_unit5,

)

plt.show()