"""
根据样品、通道和分组生成绘图计划。

`plan_figures` 返回 `~plotlib.plot_spec.FigureSpec` 列表：*by* 决定哪些样品进哪张图，
图层（`~plotlib.plot_spec.Layer`）决定每个样品画哪几条、画成什么、挂哪根 Y 轴。
计划记录每张图的轴信息，以及曲线数据、顺序和样式；画法由曲线的类型决定
（`~plotlib.plot_spec.LineSpec`、`~plotlib.plot_spec.ScatterSpec`）。
Matplotlib 和 Plotly 共用取数、去重和配色规则，渲染时再应用版式预设和格式化回调。

`plan_bars` 生成柱状图的计划：一张「类别 × 系列」的表，每格的值由数据处理层汇总，这里只负责排列和配色。
"""
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from functools import partial
from numbers import Integral, Real
from typing import Literal

import numpy as np

from .dataset import DataSet
from .group import Group
from .plot_spec import (DEFAULT_COLORBAR, Axis, BarDimension, BarMode, BarSpec, BarStyle, ColorbarStyle, Curve,
                        CurveKind, FigureSpec, Layer, Layout, LineSpec, LineStyle, Members, ScatterMap, ScatterSpec,
                        ScatterStyle)
from .processor import Reduction, check_reduction, reduce_values, reduce_with_error
from .style import check_bar_style, check_colorbar_style


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

# make_curves 的类型：给出「样品号、分组名、色带位置」，按图层顺序返回这个样品的各条曲线（样式按画法从分组读取）
type MakeCurves = Callable[[int, str | None, float | None], list[Curve]]
# make_figure 接收图键、曲线和名称。单位、负刻度及版式已绑定。
type MakeFigure = Callable[[str | int, list[Curve], str | None], FigureSpec]

_BY: tuple[Members, ...] = ('all', 'group', 'sample')
_SIDES: tuple[Axis, ...] = ('left', 'right')


