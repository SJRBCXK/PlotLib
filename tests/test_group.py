"""
测试对象：src/group.py 里的 resolve_num(group_name, group_config)
它的作用：从一组分组配置里取出 'num'，统一转成 list[int]；配置有误时报错。

─────────────────────────────────────────────────────────────────
本文件用到的写法（对应 tests/LEARNING_PLAN.md 的 Step 1~3）：
  - assert                        断言结果（Step 1）
  - pytest.raises(..., match=...) 断言必须报错，并检查报错文字（Step 2）
  - @pytest.mark.parametrize      一个测试函数跑多组输入（Step 3）

运行方式（在项目根目录 PlotLib/ 下）：
    python -m pytest -v
─────────────────────────────────────────────────────────────────
"""
import numpy as np
import pytest

from src.group import resolve_num


# ──────────────────────────────────────────────
# 合法输入：各种写法的 num 都转成 list[int]
# 每一行是一个测试点：(输入, 期望结果)，加新情况只需加一行
# ──────────────────────────────────────────────
@pytest.mark.parametrize("num, expected", [
    ([0, 1, 2],              [0, 1, 2]),   # 标准写法
    ((1, 2),                 [1, 2]),
    (5,                      [5]),         # data_reorder_app：单元素组写成 int
    (range(3, 6),            [3, 4, 5]),   # data_reorder_app：连续多元素组写成 range
    (0,                      [0]),         # 组号 0 合法——旧写法 `if not num` 会把它当成「空」跳过
    (np.int64(3),            [3]),         # 组号可能来自 numpy 计算
    (np.array([1, 2]),       [1, 2]),
], ids=['list', 'tuple', 'int', 'range', 'zero', 'np_int', 'ndarray'])
def test_num_is_normalized_to_list(num, expected):
    """各种合法写法的 num 都被转成 list[int]。"""
    assert resolve_num('A', {'num': num}) == expected


@pytest.mark.parametrize("num", [np.int64(3), np.array([1, 2]), (1, 2)],
                         ids=['np_int', 'ndarray', 'tuple'])
def test_elements_are_python_int(num):
    """元素是 Python 原生 int，而不是 np.int64 之类（下游可放心当普通整数用）。"""
    result = resolve_num('A', {'num': num})
    assert all(type(i) is int for i in result)


def test_config_is_not_modified():
    """resolve_num 只读配置，不改写原字典（range 调用后仍是 range）。"""
    config = {'num': range(0, 3), 'linestyle': '--'}
    resolve_num('A', config)
    assert config == {'num': range(0, 3), 'linestyle': '--'}


# ──────────────────────────────────────────────
# 非法输入：必须报错
# 原则：一个 pytest.raises 只包一次调用——包住循环的话，
#       第一次报错就跳出 with 块，后面的输入根本不会执行
# ──────────────────────────────────────────────
def test_num_missing_raises_value_error():
    """配置里没有 'num' 时，抛出 ValueError。"""
    with pytest.raises(ValueError):
        resolve_num('A', {'linestyle': '--'})


@pytest.mark.parametrize("num", [[], range(0), np.array([])],
                         ids=['empty_list', 'empty_range', 'empty_ndarray'])
def test_num_empty_raises_value_error(num):
    """num 为空时，抛出 ValueError（不再像旧版那样悄悄跳过这一组）。"""
    with pytest.raises(ValueError):
        resolve_num('A', {'num': num})


@pytest.mark.parametrize("num", ['0,1', None, 3.14, object()],
                         ids=['str', 'None', 'float', 'object'])
def test_num_invalid_type_raises_type_error(num):
    """num 不是 int / list / tuple / range / ndarray 时，抛出 TypeError。"""
    with pytest.raises(TypeError):
        resolve_num('A', {'num': num})


@pytest.mark.parametrize("num", [[1.9], ['2'], [0, 1.5], np.array([1.0, 2.0])],
                         ids=['float', 'str', 'mixed', 'float_ndarray'])
def test_num_elements_must_be_integers(num):
    """
    容器本身合法、但元素不是整数时，也要报 TypeError 并指出组名。
    回归：曾经直接 int() 转换，[1.9] 被截成 [1]，写错的组号静默变成另一个组。
    """
    with pytest.raises(TypeError, match="'A' 的 'num' 含非整数元素"):
        resolve_num('A', {'num': num})


@pytest.mark.parametrize("config", [
    {'linestyle': '--'},   # 缺 num
    {'num': []},           # num 为空
    {'num': 'abc'},        # num 类型不对
], ids=['missing', 'empty', 'bad_type'])
def test_error_message_names_the_group(config):
    """报错信息要指出是哪个组写错了——配置里有十几组时，这是定位问题的唯一线索。"""
    # match 用正则在报错文字里搜索；组名带引号，避免误匹配到别的字符
    with pytest.raises((ValueError, TypeError), match="'第3组'"):
        resolve_num('第3组', config)
