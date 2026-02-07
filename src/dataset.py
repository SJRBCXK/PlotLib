"""数据集容器模块。"""
from __future__ import annotations
from typing import Union, overload
from collections import Counter
import re
import copy
import numpy as np


class Column:
    """
    列视图容器 - 作为公共容器连接 DataSet 属性和 column 访问。

    修改 Column 的属性会直接影响 DataSet 中的对应数据，反之亦然。

    使用示例：
        col = dataset.column[0]
        col.name = 'New Name'       # 同时修改 dataset.names[0]
        col.data[:] = new_values    # 同时修改 dataset.data[:, 0]
    """
    _dataset: 'DataSet'
    _idx: int

    def __init__(self, dataset: 'DataSet', idx: int):
        """
        Parameters
        ----------
        dataset : DataSet
            父数据集引用
        idx : int
            该列在 dataset 中的索引
        """
        object.__setattr__(self, '_dataset', dataset)
        object.__setattr__(self, '_idx', idx)

    @property
    def local_idx(self) -> int:
        return self._idx

    @property
    def name(self) -> str:
        return self._dataset.names[self._idx]

    @name.setter
    def name(self, value: str):
        self._dataset.names[self._idx] = value

    @property
    def unit(self) -> str:
        return self._dataset.units[self._idx]

    @unit.setter
    def unit(self, value: str):
        self._dataset.units[self._idx] = value

    @property
    def group_idx(self) -> int:
        return self._dataset.groups_idx[self._idx]

    @group_idx.setter
    def group_idx(self, value: int):
        self._dataset.groups_idx[self._idx] = value

    @property
    def group_local_idx(self) -> int:
        return self._dataset.group_local_idx[self._idx]

    @property
    def data(self) -> np.ndarray:
        """返回该列数据的视图（非副本），修改会影响原数据"""
        return self._dataset.data[:, self._idx]

    @data.setter
    def data(self, value: np.ndarray):
        self._dataset.data[:, self._idx] = value

    @property
    def father_idx(self) -> int:
        return self._dataset.father_idx[self._idx]

    @property
    def initial_idx(self) -> int:
        return self._dataset.initial_idx[self._idx]

    def to_dict(self) -> dict:
        """转换为字典（副本，用于兼容旧代码）"""
        return {
            'local_idx': self.local_idx,
            'name': self.name,
            'unit': self.unit,
            'group_idx': self.group_idx,
            'group_local_idx': self.group_local_idx,
            'data': self.data.copy(),
            'father_idx': self.father_idx,
            'initial_idx': self.initial_idx
        }

    def __repr__(self):
        return f"Column({self.local_idx}, name='{self.name}', unit='{self.unit}', group={self.group_idx})"

    # 支持字典式访问（向后兼容）
    _ALLOWED_KEYS = frozenset(['name', 'unit', 'group_idx', 'data'])

    def __getitem__(self, key):
        if key not in self._ALLOWED_KEYS and key not in ('local_idx', 'group_local_idx', 'father_idx', 'initial_idx'):
            raise KeyError(f"Unknown column key: '{key}'")
        return getattr(self, key)

    def __setitem__(self, key, value):
        if key not in self._ALLOWED_KEYS:
            raise KeyError(f"Cannot set '{key}': only {list(self._ALLOWED_KEYS)} are writable")
        setattr(self, key, value)


class ColumnList:
    """
    列列表容器 - 管理所有 Column 对象。

    支持索引访问和迭代，所有操作都直接影响 DataSet。
    """

    def __init__(self, dataset: 'DataSet'):
        self._dataset = dataset

    @overload
    def __getitem__(self, idx: int) -> Column: ...
    @overload
    def __getitem__(self, idx: slice) -> list[Column]: ...

    def __getitem__(self, idx: Union[int, slice]) -> Union[Column, list[Column]]:
        if isinstance(idx, slice):
            indices = range(*idx.indices(len(self)))
            return [Column(self._dataset, i) for i in indices]
        if idx < 0:
            idx = len(self) + idx
        if idx < 0 or idx >= len(self):
            raise IndexError(f"Column index {idx} out of range")
        return Column(self._dataset, idx)

    def __len__(self) -> int:
        return self._dataset.data.shape[1] if self._dataset.data.size > 0 else 0

    def __iter__(self):
        for i in range(len(self)):
            yield Column(self._dataset, i)

    def __repr__(self):
        return f"ColumnList({len(self)} columns)"