def plan_figures(dataset: DataSet, groups: Group | None, layers: Sequence[Layer], *,
                 by: Members = 'all', merge_groups: bool = False, plotrange: int | None = None,
                 legend_title: str | None = 'auto', colorbar: ColorbarStyle | None = None) -> list[FigureSpec]:
    """
    生成绘图计划（``DataPlotter.plot``）：*by* 决定哪些样品进哪张图，*layers* 决定每个样品画哪几条。

    Parameters
    ----------
    dataset : DataSet
        数据集。
    groups : Group or None
        分组，只在 ``by='group'`` 时使用（检查规则见 `resolve_groups`）。
    layers : sequence of Layer
        图层，每个都要写明通道（``DataPlotter.plot`` 会把没写的补成构造时的通道）。
    by : {'all', 'group', 'sample'}, default: 'all'
        ``'all'``：全部样品一张 ``'main'`` 图，不看分组；``'group'``：按分组画；
        ``'sample'``：每个样品一张，key 是样品号，不看分组。
    merge_groups : bool, default: False
        ``by='group'`` 时把所有分组合并到一张 ``'main'`` 图。
    plotrange : int, optional
        每条线只取前几行；None 取全部。
    legend_title : str or None, default: 'auto'
        图例标题，``'{name}'`` 换成每张图自己的名字：``'sample'`` 是样品名，分离模式是组名
        （只有一个样品或一个分组、只画出一张图时也替换）；``'all'`` 和合并模式的图没有自己的名字，原样保留。
        ``'auto'``：一个样品画多层时是 ``'{name}'`` （样品名），否则不加；None 表示不加。
    colorbar : ColorbarStyle, optional
        颜色条的外观，叠在 ``DEFAULT_COLORBAR`` 上；只有某个图层写了 ``ScatterMap(color=...)`` 时才能给。

    Returns
    -------
    list of FigureSpec
        ``'all'`` 和合并模式一张 key 为 ``'main'`` 的图；分离模式每个分组一张，key 是分组名；
        ``'sample'`` 每个样品一张，key 是样品号，按样品号排序。曲线按「样品 → 图层」的顺序，
        同一样品各层的顺序与 *layers* 一致。

    Raises
    ------
    ValueError
        *by*、画法、轴写错；图层没写通道；没有图层或没有左侧图层；``by`` 不是 ``'group'`` 却写了 *merge_groups*；
        ``by='group'`` 但没有分组；``by='all'`` / ``'group'`` 画多个图层（暂不支持）；同一根轴上的负对数写法不一致；
        映射写错（见 `~plotlib.plot_spec.ScatterMap`）、有两个颜色映射层、给了 *colorbar* 却没有颜色映射层、
        颜色条写错或对数色标遇到不为正的值、映射值有无穷大。
    RuntimeError
        数据集为空。

    Notes
    -----
    - **分组**：分离模式中同一样品可以出现在多张图里，颜色仍按样品取，所以同一样品在各张图里同色。
      合并模式中同一样品绘制一次，归入配置中第一个包含它的分组；同组的线统一用组首色，即该组写在第一位的样品的颜色。
      分组样式按画法只读用得上的字段：折线读 ``linestyle``、``marker``、``color``，散点读 ``marker``、``color``。
    - **颜色**：``'sample'`` 每张图只有一个样品，不按色带取色（版式预设的轴颜色或后端默认色），其余按样品在整个数据集里的排名取。
    - **标签**：一层时是样品名；一个样品画多层时是各层 Y 通道的单位（样品名在图例标题里）。
    - **版式**：有右侧图层用 ``'dual_y'``，``'sample'`` 用 ``'xy'``，其余用 ``'multiline'``。
    - **负对数**：每层的数据各自取绝对值；刻度补负号按轴：共用的 X 轴看左侧图层，左右 Y 轴各看本侧图层。
      右侧图层的 ``neglog_x`` 只把自己的 X 数据取绝对值。
    - **轴标题**：X 取第一个左侧图层的 X 单位，左 / 右 Y 取该侧第一个图层的 Y 单位。
    - **映射**：先按图层取出各点的原始映射值，全部图生成后再按共用范围换算（大小换成直径、颜色条的范围），
      所以同一个值在每张图、每个样品里都是同色、同大小。
    """
    layers = list(layers)
    _check_layers(layers, by, merge_groups)
    colorbar_style = _check_colorbar(layers, colorbar)
    column_index = dataset.column_positions
    _check_not_empty(dataset)
    # 分组只在 by='group' 时使用，也只在那时检查（其他模式传进来的分组不看）
    resolved = resolve_groups(groups, dataset) if by == 'group' else None
    if resolved is not None and not resolved.names:
        raise ValueError("by='group' 要有分组：请在 DataPlotter(groups=...) 里给出；画全部样品写 by='all'")

    left = [layer for layer in layers if layer.side == 'left']
    right = [layer for layer in layers if layer.side == 'right']
    makers = [partial(_make_curve, kind=layer.kind, groups=resolved, dataset=dataset,
                      positions=column_index, channel_x=_channels(layer)[0], channel_y=_channels(layer)[1],
                      plotrange=plotrange,
                      neglog_x=layer.neglog_x, neglog_y=layer.neglog_y, axis=layer.side,
                      label_from='unit' if len(layers) > 1 else 'name', mapping=layer.mapping)
              for layer in layers]
    made: list[list[Curve]] = [[] for _ in layers]      # 每个图层生成的曲线，映射按图层换算范围时用

    def make_curves(sample: int, group_name: str | None, color_position: float | None) -> list[Curve]:
        curves = [make(sample, group_name, color_position) for make in makers]
        for own, curve in zip(made, curves):
            own.append(curve)
        return curves

    layout: Layout = 'dual_y' if right else ('xy' if by == 'sample' else 'multiline')
    if legend_title == 'auto':
        legend_title = '{name}' if len(layers) > 1 else None
    make_figure = partial(_make_figure, legend_title=legend_title, layout=layout,
                          x_unit=channel_unit(dataset, _channels(left[0])[0]),
                          y_unit=channel_unit(dataset, _channels(left[0])[1]),
                          y2_unit=channel_unit(dataset, _channels(right[0])[1]) if right else None,
                          neglog=_neglog_axes(x=left[0].neglog_x, y=left[0].neglog_y,
                                              y2=bool(right) and right[0].neglog_y))

    if by == 'sample':
        figures = [make_figure(sample, make_curves(sample, None, None),
                               sample_name(dataset, sample, positions=column_index))
                   for sample in sorted(set(dataset.sample_idx))]
    else:
        positions = color_positions(dataset.sample_idx)   # 按整个数据集排名一次
        if resolved is None:                                # by='all'
            figures = [_plan_all_samples(dataset, positions, make_curves, make_figure)]
        elif merge_groups:
            figures = [_plan_merged(resolved, positions, make_curves, make_figure)]
        else:
            figures = _plan_separate(resolved, positions, make_curves, make_figure)

    # 映射的范围要等全部曲线生成后才知道：大小按图层各自换算，颜色条各图共用
    for layer, curves in zip(layers, made):
        scatters = [curve for curve in curves if isinstance(curve, ScatterSpec)]
        if layer.mapping is not None and layer.mapping.size is not None:
            _apply_sizes(scatters, layer.mapping.size_range)
        if layer.mapping is not None and layer.mapping.color is not None and colorbar_style is not None:
            resolved_bar = _resolve_colorbar(scatters, colorbar_style, layer.mapping.color, dataset)
            for figure in figures:
                figure.colorbar = resolved_bar
    return figures


