"""
测试对象：src/plotlib/processor.py 的 DataTransformer —— 对列做数学变换（apply / Norm）

结果的命名规则（未手动指定时）：
  - 名字：只有一列 → 沿用原名；多列同名 → Results_i_of_<名>；否则 Results_i_of_<名1>_<名2>
  - 单位：所有输入单位相同 → 沿用；否则 unitless_i
  - 样品号：所有输入属于同一样品 → 沿用；new_sample=True → 新样品号

eis_dataset 列号：S0 = 0~2，S1 = 3~5，S2 = 6~8；每个样品 [Freq, Zs', Zs'']
"""
import numpy as np
import pytest

from plotlib.processor import DataTransformer

ZS_RE = "Zs'(ohm)"


# ══════════════════════════════════════════════
# apply：任意函数
# ══════════════════════════════════════════════
def test_apply_single_column_inherits_metadata(eis_dataset):
    result = DataTransformer(eis_dataset).apply(lambda d: d * 2, indicies=1)

    np.testing.assert_array_equal(result.data.ravel(), [20, 40, 60])
    assert (result.names, result.units, result.sample_idx) == (['S0'], [ZS_RE], [0])


def test_apply_same_group_different_units(eis_dataset):
    """S0 的 Zs' 与 Zs''：同名同样品、单位不同 → Results_0_of_S0 / unitless_0 / 样品 0。"""
    result = DataTransformer(eis_dataset).apply(lambda d: d.sum(axis=1), indicies=[1, 2])

    np.testing.assert_array_equal(result.data.ravel(), [9, 18, 27])
    assert result.names == ['Results_0_of_S0']
    assert result.units == ['unitless_0']
    assert result.sample_idx == [0]


def test_apply_different_names_same_unit(eis_dataset):
    """S0、S1 的 Zs'：名字不同、单位相同 → 名字拼接、单位沿用。
    （跨样品时结果的样品号有 bug，见 test_dataset.py::test_none_sample_idx_gives_consistent_metadata）"""
    result = DataTransformer(eis_dataset).apply(lambda d: d, indicies=[1, 4])
    assert result.names == ['Results_0_of_S0_S1', 'Results_1_of_S0_S1']
    assert result.units == [ZS_RE, ZS_RE]


def test_apply_cross_group_different_units(eis_dataset):
    """
    S0 的 Zs' 与 S1 的 Zs''：跨样品、单位也不同 → 结果两列同属一个样品，不能报单位冲突。
    （修 None 样品号 bug 时曾短暂引入回归：每列拆成一个样品，触发了单位一致性检查）
    """
    result = DataTransformer(eis_dataset).apply(lambda d: d, indicies=[1, 5])
    assert result.units == ['unitless_0', 'unitless_1']
    assert len(set(result.sample_idx)) == 1


def test_apply_without_indices_uses_all_columns(eis_dataset):
    received = []

    def spy(data):                    # 记下 func 收到的数据形状
        received.append(data.shape)
        return data[:, 0]

    DataTransformer(eis_dataset).apply(spy)
    assert received == [(3, 9)]


def test_apply_explicit_name_and_unit(eis_dataset):
    result = DataTransformer(eis_dataset).apply(
        lambda d: d.sum(axis=1), indicies=[1, 4], input_name=['sum'], input_unit='ohm')
    assert (result.names, result.units) == (['sum'], ['ohm'])


def test_apply_naming_func_overrides(eis_dataset):
    """naming_func 返回 None 的字段保持自动值。"""
    result = DataTransformer(eis_dataset).apply(
        lambda d: d, indicies=[1, 2],
        naming_func=lambda: {'names': ['p', 'q'], 'units': None, 'sample_idx': 9})
    assert result.names == ['p', 'q']
    assert result.units == ['unitless_0', 'unitless_1']
    assert result.sample_idx == [9, 9]


def test_apply_with_column_objects(eis_dataset):
    """用 column= 传 Column 对象，效果等同 indicies=。"""
    cols = [eis_dataset.column[4]]
    result = DataTransformer(eis_dataset).apply(lambda d: d / 2, column=cols)
    np.testing.assert_array_equal(result.data.ravel(), [10, 20, 30])
    assert result.names == ['S1']


