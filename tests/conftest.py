"""
conftest.py —— 所有测试文件共享的「准备工作」（fixture）

pytest 会自动加载这个文件，这里定义的 fixture 不用 import，
任何测试函数只要把 fixture 名写进参数列表，就能拿到它的返回值。

─────────────────────────────────────────────────────────────────
测试数据怎么来（Step 4 的核心）：
  不用真实实验数据——太大、会变、看不出「正确答案」。
  而是在测试里**现场生成**一个极小的 CSV，格式与 tools/ 的输出完全一致：

      第 0 行：| 组名 | 单位1 | 单位2 | ... | 组名 | 单位1 | ... |
      第 1 行起：|      | 数值  | 数值  | ... |      | 数值  | ... |
                 ↑ 标识列（Dataloader 只读第 0 行的组名）

  数值手工设计成「一眼能算出结果」，例如第 1 组 = 第 0 组 × 2，
  这样测 Group.apply 时，期望结果可以直接写出来。
─────────────────────────────────────────────────────────────────
"""
# 必须在任何 pyplot 导入之前切到 Agg：只在内存里画图，不弹窗口、不需要显示器。
# （src/ 本身不指定后端；tools/ 里的 TkAgg/QtAgg 只在运行那些工具时生效）
import matplotlib
matplotlib.use('Agg')

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from src.dataloader import Dataloader


@pytest.fixture(autouse=True)
def close_figures():
    """
    autouse=True：每个测试自动使用，不用写进参数。

    yield 之前是准备、之后是清理：测试跑完关闭所有图窗，
    否则图越积越多（matplotlib 超过 20 个会警告），还可能让后面的测试数错图的数量。
    """
    yield
    plt.close('all')


def write_grouped_file(path, units: list[str], groups: dict[str, list[list[float]]]):
    """
    按 tools/ 的输出格式写一个分组数据文件，格式由扩展名决定：
      .csv          逗号分隔（与 tools 导出一致）
      .xlsx / .xls  Excel
      .txt / .dat   空白分隔（仪器导出的文本格式）

    units  : 每组数据列的单位（各组相同），如 ["Frequency(Hz)", "Zs'(ohm)"]
    groups : {组名: 数据行列表}，每行长度 == len(units)
    """
    path = Path(path)
    suffix = path.suffix.lower()
    # 空白分隔时，空单元格会被连续空白「吞掉」导致列错位，
    # 所以 txt 的标识列用 '-' 占位（即 Dataloader 文档里画的格式），NaN 写成 'nan'
    is_text = suffix in ('.txt', '.dat')
    blank = '-' if is_text else ''

    columns = []
    for group_name, rows in groups.items():
        rows = np.asarray(rows, dtype=float)
        assert rows.shape[1] == len(units), f"{group_name} 的列数与 units 不一致"
        # 标识列：第 0 行是组名，下面留空
        columns.append([group_name] + [blank] * len(rows))
        # 数据列：第 0 行是单位，下面是数值
        for col_idx, unit in enumerate(units):
            if is_text:
                assert not any(c.isspace() for c in unit), f"txt 格式的单位不能含空白：{unit!r}"
            columns.append([unit] + rows[:, col_idx].tolist())
    # columns 是「列的列表」，转置成表格后写出（无表头、无索引）
    table = pd.DataFrame(columns).T

    if suffix == '.csv':
        table.to_csv(path, index=False, header=False, encoding='utf-8-sig')
    elif suffix in ('.xlsx', '.xls'):
        table.to_excel(path, index=False, header=False)
    elif is_text:
        table.to_csv(path, sep='\t', index=False, header=False, na_rep='nan')
    else:
        raise ValueError(f"不支持的扩展名：{suffix}")
    return path


def load_file(path, columns_per_group: int):
    """用真实的 Dataloader 读文件（直接给 file_path，跳过选文件对话框）。"""
    loader = Dataloader(
        DATASET_FRACTION=1 / columns_per_group,
        COLUMNS_PER_DATASET=columns_per_group,
    )
    loader.file_path = str(path)
    return loader.load_data()


# ──────────────────────────────────────────────
# 工厂 fixture：一个脚本一种数据？那就让 fixture 返回「造数据的函数」，
# 每个测试按自己的数据类型（单位、组数、数值）现场造一份。
# ──────────────────────────────────────────────
@pytest.fixture
def make_dataset(tmp_path):
    """
    返回函数 make(units, groups, fmt='csv') -> DataSet。
    fmt 取 'csv' / 'xlsx' / 'txt'，决定写出哪种文件再用 Dataloader 读回。

    tmp_path 是 pytest 内置 fixture：每个测试一个独立的临时目录，
    测试结束自动清理，不会在项目里留下垃圾文件。
    """
    def make(units, groups, fmt='csv'):
        path = write_grouped_file(tmp_path / f'data.{fmt}', units, groups)
        return load_file(path, columns_per_group=len(units) + 1)
    return make


# ──────────────────────────────────────────────
# 普通 fixture：最常用的一份 EIS 小数据，很多测试直接拿来用
# ──────────────────────────────────────────────
EIS_UNITS = ["Frequency(Hz)", "Zs'(ohm)", "Zs''(ohm)"]


@pytest.fixture
def eis_dataset(make_dataset):
    """
    3 组 × 3 行的 EIS 数据（fixture 可以依赖别的 fixture）：
      - 频率三组相同：1, 10, 100
      - S1 = S0 × 2，S2 = S0 × 3   → 组间做差/做比的结果可以心算
    """
    s0 = [[1,   10.0, -1.0],
          [10,  20.0, -2.0],
          [100, 30.0, -3.0]]
    s1 = [[f, 2 * a, 2 * b] for f, a, b in s0]
    s2 = [[f, 3 * a, 3 * b] for f, a, b in s0]
    return make_dataset(EIS_UNITS, {'S0': s0, 'S1': s1, 'S2': s2})
