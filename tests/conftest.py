"""
conftest.py —— 所有测试文件共享的「准备工作」（fixture）

pytest 会自动加载这个文件，这里定义的 fixture 不用 import，
任何测试函数只要把 fixture 名写进参数列表，就能拿到它的返回值。

─────────────────────────────────────────────────────────────────
测试数据怎么来（Step 4 的核心）：
  不用真实实验数据——太大、会变、看不出「正确答案」。
  而是在测试里**现场生成**一个极小的 CSV，格式与 tools/ 的输出完全一致：

      第 0 行：| 样品名 | 单位1 | 单位2 | ... | 样品名 | 单位1 | ... |
      第 1 行起：|        | 数值  | 数值  | ... |        | 数值  | ... |
                 ↑ 标识列（Dataloader 只读第 0 行的样品名）

  数值手工设计成「一眼能算出结果」，例如样品 1 = 样品 0 × 2，
  这样测 Group.apply 时，期望结果可以直接写出来。
─────────────────────────────────────────────────────────────────
"""
# 必须在任何 pyplot 导入之前切到 Agg：只在内存里画图，不弹窗口、不需要显示器。
# （src/ 本身不指定后端；tools/ 里的 TkAgg/QtAgg 只在运行那些工具时生效）
import matplotlib
matplotlib.use('Agg')

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from plotlib.dataloader import Dataloader
from plotlib.dataset import DataSet
from plotlib.plot_spec import BarSpec, LineSpec, ScatterSpec


# ── 按画法取出计划里的曲线（断言类型，类型检查也能据此收窄，直接读 x、y、heights）──
def xy_curves(figure) -> list[LineSpec | ScatterSpec]:
    """折线 / 散点计划的曲线；*figure* 是 FigureSpec，或带 ``spec`` 的 DrawnFigure。"""
    curves = getattr(figure, 'spec', figure).curves
    assert all(isinstance(curve, (LineSpec, ScatterSpec)) for curve in curves)
    return [curve for curve in curves if isinstance(curve, (LineSpec, ScatterSpec))]


def bar_specs(figure) -> list[BarSpec]:
    """柱状图计划的各个系列；*figure* 是 FigureSpec，或带 ``spec`` 的 DrawnFigure。"""
    curves = getattr(figure, 'spec', figure).curves
    assert all(isinstance(curve, BarSpec) for curve in curves)
    return [curve for curve in curves if isinstance(curve, BarSpec)]


def bar_data() -> DataSet:
    """
    柱状图的测试数据：两个样品，样品号无序（3 在前、0 在后），每个样品 4 个通道，行数不等（拼接时补 NaN）：

        通道 0 F(N)    样品 3: [1, 3, 100]   样品 0: [2]
        通道 1 E(%)    样品 3: [10]          样品 0: [20, 40]
        通道 2 F(N)    样品 3: [NaN, 10]     样品 0: [5]        （与通道 0 列标题相同）
        通道 3 dF(N)   样品 3: [9, 1, NaN]   样品 0: [0.2]      （误差通道）

    每次调用新建一份，测试可以随意改。
    """
    nan = np.nan
    units = ['F(N)', 'E(%)', 'F(N)', 'dF(N)']
    data = DataSet().form_array(np.array([[1, 10, nan, 9], [3, nan, 10, 1], [100, nan, nan, nan]]),
                                ['S3'] * 4, units, 3, repeat_times=4)
    data.expandata(DataSet().form_array(np.array([[2, 20, 5, 0.2], [nan, 40, nan, nan]]),
                                        ['S0'] * 4, units, 0, repeat_times=4))
    return data


@pytest.fixture(autouse=True)
def close_figures():
    """
    autouse=True：每个测试自动使用，不用写进参数。

    yield 之前是准备、之后是清理：测试跑完关闭所有图窗，
    否则图越积越多（matplotlib 超过 20 个会警告），还可能让后面的测试数错图的数量。
    """
    yield
    plt.close('all')


@pytest.fixture(scope="session")
def render():
    """
    返回函数 render(fig) -> 渲染后的完整 Figure。

    Plotly 的 fig 只是 Python 端拼出的 JSON；坐标范围、边距等最终值由浏览器里的
    Plotly.js 计算，可能与 JSON 中的设置不同（例如 automargin 重绘会重置部分自动范围）。
    full_figure_for_development() 让 kaleido 在后台 Chrome 里真正跑一遍 Plotly.js，
    返回计算后的 layout，测试就能断言“实际画出来的”结果。

    scope="session"：整轮测试只启动一次 Chrome（约 4 秒），之后每次渲染约 0.06 秒。
    没装 kaleido 或没有 Chrome 时，用到它的测试会被跳过而不是失败。
    """
    pytest.importorskip("plotly")
    kaleido = pytest.importorskip("kaleido")
    import plotly.graph_objects as go
    # 常驻 Chrome 的接口只在较新的 kaleido 1.x 中提供；没有时每次渲染单独启动，只是更慢。
    persistent = hasattr(kaleido, "start_sync_server")
    try:
        if persistent:
            kaleido.start_sync_server(silence_warnings=True)
        go.Figure().full_figure_for_development(warn=False)   # 试渲染一次，确认 Chrome 可用
    except Exception as exc:
        pytest.skip(f"kaleido 无法渲染（需要 Chrome）：{exc}")

    def render_figure(fig):
        return fig.full_figure_for_development(warn=False)

    yield render_figure
    if persistent:
        kaleido.stop_sync_server(silence_warnings=True)


