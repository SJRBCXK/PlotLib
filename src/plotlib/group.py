"""
管理命名的样品分组，用于分组绘图和计算。
"""
import copy
from collections.abc import Callable
from numbers import Integral
from collections import Counter



import numpy as np
from .dataset import DataSet
from .processor import DataProcessLayer
from .style import check_color, check_linestyle, check_marker


# 除单个整数外，num 支持以下序列类型。
_NUM_CONTAINERS = (list, tuple, range, np.ndarray)

# 校验跨后端通用的样式字段。其他选项作为自定义元数据保留。
_STYLE_CHECKS = {'linestyle': check_linestyle, 'marker': check_marker, 'color': check_color}


def _resolve_num(num) -> list[int]:
    """
    将 `_check_group` 校验后的 ``num`` 统一转换为 ``list[int]``。
    """
    if isinstance(num, Integral):
        return [int(num)]
    return [int(i) for i in num]


def _check_group(group_name, group_config, available: set[int]) -> dict:
    """
    校验一个分组的配置，原地把 ``'num'`` 整理成 ``list[int]``，返回 ``{分组名: 该配置}``。

    校验配置结构、样品号和样式字段。*available* 为数据集中的有效样品号。
    校验成功后将配置中的 ``num`` 原地转换为 ``list[int]``。

    Raises
    ------
    TypeError
        配置不是字典；``num`` 的类型不对或含非整数；样式字段的类型不对。
    ValueError
        缺少 ``num``；``num`` 为空、有重复或有数据集里没有的样品号；样式字段的取值不对。
        信息里都带分组名。
    """
    if not isinstance(group_config, dict):
        raise TypeError(
            f"数据分组配置错误：'{group_name}' 的配置必须是字典，正确写法示例：{{'num': [...]}}"
        )

    if 'num' not in group_config:
        raise ValueError(f"数据分组配置错误：'{group_name}' 缺少 'num' 键。")

    raw = group_config['num']
    if not isinstance(raw, (Integral, *_NUM_CONTAINERS)):
        raise TypeError(
            f"数据分组配置错误：'{group_name}' 的 'num' 类型不支持：{type(raw).__name__}"
        )
    if not isinstance(raw, Integral):
        # 转换为 int 前校验元素类型，避免截断或隐式转换。
        bad = [i for i in raw if not isinstance(i, Integral)]
        if bad:
            raise TypeError(
                f"数据分组配置错误：'{group_name}' 的 'num' 含非整数元素：{bad[0]!r}"
            )

    num = _resolve_num(raw)
    if not num:
        raise ValueError(f"数据分组配置错误：'{group_name}' 的 'num' 为空。")

    duplicates = [item for item, count in Counter(num).items() if count > 1]
    if duplicates:
        raise ValueError(
            f"数据分组配置错误：'{group_name}' 的 'num' 含重复样品号：{duplicates[0]!r}"
        )

    if not set(num).issubset(available):
        missing = sorted(set(num) - available)
        raise ValueError(
            f"数据分组配置错误：'{group_name}' 的 'num' 包含不存在的样品号：{missing}，已有样品号：{sorted(available)}"
        )

    # 样式值由绘图后端转换，此处仅校验。
    for field, check in _STYLE_CHECKS.items():
        if field in group_config:
            try:
                check(group_config[field])
            except (TypeError, ValueError) as error:
                # 保留异常类型，并补充分组名和字段名。
                raise type(error)(f"数据分组配置错误：'{group_name}' 的 '{field}'：{error}") from error

    group_config['num'] = num
    
    return dict({group_name: group_config})
    





