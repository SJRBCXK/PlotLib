"""
测试对象：src/plotlib/group.py 的 Group —— 分组的唯一主人
  - 创建时校验每个分组的配置，并把 'num' 统一格式化为 list[int]；
  - 读接口返回副本；修改只能通过 add / set / delete，且先校验、再修改。
  （校验与格式化的内部函数 _check_group / _resolve_num 不直接测，都通过 Group 测）

─────────────────────────────────────────────────────────────────
本文件用到的写法（对应 learning/testing/LEARNING_PLAN.md 的 Step 1~3）：
  - assert                        断言结果（Step 1）
  - pytest.raises(..., match=...) 断言必须报错，并检查报错文字（Step 2）
  - @pytest.mark.parametrize      一个测试函数跑多组输入（Step 3）

运行方式（在项目根目录 PlotLib/ 下）：
    python -m pytest -v
─────────────────────────────────────────────────────────────────
"""
import numpy as np
import pytest

from plotlib.dataset import DataSet
from plotlib.group import Group


@pytest.fixture
def six_samples():
    """样品 0 ~ 5 各一列：下面的 num 写法会用到 0 ~ 5 的样品号。"""
    ds = DataSet()
    for sample in range(6):
        ds.expandata(DataSet().form_array(np.ones(2), [f'S{sample}'], ['x'], sample))
    return ds


# ──────────────────────────────────────────────
# 合法输入：各种写法的 num 都格式化为 list[int]
# 每一行是一个测试点：(输入, 期望结果)，加新情况只需加一行
# ──────────────────────────────────────────────
@pytest.mark.parametrize("num, expected", [
    ([0, 1, 2],              [0, 1, 2]),   # 标准写法
    ((1, 2),                 [1, 2]),
    (5,                      [5]),         # data_reorder_app：单元素组写成 int
    (range(3, 6),            [3, 4, 5]),   # data_reorder_app：连续多元素组写成 range
    (0,                      [0]),         # 样品号 0 合法——旧写法 `if not num` 会把它当成「空」跳过
    (np.int64(3),            [3]),         # 样品号可能来自 numpy 计算
    (np.array([1, 2]),       [1, 2]),
], ids=['list', 'tuple', 'int', 'range', 'zero', 'np_int', 'ndarray'])
def test_num_is_normalized_to_list(six_samples, num, expected):
    """各种合法写法的 num 都被转成 list[int]。"""
    assert Group(six_samples, {'A': {'num': num}}).sample_ids('A') == expected


@pytest.mark.parametrize("num", [np.int64(3), np.array([1, 2]), (1, 2)],
                         ids=['np_int', 'ndarray', 'tuple'])
def test_elements_are_python_int(six_samples, num):
    """元素是 Python 原生 int，而不是 np.int64 之类（下游可放心当普通整数用）。"""
    result = Group(six_samples, {'A': {'num': num}}).sample_ids('A')
    assert all(type(i) is int for i in result)


def test_only_num_is_formatted(six_samples):
    """原地格式化只改 num（range → list），其余字段原样保留。"""
    config = {'num': range(0, 3), 'linestyle': '--'}
    Group(six_samples, {'A': config})
    assert config == {'num': [0, 1, 2], 'linestyle': '--'}


# ──────────────────────────────────────────────
# 非法输入：必须报错
# 原则：一个 pytest.raises 只包一次调用——包住循环的话，
#       第一次报错就跳出 with 块，后面的输入根本不会执行
# ──────────────────────────────────────────────
def test_num_missing_raises_value_error(six_samples):
    """配置里没有 'num' 时，抛出 ValueError。"""
    with pytest.raises(ValueError):
        Group(six_samples, {'A': {'linestyle': '--'}})


@pytest.mark.parametrize("num", [[], range(0), np.array([])],
                         ids=['empty_list', 'empty_range', 'empty_ndarray'])
def test_num_empty_raises_value_error(six_samples, num):
    """num 为空时，抛出 ValueError（不再像旧版那样悄悄跳过这一组）。"""
    with pytest.raises(ValueError):
        Group(six_samples, {'A': {'num': num}})


@pytest.mark.parametrize("num", ['0,1', None, 3.14, object()],
                         ids=['str', 'None', 'float', 'object'])
