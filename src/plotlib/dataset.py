"""
数据容器：`DataSet` （按「样品 × 通道」排列的数值矩阵加每列的元数据），以及按列访问的视图 `Column`、`ColumnList`。
"""
from collections.abc import Iterator
from typing import overload

import numpy as np


class Column:
    """
    `DataSet` 中一列的视图：读写的都是数据集本身，不是副本。

    一般通过 ``dataset.column[i]`` 得到，不直接创建。修改 `Column` 的属性就是修改数据集里对应的那一列，反之亦然。

    Parameters
    ----------
    dataset : DataSet
        所属的数据集。
    idx : int
        这一列在数据集里的位置。

    See Also
    --------
    Column.to_dict : 取一份与数据集脱钩的副本。

    Examples
    --------
    >>> col = dataset.column[0]
    >>> col.name = 'New Name'         # 同时修改 dataset.names[0]
    >>> col.data[:] = new_values      # 同时修改 dataset.data[:, 0]
    >>> col['unit']                   # 也支持字典式读写：'name'、'unit'、'sample_idx'、'data'
    """
    _dataset: DataSet
    _idx: int

    def __init__(self, dataset: DataSet, idx: int):
        object.__setattr__(self, '_dataset', dataset)
        object.__setattr__(self, '_idx', idx)

    @property
    def local_idx(self) -> int:
        """这一列在数据集里的位置（只读）。"""
        return self._idx

    @property
    def name(self) -> str:
        """列名，一般是样品名（可写）。"""
        return self._dataset.names[self._idx]

    @name.setter
    def name(self, value: str):
        self._dataset.names[self._idx] = value

    @property
    def unit(self) -> str:
        """单位，也是这个通道画图时的轴标题（可写；同一通道在各样品里单位必须相同）。"""
        return self._dataset.units[self._idx]

    @unit.setter
    def unit(self, value: str):
        self._dataset.units[self._idx] = value

    @property
    def sample_idx(self) -> int:
        """
        所属的样品号（可写）。

        改样品号后数据集会重算样品数和通道号并校验；校验失败（如通道单位冲突）时恢复原值再报错，
        不留下改了一半的状态。
        """
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
        """通道号：这一列在所属样品内的序号（只读，由样品号推出）。"""
        return self._dataset.channel_idx[self._idx]

    @property
    def data(self) -> np.ndarray:
        """这一列的数据，是数据矩阵的视图而不是副本：原地修改（如 ``col.data[:] = ...``）会改到数据集。"""
        return self._dataset.data[:, self._idx]

    @data.setter
    def data(self,value: np.ndarray):
        self._dataset.data[:, self._idx] = value

    @property
    def father_idx(self) -> int:
        """这一列在上一级数据集（选出它的那个数据集）里的位置（只读）。"""
        return self._dataset.father_idx[self._idx]

    @property
    def initial_idx(self) -> int:
        """这一列在最初读入的数据集里的位置（只读），经过多次选择也能追溯回原始列。"""
        return self._dataset.initial_idx[self._idx]

    def to_dict(self) -> dict:
        """
        把这一列转成字典 ``{'local_idx', 'name', 'unit', 'sample_idx', 'channel_idx', 'data', 'father_idx',
        'initial_idx'}``。返回的是副本（数据也复制了），修改它不影响数据集。
        """
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
        """
        字典式读取：``col['name']``，等同于 ``col.name``。

        Raises
        ------
        KeyError
            不是列的字段名。
        """
        if key not in self._ALLOWED_KEYS and key not in ('local_idx', 'channel_idx', 'father_idx', 'initial_idx'):
            raise KeyError(f"列没有字段 '{key}'")
        return getattr(self, key)

    def __setitem__(self, key, value):
        """
        字典式修改：``col['unit'] = 'V'``。只能改 ``'name'``、``'unit'``、``'sample_idx'``、``'data'``。

        Raises
        ------
        KeyError
            字段不存在或只读（索引类字段由数据集维护）。
        """
        if key not in self._ALLOWED_KEYS:
            raise KeyError(f"不能修改列的 '{key}'：只能改 {sorted(self._ALLOWED_KEYS)}")
        setattr(self, key, value)


