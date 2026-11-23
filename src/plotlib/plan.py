"""
绘图规则：根据数据集、分组和选定的通道生成绘图计划（`~plotlib.plot_spec.FigureSpec` 列表）。

- `plan_multiline_figures`、`plan_xy_figures`、`plan_dual_y_figures`：三种版式的计划；
- `color_positions`、`resolve_groups`、`get_xy_data` 等：生成计划时用到的公共函数。

计划只做「决定」：画几张图、每张图有哪些线、每条线的数据 / 标签 / 颜色位置 / 样式，以及每张图的轴信息。
本模块不导入任何绘图库；坐标范围、刻度格式、字体、图例位置属于版式预设和 formatter，不放进计划。

Notes
-----
分组规则（去重、先到先得、组首色、样式归属）只写在本模块，两个后端都只读计划、不读 `Group`，
所以 matplotlib 和 Plotly 画出的图在线条、顺序、颜色来源上完全一致。
"""
from collections.abc import Callable
from functools import partial
from typing import Literal

import numpy as np

from .dataset import DataSet
from .group import Group
from .plot_spec import Axis, CurveKind, CurveSpec, FigureSpec, LineStyle

NO_STYLE = LineStyle()      # 不分组的线：没有分组样式


def color_positions(sample_idx):
    """
    按样品号排名算出每个样品在色带上的位置。

    去重、排序后，第 i 个样品的位置是 ``i / 样品数``，取值在 [0, 1) 之间。
    样品号不连续时（如 0、5、9）也不会越界或重色。

    Parameters
    ----------
    sample_idx : iterable of int
        样品号，可以重复（如 ``DataSet.sample_idx`` 每列一个）。

    Returns
    -------
    dict
        ``{样品号: 色带位置}``。

    Examples
    --------
    >>> color_positions([0, 0, 5, 5, 9, 9])
    {0: 0.0, 5: 0.3333333333333333, 9: 0.6666666666666666}
    """    
    return {sample: i / (len(set(sample_idx))) for i, sample in enumerate(sorted(set(sample_idx)))}

def resolve_groups(groups: Group | None, dataset: DataSet) -> Group:
    """
    检查并规范绘图用的分组参数。

    Parameters
    ----------
    groups : Group or None
        分组对象；None 表示不分组，换成建在 *dataset* 上的空 `Group`，后面的代码不必再判断 None。
    dataset : DataSet
        绘图用的数据集。

    Returns
    -------
    Group
        合法的分组对象（传入的原对象，不复制）。

    Raises
    ------
    TypeError
        *groups* 不是 `Group` （如直接传了配置字典）。
    ValueError
        *groups* 是建在另一个数据集上的（按对象身份 ``is`` 判断，内容相同的两个数据集也不算同一个）。
    """
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
    """
    取出一个样品的 X、Y 两列数据和它们的名字、单位。

    Parameters
    ----------
    dataset : DataSet
        数据集。
    sample_idx : int
        样品号。
    channel_x, channel_y : int
        X、Y 的通道号（样品内的列序号）。
    neglog_x, neglog_y : bool, default: False
        是否对这一列取绝对值。这里只处理数据，刻度文字补负号由后端负责。
    plotrange : int, optional
        只取前 *plotrange* 行；None 取全部。

    Returns
    -------
    tuple
        ``(x, y, x_label, y_label, x_unit, y_unit)``：两列数据、两列的名字（样品名）、两列的单位。

    Raises
    ------
    RuntimeError
        数据集里没有这个样品的这个通道。
    """
    Row_x, x_label, x_unit = get_column_data(dataset, sample_idx, channel_x, plotrange)
    Row_y, y_label, y_unit = get_column_data(dataset, sample_idx, channel_y, plotrange)

    if neglog_x:
        Row_x = np.abs(Row_x)
    if neglog_y:
        Row_y = np.abs(Row_y)

    return Row_x, Row_y, x_label, y_label, x_unit, y_unit


