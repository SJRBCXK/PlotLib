"""
scripts/ 里实验脚本的冒烟测试：每个脚本用一份列数、列标题与脚本一致的小数据跑完 main()。

脚本的入口是 ``main(path=None, show=True)``：直接运行时弹窗选文件、最后 ``plt.show()``；
测试传入文件路径和 ``show=False``，所以不弹窗也不阻塞（测试用的 Agg 后端没有窗口，
``plt.show()`` 虽然不阻塞，但会发一条「不能显示」的警告，所以干脆不调用）。
导入脚本模块本身只定义常量和函数，不画图。
"""
import importlib

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.container import BarContainer
import pytest

from conftest import write_samples_file

pytest.importorskip('scipy')       # eis_bode 的寻峰；test 依赖已包含 plotlib[analysis]
pytest.importorskip('plotly')      # piezo_interactive

ROWS = 6
EIS_UNITS = ["Frequency(Hz)", "Z'(ohm)", "Z''(ohm)", "|Z|(ohm)", "Phase(deg)", "Zs'(ohm)", "Zs''(ohm)"]
BODE_UNITS = ["Frequency(Hz)", "Permittivity'", "Permittivity''", "Conductivity'(S/cm)", "Conductivity''(S/cm)",
              "Zp'(ohm)", "Zp''(ohm)", "Tan(Delta)", "Tan(Phi)"]
PIEZO_UNITS = ["Time(s)", "Force(N)", "Displacement(um)", "Time(s)", "Voltage(V)"]
TENSILE_UNITS = ["时间(s)", "应力(MPa)", "应变", "位移(mm)"]


def rows(units: list[str], k: int, overrides: dict[str, list[float]] | None = None) -> list[list[float]]:
    """
    第 k 个样品的数据：第 0 列各样品相同（频率 / 时间，正值递增），其余列按样品号放大，
    保证各样品不同、都是正值（对数轴可画，组间的差、比不为 0）。*overrides* 按列标题给定形状，同样按样品号放大。
    """
    base = np.linspace(1, 6, ROWS)
    table = np.column_stack([base * (j + 1) * (1 + 0.1 * k * (j > 0)) for j in range(len(units))])
    for unit, values in (overrides or {}).items():
        table[:, units.index(unit)] = np.asarray(values) * (1 + 0.1 * k)
    return table.tolist()


PEAK = {"Tan(Delta)": [0.1, 0.3, 0.2, 0.15, 0.12, 0.1]}         # 第 1 行一个峰
NO_PEAK = {"Tan(Delta)": [0.1, 0.12, 0.15, 0.2, 0.25, 0.3]}     # 单调，没有峰
# 两个峰（第 1、3 行），第一个峰所在行缺频率：汇总图和柱状图都应只用第一个峰那一行（频率缺就不画），不能和第二个峰的频率拼在一起
TWO_PEAKS = {"Tan(Delta)": [0.1, 0.3, 0.2, 0.4, 0.1, 0.1], "Frequency(Hz)": [1, np.nan, 3, 4, 5, 6]}
BREAK = {"应力(MPa)": [1, 5, 10, 8, 3, 1]}                       # 应力过峰后陡降：断裂


# 脚本名, 单位, 样品数, 列的形状, 期望图数（手算见 WORK_PLAN 第 5 节步骤 8）
CASES = [
    ('piezo', PIEZO_UNITS, 10, None, 6 + 2 + 1 + 4 * 10),
    ('eis_nyquist', EIS_UNITS, 18, None, 1 + 9 + 18 + 18 + 1 + 9),
    ('eis_bode', BODE_UNITS, 18, PEAK, 1 + 9 + 1 + 1 + 1 + 1),
    ('eis_bode', BODE_UNITS, 18, NO_PEAK, 1 + 9 + 1 + 1),
    ('eis_bode', BODE_UNITS, 18, TWO_PEAKS, 1 + 9 + 1 + 1 + 1 + 1),
    ('tensile', TENSILE_UNITS, 3, BREAK, 3),
    ('select_demo', EIS_UNITS, 10, None, 0),
]


def test_scripts_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(plt.rcParams, 'figure.max_open_warning', 0)     # 压电脚本一次开约 50 张图
    for i, (name, units, count, overrides, figures) in enumerate(CASES):
        path = write_samples_file(tmp_path / f'{name}_{i}.csv', units,
                                  {f'S{k}': rows(units, k, overrides) for k in range(count)})
        module = importlib.import_module(f'scripts.{name}')
        plt.close('all')
        plt.figure('caller')                # 调用方已有的图窗：main() 不能关掉它（按名字查，图号关掉后会被新图重用）
        module.main(path, show=False)
        assert 'caller' in plt.get_figlabels(), name
        assert len(plt.get_fignums()) == figures + 1, (name, overrides)
        if overrides is NO_PEAK:
            assert '没有检出损耗峰' in capsys.readouterr().out
        if overrides is TWO_PEAKS:
            # 最后一张是损耗峰柱状图：tan δ 是第一个峰的值，频率柱不画（第一个峰那一行缺频率）
            containers = plt.figure(plt.get_fignums()[-1]).axes[0].containers
            tan, freq = [c for c in containers if isinstance(c, BarContainer)]
            assert [bar.get_height() for bar in tan.patches] == pytest.approx([0.3 * (1 + 0.1 * k) for k in range(count)])
            assert not np.isfinite([bar.get_height() for bar in freq.patches]).any()
        plt.close('all')

    # 交互图脚本：不开 matplotlib 图，导出 HTML 到指定位置
    path = write_samples_file(tmp_path / 'piezo_interactive.csv', PIEZO_UNITS,
                              {f'S{k}': rows(PIEZO_UNITS, k) for k in range(3)})
    output = tmp_path / 'out' / 'piezo.html'
    importlib.import_module('scripts.piezo_interactive').main(path, output=output)
    assert output.read_text(encoding='utf-8').count('<html') == 1
    assert plt.get_fignums() == []
