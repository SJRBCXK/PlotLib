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
