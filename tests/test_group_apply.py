"""
测试对象：src/plotlib/group.py 的 Group.apply()、Group.reduce()
apply 的数据来自 conftest.py 的 eis_dataset：S1 = S0 × 2，S2 = S0 × 3，频率相同。
所以每个测试的「正确答案」都能心算出来——这就是手工设计测试数据的意义。
"""
import numpy as np
import pytest

from plotlib.group import Group
from plotlib.processor import Reduction

ZS = ("Zs'(ohm)", "Zs''(ohm)")
S0_ZS = np.array([[10, -1], [20, -2], [30, -3]], dtype=float)
S1_ZS = S0_ZS * 2
S2_ZS = S0_ZS * 3


def subtract(*slices):
    return slices[1].data - slices[0].data


def ratio(*slices):
    return slices[1].data / slices[0].data


def test_subtract_two_groups(eis_dataset):
    """S1 - S0 = S0 × 2 - S0 = S0。"""
    result = Group(eis_dataset, {'diff': {'num': [0, 1]}}).apply(subtract, select=ZS)
    np.testing.assert_allclose(result.data, S0_ZS)
    assert result.units == list(ZS)
    assert result.names == ['diff_subtract'] * 2   # 自动命名：组名_函数名

def test_multigroups_ratio(eis_dataset):
    """S1 / S0 = 2，S2 / S0 = 3。"""
    result = Group(eis_dataset, {'S1/S0': {'num': [0, 1]}, 'S2/S0': {'num': [0, 2]}}).apply(ratio, select=ZS)
    np.testing.assert_allclose(result.data[:, :2], 2)   # S1/S0
    np.testing.assert_allclose(result.data[:, 2:], 3)   # S2/S0
    assert result.units == list(ZS) * 2
    assert result.names == ['S1/S0_ratio'] * 2 + ['S2/S0_ratio'] * 2

def test_each_config_entry_becomes_one_result_sample(eis_dataset):
    """config 里有几个分组，结果里就有几个样品，样品号从 0 依次编号。"""
    config = {
        'S1/S0': {'num': [0, 1]},
        'S2/S0': {'num': [0, 2]},
    }
    result = Group(eis_dataset, config).apply(ratio, select=ZS)

    assert result.sample_idx == [0, 0, 1, 1]
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


def test_sample_index_out_of_range_raises(eis_dataset):
    """
    数据只有样品 0~2，配置里写了 5 → 创建 Group 时就报错，不等到 apply。
    （曾在 apply 中才报「无匹配列」；全部样品都不存在时报的是看不出分组的选列错误）
    """
    with pytest.raises(ValueError, match="'bad'"):
        Group(eis_dataset, {'bad': {'num': [0, 5]}})


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
    """样品 0 有 2 列、样品 1 只有 1 列 → 无法逐列对齐，报错。"""
    from plotlib.dataset import DataSet
    ds = DataSet().form_array(np.ones((2, 2)), ['A', 'A'], ['x', 'y'], 0, repeat_times=2)
    ds.expandata(DataSet().form_array(np.ones(2), ['B'], ['x'], 1))
    with pytest.raises(ValueError, match="列数不一致"):
        Group(ds, {'g': {'num': [0, 1]}}).apply(subtract)




def test_callback_may_return_python_scalar(eis_dataset):
    """回调返回 Python 标量（如 1.0）当作 1 × 1。"""
    result = Group(eis_dataset, {'g': {'num': [0, 1]}}).apply(lambda *s: 1.0, select=ZS)
    assert result.data.tolist() == [[1.0]]


# ══════════════════════════════════════════════
# reduce：先样品内汇总，再组内跨样品汇总
# ══════════════════════════════════════════════
def test_group_reduce():
    """
    样品 A（0）：F [1, 9]，E [10, 30]；B（2）：F [3]，E [50]；C（4）：F [5, NaN]，E 全 NaN。
    G1 = {A, B}，G2 = {B, C}（B 同属两组，各算一次）。行数不等：within='max' 必须先得到每个样品的一个值
    （A 的 F 是 9，不是把 1、9、3 三行混在一起统计）。
    """
    from plotlib.dataset import DataSet

    nan = np.nan
    data = DataSet().form_array(np.array([[1, 10], [9, 30]]), ['A', 'A'], ['F(N)', 'E(%)'], 0, repeat_times=2)
    data.expandata(DataSet().form_array(np.array([[3, 50]]), ['B', 'B'], ['F(N)', 'E(%)'], 2, repeat_times=2))
    data.expandata(DataSet().form_array(np.array([[5, nan], [nan, nan]]), ['C', 'C'], ['F(N)', 'E(%)'], 4,
                                        repeat_times=2))
    groups = Group(data, {'G1': {'num': [0, 2]}, 'G2': {'num': [2, 4]}})

    # 样品汇总值：G1 的 F 是 [9, 3]、E 是 [30, 50]；G2 的 F 是 [3, 5]、E 是 [50]（C 的 E 全 NaN，不计数）
    cases: list[tuple[Reduction, list]] = [('mean', [6, 40, 4, 50]),
                                           ('std', [18 ** 0.5, 200 ** 0.5, 2 ** 0.5, nan]),
                                           ('sem', [3, 10, 1, nan])]
    for how, expected in cases:
        result = groups.reduce(how, within='max')
        np.testing.assert_allclose(result.data, [expected], rtol=1e-12, err_msg=str(how))
        assert (result.names, result.units, result.sample_idx) == (
            ['G1', 'G1', 'G2', 'G2'], ['F(N)', 'E(%)'] * 2, [0, 0, 1, 1])

    # channels 定顺序和范围：结果的第 i 个通道对应 channels[i]
    result = groups.reduce('mean', within='max', channels=[1, 0])
    np.testing.assert_allclose(result.data, [[40, 6, 50, 4]])
    assert result.units == ['E(%)', 'F(N)'] * 2

    # within=None：每个样品的每个通道至多一个有效值；A 的 F 有两行，报错并指出样品和单位
    with pytest.raises(ValueError, match=r"A.*F\(N\).*2 个"):
        groups.reduce('mean')
    np.testing.assert_allclose(Group(data, {'g': {'num': [2]}}).reduce('mean').data, [[3, 50]])

    with pytest.raises(ValueError, match='通道 5'):
        groups.reduce('mean', within='max', channels=[5])

    # 一次算几种：每个样品只汇总一次，均值和误差来自同一批样品汇总值。
    # 汇总函数每次被调用返回不同的值（1、3，之后 10、30）：分两次算时柱高是 2、标准差却按 10、30 算成 14.14
    class Drifting:
        def __init__(self):
            self.calls = 0

        def __call__(self, values):
            self.calls += 1
            return [1, 3, 10, 30][self.calls - 1]

    within = Drifting()
    mean, std = Group(data, {'G1': {'num': [0, 2]}}).reduce(['mean', 'std'], within=within, channels=[0])
    assert (mean.data.tolist(), round(float(std.data[0, 0]), 3), within.calls) == ([[2.0]], 1.414, 2)

    # 两步之间检查：某个样品汇总出无穷大就报错（A 得 +inf、B 得 -inf，第二步求均值会悄悄变成 NaN）
    with pytest.raises(ValueError, match=r"G1.*A.*F\(N\).*无穷"):
        groups.reduce('mean', within=lambda v: np.inf if v[0] == 1 else -np.inf, channels=[0])
