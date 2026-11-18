from collections.abc import Callable
from dataclasses import dataclass
from functools import partial

import numpy as np

from .dataset import DataSet
from .group import Group





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


# ============================================================================
# 绘图计划（STRUCTURE_REVIEW 步骤 6.1）
#   只做「决定」：画几张图、每张图有哪些线、每条线的数据 / 标签 / 颜色 / 样式。
#   不导入任何绘图库；matplotlib 和 Plotly 照着同一份计划画，分组规则只写这一次。
#   计划保持「薄」：坐标范围、刻度、字体、图例位置不放进来，那是默认格式和 formatter 的事。
# ============================================================================

@dataclass
class CurveSpec:
    """一条线。颜色存色带位置、样式存标准写法，翻译成具体颜色值 / 原生写法是后端的事。"""
    sample_idx: int
    x: np.ndarray
    y: np.ndarray
    label: str                  # 图例文字，现在是样品名
    x_unit: str
    y_unit: str
    group_name: str | None      # 不分组时为 None
    color_position: float       # 默认颜色在色带上的位置（合并模式已换成组首位置）
    style: dict                 # 分组写了的样式（标准写法）；没写的不出现


@dataclass
class FigureSpec:
    """一张图。curves 的顺序就是画线顺序，也就是图例顺序。"""
    key: str                    # 分组名，或 'main'
    curves: list[CurveSpec]


# make_curve 的类型：给出「样品号、分组名、色带位置、样式」，返回一条线
type MakeCurve = Callable[[int, str | None, float, dict], CurveSpec]


def plan_figures(dataset: DataSet, groups: Group | None, channel_x: int, channel_y: int, *,
                 merge_groups: bool = False, plotrange: int | None = None,
                 neglog_x: bool = False, neglog_y: bool = False) -> list[FigureSpec]:
    """
    生成分组绘图计划。规则与 DataPlotter.group_plotter 一致：

    - 不分组（空 Group）：一张 'main' 图，全部样品按样品号排序，颜色按样品；
    - 分离模式：每个分组一张图（key 为分组名），同一样品可出现在多张图里，颜色按样品；
    - 合并模式：一张 'main' 图；同一样品只画一次，归第一个包含它的分组（先到先得）；
      同组的线统一用组首色（该组写在第一位的样品的位置，只看本组配置，与其他分组无关）。

    groups 的检查与绘图器相同（resolve_groups）：None 表示不分组。
    """
    groups = resolve_groups(groups, dataset)
    positions = color_positions(dataset.sample_idx)   # 按整个数据集排名一次

    # 偏应用：取数设置在一次计划里不变，先绑定好；下面三个函数只管「哪些线、归谁、什么颜色」，
    # 调用时只传 (样品号, 分组名, 色带位置, 样式)。带过去哪些变量，就是这一行列出的这些。
    make_curve = partial(_make_curve, dataset=dataset, channel_x=channel_x, channel_y=channel_y,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y)

    if not groups.names:
        return [_plan_all_samples(dataset, positions, make_curve)]
    if merge_groups:
        return [_plan_merged(groups, positions, make_curve)]
    return _plan_separate(groups, positions, make_curve)


def _make_curve(sample: int, group_name: str | None, color_position: float, style: dict, *,
                dataset: DataSet, channel_x: int, channel_y: int, plotrange: int | None,
                neglog_x: bool, neglog_y: bool) -> CurveSpec:
    """生成一条线：取数，再连同分组名、色带位置、样式装进 CurveSpec。
    * 之后的取数设置由 plan_figures 用 partial 绑定；调用方只传前四个。"""
    x, y, _, label, x_unit, y_unit = get_xy_data(
        dataset, sample, channel_x, channel_y,
        neglog_x=neglog_x, neglog_y=neglog_y, plotrange=plotrange,
    )
    return CurveSpec(sample_idx=sample, x=x, y=y, label=label, x_unit=x_unit, y_unit=y_unit,
                     group_name=group_name, color_position=color_position,
                     style=dict(style))   # 每条线一份副本：以后改一条线的样式不影响同组其他线


def _plan_all_samples(dataset: DataSet, positions: dict, make_curve: MakeCurve) -> FigureSpec:
    """不分组：一张 'main' 图，全部样品按样品号排序，没有分组名和样式。"""
    curves = [make_curve(sample, None, positions[sample], {})
              for sample in sorted(set(dataset.sample_idx))]
    return FigureSpec(key='main', curves=curves)


def _plan_separate(groups: Group, positions: dict, make_curve: MakeCurve) -> list[FigureSpec]:
    """分离模式：每个分组一张图，颜色按样品。"""
    figures = []
    for name in groups:
        style = _written_style(groups, name)
        curves = [make_curve(sample, name, positions[sample], style)
                  for sample in groups.sample_ids(name)]
        figures.append(FigureSpec(key=name, curves=curves))
    return figures


def _plan_merged(groups: Group, positions: dict, make_curve: MakeCurve) -> FigureSpec:
    """合并模式：一张 'main' 图；先算归属，再按归属生成线。"""
    # 第一步：归属表 {样品号: 分组名}。setdefault 已有就不改 → 先到先得，书写顺序即优先级；
    # dict 保持插入顺序 → 这张表的顺序就是画线顺序。
    owner: dict[int, str] = {}
    for name in groups:
        for sample in groups.sample_ids(name):
            owner.setdefault(sample, name)

    # 第二步：每条线的颜色用所属分组的组首位置，样式用所属分组写了的样式
    curves = []
    for sample, name in owner.items():
        head = groups.sample_ids(name)[0]
        curves.append(make_curve(sample, name, positions[head], _written_style(groups, name)))
    return FigureSpec(key='main', curves=curves)


def _written_style(groups: Group, name: str) -> dict:
    """该分组写了的样式，标准写法、不翻译；没写的字段不出现（对照 DataPlotter._group_style，那里会翻译）。"""
    style = {}
    if (linestyle := groups.linestyle(name)) is not None:
        style['linestyle'] = linestyle
    if (marker := groups.marker(name)) is not None:
        style['marker'] = marker
    if (color := groups.color(name)) is not None:
        style['color'] = color
    return style
