"""数据处理模块。"""
from __future__ import annotations

import re
import copy
import numpy as np
from .dataset import DataSet, Column, ColumnList






class DataProcessLayer:
    """
    数据选择与处理层。

    从 DataSet 中按条件筛选数据列，支持链式调用。

    选择方法
    --------
    select(*args)
        按名称、单位、索引或分组筛选数据列。
    by(*args)
        在已选数据上进行二次筛选。
    getdata(...)
        底层数据提取方法。

    选择语法
    --------
    支持以下参数形式：

    - 'all'              : 选择全部列
    - 'group', [0, 1]    : 按组索引选择
    - 'column_name'      : 按列名选择
    - 'unit_name'        : 按单位选择
    - 0, 1, 2            : 按列索引选择
    - [0, 1, 2]          : 按索引列表选择

    使用示例
    --------
    >>> layer = DataProcessLayer(dataset)
    >>> layer.select('all').Selected_data              # 选择全部
    >>> layer.select('group', [0, 1]).Selected_data    # 选择第 0、1 组
    >>> layer.select(0, 1, 2).Selected_data            # 选择第 0、1、2 列
    >>> layer.select('Pa').Selected_data               # 按单位选择
    >>> layer.select('all').by(0, 1).Selected_data     # 链式筛选
    """

    def __init__(
        self,
        dataset: DataSet,
        input_data: object = None,  # type: ignore
        input_dataname: list[str] = None,  # type: ignore
        input_dataunits: list[str] = None,  # type: ignore
        data_Process_Index: list[int] = None,  # type: ignore
    ):
        """
        初始化处理层。

        Parameters
        ----------
        dataset : DataSet
            输入数据集。
        input_data : object, optional
            输入数据矩阵（通常不直接使用）。
        input_dataname : list[str], optional
            数据列名称列表。
        input_dataunits : list[str], optional
            数据列单位列表。
        data_Process_Index : list[int], optional
            数据处理索引列表。
        """
        self.dataset = dataset
        self.data = input_data
        self.names = input_dataname
        self.units = input_dataunits
        self.User_data_Index = data_Process_Index
        self.Selected_data = DataSet()
        self.Processed_data = DataSet()
        self.called_select = False
        self.called_process = False



    def select(
        self,
        *args,
        dataset_for_select: DataSet | None = None,
        extended: bool = True,
        inherit: bool = False
    ) -> DataProcessLayer:
        """
        按条件选择数据列。

        Parameters
        ----------
        *args : str | int | list[int] | tuple
            选择条件，支持多种形式：

            - 'all': 选择全部列
            - 'group', [idx_list]: 按组索引选择
            - str: 按列名或单位名匹配
            - int: 按单个列索引选择
            - list[int] | tuple[int]: 按索引列表选择
            - tuple: 嵌套选择条件

        dataset_for_select : DataSet, optional
            指定选择的源数据集，默认使用 self.dataset。
        extended : bool
            True: 累加到已选数据；False: 替换已选数据。
        inherit: bool
            True: 继承已选数据；False: 不继承。

        Returns
        -------
        DataProcessLayer
            返回 self 以支持链式调用。

        Raises
        ------
        ValueError
            使用 'group' 关键字但未提供整数列表。
        RuntimeError
            选择操作未正确执行。

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
                    Selected_data = copy.deepcopy(dataset_for_select)
                    Selected_data.father_idx = list(range(len(dataset_for_select.names))) #type: ignore
                    Selected_data.initial_idx = list(range(len(dataset_for_select.names))) #type: ignore
                    continue
                
                elif re.match(r'group\w*',var,re.IGNORECASE):
                    if len(select_rc) > i+1 and \
                    isinstance(select_rc[i+1], list) and\
                    all(isinstance(x, int) for x in select_rc[i+1]):
                        group_idx_list = list(select_rc[i+1])
                        varlist_idx = [idx
                                       for g in group_idx_list
                                       for idx, grp in enumerate(dataset_for_select.groups_idx) if grp == g] #type: ignore
                        Selected_data = self.getdata(
                            varlist_idx=varlist_idx,
                            father_dataset = dataset_for_select
                        )
                        skip_next = True
                    else:
                        raise ValueError("使用 'groups' 关键字时，必须提供一个整数列表作为下一个参数。")

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
        varname: str = None,  # type: ignore
        varlist_idx: list[int] = None,  # type: ignore
        varset: object = None,  # type: ignore
        father_dataset: DataSet = None,  # type: ignore
    ) -> DataSet:
        """
        从数据集中提取指定列。

        Parameters
        ----------
        varname : str, optional
            变量名（列名或单位名），与 varset 配合使用。
        varlist_idx : list[int], optional
            要提取的列索引列表。
        varset : object, optional
            变量集合（names 或 units 列表），用于名称匹配。
        father_dataset : DataSet
            源数据集。

        Returns
        -------
        DataSet
            包含提取列的新数据集。

        Raises
        ------
        ValueError
            未提供有效的 varname 或 varlist_idx，或未提供 father_dataset。

        Notes
        -----
        必须提供以下参数组合之一：
        - varname + varset: 按名称查找
        - varlist_idx: 按索引列表提取
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
        Selected_data.groups_idx = [father_dataset.groups_idx[i] for i in varlist_idx]
        Selected_data.update_attributes()

        return Selected_data
    
    
    
    def by(self, *args, **kwargs) -> DataProcessLayer:
        """
        在已选数据上进行二次筛选。

        Parameters
        ----------
        *args : str | int | list[int] | tuple
            选择条件，语法同 select()。
        **kwargs
            传递给 select() 的额外参数。

        Returns
        -------
        DataProcessLayer
            返回 self 以支持链式调用。

        Raises
        ------
        RuntimeError
            未先调用 select()，或连续调用 by()。

        Notes
        -----
        必须在 select() 之后立即调用，用于链式筛选：
        ``layer.select('all').by(0, 1).Selected_data``
        """
        if self.called_select:
            self.called_select = False
            return self.select(*args, dataset_for_select=self.Selected_data, **kwargs)
        else:
            raise RuntimeError("by 方法仅作为子方法使用，不能单独及连续使用。")