def test_num_invalid_type_raises_type_error(six_samples, num):
    """num 不是 int / list / tuple / range / ndarray 时，抛出 TypeError。"""
    with pytest.raises(TypeError):
        Group(six_samples, {'A': {'num': num}})


@pytest.mark.parametrize("num", [[1.9], ['2'], [0, 1.5], np.array([1.0, 2.0])],
                         ids=['float', 'str', 'mixed', 'float_ndarray'])
def test_num_elements_must_be_integers(six_samples, num):
    """
    容器本身合法、但元素不是整数时，也要报 TypeError 并指出组名。
    回归：曾经直接 int() 转换，[1.9] 被截成 [1]，写错的样品号静默变成另一个样品。
    """
    with pytest.raises(TypeError, match="'A' 的 'num' 含非整数元素"):
        Group(six_samples, {'A': {'num': num}})


@pytest.mark.parametrize("config", [
    {'linestyle': '--'},   # 缺 num
    {'num': []},           # num 为空
    {'num': 'abc'},        # num 类型不对
    [0, 1],                # 简写：配置不是字典
    {'num': [0, 0]},       # 样品号重复
    {'num': [9]},          # 样品号不存在
], ids=['missing', 'empty', 'bad_type', 'not_dict', 'duplicate', 'unknown_sample'])
def test_error_message_names_the_group(six_samples, config):
    """报错信息要指出是哪个组写错了——配置里有十几组时，这是定位问题的唯一线索。"""
    # match 用正则在报错文字里搜索；组名带引号，避免误匹配到别的字符
    with pytest.raises((ValueError, TypeError), match="'第3组'"):
        Group(six_samples, {'第3组': config})


# ══════════════════════════════════════════════
# Group：读接口（eis_dataset 有样品 0、1、2）
# ══════════════════════════════════════════════
def make_config():
    """每个测试拿一份新的配置，避免测试之间互相影响。"""
    return {'B': {'num': [2, 0], 'linestyle': '--', 'label': '对照'},
            'A': {'num': [1]}}


def test_group_read_interface(eis_dataset):
    """分组名和样品号都保持书写顺序（顺序就是角色）；options 是 num 以外的字段。"""
    group = Group(eis_dataset, make_config())
    assert group.names == ['B', 'A']
    assert list(group) == ['B', 'A']
    assert group.sample_ids('B') == [2, 0]
    assert group.options('B') == {'linestyle': '--', 'label': '对照'}
    assert group.options('A') == {}


def test_group_num_is_normalized(eis_dataset):
    """num 的各种写法：range / int 都转成 list[int]。"""
    group = Group(eis_dataset, {'A': {'num': range(0, 2)}, 'B': {'num': 2}})
    assert group.sample_ids('A') == [0, 1]
    assert group.sample_ids('B') == [2]


def test_group_read_returns_copies(eis_dataset):
    """读接口不能变成写的后门：改返回值不影响 Group。要修改请用 add / set / delete。"""
    group = Group(eis_dataset, make_config())
    group.sample_ids('B').append(9)
    group.options('B')['linestyle'] = ':'
    assert group.sample_ids('B') == [2, 0]
    assert group.options('B') == {'linestyle': '--', 'label': '对照'}


def test_group_source_config_is_normalized_but_not_regrouped(eis_dataset):
    """
    创建时原地格式化：每个分组的 num 统一成 list[int]，后续处理分组数据时格式一致（用户的设计决定）。
    增删改只改 Group 自己的外层字典，不往原字典里加、删分组。
    """
    config = {'A': {'num': range(0, 2)}, 'B': {'num': [2]}}
    group = Group(eis_dataset, config)
    assert config['A']['num'] == [0, 1]              # 原地格式化
    group.add({'C': {'num': [1]}}).delete('B')
    assert list(config) == ['A', 'B']                # 增删改不影响原字典


# ══════════════════════════════════════════════
# Group：创建时校验
# ══════════════════════════════════════════════
def test_group_shorthand_raises_type_error(eis_dataset):
    """只接受完整写法；简写 {'A': [0, 1]} 要提示正确写法，而不是报「缺少 num」。"""
    with pytest.raises(TypeError, match="'A'.*字典"):
        Group(eis_dataset, {'A': [0, 1]})


