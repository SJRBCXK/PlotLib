import matplotlib.pyplot as plt
import numpy as np


from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.dataset import DataSet
from plotlib.processor import DataProcessLayer as DPL
from plotlib.processor import DataTransformer as DT
from plotlib.formatters import make_axes_formatter
from plotlib.plot_spec import AxisStyle

plt.close('all')

COLUMNS_PER_SAMPLE = 5  # 每个样品的列数（含 1 列标识）

dataRowNum_unit1 = 0  
dataRowNum_unit2 = 1  
dataRowNum_unit3 = 2  
dataRowNum_unit4 = 3  


Tensile_formatter = make_axes_formatter(
    x=AxisStyle(scale='linear', format='{x:.2f}'),
    y=AxisStyle(scale='linear', format='{y:.2f}'),
)


data = Dataloader(columns_per_sample=COLUMNS_PER_SAMPLE).load_data()


def cal_EB(data):
    """计算断裂伸长率：从强度峰值向后搜索应力下降拐点，返回对应应变"""
    # 过滤 NaN 行（不同组行数不同时 expandata 会补 NaN）
    mask = ~np.isnan(data).any(axis=1)
    data = data[mask]

    strain = data[:, 0]
    stress = data[:, 1]

    position = np.argmax(stress)

    print(f"峰值位置: {position}, 峰值应力: {stress[position]:.2f} MPa, 峰值应变: {strain[position]:.2f}%")

    while position < len(stress) - 1:
        k = abs(stress[position] - stress[position + 1]) - stress[position + 1]
        if k > 0:
            break
        position += 1

    return np.array([[strain[position]]])


Selected_data = DPL(data).select("应变","应力(MPa)").Selected_data
EB_data = DataSet()
for dataslice in Selected_data:
    EB_slice = DT(dataslice).apply(func = cal_EB)
    EB_data.expandata(EB_slice)
print(EB_data.data)
print(EB_data.names)


Tensile = DataPlotter(
    dataset=data,
).plot_xy(
    channel_x=2,
    channel_y=1,
    axes_formatter=Tensile_formatter
)

    
plt.show()