class DataSet():
    """数据集类"""
    def __init__(self):
        self.data: np.ndarray = np.empty((0, 0))  # 纯数值矩阵 (n_rows, n_cols)
        self.names: list = []
        self.units: list = []
        self.groups_idx: list = []
        self.group_local_idx: list = []
        self.local_idx: list = []
        self.father_idx: list = []
        self.initial_idx: list = []
        self.num_datagroups: int = 0
        self.generation: int = 0
        self.status: str = 'empty'  # empty, selected, processed

    @property
    def column(self) -> ColumnList:
        """返回列视图容器，修改会直接影响 DataSet"""
        return ColumnList(self)

    


    def expandata(self, other: DataSet):
        """扩展数据集"""

        if self.data.size == 0:
            self.data = other.data.copy()
        else:
            self.data = np.hstack([self.data, other.data])
        self.names.extend(other.names)
        self.units.extend(other.units)
        self.groups_idx.extend(other.groups_idx)
        self.father_idx.extend(other.father_idx)
        self.initial_idx.extend(other.initial_idx)
        self.update_attributes()
        return self
    
    
    def update_attributes(self):
        """更新内部属性并验证一致性"""

        if  not (self.data.shape[1] \
            == len(self.names) \
            == len(self.units) \
            == len(self.groups_idx) \
            == len(self.father_idx) \
            == len(self.initial_idx) \
                                        ):
            print("数据维度:", self.data.shape)
            print("names 长度:", len(self.names))
            print("units 长度:", len(self.units))
            print("groups_idx 长度:", len(self.groups_idx))
            print("father_idx 长度:", len(self.father_idx))
            print("initial_idx 长度:", len(self.initial_idx)) 
            raise RuntimeError("数据解析错误：数据维度与元数据不匹配。")
        else:
            # numpy 无需重置列索引，直接更新 local_idx
            self.local_idx = list(range(self.data.shape[1]))
            self.num_datagroups = self.get_groupnumber()
            self.group_local_idx = list(range(len(self.groups_idx)))
            self._get_group_local_idx()
            # Ensure same group-local position uses a consistent unit across groups.
            self._group_local_indices_unify_check()
            self.status = 'written'

        for i, loc in enumerate(self.local_idx):
            if self.father_idx[i] == None:
                self.father_idx[i] = loc
            if self.initial_idx[i] == None:
                self.initial_idx[i] = loc
            if self.groups_idx[i] == None:
                if all(g is None for g in self.groups_idx):
                    self.groups_idx[i] = 0
                else:
                    self.groups_idx[i] = max(g for g in self.groups_idx if g is not None) + 1 if self.groups_idx else 0
                
        return self
    
    
    
    def get_groupnumber(self):
        """获取数据组数量"""
        if not self.groups_idx:
            return 0
        return len(set(self.groups_idx))
    


    def _get_group_local_idx(self):
        counter = {}
        self.group_local_idx = []
        for g in self.groups_idx:
            counter[g] = counter.get(g, 0)
            self.group_local_idx.append(counter[g])
            counter[g] += 1
        
        return self
    

    def _group_local_indices_unify_check(self):
        unit_by_local = {}
        for i, local_idx in enumerate(self.group_local_idx):
            unit = self.units[i]
            if local_idx in unit_by_local and unit_by_local[local_idx] != unit:
                raise RuntimeError(
                    "Unit mismatch for same group_local_idx: "
                    f"idx={local_idx}, {unit_by_local[local_idx]} vs {unit}"
                )
            unit_by_local[local_idx] = unit
    
    def _rearrange_columns(self):

        
        indices = np.column_stack([self.local_idx,self.groups_idx,self.group_local_idx])

        order = np.lexsort((indices[:,2], indices[:,1])) 

        self.data = self.data[:, order]
        self.names = [self.names[i] for i in order]
        self.units = [self.units[i] for i in order]
        self.groups_idx = [self.groups_idx[i] for i in order]
        self.group_local_idx = [self.group_local_idx[i] for i in order]
        self.local_idx = list(range(len(order)))
        self.father_idx = [self.father_idx[i] for i in order]
        self.initial_idx = [self.initial_idx[i] for i in order]
        self.num_datagroups = self.num_datagroups
        self.generation = self.generation
        self.status = self.status
        self.update_attributes()

        return self
    
    def columns_to_dataset(self, columns: list[Column], extended: bool = True) -> DataSet:
        """将 Column 列表转换为新的 DataSet。

        Parameters
        ----------
        columns : list[Column]
            要转换的列列表
        extended : bool, optional
            是否扩展当前数据集，默认是 True

        Returns
        -------
        DataSet
            包含所选列的新数据集
        """
        local_dataset = DataSet()
        local_dataset.data = np.column_stack([col.data for col in columns]) if columns else np.empty((self.data.shape[0], 0))
        local_dataset.names = [col.name for col in columns]
        local_dataset.units = [col.unit for col in columns]
        local_dataset.groups_idx = [col.group_idx for col in columns]
        local_dataset.father_idx = [col.father_idx for col in columns]
        local_dataset.initial_idx = [col.initial_idx for col in columns]
        local_dataset.update_attributes()

        # 根据需要扩展或替换当前数据集
        if extended:
            self.expandata(local_dataset)
        else:
            self = local_dataset

        return self
    


    def iter(self, method: str):
        """按指定方式遍历数据集，逐组产出子 DataSet。

        Parameters
        ----------
        method : str
            遍历方式: 'groups' | 'names' | 'units'。

        Yields
        ------
        DataSet
            每次迭代产出一个子数据集。
        """
        attr_map = {
            'groups': self.groups_idx,
            'names': self.names,
            'units': self.units,
            'group_local_idx': self.group_local_idx,
        }
        if method not in attr_map:
            raise ValueError(f"不支持的遍历方式: '{method}'，可选: {list(attr_map.keys())}")

        attr = attr_map[method]
        for key in dict.fromkeys(attr):  # type: ignore
            cols = [self.column[j] for j in self.local_idx if attr[j] == key]  # type: ignore
            yield DataSet().columns_to_dataset(cols, extended=False)  # type: ignore
    




        

    


        

