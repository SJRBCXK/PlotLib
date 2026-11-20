"""
Piezo 压电数据绘图脚本
用途：绘制压电测试数据的多种图表（D-V, F-V, T-V 关系图及其组合）
"""
import matplotlib.pyplot as plt

from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.plot_spec import AxisStyle
from plotlib.group import Group

plt.close('all')

# ============================================================
# 数据配置常量
# ============================================================
COLUMNS_PER_SAMPLE = 6  # 每个样品的列数（含 1 列标识）

# 数据列索引定义（从0开始）
dataRowNum_unit1 = 0  # Time for displacement
dataRowNum_unit2 = 1  # Force
dataRowNum_unit3 = 2  # Displacement
dataRowNum_unit4 = 3  # Time for voltage
dataRowNum_unit5 = 4  # Voltage

# 数据分组配置（用于 plot_groups）
data_groups = {
    '1st': {'num': [0, 1, 2], 'linestyle': 'solid'},
    '2nd': {'num': [7, 8, 9], 'linestyle': 'dash'}
}

# ============================================================
# 格式化器配置
# ============================================================
# Displacement-Voltage 格式化器
DV_axes_formatter = make_axes_formatter(
    x=AxisStyle(limits=(0.0001, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),
)
DV_axes_formatter_log = make_axes_formatter(
    x=AxisStyle(scale='log', limits=(0.001, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),
)

# Force-Voltage 格式化器
FV_axes_formatter = make_axes_formatter(
    x=AxisStyle(limits=(0.1, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),
)
FV_axes_formatter_log = make_axes_formatter(
    x=AxisStyle(scale='log', limits=(0.1, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),
)

# Time-Voltage 格式化器
TV_axes_formatter = make_axes_formatter(
    x=AxisStyle(limits=(-5, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),
)
TV_axes_formatter_zoomed = make_axes_formatter(
    x=AxisStyle(scale='linear', limits=(0, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),
)

# ============================================================
# 数据加载
# ============================================================
data = Dataloader(columns_per_sample=COLUMNS_PER_SAMPLE).load_data()
groups = Group(data, data_groups)   # 分组只建一次：创建时校验，下面的绘图都用它

# ============================================================
# 绘图部分
# ============================================================
# --- Displacement-Voltage (D-V) 关系图 ---
DV_pltliner = DataPlotter(
    dataset=data,
    plotrange=299,
    channel_x = dataRowNum_unit3,
    channel_y = dataRowNum_unit5,
).plot_multiline(axes_formatter=DV_axes_formatter)

DV_pltliner_log = DataPlotter(
    dataset=data,
    plotrange=299,
    channel_x = dataRowNum_unit3,
    channel_y = dataRowNum_unit5,
).plot_multiline(axes_formatter=DV_axes_formatter_log)

# --- Time-Voltage (T-V) 关系图 ---
TV_Zoomed_pltliner = DataPlotter(
    dataset=data,
    plotrange=299,
    channel_x = dataRowNum_unit4,
    channel_y = dataRowNum_unit5
).plot_multiline(axes_formatter=TV_axes_formatter_zoomed)

TV_pltliner = DataPlotter(
    dataset=data,
    channel_x = dataRowNum_unit4,
    channel_y = dataRowNum_unit5
).plot_multiline(axes_formatter=TV_axes_formatter)

# --- Force-Voltage (F-V) 关系图 ---
FV_pltliner = DataPlotter(
    dataset=data,
    plotrange=299,
    channel_x = dataRowNum_unit2,
    channel_y = dataRowNum_unit5
).plot_multiline(axes_formatter=FV_axes_formatter)

FV_pltliner_log = DataPlotter(
    dataset=data,
    plotrange=299,
    channel_x = dataRowNum_unit2,
    channel_y = dataRowNum_unit5
).plot_multiline(axes_formatter=FV_axes_formatter_log)

# --- 分组绘图 (Group Plots) ---
DV_pltGliner2 = DataPlotter(
    dataset=data,
    groups=groups,
    plotrange=299,
    channel_x = dataRowNum_unit3,
    channel_y = dataRowNum_unit5
).plot_groups(axes_formatter=DV_axes_formatter)

DV_pltGliner2_merged = DataPlotter(
    dataset=data,
    groups=groups,
    plotrange=299,
    channel_x = dataRowNum_unit2,
    channel_y = dataRowNum_unit5
).plot_groups(axes_formatter=DV_axes_formatter, merge_groups=True)

# --- Y-Y 子图（一个Y对另一个Y）---
DV_pltsubsyy = DataPlotter(
    dataset=data,
    plotrange=299
).plot_xy(
    channel_x=dataRowNum_unit3,
    channel_y=dataRowNum_unit5,
    axes_formatter=DV_axes_formatter
)

FV_pltsubsyy = DataPlotter(
    dataset=data,
    plotrange=299
).plot_xy(
    channel_x=dataRowNum_unit2,
    channel_y=dataRowNum_unit5,
    axes_formatter=FV_axes_formatter
)

# --- X-YY 双轴子图（两个Y共享一个X）---
DTV_pltsubsxyy = DataPlotter(
    dataset=data,
    plotrange=299,
).plot_dual_y(
    left=(dataRowNum_unit1, dataRowNum_unit3),
    right=(dataRowNum_unit4, dataRowNum_unit5),

)

FTV_pltsubsxyy = DataPlotter(
    dataset=data,
    plotrange=299
).plot_dual_y(
    left=(dataRowNum_unit1, dataRowNum_unit2),
    right=(dataRowNum_unit4, dataRowNum_unit5),

)

plt.show()