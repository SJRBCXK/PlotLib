from plotlib.dataloader import Dataloader
from plotlib.dataset import DataSet
from plotlib.processor import DataProcessLayer as DPL
from plotlib.processor import DataTransformer as DT

COLUMNS_PER_SAMPLE = 8  # 每个样品的列数（含 1 列标识）

# 选择第1组和第3组
Group = [0,2,1,8,7]
Group2 = [3,4,5,6,9]


def main(path=None, show=True):
    """读取数据，演示选列和逐样品计算并打印结果。*path* 为 None 时弹窗选文件；本脚本不画图，*show* 不起作用。"""
    data = Dataloader(columns_per_sample=COLUMNS_PER_SAMPLE).load_data(path)

    selected_data = DPL(dataset=data).select('samples',Group,'samples',Group2).by("Zs'(ohm)","Zs''(ohm)")
    impendence = DataSet()

    for dataslice in selected_data.Selected_data:
        impendence_slice = DT(dataslice).Norm(extended=False)
        impendence.expandata(impendence_slice)

    print(selected_data.Selected_data.names)
    print(selected_data.Selected_data.units)
    print(selected_data.Selected_data.sample_idx)
    print(selected_data.Selected_data.channel_idx)
    print(selected_data.Selected_data.father_idx)
    print(selected_data.Selected_data.initial_idx)
    print(selected_data.Selected_data.column[-1])
    print(impendence.sample_idx)
    # print(impendence.column[-1])


if __name__ == "__main__":
    main()
