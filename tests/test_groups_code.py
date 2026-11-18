"""
测试对象：重排工具生成的 groups 代码（tools/data_reorder_qt.py 与 tools/data_reorder_app.py）
  - 生成的代码能直接执行，得到的配置能被 Group 接受；
  - 线型是标准写法（见 src/plotlib/style.py）：前 4 组依次为
    'solid' / 'dash' / 'dashdot' / 'dot'，之后是自定义虚线 (on, off)。

运行方式（在项目根目录 PlotLib/ 下）：
    python -m pytest tests/test_groups_code.py -v
"""
from types import SimpleNamespace

import numpy as np
import pytest

from plotlib.dataset import DataSet
from plotlib.group import Group

# 9 个分组时期望的线型：前 4 组用标准词，之后是循环生成的自定义虚线
EXPECTED_LINESTYLES = ['solid', 'dash', 'dashdot', 'dot',
                       (3, 5), (5, 7), (7, 9), (3, 11), (5, 5)]


def make_data(sample_count):
    ds = DataSet()
    for sample in range(sample_count):
        ds.expandata(DataSet().form_array(np.ones(2), [f'S{sample}'], ['x'], sample))
    return ds


def run_groups_code(code, sample_count):
    """执行生成的代码，用得到的 groups 建一个 Group（不合法会在这里报错）。"""
    namespace = {}
    exec(code, namespace)
    return Group(make_data(sample_count), namespace['groups'])


def linestyles(groups):
    return [groups.linestyle(name) for name in groups.names]


def test_qt_groups_code_is_standard():
    pytest.importorskip('PySide6')
    from tools.data_reorder_qt import ReorderLogic

    user_groups = [[i] for i in range(9)]
    groups = run_groups_code(ReorderLogic.generate_groups_code(user_groups), 9)
    assert linestyles(groups) == EXPECTED_LINESTYLES
    assert groups.names[:4] == ['1st', '2nd', '3rd', '4th']


def test_tk_groups_code_from_user_groups_is_standard():
    from tools.data_reorder_app import DataReorderGUI

    fake = SimpleNamespace(
        user_groups=[[i] for i in range(9)],
        _get_ordinal_name=lambda i: DataReorderGUI._get_ordinal_name(None, i),
        _get_linestyle_for_group=lambda i: DataReorderGUI._get_linestyle_for_group(None, i),
    )
    code = DataReorderGUI._generate_groups_dict_from_user_groups(fake)
    assert linestyles(run_groups_code(code, 9)) == EXPECTED_LINESTYLES


def test_tk_groups_code_from_selection_is_standard():
    from tools.data_reorder_app import DataReorderGUI

    fake = SimpleNamespace(
        _get_ordinal_name=lambda i: DataReorderGUI._get_ordinal_name(None, i),
        _get_linestyle_for_group=lambda i: DataReorderGUI._get_linestyle_for_group(None, i),
    )
    # 连续的序号合成一组：9 组，单元素组生成 int，多元素组生成 range
    selected = [0, 1, 3, 5, 6, 7, 9, 11, 13, 15, 17, 19]
    code = DataReorderGUI._generate_groups_dict(fake, selected)
    groups = run_groups_code(code, 20)
    assert linestyles(groups) == EXPECTED_LINESTYLES
    assert groups.sample_ids(groups.names[0]) == [0, 1]


# 组名是从 1 开始的序数词；11 ~ 13 是特例（eleventh、twelfth、thirteenth），21 ~ 23 又回到 st / nd / rd
EXPECTED_ORDINALS = {0: '1st', 1: '2nd', 2: '3rd', 3: '4th', 9: '10th',
                     10: '11th', 11: '12th', 12: '13th',
                     20: '21st', 21: '22nd', 22: '23rd', 100: '101st', 110: '111th'}


def test_ordinal_names_are_the_same_in_both_tools():
    from tools.data_reorder_app import DataReorderGUI

    tk_names = {i: DataReorderGUI._get_ordinal_name(None, i) for i in EXPECTED_ORDINALS}
    assert tk_names == EXPECTED_ORDINALS

    pytest.importorskip('PySide6')
    from tools.data_reorder_qt import ReorderLogic

    count = max(EXPECTED_ORDINALS) + 1
    groups = run_groups_code(ReorderLogic.generate_groups_code([[i] for i in range(count)]), count)
    qt_names = {i: groups.names[i] for i in EXPECTED_ORDINALS}
    assert qt_names == EXPECTED_ORDINALS
