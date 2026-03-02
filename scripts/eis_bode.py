"""
EIS 电化学阻抗谱绘图脚本
用途：绘制 EIS 数据的 Nyquist 图、Bode 图及双轴图
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator
import numpy as np


from src.dataloader import Dataloader
from src.plotter import DataPlotter
from src.dataset import DataSet
from src.processor import DataProcessLayer as DPL
from src.processor import DataTransformer as DT
from src.formatters import make_axes_formatter, make_lines_formatter, make_legend_formatter

plt.close('all')

# ============================================================
# 数据配置常量
# ============================================================
INPUT_COLUMNS_PER_DATASET = 10  # 每组数据集的列数
INPUT_DATASET_FRACTION = 1/INPUT_COLUMNS_PER_DATASET

# 数据列索引定义（从0开始）
dataRowNum_unit1 = 0  # Frequency
dataRowNum_unit2 = 1  # Permittivity'
dataRowNum_unit3 = 2  # Permittivity''
dataRowNum_unit4 = 3  # Conductivity'
dataRowNum_unit5 = 4  # Conductivity''
dataRowNum_unit6 = 5  # Zp'
dataRowNum_unit7 = 6  # Zp''
dataRowNum_unit8 = 7  # Tan Delta
dataRowNum_unit9 = 8  # Tan Phi

# 数据分组配置（用于 group_plotter）
data_groups = {
    '1th': {'num': [0,1], 'linestyle': "-"},
    '2st': {'num': [2,3], 'linestyle': "--"},
    '3nd': {'num': [4,5], 'linestyle': "-."},
    '4rd': {'num': [6,7], 'linestyle': ":"},
    '5th': {'num': [8,9], 'linestyle': (0, (3, 5))},
    '6th': {'num': [10,11], 'linestyle': (0, (5, 7))},
    '7th': {'num': [12,13], 'linestyle': (0, (7, 9))},
    '8th': {'num': [14,15], 'linestyle': (0, (3, 11))},
    '9th': {'num': [16,17], 'linestyle': (0, (5, 5))}
}

# ============================================================
# 格式化器配置
# ============================================================
Bode_Delta_formatter = make_axes_formatter(
    xscale_type='log',
    yscale_type='linear',
    x_format='{x:.1e}',
    y_format='{y:.1f}'
)

NegLog_formatter = make_axes_formatter(
    xscale_type='log',
    yscale_type='log',
    x_format='{x:.1e}',
    y_format='{y:.2e}'
)

def Group_lines_formatter(lines):
    """为每条线设置不同的线型"""
    for i, line in enumerate(lines):
        linestyle = ( i, ( 3*(i+1), 5*(i+1) ) )
        line.set_linestyle(linestyle)


# ============================================================
# 自定义格式化函数
# ============================================================






# ============================================================
# 数据加载
# ============================================================
data = Dataloader(
    DATASET_FRACTION = INPUT_DATASET_FRACTION,
    COLUMNS_PER_DATASET = INPUT_COLUMNS_PER_DATASET
).load_data()

# ============================================================
# 数据处理
# ============================================================





# ============================================================
# 绘图配置
# ============================================================

Bode_Plotter_TanDelta = DataPlotter(
    input_dataset=data,#type: ignore
    plotdataRowNum_x=dataRowNum_unit1,
    plotdataRowNum_y=dataRowNum_unit8
).plot_lines(axes_formatter=Bode_Delta_formatter)

Bode_Plotter_TanDelta_group = DataPlotter(
    input_dataset=data,#type: ignore
    plotdataRowNum_x=dataRowNum_unit1,
    plotdataRowNum_y=dataRowNum_unit8,
    plot_data_groups=data_groups
).group_plotter(    
    axes_formatter=Bode_Delta_formatter,
    lines_formatter=Group_lines_formatter)




# ============================================================
# 使用 Group.apply() 重构的组间计算
# ============================================================


from src.group import Group

def rev_camp(*slices):
    camp = slices[1].data[:,:2] / slices[0].data[:,:2]
    freq = slices[0].data[:,2].reshape(-1, 1)  # 假设频率在第三列
    camp_with_freq = np.hstack((camp, freq))
    return camp_with_freq



RevCampdata_v2 = Group(data, data_groups).apply(
    rev_camp,
    select=("Conductivity'(S/cm)", "Conductivity''(S/cm)", "Frequency(Hz)"),
)

RevCampdata_v2_pltsubsyy = DataPlotter(
    input_dataset=RevCampdata_v2,#type: ignore
    plotdataRowNum_x=2,
    plotdataRowNum_y=1,
).plot_lines(
    axes_formatter=NegLog_formatter
)

Selected_data = DPL(dataset=data).select("Conductivity'(S/cm)", "Conductivity''(S/cm)").Selected_data #type: ignore
Conductivity = DataSet()
for dataslice in Selected_data.iter('groups'): #type: ignore
    conductivity_slice = DT(dataslice).Norm(extended=False,norm_unit='|C|(S/cm)') #type: ignore
    Conductivity.expandata(conductivity_slice)
data = data.expandata(Conductivity)._rearrange_columns() #type: ignore
Conductivity_pltliner1 = DataPlotter(
    input_dataset=data,#type: ignore
    plotdataRowNum_x = 0,
    plotdataRowNum_y = 9
).plot_lines(
    axes_formatter=NegLog_formatter,
)


plt.show()