class Group():
    """
    管理同一数据集中的命名样品分组。

    创建时校验所有分组。可通过 `names`、`sample_ids` 和 `options` 查询配置，
    通过 `add`、`set` 和 `delete` 更新分组。批量更新先完成校验，再应用变更。
    `apply` 对每个分组执行一次计算，生成一个结果样品。

    Notes
    -----
    配置采用 ``{分组名: {'num': [样品号, ...], 其他字段...}}`` 的形式。

    - ``num`` 接受单个整数、列表、元组、``range`` 或 NumPy 数组。每组至少包含一个样品，
      且样品号必须存在于数据集中并且互不重复。样品号顺序决定 `apply` 的参数顺序。
    - ``linestyle``、``marker`` 和 ``color`` 采用 `plotlib.style` 中定义的通用取值。
    - 其余字段作为自定义选项保留，可通过 `options` 读取。

    `Group` 持有独立的外层字典，与传入的配置共享各分组的内层字典。
    创建时会原地将内层字典的 ``num`` 转为 ``list[int]``。
    后续应通过 `set` 更新已有分组，以便校验配置。

    Examples
    --------
    >>> groups = Group(data, {
    ...     'Ref': {'num': [0, 1]},
    ...     'Doped': {'num': range(2, 5), 'linestyle': 'dash', 'color': 'red'},
    ... })
    >>> groups.names
    ['Ref', 'Doped']
    >>> groups.sample_ids('Doped')
    [2, 3, 4]
    >>> DataPlotter(data, groups=groups).plot_groups(merge_groups=True)
    """

    def __init__(self, dataset: DataSet, group_config: dict):
        """
        创建分组，并校验全部分组的配置。

        Parameters
        ----------
        dataset : DataSet
            分组所属的数据集。样品号按它校验；绘图时必须用同一个数据集。
        group_config : dict
            ``{分组名: {'num': [...], ...}}``，写法见类说明。其中的 ``num`` 会被原地整理成 ``list[int]``。

        Raises
        ------
        TypeError, ValueError
            配置写法不对，信息里带分组名（详见 `_check_group`）。
        """
        self.dataset = dataset
        # 校验并格式化后的配置：{分组名: {'num': list[int], 其余字段...}}
        self._config: dict[str, dict] = self._validated(group_config)

    # ── 内部工具 ───────────────────────────────────────────────

    def _validated(self, group_config: dict) -> dict[str, dict]:
        """
        逐个校验 *group_config* 中的分组，全部通过才返回 ``{分组名: 整理后的配置}``。
        ``__init__``、`add`、`set` 共用，保证三处规则完全一致。样品号每次现查数据集，不存快照。
        """
        if not isinstance(group_config, dict):
            raise TypeError(
                "数据分组配置错误：分组配置必须是字典 {分组名: {'num': [...]}}，"
                f"实际是 {type(group_config).__name__}"
            )
        # 使用数据集当前的样品号，支持创建分组后继续扩展数据集。
        available = set(self.dataset.ensure_updated().sample_idx)
        validated: dict[str, dict] = {}
        for name, config in group_config.items():
            validated.update(_check_group(name, config, available))
        return validated

    def _require(self, group_name: str) -> dict:
        """取出已有分组的内部配置（不是副本），供读接口和 `delete` 共用；分组不存在时报 `ValueError`。"""
        if group_name not in self._config:
            raise ValueError(f"数据分组配置错误：缺少 '{group_name}' 组。")
        return self._config[group_name]

    @staticmethod
    def _quoted(names) -> str:
        """报错信息里的分组名列表：``'A', 'B'``。"""
        return ', '.join(f"'{name}'" for name in names)

    # ── 读：都返回副本，改返回值不影响 Group ─────────────────────

    @property
    def names(self) -> list[str]:
        """全部分组名，保持书写顺序（返回新列表）。"""
        return list(self._config)

    def __iter__(self):
        """按配置顺序遍历分组名的快照。"""
        # 遍历快照，以支持遍历期间更新分组。
        return iter(self.names)

    def sample_ids(self, group_name: str) -> list[int]:
        """
        返回指定分组的样品号列表，顺序与分组配置一致。

        Raises
        ------
        ValueError
            没有这个分组。
        """
        return list(self._require(group_name)['num'])

    def options(self, group_name: str) -> dict:
        """
        该分组 ``num`` 以外的全部字段（包括三个样式字段和自定义字段），如 ``{'linestyle': 'dash'}``；
        没有时为 ``{}``。返回的是深拷贝。
        """
        config = self._require(group_name)
        return {key: copy.deepcopy(value) for key, value in config.items() if key != 'num'}


    def linestyle(self, group_name: str):
        """返回分组线型，如 ``'dash'`` 或 ``(3, 5)``。未设置时返回 ``None``。"""
        return copy.deepcopy(self._require(group_name).get('linestyle'))

    def marker(self, group_name: str):
        """返回分组标记，如 ``'circle'``。未设置时返回 ``None``。"""
        return copy.deepcopy(self._require(group_name).get('marker'))

    def color(self, group_name: str):
        """返回应用于组内所有样品的颜色。未设置时返回 ``None``。"""
        return copy.deepcopy(self._require(group_name).get('color'))

    def to_config(self) -> dict[str, dict]:
        """当前配置的深拷贝（``num`` 已整理成列表），可以保存、打印或用来创建新的 `Group`。"""
        return copy.deepcopy(self._config)

    # ── 改：先校验全部、再修改；都返回 self，可链式调用 ────────────

    def add(self, group_config: dict) -> Group:
        """
        新增分组，加在最后。

        Parameters
        ----------
        group_config : dict
            ``{分组名: 配置}``，可以一次加多个。

        Returns
        -------
        Group
            ``self``，可以链式调用。

        Raises
        ------
        ValueError
            有分组名已存在（替换请用 `set`）；或配置写法不对。此时一个分组都不加。
        """
        validated = self._validated(group_config)
        existing = [name for name in validated if name in self._config]
        if existing:
            raise ValueError(
                f"数据分组配置错误：分组 {self._quoted(existing)} 已存在；替换已有分组请用 set。"
            )
        self._config.update(validated)
        return self

    def set(self, group_config: dict) -> Group:
        """
        替换已有分组的配置并保留其顺序。

        Parameters
        ----------
        group_config : dict
            ``{分组名: 新配置}``，可以一次替换多个。

        Returns
        -------
        Group
            ``self``，可以链式调用。

        Raises
        ------
        ValueError
            有分组名不存在（新增请用 `add`）；或配置写法不对。此时一个分组都不改。
        """
        validated = self._validated(group_config)
        missing = [name for name in validated if name not in self._config]
        if missing:
            raise ValueError(
                f"数据分组配置错误：分组 {self._quoted(missing)} 不存在；新增分组请用 add。"
            )
        self._config.update(validated)
        return self

    def delete(self, group_name: str) -> Group:
        """
        删除分组，返回 ``self``。

        Raises
        ------
        ValueError
            没有这个分组。
        """
        self._require(group_name)
        del self._config[group_name]
        return self

    # ── 计算 ──────────────────────────────────────────────────


    def apply(
        self,
        callback: Callable[..., np.ndarray | float],
        select: tuple | None = None,
        naming: Callable | None = None,
    ) -> DataSet:
        """
        对每个分组执行计算，并将各组的结果合并为一个数据集。

        筛选并对齐输入列后，将每个样品的子数据集传给 *callback*。
        每个分组的计算结果构成一个新样品。

        Parameters
        ----------
        callback : callable
            以 ``callback(*slices)`` 调用。每个参数是一个样品的子数据集，按配置中的 ``num`` 排列。
            子数据集的列顺序由 *select* 决定。返回值可以是形状为 ``(行数, 结果列数)`` 的数组、
            一维数组或数值标量。一维数组转换为单列，标量转换为 1 × 1 数组。
        select : tuple, optional
            每组再筛选列的条件，按顺序交给 `~plotlib.processor.DataProcessLayer.by`，
            如 ``("Frequency(Hz)", "Zs'(ohm)", "Zs''(ohm)")``；None 表示用全部列。
        naming : callable, optional
            ``naming(slices, result_data) -> (names, units)``，两个列表的长度都必须等于结果列数。
            *callback* 改变了列的顺序或个数（如把频率列放在最前面）时必须提供，否则名字、单位会错位。
            不给时每列都叫 ``组名_函数名`` （如分组 ``'diff'`` 用 ``subtract`` 计算得到 ``'diff_subtract'``），
            单位取第一个样品同位置列的单位。

        Returns
        -------
        DataSet
            每个分组一个新样品（样品号从 0 起依次编号），按分组的书写顺序拼接。

        Raises
        ------
        ValueError
            某个样品在 *select* 筛选后没有列；同一组的几个样品列数不同。
        RuntimeError
            命名的个数与结果列数不一致；或结果违反数据集约定（如同一通道单位不同）。

        See Also
        --------
        plotlib.processor.DataTransformer : 逐样品计算，结果仍按原样品号对应。

        Examples
        --------
        两个样品做差（结果列顺序与输入一致，可以不写 *naming*）：

        >>> groups = Group(data, {'diff': {'num': [0, 1]}})
        >>> def subtract(*slices):
        ...     return slices[1].data - slices[0].data
        >>> groups.apply(subtract, select=("Zs'(ohm)", "Zs''(ohm)"))

        保留频率列在最前面，必须同时写 *naming* （按单位取列）：

        >>> def subtract_with_freq(s0, s1):
        ...     freq = s0.units.index("Frequency(Hz)")
        ...     zs = [i for i, u in enumerate(s0.units) if u in ("Zs'(ohm)", "Zs''(ohm)")]
        ...     return np.hstack((s0.data[:, [freq]], s1.data[:, zs] - s0.data[:, zs]))
        >>> def naming(slices, result):
        ...     s0 = slices[0]
        ...     freq = s0.units.index("Frequency(Hz)")
        ...     zs = [i for i, u in enumerate(s0.units) if u in ("Zs'(ohm)", "Zs''(ohm)")]
        ...     return ([s0.names[freq]] + [f"Delta_{s0.names[i]}" for i in zs],
        ...             [s0.units[freq]] + [s0.units[i] for i in zs])
        >>> groups.apply(subtract_with_freq, naming=naming)
        """
        accumulated = DataSet()
        result_sample_idx = 0

        for group_name in self:
            sample_ids = self.sample_ids(group_name)    # 创建时已校验：样品号存在、无重复

            # 选出该分组内各样品的列
            dpl = DataProcessLayer(dataset=self.dataset)
            dpl.select("samples", sample_ids)
            if select is not None:
                dpl.by(*select)
            selected = dpl.Selected_data

            # 按样品拆分为对齐的切片，顺序与 num 的书写顺序一致
            slices = []
            for sample in sample_ids:
                col_positions = [
                    i for i in selected.local_idx
                    if selected.sample_idx[i] == sample
                ]
                if not col_positions:
                    raise ValueError(
                        f"组 '{group_name}' 中 sample_idx={sample} 无匹配列。"
                    )
                slice_ds = DataProcessLayer(dataset=selected).getdata(
                    varlist_idx=col_positions,
                    father_dataset=selected
                )
                slices.append(slice_ds)

            # 验证各切片列数一致
            col_counts = [s.data.shape[1] for s in slices]
            if len(set(col_counts)) != 1:
                raise ValueError(
                    f"组 '{group_name}' 各切片列数不一致：{col_counts}"
                )

            # 调用用户回调
            result_data = np.asarray(callback(*slices))
            if result_data.ndim == 0:
                result_data = result_data.reshape(1, 1)
            if result_data.ndim == 1:
                result_data = result_data.reshape(-1, 1)
            n_cols = result_data.shape[1]

            # 命名回调可为新增列提供单位。默认规则依赖输入列的位置。
            if naming is not None:
                result_names, result_units = naming(slices, result_data)
            else:
                result_names, result_units = self._auto_naming(slices, n_cols, group_name, callback)



            # 组装结果切片
            result_slice = DataSet().form_array(
                data=result_data,
                name=result_names,
                unit=result_units,
                sample_idx=result_sample_idx,
                repeat_times=n_cols
            )#type: ignore

            accumulated.expandata(result_slice)
            result_sample_idx += 1

        return accumulated


    def _auto_naming(self, slices, n_cols, group_name, callback):
        """
        没给 ``naming`` 时生成结果的名字和单位：每列都叫 ``组名_函数名``，单位取第一个样品同位置列的单位
        （数据集的约定保证同一位置的通道在各样品里单位相同）。
        """
        cb_name = getattr(callback, '__name__', 'calc')

        names = [f"{group_name}_{cb_name}"] * n_cols

        # units 取第一个 slice（_channel_units_unify_check 保证同位置 unit 一致）
        units = [slices[0].units[col_idx] for col_idx in range(n_cols)]

        return names, units