def get_column_data(dataset: DataSet, sample_idx: int, channel_idx: int, plotrange: int | None = None):
    """
    按样品号和通道号找到一列，返回 ``(数据, 名字, 单位)``。

    数据是 DataSet 的视图（取了前 *plotrange* 行），不是副本。

    Raises
    ------
    RuntimeError
        数据集里没有这一列。
    """
    for column in dataset.column:
        if column.sample_idx == sample_idx and column.channel_idx == channel_idx:
            return column.data[:plotrange], column.name, column.unit
    raise RuntimeError("未找到对应的列数据")


def sample_name(dataset: DataSet, sample_idx: int) -> str:
    """
    样品名。同一样品的各列名字相同（`~plotlib.dataloader.Dataloader` 按样品展开），取第一列的即可。

    Raises
    ------
    RuntimeError
        数据集里没有这个样品。
    """
    for column in dataset.column:
        if column.sample_idx == sample_idx:
            return column.name
    raise RuntimeError("未找到对应的列数据")


def channel_unit(dataset: DataSet, channel_idx: int) -> str:
    """
    通道的单位，用作轴标题。同一通道在所有样品里单位相同（`DataSet` 会校验），取第一列的即可。

    Raises
    ------
    RuntimeError
        数据集里没有这个通道。
    """
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
type MakeCurve = Callable[[int, str | None, float | None, LineStyle], CurveSpec]
# make_figure 的类型：给出「key、线、这张图自己的名字」，返回一张图（单位、neglog、版式、图例标题写法已绑定）
type MakeFigure = Callable[[str | int, list[CurveSpec], str | None], FigureSpec]


def plan_multiline_figures(dataset: DataSet, groups: Group | None, channel_x: int, channel_y: int, *,
                 merge_groups: bool = False, plotrange: int | None = None,
                 neglog_x: bool = False, neglog_y: bool = False,
                 kind: CurveKind = 'line', legend_title: str | None = None) -> list[FigureSpec]:
    """
    生成多线图和分组绘图的计划（``DataPlotter.plot_multiline``、``plot_groups``）。

    Parameters
    ----------
    dataset : DataSet
        数据集。
    groups : Group or None
        分组；None 或空 `Group` 表示不分组（检查规则见 `resolve_groups`）。
    channel_x, channel_y : int
        X、Y 的通道号。
    merge_groups : bool, default: False
        分组时是否把所有分组合并到一张图。
    plotrange : int, optional
        每条线只取前几行；None 取全部。
    neglog_x, neglog_y : bool, default: False
        负对数：数据取绝对值，刻度文字补负号。
    kind : {'line', 'scatter', 'bar'}, default: 'line'
        画法。
    legend_title : str, optional
        图例标题。``'{name}'`` 在分离模式换成组名；只有一张图时没有名字可换，原样保留。

    Returns
    -------
    list of FigureSpec
        不分组、合并模式：一张 key 为 ``'main'`` 的图；分离模式：每个分组一张，key 是分组名。

    Raises
    ------
    RuntimeError
        数据集为空。

    Notes
    -----
    - **不分组**：全部样品按样品号排序，颜色按样品在整个数据集里的排名取。
    - **分离模式**：同一样品可以出现在多张图里，颜色仍按样品取，所以同一样品在各张图里同色。
    - **合并模式**：同一样品只画一次，归第一个包含它的分组（先到先得，书写顺序就是优先级）；
      同组的线统一用组首色，即该组写在第一位的样品的颜色，只看本组配置。
    """
    _check_not_empty(dataset)
    groups = resolve_groups(groups, dataset)
    positions = color_positions(dataset.sample_idx)   # 按整个数据集排名一次

    # 偏应用：取数设置在一次计划里不变，先绑定好；下面三个函数只管「哪些线、归谁、什么颜色」，
    # 调用时只传 (样品号, 分组名, 色带位置, 样式)。带过去哪些变量，就是这一行列出的这些。
    make_curve = partial(_make_curve, dataset=dataset, channel_x=channel_x, channel_y=channel_y,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y, kind=kind)
    # 同理：一次计划里每张图的单位、neglog、版式、图例标题写法都一样，三个函数只传 (key, 线, 这张图的名字)
    make_figure = partial(_make_figure, legend_title=legend_title,
                          x_unit=channel_unit(dataset, channel_x), y_unit=channel_unit(dataset, channel_y),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y), layout='multiline')

    if not groups.names:
        return [_plan_all_samples(dataset, positions, make_curve, make_figure)]
    if merge_groups:
        return [_plan_merged(groups, positions, make_curve, make_figure)]
    return _plan_separate(groups, positions, make_curve, make_figure)


