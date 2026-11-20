"""数据集容器模块。"""
from typing import overload
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
    _dataset: DataSet
    _idx: int

    def __init__(self, dataset: DataSet, idx: int):
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
    def sample_idx(self) -> int:
        return self._dataset.sample_idx[self._idx]

    @sample_idx.setter
    def sample_idx(self, value: int):
        """改样品号后重算样品数、通道号并校验；校验失败则回滚，不留下半改的状态。"""
        old = self._dataset.sample_idx[self._idx]
        self._dataset.sample_idx[self._idx] = value
        try:
            self._dataset.update_attributes()
        except RuntimeError:
            self._dataset.sample_idx[self._idx] = old
            self._dataset.update_attributes()
            raise

    @property
    def channel_idx(self) -> int:
        return self._dataset.channel_idx[self._idx]

    @property
    def data(self) -> np.ndarray:
        """返回该列数据的视图（非副本），修改会影响原数据"""
        return self._dataset.data[:, self._idx]

    @data.setter
    def data(self,value: np.ndarray):
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
            'sample_idx': self.sample_idx,
            'channel_idx': self.channel_idx,
            'data': self.data.copy(),
            'father_idx': self.father_idx,
            'initial_idx': self.initial_idx
        }

    def __repr__(self):
        return f"Column({self.local_idx}, name='{self.name}', unit='{self.unit}', sample={self.sample_idx})"

    # 支持字典式访问（向后兼容）
    _ALLOWED_KEYS = frozenset(['name', 'unit', 'sample_idx', 'data'])

    def __getitem__(self, key):
        if key not in self._ALLOWED_KEYS and key not in ('local_idx', 'channel_idx', 'father_idx', 'initial_idx'):
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

    def __init__(self, dataset: DataSet):
        self._dataset = dataset

    @overload
    def __getitem__(self, idx: int) -> Column: ...
    @overload
    def __getitem__(self, idx: slice) -> list[Column]: ...

    def __getitem__(self, idx: int | slice) -> Column | list[Column]:
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
        self.sample_idx: list = []
        self.channel_idx: list = []
        self.local_idx: list = []
        self.father_idx: list = []
        self.initial_idx: list = []
        self.num_samples: int = 0
        self.generation: int = 0
        self.status: str = 'empty'  # empty, selected, processed

    @property
    def column(self) -> ColumnList:
        """返回列视图容器，修改会直接影响 DataSet"""
        return ColumnList(self)

    


    def expandata(self, other: DataSet):
        """
        横向拼接另一个数据集：行数不同时短的一方在下面补 NaN。
        拼接后校验失败（如同一通道单位不同）→ 恢复原状再抛出，不留下半改的对象。
        """
        # 「空」看有没有列，不看 size：零行的样品（如找不到峰的峰表，形状 (0, 2)）size 也是 0，
        # 但它有列，要照常拼接（第三方审查 B）
        if self.data.shape[1] == 0:
            new_data = other.data.copy()
        else:
            a, b = self.data, other.data
            max_rows = max(a.shape[0], b.shape[0])
            if a.shape[0] < max_rows:
                a = np.vstack([a, np.full((max_rows - a.shape[0], a.shape[1]), np.nan)])
            if b.shape[0] < max_rows:
                b = np.vstack([b, np.full((max_rows - b.shape[0], b.shape[1]), np.nan)])
            new_data = np.hstack([a, b])

        # 先记下原状（与 Column.sample_idx 的 setter 同一做法）：update_attributes 校验失败时恢复
        fields = ('data', 'names', 'units', 'sample_idx', 'father_idx', 'initial_idx')
        backup = {field: getattr(self, field) for field in fields}
        self.data = new_data
        for field in fields[1:]:
            setattr(self, field, getattr(self, field) + getattr(other, field))   # 新列表，原列表留作备份
        try:
            self.update_attributes()
        except RuntimeError:
            for field, value in backup.items():
                setattr(self, field, value)
            self.update_attributes()
            raise
        return self
    
    
    def update_attributes(self):
        """更新内部属性并验证一致性"""

        if  not (self.data.shape[1] \
            == len(self.names) \
            == len(self.units) \
            == len(self.sample_idx) \
            == len(self.father_idx) \
            == len(self.initial_idx) \
                                        ):
            print("数据维度:", self.data.shape)
            print("names 长度:", len(self.names))
            print("units 长度:", len(self.units))
            print("sample_idx 长度:", len(self.sample_idx))
            print("father_idx 长度:", len(self.father_idx))
            print("initial_idx 长度:", len(self.initial_idx)) 
            raise RuntimeError("数据解析错误：数据维度与元数据不匹配。")
        # numpy 无需重置列索引，直接更新 local_idx
        self.local_idx = list(range(self.data.shape[1]))

        # 先把 None 补成实际值，再计算派生属性——
        # 顺序反了的话，样品数和通道号会按 None 统计，与补全后的样品号对不上
        for i, loc in enumerate(self.local_idx):
            if self.father_idx[i] is None:
                self.father_idx[i] = loc
            if self.initial_idx[i] is None:
                self.initial_idx[i] = loc
        # 未指定样品号的列（如 DataTransformer 跨样品计算的结果）属于同一次计算，
        # 共用一个新样品号；逐列递增会把它们拆成不同样品，单位不同时触发单位一致性检查
        missing = [i for i, g in enumerate(self.sample_idx) if g is None]
        if missing:
            known = [g for g in self.sample_idx if g is not None]
            new_group = max(known) + 1 if known else 0
            for i in missing:
                self.sample_idx[i] = new_group

        self.num_samples = self.count_samples()
        self._get_channel_idx()
        # Ensure same group-local position uses a consistent unit across groups.
        self._channel_units_unify_check()
        self.status = 'written'

        return self
    
    
    
    def count_samples(self):
        """获取样品数量"""
        if not self.sample_idx:
            return 0
        return len(set(self.sample_idx))
    


    def _get_channel_idx(self):
        counter = {}
        self.channel_idx = []
        for g in self.sample_idx:
            counter[g] = counter.get(g, 0)
            self.channel_idx.append(counter[g])
            counter[g] += 1
        
        return self
    

    def _channel_units_unify_check(self):
        unit_by_local = {}
        for i, local_idx in enumerate(self.channel_idx):
            unit = self.units[i]
            if local_idx in unit_by_local and unit_by_local[local_idx] != unit:
                raise RuntimeError(
                    "Unit mismatch for same channel_idx: "
                    f"idx={local_idx}, {unit_by_local[local_idx]} vs {unit}"
                )
            unit_by_local[local_idx] = unit
    
    def _rearrange_columns(self):

        
        indices = np.column_stack([self.local_idx,self.sample_idx,self.channel_idx])

        order = np.lexsort((indices[:,2], indices[:,1])) 

        self.data = self.data[:, order]
        self.names = [self.names[i] for i in order]
        self.units = [self.units[i] for i in order]
        self.sample_idx = [self.sample_idx[i] for i in order]
        self.channel_idx = [self.channel_idx[i] for i in order]
        self.local_idx = list(range(len(order)))
        self.father_idx = [self.father_idx[i] for i in order]
        self.initial_idx = [self.initial_idx[i] for i in order]
        self.num_samples = self.num_samples
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
        local_dataset.sample_idx = [col.sample_idx for col in columns]
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
        """按指定方式遍历数据集，该属性的每个取值产出一个子 DataSet。

        Parameters
        ----------
        method : str
            遍历方式: 'samples' | 'names' | 'units' | 'channels'。

        Yields
        ------
        DataSet
            每次迭代产出一个子数据集。
        """
        attr_map = {
            'samples': self.sample_idx,
            'names': self.names,
            'units': self.units,
            'channels': self.channel_idx,
        }
        if method not in attr_map:
            raise ValueError(f"不支持的遍历方式: '{method}'，可选: {list(attr_map.keys())}")

        attr = attr_map[method]
        for key in dict.fromkeys(attr):  # type: ignore
            cols = [self.column[j] for j in self.local_idx if attr[j] == key]  # type: ignore
            yield DataSet().columns_to_dataset(cols, extended=False)  # type: ignore
    
    def form_array(self, data, name, unit, sample_idx, repeat_times=1):
        """根据输入数据和元信息创建一个新的 DataSet 切片。"""
        local_dataset = DataSet()
        if data.ndim == 0:
            data = data.reshape(1, 1)
        elif data.ndim == 1:
            data = data.reshape(-1, 1)
        local_dataset.data = data
        local_dataset.names = name
        local_dataset.units = unit
        local_dataset.sample_idx = [sample_idx]*repeat_times
        local_dataset.father_idx = [None]*repeat_times  # type: ignore
        local_dataset.initial_idx = [None]*repeat_times  # type: ignore
        local_dataset.update_attributes()
        return local_dataset    



        

    


        