def _channels(layer: Layer) -> tuple[int, int]:
    """图层的 (X 通道, Y 通道)；没写时报错（``DataPlotter.plot`` 会先补成构造时的通道）。"""
    if layer.x is None or layer.y is None:
        raise ValueError(f"图层要写明通道（x、y），实际是 {layer!r}")
    return layer.x, layer.y


def _check_layers(layers: list[Layer], by: str, merge_groups: bool) -> None:
    """
    在取数前校验分图方式、图层组合及各坐标轴的负对数设置。
    """
    if not layers:
        raise ValueError("至少要一个图层，如 [Layer(0, 1)]")
    if by not in _BY:
        raise ValueError(f"by 只能是 'all'、'group'、'sample'，实际是 {by!r}")
    if merge_groups and by != 'group':
        raise ValueError(f"merge_groups 只用于 by='group'，当前 by={by!r}")
    for layer in layers:
        _channels(layer)
        if layer.kind not in _KINDS:
            raise ValueError(f"不支持的画法 {layer.kind!r}，图层可选 'line'、'scatter'")
        if layer.side not in _SIDES:
            raise ValueError(f"图层的 side 只能是 'left'、'right'，实际是 {layer.side!r}")
        if layer.mapping is not None:
            if layer.kind != 'scatter':
                raise ValueError(f"只有散点图层能写 mapping（第三通道映射），这一层是 kind={layer.kind!r}")
            _check_mapping(layer.mapping)
    if sum(_maps_color(layer) for layer in layers) > 1:
        raise ValueError("一次绘图只能有一个颜色映射层（ScatterMap(color=...)）：一张图只设计了一个颜色条")
    if not any(layer.side == 'left' for layer in layers):
        raise ValueError("至少要有一个左侧图层：两侧共用的 X 轴按左侧图层定（单位、负号）")
    if len(layers) > 1 and by != 'sample':
        raise ValueError(f"by={by!r} 暂不支持多个图层（一张图多个样品时，各层的颜色和图例规则未定）；"
                         f"每样品一张（by='sample'）时可以画多层")
    if len({layer.neglog_x for layer in layers if layer.side == 'left'}) > 1:
        raise ValueError("左侧图层的 neglog_x 要写得一致：它们共用的 X 轴只能有一种刻度符号")
    for side in _SIDES:
        if len({layer.neglog_y for layer in layers if layer.side == side}) > 1:
            raise ValueError(f"{side} 侧图层的 neglog_y 要写得一致：它们共用一根 Y 轴")


def _maps_color(layer: Layer) -> bool:
    """这个图层是否把某个通道映射成颜色。"""
    return layer.mapping is not None and layer.mapping.color is not None


def _check_mapping(mapping: ScatterMap) -> None:
    """校验散点映射：类型、至少一个通道、通道号是整数、``size_range`` 是两个有限正数且下限不大于上限。"""
    if not isinstance(mapping, ScatterMap):
        raise TypeError(f"mapping 要写 ScatterMap(color=..., size=...)，实际是 {type(mapping).__name__}")
    if mapping.color is None and mapping.size is None:
        raise ValueError("ScatterMap 至少要写 color 或 size 中的一个通道号")
    for name in ('color', 'size'):
        channel = getattr(mapping, name)
        if channel is not None and (not isinstance(channel, Integral) or isinstance(channel, bool)):
            raise TypeError(f"ScatterMap 的 {name} 要写通道号（整数），实际是 {channel!r}")
    size_range = mapping.size_range
    if not isinstance(size_range, (tuple, list)) or len(size_range) != 2:
        raise ValueError(f"ScatterMap 的 size_range 要写 (最小直径, 最大直径) 两个数（磅），实际是 {size_range!r}")
    if not all(isinstance(d, Real) and not isinstance(d, bool) for d in size_range):
        raise TypeError(f"ScatterMap 的 size_range 要写数字（磅），实际是 {size_range!r}")
    low, high = size_range
    if not (math.isfinite(low) and math.isfinite(high) and 0 < low <= high):
        raise ValueError(f"ScatterMap 的 size_range 要写两个有限正数，下限不大于上限，实际是 {size_range!r}")