class DataTransformer:
    """
    数据变换类。

    对 DataSet 进行数学变换操作（范数、FFT 等）。

    Attributes
    ----------
    dataset : DataSet
        源数据集。
    data : np.ndarray
        数据矩阵。
    status : str
        状态标识，'ready' 或 'transformed'。
    """

    def __init__(self, dataset: DataSet = None):# type: ignore
        """
        初始化变换器。

        Parameters
        ----------
        dataset : DataSet
            输入数据集。
        """
        if dataset is None:
            dataset = DataSet()

        self.dataset = dataset
        self.data = dataset.data
        self.names = dataset.names
        self.units = dataset.units
        self.groups_idx = dataset.groups_idx
        self.num_datagroups = dataset.num_datagroups
        self.local_idx = dataset.local_idx
        self.initial_idx = dataset.initial_idx
        self.father_idx = dataset.father_idx
        self.generation = dataset.generation
        self.column = dataset.column
        self.status = 'ready'



        
        

    def Norm(
        self,
        order: int = 2,
        indicies: (list[int],int) = None,  # type: ignore
        column: list[Column] = None,  # type: ignore
        norm_unit: str = None,  # type: ignore
        New_group: bool = False,  # type: ignore
        norm_groups_idx: int = None,  # type: ignore
        extended: bool = True
        ):
        """
        计算数据列的范数。

        Parameters
        ----------
        order : int
            范数阶数，默认 2（欧几里得范数）。
        indicies : list[int] | int, optional
            参与计算的列索引，None 表示全部列。
        norm_unit : str, optional
            结果单位，None 则自动推断。

        Returns
        Dataset.column
        """
        col_data, names, units, groups_idx = self._resolve_input_data(column, indicies)
        
        norm_value = np.sum(np.abs(col_data)**order, axis=1)**(1/order)


        data_name, data_unit, data_groups_idx = self.__update_dataset_attributes(
            names_extracted = names,
            units_extracted = units,
            groups_idx_extracted = groups_idx,
            units_input = norm_unit,   
            groups_idx_input = norm_groups_idx,
            New_group = New_group) # type: ignore
        
        local_dataset = self._create_local_dataset(
            data = norm_value,
            name = data_name,
            unit = data_unit,
            group_idx = data_groups_idx
        )
      
        if extended:      
            self.dataset.expandata(local_dataset)
        else:
            self.dataset = copy.deepcopy(local_dataset)

        return self.dataset
    



    def _resolve_input_data(self, column, indicies):
        if column is not None:
            col_data = np.array([col.data for col in column]).T
            names = [col.name for col in column]
            units = [col.unit for col in column]
            groups_idx = [col.group_idx for col in column]
            return col_data, names, units, groups_idx

        if indicies is None:
            return self.data, list(self.names), list(self.units), list(self.groups_idx)

        # 允许 int / list[int] / tuple[int] / np.ndarray
        if isinstance(indicies, int):
            col_data = self.data[:, indicies:indicies + 1]
            names = [self.names[indicies]]
            units = [self.units[indicies]]
            groups_idx = [self.groups_idx[indicies]]
        else:
            idx = list(indicies)
            col_data = self.data[:, idx]
            names = [self.names[i] for i in idx]
            units = [self.units[i] for i in idx]
            groups_idx = [self.groups_idx[i] for i in idx]

        return col_data, names, units, groups_idx


    
    def __update_dataset_attributes(self,
        names_extracted,
        units_extracted,
        groups_idx_extracted,
        names_input = None,  # type: ignore
        units_input = None,  # type: ignore
        groups_idx_input = None,  # type: ignore
        New_group = False,  # type: ignore
        ):

        if names_input is not None:
            data_name = names_input
        
        elif len(names_extracted) == 1:
            data_name = f"{names_extracted[0]}"
        elif len(set(names_extracted)) == 1:
            data_name = f"Norm_of_{names_extracted[0]}"
        else:
            data_name = "Norm_of_" + "_".join(names_extracted)

        
        
        if units_input is not None:
            data_unit = units_input
        elif len(set(units_extracted)) == 1:
            data_unit = units_extracted[0]
        else:
            data_unit = "unitless"


        if groups_idx_input is not None:
            data_groups_idx = groups_idx_input
        elif New_group:
            data_groups_idx = self.num_datagroups + 1
            self.num_datagroups += 1
        elif len(set(groups_idx_extracted)) == 1:
            data_groups_idx = groups_idx_extracted[0]
        else:
            raise ValueError("无法确定结果列的组索引，请手动指定 norm_group_idx。")

        return data_name, data_unit, data_groups_idx
    
    
    def _create_local_dataset(self, data, name, unit, group_idx):
        local_dataset = DataSet()
        local_dataset.data = data.reshape(-1, 1)
        local_dataset.names = [name]
        local_dataset.units = [unit]
        local_dataset.groups_idx = [group_idx]
        local_dataset.father_idx = [None] #type: ignore
        local_dataset.initial_idx = [None] #type: ignore
        local_dataset.update_attributes()

        return local_dataset



       






        
