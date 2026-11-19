"""
EIS 电化学阻抗谱绘图脚本
用途：绘制 EIS 数据的 Nyquist 图、Bode 图及双轴图
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator

from plotlib.dataloader import Dataloader
from plotlib.dataset import DataSet
from plotlib.processor import DataProcessLayer as DPL
from plotlib.processor import DataTransformer as DT
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.group import Group

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
    '9th': {'num': [16, 17], 'linestyle': (5, 5)}
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
    xscale_type='log',
    yscale_type='log',
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
groups = Group(data, data_groups)   # 分组只建一次：创建时校验，下面的绘图和计算都用它

# ============================================================
# 绘图部分
# ============================================================
# --- Nyquist 图（标准线图）---
Test_pltliner1 = DataPlotter(
    dataset=data,
    channel_x = dataRowNum_unit6,
    channel_y = dataRowNum_unit7
).plot_multiline(
    axes_formatter=Nyquist_formatter,
    neglog_y=True
)

# --- Nyquist 图（分组绘制）---
Test_pltGliner2 = DataPlotter(
    dataset=data,
    groups=groups,
    channel_x = dataRowNum_unit6,
    channel_y = dataRowNum_unit7
).plot_groups(
    axes_formatter=Nyquist_formatter,
    neglog_y=True,
    merge_groups=False,
    lines_formatter=Group_lines_formatter
)


# --- Y-Y 子图（Real Z vs -Imaginary Z）---
Test_pltsubsyy = DataPlotter(
    dataset=data,
).plot_xy(
    channel_x=dataRowNum_unit6,
    channel_y=dataRowNum_unit7,
    neglog_y=True,
    axes_formatter=NegLog_formatter
)
# 备用方案：使用自定义 eis_log_formatter
# ).plot_xy(
#     channel_x=dataRowNum_unit6,
#     channel_y=dataRowNum_unit7,
#     axes_formatter=eis_log_formatter
# )

# --- X-YY 双轴子图（Frequency vs Z components）---
Test_pltsubsxyy = DataPlotter(
    dataset=data,
).plot_dual_y(
    left=(dataRowNum_unit1, dataRowNum_unit6),
    right=(dataRowNum_unit1, dataRowNum_unit7),
    neglog_y2=True,
    axes_formatter=NegLog_formatter,
    right_axes_formatter=NegLog_formatter,
    # 整图回调 (fig, axes)：axes['right'] 是右轴（原 custom_formatter(ax1, ax2, fig) 的 ax2）
    figure_formatter=lambda _fig, axes: (
        axes['right'].spines['right'].set_visible(True),
        axes['right'].spines['top'].set_visible(True),
        axes['right'].set_xscale('log'),
        axes['right'].yaxis.set_major_formatter(FuncFormatter(lambda y, _: f"{y:.1e}"))
    )
)
# 备用方案：使用自定义 eis_dual_axis_formatter
# ).plot_dual_y(
#     left=(dataRowNum_unit1, dataRowNum_unit6),
#     right=(dataRowNum_unit1, dataRowNum_unit7),
#     figure_formatter=lambda fig, axes: eis_dual_axis_formatter(axes['left'], axes['right'], fig),
# )
Selected_data = DPL(dataset=data).select("Zs'(ohm)","Zs''(ohm)").Selected_data
Impendence = DataSet()
for dataslice in Selected_data.iter('samples'):
    impendence_slice = DT(dataslice).Norm(extended=False,norm_unit='|Z|(ohm)')
    Impendence.expandata(impendence_slice)
data = data.expandata(Impendence)._rearrange_columns()
Impendence_pltliner1 = DataPlotter(
    dataset=data,
    channel_x = 0,
    channel_y = 7
).plot_multiline(
    axes_formatter=Nyquist_formatter,
)





# ============================================================
# 使用 Group.apply() 重构的分组计算
# ============================================================

def rev_camp(*slices):
    camp = slices[1].data[:,:2] - slices[0].data[:,:2]
    freq = slices[0].data[:,2].reshape(-1, 1)  # 假设频率在第三列
    camp_with_freq = np.hstack((camp, freq))
    return camp_with_freq


RevCampdata_v2 = groups.apply(
    rev_camp,
    select=("Zs'(ohm)", "Zs''(ohm)", "Frequency(Hz)")
)
print(RevCampdata_v2.units)

RevCampdata_v2_pltsubsyy = DataPlotter(
    dataset=RevCampdata_v2,
).plot_xy(
    channel_x=2,
    channel_y=1,
    neglog_y=True,
    axes_formatter=NegLog_formatter
)

plt.show()