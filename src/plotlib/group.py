"""
分组：`Group` 是若干样品组成的、有名字的集合，用于分组绘图（``DataPlotter.plot_groups``）
和逐分组计算（`Group.apply`）。
"""
import copy
from collections.abc import Callable
from numbers import Integral
from collections import Counter



import numpy as np
from .dataset import DataSet
from .processor import DataProcessLayer
from .style import check_color, check_linestyle, check_marker


# num 支持的写法：单个整数，或这几种容器
# （data_reorder_app 生成的配置中，单元素组为 int，连续多元素组为 range）
_NUM_CONTAINERS = (list, tuple, range, np.ndarray)

# 有专门读接口的样式字段 → 校验函数。值只收 style.py 的标准写法，原样保存，翻译在后端渲染时做。
# 其余字段（如 'label'）不检查，原样保存在 options 里。
_STYLE_CHECKS = {'linestyle': check_linestyle, 'marker': check_marker, 'color': check_color}


def _resolve_num(num) -> list[int]:
    """
    把已经校验过的 ``num`` 转成 ``list[int]``：单个整数变成 ``[n]``，容器逐个转成 Python 的 int。
    只做转换，不做检查，调用前必须先经过 `_check_group` 的类型与元素检查。
    """
    if isinstance(num, Integral):
        return [int(num)]
    return [int(i) for i in num]


def _check_group(group_name, group_config, available: set[int]) -> dict:
    """
    校验一个分组的配置，原地把 ``'num'`` 整理成 ``list[int]``，返回 ``{分组名: 该配置}``。

    检查顺序：是不是字典 → 有没有 ``num`` → ``num`` 的类型 → 元素是不是整数 → 是否为空 → 有无重复 →
    是否都在数据集里 → 样式字段是不是标准写法。*available* 是数据集里现有的样品号，由调用方传入；
    本函数不读写任何对象的状态（传入的配置除外，其中的 ``num`` 被原地整理）。

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
        # 逐个检查元素：直接 int() 会把 1.9 截成 1、把 '2' 转成 2，样品号写错也不报错
        bad = [i for i in raw if not isinstance(i, Integral)]
        if bad:
            raise TypeError(
                f"数据分组配置错误：'{group_name}' 的 'num' 含非整数元素：{bad[0]!r}"
            )

    num = _resolve_num(raw)
    if not num:
        # 空分组会在绘图和计算中被静默忽略，必须报错
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

    # 样式字段：只校验，不改写（与 num 不同，标准写法本身就是统一格式）
    for field, check in _STYLE_CHECKS.items():
        if field in group_config:
            try:
                check(group_config[field])
            except (TypeError, ValueError) as error:
                # 保留原来的异常类型，在前面补上分组名和字段名
                raise type(error)(f"数据分组配置错误：'{group_name}' 的 '{field}'：{error}") from error

    group_config['num'] = num
    
    return dict({group_name: group_config})
    





class Group():
    """
    分组：若干样品组成的、有名字的集合，是分组配置的唯一主人。

    创建时解析并校验全部分组，之后其他地方只向它要结果，不再自己解析配置。

    - **读**：`names`、``for name in group``、`sample_ids`、`options`、`linestyle` / `marker` / `color`、
      `to_config`，返回的都是副本；
    - **改**：`add` / `set` / `delete`，先校验全部、再修改，任何一个分组不合法就一个都不改；
    - **算**：`apply`，每个分组得到一个新样品。

    Notes
    -----
    **配置写法。** 只接受完整写法 ``{分组名: {'num': [样品号, ...], 其余字段...}}``：

    - ``num``：样品号，可以写单个整数、列表、元组、``range`` 或 numpy 数组，不能为空、不能重复，
      必须都在数据集里；书写顺序有意义（`apply` 里是 ``slices`` 的顺序，合并绘图时是优先级）；
    - ``linestyle`` / ``marker`` / ``color``：分组绘图的样式，只收标准写法（如 ``'dash'``、``'circle'``、
      ``'red'``，见 `plotlib.style`），创建时校验、原样保存；
    - 其余字段（如 ``'label'``）不检查，原样保存，用 `options` 读取。

    **传入的配置会被原地整理。** 每个分组的 ``num`` 被整理成 ``list[int]``，后续处理不再各自解析；
    增删分组只改 `Group` 自己的外层字典，不会往原字典里加、删分组。`Group` 与传入的字典共用各分组的配置对象，
    所以创建之后在脚本里直接改分组配置会绕过校验，请用 `set`。

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
        # 外层字典是 Group 自己的；下划线开头表示内部数据，请通过下面的方法读写
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
        # 每次现查数据集里的样品号，不存快照：创建 Group 后 DataSet 还可能被 expandata 扩充
        available = set(self.dataset.sample_idx)
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
        """``for name in group``：按书写顺序遍历分组名，与遍历字典得到键一样；循环里增删分组也不出错。"""
        # 遍历名字列表的副本：循环里即使调用 add / delete 也不会出现「字典在遍历时被修改」的错误
        return iter(self.names)

    def sample_ids(self, group_name: str) -> list[int]:
        """
        该分组的样品号，保持书写顺序（顺序就是角色，如 `apply` 里的 ``slices[1] - slices[0]``）。

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

    # 三个常用样式字段的专门读接口：返回用户写的标准写法（style.py），没写时返回 None。
    # 翻译成 matplotlib / Plotly 原生值是后端的事，Group 不关心。

    def linestyle(self, group_name: str):
        """该分组写的线型（标准写法，如 ``'dash'`` 或 ``(3, 5)``）；没写时为 None。"""
        return copy.deepcopy(self._require(group_name).get('linestyle'))

    def marker(self, group_name: str):
        """该分组写的标记（标准写法，如 ``'circle'``）；没写时为 None。"""
        return copy.deepcopy(self._require(group_name).get('marker'))

    def color(self, group_name: str):
        """该分组写的颜色（CSS 颜色名、``'#rrggbb'`` 或 RGB 元组）；没写时为 None。写了就覆盖这组所有样品的按样品配色。"""
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
        整体替换已有分组：旧字段不保留，分组的位置不变。

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
        # 给已有的键重新赋值，字典会保留它原来的位置
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
        callback: Callable[..., np.ndarray],
        select: tuple | None = None,
        naming: Callable | None = None,
    ) -> DataSet:
        """
        逐分组计算：每个分组里的几个样品一起交给 *callback*，每组得到一个新样品。

        对每个分组依次做：选出这组样品的列 →（按 *select* 再筛选）→ 按样品切开、对齐 →
        调用 *callback* → 生成名字和单位 → 装成一个新样品。用户只需提供计算逻辑和可选的命名逻辑。

        Parameters
        ----------
        callback : callable
            ``callback(*slices) -> ndarray``。``slices[i]`` 是这组第 i 个样品的子数据集，
            顺序就是配置里 ``num`` 的书写顺序（顺序即角色，如 ``slices[1] - slices[0]``）；
            每个子数据集的列顺序与 *select* 的条件顺序一致。返回形状 ``(行数, 结果列数)`` 的数组
            （标量、一维数组也可以，会整理成二维）。
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
            result_data = callback(*slices)
            if result_data.ndim == 0:
                result_data = result_data.reshape(1, 1)
            if result_data.ndim == 1:
                result_data = result_data.reshape(-1, 1)
            n_cols = result_data.shape[1]

            # 生成命名：提供了 naming 就只用它。
            # 不能先跑 _auto_naming——它按列号取 slice 的单位，结果列多于输入列时会越界
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