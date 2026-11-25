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
from plotlib.formatters import make_axes_formatter, make_legend_formatter, make_scatter_formatter
from plotlib.plot_spec import AxesFormatter, AxisStyle, Layer, LegendStyle, ScatterStyle
from plotlib.group import Group

plt.close('all')

# ============================================================
# 数据配置常量
# ============================================================
COLUMNS_PER_SAMPLE = 10  # 每个样品的列数（含 1 列标识）

# 通道编号从 0 开始。
dataRowNum_unit1 = 0  # Frequency
dataRowNum_unit2 = 1  # Permittivity'
dataRowNum_unit3 = 2  # Permittivity''
dataRowNum_unit4 = 3  # Conductivity'
dataRowNum_unit5 = 4  # Conductivity''
dataRowNum_unit6 = 5  # Zp'
dataRowNum_unit7 = 6  # Zp''
dataRowNum_unit8 = 7  # Tan Delta
dataRowNum_unit9 = 8  # Tan Phi

# 分组配置，供 plot(by='group') 使用。
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
data = Dataloader(columns_per_sample=COLUMNS_PER_SAMPLE).load_data()
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
).plot(formatters=AxesFormatter(axes=Bode_Delta_formatter))

Bode_Plotter_TanDelta_group = DataPlotter(
    dataset=data,
    channel_x=dataRowNum_unit1,
    channel_y=dataRowNum_unit8,
    groups=groups
).plot(by='group', formatters=AxesFormatter(axes=Bode_Delta_formatter, lines=Group_lines_formatter))




# ============================================================
# 使用 Group.apply() 按组计算
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
).plot(formatters=AxesFormatter(axes=NegLog_formatter))



Selected_data = DPL(dataset=data).select("Conductivity'(S/cm)", "Conductivity''(S/cm)").Selected_data
Conductivity = DataSet()
for dataslice in Selected_data:
    conductivity_slice = DT(dataslice).Norm(extended=False,norm_unit='|C|(S/cm)')
    Conductivity.expandata(conductivity_slice)
data = data.expandata(Conductivity).sort_columns()
Conductivity_pltliner1 = DataPlotter(
    dataset=data,
    channel_x = 0,
    channel_y = 9
).plot(formatters=AxesFormatter(axes=NegLog_formatter))




def f_peak(data):
    result_data_indice,_= sp.signal.find_peaks(data[:,0].ravel())
    result_tan_values = data[result_data_indice,0].ravel()
    result_freq_values = data[result_data_indice,1].ravel()
    result_data = np.vstack((result_tan_values, result_freq_values)).T
    
    return  result_data


Selected_data = DPL(dataset=data).select("Tan(Delta)","Frequency(Hz)").Selected_data
f_delta_peak = DataSet()
for dataslice in Selected_data:
    # 结果的名字用原样品名、单位写明两个计算结果（柱状图的图例就是这两个单位）；
    # 不写时自动命名为 Results_0_of_样品名、unitless_0 / unitless_1
    f_delta_peak_slice = DT(dataslice).apply(
        func=f_peak,
        extended=False,
        naming_func=lambda: {'names': [dataslice.names[0]] * 2, 'units': ['Peak tan δ', 'Peak frequency (Hz)']},
    )
    f_delta_peak.expandata(f_delta_peak_slice)

# 汇总图每行对应一个原始样品，保留按输入行顺序检出的第一个峰。
peak_sample_names = f_delta_peak.names[::2]
peak_sample_positions = np.arange(len(peak_sample_names))
first_peaks = f_delta_peak.data[0].reshape(-1, 2)
peak_summary = DataSet().form_array(
    data=np.column_stack((peak_sample_positions, first_peaks)),
    name=['Loss peaks'] * 3,
    unit=['', 'Peak tan δ', 'Peak frequency (Hz)'],
    sample_idx=0,
    repeat_times=3,
)


def format_peak_summary(fig, axes):
    """在共享 X 轴上显示样品标签。"""
    axes['left'].set_xticks(peak_sample_positions, peak_sample_names, fontsize=11, rotation=45, ha='right')
    fig.tight_layout()


peak_plotter = DataPlotter(peak_summary).plot(
    [Layer(0, 1, kind='scatter'), Layer(0, 2, kind='scatter', side='right')],
    by='sample',
    formatters={
        'left': AxesFormatter(scatter=make_scatter_formatter(ScatterStyle(marker='circle', size=10))),
        'right': AxesFormatter(axes=make_axes_formatter(y=AxisStyle(scale='log')),
                               scatter=make_scatter_formatter(ScatterStyle(marker='x', size=10))),
    },
    figure_formatter=format_peak_summary,
    legend_title=None,
)


# 同一份损耗峰汇总的柱状图模式：每个样品一组柱，两个计算结果（峰值 tan δ、峰频率）各一根，图例是两者的单位。
# 一个样品可能检出多个峰，reduce='first' 取按行顺序的第一个（与上面的汇总图一致）。
# 两者量级相差很大（tan δ 约 0.1，频率 1e3～1e6），Y 轴用对数，矮的那组柱才看得见；单位不同，Y 轴标题自动留空。
def rotate_sample_labels(fig, axes):
    """样品名较长：X 轴刻度文字斜放，再收紧边距。"""
    ax = axes['left']
    ax.tick_params(axis='x', labelrotation=45, labelsize=11)
    for label in ax.get_xticklabels():
        label.set_horizontalalignment('right')
    fig.tight_layout()


peak_bars = DataPlotter(f_delta_peak).plot_bars(
    [0, 1],
    reduce='first',
    formatters=AxesFormatter(
        axes=make_axes_formatter(y=AxisStyle(scale='log')),
        legend=make_legend_formatter(LegendStyle(position='best')),     # 默认右上角会压住最高的柱
    ),
    figure_formatter=rotate_sample_labels,
)


plt.show()
