from __future__ import annotations
from typing import Callable

import numpy as np
from .dataset import DataSet
from .processor import DataProcessLayer


class Group():

    def __init__(self, dataset: DataSet, group_config: dict):
        self.dataset = dataset
        self.group_config = group_config


    def resolve_group_indices(self, group_name: str) -> list[int]:
        """获取指定组名的列索引列表"""

        if group_name not in self.group_config:
            raise ValueError(f"数据分组配置错误：缺少 '{group_name}' 组。")
        return self.group_config[group_name]['num']


    def apply(
        self,
        callback: Callable[..., np.ndarray],
        select: tuple | None = None,
        naming: Callable | None = None,
    ) -> DataSet:
        """
        对每组 config 条目执行回调计算。

        固定流程：遍历 config → 选择列 → 按组拆分对齐 → 调用 callback → 拼装结果。
        用户只需提供 callback（计算逻辑）和可选的 naming（命名逻辑）。

        Parameters
        ----------
        callback : Callable[*DataSet] -> np.ndarray
            签名：callback(*slices) -> np.ndarray

            - slices[i] 是第 i 个组的 DataSet 切片，顺序对应 config['num'][i]
            - 每个 slice 的列顺序与 select 参数中词条的顺序一致
            - 返回值为 ndarray，shape (n_rows, n_result_cols)
            - 若返回列顺序与 slice 列顺序不同（如透传、reorder），
              必须同时提供 naming，否则 name/unit 会错位

            标准示例（两组做差，无透传）::

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

            标准示例（两组做差，结果列顺序与 slice 一致）::

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
            所有 config 条目的计算结果按组累加而成的数据集。
        """
        accumulated = DataSet()
        result_group_idx = 0

        for group_name, config in self.group_config.items():
            if 'num' not in config:
                raise ValueError(
                    f"数据分组配置错误：'{group_name}' 缺少 'num' 键。"
                )
            group_indices = config['num']

            # 选择对应组的列
            dpl = DataProcessLayer(dataset=self.dataset)
            dpl.select("Group_indices", group_indices)
            if select is not None:
                dpl.by(*select)
            selected = dpl.Selected_data

            # 按组号拆分为对齐的切片
            slices = []
            for g_idx in group_indices:
                col_positions = [
                    i for i in selected.local_idx
                    if selected.groups_idx[i] == g_idx
                ]
                if not col_positions:
                    raise ValueError(
                        f"组 '{group_name}' 中 group_idx={g_idx} 无匹配列。"
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
            if result_data.ndim == 1:
                result_data = result_data.reshape(-1, 1)
            n_cols = result_data.shape[1]

            # 生成命名
            result_names, result_units = self._auto_naming(
                    slices, n_cols, callback
                )
            
            if naming is not None:
                result_names, result_units = naming(slices, result_data)
            


            # 组装结果切片
            result_slice = DataSet().form_array(
                data=result_data,
                name=result_names,
                unit=result_units,
                group_idx=result_group_idx,
                repeat_times=n_cols
            )#type: ignore

            accumulated.expandata(result_slice)
            result_group_idx += 1

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

        # units 取第一个 slice（_group_local_indices_unify_check 保证同位置 unit 一致）
        units = [slices[0].units[col_idx] for col_idx in range(n_cols)]

        return names, units