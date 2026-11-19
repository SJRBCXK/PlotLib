"""
绘图规则（2026-11-20 从 plot_common.py 拆出）：根据数据集、分组和选列生成绘图计划（plot_spec 里的 FigureSpec）。

  - plan_multiline_figures / plan_xy_figures / plan_dual_y_figures：三种版式的计划；
  - color_positions、resolve_groups、get_xy_data 等：生成计划时用到的公共函数。

分组规则（去重、先到先得、组首色、样式归属）只写在这里；两个后端都只读计划，不读 Group。
"""
from collections.abc import Callable
from functools import partial

import numpy as np

from .dataset import DataSet
from .group import Group
from .plot_spec import Axis, CurveKind, CurveSpec, FigureSpec


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


def channel_unit(dataset: DataSet, channel_idx: int) -> str:
    """通道的单位。同一通道在所有样品里单位相同（DataSet._channel_units_unify_check），取第一列即可。"""
    for column in dataset.column:
        if column.channel_idx == channel_idx:
            return column.unit
    raise RuntimeError("未找到对应的列数据")


# ============================================================================
# 绘图计划（STRUCTURE_REVIEW 步骤 6.1；6.4 补全为四种绘图方法共用）
#   只做「决定」：画几张图、每张图有哪些线、每条线的数据 / 标签 / 颜色 / 样式，每张图的轴信息。
#   不导入任何绘图库；matplotlib 和 Plotly 照着同一份计划画，规则只写这一次。
#   计划保持「薄」：坐标范围、刻度格式、字体、图例位置不放进来，那是排版预设（layouts.py）和 formatter 的事。
# ============================================================================

# make_curve 的类型：给出「样品号、分组名、色带位置、样式」，返回一条线
type MakeCurve = Callable[[int, str | None, float | None, dict], CurveSpec]
# make_figure 的类型：给出「key、线」，返回一张图（单位、neglog、版式已绑定）
type MakeFigure = Callable[[str | int, list[CurveSpec]], FigureSpec]


def plan_multiline_figures(dataset: DataSet, groups: Group | None, channel_x: int, channel_y: int, *,
                 merge_groups: bool = False, plotrange: int | None = None,
                 neglog_x: bool = False, neglog_y: bool = False,
                 kind: CurveKind = 'line') -> list[FigureSpec]:
    """
    生成多线图 / 分组绘图计划（DataPlotter.plot_multiline、plot_groups）。规则：

    - 不分组（空 Group）：一张 'main' 图，全部样品按样品号排序，颜色按样品；
    - 分离模式：每个分组一张图（key 为分组名），同一样品可出现在多张图里，颜色按样品；
    - 合并模式：一张 'main' 图；同一样品只画一次，归第一个包含它的分组（先到先得）；
      同组的线统一用组首色（该组写在第一位的样品的位置，只看本组配置，与其他分组无关）。

    groups 的检查与绘图器相同（resolve_groups）：None 表示不分组。
    """
    _check_not_empty(dataset)
    groups = resolve_groups(groups, dataset)
    positions = color_positions(dataset.sample_idx)   # 按整个数据集排名一次

    # 偏应用：取数设置在一次计划里不变，先绑定好；下面三个函数只管「哪些线、归谁、什么颜色」，
    # 调用时只传 (样品号, 分组名, 色带位置, 样式)。带过去哪些变量，就是这一行列出的这些。
    make_curve = partial(_make_curve, dataset=dataset, channel_x=channel_x, channel_y=channel_y,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y, kind=kind)
    # 同理：一次计划里每张图的单位、neglog、版式都一样，三个函数只传 (key, 线)
    make_figure = partial(FigureSpec,
                          x_unit=channel_unit(dataset, channel_x), y_unit=channel_unit(dataset, channel_y),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y), layout='multiline')

    if not groups.names:
        return [_plan_all_samples(dataset, positions, make_curve, make_figure)]
    if merge_groups:
        return [_plan_merged(groups, positions, make_curve, make_figure)]
    return _plan_separate(groups, positions, make_curve, make_figure)


def plan_xy_figures(dataset: DataSet, channel_x: int, channel_y: int, *,
                    plotrange: int | None = None, neglog_x: bool = False, neglog_y: bool = False,
                    kind: CurveKind = 'line') -> list[FigureSpec]:
    """
    xy 单线图计划（DataPlotter.plot_xy）：每个样品一张图、一条线，key 是样品号。
    一张图只有一条线，不靠颜色区分样品：色带位置为 None，用后端默认色。
    """
    _check_not_empty(dataset)
    make_curve = partial(_make_curve, dataset=dataset, channel_x=channel_x, channel_y=channel_y,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y, kind=kind)
    make_figure = partial(FigureSpec,
                          x_unit=channel_unit(dataset, channel_x), y_unit=channel_unit(dataset, channel_y),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y), layout='xy')
    return [make_figure(sample, [make_curve(sample, None, None, {})])
            for sample in sorted(set(dataset.sample_idx))]