def _check_colorbar(layers: list[Layer], colorbar: ColorbarStyle | None) -> ColorbarStyle | None:
    """
    叠上库默认并校验颜色条，返回这次绘图的颜色条外观；没有颜色映射层时返回 None。

    给了 *colorbar* 却没有颜色映射层时报错：否则这份设置会被悄悄忽略。
    """
    if not any(_maps_color(layer) for layer in layers):
        if colorbar is not None:
            raise ValueError("给了 colorbar，但没有颜色映射层（Layer(kind='scatter', mapping=ScatterMap(color=...))），"
                             "颜色条不会画出来")
        return None
    if colorbar is not None and not isinstance(colorbar, ColorbarStyle):
        raise TypeError(f"colorbar 要写 ColorbarStyle(...)，实际是 {type(colorbar).__name__}")
    style = DEFAULT_COLORBAR.updated(colorbar)
    check_colorbar_style(style)
    return style


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
                axis: Axis = 'left', label_from: Literal['name', 'unit'] = 'name',
                mapping: ScatterMap | None = None) -> Curve:
    """
    取一个样品的 X、Y 数据，按 *kind* 生成 `LineSpec` 或 `ScatterSpec`，样式按画法从分组读取。

    各计划函数预先绑定画法、分组和用于读取曲线的共用参数，包括已经校验的列位置索引；
    调用处只给样品号、分组名、色带位置。

    对映射散点按原始行对齐各通道。排除坐标非有限或映射值缺失的行，保留其余行的映射原值。
    `plan_figures` 收集全部样品后，使用共享范围将大小值换算为直径。颜色映射覆盖分组颜色。
    """
    spec_type, read_style = _KINDS[kind]
    x, y, _, name, _, unit = get_xy_data(
        dataset, sample, channel_x, channel_y,
        neglog_x=neglog_x, neglog_y=neglog_y, plotrange=plotrange, positions=positions,
    )
    label = name if label_from == 'name' else unit
    style = read_style(groups, group_name)
    if mapping is None:
        return spec_type(sample_idx=sample, x=x, y=y, label=label,
                         group_name=group_name, color_position=color_position,
                         style=style,       # type: ignore[arg-type]  _KINDS 里类型与样式一一对应
                         axis=axis)

    values = {role: _mapping_values(dataset, sample, channel, plotrange, positions, role)
              for role, channel in (('size', mapping.size), ('color', mapping.color)) if channel is not None}
    keep = np.isfinite(x) & np.isfinite(y)          # 排除不可绘制的坐标及对应的映射值。
    for column in values.values():
        keep &= ~np.isnan(column)
    if mapping.color is not None:
        style = replace(style, color=None)
    return ScatterSpec(sample_idx=sample, x=x[keep], y=y[keep], label=label,
                       group_name=group_name, color_position=color_position,
                       style=style, axis=axis,      # type: ignore[arg-type]  散点读的是 ScatterStyle
                       sizes=values['size'][keep] if 'size' in values else None,
                       colors=values['color'][keep] if 'color' in values else None,
                       color_unit=None if mapping.color is None else channel_unit(dataset, mapping.color))


def _mapping_values(dataset: DataSet, sample: int, channel: int, plotrange: int | None,
                    positions: Mapping[tuple[int, int], int], role: str) -> np.ndarray:
    """取一个样品映射通道的前 *plotrange* 行（至少双精度）；是复数或有无穷大时报错。"""
    column, _, unit = get_column_data(dataset, sample, channel, plotrange, positions=positions)
    what = '颜色' if role == 'color' else '大小'
    if np.iscomplexobj(column):
        raise ValueError(f"样品 {sample} 的通道 {channel}（{unit}）是复数，不能直接映射成{what}；"
                         f"请先用变换器取模（np.abs）或实部，存成实数通道再映射")
    column = np.asarray(column, dtype=np.promote_types(np.asarray(column).dtype, np.float64))
    if np.isinf(column).any():
        raise ValueError(f"样品 {sample} 的通道 {channel}（{unit}）有无穷大，不能映射成{what}")
    return column


def _apply_sizes(scatters: list[ScatterSpec], size_range: tuple[float, float]) -> None:
    """
    把一个图层各条散点的原始大小值按共用范围换成直径（磅），原地改写 ``sizes``。

    面积线性：数值从最小到最大，面积从 ``size_range[0]²`` 变到 ``size_range[1]²``；整列相同时取面积的中点。
    先各除以 2 再相减，数值跨度接近浮点上限时也不溢出。
    """
    present = [curve.sizes for curve in scatters if curve.sizes is not None and curve.sizes.size]
    if not present:
        return
    low = min(float(values.min()) for values in present)
    high = max(float(values.max()) for values in present)
    small, large = (d ** 2 for d in size_range)
    for curve in scatters:
        if curve.sizes is None:
            continue
        if high > low:
            fraction = (curve.sizes / 2 - low / 2) / (high / 2 - low / 2)
        else:
            fraction = np.full_like(curve.sizes, 0.5)
        curve.sizes = np.sqrt(small + fraction * (large - small))


