"""
数据选择与逐样品计算。

- `DataProcessLayer`：按样品号、列名、单位、位置从数据集中选列，可链式二次筛选；
- `DataTransformer`：对选出的列做计算（自定义函数 `DataTransformer.apply`、范数 `DataTransformer.Norm`），
  结果带上自动生成的名字、单位和样品号，成为新的 `~plotlib.dataset.DataSet`。

按分组计算（一组样品得到一个新样品）见 `plotlib.group.Group.apply`。
"""
import copy
from collections.abc import Callable
from typing import TypedDict

import numpy as np
from .dataset import Column, ColumnList, DataSet






class TransformMetadata(TypedDict, total=False):
    """
    `DataTransformer` 的命名回调 ``naming_func()`` 的返回值：要覆盖的结果元数据。

    每个键都可以省略或写 None，表示保留自动生成的值。

    Attributes
    ----------
    names : list of str or None
        结果每列的名字，长度等于结果列数。
    units : list of str or None
        结果每列的单位，长度等于结果列数。
    sample_idx : int or None
        结果的样品号。一次计算生成一个样品。
    """

    names: list[str] | None
    units: list[str] | None
    sample_idx: int | None


class DataProcessLayer:
    """
    按样品号、列名、单位或位置筛选数据列。

    最近一次筛选的结果保存在 ``Selected_data``，并可通过 `by` 继续筛选。

    Attributes
    ----------
    dataset : DataSet
        从中选列的数据集。
    Selected_data : DataSet
        最近一次选择的结果（列是副本，修改不影响原数据集）。

    Notes
    -----
    选择条件的写法（`select` 和 `by` 相同）：

    ======================  ==============================================
    ``'all'``               全部列
    ``'samples', [0, 1]``   这些样品的全部列，按列表顺序
    ``'Zs(ohm)'``           列名等于它的列；没有这样的列名时按单位匹配
    ``0, 1, 2``             这些位置的列
    ``[0, 1, 2]``           同上，写成一个列表
    ``('Freq', 'Zs')``      嵌套的一组条件，整体选出
    ======================  ==============================================

    Examples
    --------
    >>> layer = DataProcessLayer(dataset)
    >>> layer.select('samples', [0, 1]).Selected_data       # 样品 0、1
    >>> layer.select("Zs'(ohm)", "Zs''(ohm)").Selected_data  # 两个单位的列，按条件顺序
    >>> layer.select('samples', [0, 1]).by(1, 2).Selected_data   # 先选样品，再在结果里选第 1、2 列
    """

    def __init__(self, dataset: DataSet):
        """
        创建选择层。

        Parameters
        ----------
        dataset : DataSet
            从中选列的数据集，不会被修改。
        """
        self.dataset = dataset
        self.Selected_data = DataSet()
        self.called_select = False



    def select(
        self,
        *args,
        dataset_for_select: DataSet | None = None,
        extended: bool = True,
        inherit: bool = False
    ) -> DataProcessLayer:
        """
        按条件选列，并将结果保存到 ``Selected_data``。

        所有条件均成功后才更新筛选结果。筛选失败后可继续使用上一次成功的结果。

        Parameters
        ----------
        *args : str, int, list or tuple
            选择条件，写法见类说明。多个条件按顺序依次选出，结果也按这个顺序排列。
        dataset_for_select : DataSet, optional
            待筛选的数据集。默认使用 ``self.dataset``；`by` 使用上一次的筛选结果。
        extended : bool, default: True
            为真时依次合并各条件的结果，为假时仅保留最后一个条件的结果。
        inherit : bool, default: False
            为真时以上一次的 ``Selected_data`` 为初始结果，为假时从空数据集开始。

        Returns
        -------
        DataProcessLayer
            ``self``，可以接着调用 `by` 或读 ``Selected_data``。

        Raises
        ------
        ValueError
            ``'samples'`` 后面不是整数列表，或其中有数据集里没有的样品号；找不到名字或单位。
        TypeError
            不支持的条件类型。
        RuntimeError
            没有给任何条件，什么都没选出来；或选出的列违反数据集约定（如同一通道单位不同）。

        Examples
        --------
        >>> DataProcessLayer(data).select("Conductivity'(S/cm)", "Conductivity''(S/cm)").Selected_data
        """

        # 在临时数据集中累积结果，全部条件成功后再替换当前结果。
        result = copy.deepcopy(self.Selected_data) if inherit else DataSet()
        Selected_data = DataSet()

        if dataset_for_select is None:
            dataset_for_select = self.dataset
        dataset_for_select.ensure_updated()

        select_rc = args
        skip_next = False

        for i, var in enumerate(select_rc):

            if skip_next :
                skip_next = False
                continue

            if isinstance(var, str):
                if var == 'all':
                    # 复用列选择流程，保留 initial_idx 对原始列的引用。
                    Selected_data = self.getdata(
                        varlist_idx=list(range(len(dataset_for_select.names))),
                        father_dataset=dataset_for_select
                    )

                elif var == 'samples':
                    if len(select_rc) > i+1 and \
                    isinstance(select_rc[i+1], list) and\
                    all(isinstance(x, int) for x in select_rc[i+1]):
                        sample_idx_list = list(select_rc[i+1])
                        # 在筛选前校验所有请求的样品号。
                        missing = set(sample_idx_list).difference(dataset_for_select.sample_idx)
                        if missing:
                            raise ValueError(f"找不到样品号：{sorted(missing)}；已有样品号：{sorted(set(dataset_for_select.sample_idx))}")
                        varlist_idx = [idx
                            for g in sample_idx_list
                            for idx, grp in enumerate(dataset_for_select.sample_idx) if grp == g] #type: ignore
                        Selected_data = self.getdata(
                            varlist_idx=varlist_idx,
                            father_dataset = dataset_for_select
                        )
                        skip_next = True
                    else:
                        raise ValueError("使用 'samples' 关键字时，必须提供一个整数列表作为下一个参数。")

                elif var in dataset_for_select.names:#type: ignore
                    Selected_data = self.getdata(
                    varname=var, 
                    varset=dataset_for_select.names,#type: ignore
                    father_dataset = dataset_for_select
                    ) #type: ignore

                
                elif var in dataset_for_select.units:#type: ignore
                    Selected_data = self.getdata(
                    varname=var,
                    varset=dataset_for_select.units,#type: ignore
                    father_dataset = dataset_for_select
                    ) #type: ignore

                else:
                    # 无效条件必须中止当前选择，以免重复追加前一条件的结果。
                    raise ValueError(f"找不到名称或单位：'{var}'")

            elif isinstance(var, int):
                Selected_data = self.getdata(varlist_idx=[var],
                father_dataset = dataset_for_select,
                ) #type: ignore
            

            elif isinstance(var, (tuple, list)) and all(isinstance(x, int) for x in var):
                Selected_data = self.getdata(varlist_idx=list(var),
                father_dataset = dataset_for_select,
                ) #type: ignore

            elif isinstance(var, (tuple, list)):
                Local_Docker = DataProcessLayer(dataset_for_select)
                Selected_data = Local_Docker.select(*var, dataset_for_select=dataset_for_select).Selected_data

            else:
                raise TypeError(f"不支持的选择条件类型：{type(var).__name__}（{var!r}）")




            if extended:
                result.expandata(Selected_data)
            else:
                result = copy.deepcopy(Selected_data)

        if result.status != 'written':
            raise RuntimeError("数据选择未执行。")

        self.Selected_data = result
        self.called_select = True
        return self
        
    

        
    
    def getdata(
        self,
        varname: str | None = None,
        varlist_idx: list[int] | None = None,
        varset: object | None = None,
        father_dataset: DataSet | None = None,
    ) -> DataSet:
        """
        从源数据集中取出指定的列，组成新数据集。`select` 的每个条件最终都走这里。

        Parameters
        ----------
        varname : str, optional
            要找的列名或单位，与 *varset* 一起用。
        varlist_idx : list of int, optional
            要提取的列位置，优先于 *varname*。
        varset : list of str, optional
            在哪个列表里找 *varname*：源数据集的 ``names`` 或 ``units``。
        father_dataset : DataSet
            源数据集（必填）。

        Returns
        -------
        DataSet
            新数据集，数据是副本。``father_idx`` 是各列在源数据集里的位置，
            ``initial_idx`` 沿用源数据集的，仍能追溯到最初的列。

        Raises
        ------
        ValueError
            按名字没找到任何列，或两种写法都没给；或没给 *father_dataset*。
        IndexError
            *varlist_idx* 里有超出范围的位置（支持负数，-1 是最后一列）。
        """
        Selected_data = DataSet()

        if varset is not None and varlist_idx is None:
            varlist_idx = [i for i, x in enumerate(varset) if x == varname] # type: ignore

        if varlist_idx is None or len(varlist_idx) == 0:
            raise ValueError("必须提供有效的 varname 或 varlist_idx 参数。")
        
        if father_dataset is None:
            raise ValueError("必须提供有效的 father_dataset 数据集以供选择。")
        father_dataset.ensure_updated()
        # 将负索引转换为非负列位置，再记录来源位置。
        n_cols = father_dataset.data.shape[1]
        if bad := [i for i in varlist_idx if not -n_cols <= i < n_cols]:
            raise IndexError(f"列位置超出范围：{bad}（共 {n_cols} 列）")
        varlist_idx = [i % n_cols for i in varlist_idx]

        # 根数据集或未经筛选的数据集可直接使用当前列位置。
        f_initial = father_dataset.initial_idx #type: ignore
        if not f_initial or f_initial == father_dataset.local_idx:
            Selected_data.initial_idx = list(varlist_idx) #type: ignore
        else:
            Selected_data.initial_idx = [f_initial[i] for i in varlist_idx] #type: ignore


        Selected_data.father_idx = list(varlist_idx) #type: ignore
        Selected_data.data = father_dataset.data[:, varlist_idx].copy()
        Selected_data.names = [father_dataset.names[i] for i in varlist_idx]
        Selected_data.units = [father_dataset.units[i] for i in varlist_idx]
        Selected_data.sample_idx = [father_dataset.sample_idx[i] for i in varlist_idx]
        Selected_data.update_attributes()

        return Selected_data
    
    
    
    def by(self, *args, **kwargs) -> DataProcessLayer:
        """
        在上一次选择的结果里再筛选一次，结果替换 ``Selected_data``。

        列位置、列名和单位均在上一次的筛选结果中解析。

        Parameters
        ----------
        *args
            选择条件，写法同 `select`。
        **kwargs
            转交给 `select` 的其他参数（如 *extended*）。

        Returns
        -------
        DataProcessLayer
            ``self``，可以接着再调用 `by`。

        Raises
        ------
        RuntimeError
            前面没有调用过 `select`。

        Examples
        --------
        >>> layer.select('samples', [0, 1]).by("Zs'(ohm)", "Zs''(ohm)").Selected_data
        """
        if not self.called_select:
            raise RuntimeError("by 方法仅作为子方法使用，不能单独及连续使用。")
        self.called_select = False
        try:
            return self.select(*args, dataset_for_select=self.Selected_data, **kwargs)
        except Exception:
            self.called_select = True       # 保留对上一次成功结果继续筛选的能力。
            raise

