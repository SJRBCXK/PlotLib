import copy
from collections.abc import Callable
from numbers import Integral
from collections import Counter



import numpy as np
from .dataset import DataSet
from .processor import DataProcessLayer


# num 支持的写法：单个整数，或这几种容器
# （data_reorder_app 生成的配置中，单元素组为 int，连续多元素组为 range）
_NUM_CONTAINERS = (list, tuple, range, np.ndarray)


def _resolve_num(num) -> list[int]:
    """
    把已经校验过的 num 转成 list[int]：单个整数 → [n]；容器 → 逐个转成 Python int。
    只做转换，不做检查；调用前必须先经过 _check_group 的类型与元素检查。
    """
    if isinstance(num, Integral):
        return [int(num)]
    return [int(i) for i in num]


def _check_group(group_name, group_config, available: set[int]) -> dict:
    """
    校验一个分组的配置，原地把 'num' 格式化为 list[int]，返回 {分组名: 该配置}。

    检查顺序：是否为字典 → 有无 num → num 的类型 → 元素是否为整数 → 是否为空 → 重复 → 是否在数据集中。
    模块级函数：只依赖传入的参数，不读写任何对象的状态（传入的分组配置除外：num 被原地格式化）。
    available 是数据集里现有的样品号集合，由调用方传入。
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

    group_config['num'] = num
    
    return dict({group_name: group_config})
    





class Group():
    """
    分组：若干样品组成的、有名字的集合，是分组配置的唯一主人。

    配置只接受完整写法：{分组名: {'num': [样品号, ...], 其余字段...}}。
    创建时解析并校验全部分组；之后其他地方只向它要结果，不再自己解析配置。
    - 读：names、for name in group、sample_ids(name)、options(name)、to_config()，都返回副本；
    - 改：add / set / delete，先校验全部、再修改，任何一个分组不合法就一个都不改。

    传入的配置：每个分组的 'num' 会被原地格式化为 list[int]（用户的设计决定：
    输入先统一格式，后续处理不再各自解析）；分组的增删改只改 Group 自己的外层字典，
    不会往原字典里加、删分组。
    已知取舍：Group 与传入字典共用各分组的配置对象，创建后在脚本里直接改分组配置会绕过校验。
    """

    def __init__(self, dataset: DataSet, group_config: dict):
        self.dataset = dataset
        # 校验并格式化后的配置：{分组名: {'num': list[int], 其余字段...}}
        # 外层字典是 Group 自己的；下划线开头表示内部数据，请通过下面的方法读写
        self._config: dict[str, dict] = self._validated(group_config)

    # ── 内部工具 ───────────────────────────────────────────────

    def _validated(self, group_config: dict) -> dict[str, dict]:
        """
        逐个校验 group_config 中的分组，全部通过才返回 {分组名: 格式化后的配置}。
        __init__、add、set 共用，保证三处规则完全一致。
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
        """取出已有分组的内部配置；分组不存在 → ValueError。供读接口和 delete 共用。"""
        if group_name not in self._config:
            raise ValueError(f"数据分组配置错误：缺少 '{group_name}' 组。")
        return self._config[group_name]

    @staticmethod
    def _quoted(names) -> str:
        """报错信息里的分组名列表：'A', 'B'。"""
        return ', '.join(f"'{name}'" for name in names)

    # ── 读：都返回副本，改返回值不影响 Group ─────────────────────

    @property
    def names(self) -> list[str]:
        """全部分组名，保持书写顺序。"""
        return list(self._config)

    def __iter__(self):
        """for name in group：按书写顺序遍历分组名，与遍历字典得到键一样。"""
        # 遍历名字列表的副本：循环里即使调用 add / delete 也不会出现「字典在遍历时被修改」的错误
        return iter(self.names)

    def sample_ids(self, group_name: str) -> list[int]:
        """该分组的样品号列表，保持书写顺序（顺序就是角色，如 slices[1] / slices[0]）。"""
        return list(self._require(group_name)['num'])

    def options(self, group_name: str) -> dict:
        """该分组 'num' 以外的全部字段，如 {'linestyle': '--'}；没有则为 {}。"""
        config = self._require(group_name)
        return {key: copy.deepcopy(value) for key, value in config.items() if key != 'num'}

    def to_config(self) -> dict[str, dict]:
        """当前配置的新字典（num 为规范化后的列表），可以保存、打印或交给别处使用。"""
        return copy.deepcopy(self._config)

    # ── 改：先校验全部、再修改；都返回 self，可链式调用 ────────────

    def add(self, group_config: dict) -> Group:
        """新增分组；分组名已存在 → ValueError（替换请用 set）。"""
        validated = self._validated(group_config)
        existing = [name for name in validated if name in self._config]
        if existing:
            raise ValueError(
                f"数据分组配置错误：分组 {self._quoted(existing)} 已存在；替换已有分组请用 set。"
            )
        self._config.update(validated)
        return self

    def set(self, group_config: dict) -> Group:
        """整体替换已有分组，旧字段不保留，位置不变；分组名不存在 → ValueError（新增请用 add）。"""
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
        """删除分组；分组名不存在 → ValueError。"""
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
        对每组 config 条目执行回调计算。

        固定流程：遍历 config → 选择列 → 按样品拆分对齐 → 调用 callback → 拼装结果。
        用户只需提供 callback（计算逻辑）和可选的 naming（命名逻辑）。

        Parameters
        ----------
        callback : Callable[*DataSet] -> np.ndarray
            签名：callback(*slices) -> np.ndarray

            - slices[i] 是该分组中第 i 个样品的 DataSet 切片，顺序对应 config['num'][i]
            - 每个 slice 的列顺序与 select 参数中词条的顺序一致
            - 返回值为 ndarray，shape (n_rows, n_result_cols)
            - 若返回列顺序与 slice 列顺序不同（如透传、reorder），
              必须同时提供 naming，否则 name/unit 会错位

            标准示例（两个样品做差，无透传）::

                def subtract(*slices):
                    return slices[1].data - slices[0].data

            含透传列示例（按列名精确取列，结果列顺序自定义）::

                def subtract_with_freq(*slices):
                    s0, s1 = slices[0], slices[1]
                    zs_idx = [i for i, n in enumerate(s0.names)
                               if n in ("Zs'(ohm)", "Zs''(ohm)")]
                    freq_idx = s0.names.index("Frequency(Hz)")
                    camp = s1.data[:, zs_idx] - s0.data[:, zs_idx]
                    freq = s0.data[:, freq_idx].reshape(-1, 1)
                    return np.hstack((freq, camp))   # 透传列在前

        select : tuple, optional
            列过滤词条，按顺序传给 DataProcessLayer.by()。
            slice 内的列顺序与此一致。
            如 ("Zs'(ohm)", "Zs''(ohm)", "Frequency(Hz)")。
            None 则不过滤，传入全部列。

        naming : Callable, optional
            签名：naming(slices, result_data) -> (names: list[str], units: list[str])

            - slices：与传入 callback 相同的切片列表
            - result_data：callback 返回的 ndarray
            - 返回的 names/units 长度必须等于 result_data.shape[1]
            - 凡是 callback 改变了列顺序（透传、reorder、hstack），
              必须提供 naming，不能依赖 _auto_naming

            标准示例（两个样品做差，结果列顺序与 slice 一致）::

                def my_naming(slices, result_data):
                    s0 = slices[0]
                    names = [f"Delta_{n}" for n in s0.names]
                    units = list(s0.units)
                    return names, units

            含透传列示例（结果列顺序：freq 在前，camp 在后）::

                def my_naming(slices, result_data):
                    s0 = slices[0]
                    freq_idx = s0.names.index("Frequency(Hz)")
                    zs_idx = [i for i, n in enumerate(s0.names)
                               if n in ("Zs'(ohm)", "Zs''(ohm)")]
                    names = [s0.names[freq_idx]] + [f"Delta_{s0.names[i]}" for i in zs_idx]
                    units = [s0.units[freq_idx]] + [s0.units[i] for i in zs_idx]
                    return names, units

            None 则由 _auto_naming 自动生成（仅适用于列顺序未改变的情况）。

        Returns
        -------
        DataSet
            每个分组的计算结果作为一个新样品（样品号从 0 起依次编号），依次拼接而成的数据集。
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
                result_names, result_units = self._auto_naming(slices, n_cols, callback)



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


    def _auto_naming(self, slices, n_cols, callback):
        """自动生成结果列的 names 和 units。"""
        cb_name = getattr(callback, '__name__', 'calc')

        names = []
        for col_idx in range(n_cols):
            slice_names = [
                s.names[col_idx] for s in slices
                if col_idx < len(s.names)
            ]
            names.append(f"{cb_name}_" + "_".join(slice_names))

        # units 取第一个 slice（_channel_units_unify_check 保证同位置 unit 一致）
        units = [slices[0].units[col_idx] for col_idx in range(n_cols)]

        return names, units