def plan_dual_y_figures(dataset: DataSet, left: tuple[int, int], right: tuple[int, int], *,
                        plotrange: int | None = None,
                        neglog_x: bool = False, neglog_y: bool = False,
                        neglog_x2: bool = False, neglog_y2: bool = False,
                        kinds: tuple[CurveKind, CurveKind] = ('line', 'line')) -> list[FigureSpec]:
    """
    双 Y 轴图计划（DataPlotter.plot_dual_y）：每个样品一张图、两条线，key 是样品号。
    left / right 各是 (X 通道, Y 通道)：左线挂左轴、右线挂右轴，两侧共用 X 轴（X 轴标题取左侧的单位）。
    两条线不带颜色（style 为空、色带位置为 None）：左红右蓝属于呈现，由排版预设 layouts.LAYOUTS['dual_y'] 决定（6.6b）。
    """
    _check_not_empty(dataset)
    left_curve = partial(_make_curve, dataset=dataset, channel_x=left[0], channel_y=left[1],
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y,
                         kind=kinds[0], axis='left')
    right_curve = partial(_make_curve, dataset=dataset, channel_x=right[0], channel_y=right[1],
                          plotrange=plotrange, neglog_x=neglog_x2, neglog_y=neglog_y2,
                          kind=kinds[1], axis='right')
    make_figure = partial(FigureSpec,
                          x_unit=channel_unit(dataset, left[0]), y_unit=channel_unit(dataset, left[1]),
                          y2_unit=channel_unit(dataset, right[1]),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y, x2=neglog_x2, y2=neglog_y2),
                          layout='dual_y')
    return [make_figure(sample, [left_curve(sample, None, None, {}),
                                 right_curve(sample, None, None, {})])
            for sample in sorted(set(dataset.sample_idx))]


def _check_not_empty(dataset: DataSet) -> None:
    """数据集为空时给出明确的报错（否则会在取单位时报「未找到对应的列数据」，看不出原因）。"""
    if len(dataset.sample_idx) == 0:
        raise RuntimeError("数据集为空，无法绘图")


def _neglog_axes(**flags: bool) -> frozenset[str]:
    """{'x': True, 'y': False} → frozenset({'x'})：哪些轴的刻度要补负号。"""
    return frozenset(axis for axis, on in flags.items() if on)


def _make_curve(sample: int, group_name: str | None, color_position: float | None, style: dict, *,
                dataset: DataSet, channel_x: int, channel_y: int, plotrange: int | None,
                neglog_x: bool, neglog_y: bool,
                kind: CurveKind = 'line', axis: Axis = 'left') -> CurveSpec:
    """生成一条线：取数，再连同分组名、色带位置、样式装进 CurveSpec。
    * 之后的取数设置、画法、所在轴由各 plan_* 用 partial 绑定；调用方只传前四个。"""
    x, y, _, label, _, _ = get_xy_data(
        dataset, sample, channel_x, channel_y,
        neglog_x=neglog_x, neglog_y=neglog_y, plotrange=plotrange,
    )
    return CurveSpec(sample_idx=sample, x=x, y=y, label=label,
                     group_name=group_name, color_position=color_position,
                     style=dict(style),   # 每条线一份副本：以后改一条线的样式不影响同组其他线
                     kind=kind, axis=axis)


def _plan_all_samples(dataset: DataSet, positions: dict, make_curve: MakeCurve,
                      make_figure: MakeFigure) -> FigureSpec:
    """不分组：一张 'main' 图，全部样品按样品号排序，没有分组名和样式。"""
    curves = [make_curve(sample, None, positions[sample], {})
              for sample in sorted(set(dataset.sample_idx))]
    return make_figure('main', curves)


def _plan_separate(groups: Group, positions: dict, make_curve: MakeCurve,
                   make_figure: MakeFigure) -> list[FigureSpec]:
    """分离模式：每个分组一张图，颜色按样品。"""
    figures = []
    for name in groups:
        style = _written_style(groups, name)
        curves = [make_curve(sample, name, positions[sample], style)
                  for sample in groups.sample_ids(name)]
        figures.append(make_figure(name, curves))
    return figures


def _plan_merged(groups: Group, positions: dict, make_curve: MakeCurve,
                 make_figure: MakeFigure) -> FigureSpec:
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
    return make_figure('main', curves)


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
