"""
EIS 电化学阻抗谱绘图脚本
用途：绘制 EIS 数据的 Nyquist 图、Bode 图及双轴图
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator

from src.dataloader import Dataloader
from src.dataset import DataSet
from src.processor import DataProcessLayer as DPL
from src.processor import DataTransformer as DT
from src.plotter import DataPlotter
from src.formatters import make_axes_formatter, make_lines_formatter, make_legend_formatter

plt.close('all')

# ============================================================
# 数据配置常量
# ============================================================
INPUT_COLUMNS_PER_DATASET = 8  # 每组数据集的列数
INPUT_DATASET_FRACTION = 1/INPUT_COLUMNS_PER_DATASET

# 数据列索引定义（从0开始）
dataRowNum_unit1 = 0  # Frequency
dataRowNum_unit2 = 1  # Real Z (实部阻抗)
dataRowNum_unit3 = 2  # Imaginary Z (虚部阻抗)
dataRowNum_unit4 = 3  # |Z| (阻抗模)
dataRowNum_unit5 = 4  # Phase angle (相角)
dataRowNum_unit6 = 5  # Real Z' (for Nyquist)
dataRowNum_unit7 = 6  # Imaginary Z'' (for Nyquist)

# 数据分组配置（用于 group_plotter）
data_groups = {
    '1th': {'num': [0, 1], 'linestyle': "-"},
    '2st': {'num': [2, 3], 'linestyle': "--"},
    '3nd': {'num': [4, 5], 'linestyle': "-."},
    '4rd': {'num': [6, 7], 'linestyle': ":"},
    '5th': {'num': [8, 9], 'linestyle': (0, (3, 5))},
    '6th': {'num': [10, 11], 'linestyle': (0, (5, 7))},
    '7th': {'num': [12, 13], 'linestyle': (0, (7, 9))},
    '8th': {'num': [14, 15], 'linestyle': (0, (3, 11))},
    '9th': {'num': [16, 17], 'linestyle': (0, (5, 5))}
}

# ============================================================
# 格式化器配置
# ============================================================
Nyquist_formatter = make_axes_formatter(
    xscale_type='log',
    yscale_type='log',
    x_format='{x:.1e}',
    y_format='{y:.1e}'
)

NegLog_formatter = make_axes_formatter(
    xscale_type='linear',
    yscale_type='linear',
    x_format='{x:.1e}',
    y_format='{y:.1e}'
)

def Group_lines_formatter(lines):
    """为每条线设置不同的线型"""
    for i, line in enumerate(lines):
        linestyle = ( i, ( 3*(i+1), 5*(i+1) ) )
        line.set_linestyle(linestyle)




# ============================================================
# 自定义格式化函数
# ============================================================
def eis_log_formatter(ax, _fig):
    """EIS 阻抗谱对数坐标格式化器"""
    ax.grid(True, which='major', linestyle='-', alpha=0.5)
    ax.grid(True, which='minor', linestyle=':', alpha=0.3)
    max_value = max(ax.get_ylim()[1], ax.get_xlim()[1])
    min_value = min(ax.get_ylim()[0], ax.get_xlim()[0])
    max_ax_value = max(abs(max_value), abs(min_value))
    ax.set_ylim(bottom=0, top=-max_ax_value)
    ax.set_xlim(left=0, right=max_ax_value)
    ax_formatter = FuncFormatter(lambda y, _: f"{y:.0e}")
    ax.yaxis.set_major_formatter(ax_formatter)
    ax.xaxis.set_major_formatter(ax_formatter)

def eis_dual_axis_formatter(ax1, ax2, _fig):
    """EIS 双轴格式化器 - 统一设置左右轴格式"""
    # X轴设置（对数刻度）
    ax1.set_xscale('log')
    ax1.grid(True, which='both', alpha=0.3)
    ax1.xaxis.set_major_locator(LogLocator(base=10, numticks=15))

    # Y轴格式设置
    y_formatter = FuncFormatter(lambda y, _: f"{y:.0e}")
    ax1.yaxis.set_major_formatter(y_formatter)
    ax2.yaxis.set_major_formatter(y_formatter)

    # Y轴范围设置
    max_value = max(ax1.get_ylim()[1], ax2.get_ylim()[1])
    min_value = min(ax1.get_ylim()[0], ax2.get_ylim()[0])
    ax1.set_ylim(bottom=0, top=max_value)
    ax2.set_ylim(bottom=0, top=min_value)

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
# --- Nyquist 图（标准线图）---
Test_pltliner1 = DataPlotter(
    input_dataset=data,#type: ignore
    plotdataRowNum_x = dataRowNum_unit6,
    plotdataRowNum_y = dataRowNum_unit7
).plot_lines(
    axes_formatter=Nyquist_formatter,
    NegLogScale_y=True
)

# --- Nyquist 图（分组绘制）---
Test_pltGliner2 = DataPlotter(
    input_dataset=data,#type: ignore
    plot_data_groups=data_groups,
    plotdataRowNum_x = dataRowNum_unit6,
    plotdataRowNum_y = dataRowNum_unit7
).group_plotter(
    axes_formatter=Nyquist_formatter,
    NegLogScale_y=True,
    merge_groups=False,
    lines_formatter=Group_lines_formatter
)


# --- Y-Y 子图（Real Z vs -Imaginary Z）---
Test_pltsubsyy = DataPlotter(
    input_dataset=data,#type: ignore
).subplotter_yy(
    plotdataRowNum_Y1=dataRowNum_unit6,
    plotdataRowNum_Y2=dataRowNum_unit7,
    NegLogScale_Y2=True,
    axes_formatter=NegLog_formatter
)
# 备用方案：使用自定义 eis_log_formatter
# ).subplotter_yy(
#     plotdataRowNum_Y1=dataRowNum_unit6,
#     plotdataRowNum_Y2=dataRowNum_unit7,
#     axes_formatter=eis_log_formatter
# )

# --- X-YY 双轴子图（Frequency vs Z components）---
Test_pltsubsxyy = DataPlotter(
    input_dataset=data,#type: ignore
).subplotter_xyy(
    plotdataRowNum_X1=dataRowNum_unit1,
    plotdataRowNum_Y1=dataRowNum_unit6,
    plotdataRowNum_X2=dataRowNum_unit1,
    plotdataRowNum_Y2=dataRowNum_unit7,
    NegLogScale_Y2=True,
    axes_formatter_ax1=NegLog_formatter,
    axes_formatter_ax2=NegLog_formatter,
    custom_formatter=lambda _ax1, ax2, _fig: (
        ax2.spines['right'].set_visible(True),
        ax2.spines['top'].set_visible(True),
        ax2.set_xscale('log'),
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.1e}"))
    )
)
# 备用方案：使用自定义 eis_dual_axis_formatter
# ).subplotter_xyy(
#     plotdataRowNum_X1=dataRowNum_unit1,
#     plotdataRowNum_Y1=dataRowNum_unit6,
#     plotdataRowNum_X2=dataRowNum_unit1,
#     plotdataRowNum_Y2=dataRowNum_unit7,
#     custom_formatter=eis_dual_axis_formatter,
# )
Selected_data = DPL(dataset=data).select("Zs'(ohm)","Zs''(ohm)").Selected_data #type: ignore
Impendence = DataSet()
for dataslice in Selected_data.iter('groups'): #type: ignore
    impendence_slice = DT(dataslice).Norm(extended=False,norm_unit='|Z|(ohm)') #type: ignore
    Impendence.expandata(impendence_slice)
data = data.expandata(Impendence)._rearrange_columns() #type: ignore
Impendence_pltliner1 = DataPlotter(
    input_dataset=data,#type: ignore
    plotdataRowNum_x = 0,
    plotdataRowNum_y = 7
).plot_lines(
    axes_formatter=Nyquist_formatter,
)

RevCampdata = DataSet()
RevCampdata_group_idx = -1
for group_name, group_config in data_groups.items():
    RevCampdata_group_idx += 1
    RevCampdata_slice = DataSet()
    if 'num' not in group_config:
        raise ValueError(f"数据分组配置错误：'{group_name}' 缺少 'num' 键。")
    Group_indices = group_config['num']
    Selected_data_Zs = DPL(dataset=data).select("Group_indices",Group_indices).by("Zs'(ohm)","Zs''(ohm)").Selected_data._rearrange_columns() #type: ignore
    col_indices = {gc:[] for gc in group_config['num']}
    for gc in group_config['num']:
        for i in Selected_data_Zs.local_idx:
            if Selected_data_Zs.groups_idx[i] == gc:
                col_indices[gc].append(i)
                
    idx0 = col_indices[group_config['num'][0]]
    idx1 = col_indices[group_config['num'][1]]
    
    if len(idx0) != len(idx1):
        raise ValueError(f"数据分组配置错误：'{group_name}' 的 'num' 列表中的索引数量不匹配。")
    else:
        repeat_times = range(len(idx0))
    
    RevCampdata_slice.data = Selected_data_Zs.data[:,idx1] - Selected_data_Zs.data[:,idx0]#type: ignore
    RevCampdata_slice.names = ["RevCamp_"+Selected_data_Zs.names[i] + "_" + Selected_data_Zs.names[j] for i, j in zip(idx0, idx1)] #type: ignore
    RevCampdata_slice.units = [Selected_data_Zs.units[i] for i in idx0] #type: ignore
    RevCampdata_slice.groups_idx = [RevCampdata_group_idx for i in repeat_times] #type: ignore
    RevCampdata_slice.father_idx = [None for i in repeat_times]  #type: ignore 
    RevCampdata_slice.initial_idx = [None for i in repeat_times] #type: ignore
    RevCampdata.expandata(RevCampdata_slice)    
    # #type: ignore
RevCampdata_pltsubsyy = DataPlotter(
    input_dataset=RevCampdata,#type: ignore
).subplotter_yy(
    plotdataRowNum_Y1=dataRowNum_unit1,
    plotdataRowNum_Y2=dataRowNum_unit2,
    NegLogScale_Y2=True,
    axes_formatter=NegLog_formatter
)




         #type: ignore
    # RevCampdata_slice =  #type: ignore
    



plt.show()