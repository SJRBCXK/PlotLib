from .group import Group
from .dataset import DataSet
import numpy as np





def color_positions(sample_idx):
    
    return {sample: i / (len(set(sample_idx))) for i, sample in enumerate(sorted(set(sample_idx)))}

def resolve_groups(groups: Group | None, dataset: DataSet) -> Group:
    if groups is None:
        # 不分组：用空 Group，后面的代码总是面对一个 Group，不用判断 None
        groups = Group(dataset, {})

    elif not isinstance(groups, Group):
        # 类型标注只在编辑器里提醒，运行时要自己检查，才能给出清楚的报错
        raise TypeError(
            f"groups 必须是 Group 对象，实际是 {type(groups).__name__}；"
            "请先用 Group(input_dataset, config) 创建。"
        )
    elif groups.dataset is not dataset:
        # 用 is 判断「是不是同一个对象」：内容相同的两个数据集也不算
        raise ValueError("groups 是基于另一个数据集创建的；请基于绘图用的数据集创建 Group。")

    return groups

def get_xy_data(dataset: DataSet, sample_idx: int, channel_x: int, channel_y: int,
                neglog_x: bool = False, neglog_y: bool = False, plotrange: int | None = None):
    """取出一个样品的 X、Y 两列，返回 (x, y, x_label, y_label, x_unit, y_unit)。

    neglog 在这里只对数据取绝对值；坐标尺度和刻度文字属于后续格式化，不在这里处理。
    plotrange 是绘图器的设置（只画前几行），None 取全部行。
    """
    Row_x, x_label, x_unit = get_column_data(dataset, sample_idx, channel_x, plotrange)
    Row_y, y_label, y_unit = get_column_data(dataset, sample_idx, channel_y, plotrange)

    if neglog_x:
        Row_x = np.abs(Row_x)
    if neglog_y:
        Row_y = np.abs(Row_y)

    return Row_x, Row_y, x_label, y_label, x_unit, y_unit


def get_column_data(dataset: DataSet, sample_idx: int, channel_idx: int, plotrange: int | None = None):
    """根据样品号和通道号获取列数据，返回 (data, name, unit)。"""
    for column in dataset.column:
        if column.sample_idx == sample_idx and column.channel_idx == channel_idx:
            return column.data[:plotrange], column.name, column.unit
    raise RuntimeError("未找到对应的列数据")