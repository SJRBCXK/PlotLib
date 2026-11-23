"""
读取按样品排列的数据文件（.csv、.xlsx、.xls、.txt、.dat），得到 `~plotlib.dataset.DataSet`。

Examples
--------
>>> data = Dataloader(columns_per_sample=6).load_data('piezo.csv')    # 直接读这个文件
>>> data = Dataloader(columns_per_sample=6).load_data()               # 不传路径：弹出选择文件对话框
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import DataSet

# 支持的扩展名（不区分大小写）；选择文件对话框的过滤条件也用它
SUPPORTED_SUFFIXES = ('.csv', '.xlsx', '.xls', '.txt', '.dat')


class NoFileSelected(Exception):
    """
    文件选择对话框关闭且未选择文件。

    Examples
    --------
    >>> try:
    ...     data = Dataloader(columns_per_sample=6).load_data()
    ... except NoFileSelected:
    ...     print('已取消')
    """


class Dataloader:
    """
    从按样品排列的表格加载 `~plotlib.dataset.DataSet`。

    加载器可复用于采用相同列结构的多个文件。

    Notes
    -----
    每个样品占固定的 *columns_per_sample* 列，依次为标识列和数据列。
    首行的标识列记录样品名，数据列记录单位。从第二行起读取数据，标识列可留空。
    在以空白分隔的文本文件中，使用 ``-`` 等占位符保留标识列。
    下例每个样品 6 列（1 列标识 + 5 列数据）::

        | 标识列 | 数据列1 | 数据列2 | 数据列3 | 数据列4 | 数据列5 | 标识列 | ... |
        |--------|---------|---------|---------|---------|---------|--------|-----|
        | File1  | m/s     | Pa      | K       | J       | W       | File2  | ... |   ← 第 0 行：样品名、单位
        | -      | 1.2     | 101     | 300     | 50      | 100     | -      | ... |   ← 第 1 行起：数据

    扩展名不区分大小写。TXT 和 DAT 文件以连续空白分隔。
    样品名和单位按文本原样保留，例如 ``'101'``、``'NA'`` 和 ``'N/A'``。
    数据区中无法解析为数值的单元格转换为 NaN。

    Examples
    --------
    >>> data = Dataloader(columns_per_sample=6).load_data('piezo.csv')
    >>> data.names[0:5]          # 第一个样品各列的名字
    >>> data.data[:, 0:5]        # 第一个样品的数据
    """

    def __init__(self, columns_per_sample: int):
        """
        创建加载器。

        Parameters
        ----------
        columns_per_sample : int
            每个样品在文件里占的列数（含 1 列标识），至少 2。不同实验的文件不一样，所以没有默认值。

        Raises
        ------
        ValueError
            *columns_per_sample* 不是不小于 2 的整数。
        """
        if isinstance(columns_per_sample, bool) or not isinstance(columns_per_sample, int) or columns_per_sample < 2:
            raise ValueError(f"columns_per_sample 要写不小于 2 的整数（1 列标识 + 至少 1 列数据），实际是 {columns_per_sample!r}")
        self.columns_per_sample = columns_per_sample

    @staticmethod
    def select_data_file() -> str:
        """
        弹出选择文件对话框，返回选中文件的路径。

        Returns
        -------
        str
            选中文件的绝对路径。

        Raises
        ------
        NoFileSelected
            对话框关闭且未选择文件。

        Notes
        -----
        仅打开对话框时才导入 tkinter，因此可在无图形界面的环境中按路径加载文件。
        """
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        try:
            file_path = filedialog.askopenfilename(
                title="请选择数据文件",
                filetypes=[("数据文件", " ".join(f"*{suffix}" for suffix in SUPPORTED_SUFFIXES)),
                           ("所有文件", "*.*")],
            )
        finally:
            root.destroy()          # 释放为文件对话框创建的 Tk 根窗口。

        if not file_path:
            raise NoFileSelected("未选择数据文件")
        return file_path

    def load_data(self, path: str | os.PathLike | None = None) -> DataSet:
        """
        读取并解析数据文件。

        Parameters
        ----------
        path : str or PathLike, optional
            数据文件路径；不传时弹出选择文件对话框。

        Returns
        -------
        DataSet
            每个样品的数据列（标识列不进数据）。``names`` 是各列的样品名，``units`` 是各列的单位，
            ``local_idx`` / ``father_idx`` / ``initial_idx`` 都是 0, 1, 2, ...，``status`` 为 ``'loaded'``。

        Raises
        ------
        NoFileSelected
            没传路径，在对话框里又取消了选择。
        FileNotFoundError
            文件不存在。
        ValueError
            扩展名不支持；总列数不是 *columns_per_sample* 的整数倍；有样品名为空（信息里指出是第几列）。
        RuntimeError
            同一通道在不同样品里单位不同。

        Examples
        --------
        >>> loader = Dataloader(columns_per_sample=4)
        >>> eis = loader.load_data('eis.CSV')
        >>> eis.num_samples
        """
        if path is None:
            path = self.select_data_file()
        return _to_dataset(_read_table(Path(path)), self.columns_per_sample)


def _read_table(path: Path) -> pd.DataFrame:
    """
    根据扩展名读取文本表格。

    ``dtype=str`` 和 ``keep_default_na=False`` 用于保留数字形式的名称以及 ``'NA'`` 等文本。
    `_to_dataset` 再对数据区执行数值转换，并将无效数据转换为 NaN。

    Raises
    ------
    ValueError
        扩展名不支持，信息里有文件名和支持的格式。
    """
    suffix = path.suffix.lower()
    if suffix == '.csv':
        return pd.read_csv(path, low_memory=False, header=None, dtype=str, keep_default_na=False)
    if suffix in ('.xlsx', '.xls'):
        return pd.read_excel(path, header=None, dtype=str, keep_default_na=False)
    if suffix in ('.txt', '.dat'):
        return pd.read_csv(path, sep=r'\s+', header=None, dtype=str, keep_default_na=False)
    raise ValueError(f"不支持的文件格式：{path}；支持 {'、'.join(SUPPORTED_SUFFIXES)}（不区分大小写）")


def _to_dataset(table: pd.DataFrame, columns_per_sample: int) -> DataSet:
    """
    按每个样品 *columns_per_sample* 列拆分表格并构建 `DataSet`。

    从标识列首行提取样品名，从各数据列首行提取单位，并转换后续行的数值。

    Raises
    ------
    ValueError
        总列数不是 *columns_per_sample* 的整数倍；或有样品名为空。
    RuntimeError
        同一通道在不同样品里单位不同。
    """
    total_cols = table.shape[1]
    if total_cols % columns_per_sample != 0:
        raise ValueError(f"文件共 {total_cols} 列，不是每个样品列数（columns_per_sample={columns_per_sample}）的整数倍")

    num_samples = total_cols // columns_per_sample
    channels = columns_per_sample - 1                       # 每个样品的数据列数
    starts = range(0, total_cols, columns_per_sample)       # 各样品标识列的位置

    # 每个样品的名称取自标识列首行，并用于该样品的各数据列。
    sample_names = [table.iloc[0, start] for start in starts]
    for start, name in zip(starts, sample_names):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"第 {start + 1} 列的样品名为空（每个样品的第一列第 0 行要写样品名）")

    dataset = DataSet()
    dataset.names = [name for name in sample_names for _ in range(channels)]
    dataset.units = [unit for start in starts for unit in table.iloc[0, start + 1:start + columns_per_sample].tolist()]
    # 数值区从第二行起读取，无法转换的单元格记为 NaN。
    dataset.data = np.hstack([  # type: ignore
        table.iloc[1:, start + 1:start + columns_per_sample]
        .apply(pd.to_numeric, errors='coerce')
        .to_numpy(dtype=np.float64, na_value=np.nan)
        for start in starts
    ])
    dataset.sample_idx = [sample for sample in range(num_samples) for _ in range(channels)]  # type: ignore
    # 加载时三个列索引相同，后续选择可通过索引追溯来源。
    dataset.father_idx = list(range(num_samples * channels))  # type: ignore
    dataset.initial_idx = list(range(num_samples * channels))  # type: ignore
    # 统一生成派生元数据并校验通道单位。
    dataset.update_attributes()
    dataset.status = 'loaded'
    return dataset