def _row_norm(data: np.ndarray, order: int) -> np.ndarray:
    """
    通过缩放逐行计算 ``(Σ|x|^order)^(1/order)``，减少中间运算的上溢和下溢。

    取模前将实数和整数提升到至少 ``float64``，将复数提升到至少 ``complex128``。
    对有限的非零缩放因子 *m*，按 ``m · (Σ(|x|/m)^order)^(1/order)`` 计算。
    正阶取行内最大模，负阶取最小模，使求和中的各项不超过 1。
    含 NaN 的行返回 NaN。正阶时，含无穷大的行返回无穷大，全零行返回 0。
    负阶时，全为无穷大的行返回无穷大，含 0 的行返回 0。
    """
    values = np.asarray(data)
    wide = np.complex128 if np.iscomplexobj(values) else np.float64
    x = np.abs(values.astype(np.promote_types(values.dtype, wide)))
    if x.shape[1] == 0:
        return np.zeros(x.shape[0])
    scale = np.max(x, axis=1) if order > 0 else np.min(x, axis=1)
    # 负阶时，溢出为无穷大的比值对求和的贡献为 0。
    with np.errstate(invalid='ignore', divide='ignore', over='ignore'):
        ratio = np.where(scale[:, None] > 0, x / scale[:, None], 0.0)
        norm = scale * np.sum(ratio ** order, axis=1) ** (1 / order)
    return np.where(np.isinf(scale), np.inf, norm)


