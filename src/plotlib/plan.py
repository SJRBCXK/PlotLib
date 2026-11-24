"""
根据样品、通道和分组生成绘图计划。

`plan_multiline_figures`、`plan_scatter_figures`、`plan_xy_figures` 和 `plan_dual_y_figures` 返回
`~plotlib.plot_spec.FigureSpec` 列表。计划记录每张图的轴信息，以及曲线数据、顺序和样式；
画法由曲线的类型决定（`~plotlib.plot_spec.LineSpec`、`~plotlib.plot_spec.ScatterSpec`）。
Matplotlib 和 Plotly 共用取数、去重和配色规则，渲染时再应用版式预设和格式化回调。
"""
from collections.abc import Callable, Mapping
from functools import partial
from typing import Literal

import numpy as np

from .dataset import DataSet
from .group import Group
from .plot_spec import Axis, Curve, CurveKind, FigureSpec, LineSpec, LineStyle, ScatterSpec, ScatterStyle


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
        # 用空 Group 表示未分组的数据。
        groups = Group(dataset, {})

    elif not isinstance(groups, Group):
        raise TypeError(
            f"groups 必须是 Group 对象，实际是 {type(groups).__name__}；"
            "请先用 Group(input_dataset, config) 创建。"
        )
    elif groups.dataset is not dataset:
        # 分组配置必须与绘图引用同一个数据集实例。
        raise ValueError("groups 是基于另一个数据集创建的；请基于绘图用的数据集创建 Group。")

    return groups