def _resolve_colorbar(scatters: list[ScatterSpec], style: ColorbarStyle, channel: int,
                      dataset: DataSet) -> ColorbarStyle:
    """
    根据各图的可绘制点补齐颜色范围，默认以颜色通道的列标题命名颜色条。
    两端均为自动值且颜色值相同时，扩展范围以统一两个后端的着色结果。

    Raises
    ------
    ValueError
        对数色标的颜色值非正、范围无效、自动扩展前的端点量级超过 ``1e300``，或自动定界时没有可绘制点。
    """
    present = [curve.colors for curve in scatters if curve.colors is not None and curve.colors.size]
    unit = channel_unit(dataset, channel)
    if style.scale == 'log' and any((values <= 0).any() for values in present):
        raise ValueError(f"对数色标要求颜色值都为正：颜色通道 {channel}（{unit}）有不为正的值；"
                         f"请改用线性色标，或先把数据变换后再映射")
    low, high = style.limits if style.limits is not None else (None, None)
    if (low is None or high is None) and not present:
        raise ValueError(f"颜色通道 {channel}（{unit}）没有可画的点，无法自动确定颜色条的范围；请写全 limits")
    automatic = low is None and high is None
    if low is None:
        low = min(float(values.min()) for values in present)
    if high is None:
        high = max(float(values.max()) for values in present)
    if max(abs(low), abs(high)) > _COLOR_LIMIT:
        raise ValueError(f"颜色条的范围 ({low:g}, {high:g}) 量级超过 ±1e300：matplotlib 在接近浮点上限时"
                         f"画不出颜色条；请先缩放数据（如换单位），或用 limits 写一个更小的范围")
    if automatic and low == high:
        low, high = _widen(low, style.scale == 'log')
    if not low < high:
        raise ValueError(f"颜色条的 limits 补齐后下限不小于上限：({low}, {high})；请检查写了的那一端")
    return replace(style, limits=(float(low), float(high)), title=unit if style.title is None else style.title)


# 在等值范围扩展前检查端点，为 Matplotlib 计算刻度预留数值余量。
_COLOR_LIMIT = 1e300


def _widen(value: float, log: bool) -> tuple[float, float]:
    """
    扩展自动计算的等值范围，使该值位于色带中点。

    线性撑开成 ``(v - |v| / 2, v + |v| / 2)``，v 为 0 时是 ``(-0.5, 0.5)``；对数各撑开半个数量级 ``(v / √10, v × √10)``。
    调用前已检查 ``|v| ≤ _COLOR_LIMIT``，撑开后不会溢出。
    """
    if log:
        return value / math.sqrt(10), value * math.sqrt(10)
    half = abs(value) / 2 or 0.5
    return value - half, value + half


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


def _plan_all_samples(dataset: DataSet, positions: dict, make_curves: MakeCurves,
                      make_figure: MakeFigure) -> FigureSpec:
    """不分组：一张 'main' 图，全部样品按样品号排序，没有分组名和样式。"""
    curves = [curve for sample in sorted(set(dataset.sample_idx))
              for curve in make_curves(sample, None, positions[sample])]
    return make_figure('main', curves, None)


def _plan_separate(groups: Group, positions: dict, make_curves: MakeCurves,
                   make_figure: MakeFigure) -> list[FigureSpec]:
    """分离模式：每个分组一张图，颜色按样品。"""
    figures = []
    for name in groups:
        curves = [curve for sample in groups.sample_ids(name)
                  for curve in make_curves(sample, name, positions[sample])]
        figures.append(make_figure(name, curves, name))
    return figures