class DataTransformer:
    """
    变换所选数据列并为结果生成元数据。

    逐样品计算时，可以对每个子数据集创建一个变换器，再按原样品号合并结果。
    需要在一次回调中分别访问多个样品时，可使用 `~plotlib.group.Group.apply`。

    Attributes
    ----------
    dataset : DataSet
        参与计算的数据集。每次计算均读取其当前的列顺序和元数据。
    result_dataset : DataSet
        计算结果。``extended=True`` 时，同一个变换器上多次计算的结果在这里依次累加。

    Notes
    -----
    结果的元数据按以下规则自动生成，可用参数或 ``naming_func`` 覆盖：

    - **名字**：只有一列输入时沿用它的名字；输入的列同名（同一样品）时为 ``Results_0_of_样品名``、
      ``Results_1_of_样品名`` ……；否则为 ``Results_0_of_名字1_名字2`` ……（各列名字用 ``_`` 连起来）。
    - **单位**：输入的列单位相同时沿用；否则为 ``unitless_0``、``unitless_1`` ……
    - 同一样品的输入列默认沿用原样品号。跨样品计算或设置 ``new_sample=True`` 时，
      自动分配的新样品号避开当前源数据、输入列及已有结果。

    Examples
    --------
    逐样品求阻抗的模：

    >>> impedance = DataSet()
    >>> for sample in selected:
    ...     impedance.expandata(DataTransformer(sample).Norm(norm_unit='|Z|(ohm)'))
    """

    def __init__(self, dataset: DataSet | None = None):
        """
        创建变换器。

        Parameters
        ----------
        dataset : DataSet, optional
            参与计算的数据集；不给时是空数据集。
        """
        if dataset is None:
            dataset = DataSet()
        dataset.ensure_updated()

        self.dataset = dataset
        self.num_samples = dataset.num_samples
        self.status = 'ready'
        self.result_dataset = DataSet()
        # 样品号可能不连续，因此从最大样品号之后开始分配。
        existing = [g for g in dataset.sample_idx if g is not None]
        self._next_new_sample = max(existing) + 1 if existing else 0

    @property
    def data(self) -> np.ndarray:
        """校验并返回源数据集当前的数据数组。"""
        return self.dataset.ensure_updated().data

    @property
    def names(self) -> list:
        """校验并返回源数据集当前的列名。"""
        return self.dataset.ensure_updated().names

    @property
    def units(self) -> list:
        """校验并返回源数据集当前的列单位。"""
        return self.dataset.ensure_updated().units

    @property
    def sample_idx(self) -> list:
        """校验并返回源数据集当前的各列样品号。"""
        return self.dataset.ensure_updated().sample_idx

    @property
    def column(self) -> ColumnList:
        """返回源数据集的列视图。"""
        return self.dataset.column


    def apply(self,
        func: Callable[..., np.ndarray | float] = lambda x: x,
        naming_func: Callable[[], TransformMetadata] | None = None,
        input_name: str | list[str] | None = None,
        indicies: list[int] | int | None = None,
        column: list[Column] | None = None,
        input_unit: str | None = None,
        new_sample: bool = False,
        input_sample_idx: int | None = None,
        extended: bool = True
    ) -> DataSet:
        """
        用自定义函数计算，返回结果数据集。

        Parameters
        ----------
        func : callable, default: 原样返回
            ``func(data) -> ndarray``。*data* 是选中各列组成的二维数组（行 × 列，副本，原地修改不影响数据集）；
            返回标量、一维或二维数组，标量当作 1 × 1，一维当作一列。
        naming_func : callable, optional
            ``naming_func() -> TransformMetadata``，返回要覆盖的名字、单位、样品号；写 None 的项保留自动值。
        input_name : str or list of str, optional
            结果的名字：字符串表示每列同名，列表逐列指定。
        indicies : int or list of int, optional
            参与计算的列的位置（支持负数）；None 表示全部列。
        column : list of Column, optional
            参与计算的列，优先于 *indicies*。
        input_unit : str, optional
            结果的单位，每列相同。
        new_sample : bool, default: False
            True：结果作为一个新样品，样品号避开数据集和已累计结果里的所有样品号。
        input_sample_idx : int, optional
            直接指定结果的样品号，优先于 *new_sample*。
        extended : bool, default: True
            True：结果累加到 ``result_dataset`` 并返回它；False：返回只含这次结果的新数据集。

        Returns
        -------
        DataSet
            计算结果（元数据的自动规则见类说明）。

        Raises
        ------
        TypeError
            *naming_func* 返回的 ``sample_idx`` 不是一个整数。
        RuntimeError
            结果的名字、单位个数与列数不一致；或累加后违反数据集约定（如同一通道单位不同）。

        Examples
        --------
        求每个样品的断裂伸长率（取应变列的最大值）：

        >>> def elongation(data):
        ...     return np.nanmax(data[:, 0])
        >>> DataTransformer(sample).apply(elongation, input_name='EB', input_unit='%')
        """
        col_data, _, _, _ = self._resolve_input_data(column, indicies)

        transformed_data = self._get_datadim(func(col_data))
        colnum_of_result = transformed_data.shape[1]

 

        local_dataset = self._cal_pipe(
            naming_func = naming_func,
            col_num = colnum_of_result,
            column = column,
            indicies = indicies,
            input_data = transformed_data,
            input_name = input_name,
            input_unit = input_unit,
            input_sample_idx = input_sample_idx,
            new_sample = new_sample
        )   

        if extended:
            self.result_dataset.expandata(local_dataset)
        else:
            self.result_dataset = copy.deepcopy(local_dataset)
        
        
        return self.result_dataset


        
        

    def Norm(
        self,
        order: int = 2,
        indicies: list[int] | int | None = None,
        column: list[Column] | None = None,
        norm_unit: str | None = None,
        new_sample: bool = False,
        norm_sample_idx: int | None = None,
        extended: bool = True
        ):
        """
        逐行计算选中各列的范数，结果是一列。

        第 i 行的结果为 ``(Σ|x_ij|^order)^(1/order)``，如阻抗的模 ``|Z| = sqrt(Zs'^2 + Zs''^2)``。

        Parameters
        ----------
        order : int, default: 2
            非零整数阶数。2 对应欧几里得范数。
        indicies : int or list of int, optional
            参与计算的列的位置；None 表示全部列。
        column : list of Column, optional
            参与计算的列，优先于 *indicies*。
        norm_unit : str, optional
            结果的单位；不给时按自动规则（见类说明）。
        new_sample : bool, default: False
            True：结果作为一个新样品。
        norm_sample_idx : int, optional
            直接指定结果的样品号，优先于 *new_sample*。
        extended : bool, default: True
            True：结果累加到 ``result_dataset`` 并返回它；False：返回只含这次结果的新数据集。

        Returns
        -------
        DataSet
            每行的范数构成一列。启用累加时，结果包含同一变换器的历史计算列。

        Examples
        --------
        >>> zs = DataProcessLayer(data).select("Zs'(ohm)", "Zs''(ohm)").Selected_data
        >>> for sample in zs:
        ...     print(DataTransformer(sample).Norm(norm_unit='|Z|(ohm)').data[:3])
        """
        col_data, _, _, _ = self._resolve_input_data(column, indicies)
        norm_value = _row_norm(col_data, order)

        local_dataset = self._cal_pipe(
            column = column,
            indicies = indicies,
            input_data = norm_value,
            input_unit = norm_unit,
            input_sample_idx = norm_sample_idx,
            new_sample = new_sample
        )

        if extended:      
            self.result_dataset.expandata(local_dataset)
        else:
            self.result_dataset = copy.deepcopy(local_dataset)


        return self.result_dataset


    def _cal_pipe(self,
        naming_func: Callable[[], TransformMetadata] | None = None,
        col_num: int = 1,
        column: list[Column] | None= None, 
        indicies: list[int] | int | None = None, 
        input_data: np.ndarray | None = None, 
        input_name: str | list[str] | None = None, 
        input_unit: str | None = None, 
        input_sample_idx: int | None = None, 
        new_sample: bool = False
        ):
        """
        合并计算结果的元数据并构建数据集。

        元数据优先采用 ``naming_func`` 的返回值，其次采用显式参数，最后使用自动生成的值。
        """
        _, names, units, sample_idx = self._resolve_input_data(column, indicies)

        data_name = self._auto_naming(
            names_extracted=names,
            names_input=input_name,
            col_num=col_num
        )

        data_unit = self._auto_units(
            units_extracted=units,
            units_input=input_unit,
            col_num=col_num
        )

        data_sample_idx = self._auto_sample_idx(
            sample_idx_extracted=sample_idx,
            sample_idx_input=input_sample_idx,
            new_sample=new_sample
        )

        if naming_func is not None:
            meta = naming_func()
            func_names = meta.get('names')
            func_units = meta.get('units')
            func_sample_idx = meta.get('sample_idx')
            
            if func_names is not None:
                data_name = func_names
            if func_units is not None:
                data_unit = func_units
            if func_sample_idx is not None:
                # 布尔值是 int 的子类，此处显式排除。
                if isinstance(func_sample_idx, bool) or not isinstance(func_sample_idx, int):
                    raise TypeError(f"naming_func 返回的 sample_idx 只收一个整数（一次计算只产出一个样品），"
                                    f"实际是 {func_sample_idx!r}")
                data_sample_idx = func_sample_idx
    
           
        
        local_dataset = DataSet().form_array(
            data = input_data,
            name = data_name,
            unit = data_unit,
            sample_idx = data_sample_idx,
            repeat_times = col_num
        )

        return local_dataset

    



    def _resolve_input_data(self, column, indicies):
        """
        取出参与计算的列：返回 ``(数据, 名字列表, 单位列表, 样品号列表)``。

        优先使用 *column*，其次按 *indicies* 选择列。两者均为 None 时选择全部列。
        读取前校验相关数据集，并返回数据副本供计算回调使用。
        """
        if column is not None:
            # 同一源数据集只需校验一次。
            for source in {id(col._dataset): col._dataset for col in column}.values():
                source.ensure_updated()
            col_data = np.array([col.data for col in column]).T
            names = [col.name for col in column]
            units = [col.unit for col in column]
            sample_idx = [col.sample_idx for col in column]
            return col_data, names, units, sample_idx

        if indicies is None:
            # 向计算回调提供副本，隔离原地修改。
            return self.data.copy(), list(self.names), list(self.units), list(self.sample_idx)

        # 允许 int / list[int] / tuple[int] / np.ndarray；int 也按列表处理：
        # 花式索引返回副本（不是视图），且负索引与 Python 一致（-1 = 最后一列）
        idx = [indicies] if isinstance(indicies, int) else list(indicies)
        col_data = self.data[:, idx]
        names = [self.names[i] for i in idx]
        units = [self.units[i] for i in idx]
        sample_idx = [self.sample_idx[i] for i in idx]

        return col_data, names, units, sample_idx


    

    def _auto_naming(self,
        names_extracted,
        names_input = None,
        col_num: int = 1
          ):
        """
        结果的名字：给了 *names_input* 用它（字符串按列数重复）；否则按类说明里的自动规则，
        由输入各列的名字 *names_extracted* 推出。
        """
        
        if isinstance(names_input, str):
            # 将单个名称应用于全部结果列。
            data_name = [names_input] * col_num
        elif names_input is not None:
            data_name = list(names_input)

        elif len(names_extracted) == 1:
            data_name = [f"{names_extracted[0]}"]*col_num
        elif len(set(names_extracted)) == 1:
            data_name = [f"Results_{i}_of_{names_extracted[0]}" for i in range(col_num)]
        else:
            data_name = [f"Results_{i}_of_" + "_".join(names_extracted)for i in range(col_num)]
        
        return data_name
    
    def _auto_units(self,
        units_extracted,
        units_input = None,
        col_num: int = 1
          ):
        """
        结果的单位：给了 *units_input* 每列都用它；输入各列单位相同时沿用；否则为 ``unitless_0``、``unitless_1`` ……
        """
        
        if units_input is not None:
            data_unit = [units_input]*col_num
                   
        elif len(set(units_extracted)) == 1:
            data_unit = [units_extracted[0]]*col_num
        else:
            data_unit = [f"unitless_{i}"for i in range(col_num)]
        
        return data_unit
    
    def _auto_sample_idx(self,
        sample_idx_extracted:list[int],
        sample_idx_input:int| None = None,
        new_sample: bool = False,
            ):
        """
        确定本次计算的结果样品号。

        优先使用显式指定的 *sample_idx_input*。输入仅涉及一个样品且 *new_sample* 为假时，
        沿用输入的样品号。自动分配的新样品号避开当前源数据集、输入列、累计结果及本变换器已分配的样品号。
        """

        if sample_idx_input is not None:
            return sample_idx_input
        if not new_sample and len(set(sample_idx_extracted)) == 1:
            return sample_idx_extracted[0]
        taken = [idx for idx in (*self.sample_idx, *sample_idx_extracted, *self.result_dataset.sample_idx)
                 if idx is not None]
        data_sample_idx = max(self._next_new_sample, max(taken, default=-1) + 1)
        self._next_new_sample = data_sample_idx + 1
        self.num_samples += 1
        return data_sample_idx
    
    
    
    @staticmethod
    def _get_datadim(data):
        """把计算结果整理成二维：标量（含 Python 的 int、float）变成 1 × 1，一维数组变成一列，二维原样返回。"""
        data = np.asarray(data)
        if data.ndim == 0:
            data = data.reshape(1, 1)
        elif data.ndim == 1:
            data = data.reshape(-1, 1)
        return data
    



    




    



        
