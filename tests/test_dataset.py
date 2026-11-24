"""
测试对象：src/plotlib/dataset.py —— DataSet（数据容器）、Column / ColumnList（列视图）

DataSet 的核心约定（各测试围绕它们展开）：
  1. 元数据长度一致：data 的列数 == len(names) == len(units) == len(sample_idx) ...
  2. 同一通道在各样品中单位相同（通道 0 都是频率、通道 1 都是 Zs' ...）
  3. column[i] 是视图：改它就是改 DataSet 本身
"""
import numpy as np
import pytest

from plotlib.dataset import DataSet


def make(data, names, units, sample_idx=0):
    """手工造一个单样品 DataSet（不经过文件）。"""
    data = np.asarray(data, dtype=float)
    n_cols = 1 if data.ndim < 2 else data.shape[1]
    return DataSet().form_array(data, list(names), list(units), sample_idx, repeat_times=n_cols)


# ══════════════════════════════════════════════
# form_array：由数组 + 元信息创建 DataSet
# ══════════════════════════════════════════════
def test_empty_dataset():
    ds = DataSet()
    assert ds.status == 'empty'
    assert ds.data.shape == (0, 0)
    assert len(ds.column) == 0


def test_form_array_fills_metadata():
    ds = make([[1, 2], [3, 4]], ['a', 'b'], ['x', 'y'], sample_idx=5)

    assert ds.status == 'written'
    assert ds.sample_idx == [5, 5]
    assert ds.channel_idx == [0, 1]
    assert ds.local_idx == [0, 1]
    assert ds.father_idx == [0, 1]       # None 被补成自身位置
    assert ds.initial_idx == [0, 1]
    assert ds.num_samples == 1


@pytest.mark.parametrize("data, shape", [
    (np.array(7.0),          (1, 1)),    # 标量
    (np.array([1.0, 2, 3]),  (3, 1)),    # 一维 → 一列
], ids=['scalar', '1d'])
def test_form_array_reshapes_to_2d(data, shape):
    ds = DataSet().form_array(data, ['a'], ['u'], 0)
    assert ds.data.shape == shape


def test_metadata_length_mismatch_raises(capsys):
    """
    2 列数据只给 1 个名字 → 约定 1 被破坏；各项长度写在异常信息里，不打印到标准输出。
    回归（2026-11-20 全面评审发现）：曾先 print 六行长度、再抛一个不带细节的异常。
    """
    with pytest.raises(RuntimeError, match=r"不匹配.*数据 2 列.*names 1"):
        DataSet().form_array(np.ones((3, 2)), ['a'], ['x', 'y'], 0, repeat_times=2)
    assert capsys.readouterr().out == ''


def test_none_sample_idx_gives_consistent_metadata():
    """
    未指定样品号（None）的列共用一个新样品，样品数和通道号与之一致。
    回归：曾经先按 None 统计样品数/通道号、后补样品号，得到 sample_idx=[0,1,2] 但 num_samples=1。
    """
    ds = DataSet().form_array(np.ones((2, 3)), ['a', 'b', 'c'], ['u'] * 3, None, repeat_times=3)
    assert ds.sample_idx == [0, 0, 0]
    assert ds.num_samples == 1
    assert ds.channel_idx == [0, 1, 2]


def test_none_sample_idx_after_existing_samples():
    """已有样品号时，None 列的新样品号 = 已有最大样品号 + 1。"""
    ds = make([1, 2], ['a'], ['u'], 4)
    ds.sample_idx.append(None)
    ds.names.append('b')
    ds.units.append('u')
    ds.father_idx.append(None)
    ds.initial_idx.append(None)
    ds.data = np.column_stack([ds.data, [3, 4]])
    ds.update_attributes()
    assert ds.sample_idx == [4, 5]
    assert ds.num_samples == 2


# ══════════════════════════════════════════════
# expandata：横向拼接
# ══════════════════════════════════════════════
def test_expandata_appends_columns_and_samples():
    ds = DataSet()
    ds.expandata(make([1, 2], ['a'], ['u'], 0)).expandata(make([3, 4], ['b'], ['u'], 1))

    np.testing.assert_array_equal(ds.data, [[1, 3], [2, 4]])
    assert ds.names == ['a', 'b']
    assert ds.sample_idx == [0, 1]
    assert ds.num_samples == 2
    assert ds.channel_idx == [0, 0]


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