class ColumnList:
    """
    数据集所有列的视图，即 ``dataset.column``。

    支持 ``len``、按位置取（``column[0]``、``column[-1]``、``column[2:5]``）和逐列遍历；
    取出的 `Column` 都是视图，修改会直接改到数据集。

    Examples
    --------
    >>> for col in dataset.column:
    ...     print(col.name, col.unit)
    """

    def __init__(self, dataset: DataSet):
        self._dataset = dataset

    @overload
    def __getitem__(self, idx: int) -> Column: ...
    @overload
    def __getitem__(self, idx: slice) -> list[Column]: ...

    def __getitem__(self, idx: int | slice) -> Column | list[Column]:
        """
        按位置取列：整数返回一个 `Column` （支持负数），切片返回 `Column` 列表。

        Raises
        ------
        IndexError
            列号超出范围。
        """
        if isinstance(idx, slice):
            indices = range(*idx.indices(len(self)))
            return [Column(self._dataset, i) for i in indices]
        if idx < 0:
            idx = len(self) + idx
        if idx < 0 or idx >= len(self):
            raise IndexError(f"列号 {idx} 超出范围（共 {len(self)} 列）")
        return Column(self._dataset, idx)

    def __len__(self) -> int:
        """列数。零行的数据集（有列、没有行）也照实返回列数。"""
        # 列数看列，不看元素个数：零行的数据集（如找不到峰的峰表，形状 (0, 2)）size 是 0，但有 2 列（与 expandata 同一判断）
        return self._dataset.data.shape[1]

    def __iter__(self):
        """按位置逐列遍历，每次产出一个 `Column` 视图。"""
        for i in range(len(self)):
            yield Column(self._dataset, i)

    def __repr__(self):
        return f"ColumnList({len(self)} columns)"



