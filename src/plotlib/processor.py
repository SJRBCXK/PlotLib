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
from .dataset import DataSet, Column






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
        结果的样品号，只收一个整数：一次计算只产出一个样品。
        要拆成几个样品，就逐样品分开算再拼回（``for sample in dataset``）。
    """

    names: list[str] | None
    units: list[str] | None
    sample_idx: int | None


class DataProcessLayer:
    """
    数据选择层：按条件从数据集中选列，结果放在 `Selected_data`。

    计算不在这一层：逐样品计算用 `DataTransformer`，按分组计算用 `~plotlib.group.Group.apply`。

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
        按条件选列，结果放进 ``Selected_data``。

        Parameters
        ----------
        *args : str, int, list or tuple
            选择条件，写法见类说明。多个条件按顺序依次选出，结果也按这个顺序排列。
        dataset_for_select : DataSet, optional
            从哪个数据集里选；默认 ``self.dataset``。`by` 用它在上一次的结果里选。
        extended : bool, default: True
            True：每个条件的结果依次累加；False：每个条件的结果替换前一个，最后只留下最后一个条件的。
        inherit : bool, default: False
            True：在上一次的 ``Selected_data`` 后面继续累加；False：先清空。

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

        if not inherit:
            self.Selected_data = DataSet()
        

        Selected_data = DataSet()

        if dataset_for_select is None:
            dataset_for_select = self.dataset


        select_rc = args
        skip_next = False

        for i, var in enumerate(select_rc):

            if skip_next :
                skip_next = False
                continue

            if isinstance(var, str):
                if var == 'all':
                    # 与其他条件走同一条路径（getdata），结果才会加入已选数据，
                    # 且在 by('all') 时 initial_idx 仍能追溯到原始数据
                    Selected_data = self.getdata(
                        varlist_idx=list(range(len(dataset_for_select.names))),
                        father_dataset=dataset_for_select
                    )

                elif var == 'samples':
                    if len(select_rc) > i+1 and \
                    isinstance(select_rc[i+1], list) and\
                    all(isinstance(x, int) for x in select_rc[i+1]):
                        sample_idx_list = list(select_rc[i+1])
                        # 写错的样品号要报出来，不能静默只选出存在的（1.0 发布前复审）
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
                    # 不能静默跳过：否则 Selected_data 还是上一个条件的结果，会被重复追加
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
                self.Selected_data.expandata(Selected_data)
            else:
                self.Selected_data = copy.deepcopy(Selected_data)



        self.called_select = True
        self.Selected_data.generation += 1
        
        if self.Selected_data.status != 'written':
            raise RuntimeError("数据选择未执行。")
            

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
            要取的列的位置；给了它就不看 *varname*。
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
        """
        Selected_data = DataSet()

        if varset is not None and varlist_idx is None:
            varlist_idx = [i for i, x in enumerate(varset) if x == varname] # type: ignore

        # 如果 varlist_idx 仍然是 None 或为空，抛出异常
        if varlist_idx is None or len(varlist_idx) == 0:
            raise ValueError("必须提供有效的 varname 或 varlist_idx 参数。")
        
        if father_dataset is None:
            raise ValueError("必须提供有效的 father_dataset 数据集以供选择。")


        # 批量提取数据以提高效率
        # 逻辑修正：如果 initial_idx 为空（根数据集）或等于 absolute_idx（未经过滤），则直接使用当前索引
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

        条件里的列位置、列名、单位都相对于上一次的结果，而不是原数据集。

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
        if self.called_select:
            self.called_select = False
            return self.select(*args, dataset_for_select=self.Selected_data, **kwargs)
        else:
            raise RuntimeError("by 方法仅作为子方法使用，不能单独及连续使用。")

class DataTransformer:
    """
    对一个数据集的列做计算，结果带上名字、单位和样品号，成为新的 `DataSet`。

    最常见的用法是逐样品计算：对每个样品各建一个 `DataTransformer`，结果仍按原样品号对应，再拼回一个数据集。
    一组样品一起算（如两个样品做差）请用 `~plotlib.group.Group.apply`。

    Attributes
    ----------
    dataset : DataSet
        参与计算的数据集，不会被修改。
    result_dataset : DataSet
        计算结果。``extended=True`` 时，同一个变换器上多次计算的结果在这里依次累加。

    Notes
    -----
    结果的元数据按以下规则自动生成，可用参数或 ``naming_func`` 覆盖：

    - **名字**：只有一列输入时沿用它的名字；输入的列同名（同一样品）时为 ``Results_0_of_样品名``、
      ``Results_1_of_样品名`` ……；否则为 ``Results_0_of_名字1_名字2`` ……（各列名字用 ``_`` 连起来）。
    - **单位**：输入的列单位相同时沿用；否则为 ``unitless_0``、``unitless_1`` ……
    - **样品号**：输入的列来自同一样品时沿用它的样品号；来自多个样品时分配一个新样品号。

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

        self.dataset = dataset
        self.data = dataset.data
        self.names = dataset.names
        self.units = dataset.units
        self.sample_idx = dataset.sample_idx
        self.num_samples = dataset.num_samples
        self.local_idx = dataset.local_idx
        self.initial_idx = dataset.initial_idx
        self.father_idx = dataset.father_idx
        self.generation = dataset.generation
        self.column = dataset.column
        self.status = 'ready'
        self.result_dataset = DataSet()
        # new_sample 时分配的下一个样品号：从「已有最大样品号 + 1」开始，
        # 不能用样品数推算——样品号可能不连续（如 [0, 3]），按样品数会撞上已有样品
        existing = [g for g in dataset.sample_idx if g is not None]
        self._next_new_sample = max(existing) + 1 if existing else 0


    def apply(self,
        func: Callable[..., np.ndarray] = lambda x: x,
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
            直接给出参与计算的列，给了它就不看 *indicies*。
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
            范数的阶数；2 是欧几里得范数。
        indicies : int or list of int, optional
            参与计算的列的位置；None 表示全部列。
        column : list of Column, optional
            直接给出参与计算的列，给了它就不看 *indicies*。
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
            一列范数（累加时含之前的结果）。

        Examples
        --------
        >>> zs = DataProcessLayer(data).select("Zs'(ohm)", "Zs''(ohm)").Selected_data
        >>> for sample in zs:
        ...     print(DataTransformer(sample).Norm(norm_unit='|Z|(ohm)').data[:3])
        """
        col_data, _, _, _ = self._resolve_input_data(column, indicies)
    
        norm_value = np.sum(np.abs(col_data)**order, axis=1)**(1/order)

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
        `apply` 和 `Norm` 共用的收尾：按自动规则和用户给的值，为计算结果生成名字、单位、样品号，
        再用 `DataSet.form_array` 装成数据集。优先级：``naming_func`` > 直接给的参数 > 自动规则。
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
                # bool 也是 int 的子类，但 True / False 当样品号多半是写错了
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

        给了 *column* 用它；否则按 *indicies* 取（整数、列表、元组、数组都行，支持负数）；都没给取全部列。
        数据总是副本，交给用户函数时原地修改也不会改到数据集。
        """
        if column is not None:
            col_data = np.array([col.data for col in column]).T
            names = [col.name for col in column]
            units = [col.unit for col in column]
            sample_idx = [col.sample_idx for col in column]
            return col_data, names, units, sample_idx

        if indicies is None:
            # 交给 func 的必须是副本：func 原地修改（如 data *= 0）不能改到原始数据集
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
            # 与 _auto_units 对 input_unit 的处理一致：单个字符串按列数重复
            # （直接当列表用会被拆成单个字符：'sum' → ['s', 'u', 'm']）
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
        结果的样品号，优先级：直接指定的 *sample_idx_input* > *new_sample* 分配的新样品号
        > 输入来自同一样品时沿用 > None（由 `DataSet.update_attributes` 分配新样品号）。

        新样品号同时避开数据集里和已累计结果里的样品号，同一个变换器多次分配也不会撞号。
        """
        
        if sample_idx_input is not None:
            data_sample_idx = sample_idx_input
        elif new_sample:
            # 新样品号要避开输入数据集和已累计的结果：结果里可能有显式写入的样品号（input_sample_idx / naming_func），
            # 只看输入数据集会撞号，两次结果被并成同一个样品（1.0 发布前复审）
            in_results = [idx for idx in self.result_dataset.sample_idx if idx is not None]
            data_sample_idx = max(self._next_new_sample, max(in_results, default=-1) + 1)
            self._next_new_sample = data_sample_idx + 1
            self.num_samples += 1
        elif len(set(sample_idx_extracted)) == 1:
            data_sample_idx = sample_idx_extracted[0]
        else:
            data_sample_idx = None

        return data_sample_idx
    
    
    
    @staticmethod
    def _get_datadim(data):
        """把计算结果整理成二维：标量变成 1 × 1，一维数组变成一列，二维原样返回。"""
        if data.ndim == 0:
            data = data.reshape(1, 1)
        elif data.ndim == 1:
            data = data.reshape(-1, 1)
        return data
    



    




    



        