def test_unit_mismatch_between_samples_raises():
    """样品 1 的通道 1 单位和样品 0 不同 → 约定 2 被破坏。"""
    g0 = make([[1, 2]], ['a', 'b'], ['x', 'y'], 0)
    g1 = make([[1, 2]], ['c', 'd'], ['x', 'z'], 1)
    with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
        g0.expandata(g1)


def zero_rows(sample_idx):
    """有两个通道、没有行的样品（例如找不到峰时的峰表）。"""
    return make(np.empty((0, 2)), ['p', 'p'], ['x', 'y'], sample_idx)


def test_expandata_zero_row_sample_first():
    """
    回归（第三方审查 B）：零行样品也有列，拼接时补 NaN，不能当成「空容器」。
    曾用 data.size == 0 判断空：(0, 2) 的 size 也是 0，第二次拼接时整块矩阵被替换，报维度不匹配。
    """
    ds = DataSet().expandata(zero_rows(0)).expandata(make([[1, 2]], ['b', 'b'], ['x', 'y'], 1))

    assert ds.data.shape == (1, 4)
    assert np.isnan(ds.data[0, :2]).all()
    np.testing.assert_array_equal(ds.data[0, 2:], [1, 2])
    assert ds.sample_idx == [0, 0, 1, 1]


def test_expandata_all_zero_rows():
    """全部样品都是零行：列照常拼上，行数仍是 0。"""
    ds = DataSet().expandata(zero_rows(0)).expandata(zero_rows(1))
    assert ds.data.shape == (0, 4)
    assert ds.num_samples == 2


def test_zero_row_dataset_columns_and_samples():
    """
    零行数据集（有列、没有行）照样能按列、按样品访问：列数看列，不看元素个数。
    回归（2026-11-20 全面评审发现）：ColumnList 的长度曾用 data.size 判断，零行时为 0，
    column 一列都取不到，for 逐样品遍历时 IndexError。
    """
    ds = DataSet().expandata(zero_rows(0)).expandata(zero_rows(1))
    assert len(ds.column) == 4
    assert [column.sample_idx for column in ds.column] == [0, 0, 1, 1]
    assert [sample.data.shape for sample in ds] == [(0, 2), (0, 2)]


def test_expandata_failure_keeps_status():
    """拼接失败回滚时状态也恢复：读进来的 'loaded' 不变成 'written'（1.0 发布前复审）。"""
    ds = make([[1, 2]], ['a', 'a'], ['x', 'y'], 0)
    ds.status = 'loaded'
    with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
        ds.expandata(make([[1, 2]], ['c', 'c'], ['x', 'z'], 1))
    assert ds.status == 'loaded'


def test_expandata_failure_leaves_dataset_unchanged():
    """
    回归（第三方审查 B）：拼接失败（单位冲突）后原对象不变，之后还能继续正确拼接。
    曾先改数据和元数据、后校验，报错时原对象已经多了这次的列。
    """
    ds = make([[1, 2]], ['a', 'a'], ['x', 'y'], 0)
    with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
        ds.expandata(make([[1, 2]], ['c', 'c'], ['x', 'z'], 1))

    assert ds.data.shape == (1, 2)
    assert ds.names == ['a', 'a'] and ds.units == ['x', 'y'] and ds.sample_idx == [0, 0]
    assert ds.num_samples == 1

    ds.expandata(make([[3, 4]], ['c', 'c'], ['x', 'y'], 1))
    np.testing.assert_array_equal(ds.data, [[1, 2, 3, 4]])
    assert ds.num_samples == 2


# ══════════════════════════════════════════════
# Column / ColumnList：列视图
# ══════════════════════════════════════════════
def test_column_reads_metadata(eis_dataset):
    col = eis_dataset.column[4]          # S1 的 Zs'
    assert (col.name, col.unit, col.sample_idx, col.channel_idx) == ('S1', "Zs'(ohm)", 1, 1)
    np.testing.assert_array_equal(col.data, [20, 40, 60])


