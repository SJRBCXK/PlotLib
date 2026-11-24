"""
测试对象：src/plotlib/processor.py 的 DataTransformer —— 对列做数学变换（apply / Norm）

结果的命名规则（未手动指定时）：
  - 名字：只有一列 → 沿用原名；多列同名 → Results_i_of_<名>；否则 Results_i_of_<名1>_<名2>
  - 单位：所有输入单位相同 → 沿用；否则 unitless_i
  - 样品号：所有输入属于同一样品 → 沿用；new_sample=True 或输入跨样品 → 新样品号

eis_dataset 列号：S0 = 0~2，S1 = 3~5，S2 = 6~8；每个样品 [Freq, Zs', Zs'']
"""
import numpy as np
import pytest

from plotlib.processor import DataTransformer, Reduction

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
    """不同样品的同单位列使用组合名称，并沿用输入单位。"""
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


@pytest.mark.parametrize("explicit", [
    lambda dt: dt.apply(lambda d: d, indicies=[1], input_sample_idx=3, input_unit='|Z|'),
    lambda dt: dt.apply(lambda d: d, indicies=[1], naming_func=lambda: {'sample_idx': 3, 'units': ['|Z|']}),
], ids=['input_sample_idx', 'naming_func'])
def test_new_sample_skips_ids_already_in_results(eis_dataset, explicit):
    """
    先显式把结果写到样品 3（数据集已有 0 ~ 2），再 new_sample=True 自动分配：新样品是 4，不与已累计的结果撞号。
    回归（1.0 发布前复审）：自动编号只看输入数据集，也分到 3，两次结果被并成同一个样品。
    """
    dt = DataTransformer(eis_dataset)
    explicit(dt)
    assert dt.Norm(indicies=[1, 2], new_sample=True, norm_unit='|Z|').sample_idx == [3, 4]


@pytest.mark.parametrize("sample_idx", [[3, 4], 1.5, True], ids=['list', 'float', 'bool'])
def test_apply_naming_func_sample_idx_must_be_one_int(eis_dataset, sample_idx):
    """
    一次计算只产出一个样品（逐样品、逐分组、跨样品合成都如此），naming_func 的 sample_idx 只收一个整数，
    写错 → 中文 TypeError。回归（2026-11-20 全面评审）：标注曾写 int | list[int]，传列表在深处报「unhashable type」。
    """
    with pytest.raises(TypeError, match='sample_idx 只收一个整数'):
        DataTransformer(eis_dataset).apply(lambda d: d, indicies=[1, 2],
                                           naming_func=lambda: {'sample_idx': sample_idx})


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


# ══════════════════════════════════════════════
# 样品号分配、源数据校验与数值边界
# ══════════════════════════════════════════════
def two_samples(dtype=float):
    """第 0 列是样品 3（[1, 2]），第 1 列是样品 0（[10, 20]），单位相同。"""
    from plotlib.dataset import DataSet

    ds = DataSet().form_array(np.array([1, 2], dtype=dtype), ['A'], ['u'], 3)
    return ds.expandata(DataSet().form_array(np.array([10, 20], dtype=dtype), ['B'], ['u'], 0))


def test_cross_sample_results_get_new_samples():
    """输入来自多个样品时，每次计算分配一个新样品号（类说明的规则），不会合进同一个样品。"""
    t = DataTransformer(two_samples())
    t.apply(lambda d: d.sum(axis=1))
    result = t.apply(lambda d: d[:, 0] - d[:, 1])
    assert result.sample_idx == [4, 5]

    # 变换器创建后源数据集又加了样品 4：分配时按源数据集当前的样品号避开，不撞号
    from plotlib.dataset import DataSet

    ds = two_samples()
    t = DataTransformer(ds)
    ds.expandata(DataSet().form_array(np.array([5, 6], dtype=float), ['C'], ['u'], 4))
    assert t.apply(lambda d: d.sum(axis=1), indicies=[0, 1]).sample_idx == [5]


def test_transformer_reads_current_dataset():
    """数据集在变换器创建后被排序：按位置取列和按 Column 取列读到的是同一列（当前的）。"""
    ds = two_samples()
    t = DataTransformer(ds)
    ds.sort_columns()                                       # 样品 0 排到第 0 列
    by_index = t.apply(indicies=0, extended=False)
    by_column = t.apply(column=[ds.column[0]], extended=False)
    assert by_index.data.ravel().tolist() == by_column.data.ravel().tolist() == [10, 20]

    # 同通道单位冲突时两条入口都拦下：按 Column 取列也要校验列所在的数据集
    col = ds.column[0]
    ds.units[0] = 'ms'
    for call in (lambda: t.apply(indicies=0), lambda: t.apply(column=[col])):
        with pytest.raises(RuntimeError, match='单位不一致'):
            call()


def test_norm_without_overflow():
    """整数平方不在整数类型里溢出；浮点的中间平方溢出、结果可表示时也算得出来；复数取模、负阶也照常。"""
    from plotlib.dataset import DataSet

    for row, order, expected in (([50000, 50000], 2, 50000 * 2 ** 0.5), ([3e200, 4e200], 2, 5e200),
                                 ([3, 4], 1, 7), ([3, 4], 3, 91 ** (1 / 3)), ([0, 0], 2, 0),
                                 ([3 + 4j, 0], 2, 5),                        # 复数取模，不丢虚部
                                 ([1e200, 1e-200], -1, 1e-200),             # 负阶：由最小的数主导，不下溢成 0
                                 ([2, 0], -1, 0)):
        dtype = {int: np.int32, float: float, complex: complex}[type(row[0])]
        ds = DataSet().form_array(np.array([row], dtype=dtype), ['A', 'A'], ['u', 'u'], 0, repeat_times=2)
        np.testing.assert_allclose(DataTransformer(ds).Norm(order=order).data.ravel(), [expected], rtol=1e-12)

    # complex64 取模时不能在单精度里溢出：|3e38+3e38j| ≈ 4.24e38 超出 float32，结果 2.12e38 可以表示
    z = np.array([[3e38 + 3e38j, 3e38 + 3e38j]], dtype=np.complex64)
    ds = DataSet().form_array(z, ['A', 'A'], ['u', 'u'], 0, repeat_times=2)
    np.testing.assert_allclose(DataTransformer(ds).Norm(order=-1).data.ravel(), [3e38 * 2 ** 0.5 / 2], rtol=1e-6)