def test_group_missing_num_raises(eis_dataset):
    with pytest.raises(ValueError, match="'A'.*'num'"):
        Group(eis_dataset, {'A': {'linestyle': '--'}})


def test_group_empty_num_raises(eis_dataset):
    """
    num 为空不能静默变成空分组。
    回归：_check_group 曾复制当时 resolve_num 的检查，漏掉了「为空」这一条。
    """
    with pytest.raises(ValueError, match="'A'.*为空"):
        Group(eis_dataset, {'A': {'num': []}})


def test_group_unknown_sample_raises(eis_dataset):
    """样品号不存在：创建时就报错，信息里有分组名、不存在的样品号、已有的样品号。"""
    with pytest.raises(ValueError) as excinfo:
        Group(eis_dataset, {'bad': {'num': [0, 5]}})
    message = str(excinfo.value)
    assert "'bad'" in message
    assert '[5]' in message
    assert '[0, 1, 2]' in message


def test_group_duplicate_sample_raises(eis_dataset):
    """同一分组里样品号重复没有实验意义（样品是最小单位）。"""
    with pytest.raises(ValueError, match="'A'.*重复.*0"):
        Group(eis_dataset, {'A': {'num': [0, 1, 0]}})


def test_group_unknown_name_raises(eis_dataset):
    group = Group(eis_dataset, make_config())
    with pytest.raises(ValueError, match="'C'"):
        group.sample_ids('C')
    with pytest.raises(ValueError, match="'C'"):
        group.options('C')


# ══════════════════════════════════════════════
# Group：修改（add / set / delete）与导出（to_config）
# ══════════════════════════════════════════════
def test_group_set_replaces_whole_group_in_place(eis_dataset):
    """set 整体替换已有分组：旧字段（label）不保留，位置不变。"""
    group = Group(eis_dataset, make_config())
    assert group.set({'B': {'num': [2, 0, 1], 'linestyle': ':'}}) is group
    assert group.sample_ids('B') == [2, 0, 1]
    assert group.options('B') == {'linestyle': ':'}
    assert group.names == ['B', 'A']


def test_group_add_appends_new_group(eis_dataset):
    group = Group(eis_dataset, make_config())
    assert group.add({'C': {'num': [1]}}) is group
    assert group.names == ['B', 'A', 'C']


def test_group_delete(eis_dataset):
    group = Group(eis_dataset, make_config())
    assert group.delete('A') is group
    assert group.names == ['B']


@pytest.mark.parametrize("operation, name", [
    (lambda g: g.add({'A': {'num': [0]}}), 'A'),     # add：分组已存在
    (lambda g: g.set({'C': {'num': [0]}}), 'C'),     # set：分组不存在
    (lambda g: g.delete('C'), 'C'),                  # delete：分组不存在
], ids=['add_existing', 'set_missing', 'delete_missing'])
def test_group_modify_wrong_name_raises(eis_dataset, operation, name):
    group = Group(eis_dataset, make_config())
    with pytest.raises(ValueError, match=f"'{name}'"):
        operation(group)
    assert group.to_config() == Group(eis_dataset, make_config()).to_config()


@pytest.mark.parametrize("operation", [
    lambda g: g.set({'B': {'num': [5]}}),                         # 样品号不存在
    lambda g: g.add({'C': {'num': [1]}, 'D': {'num': [0, 0]}}),   # 第二个分组有重复
], ids=['set_unknown_sample', 'add_partly_invalid'])
def test_group_modify_validates_before_changing(eis_dataset, operation):
    """先校验全部、再修改：有任何一个分组不合法，就一个都不改。"""
    group = Group(eis_dataset, make_config())
    with pytest.raises(ValueError):
        operation(group)
    assert group.names == ['B', 'A']
    assert group.sample_ids('B') == [2, 0]


def test_group_to_config_returns_new_dict(eis_dataset):
    """to_config 输出当前配置的新字典；num 是规范化后的列表；改它不影响 Group。"""
    group = Group(eis_dataset, {'A': {'num': range(0, 2), 'linestyle': '--'}})
    group.add({'C': {'num': [2]}})
    config = group.to_config()
    assert config == {'A': {'num': [0, 1], 'linestyle': '--'}, 'C': {'num': [2]}}
    config['A']['num'].append(2)
    assert group.sample_ids('A') == [0, 1]