def test_column_is_a_view(eis_dataset):
    """改 Column 就是改 DataSet（约定 3）。"""
    col = eis_dataset.column[0]
    col.name = 'renamed'
    col.data[:] = 0                  # 原地修改视图

    assert eis_dataset.names[0] == 'renamed'
    assert (eis_dataset.data[:, 0] == 0).all()

    eis_dataset.column[1].data = [5, 6, 7]     # 整体赋值也写回
    np.testing.assert_array_equal(eis_dataset.data[:, 1], [5, 6, 7])

    # 单位：只有一个样品时，改一列不会和别的样品冲突
    single = make([[1, 2]], ['a', 'a'], ['u', 'v'], sample_idx=0)
    single.column[1].unit = 'Hz'
    assert single.units == ['u', 'Hz']


def test_column_unit_change_breaking_units_raises_and_rolls_back(eis_dataset):
    """
    逐列更新拒绝单位冲突，并保留原单位。统一修改该通道的单位可以通过校验。
    """
    with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
        eis_dataset.column[0].unit = 'Hz'
    assert eis_dataset.units[0] == 'Frequency(Hz)'

    with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
        eis_dataset.column[0]['unit'] = 'Hz'       # 字典式写法走同一个校验
    assert eis_dataset.units[0] == 'Frequency(Hz)'

    eis_dataset.units[0::3] = ['Hz'] * 3            # 批量更新同一通道的单位。
    eis_dataset.update_attributes()
    assert eis_dataset.column[3].unit == 'Hz'


def test_column_sample_change_updates_derived_metadata():
    """
    改样品号后，样品数和通道号随之更新。
    回归：setter 曾只写回 sample_idx，num_samples、channel_idx 保持旧值。
    （用单位全相同的数据：移动任何一列都不会破坏「同位置同单位」约束）
    """
    ds = make([[1, 2, 3]], ['a', 'b', 'c'], ['u'] * 3, sample_idx=0)
    ds.column[2].sample_idx = 5
    assert ds.sample_idx == [0, 0, 5]
    assert ds.num_samples == 2
    assert ds.channel_idx == [0, 1, 0]


def test_column_sample_change_breaking_units_raises_and_rolls_back(eis_dataset):
    """
    把 S0 的频率列移走后，S0 的第 0 列变成 Zs'，而 S1/S2 的第 0 列仍是频率 → 违反约束 2。
    要报错，且回滚到原状态，不能留下半改的数据集。
    """
    with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
        eis_dataset.column[0].sample_idx = 7
    assert eis_dataset.sample_idx[0] == 0
    assert eis_dataset.num_samples == 3
    assert eis_dataset.channel_idx == [0, 1, 2] * 3


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
def test_iter_by_units(eis_dataset):
    """按单位遍历：每次产出所有样品中该单位的列。"""
    parts = list(eis_dataset.iter('units'))
    assert [p.units[0] for p in parts] == ["Frequency(Hz)", "Zs'(ohm)", "Zs''(ohm)"]
    assert all(p.names == ['S0', 'S1', 'S2'] for p in parts)


def test_iter_unknown_method_raises(eis_dataset):
    with pytest.raises(ValueError, match="不支持的遍历方式"):
        next(eis_dataset.iter('colors'))


# 逐样品（步骤 7.2，用户定：仿照 Group 的 __iter__，for 直接遍历 DataSet）
def test_for_loop_iterates_samples(sparse_dataset):
    """
    for sample in dataset：每次一个样品的子 DataSet，按样品在数据集里出现的顺序，与 iter('samples') 相同；
    样品号不连续（0、5、9）时子数据集保留原样品号。
    """
    parts = list(sparse_dataset)
    expected = list(sparse_dataset.iter('samples'))
    assert [p.sample_idx for p in parts] == [[0, 0], [5, 5], [9, 9]]
    assert [p.names for p in parts] == [e.names for e in expected] == [['S0'] * 2, ['S5'] * 2, ['S9'] * 2]
    for part, sample in zip(parts, (0, 5, 9)):
        np.testing.assert_array_equal(part.data, np.arange(6.0).reshape(3, 2) + sample)