def plan_xy_figures(dataset: DataSet, channel_x: int, channel_y: int, *,
                    plotrange: int | None = None, neglog_x: bool = False, neglog_y: bool = False,
                    kind: CurveKind = 'line', legend_title: str | None = None) -> list[FigureSpec]:
    """
    生成 x-y 单线图的计划（``DataPlotter.plot_xy``）：每个样品一张图、一条线。

    参数含义同 `plan_multiline_figures`；*legend_title* 里的 ``'{name}'`` 换成每张图的样品名。

    Returns
    -------
    list of FigureSpec
        每个样品一张，key 是样品号，按样品号排序。一张图只有一条线，不靠颜色区分样品，
        所以色带位置为 None，用后端默认色。

    Raises
    ------
    RuntimeError
        数据集为空。
    """
    _check_not_empty(dataset)
    make_curve = partial(_make_curve, dataset=dataset, channel_x=channel_x, channel_y=channel_y,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y, kind=kind)
    make_figure = partial(_make_figure, legend_title=legend_title,
                          x_unit=channel_unit(dataset, channel_x), y_unit=channel_unit(dataset, channel_y),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y), layout='xy')
    return [make_figure(sample, [make_curve(sample, None, None, NO_STYLE)], sample_name(dataset, sample))
            for sample in sorted(set(dataset.sample_idx))]


def plan_dual_y_figures(dataset: DataSet, left: tuple[int, int], right: tuple[int, int], *,
                        plotrange: int | None = None,
                        neglog_x: bool = False, neglog_y: bool = False,
                        neglog_x2: bool = False, neglog_y2: bool = False,
                        kinds: tuple[CurveKind, CurveKind] = ('line', 'line'),
                        legend_title: str | None = '{name}') -> list[FigureSpec]:
    """
    生成双 Y 轴图的计划（``DataPlotter.plot_dual_y``）：每个样品一张图、左右两条线。

    Parameters
    ----------
    dataset : DataSet
        数据集。
    left, right : tuple of (int, int)
        左线、右线的 ``(X 通道, Y 通道)``。左线挂左轴、右线挂右轴，两侧共用 X 轴，
        X 轴标题取左侧 X 通道的单位。
    plotrange : int, optional
        每条线只取前几行；None 取全部。
    neglog_x, neglog_y, neglog_x2, neglog_y2 : bool, default: False
        左线的 X、Y 和右线的 X、Y 是否按负对数画。
    kinds : tuple of (str, str), default: ('line', 'line')
        左线、右线的画法。
    legend_title : str or None, default: '{name}'
        图例标题，``'{name}'`` 换成样品名；None 表示不加。

    Returns
    -------
    list of FigureSpec
        每个样品一张，key 是样品号，按样品号排序。

    Raises
    ------
    RuntimeError
        数据集为空。

    Notes
    -----
    两条线是同一个样品的两个变量，所以线的标签是各自的单位，样品名放在图例标题里。
    两条线不带颜色（样式为空、色带位置为 None）：左红右蓝属于呈现，由版式预设
    ``LAYOUTS['dual_y']`` 决定。
    """
    _check_not_empty(dataset)
    left_curve = partial(_make_curve, dataset=dataset, channel_x=left[0], channel_y=left[1],
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y,
                         kind=kinds[0], axis='left', label_from='unit')
    right_curve = partial(_make_curve, dataset=dataset, channel_x=right[0], channel_y=right[1],
                          plotrange=plotrange, neglog_x=neglog_x2, neglog_y=neglog_y2,
                          kind=kinds[1], axis='right', label_from='unit')
    make_figure = partial(_make_figure, legend_title=legend_title,
                          x_unit=channel_unit(dataset, left[0]), y_unit=channel_unit(dataset, left[1]),
                          y2_unit=channel_unit(dataset, right[1]),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y, x2=neglog_x2, y2=neglog_y2),
                          layout='dual_y')
    return [make_figure(sample, [left_curve(sample, None, None, NO_STYLE), right_curve(sample, None, None, NO_STYLE)],
                        sample_name(dataset, sample))
            for sample in sorted(set(dataset.sample_idx))]


