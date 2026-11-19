"""
测试对象：src/plotlib/plot_common.py —— 两个绘图器共用的函数

color_positions(sample_ids)：样品号 → 色带位置（0 ~ 1 之间）。
规则：去重、排序后，位置 = 排名 ÷ 样品数。
  - 样品号连续时与旧公式「样品号 ÷ 样品数」结果相同，已有图的颜色不变；
  - 样品号不连续（如 select 后只剩 0、5、9）时也不越界；
  - 最大位置是 (n-1)/n，用不到色带末端（plasma 末端是浅黄色，白底上看不清）。
"""
import pytest

from plotlib.plot_common import color_positions


@pytest.mark.parametrize("sample_ids, expected", [
    ([0, 5, 9],       {0: 0, 5: 1/3, 9: 2/3}),
    ([0, 1, 2],       {0: 0, 1: 1/3, 2: 2/3}),     # 连续：与旧公式结果相同
    ([9, 0, 5, 5, 0], {0: 0, 5: 1/3, 9: 2/3}),     # 乱序、重复：sample_idx 每列记一次样品号
    ([7],             {7: 0}),                     # 单个样品：0/1，不会除以零
    ([],              {}),                         # 没有样品就没有映射
], ids=['sparse', 'contiguous', 'unordered_repeated', 'single', 'empty'])
def test_color_positions(sample_ids, expected):
    assert color_positions(sample_ids) == pytest.approx(expected)


# ──────────────────────────────────────────────
# resolve_groups(groups, dataset)：两个绘图器共用的分组参数检查
# 三种情况（None / 非 Group / 别的数据集）在 test_backend_parity.py 里对两个绘图器一起测，这里只测「不复制」
# ──────────────────────────────────────────────
def test_resolve_groups_returns_same_object(eis_dataset):
    """合法的 Group 原样返回，不复制：绘图器和调用方看到的是同一个 Group。"""
    from plotlib.group import Group
    from plotlib.plot_common import resolve_groups

    groups = Group(eis_dataset, {'A': {'num': [0, 1]}})
    assert resolve_groups(groups, eis_dataset) is groups


# ──────────────────────────────────────────────
# 共用取数：get_column_data / get_xy_data（两个绘图器都用它们取 X、Y）
# eis_dataset：S1 = S0 × 2；通道 0 是频率 [1, 10, 100]，通道 1 是 Zs' [20, 40, 60]，通道 2 是 Zs'' [-2, -4, -6]
# ──────────────────────────────────────────────
def test_get_column_data(eis_dataset):
    """按样品号 + 通道号取一列，返回 (数据, 列名, 单位)；列名是样品名。"""
    from plotlib.plot_common import get_column_data

    data, name, unit = get_column_data(eis_dataset, 1, 1)
    assert data.tolist() == [20, 40, 60]
    assert (name, unit) == ('S1', "Zs'(ohm)")


def test_get_column_data_plotrange(eis_dataset):
    """plotrange 只取前几行；不传（None）取全部行。"""
    from plotlib.plot_common import get_column_data

    assert get_column_data(eis_dataset, 1, 1, plotrange=2)[0].tolist() == [20, 40]


@pytest.mark.parametrize("sample_idx, channel_idx", [(1, 5), (7, 0)], ids=['no_channel', 'no_sample'])
def test_get_column_data_missing_raises(eis_dataset, sample_idx, channel_idx):
    from plotlib.plot_common import get_column_data

    with pytest.raises(RuntimeError, match="未找到对应的列数据"):
        get_column_data(eis_dataset, sample_idx, channel_idx)


def test_get_xy_data_neglog(eis_dataset):
    """neglog_y 只对 Y 取绝对值，X 不变；返回 (x, y, x_label, y_label, x_unit, y_unit)。"""
    from plotlib.plot_common import get_xy_data

    x, y, x_label, y_label, x_unit, y_unit = get_xy_data(eis_dataset, 1, 0, 2, neglog_y=True)
    assert x.tolist() == [1, 10, 100]
    assert y.tolist() == [2, 4, 6]
    assert (x_label, y_label, x_unit, y_unit) == ('S1', 'S1', 'Frequency(Hz)', "Zs''(ohm)")