def test_for_loop_on_empty_dataset():
    """空数据集没有样品：for 一次也不执行。"""
    assert list(DataSet()) == []


def test_per_sample_transform_keeps_sample_idx(eis_dataset):
    """
    脚本里的逐样品变换：for 遍历样品，每个样品各用一个 DataTransformer 计算，结果拼回一个 DataSet。
    结果仍按原样品号对应（与 Group.apply 不同：那里每个分组的结果是新样品）。
    """
    from plotlib.processor import DataTransformer

    norms = DataSet()
    for sample in eis_dataset:
        norms.expandata(DataTransformer(sample).Norm(norm_unit='|Z|(ohm)'))

    assert norms.sample_idx == [0, 1, 2]
    assert norms.names == ['Results_0_of_S0', 'Results_0_of_S1', 'Results_0_of_S2']   # DataTransformer 的自动命名
    assert norms.units == ['|Z|(ohm)'] * 3
    expected = np.column_stack([np.linalg.norm(eis_dataset.data[:, 3 * k:3 * k + 3], axis=1) for k in range(3)])
    np.testing.assert_allclose(norms.data, expected)


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


def test_sort_columns_sorts_by_sample_then_channel():
    """
    sort_columns（步骤 7.3：原私有方法 _rearrange_columns，脚本在用，改成公开名字）：按「样品号 → 通道号」原地排序，
    返回自己（脚本里接在 expandata 后面链式调用）；旧名字不再保留。
    """
    ds = make([[1, 2, 3, 4]], ['a', 'b', 'c', 'd'], ['x', 'x', 'y', 'y'])
    ds.sample_idx = [1, 0, 1, 0]
    ds.update_attributes()
    assert ds.sort_columns() is ds
    assert not hasattr(ds, '_rearrange_columns')

    assert ds.names == ['b', 'd', 'a', 'c']
    assert ds.sample_idx == [0, 0, 1, 1]
    assert ds.channel_idx == [0, 1, 0, 1]
    np.testing.assert_array_equal(ds.data, [[2, 4, 1, 3]])


# 列位置索引及自动校验
def interleaved():
    """构造样品号不连续且列交错的输入。"""
    ds = DataSet()
    ds.data = np.arange(12, dtype=float).reshape(2, 6)
    ds.names = ['b', 'a', 'b', 'c', 'a', 'b']
    ds.units = ['u0', 'u0', 'u1', 'u0', 'u1', 'u2']
    ds.sample_idx = [5, 2, 5, 9, 2, 5]
    ds.father_idx = [None] * 6
    ds.initial_idx = [None] * 6
    return ds.update_attributes()


def tricky_datasets():
    """覆盖交错列、异长拼接、样品号变更以及列排序。"""
    moved = interleaved()
    moved.column[3].sample_idx = 11
    return [interleaved(),
            interleaved().expandata(make([[7, 8]], ['d', 'd'], ['u0', 'u1'], sample_idx=3)),
            moved,
            interleaved().sort_columns()]


def test_index_and_iter_match_old_scan():
    """
    以逐列扫描验证索引和分组结果，并校验索引的只读性。
    """
    for ds in tricky_datasets():
        positions = ds.column_positions
        for sample in set(ds.sample_idx) | {max(ds.sample_idx) + 1}:
            for channel in range(max(ds.channel_idx) + 2):
                expected = next((i for i, (s, c) in enumerate(zip(ds.sample_idx, ds.channel_idx))
                                 if s == sample and c == channel), None)
                assert positions.get((sample, channel)) == expected
        for method, values in [('samples', ds.sample_idx), ('names', ds.names),
                               ('units', ds.units), ('channels', ds.channel_idx)]:
            groups = [[i for i, v in enumerate(values) if v == key] for key in dict.fromkeys(values)]
            parts = list(ds.iter(method))
            assert [part.initial_idx for part in parts] == [[ds.initial_idx[i] for i in g] for g in groups]
            for part, group in zip(parts, groups):
                np.testing.assert_array_equal(part.data, ds.data[:, group])
    with pytest.raises(TypeError):
        positions[(0, 0)] = 5          # type: ignore[index]


