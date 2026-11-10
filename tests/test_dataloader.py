"""
测试对象：src/dataloader.py 的 Dataloader.load_data()
重点：tools/ 输出格式的文件，读进来后 names / units / groups_idx / data 是否正确。

本文件用到的新写法（Step 4）：
  - fixture 参数：测试函数参数写 eis_dataset，pytest 自动调用 conftest.py 里同名 fixture
  - 工厂 fixture：make_dataset 返回一个函数，按需造不同类型的数据
  - tmp_path：pytest 内置的临时目录
"""
import numpy as np
import pytest

from conftest import EIS_UNITS, load_file, write_grouped_file


# ──────────────────────────────────────────────
# 直接使用现成的 fixture
# ──────────────────────────────────────────────
def test_eis_dataset_metadata(eis_dataset):
    """每列的组名、单位、组号都按「组 × 列」展开。"""
    assert eis_dataset.names == ['S0'] * 3 + ['S1'] * 3 + ['S2'] * 3
    assert eis_dataset.units == EIS_UNITS * 3
    assert eis_dataset.groups_idx == [0, 0, 0, 1, 1, 1, 2, 2, 2]
    assert eis_dataset.group_local_idx == [0, 1, 2] * 3


def test_eis_dataset_values(eis_dataset):
    """标识列被跳过，只剩数值列；第 0 行（单位行）不进 data。"""
    assert eis_dataset.data.shape == (3, 9)
    # 第 0 组的 Zs' 列
    np.testing.assert_array_equal(eis_dataset.data[:, 1], [10, 20, 30])
    # 第 1 组 = 第 0 组 × 2
    np.testing.assert_array_equal(eis_dataset.data[:, 4], [20, 40, 60])


# ──────────────────────────────────────────────
# 工厂 fixture：一个脚本一种数据，同一套测试覆盖所有列宽
# piezo 每组 6 列、eis_nyquist 8 列、eis_bode 10 列（都含 1 列标识）
# ──────────────────────────────────────────────
@pytest.mark.parametrize("columns_per_group", [6, 8, 10],
                         ids=['piezo', 'eis_nyquist', 'eis_bode'])
def test_various_group_widths(make_dataset, columns_per_group):
    n_units = columns_per_group - 1
    units = [f"U{i}" for i in range(n_units)]
    row = list(range(n_units))
    ds = make_dataset(units, {'A': [row, row], 'B': [row, row]})

    assert ds.num_datagroups == 2
    assert ds.data.shape == (2, 2 * n_units)
    assert ds.units == units * 2


# ──────────────────────────────────────────────
# 三种文件格式：同一份数据，读出来必须完全一样
#
# 历史（Step 6）：txt 原本用 delim_whitespace=True 读取，pandas 3 删掉了这个参数。
# 当时 'txt' 用 pytest.param('txt', marks=xfail(raises=TypeError, strict=True)) 标成
# 「已知会失败」；修好后它「意外通过」(XPASS) 被 strict 判为失败，于是删掉了标记。
# 现在它是回归测试：谁再改坏 txt 读取，这里立刻变红。
# ──────────────────────────────────────────────
ALL_FORMATS = ['csv', 'xlsx', 'txt']


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_all_formats_load_identically(make_dataset, fmt):
    rows = [[1, 10.0, -1.0], [10, 20.0, -2.0]]
    ds = make_dataset(EIS_UNITS, {'S0': rows, 'S1': rows}, fmt=fmt)

    assert ds.names == ['S0'] * 3 + ['S1'] * 3
    assert ds.units == EIS_UNITS * 2
    np.testing.assert_array_equal(ds.data, np.hstack([rows, rows]))


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_empty_cell_becomes_nan(make_dataset, fmt):
    """数据缺一格，读进来应是 NaN，其余数值不受影响。"""
    ds = make_dataset(["X", "Y"], {'A': [[1, float('nan')], [3, 4]]}, fmt=fmt)
    assert np.isnan(ds.data[0, 1])
    np.testing.assert_array_equal(ds.data[1], [3, 4])


# ──────────────────────────────────────────────
# 报错：列数对不上
# ──────────────────────────────────────────────
def test_wrong_columns_per_group_raises(tmp_path):
    """文件每组 4 列，却按每组 6 列去读 → ValueError。"""
    path = write_grouped_file(tmp_path / 'eis.csv', EIS_UNITS,
                             {'S0': [[1, 2, 3]], 'S1': [[1, 2, 3]]})   # 共 8 列
    with pytest.raises(ValueError, match="multiple of COLUMNS_PER_DATASET"):
        load_file(path, columns_per_group=6)


def test_txt_with_mixed_whitespace(tmp_path):
    """仪器导出的 txt 常用「多个空格对齐」或空格、制表符混用，都应按一个分隔符处理。"""
    path = tmp_path / 'aligned.txt'
    path.write_text(
        "S0    Frequency(Hz)   Zs'(ohm)\tZs''(ohm)\n"
        "-     1.0             10.0\t\t-1.0\n"
        "-     10.0            20.0  \t-2.0\n",
        encoding='utf-8',
    )
    ds = load_file(path, columns_per_group=4)

    assert ds.units == EIS_UNITS
    np.testing.assert_array_equal(ds.data, [[1, 10, -1], [10, 20, -2]])


def test_unsupported_extension_raises(tmp_path):
    path = tmp_path / 'data.json'
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(RuntimeError, match="数据集加载失败"):
        load_file(path, columns_per_group=4)


# ──────────────────────────────────────────────
# monkeypatch：临时替换掉「弹窗选文件」
# 不给 file_path 时 Dataloader 会弹出文件对话框——测试里不能等人点。
# monkeypatch.setattr 在本测试内把它换成直接返回路径的函数，测试结束自动还原。
# ──────────────────────────────────────────────
def test_load_without_path_uses_file_dialog(tmp_path, monkeypatch):
    from src.dataloader import Dataloader

    path = write_grouped_file(tmp_path / 'picked.csv', EIS_UNITS, {'S0': [[1, 2, 3]]})
    monkeypatch.setattr(Dataloader, 'select_data_file', staticmethod(lambda: str(path)))

    ds = Dataloader(DATASET_FRACTION=1 / 4, COLUMNS_PER_DATASET=4).load_data()
    assert ds.names == ['S0'] * 3