def _check_not_empty(dataset: DataSet) -> None:
    """数据集为空时报一个看得懂的错，而不是等到取单位时才报「未找到对应的列数据」。"""
    if len(dataset.sample_idx) == 0:
        raise RuntimeError("数据集为空，无法绘图")


def _neglog_axes(**flags: bool) -> frozenset[str]:
    """把开关 ``x=True, y=False`` 收成 ``frozenset({'x'})``：哪些轴的刻度要补负号。"""
    return frozenset(axis for axis, on in flags.items() if on)


def _make_curve(sample: int, group_name: str | None, color_position: float | None, style: LineStyle, *,
                dataset: DataSet, channel_x: int, channel_y: int, plotrange: int | None,
                neglog_x: bool, neglog_y: bool,
                kind: CurveKind = 'line', axis: Axis = 'left',
                label_from: Literal['name', 'unit'] = 'name') -> CurveSpec:
    """
    生成一条线：取数，再连同分组名、色带位置、样式装进 `CurveSpec`。

    ``*`` 之后的参数（取数设置、画法、所在轴、标签取样品名还是 Y 的单位）在一次计划里不变，
    由各 ``plan_*`` 用 `functools.partial` 先绑定好，调用处只传前四个。
    """
    x, y, _, name, _, unit = get_xy_data(
        dataset, sample, channel_x, channel_y,
        neglog_x=neglog_x, neglog_y=neglog_y, plotrange=plotrange,
    )
    label = name if label_from == 'name' else unit
    return CurveSpec(sample_idx=sample, x=x, y=y, label=label,
                     group_name=group_name, color_position=color_position,
                     style=style,         # LineStyle 是冻结的，同组的线共用一个也不会互相影响
                     kind=kind, axis=axis)


def _make_figure(key: str | int, curves: list[CurveSpec], name: str | None, *,
                 legend_title: str | None, **figure_info) -> FigureSpec:
    """
    生成一张图。

    *name* 是这张图自己的名字（每个样品一张图时是样品名，分离模式是组名，只有一张图时为 None），
    存进 ``FigureSpec.name``，并替换图例标题里的 ``'{name}'``；没有名字时标题原样使用，不报错。
    ``*`` 之后的参数（图例标题写法、单位、neglog、版式）由各 ``plan_*`` 用 `functools.partial` 绑定，
    调用处只传前三个。
    """
    if legend_title is not None and name is not None:
        legend_title = legend_title.replace('{name}', name)
    return FigureSpec(key=key, curves=curves, legend_title=legend_title, name=name, **figure_info)


def _plan_all_samples(dataset: DataSet, positions: dict, make_curve: MakeCurve,
                      make_figure: MakeFigure) -> FigureSpec:
    """不分组：一张 'main' 图，全部样品按样品号排序，没有分组名和样式。"""
    curves = [make_curve(sample, None, positions[sample], NO_STYLE)
              for sample in sorted(set(dataset.sample_idx))]
    return make_figure('main', curves, None)


def _plan_separate(groups: Group, positions: dict, make_curve: MakeCurve,
                   make_figure: MakeFigure) -> list[FigureSpec]:
    """分离模式：每个分组一张图，颜色按样品。"""
    figures = []
    for name in groups:
        style = _written_style(groups, name)
        curves = [make_curve(sample, name, positions[sample], style)
                  for sample in groups.sample_ids(name)]
        figures.append(make_figure(name, curves, name))
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
    return make_figure('main', curves, None)


def _written_style(groups: Group, name: str) -> LineStyle:
    """该分组写了的样式（线型、标记、颜色），装进 `LineStyle`；保持标准写法、不翻译，没写的字段为 None。"""
    return LineStyle(linestyle=groups.linestyle(name), marker=groups.marker(name), color=groups.color(name))