def write_samples_file(path, units: list[str], samples: dict[str, list[list[float]]]):
    """
    按 tools/ 的输出格式写一个按样品排列的数据文件，格式由扩展名决定：
      .csv          逗号分隔（与 tools 导出一致）
      .xlsx / .xls  Excel
      .txt / .dat   空白分隔（仪器导出的文本格式）

    units   : 每个样品数据列的单位（各样品相同），如 ["Frequency(Hz)", "Zs'(ohm)"]
    samples : {样品名: 数据行列表}，每行长度 == len(units)
    （步骤 7.1 改名：原名 write_grouped_file / groups；「组」现在专指 Group，这里是样品）
    """
    path = Path(path)
    suffix = path.suffix.lower()
    # 空白分隔时，空单元格会被连续空白「吞掉」导致列错位，
    # 所以 txt 的标识列用 '-' 占位（即 Dataloader 文档里画的格式），NaN 写成 'nan'
    is_text = suffix in ('.txt', '.dat')
    blank = '-' if is_text else ''

    columns = []
    for sample_name, rows in samples.items():
        rows = np.asarray(rows, dtype=float)
        assert rows.shape[1] == len(units), f"{sample_name} 的列数与 units 不一致"
        # 标识列：第 0 行是样品名，下面留空
        columns.append([sample_name] + [blank] * len(rows))
        # 数据列：第 0 行是单位，下面是数值
        for col_idx, unit in enumerate(units):
            if is_text:
                assert not any(c.isspace() for c in unit), f"txt 格式的单位不能含空白：{unit!r}"
            columns.append([unit] + rows[:, col_idx].tolist())
    # columns 是「列的列表」，转置成表格后写出（无表头、无索引）
    table = pd.DataFrame(columns).T

    if suffix == '.csv':
        table.to_csv(path, index=False, header=False, encoding='utf-8-sig')
    elif suffix in ('.xlsx', '.xls'):
        table.to_excel(path, index=False, header=False)
    elif is_text:
        table.to_csv(path, sep='\t', index=False, header=False, na_rep='nan')
    else:
        raise ValueError(f"不支持的扩展名：{suffix}")
    return path


def load_file(path, columns_per_sample: int):
    """用真实的 Dataloader 读文件（直接传路径，不弹选文件对话框）。"""
    return Dataloader(columns_per_sample=columns_per_sample).load_data(path)


# ──────────────────────────────────────────────
# 工厂 fixture：一个脚本一种数据？那就让 fixture 返回「造数据的函数」，
# 每个测试按自己的数据类型（单位、样品数、数值）现场造一份。
# ──────────────────────────────────────────────
@pytest.fixture
def make_dataset(tmp_path):
    """
    返回函数 make(units, samples, fmt='csv') -> DataSet。
    fmt 取 'csv' / 'xlsx' / 'txt'，决定写出哪种文件再用 Dataloader 读回。

    tmp_path 是 pytest 内置 fixture：每个测试一个独立的临时目录，
    测试结束自动清理，不会在项目里留下垃圾文件。
    """
    def make(units, samples, fmt='csv'):
        path = write_samples_file(tmp_path / f'data.{fmt}', units, samples)
        return load_file(path, columns_per_sample=len(units) + 1)
    return make


# ──────────────────────────────────────────────
# 普通 fixture：最常用的一份 EIS 小数据，很多测试直接拿来用
# ──────────────────────────────────────────────
EIS_UNITS = ["Frequency(Hz)", "Zs'(ohm)", "Zs''(ohm)"]


@pytest.fixture
def eis_dataset(make_dataset):
    """
    3 个样品 × 3 行的 EIS 数据（fixture 可以依赖别的 fixture）：
      - 三个样品的频率相同：1, 10, 100
      - S1 = S0 × 2，S2 = S0 × 3   → 样品间做差/做比的结果可以心算
    """
    s0 = [[1,   10.0, -1.0],
          [10,  20.0, -2.0],
          [100, 30.0, -3.0]]
    s1 = [[f, 2 * a, 2 * b] for f, a, b in s0]
    s2 = [[f, 3 * a, 3 * b] for f, a, b in s0]
    return make_dataset(EIS_UNITS, {'S0': s0, 'S1': s1, 'S2': s2})


@pytest.fixture
def sparse_dataset():
    """
    样品号不连续（0、5、9）的数据集，模拟 select 挑出部分样品后的情况。
    每个样品 2 个通道 [x, y]，各 3 行。用于测试配色不越界、不重色。
    """
    ds = DataSet()
    for sample in (0, 5, 9):
        values = np.arange(6.0).reshape(3, 2) + sample
        ds.expandata(DataSet().form_array(values, [f'S{sample}'] * 2, ['x', 'y'],
                                          sample, repeat_times=2))
    return ds
