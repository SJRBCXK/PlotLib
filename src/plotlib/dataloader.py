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
    选择文件对话框被取消，没有选文件。

    不继承 `OSError`，调用方可以把「用户不想选了」和「文件读不了」（`FileNotFoundError` 等）分开处理。

    Examples
    --------
    >>> try:
    ...     data = Dataloader(columns_per_sample=6).load_data()
    ... except NoFileSelected:
    ...     print('已取消')
    """


class Dataloader:
    """
    数据文件加载器：读取按样品排列的表格，得到 `~plotlib.dataset.DataSet`。

    加载器只记住每个样品占几列，读取过程的中间结果都是局部变量，所以同一个加载器读多少次都互不影响。

    Notes
    -----
    **文件格式。** 每个样品占固定的 *columns_per_sample* 列：第一列是标识列，其余是数据列。
    第 0 行在标识列写样品名、在数据列写单位；第 1 行起是数据，标识列留空（txt 里用 ``-`` 占位）。
    下例每个样品 6 列（1 列标识 + 5 列数据）::

        | 标识列 | 数据列1 | 数据列2 | 数据列3 | 数据列4 | 数据列5 | 标识列 | ... |
        |--------|---------|---------|---------|---------|---------|--------|-----|
        | File1  | m/s     | Pa      | K       | J       | W       | File2  | ... |   ← 第 0 行：样品名、单位
        | -      | 1.2     | 101     | 300     | 50      | 100     | -      | ... |   ← 第 1 行起：数据

    **读取规则。**

    - 扩展名不区分大小写：.csv、.xlsx、.xls、.txt、.dat（txt / dat 以任意连续空白分隔）；
    - 表头（样品名、单位）原样作为文本读入：``'101'`` 不会变成 ``101.0``，``'NA'``、``'N/A'`` 不会变成缺失值；
    - 数据区读不成数字的格子（空格、``'nan'``、文字）变成 NaN。

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
            用户取消了选择。只抛异常，不会退出调用它的程序。

        Notes
        -----
        tkinter 在这里才导入：只按路径读文件时用不到它，没有图形界面的环境（服务器、CI）也能导入本模块。
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
            root.destroy()          # 关掉隐藏的主窗口，不留在后台

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
    按扩展名（不区分大小写）把整张表读成文本表格，不解析。

    - ``dtype=str``：整张表按文本读，样品名、单位保持原样（``'101'`` 不会变成 ``101.0``，``'1.50'`` 不会变成 ``1.5``）；
      标识列除了第 0 行都是空的，若让 pandas 推断类型，整列会被当成浮点数；
    - ``keep_default_na=False``：不按 pandas 的默认规则把 ``'NA'``、``'N/A'``、空格子当缺失值，表头原样保留。
      数据区的空格子、``'nan'`` 仍在 ``_to_dataset`` 里由 ``pd.to_numeric(errors='coerce')`` 转成 NaN。

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
        # sep=r'\s+'：任意连续空白（空格/制表符）作为分隔符。
        # pandas 3 已移除 delim_whitespace=True；python engine 不支持 low_memory，此处不再传
        return pd.read_csv(path, sep=r'\s+', header=None, dtype=str, keep_default_na=False)
    raise ValueError(f"不支持的文件格式：{path}；支持 {'、'.join(SUPPORTED_SUFFIXES)}（不区分大小写）")


def _to_dataset(table: pd.DataFrame, columns_per_sample: int) -> DataSet:
    """
    把读进来的表按「每个样品 *columns_per_sample* 列」拆开，装进 `DataSet`。

    每个样品的第一列是标识列，只取第 0 行的样品名，不进数据；数据列的第 0 行是单位，第 1 行起转成数字。

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

    # 整数除法（第三方审查 A：以前用浮点系数 DATASET_FRACTION，int(98 * (1/49)) 得 1，静默丢样品）
    num_samples = total_cols // columns_per_sample
    channels = columns_per_sample - 1                       # 每个样品的数据列数
    starts = range(0, total_cols, columns_per_sample)       # 各样品标识列的位置

    # 第 0 行：标识列是样品名（同一样品的各列重复），数据列是单位。样品名为空在这里就报错，不等到绘图时莫名出错
    sample_names = [table.iloc[0, start] for start in starts]
    for start, name in zip(starts, sample_names):
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"第 {start + 1} 列的样品名为空（每个样品的第一列第 0 行要写样品名）")

    dataset = DataSet()
    dataset.names = [name for name in sample_names for _ in range(channels)]
    dataset.units = [unit for start in starts for unit in table.iloc[0, start + 1:start + columns_per_sample].tolist()]
    # 第 1 行起：数值（跳过标识列）；读不成数字的格子是 NaN
    dataset.data = np.hstack([  # type: ignore
        table.iloc[1:, start + 1:start + columns_per_sample]
        .apply(pd.to_numeric, errors='coerce')
        .to_numpy(dtype=np.float64, na_value=np.nan)
        for start in starts
    ])
    dataset.num_samples = num_samples  # type: ignore
    dataset.sample_idx = [sample for sample in range(num_samples) for _ in range(channels)]  # type: ignore
    dataset.channel_idx = [channel for _ in range(num_samples) for channel in range(channels)]  # type: ignore
    # 索引：本列位置、父列、初始列（加载时都相同，之后用于追溯原始位置）
    dataset.local_idx = list(range(num_samples * channels))  # type: ignore
    dataset.father_idx = list(dataset.local_idx)  # type: ignore
    dataset.initial_idx = list(dataset.local_idx)  # type: ignore
    dataset.status = 'loaded'
    dataset._channel_units_unify_check()
    return dataset
