from plotlib.dataloader import Dataloader
from plotlib.dataset import DataSet
from plotlib.processor import DataProcessLayer as DPL
from plotlib.processor import DataTransformer as DT

INPUT_COLUMNS_PER_DATASET = 8  # 每组数据集的列数
INPUT_DATASET_FRACTION = 1/INPUT_COLUMNS_PER_DATASET

data = Dataloader(
    DATASET_FRACTION = INPUT_DATASET_FRACTION,
    COLUMNS_PER_DATASET = INPUT_COLUMNS_PER_DATASET
).load_data()

# 选择第1组和第3组
Group = [0,2,1,8,7]
Group2 = [3,4,5,6,9]

selected_data = DPL(dataset=data).select('Group1',Group,'Group2',Group2).by("Zs'(ohm)","Zs''(ohm)")
impendence = DataSet()

for dataslice in selected_data.Selected_data.iter('groups'):
    impendence_slice = DT(dataslice).Norm(extended=False)
    impendence.expandata(impendence_slice)

print(selected_data.Selected_data.names)
print(selected_data.Selected_data.units)
print(selected_data.Selected_data.groups_idx)
print(selected_data.Selected_data.group_local_idx)
print(selected_data.Selected_data.father_idx)
print(selected_data.Selected_data.initial_idx)
print(selected_data.Selected_data.column[-1])
print(impendence.groups_idx)
# print(impendence.column[-1])