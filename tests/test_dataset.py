"""
测试对象：src/dataset.py —— DataSet（数据容器）、Column / ColumnList（列视图）

DataSet 的核心约定（各测试围绕它们展开）：
  1. 元数据长度一致：data 的列数 == len(names) == len(units) == len(groups_idx) ...
  2. 同一「组内位置」在各组中单位相同（第 0 列都是频率、第 1 列都是 Zs' ...）
  3. column[i] 是视图：改它就是改 DataSet 本身
"""
import numpy as np
import pytest

from src.dataset import DataSet


def make(data, names, units, group_idx=0):
    """手工造一个单组 DataSet（不经过文件）。"""
    data = np.asarray(data, dtype=float)
    n_cols = 1 if data.ndim < 2 else data.shape[1]
    return DataSet().form_array(data, list(names), list(units), group_idx, repeat_times=n_cols)


# ══════════════════════════════════════════════
# form_array：由数组 + 元信息创建 DataSet
# ══════════════════════════════════════════════
def test_empty_dataset():
    ds = DataSet()
    assert ds.status == 'empty'
    assert ds.data.shape == (0, 0)
    assert len(ds.column) == 0


def test_form_array_fills_metadata():
    ds = make([[1, 2], [3, 4]], ['a', 'b'], ['x', 'y'], group_idx=5)

    assert ds.status == 'written'
    assert ds.groups_idx == [5, 5]
    assert ds.group_local_idx == [0, 1]
    assert ds.local_idx == [0, 1]
    assert ds.father_idx == [0, 1]       # None 被补成自身位置
    assert ds.initial_idx == [0, 1]
    assert ds.num_datagroups == 1


@pytest.mark.parametrize("data, shape", [
    (np.array(7.0),          (1, 1)),    # 标量
    (np.array([1.0, 2, 3]),  (3, 1)),    # 一维 → 一列
], ids=['scalar', '1d'])
def test_form_array_reshapes_to_2d(data, shape):
    ds = DataSet().form_array(data, ['a'], ['u'], 0)
    assert ds.data.shape == shape


def test_metadata_length_mismatch_raises():
    """2 列数据只给 1 个名字 → 约定 1 被破坏。"""
    with pytest.raises(RuntimeError, match="不匹配"):
        DataSet().form_array(np.ones((3, 2)), ['a'], ['x', 'y'], 0, repeat_times=2)


def test_none_group_idx_gives_consistent_metadata():
    """
    未指定组号（None）的列共用一个新组，组数和组内序号与之一致。
    回归：曾经先按 None 统计组数/序号、后补组号，得到 groups=[0,1,2] 但 num_datagroups=1。
    """
    ds = DataSet().form_array(np.ones((2, 3)), ['a', 'b', 'c'], ['u'] * 3, None, repeat_times=3)
    assert ds.groups_idx == [0, 0, 0]
    assert ds.num_datagroups == 1
    assert ds.group_local_idx == [0, 1, 2]


def test_none_group_idx_after_existing_groups():
    """已有组号时，None 列的新组号 = 已有最大组号 + 1。"""
    ds = make([1, 2], ['a'], ['u'], 4)
    ds.groups_idx.append(None)
    ds.names.append('b')
    ds.units.append('u')
    ds.father_idx.append(None)
    ds.initial_idx.append(None)
    ds.data = np.column_stack([ds.data, [3, 4]])
    ds.update_attributes()
    assert ds.groups_idx == [4, 5]
    assert ds.num_datagroups == 2


# ══════════════════════════════════════════════
# expandata：横向拼接
# ══════════════════════════════════════════════
def test_expandata_appends_columns_and_groups():
    ds = DataSet()
    ds.expandata(make([1, 2], ['a'], ['u'], 0)).expandata(make([3, 4], ['b'], ['u'], 1))

    np.testing.assert_array_equal(ds.data, [[1, 3], [2, 4]])
    assert ds.names == ['a', 'b']
    assert ds.groups_idx == [0, 1]
    assert ds.num_datagroups == 2
    assert ds.group_local_idx == [0, 0]


@pytest.mark.parametrize("left, right, nan_col", [
    ([1, 2, 3], [9],       1),     # 新加的短 → 新列补 NaN
    ([9],       [1, 2, 3], 0),     # 原有的短 → 原列补 NaN
], ids=['new_shorter', 'old_shorter'])
def test_expandata_pads_shorter_with_nan(left, right, nan_col):
    """行数不同的数据拼接时，短的一方在下面补 NaN。"""
    ds = make(left, ['a'], ['u'], 0).expandata(make(right, ['b'], ['u'], 1))
    assert ds.data.shape == (3, 2)
    assert ds.data[0, nan_col] == 9
    assert np.isnan(ds.data[1:, nan_col]).all()


def test_unit_mismatch_between_groups_raises():
    """组 1 的第 1 列单位和组 0 不同 → 约定 2 被破坏。"""
    g0 = make([[1, 2]], ['a', 'b'], ['x', 'y'], 0)
    g1 = make([[1, 2]], ['c', 'd'], ['x', 'z'], 1)
    with pytest.raises(RuntimeError, match="Unit mismatch"):
        g0.expandata(g1)


# ══════════════════════════════════════════════
# Column / ColumnList：列视图
# ══════════════════════════════════════════════
def test_column_reads_metadata(eis_dataset):
    col = eis_dataset.column[4]          # S1 的 Zs'
    assert (col.name, col.unit, col.group_idx, col.group_local_idx) == ('S1', "Zs'(ohm)", 1, 1)
    np.testing.assert_array_equal(col.data, [20, 40, 60])