class DataSet():
    """
    按「样品 × 通道」组织的数据集：一个数值矩阵，加上每一列的元数据。

    每一列是某个样品的某个通道（如样品 0 的频率、样品 0 的阻抗实部 ……）。
    一般由 `~plotlib.dataloader.Dataloader` 读文件得到，或由选择、计算的结果拼接而成；
    新建的 `DataSet` 是空的。

    Attributes
    ----------
    data : numpy.ndarray
        数值矩阵，形状为（行数, 列数），每列一个序列。各列长度不同时，短的在下面补 NaN。
    names : list of str
        每列的名字，一般是样品名（同一样品的各列相同）。
    units : list of str
        每列的单位，画图时作为轴标题。
    sample_idx : list of int
        每列所属的样品号。
    channel_idx : list of int
        每列在所属样品内的通道号，由 *sample_idx* 推出。
    local_idx : list of int
        每列在本数据集里的位置 ``0, 1, 2, ...``。
    father_idx, initial_idx : list of int
        每列在上一级数据集、最初数据集里的位置，用于追溯原始列。
    num_samples : int
        样品数。
    status : str
        ``'empty'`` （新建）、``'written'`` （经 `update_attributes` 校验过）或 ``'loaded'`` （由 Dataloader 读出）。

    Notes
    -----
    数据集始终满足两条约定，每次修改后都由 `update_attributes` 校验：

    1. 元数据长度一致：``data`` 的列数等于 ``names``、``units``、``sample_idx`` 等各列表的长度；
    2. 同一通道在各样品里单位相同（通道 0 都是频率、通道 1 都是 Zs' ……），
       所以画图时一个通道对应一个轴标题。

    Examples
    --------
    >>> data = Dataloader(columns_per_sample=4).load_data('eis.csv')
    >>> data.column[1].name, data.column[1].unit
    >>> for sample in data:               # 逐样品遍历，每次一个子数据集
    ...     print(sample.names[0])
    """
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
        self.status: str = 'empty'  # 'empty' 新建；'written' 经 update_attributes 校验过；'loaded' 由 Dataloader 读出

    @property
    def column(self) -> ColumnList:
        """所有列的视图（`ColumnList`），按位置取出的 `Column` 读写的都是本数据集。"""
        return ColumnList(self)

    


    def expandata(self, other: DataSet):
        """
        把另一个数据集的列拼接到本数据集右边（原地修改）。

        Parameters
        ----------
        other : DataSet
            要拼上的数据集，不会被修改。

        Returns
        -------
        DataSet
            ``self``，可以链式调用，如 ``data.expandata(result).sort_columns()``。

        Raises
        ------
        RuntimeError
            拼接后违反约定（如同一通道在两个数据集里单位不同）。此时本数据集恢复原状
            （包括 ``status``），不会留下拼了一半的状态。

        Notes
        -----
        行数不同时，短的一方在下面补 NaN。本数据集是否为空看有没有列而不是有没有元素，
        所以零行的数据集（如找不到峰的峰表）也照常拼接。
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
        status = self.status        # update_attributes 会把状态改成 'written'，回滚时连状态一起恢复（如 'loaded'）
        self.data = new_data
        for field in fields[1:]:
            setattr(self, field, getattr(self, field) + getattr(other, field))   # 新列表，原列表留作备份
        try:
            self.update_attributes()
        except RuntimeError:
            for field, value in backup.items():
                setattr(self, field, value)
            self.update_attributes()
            self.status = status
            raise
        return self
    
    
    def update_attributes(self):
        """
        重算派生的元数据并校验两条约定，修改 ``data`` 或元数据列表后调用。

        依次做：检查元数据长度与列数一致；重排 ``local_idx``；把 ``father_idx`` / ``initial_idx`` 里的 None
        补成当前位置；把 ``sample_idx`` 里的 None 补成同一个新样品号（已有最大样品号 + 1）；
        重算样品数和通道号；检查同一通道的单位一致；最后把 ``status`` 设为 ``'written'``。

        Returns
        -------
        DataSet
            ``self``。

        Raises
        ------
        RuntimeError
            元数据长度与列数不一致（信息里有各项长度）；或同一通道在不同样品里单位不同。

        Notes
        -----
        未指定样品号的列（如跨样品计算的结果）属于同一次计算，所以共用一个新样品号；
        逐列递增会把它们拆成不同样品，单位不同时还会违反约定 2。
        """

        lengths = {field: len(getattr(self, field))
                   for field in ('names', 'units', 'sample_idx', 'father_idx', 'initial_idx')}
        if any(length != self.data.shape[1] for length in lengths.values()):
            # 各项长度写进异常信息（以前先 print 到标准输出，再抛一个不带细节的异常）
            detail = '，'.join(f"{field} {length}" for field, length in lengths.items())
            raise RuntimeError(f"数据解析错误：数据维度与元数据不匹配（数据 {self.data.shape[1]} 列；{detail}）")
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
        """样品数：不同样品号的个数。"""
        if not self.sample_idx:
            return 0
        return len(set(self.sample_idx))
    


    def _get_channel_idx(self):
        """按样品号重算通道号：每个样品的列按出现顺序依次编为 0, 1, 2, ...。"""
        counter = {}
        self.channel_idx = []
        for g in self.sample_idx:
            counter[g] = counter.get(g, 0)
            self.channel_idx.append(counter[g])
            counter[g] += 1
        
        return self
    

    def _channel_units_unify_check(self):
        """
        检查约定 2：同一通道在各样品里单位相同（通道 0 都是频率、通道 1 都是 Zs' ……）。

        Raises
        ------
        RuntimeError
            有通道的单位不一致，信息里指出是哪一列、哪个样品。
        """
        unit_by_channel = {}
        for i, channel in enumerate(self.channel_idx):
            unit = self.units[i]
            if channel in unit_by_channel and unit_by_channel[channel] != unit:
                raise RuntimeError(
                    f"同一通道的单位不一致：通道 {channel} 已经是 '{unit_by_channel[channel]}'，"
                    f"第 {i} 列（样品 {self.sample_idx[i]}）却是 '{unit}'"
                )
            unit_by_channel[channel] = unit
    
    def sort_columns(self) -> DataSet:
        """
        各列按「样品号 → 通道号」原地排序。

        把逐样品算出的结果拼回原数据之后，新列都在最右边；排序后同一样品的列重新挨在一起，
        新列成为这个样品的最后一个通道。

        Returns
        -------
        DataSet
            ``self``，可以接在 `expandata` 后面链式调用。

        Examples
        --------
        >>> impedance = DataSet()
        >>> for sample in selected:
        ...     impedance.expandata(DataTransformer(sample).Norm(norm_unit='|Z|(ohm)'))
        >>> data = data.expandata(impedance).sort_columns()
        """
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
        self.update_attributes()

        return self
    
    def columns_to_dataset(self, columns: list[Column], extended: bool = True) -> DataSet:
        """
        用一组列（`Column` 视图）组成数据集。

        Parameters
        ----------
        columns : list of Column
            要用的列，可以来自别的数据集；数据会被复制。
        extended : bool, default: True
            True：把这些列拼接到本数据集右边并返回 ``self``；False：返回只含这些列的新数据集，本数据集不变。

        Returns
        -------
        DataSet
            ``self`` （*extended* 为 True）或新数据集。新列的 ``initial_idx`` 沿用原列的，仍能追溯到原始位置。
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
        """
        按某个属性分组遍历：这个属性的每个取值产出一个子数据集。

        Parameters
        ----------
        method : {'samples', 'names', 'units', 'channels'}
            按什么分组：样品号、列名、单位、通道号。``'samples'`` 等同于直接 ``for sample in dataset``。

        Yields
        ------
        DataSet
            这个取值对应的所有列组成的新数据集（数据是副本），按取值第一次出现的顺序产出。

        Raises
        ------
        ValueError
            不支持的 *method* （在第一次取值时报出）。

        Examples
        --------
        >>> for part in dataset.iter('units'):      # 每个单位一组，含所有样品的这一列
        ...     print(part.units[0], part.names)
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

    def __iter__(self) -> Iterator[DataSet]:
        """
        逐样品遍历：``for sample in dataset`` 每次产出一个样品的子数据集，等同于 ``iter('samples')``。

        样品按在数据集里出现的顺序产出；子数据集保留原样品号，所以逐样品计算的结果拼回后仍按原样品对应。
        逐列遍历用 ``dataset.column``，按名字、单位、通道遍历用 `iter`。

        Examples
        --------
        逐样品计算：每个样品各用一个 `DataTransformer`，结果拼回一个数据集。

        >>> norms = DataSet()
        >>> for sample in dataset:
        ...     norms.expandata(DataTransformer(sample).Norm(norm_unit='|Z|(ohm)'))
        """
        return self.iter('samples')
    
    def form_array(self, data, name, unit, sample_idx, repeat_times=1):
        """
        用一个数组和它的元数据创建新的数据集（本数据集不变）。

        Parameters
        ----------
        data : numpy.ndarray
            数据。标量变成 1 × 1，一维数组变成一列。
        name, unit : list of str
            每列的名字和单位，长度等于列数。
        sample_idx : int or None
            这些列共同的样品号；None 表示分配一个新样品号（已有最大样品号 + 1）。
        repeat_times : int, default: 1
            列数，*sample_idx* 按它重复。

        Returns
        -------
        DataSet
            新数据集，``father_idx`` / ``initial_idx`` 是各列自己的位置。

        Raises
        ------
        RuntimeError
            *name*、*unit* 的长度与列数不一致。

        Examples
        --------
        >>> part = DataSet().form_array(np.array([[1.0, 2.0]]), ['S0', 'S0'], ['x', 'y'], 0, repeat_times=2)
        """
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



        

    


        