def test_apply_accepts_python_scalar(eis_dataset):
    """回调返回 Python 标量（如 1.0）当作 1 × 1，与返回 np.float64 一样。"""
    result = DataTransformer(eis_dataset).apply(lambda d: float(d.max()), indicies=1)
    assert result.data.tolist() == [[30.0]]


# ══════════════════════════════════════════════
# Reduce：每列汇总成一个值
# ══════════════════════════════════════════════
def test_reduce_statistics():
    """
    四列：[1, NaN, 3, 5]（样品 3）、[7]（样品 3）、[2]（样品 5）、全 NaN（样品 5）。
    忽略 NaN 后手算；单个有效值的 std / sem 为 NaN，全 NaN 的列任何汇总都是 NaN。
    """
    from plotlib.dataset import DataSet

    nan = np.nan
    s3 = DataSet().form_array(np.array([[1, 7], [nan, nan], [3, nan], [5, nan]]),
                              ['S3', 'S3'], ['F(N)', 'E(%)'], 3, repeat_times=2)
    s5 = DataSet().form_array(np.array([[2, nan]]), ['S5', 'S5'], ['F(N)', 'E(%)'], 5, repeat_times=2)
    data = s3.expandata(s5)
    data.data = data.data.astype(np.float32)        # 单精度输入，结果提升到双精度

    expected = {
        'mean': [3, 7, 2, nan], 'median': [3, 7, 2, nan],
        'first': [1, 7, 2, nan], 'last': [5, 7, 2, nan],
        'max': [5, 7, 2, nan], 'min': [1, 7, 2, nan],
        'std': [2, nan, nan, nan], 'sem': [2 / 3 ** 0.5, nan, nan, nan],
        np.sum: [9, 7, 2, nan],                     # 函数收到去掉 NaN 的一维数组
    }
    for how, values in expected.items():
        result = DataTransformer(data).Reduce(how)
        assert result.data.dtype == np.float64
        np.testing.assert_allclose(result.data, [values], rtol=1e-12, err_msg=str(how))
        assert (result.names, result.units, result.sample_idx) == (
            ['S3', 'S3', 'S5', 'S5'], ['F(N)', 'E(%)'] * 2, [3, 3, 5, 5])

    # None：每列至多一个有效值，原样取出；多于一个时报错，信息带样品、单位和个数
    np.testing.assert_array_equal(DataTransformer(data).Reduce(None, indicies=[1, 3]).data, [[7, nan]])
    with pytest.raises(ValueError, match=r"S3.*F\(N\).*3 个"):
        DataTransformer(data).Reduce(None)

    # 写法不对、函数返回的不是一个实数（数组、字符串、None、复数），都在汇总时报错
    for how, error in (('avg', ValueError), (3, TypeError), (lambda v: v, TypeError),
                       (lambda v: 'bad', TypeError), (lambda v: None, TypeError), (lambda v: 3 + 4j, TypeError)):
        with pytest.raises(error):
            DataTransformer(data).Reduce(how)       # type: ignore[arg-type]

    complex_data = DataSet().form_array(np.array([[1 + 1j]]), ['A'], ['u'], 0)
    with pytest.raises(TypeError, match='复数'):
        DataTransformer(complex_data).Reduce('mean')

    # 来自两个数据集、长度不同的列：逐列先算成一个值再组装，不在拼原始列时出错
    a = DataSet().form_array(np.array([2, 4]), ['A'], ['u'], 0)
    b = DataSet().form_array(np.array([3, 6, 9]), ['B'], ['u'], 1)
    result = DataTransformer().Reduce('mean', column=[a.column[0], b.column[0]])
    np.testing.assert_array_equal(result.data, [[3, 6]])
    assert (result.names, result.sample_idx) == (['A', 'B'], [0, 1])

    # 中间步骤不上溢、不下溢（原则 14）：std 的平方项、mean 的求和（含正负无穷相加得到 NaN）；
    # 常规量级走原来的算法，大偏置、小波动的数据不因缩放丢精度
    extremes: list[tuple[list[float], Reduction, float]] = [
        ([1e200, 2e200], 'std', 0.5 ** 0.5 * 1e200), ([1e-200, 2e-200], 'std', 0.5 ** 0.5 * 1e-200),
        ([1e308, 1e308], 'mean', 1e308), ([1e308, 1e308], 'median', 1e308),
        ([1e308, 1e308, -1e308, -1e308], 'mean', 0.0), ([1e15, 1e15 + 1], 'std', 0.5 ** 0.5),
        ([-1.5e308, 1.5e308], 'sem', 1.5e308)]          # 标准差本身上溢，除以 √n 后可以表示
    for values, how, expected in extremes:
        extreme = DataSet().form_array(np.array(values), ['A'], ['u'], 0)
        np.testing.assert_allclose(DataTransformer(extreme).Reduce(how).data, [[expected]], rtol=1e-12)