def test_direct_edit_is_checked_on_use(eis_dataset):
    """
    直接编辑元数据后，绘图和列视图使用更新后的样品号及通道号。
    已取得的索引视图随重建同步，样品号的哈希碰撞也不会影响变更检测。
    """
    from plotlib.plotter import DataPlotter

    saved = eis_dataset.column_positions
    eis_dataset.sample_idx[0:3] = [7, 7, 7]
    eis_dataset.sample_idx[6:9] = [0, 0, 0]                  # 将原样品 2 分配为样品 0。
    spec = DataPlotter(eis_dataset).plot_multiline().figures['main'].spec
    assert [curve.sample_idx for curve in spec.curves] == [0, 1, 7]
    assert spec.curves[0].y.tolist() == [30, 60, 90]         # 新的样品 0 是原来的 S2
    assert saved[(0, 1)] == 7
    assert eis_dataset.status == 'written'

    ds = make([[1, 2, 3]], ['a'] * 3, ['u'] * 3, sample_idx=-1)
    ds.sample_idx[0] = -2                                    # 第 0 列单独成样品 -2 → 其余两列通道号变成 0、1
    assert [ds.column[i].channel_idx for i in range(3)] == [0, 0, 1]


def test_conflict_raises_at_every_entry_and_rollback(eis_dataset):
    """
    各入口拒绝不一致的通道单位。修正冲突后可以重新构建索引。
    列视图的校验失败时恢复元数据、索引和状态。
    """
    from plotlib.group import Group
    from plotlib.plotter import DataPlotter
    from plotlib.processor import DataProcessLayer, DataTransformer

    entries = [lambda ds: ds.column_positions, lambda ds: ds.column[1].channel_idx,
               lambda ds: DataPlotter(ds).plot_multiline(), lambda ds: Group(ds, {'A': {'num': [0]}}),
               lambda ds: DataProcessLayer(ds).select('samples', [0]),
               lambda ds: DataProcessLayer(ds).getdata(varlist_idx=[1], father_dataset=ds),
               DataTransformer, list, lambda ds: list(ds.iter('units'))]
    original = {(s, c): 3 * s + c for s in range(3) for c in range(3)}

    eis_dataset.sample_idx[0] = 7                            # 频率列移走 → 样品 0 的通道 0 变成 Zs' → 冲突
    for use in entries:
        with pytest.raises(RuntimeError, match="同一通道的单位不一致"):
            use(eis_dataset)
    eis_dataset.sample_idx[0] = 0
    assert dict(eis_dataset.column_positions) == original

    eis_dataset.status = 'loaded'
    for field, value in [('unit', 'Hz'), ('sample_idx', 7)]:
        with pytest.raises(RuntimeError):
            setattr(eis_dataset.column[0], field, value)
    assert (eis_dataset.units[0], eis_dataset.sample_idx[0]) == ('Frequency(Hz)', 0)
    assert dict(eis_dataset.column_positions) == original
    assert eis_dataset.status == 'loaded'


def test_unchanged_dataset_is_not_rechecked(eis_dataset, monkeypatch):
    """元数据与快照一致时复用索引，并保留加载状态。"""
    from plotlib.plotter import DataPlotter

    calls = []
    original = DataSet.update_attributes
    monkeypatch.setattr(DataSet, 'update_attributes', lambda self: calls.append(self) or original(self))

    DataPlotter(eis_dataset).plot_multiline()
    eis_dataset.units[0] = 'x'
    eis_dataset.units[0] = 'Frequency(Hz)'
    eis_dataset.column_positions
    assert [ds for ds in calls if ds is eis_dataset] == []
    assert eis_dataset.status == 'loaded'


def test_failed_check_keeps_index(eis_dataset):
    """校验失败（同通道单位冲突）时，已取得的列索引视图和通道号保持上一次成功时的样子。"""
    view = eis_dataset.column_positions
    before, channels = dict(view), list(eis_dataset.channel_idx)
    eis_dataset.sample_idx[0] = 1                   # S0 的频率列并进 S1：S1 的通道 1 变成频率
    with pytest.raises(RuntimeError, match="单位不一致"):
        eis_dataset.update_attributes()
    assert (dict(view), eis_dataset.channel_idx) == (before, channels)
