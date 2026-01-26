from __future__ import annotations
from collections import Counter

import tkinter as tk
from tkinter import filedialog
import pandas as pd
import numpy as np
from typing import Optional
from .dataset import DataSet


# ============================================================================
# 全局配置
# ============================================================================
INPUT_COLUMNS_PER_DATASET = 6      # 每组数据集的列数（1列标识 + 5列数据）
INPUT_DATASET_FRACTION = 1 / INPUT_COLUMNS_PER_DATASET




class Dataloader:
    """
    结构化数据文件加载器。

    从 Excel/CSV/文本文件中读取分组数据，解析为统一的 DataSet 对象。

    输入文件格式
    ------------
    文件按固定列宽分组，每组 COLUMNS_PER_DATASET 列（默认 6 列）：

        | 标识列 | 数据列1 | 数据列2 | 数据列3 | 数据列4 | 数据列5 | 标识列 | ... |
        |--------|---------|---------|---------|---------|---------|--------|-----|
        | File1  | m/s     | Pa      | K       | J       | W       | File2  | ... |  <- 第0行：标题
        | -      | 1.2     | 101     | 300     | 50      | 100     | -      | ... |  <- 第1行起：数据

    输出结构
    --------
    返回 DataSet 对象，包含以下属性：

        属性              类型              说明
        ─────────────────────────────────────────────────────────────────
        names             list[str]         各列对应的组名（重复展开）
        units             list[str]         各列的单位
        data              np.ndarray        数值矩阵 (n_rows, n_cols)
        num_datagroups    int               数据组数量
        groups_idx        list[int]         各列所属的组索引
        group_local_idx   list[int]         各列在组内的局部索引

    使用示例
    --------
    >>> dataset = Dataloader().load_data()
    >>> dataset.data[:, 0:5]      # 第一组的数据
    >>> dataset.names[0:5]        # 第一组的列名
    """

    def __init__(self,
                 DATASET_FRACTION=INPUT_DATASET_FRACTION,
                 COLUMNS_PER_DATASET=INPUT_COLUMNS_PER_DATASET):
        """
        初始化加载器。

        Parameters
        ----------
        DATASET_FRACTION : float, optional
            组数计算系数，默认 1/6。
        COLUMNS_PER_DATASET : int, optional
            每组的列数，默认 6。
        """
        self.file_path: Optional[str] = None
        self.dataset: Optional[pd.DataFrame] = None
        self.DATASET_FRACTION = DATASET_FRACTION
        self.COLUMNS_PER_DATASET = COLUMNS_PER_DATASET

    @staticmethod
    def select_data_file() -> str:
        """
        弹出文件选择对话框。

        Returns
        -------
        str
            选中文件的绝对路径。

        Raises
        ------
        SystemExit
            用户取消选择时退出程序。

        Notes
        -----
        支持格式：Excel (.xlsx, .xls)、CSV (.csv)、文本 (.txt, .dat)
        """
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="请选择数据文件",
            filetypes=[("数据文件", "*.xlsx *.xls *.csv *.txt *.dat"), ("所有文件", "*.*")]
        )

        if not file_path:
            print("未选择文件，程序退出。")
            exit()

        return file_path




    def load_data(self) -> 'DataSet':
        """
        加载并解析数据文件。

        Returns
        -------
        DataSet
            解析后的数据集对象，包含以下属性：

            data : np.ndarray, shape (n_rows, n_cols)
                数值矩阵，每列对应一个数据序列。
            names : list[str]
                各列的组名（同组内各列名称相同）。
            units : list[str]
                各列的单位。
            num_datagroups : int
                数据组的数量。
            groups_idx : list[int]
                各列所属的组索引（0, 0, ..., 1, 1, ...）。
            group_local_idx : list[int]
                各列在组内的局部索引（0, 1, 2, 3, 4, 0, 1, ...）。
            local_idx : list[int]
                各列的全局索引（0, 1, 2, ...）。
            father_idx : list[int]
                各列的父索引（初始与 local_idx 相同）。
            initial_idx : list[int]
                各列的初始索引（用于追溯原始位置）。
            status : str
                数据集状态，加载后为 'loaded'。

        Raises
        ------
        ValueError
            文件路径未指定或列数不符合要求。
        RuntimeError
            文件读取失败或数据维度不匹配。
        """
        # 获取文件路径
        if self.file_path is None:
            self.file_path = Dataloader.select_data_file()
            if self.file_path is None:
                raise ValueError("文件路径未指定。")

        # 根据扩展名读取文件
        if self.file_path.endswith('.csv'):
            self.dataset = pd.read_csv(self.file_path, low_memory=False, header=None)
        elif self.file_path.endswith(('.xlsx', '.xls')):
            self.dataset = pd.read_excel(self.file_path, header=None)
        elif self.file_path.endswith(('.txt', '.dat')):
            self.dataset = pd.read_csv(self.file_path, delim_whitespace=True, low_memory=False, header=None)

        if self.dataset is None:
            raise RuntimeError("数据集加载失败")

        # 验证列数
        total_cols = len(self.dataset.columns)
        if total_cols % self.COLUMNS_PER_DATASET != 0:
            raise ValueError("Column count must be a multiple of COLUMNS_PER_DATASET.")

        self.num_datagroups = int(len(self.dataset.columns) * self.DATASET_FRACTION)

        # 提取组名（每列重复对应的组标识）
        self.names = [self.dataset.iloc[0, i * self.COLUMNS_PER_DATASET]
                      for i in range(self.num_datagroups)
                      for _ in range(self.COLUMNS_PER_DATASET - 1)]

        # 记录每列所属的组索引
        self.groups_idx = [i
                           for i in range(self.num_datagroups)
                           for _ in range(self.COLUMNS_PER_DATASET - 1)]

        # 提取单位
        self.units = [unit
                      for i in range(self.num_datagroups)
                      for unit in self.dataset.iloc[0, i * self.COLUMNS_PER_DATASET + 1:(i + 1) * self.COLUMNS_PER_DATASET].tolist()]

        # 提取数值数据（跳过标识列和标题行）
        data_parts = [
            self.dataset.iloc[1:, i * self.COLUMNS_PER_DATASET + 1:(i + 1) * self.COLUMNS_PER_DATASET]
            .apply(pd.to_numeric, errors='coerce')
            .to_numpy(dtype=np.float64, na_value=np.nan)
            for i in range(self.num_datagroups)
        ]

        # 水平拼接所有数据块
        self.data = np.hstack(data_parts)
        
        # 数据一致性校验
        expected_cols = self.num_datagroups * (self.COLUMNS_PER_DATASET - 1)
        if not (self.data.shape[1] == len(self.names) == len(self.units)
                == len(self.groups_idx) == expected_cols):
            raise RuntimeError("数据解析错误：数据维度与元数据不匹配。")

        # 初始化索引
        self.local_idx = list(range(self.data.shape[1]))
        self.initial_idx = list(self.local_idx)
        self.father_idx = list(self.local_idx)
        self._get_group_local_idx()

        return self._formatter()

    def _get_group_local_idx(self) -> 'Dataloader':
        """计算每列在其所属组内的局部索引。"""
        counter: dict[int, int] = {}
        self.group_local_idx = []
        for g in self.groups_idx:
            counter[g] = counter.get(g, 0)
            self.group_local_idx.append(counter[g])
            counter[g] += 1
        return self

    def _formatter(self) -> 'DataSet':
        """将解析结果封装为 DataSet 对象。"""
        dataset = DataSet()
        dataset.names = self.names
        dataset.units = self.units
        dataset.data = self.data  # type: ignore
        dataset.num_datagroups = self.num_datagroups  # type: ignore
        dataset.groups_idx = self.groups_idx  # type: ignore
        dataset.group_local_idx = self.group_local_idx  # type: ignore
        dataset.local_idx = self.local_idx  # type: ignore
        dataset.father_idx = self.father_idx  # type: ignore
        dataset.initial_idx = self.initial_idx  # type: ignore
        dataset.status = 'loaded'
        dataset._group_local_indices_unify_check()
        return dataset


# data = Dataloader().load_data()
# print(data.names[:])
