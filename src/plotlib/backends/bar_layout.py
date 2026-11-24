"""
计算柱状图各堆叠段的基线。

Matplotlib 使用基线放置柱体。Plotly 通过 ``barmode='relative'`` 放置柱体，并使用这些基线定位单独绘制的误差棒。
"""
from collections.abc import Sequence

import numpy as np

from ..plot_spec import BarSpec


def stack_bottoms(bars: Sequence[BarSpec]) -> dict[int, np.ndarray]:
    """
    返回各堆叠系列的基线数组，以 ``id(系列)`` 为键。

    各类别按系列顺序分别累加正值和负值。NaN 不参与累加，并排系列不包含在返回结果中。
    """
    stacked = [bar for bar in bars if bar.mode == 'stack']
    if not stacked:
        return {}
    positive = np.zeros(len(stacked[0].heights))
    negative = np.zeros_like(positive)
    bottoms = {}
    for bar in stacked:
        heights = np.asarray(bar.heights, dtype=float)
        valid = ~np.isnan(heights)
        below_zero = valid & (heights < 0)
        bottoms[id(bar)] = np.where(below_zero, negative, positive)
        positive = positive + np.where(valid & ~below_zero, heights, 0)
        negative = negative + np.where(below_zero, heights, 0)
    return bottoms