def test_apply_extended_accumulates_results(eis_dataset):
    """同一个 DataTransformer 多次调用：extended=True 累加，extended=False 只留最后一次。"""
    t = DataTransformer(eis_dataset)
    t.apply(lambda d: d, indicies=1)
    t.apply(lambda d: d, indicies=2)
    assert t.result_dataset.names == ['S0', 'S0']

    t.apply(lambda d: d, indicies=4, extended=False)
    assert t.result_dataset.names == ['S1']


@pytest.mark.parametrize("indicies", [[1, 2], 1, None], ids=['list', 'int', 'all'])
def test_apply_does_not_modify_source(eis_dataset, indicies):
    """
    func 即使「原地」修改收到的数组，原始数据也不能变。
    （用 d * 0 这种返回新数组的写法测不出问题，必须用 *=）
    回归：曾经 int 索引传的是切片视图、None 传的是原数组本身。
    """
    def zero_inplace(data):
        data *= 0
        return data

    before = eis_dataset.data.copy()
    DataTransformer(eis_dataset).apply(zero_inplace, indicies=indicies, input_sample_idx=0)
    np.testing.assert_array_equal(eis_dataset.data, before)


@pytest.mark.parametrize("method", ['apply', 'Norm'])
def test_negative_index(eis_dataset, method):
    """
    负索引与 Python 一致：-1 = 最后一列（S2 的 Zs''：-3, -6, -9）。
    回归：曾经用切片 data[:, i:i+1] 取列，i=-1 变成 data[:, -1:0] 得到空列。
    """
    t = DataTransformer(eis_dataset)
    result = t.apply(lambda d: d, indicies=-1) if method == 'apply' else t.Norm(indicies=-1)
    expected = [-3, -6, -9] if method == 'apply' else [3, 6, 9]      # Norm 取绝对值
    np.testing.assert_allclose(result.data.ravel(), expected)
    assert result.names == ['S2']


@pytest.mark.parametrize("indicies, expected", [
    (1,      ['sum']),
    ([1, 2], ['sum', 'sum']),          # 多列结果：与 input_unit 一样按列数重复
], ids=['one_col', 'two_cols'])
def test_apply_input_name_as_str(eis_dataset, indicies, expected):
    """回归：字符串曾被当成名字列表，'sum' 拆成 ['s','u','m'] 与列数不符而报错。"""
    result = DataTransformer(eis_dataset).apply(lambda d: d, indicies=indicies, input_name='sum')
    assert result.names == expected


# ══════════════════════════════════════════════
# Norm：按行求范数
# ══════════════════════════════════════════════
@pytest.mark.parametrize("order, expected", [
    (1, [11, 22, 33]),                                  # |10|+|-1| ...
    (2, np.sqrt([101, 404, 909])),                      # √(10²+1²) ...
], ids=['L1', 'L2'])
def test_norm_values(eis_dataset, order, expected):
    result = DataTransformer(eis_dataset).Norm(order=order, indicies=[1, 2])
    np.testing.assert_allclose(result.data.ravel(), expected)


def test_norm_extended(eis_dataset):
    t = DataTransformer(eis_dataset)
    t.Norm(indicies=[1, 2])
    assert len(t.Norm(indicies=[4, 5]).names) == 2                     # 累加
    assert len(t.Norm(indicies=[7, 8], extended=False).names) == 1     # 替换


def test_norm_unit_and_group(eis_dataset):
    result = DataTransformer(eis_dataset).Norm(indicies=[1, 2], norm_unit='ohm', norm_sample_idx=7)
    assert (result.units, result.sample_idx) == (['ohm'], [7])


def test_norm_new_sample_is_distinct(eis_dataset):
    """new_sample=True：新样品号 = 已有最大样品号 + 1，同一个 DataTransformer 再分配就继续 + 1。"""
    t = DataTransformer(eis_dataset)                       # 已有样品 0、1、2
    t.Norm(indicies=[1, 2], new_sample=True)
    result = t.Norm(indicies=[4, 5], new_sample=True)
    assert result.sample_idx == [3, 4]


def test_norm_new_sample_with_sparse_sample_ids():
    """
    样品号不连续时也不能撞号：已有样品 [0, 3] → 新样品 4。
    回归：曾经按「样品数 + 1」算，得到 3，与已有样品冲突。
    """
    from plotlib.dataset import DataSet

    ds = DataSet().form_array(np.ones(2), ['a'], ['u'], 0)
    ds.expandata(DataSet().form_array(np.ones(2), ['b'], ['u'], 3))
    result = DataTransformer(ds).Norm(indicies=0, new_sample=True)
    assert result.sample_idx == [4]