def _plan_merged(groups: Group, positions: dict, make_curves: MakeCurves,
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
        curves.extend(make_curves(sample, name, positions[head]))
    return make_figure('main', curves, None)


# ============================================================================
# 柱状图计划
# ============================================================================
_BAR_DIMENSIONS: tuple[BarDimension, ...] = ('sample', 'group', 'channel')
_BAR_MODES: tuple[BarMode, ...] = ('group', 'stack')
type BarErrors = Literal['std', 'sem'] | Mapping[int, int] | None


def plan_bars(dataset: DataSet, groups: Group | None, channels: int | Sequence[int], *,
              x: BarDimension = 'sample', series: BarDimension = 'channel',
              reduce: Reduction | None = None, errors: BarErrors = None,
              mode: BarMode = 'group', width: float = 0.8,
              styles: BarStyle | Mapping[int, BarStyle] | Mapping[str, BarStyle] | None = None,
              plotrange: int | None = None, legend_title: str | None = 'auto') -> FigureSpec:
    """
    生成柱状图计划，在 X 轴上排列类别，在每个类别内并排或堆叠各系列。

    数据处理层计算柱高和误差。本函数确定类别、系列顺序和样式。

    Parameters
    ----------
    dataset : DataSet
        数据集。
    groups : Group or None
        分组，只在 *x* 或 *series* 是 ``'group'`` 时使用（检查规则见 `resolve_groups`）。
    channels : int or sequence of int
        画哪几个通道（原数据集里的通道号），按书写顺序排列，不能重复。
    x, series : {'sample', 'group', 'channel'}
        类别（X 轴）和系列（图例）各取哪一维：恰好一个是 ``'channel'``，另一个是 ``'sample'`` 或 ``'group'``。
        样品维画全部样品（按样品号排序），不看分组；``'group'`` 按分组的顺序。
    reduce : str, callable or None, default: None
        每一格多行数据怎么汇总成柱高，写法见 `~plotlib.processor.DataTransformer.Reduce`。
        None 表示每格至多一个有效值，多于一个时报错。用到分组时，先按 *reduce* 汇总每个样品，再组内取平均。
    errors : {'std', 'sem'}, dict or None, default: None
        误差棒。``'std'`` / ``'sem'``：用到分组时是组内各样品汇总值之间的，否则是同一列多行之间的（要配
        ``reduce='mean'``）。``{值通道: 误差通道}``：误差来自另一个通道，按原行与柱高对齐
        （见 `~plotlib.processor.reduce_with_error`），用到分组时不能用。
    mode : {'group', 'stack'}, default: 'group'
        并排或堆叠（正负值分开叠）。
    width : float, default: 0.8
        一个类别里全部柱子占间距的比例，在 (0, 1] 之间。
    styles : BarStyle or dict, optional
        一个 `BarStyle` 用于全部系列；``{系列键: BarStyle}`` 逐个系列指定。优先于分组配置。
    plotrange : int, optional
        每列只取前几行再汇总；None 取全部。
    legend_title : str or None, default: 'auto'
        图例标题；``'auto'`` 和 None 都不加。

    Returns
    -------
    FigureSpec
        一张 key 为 ``'main'``、版式为 ``'bars'`` 的图，每个系列一个 `~plotlib.plot_spec.BarSpec`。

    Raises
    ------
    ValueError
        维度、模式、柱宽、汇总方式、误差写错或组合不支持；通道重复或不存在；用到 ``'group'`` 却没有分组；
        *styles* 的键不是系列的键；写了 *errors* 却没有一根柱算得出误差；某一格有多个值却没写 *reduce*。
    TypeError
        通道号、柱宽、样式的类型不对。
    RuntimeError
        数据集为空。

    Notes
    -----
    - **系列的键**：样品号、通道号（原数据集里的）或组名。
    - **颜色**：系列是样品 → 按样品在整个数据集里的排名取色带；是分组 → 分组写的 ``color``，没写用组首样品的位置；
      是通道 → 按在 *channels* 里的名次取色带。分组写的 ``color``、``hatch`` 只在系列是分组时生效。
    - **Y 轴标题**：一个通道是它的列标题；多个通道只在列标题完全相同时沿用，否则留空。
    - **缺数据**：某格全是 NaN 时保留位置、不画。
    """
    channels = _bar_channels(channels)
    by_group = 'group' in (x, series)
    _check_bar_options(x, series, reduce, errors, mode, width, by_group)
    index = dataset.column_positions
    _check_not_empty(dataset)
    resolved = resolve_groups(groups, dataset) if by_group else None
    if resolved is not None and not resolved.names:
        raise ValueError("x 或 series 用到 'group' 要有分组：请在 DataPlotter(groups=...) 里给出；"
                         "画全部样品写 'sample'")
    available = set(dataset.channel_idx)
    error_map = dict(errors) if isinstance(errors, Mapping) else None
    for channel in channels + list((error_map or {}).values()):
        if channel not in available:
            raise ValueError(f"数据集里没有通道 {channel}，已有通道 {sorted(available)}")
    if error_map is not None and not set(error_map) <= set(channels):
        raise ValueError(f"误差字典的键 {sorted(set(error_map) - set(channels))} 不在 channels={channels} 里")

    # 成员（样品或分组）和系列的键不用汇总就能定下，样式在汇总之前校验
    samples = sorted(set(dataset.sample_idx))
    members: list[int] | list[str] = samples if resolved is None else resolved.names
    keys: list = list(channels) if series == 'channel' else list(members)
    _check_bar_styles(styles, keys)

    used_samples = samples if resolved is None else sorted({s for name in resolved for s in resolved.sample_ids(name)})
    _check_finite(dataset, index, used_samples, channels, error_map, plotrange)
    units = [channel_unit(dataset, channel) for channel in channels]
    # 汇总成一张表：行是成员，列是通道（按 channels 的顺序，保留原通道号）
    if resolved is None:
        member_names = [sample_name(dataset, sample, positions=index) for sample in samples]
        table, table_errors = _sample_table(dataset, index, samples, member_names, channels, reduce, errors,
                                            error_map, plotrange)
    else:
        member_names = list(resolved.names)
        table, table_errors = _group_table(resolved, plotrange, channels, reduce, errors)

    if np.isinf(table).any():
        i, j = np.argwhere(np.isinf(table))[0]
        raise ValueError(f"{member_names[i]} 的 {units[j]} 汇总出的柱高是 {table[i, j]}：柱高要是有限的数"
                         "（无穷大画不出来；NaN 表示缺数据、保留位置不画）")
    if table_errors is not None:
        _check_bar_errors(table, table_errors, errors, member_names, units)

    if series == 'channel':
        labels, categories = units, member_names
        heights, series_errors = table.T, None if table_errors is None else table_errors.T
    else:
        labels, categories = member_names, units
        heights, series_errors = table, table_errors

    bars = []
    for i, key in enumerate(keys):
        errors_i = None if series_errors is None else series_errors[i]
        if series == 'channel' and error_map is not None and key not in error_map:
            errors_i = None                         # 没写误差通道的系列不画误差棒
        color_position, group_name, style = _bar_series_style(key, i, len(keys), series, dataset, resolved)
        if isinstance(styles, BarStyle):
            style = style.updated(styles)
        elif styles is not None:
            style = style.updated(styles.get(key))
        bars.append(BarSpec(
            key=key, label=labels[i], group_name=group_name, color_position=color_position,
            categories=list(categories), heights=heights[i], errors=errors_i,
            caps=errors_i is None or not np.any(~np.isnan(heights[i]) & np.isnan(errors_i)),
            series_index=i, series_count=len(keys), mode=mode, width=width, style=style,
        ))
    return FigureSpec(key='main', curves=list(bars), x_unit='', y_unit=units[0] if len(set(units)) == 1 else '',
                      layout='bars', legend_title=None if legend_title == 'auto' else legend_title)


def _bar_channels(channels) -> list[int]:
    """规范 *channels*：单个通道号写成列表；不能为空、不能重复，只收整数。"""
    written = [channels] if isinstance(channels, Integral) else list(channels)
    if not written:
        raise ValueError("channels 至少要一个通道")
    for channel in written:
        if isinstance(channel, bool) or not isinstance(channel, Integral):
            raise TypeError(f"通道号要写整数，实际是 {channel!r}")
    result = [int(channel) for channel in written]
    duplicates = sorted({c for c in result if result.count(c) > 1})
    if duplicates:
        raise ValueError(f"channels 里有重复的通道 {duplicates}：每个通道只能是一个系列或类别")
    return result


def _check_bar_options(x, series, reduce, errors, mode, width, by_group: bool) -> None:
    """入口校验：维度、模式、柱宽、汇总方式和误差的写法与组合，在取数之前报错。"""
    for name, value in (('x', x), ('series', series)):
        if value not in _BAR_DIMENSIONS:
            raise ValueError(f"{name} 只能是 'sample'、'group'、'channel'，实际是 {value!r}")
    if (x == 'channel') == (series == 'channel'):
        raise ValueError(f"x 和 series 要恰好一个是 'channel'、另一个是 'sample' 或 'group'，"
                         f"实际是 x={x!r}、series={series!r}")
    if mode not in _BAR_MODES:
        raise ValueError(f"mode 只能是 'group'（并排）、'stack'（堆叠），实际是 {mode!r}")
    if isinstance(width, bool) or not isinstance(width, Real):
        raise TypeError(f"width 要写 (0, 1] 之间的数，实际是 {width!r}")
    if not 0 < float(width) <= 1:                   # NaN 也不满足
        raise ValueError(f"width 要在 (0, 1] 之间，实际是 {width!r}")
    check_reduction(reduce)
    if isinstance(errors, Mapping):
        if by_group:
            raise ValueError("用到分组时不能写误差字典：组内合并各样品的误差要做误差传递，没有唯一的算法；"
                             "请用 errors='std' 或 'sem'（组内各样品之间）")
        for value_channel, error_channel in errors.items():
            for channel in (value_channel, error_channel):
                if isinstance(channel, bool) or not isinstance(channel, Integral):
                    raise TypeError(f"误差字典要写 {{值通道: 误差通道}}，通道号是整数，实际是 {channel!r}")
    elif errors is not None and errors not in ('std', 'sem'):
        raise ValueError(f"errors 只能是 'std'、'sem'、{{值通道: 误差通道}} 或 None，实际是 {errors!r}")
    elif errors is not None and not by_group and reduce != 'mean':
        raise ValueError(f"不用分组时，errors={errors!r} 是同一列多行之间的离散程度，柱高要是均值：请写 reduce='mean'")


def _check_bar_errors(table: np.ndarray, table_errors: np.ndarray, errors, member_names: list[str],
                      units: list[str]) -> None:
    """
    校验汇总后的误差：NaN 表示这根柱没有误差，其余必须有限且非负（原始误差都合法时，函数汇总也可能得到负数或无穷大）；
    指定误差时，至少一根有效柱须有可绘制的误差棒。
    """
    bad = ~np.isnan(table_errors) & ~(np.isfinite(table_errors) & (table_errors >= 0))
    if bad.any():
        i, j = np.argwhere(bad)[0]
        raise ValueError(f"{member_names[i]} 的 {units[j]} 汇总出的误差是 {table_errors[i, j]}："
                         "误差要是有限的非负数（NaN 表示这根柱没有误差）")
    if not np.any(~np.isnan(table) & ~np.isnan(table_errors)):
        raise ValueError(f"写了 errors={errors!r}，但没有一根柱算得出误差（如每格只有一个值、每组只有一个样品），"
                         "图上不会有误差棒")


def _check_finite(dataset: DataSet, index: Mapping[tuple[int, int], int], samples: list[int], channels: list[int],
                  error_map: dict[int, int] | None, plotrange: int | None) -> None:
    """
    在汇总前校验选定样品和通道的前 *plotrange* 行。
    相反符号的无穷大求均值会产生 NaN，须在计算前区分无穷大与缺失值。
    """
    error_channels = set((error_map or {}).values())
    for sample in samples:
        for channel in [*channels, *sorted(error_channels - set(channels))]:
            position = index.get((sample, channel))
            if position is None or not np.isinf(dataset.data[:plotrange, position]).any():
                continue
            kind = '误差通道 ' if channel in error_channels else ''
            raise ValueError(f"样品 {dataset.names[position]}（样品号 {sample}）的{kind} {dataset.units[position]} 有无穷大："
                             "柱状图只用 NaN 表示缺数据，无穷大画不出来")


def _sample_table(dataset: DataSet, index: Mapping[tuple[int, int], int], samples: list, names: list[str],
                  channels: list[int], reduce, errors, error_map: dict[int, int] | None, plotrange: int | None):
    """不用分组：每个样品、每个通道汇总成一格（只取前 *plotrange* 行）；误差是同一列多行之间的，或来自误差通道（按原行对齐）。"""
    table = np.full((len(samples), len(channels)), np.nan)
    table_errors = None if errors is None else np.full_like(table, np.nan)
    for i, (sample, name) in enumerate(zip(samples, names)):
        for j, channel in enumerate(channels):
            if (sample, channel) not in index:
                raise ValueError(f"样品 {name}（样品号 {sample}）没有通道 {channel}")
            column = dataset.data[:plotrange, index[(sample, channel)]]
            where = f"样品 {name}（样品号 {sample}）的 {dataset.units[index[(sample, channel)]]} "
            if error_map is not None and channel in error_map:
                if (sample, error_map[channel]) not in index:
                    raise ValueError(f"样品 {name}（样品号 {sample}）没有误差通道 {error_map[channel]}")
                table[i, j], table_errors[i, j] = reduce_with_error(       # type: ignore[index]
                    column, dataset.data[:plotrange, index[(sample, error_map[channel])]], reduce, where)
                continue
            table[i, j] = reduce_values(column, reduce, where)
            if error_map is None and table_errors is not None:
                table_errors[i, j] = reduce_values(column, errors, where)
    return table, table_errors


def _group_table(groups: Group, plotrange: int | None, channels: list[int], reduce, errors):
    """
    按组计算柱高和误差，使用各样品的汇总值作为组内统计的输入。
    ``Group.reduce(rows=...)`` 在读取原分组的数据时截取行。
    """
    shape = (len(groups.names), len(channels))      # Group.reduce 的结果按「分组 → 通道」排列
    if errors is None:
        return groups.reduce('mean', within=reduce, channels=channels, rows=plotrange).data[0].reshape(shape), None
    # 一次算：柱高和误差用同一批样品汇总值（reduce 是函数时只对每个样品调用一次）
    means, spreads = groups.reduce(['mean', errors], within=reduce, channels=channels, rows=plotrange)
    return means.data[0].reshape(shape), spreads.data[0].reshape(shape)


def _bar_series_style(key, index: int, count: int, series: BarDimension, dataset: DataSet,
                      groups: Group | None) -> tuple[float | None, str | None, BarStyle]:
    """一个系列的默认配色位置、分组名和分组样式（只有系列是分组时读分组的 ``color``、``hatch``）。"""
    if series == 'sample':
        return color_positions(dataset.sample_idx)[key], None, BarStyle()
    if series == 'group':
        assert groups is not None
        head = groups.sample_ids(key)[0]
        return (color_positions(dataset.sample_idx)[head], key,
                BarStyle(color=groups.color(key), hatch=groups.hatch(key)))
    return index / count, None, BarStyle()


def _check_bar_styles(styles, keys: list) -> None:
    """*styles* 是一个 `BarStyle`、``{系列键: BarStyle}`` 或 None；键必须是系列的键，样式逐个校验。"""
    if styles is None:
        return
    if isinstance(styles, BarStyle):
        check_bar_style(styles)
        return
    if not isinstance(styles, Mapping):
        raise TypeError(f"styles 要写 BarStyle 或 {{系列键: BarStyle}}，实际是 {type(styles).__name__}")
    unknown = [key for key in styles if key not in keys]
    if unknown:
        raise ValueError(f"styles 的键 {unknown} 不是系列的键，可用 {keys}")
    for key, style in styles.items():
        if not isinstance(style, BarStyle):
            raise TypeError(f"styles[{key!r}] 要写 BarStyle，实际是 {type(style).__name__}")
        check_bar_style(style)
