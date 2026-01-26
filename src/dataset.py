"""数据集容器模块。"""
from __future__ import annotations
from collections import Counter
import re
import copy
import numpy as np





class DataSet():
    """数据集类"""
    def __init__(self):
        self.data: np.ndarray = np.empty((0, 0))  # 纯数值矩阵 (n_rows, n_cols)
        self.names: list = []
        self.units: list = []
        self.groups_idx: list = []
        self.group_local_idx: list = []
        self.group_column: list = []
        self.local_idx: list = []
        self.father_idx: list = []
        self.initial_idx: list = []
        self.num_datagroups: int = 0
        self.generation: int = 0
        self.status: str = 'empty'  # empty, selected, processed

    @property #type: ignore
    def column(self) -> list[dict]:
            column:list[dict] = []

            for i in self.local_idx:
                column.append({
                'local_idx': i,
                'name': self.names[i],
                'unit': self.units[i],
                'group_idx': self.groups_idx[i],
                'group_local_idx': self.group_local_idx[i],
                'data': self.data[:, i].copy(),
                'father_idx': self.father_idx[i],
                'initial_idx': self.initial_idx[i]
                })         
            return column

    


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
    
    def insert_column(self, data, name, unit):
        pass
        
    def insert_dataset(self, dataset: DataSet):
        pass
