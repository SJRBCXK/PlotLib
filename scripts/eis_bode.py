"""
EIS 介电谱 Bode 图脚本
用途：绘制损耗角正切 tan δ 随频率变化的 Bode 图（全部组 / 分组），
      计算各组内的电导率比与电导率模 |C| 并绘图，以及提取各组 tan δ 损耗峰及其对应频率
"""



import matplotlib.pyplot as plt
import numpy as np
import scipy as sp


from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.dataset import DataSet
from plotlib.processor import DataProcessLayer as DPL
from plotlib.processor import DataTransformer as DT
from plotlib.formatters import make_axes_formatter
from plotlib.plot_spec import AxisStyle
from plotlib.group import Group

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

# 数据分组配置（用于 plot_groups）
# 样式用标准写法（style.py）：线型 'solid' / 'dash' / 'dot' / 'dashdot'，或自定义虚线 (实线长, 空白长)
data_groups = {
    '1st': {'num': [0, 1], 'linestyle': 'solid'},
    '2nd': {'num': [2, 3], 'linestyle': 'dash'},
    '3rd': {'num': [4, 5], 'linestyle': 'dashdot'},
    '4th': {'num': [6, 7], 'linestyle': 'dot'},
    '5th': {'num': [8, 9], 'linestyle': (3, 5)},
    '6th': {'num': [10, 11], 'linestyle': (5, 7)},
    '7th': {'num': [12, 13], 'linestyle': (7, 9)},
    '8th': {'num': [14, 15], 'linestyle': (3, 11)},
    '9th': {'num': [16, 17], 'linestyle': (5, 5)},
    # '10th': {'num': [18, 19], 'linestyle': (7, 7)},
    # '11th': {'num': [20, 21], 'linestyle': (3, 9)},
    # '12th': {'num': [22, 23], 'linestyle': (5, 11)}
}

# ============================================================
# 格式化器配置
# ============================================================
Bode_Delta_formatter = make_axes_formatter(
    x=AxisStyle(scale='log', format='{x:.1e}'),
    y=AxisStyle(scale='linear', format='{y:.1f}'),
)

NegLog_formatter = make_axes_formatter(
    x=AxisStyle(scale='log', format='{x:.1e}'),
    y=AxisStyle(scale='log', format='{y:.2e}'),
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
groups = Group(data, data_groups)   # 分组只建一次：创建时校验，下面的绘图和计算都用它

# ============================================================
# 数据处理
# ============================================================





# ============================================================
# 绘图配置
# ============================================================

Bode_Plotter_TanDelta = DataPlotter(
    dataset=data,
    channel_x=dataRowNum_unit1,
    channel_y=dataRowNum_unit8
).plot_multiline(axes_formatter=Bode_Delta_formatter)

Bode_Plotter_TanDelta_group = DataPlotter(
    dataset=data,
    channel_x=dataRowNum_unit1,
    channel_y=dataRowNum_unit8,
    groups=groups
).plot_groups(    
    axes_formatter=Bode_Delta_formatter,
    lines_formatter=Group_lines_formatter)




# ============================================================
# 使用 Group.apply() 重构的分组计算
# ============================================================


def rev_camp(*slices):
    camp = slices[1].data[:,:2] / slices[0].data[:,:2]
    freq = slices[0].data[:,2].reshape(-1, 1)  # 假设频率在第三列
    camp_with_freq = np.hstack((camp, freq))
    return camp_with_freq



RevCampdata_v2 = groups.apply(
    rev_camp,
    select=("Conductivity'(S/cm)", "Conductivity''(S/cm)", "Frequency(Hz)"),
)

RevCampdata_v2_pltsubsyy = DataPlotter(
    dataset=RevCampdata_v2,
    channel_x=2,
    channel_y=1,
).plot_multiline(
    axes_formatter=NegLog_formatter
)



Selected_data = DPL(dataset=data).select("Conductivity'(S/cm)", "Conductivity''(S/cm)").Selected_data
Conductivity = DataSet()
for dataslice in Selected_data.iter('samples'):
    conductivity_slice = DT(dataslice).Norm(extended=False,norm_unit='|C|(S/cm)')
    Conductivity.expandata(conductivity_slice)
data = data.expandata(Conductivity)._rearrange_columns()
Conductivity_pltliner1 = DataPlotter(
    dataset=data,
    channel_x = 0,
    channel_y = 9
).plot_multiline(
    axes_formatter=NegLog_formatter,
)




def f_peak(data):
    result_data_indice,_= sp.signal.find_peaks(data[:,0].ravel())
    result_tan_values = data[result_data_indice,0].ravel()
    result_freq_values = data[result_data_indice,1].ravel()
    result_data = np.vstack((result_tan_values, result_freq_values)).T
    
    return  result_data


Selected_data = DPL(dataset=data).select("Tan(Delta)","Frequency(Hz)").Selected_data
f_delta_peak = DataSet()
for dataslice in Selected_data.iter('samples'):
    f_delta_peak_slice = DT(dataslice).apply(func=f_peak,extended=False)
    f_delta_peak.expandata(f_delta_peak_slice)

fig, ax = plt.subplots()
ax2 = ax.twinx()

x_labels = f_delta_peak.names[0::2]
x = range(len(x_labels))

ax.plot(x, f_delta_peak.data[0, 0::2], 'o', markersize=10)
ax2.plot(x, f_delta_peak.data[0, 1::2], 'x', markersize=10)
ax.set_xticks(x)
ax.set_xticklabels(x_labels, rotation=45, ha='right')
ax2.set_yscale('log')


plt.show()