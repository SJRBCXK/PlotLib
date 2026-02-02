
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))




import matplotlib.pyplot as plt

from src.dataloader import Dataloader
from src.dataset import DataSet
from src.plotter import DataPlotter
from src.processor import DataProcessLayer as DPL
from src.processor import DataTransformer as DT
from src.formatters import make_axes_formatter, make_lines_formatter, make_legend_formatter

INPUT_COLUMNS_PER_DATASET = 8  # 每组数据集的列数
INPUT_DATASET_FRACTION = 1/INPUT_COLUMNS_PER_DATASET

data = Dataloader(
    DATASET_FRACTION = INPUT_DATASET_FRACTION,
    COLUMNS_PER_DATASET = INPUT_COLUMNS_PER_DATASET
).load_data()

# 选择第1组和第3组
Group = [0,2,1,8,7]
Group2 = [3,4,5,6,9]

selected_data = DPL(dataset=data).select('Group1',Group,'Group2',Group2).by("Zs'(ohm)","Zs''(ohm)") #type: ignore
impendence = DataSet()

for dataslice in selected_data.Selected_data.iter('groups'): #type: ignore
    impendence_slice = DT(dataslice).Norm(extended=False) #type: ignore
    impendence.expandata(impendence_slice)

print(selected_data.Selected_data.names) #type: ignore
print(selected_data.Selected_data.units) #type: ignore
print(selected_data.Selected_data.groups_idx) #type: ignore
print(selected_data.Selected_data.group_local_idx) #type: ignore
print(selected_data.Selected_data.father_idx) #type: ignore
print(selected_data.Selected_data.initial_idx) #type: ignore
print(selected_data.Selected_data.column[-1])#type: ignore
print(impendence.groups_idx) #type: ignore
# print(impendence.column[-1])#type: ignore