def test_column_is_a_view(eis_dataset):
    """改 Column 就是改 DataSet（约定 3）。"""
    col = eis_dataset.column[0]
    col.name = 'renamed'
    col.unit = 'Hz'
    col.data[:] = 0                  # 原地修改视图

    assert eis_dataset.names[0] == 'renamed'
    assert eis_dataset.units[0] == 'Hz'
    assert (eis_dataset.data[:, 0] == 0).all()

    eis_dataset.column[1].data = [5, 6, 7]     # 整体赋值也写回
    np.testing.assert_array_equal(eis_dataset.data[:, 1], [5, 6, 7])


def test_column_group_change_updates_derived_metadata():
    """
    改组号后，组数和组内序号随之更新。
    回归：setter 曾只写回 groups_idx，num_datagroups、group_local_idx 保持旧值。
    （用单位全相同的数据：移动任何一列都不会破坏「同位置同单位」约束）
    """
    ds = make([[1, 2, 3]], ['a', 'b', 'c'], ['u'] * 3, group_idx=0)
    ds.column[2].group_idx = 5
    assert ds.groups_idx == [0, 0, 5]
    assert ds.num_datagroups == 2
    assert ds.group_local_idx == [0, 1, 0]


def test_column_group_change_breaking_units_raises_and_rolls_back(eis_dataset):
    """
    把 S0 的频率列移走后，S0 的第 0 列变成 Zs'，而 S1/S2 的第 0 列仍是频率 → 违反约束 2。
    要报错，且回滚到原状态，不能留下半改的数据集。
    """
    with pytest.raises(RuntimeError, match="Unit mismatch"):
        eis_dataset.column[0].group_idx = 7
    assert eis_dataset.groups_idx[0] == 0
    assert eis_dataset.num_datagroups == 3
    assert eis_dataset.group_local_idx == [0, 1, 2] * 3


def test_column_dict_access(eis_dataset):
    col = eis_dataset.column[1]
    assert col['unit'] == "Zs'(ohm)"
    col['name'] = 'X'
    assert eis_dataset.names[1] == 'X'


@pytest.mark.parametrize("action, key", [
    ('get', 'nope'),
    ('set', 'nope'),
    ('set', 'local_idx'),       # 索引类属性只读
], ids=['get_unknown', 'set_unknown', 'set_readonly'])
def test_column_bad_key_raises(eis_dataset, action, key):
    col = eis_dataset.column[0]
    with pytest.raises(KeyError):
        if action == 'get':
            col[key]
        else:
            col[key] = 1


def test_column_to_dict_is_a_copy(eis_dataset):
    d = eis_dataset.column[1].to_dict()
    d['data'][:] = 0
    assert eis_dataset.data[0, 1] == 10      # 原数据未变


def test_column_list_indexing(eis_dataset):
    cols = eis_dataset.column
    assert len(cols) == 9
    assert cols[-1].local_idx == 8
    assert [c.local_idx for c in cols[2:5]] == [2, 3, 4]
    assert [c.local_idx for c in cols] == list(range(9))
    with pytest.raises(IndexError):
        cols[9]


# ══════════════════════════════════════════════
# 遍历与重组
# ══════════════════════════════════════════════
def test_iter_by_groups(eis_dataset):
    parts = list(eis_dataset.iter('groups'))
    assert [p.names for p in parts] == [['S0'] * 3, ['S1'] * 3, ['S2'] * 3]


def test_iter_by_units(eis_dataset):
    """按单位遍历：每次产出所有组中该单位的列。"""
    parts = list(eis_dataset.iter('units'))
    assert [p.units[0] for p in parts] == ["Frequency(Hz)", "Zs'(ohm)", "Zs''(ohm)"]
    assert all(p.names == ['S0', 'S1', 'S2'] for p in parts)


def test_iter_unknown_method_raises(eis_dataset):
    with pytest.raises(ValueError, match="不支持的遍历方式"):
        next(eis_dataset.iter('colors'))


def test_columns_to_new_dataset(eis_dataset):
    """extended=False：用选中的列组成新数据集，initial_idx 记住原位置。"""
    new = eis_dataset.columns_to_dataset([eis_dataset.column[1], eis_dataset.column[4]],
                                         extended=False)
    assert new is not eis_dataset
    assert new.names == ['S0', 'S1']
    assert new.initial_idx == [1, 4]
    assert len(eis_dataset.names) == 9          # 原数据集不变


def test_columns_appended_to_self(eis_dataset):
    """extended=True：选中的列追加到当前数据集末尾。"""
    result = eis_dataset.columns_to_dataset([eis_dataset.column[1]])
    assert result is eis_dataset
    assert len(eis_dataset.names) == 10


def test_rearrange_columns_sorts_by_group_then_position():
    ds = make([[1, 2, 3, 4]], ['a', 'b', 'c', 'd'], ['x', 'x', 'y', 'y'])
    ds.groups_idx = [1, 0, 1, 0]
    ds.update_attributes()
    ds._rearrange_columns()

    assert ds.names == ['b', 'd', 'a', 'c']
    assert ds.groups_idx == [0, 0, 1, 1]
    assert ds.group_local_idx == [0, 1, 0, 1]
    np.testing.assert_array_equal(ds.data, [[2, 4, 1, 3]])
