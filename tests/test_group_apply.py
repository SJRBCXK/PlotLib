"""
测试对象：src/group.py 的 Group.apply()
数据来自 conftest.py 的 eis_dataset：S1 = S0 × 2，S2 = S0 × 3，频率相同。
所以每个测试的「正确答案」都能心算出来——这就是手工设计测试数据的意义。
"""
import numpy as np
import pytest

from src.group import Group

ZS = ("Zs'(ohm)", "Zs''(ohm)")
S0_ZS = np.array([[10, -1], [20, -2], [30, -3]], dtype=float)


def subtract(*slices):
    return slices[1].data - slices[0].data


def ratio(*slices):
    return slices[1].data / slices[0].data


def test_subtract_two_groups(eis_dataset):
    """S1 - S0 = S0 × 2 - S0 = S0。"""
    result = Group(eis_dataset, {'diff': {'num': [0, 1]}}).apply(subtract, select=ZS)

    np.testing.assert_allclose(result.data, S0_ZS)
    assert result.units == list(ZS)
    assert result.names == ['subtract_S0_S1'] * 2   # 自动命名：函数名_组名_组名


def test_each_config_entry_becomes_one_result_group(eis_dataset):
    """config 里有几项，结果里就有几组，组号从 0 依次编号。"""
    config = {
        'S1/S0': {'num': [0, 1]},
        'S2/S0': {'num': [0, 2]},
    }
    result = Group(eis_dataset, config).apply(ratio, select=ZS)

    assert result.groups_idx == [0, 0, 1, 1]
    np.testing.assert_allclose(result.data[:, :2], 2)   # S1/S0
    np.testing.assert_allclose(result.data[:, 2:], 3)   # S2/S0


def test_custom_naming_with_passthrough_column(eis_dataset):
    """callback 改了列顺序（频率透传到最前）时，naming 负责给出正确的名字和单位。"""
    def diff_with_freq(*slices):
        s0, s1 = slices
        freq = s0.data[:, [2]]                      # select 顺序：Zs', Zs'', Freq
        return np.hstack((freq, s1.data[:, :2] - s0.data[:, :2]))

    def naming(slices, result_data):
        return (['Freq', "dZs'", "dZs''"],
                ['Frequency(Hz)', "Zs'(ohm)", "Zs''(ohm)"])

    result = Group(eis_dataset, {'d': {'num': [0, 1]}}).apply(
        diff_with_freq, select=ZS + ("Frequency(Hz)",), naming=naming)

    np.testing.assert_allclose(result.data[:, 0], [1, 10, 100])
    np.testing.assert_allclose(result.data[:, 1:], S0_ZS)
    assert result.names == ['Freq', "dZs'", "dZs''"]


def test_custom_naming_with_extra_result_column(eis_dataset):
    """
    callback 多返回一列（输入 2 列 → 输出 3 列），由 naming 给出全部名字。
    回归：曾经总是先跑 _auto_naming，按列号取单位越界（IndexError）。
    """
    def diff_and_flag(*slices):
        return np.column_stack((slices[1].data - slices[0].data, np.ones(3)))

    def naming(slices, result_data):
        return ['a', 'b', 'c'], ['u1', 'u2', 'u3']

    result = Group(eis_dataset, {'A': {'num': [0, 1]}}).apply(
        diff_and_flag, select=ZS, naming=naming)
    assert result.names == ['a', 'b', 'c']
    assert result.units == ['u1', 'u2', 'u3']


def test_input_dataset_is_not_modified(eis_dataset):
    """apply 只产生新数据集，不改原始数据。"""
    before = eis_dataset.data.copy()
    Group(eis_dataset, {'d': {'num': [0, 1]}}).apply(subtract, select=ZS)
    np.testing.assert_array_equal(eis_dataset.data, before)


def test_group_index_out_of_range_raises(eis_dataset):
    """数据只有 0~2 组，配置里写了 5 → 报错，而不是静默算出错误结果。"""
    with pytest.raises(ValueError, match="group_idx=5 无匹配列"):
        Group(eis_dataset, {'bad': {'num': [0, 5]}}).apply(subtract, select=ZS)


# ──────────────────────────────────────────────
# callback 返回值的形状
# ──────────────────────────────────────────────
@pytest.mark.parametrize("callback, shape", [
    (lambda *s: s[1].data[:, 0] - s[0].data[:, 0], (3, 1)),   # 一维 → 一列
    (lambda *s: np.float64(s[1].data.sum()),        (1, 1)),   # 标量 → 1×1
], ids=['1d', 'scalar'])
def test_callback_result_is_reshaped_to_2d(eis_dataset, callback, shape):
    result = Group(eis_dataset, {'d': {'num': [0, 1]}}).apply(callback, select=ZS)
    assert result.data.shape == shape


def test_slices_with_different_column_counts_raise():
    """组 0 有 2 列、组 1 只有 1 列 → 无法逐列对齐，报错。"""
    from src.dataset import DataSet
    ds = DataSet().form_array(np.ones((2, 2)), ['A', 'A'], ['x', 'y'], 0, repeat_times=2)
    ds.expandata(DataSet().form_array(np.ones(2), ['B'], ['x'], 1))
    with pytest.raises(ValueError, match="列数不一致"):
        Group(ds, {'g': {'num': [0, 1]}}).apply(subtract)


# ──────────────────────────────────────────────
# resolve_group_indices：按组名取配置
# ──────────────────────────────────────────────
def test_resolve_group_indices(eis_dataset):
    group = Group(eis_dataset, {'A': {'num': range(1, 3)}})
    assert group.resolve_group_indices('A') == [1, 2]
    with pytest.raises(ValueError, match="缺少 'B' 组"):
        group.resolve_group_indices('B')