def get_xy_data(dataset: DataSet, sample_idx: int, channel_x: int, channel_y: int,
                neglog_x: bool = False, neglog_y: bool = False, plotrange: int | None = None, *,
                positions: Mapping[tuple[int, int], int] | None = None):
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
    positions : Mapping, optional
        列位置索引，见 `get_column_data`。

    Returns
    -------
    tuple
        ``(x, y, x_label, y_label, x_unit, y_unit)``：两列数据、两列的名字（样品名）、两列的单位。

    Raises
    ------
    RuntimeError
        数据集里没有这个样品的这个通道。
    """
    Row_x, x_label, x_unit = get_column_data(dataset, sample_idx, channel_x, plotrange, positions=positions)
    Row_y, y_label, y_unit = get_column_data(dataset, sample_idx, channel_y, plotrange, positions=positions)

    if neglog_x:
        Row_x = np.abs(Row_x)
    if neglog_y:
        Row_y = np.abs(Row_y)

    return Row_x, Row_y, x_label, y_label, x_unit, y_unit


def get_column_data(dataset: DataSet, sample_idx: int, channel_idx: int, plotrange: int | None = None, *,
                    positions: Mapping[tuple[int, int], int] | None = None):
    """
    按样品号和通道号读取一列。

    Parameters
    ----------
    dataset : DataSet
        源数据集。
    sample_idx, channel_idx : int
        样品号和样品内的通道号。
    plotrange : int, optional
        返回的最大行数。``None`` 表示全部行。
    positions : Mapping, optional
        当前数据集经校验的列位置索引。默认读取 ``dataset.column_positions``。
        当数据集结构固定时，可为多次读取传入同一个索引。

    Returns
    -------
    tuple
        ``(数值视图, 列名, 单位)``。

    Raises
    ------
    RuntimeError
        样品或通道不存在，或数据集未通过校验。
    """
    if positions is None:
        positions = dataset.column_positions
    try:
        position = positions[(sample_idx, channel_idx)]
    except KeyError:
        raise RuntimeError(f"数据集里没有样品 {sample_idx} 的通道 {channel_idx}") from None
    return dataset.data[:plotrange, position], dataset.names[position], dataset.units[position]


def sample_name(dataset: DataSet, sample_idx: int, *,
                positions: Mapping[tuple[int, int], int] | None = None) -> str:
    """
    以样品的通道 0 所在列的名称作为样品名。*positions* 的用法见 `get_column_data`。

    Raises
    ------
    RuntimeError
        数据集里没有这个样品。
    """
    if positions is None:
        positions = dataset.column_positions
    try:
        return dataset.names[positions[(sample_idx, 0)]]
    except KeyError:
        raise RuntimeError(f"数据集里没有样品 {sample_idx}") from None


def channel_unit(dataset: DataSet, channel_idx: int) -> str:
    """
    返回通道单位，用作轴标题。校验数据集后，读取该通道首列的单位。

    Raises
    ------
    RuntimeError
        数据集里没有这个通道。
    """
    try:
        return dataset.units[dataset.ensure_updated().channel_idx.index(channel_idx)]
    except ValueError:
        raise RuntimeError(f"数据集里没有通道 {channel_idx}") from None


# ============================================================================
# 绘图计划
# ============================================================================

# make_curve 的类型：给出「样品号、分组名、色带位置」，返回一条线（样式由它按画法从分组读取）
type MakeCurve = Callable[[int, str | None, float | None], Curve]
# make_figure 接收图键、曲线和名称。单位、负刻度及版式已绑定。
type MakeFigure = Callable[[str | int, list[Curve], str | None], FigureSpec]


def plan_multiline_figures(dataset: DataSet, groups: Group | None, channel_x: int, channel_y: int, *,
                 merge_groups: bool = False, plotrange: int | None = None,
                 neglog_x: bool = False, neglog_y: bool = False,
                 legend_title: str | None = None) -> list[FigureSpec]:
    """
    生成多线图和分组绘图的计划（``DataPlotter.plot_multiline``、``plot_groups``），每条线是 `LineSpec`。

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
    - **合并模式**：同一样品绘制一次，归入配置中第一个包含它的分组。
      同组的线统一用组首色，即该组写在第一位的样品的颜色，只看本组配置。
    - 分组样式只读折线用得上的 ``linestyle``、``marker``、``color``。
    """
    return _plan_samples('line', dataset, groups, channel_x, channel_y, merge_groups=merge_groups,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y, legend_title=legend_title)


def plan_scatter_figures(dataset: DataSet, groups: Group | None, channel_x: int, channel_y: int, *,
                         merge_groups: bool = False, plotrange: int | None = None,
                         neglog_x: bool = False, neglog_y: bool = False,
                         legend_title: str | None = None) -> list[FigureSpec]:
    """
    生成散点图的计划（``DataPlotter.plot_scatter``），每组散点是 `ScatterSpec`。

    与 `plan_multiline_figures` 共用同一套规则（不分组、分离、合并三种模式，配色、去重、归属都相同），
    只是画法不同；参数含义也相同。分组样式只读散点用得上的 ``marker``、``color``，其余字段不解析。

    Returns
    -------
    list of FigureSpec
        同 `plan_multiline_figures`。

    Raises
    ------
    RuntimeError
        数据集为空。
    """
    return _plan_samples('scatter', dataset, groups, channel_x, channel_y, merge_groups=merge_groups,
                         plotrange=plotrange, neglog_x=neglog_x, neglog_y=neglog_y, legend_title=legend_title)


def _plan_samples(kind: CurveKind, dataset: DataSet, groups: Group | None, channel_x: int, channel_y: int, *,
                  merge_groups: bool, plotrange: int | None, neglog_x: bool, neglog_y: bool,
                  legend_title: str | None) -> list[FigureSpec]:
    """
    多线图、散点图共用的规则：按分组情况选不分组、分离或合并三种模式。*kind* 只决定每条线画成什么
    （交给 `_make_curve`），规则本身只写这一份。
    """
    column_index = dataset.column_positions
    _check_not_empty(dataset)
    groups = resolve_groups(groups, dataset)
    positions = color_positions(dataset.sample_idx)   # 按整个数据集排名一次

    # 预先绑定同一计划共用的数据选择参数，以及画法和读样式用的分组。
    make_curve = partial(_make_curve, kind=kind, groups=groups, dataset=dataset, positions=column_index,
                         channel_x=channel_x, channel_y=channel_y, plotrange=plotrange,
                         neglog_x=neglog_x, neglog_y=neglog_y)
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
                    legend_title: str | None = None) -> list[FigureSpec]:
    """
    生成 x-y 单线图的计划（``DataPlotter.plot_xy``）：每个样品一张图、一条折线（`LineSpec`）。

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
    column_index = dataset.column_positions
    _check_not_empty(dataset)
    make_curve = partial(_make_curve, kind='line', groups=None, dataset=dataset, positions=column_index,
                         channel_x=channel_x, channel_y=channel_y, plotrange=plotrange,
                         neglog_x=neglog_x, neglog_y=neglog_y)
    make_figure = partial(_make_figure, legend_title=legend_title,
                          x_unit=channel_unit(dataset, channel_x), y_unit=channel_unit(dataset, channel_y),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y), layout='xy')
    return [make_figure(sample, [make_curve(sample, None, None)],
                        sample_name(dataset, sample, positions=column_index))
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
    kinds : tuple of ({'line', 'scatter'}, {'line', 'scatter'}), default: ('line', 'line')
        左线、右线的画法：折线（`LineSpec`）或散点（`ScatterSpec`）。
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
    ValueError
        *kinds* 里有不认识的画法。

    Notes
    -----
    两条线是同一个样品的两个变量，所以线的标签是各自的单位，样品名放在图例标题里。
    两条线不带颜色（样式为空、色带位置为 None）：左红右蓝属于呈现，由版式预设
    ``LAYOUTS['dual_y']`` 决定。
    """
    if len(kinds) != 2:
        raise ValueError(f"kinds 要写两个画法（左线, 右线），实际是 {kinds!r}")
    for kind in kinds:
        if kind not in _KINDS:
            raise ValueError(f"不支持的画法 {kind!r}，双 Y 轴每一侧可选 'line'、'scatter'")
    column_index = dataset.column_positions
    _check_not_empty(dataset)
    left_curve = partial(_make_curve, kind=kinds[0], groups=None, dataset=dataset, positions=column_index,
                         channel_x=left[0], channel_y=left[1], plotrange=plotrange,
                         neglog_x=neglog_x, neglog_y=neglog_y, axis='left', label_from='unit')
    right_curve = partial(_make_curve, kind=kinds[1], groups=None, dataset=dataset, positions=column_index,
                          channel_x=right[0], channel_y=right[1], plotrange=plotrange,
                          neglog_x=neglog_x2, neglog_y=neglog_y2, axis='right', label_from='unit')
    make_figure = partial(_make_figure, legend_title=legend_title,
                          x_unit=channel_unit(dataset, left[0]), y_unit=channel_unit(dataset, left[1]),
                          y2_unit=channel_unit(dataset, right[1]),
                          neglog=_neglog_axes(x=neglog_x, y=neglog_y, x2=neglog_x2, y2=neglog_y2),
                          layout='dual_y')
    return [make_figure(sample, [left_curve(sample, None, None), right_curve(sample, None, None)],
                        sample_name(dataset, sample, positions=column_index))
            for sample in sorted(set(dataset.sample_idx))]


def _check_not_empty(dataset: DataSet) -> None:
    """在提取数据前检查数据集是否为空。"""
    if len(dataset.sample_idx) == 0:
        raise RuntimeError("数据集为空，无法绘图")


def _neglog_axes(**flags: bool) -> frozenset[str]:
    """返回需要在刻度标签前添加负号的轴名集合。"""
    return frozenset(axis for axis, on in flags.items() if on)


def _line_style(groups: Group | None, name: str | None) -> LineStyle:
    """折线从分组读取 ``linestyle``、``marker``、``color``；不分组时是空样式。"""
    if groups is None or name is None:
        return LineStyle()
    return LineStyle(linestyle=groups.linestyle(name), marker=groups.marker(name), color=groups.color(name))


def _scatter_style(groups: Group | None, name: str | None) -> ScatterStyle:
    """散点从分组只读取 ``marker``、``color``，其余字段不解析；不分组时是空样式。"""
    if groups is None or name is None:
        return ScatterStyle()
    return ScatterStyle(marker=groups.marker(name), color=groups.color(name))


# 画法 → (这种画法的曲线类型, 从分组读样式的函数)
_KINDS: dict[str, tuple[type[LineSpec] | type[ScatterSpec], Callable[[Group | None, str | None], LineStyle | ScatterStyle]]] = {
    'line': (LineSpec, _line_style),
    'scatter': (ScatterSpec, _scatter_style),
}


def _make_curve(sample: int, group_name: str | None, color_position: float | None, *,
                kind: CurveKind, groups: Group | None,
                dataset: DataSet, positions: Mapping[tuple[int, int], int],
                channel_x: int, channel_y: int, plotrange: int | None,
                neglog_x: bool, neglog_y: bool,
                axis: Axis = 'left', label_from: Literal['name', 'unit'] = 'name') -> Curve:
    """
    取一个样品的 X、Y 数据，按 *kind* 生成 `LineSpec` 或 `ScatterSpec`，样式按画法从分组读取。

    各计划函数预先绑定画法、分组和用于读取曲线的共用参数，包括已经校验的列位置索引；
    调用处只给样品号、分组名、色带位置。
    """
    spec_type, read_style = _KINDS[kind]
    x, y, _, name, _, unit = get_xy_data(
        dataset, sample, channel_x, channel_y,
        neglog_x=neglog_x, neglog_y=neglog_y, plotrange=plotrange, positions=positions,
    )
    label = name if label_from == 'name' else unit
    return spec_type(sample_idx=sample, x=x, y=y, label=label,
                     group_name=group_name, color_position=color_position,
                     style=read_style(groups, group_name),     # type: ignore[arg-type]  _KINDS 里类型与样式一一对应
                     axis=axis)


def _make_figure(key: str | int, curves: list[Curve], name: str | None, *,
                 legend_title: str | None, **figure_info) -> FigureSpec:
    """
    生成一张图。

    *name* 为样品名或组名，保存到 ``FigureSpec.name``，并替换图例标题中的 ``'{name}'``。
    *name* 为 ``None`` 时保留原始标题文本。公共图形参数由计划函数预先绑定。
    """
    if legend_title is not None and name is not None:
        legend_title = legend_title.replace('{name}', name)
    return FigureSpec(key=key, curves=curves, legend_title=legend_title, name=name, **figure_info)


def _plan_all_samples(dataset: DataSet, positions: dict, make_curve: MakeCurve,
                      make_figure: MakeFigure) -> FigureSpec:
    """不分组：一张 'main' 图，全部样品按样品号排序，没有分组名和样式。"""
    curves = [make_curve(sample, None, positions[sample])
              for sample in sorted(set(dataset.sample_idx))]
    return make_figure('main', curves, None)


def _plan_separate(groups: Group, positions: dict, make_curve: MakeCurve,
                   make_figure: MakeFigure) -> list[FigureSpec]:
    """分离模式：每个分组一张图，颜色按样品。"""
    figures = []
    for name in groups:
        curves = [make_curve(sample, name, positions[sample])
                  for sample in groups.sample_ids(name)]
        figures.append(make_figure(name, curves, name))
    return figures


def _plan_merged(groups: Group, positions: dict, make_curve: MakeCurve,
                 make_figure: MakeFigure) -> FigureSpec:
    """合并模式：一张 'main' 图；先算归属，再按归属生成线。"""
    # 以首次出现为准确定分组，字典的插入顺序即绘制顺序。
    owner: dict[int, str] = {}
    for name in groups:
        for sample in groups.sample_ids(name):
            owner.setdefault(sample, name)

    # 默认颜色取该组首个样品的色带位置，分组样式可覆盖它。
    curves = []
    for sample, name in owner.items():
        head = groups.sample_ids(name)[0]
        curves.append(make_curve(sample, name, positions[head]))
    return make_figure('main', curves, None)
