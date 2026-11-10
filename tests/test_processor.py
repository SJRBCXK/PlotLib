"""
测试对象：src/processor.py 的 DataProcessLayer —— 按条件选列

eis_dataset 的 9 列（便于对照下面的索引）：
    列号    0     1      2       3     4      5       6     7      8
    组      S0    S0     S0      S1    S1     S1      S2    S2     S2
    单位    Freq  Zs'    Zs''    Freq  Zs'    Zs''    Freq  Zs'    Zs''
"""
import numpy as np
import pytest

from src.processor import DataProcessLayer

ZS_RE, ZS_IM = "Zs'(ohm)", "Zs''(ohm)"


def select(dataset, *args, **kwargs):
    return DataProcessLayer(dataset).select(*args, **kwargs).Selected_data


# ══════════════════════════════════════════════
# select 的各种条件
# ══════════════════════════════════════════════
def test_select_by_group(eis_dataset):
    sel = select(eis_dataset, 'group', [1, 2])
    assert sel.names == ['S1'] * 3 + ['S2'] * 3
    assert sel.initial_idx == [3, 4, 5, 6, 7, 8]       # 记住在原数据中的位置
    assert sel.groups_idx == [1, 1, 1, 2, 2, 2]        # 组号保持原值


def test_select_group_keyword_is_case_insensitive(eis_dataset):
    """'group' / 'Group1' / 'groups' 都能当关键字（scripts/select_test.py 就这么用）。"""
    assert select(eis_dataset, 'Group1', [0]).names == ['S0'] * 3


def test_select_by_group_name(eis_dataset):
    # 只查单位不够：每组单位都一样，选错组也能通过——所以同时查名字和原始位置
    sel = select(eis_dataset, 'S1')
    assert sel.names == ['S1'] * 3
    assert sel.initial_idx == [3, 4, 5]
    assert sel.units == ["Frequency(Hz)", ZS_RE, ZS_IM]


def test_select_by_unit(eis_dataset):
    sel = select(eis_dataset, ZS_RE)
    assert sel.names == ['S0', 'S1', 'S2']
    assert sel.initial_idx == [1, 4, 7]


def test_select_two_units_orders_by_condition(eis_dataset):
    """多个条件依次累加：先所有组的 Zs'，再所有组的 Zs''；组内序号随之重排。"""
    sel = select(eis_dataset, ZS_RE, ZS_IM)
    assert sel.units == [ZS_RE] * 3 + [ZS_IM] * 3
    assert sel.groups_idx == [0, 1, 2, 0, 1, 2]
    assert sel.group_local_idx == [0, 0, 0, 1, 1, 1]


@pytest.mark.parametrize("args, expected_idx", [
    ((4,),       [4]),
    (([1, 4],),  [1, 4]),
    ((1, 4),     [1, 4]),
], ids=['int', 'list', 'several_ints'])
def test_select_by_index(eis_dataset, args, expected_idx):
    sel = select(eis_dataset, *args)
    assert sel.initial_idx == expected_idx
    assert sel.units == [ZS_RE] * len(expected_idx)


def test_select_nested_condition(eis_dataset):
    """元组里放一整套条件，相当于子查询。"""
    assert select(eis_dataset, ('group', [2])).names == ['S2'] * 3


def test_select_extended_false_keeps_last_condition(eis_dataset):
    sel = select(eis_dataset, 'group', [0], 'group', [2], extended=False)
    assert sel.names == ['S2'] * 3


def test_selection_is_a_copy(eis_dataset):
    sel = select(eis_dataset, 'group', [0])
    sel.data[:] = 0
    assert eis_dataset.data[0, 0] == 1


@pytest.mark.parametrize("args", [
    ('group',),               # 后面没有列表
    ('group', (0, 1)),        # 必须是 list，tuple 不行
    ('group', [0, 'a']),      # 列表里必须全是整数
], ids=['missing', 'tuple', 'non_int'])
def test_select_group_without_int_list_raises(eis_dataset, args):
    with pytest.raises(ValueError, match="整数列表"):
        select(eis_dataset, *args)


def test_select_inconsistent_units_raises(eis_dataset):
    """跨组选列时，同一组内位置的单位必须一致：列 0 是 Freq、列 4 是 Zs' → 报错。"""
    with pytest.raises(RuntimeError, match="Unit mismatch"):
        select(eis_dataset, 0, 4)


def test_select_all(eis_dataset):
    """回归：'all' 分支曾以 continue 结尾，跳过了加入已选数据，select('all') 必定报错。"""
    sel = select(eis_dataset, 'all')
    assert sel.names == eis_dataset.names
    assert sel.initial_idx == list(range(9))
    np.testing.assert_array_equal(sel.data, eis_dataset.data)


def test_by_all_keeps_original_positions(eis_dataset):
    """在已选数据上 by('all')：initial_idx 仍指向原始数据，而不是 0..n-1。"""
    sel = DataProcessLayer(eis_dataset).select('group', [1]).by('all').Selected_data
    assert sel.initial_idx == [3, 4, 5]


@pytest.mark.parametrize("args", [('typo',), (ZS_RE, 'typo')],
                         ids=['alone', 'after_valid'])
def test_unknown_name_raises(eis_dataset, args):
    """
    名字/单位拼错要报错，并指出是哪个。
    回归：曾经静默忽略——单独写时返回空数据；跟在有效条件后时把上一个结果再追加一遍。
    """
    with pytest.raises(ValueError, match="找不到名称或单位：'typo'"):
        select(eis_dataset, *args)


def test_unsupported_condition_type_raises(eis_dataset):
    with pytest.raises(TypeError, match="float"):
        select(eis_dataset, 1.5)


# ══════════════════════════════════════════════
# by：在已选结果上二次筛选
# ══════════════════════════════════════════════
def test_by_filters_previous_selection(eis_dataset):
    sel = DataProcessLayer(eis_dataset).select('group', [1, 2]).by(ZS_RE).Selected_data
    assert sel.names == ['S1', 'S2']
    assert sel.father_idx == [1, 4]       # 在上一层（6 列的已选数据）中的位置
    assert sel.initial_idx == [4, 7]      # 在原始数据中的位置


def test_by_without_select_raises(eis_dataset):
    with pytest.raises(RuntimeError, match="by 方法"):
        DataProcessLayer(eis_dataset).by(ZS_RE)


# ══════════════════════════════════════════════
# getdata：底层取列
# ══════════════════════════════════════════════
@pytest.mark.parametrize("kwargs, msg", [
    ({},                                   "varname 或 varlist_idx"),
    ({'varlist_idx': []},                  "varname 或 varlist_idx"),
    ({'varname': 'typo', 'varset': ['a']}, "varname 或 varlist_idx"),   # 名字找不到
    ({'varlist_idx': [0]},                 "father_dataset"),
], ids=['nothing', 'empty_list', 'name_not_found', 'no_father'])
def test_getdata_bad_arguments_raise(eis_dataset, kwargs, msg):
    with pytest.raises(ValueError, match=msg):
        DataProcessLayer(eis_dataset).getdata(**kwargs)
