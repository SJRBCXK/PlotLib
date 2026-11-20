"""
测试对象：src/plotlib/dataloader.py 的 Dataloader.load_data()
重点：tools/ 输出格式的文件，读进来后 names / units / sample_idx / data 是否正确。

本文件用到的新写法（Step 4）：
  - fixture 参数：测试函数参数写 eis_dataset，pytest 自动调用 conftest.py 里同名 fixture
  - 工厂 fixture：make_dataset 返回一个函数，按需造不同类型的数据
  - tmp_path：pytest 内置的临时目录
"""
import numpy as np
import pytest

from conftest import EIS_UNITS, load_file, write_samples_file


# ──────────────────────────────────────────────
# 直接使用现成的 fixture
# ──────────────────────────────────────────────
def test_eis_dataset_metadata(eis_dataset):
    """每列的样品名、单位、样品号都按「样品 × 通道」展开。"""
    assert eis_dataset.names == ['S0'] * 3 + ['S1'] * 3 + ['S2'] * 3
    assert eis_dataset.units == EIS_UNITS * 3
    assert eis_dataset.sample_idx == [0, 0, 0, 1, 1, 1, 2, 2, 2]
    assert eis_dataset.channel_idx == [0, 1, 2] * 3


@pytest.mark.parametrize("fmt", ['csv', 'xlsx', 'txt'])
def test_numeric_sample_names_stay_text(make_dataset, fmt):
    """
    样品名按文本原样读：'101' 不变成 101.0，'1.50' 不变成 1.5；数据照常是数字。
    回归（55576fb 复审 1）：标识列除了第 0 行全空，pandas 把整列当浮点数，数字样品名读成 float，
    双 Y 轴替换 '{name}'、Plotly 滑块的档位标签都因此报错。
    """
    ds = make_dataset(['x(s)', 'y(V)'], {'101': [[1, 2.5]], '1.50': [[3, 4]]}, fmt)
    assert ds.names == ['101'] * 2 + ['1.50'] * 2
    assert all(type(name) is str for name in ds.names)
    np.testing.assert_array_equal(ds.data, [[1, 2.5, 3, 4]])


def test_eis_dataset_values(eis_dataset):
    """标识列被跳过，只剩数值列；第 0 行（单位行）不进 data。"""
    assert eis_dataset.data.shape == (3, 9)
    # 样品 0 的 Zs' 列
    np.testing.assert_array_equal(eis_dataset.data[:, 1], [10, 20, 30])
    # 样品 1 = 样品 0 × 2
    np.testing.assert_array_equal(eis_dataset.data[:, 4], [20, 40, 60])


# ──────────────────────────────────────────────
# 工厂 fixture：一个脚本一种数据，同一套测试覆盖所有列宽
# piezo 每个样品 6 列、eis_nyquist 8 列、eis_bode 10 列（都含 1 列标识）
# ──────────────────────────────────────────────
@pytest.mark.parametrize("columns_per_sample", [6, 8, 10],
                         ids=['piezo', 'eis_nyquist', 'eis_bode'])
def test_various_sample_widths(make_dataset, columns_per_sample):
    n_units = columns_per_sample - 1
    units = [f"U{i}" for i in range(n_units)]
    row = list(range(n_units))
    ds = make_dataset(units, {'A': [row, row], 'B': [row, row]})

    assert ds.num_samples == 2
    assert ds.data.shape == (2, 2 * n_units)
    assert ds.units == units * 2


# ──────────────────────────────────────────────
# 三种文件格式：同一份数据，读出来必须完全一样
#
# 历史（Step 6）：txt 原本用 delim_whitespace=True 读取，pandas 3 删掉了这个参数。
# 当时 'txt' 用 pytest.param('txt', marks=xfail(raises=TypeError, strict=True)) 标成
# 「已知会失败」；修好后它「意外通过」(XPASS) 被 strict 判为失败，于是删掉了标记。
# 现在它是回归测试：谁再改坏 txt 读取，这里立刻变红。
# ──────────────────────────────────────────────
ALL_FORMATS = ['csv', 'xlsx', 'txt']


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_all_formats_load_identically(make_dataset, fmt):
    rows = [[1, 10.0, -1.0], [10, 20.0, -2.0]]
    ds = make_dataset(EIS_UNITS, {'S0': rows, 'S1': rows}, fmt=fmt)

    assert ds.names == ['S0'] * 3 + ['S1'] * 3
    assert ds.units == EIS_UNITS * 2
    np.testing.assert_array_equal(ds.data, np.hstack([rows, rows]))


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_header_text_kept_as_written(make_dataset, fmt):
    """
    表头（样品名、单位）原样保留：样品名 'NA'、单位 'N/A' 不被当成缺失值；数值区的空格子照样是 NaN。
    回归（1.0 发布前复审）：pandas 默认把 'NA'、'N/A' 当缺失值，样品名、单位都读成 nan。
    """
    ds = make_dataset(['N/A', 'y(V)'], {'NA': [[1, float('nan')]], 'S1': [[3, 4]]}, fmt=fmt)
    assert ds.names == ['NA'] * 2 + ['S1'] * 2
    assert ds.units == ['N/A', 'y(V)'] * 2
    assert ds.data[0, 0] == 1 and np.isnan(ds.data[0, 1])


def test_empty_sample_name_raises(tmp_path):
    """样品名是空的 → ValueError，指出文件里第几列（从 1 数），不等到绘图时才出错。"""
    path = tmp_path / 'blank.csv'
    path.write_text('S0,x,y,,x,y\n,1,2,,3,4\n', encoding='utf-8')
    with pytest.raises(ValueError, match='第 4 列的样品名为空'):
        load_file(path, columns_per_sample=3)


@pytest.mark.parametrize("fmt", ALL_FORMATS)
def test_empty_cell_becomes_nan(make_dataset, fmt):
    """数据缺一格，读进来应是 NaN，其余数值不受影响。"""
    ds = make_dataset(["X", "Y"], {'A': [[1, float('nan')], [3, 4]]}, fmt=fmt)
    assert np.isnan(ds.data[0, 1])
    np.testing.assert_array_equal(ds.data[1], [3, 4])


# ──────────────────────────────────────────────
# 报错：列数对不上
# ──────────────────────────────────────────────
def test_wrong_columns_per_sample_raises(tmp_path):
    """文件每个样品 4 列，却按每个样品 6 列去读 → ValueError，信息里写出总列数和每个样品的列数。"""
    path = write_samples_file(tmp_path / 'eis.csv', EIS_UNITS,
                              {'S0': [[1, 2, 3]], 'S1': [[1, 2, 3]]})   # 共 8 列
    with pytest.raises(ValueError, match=r"8 列.*columns_per_sample=6"):
        load_file(path, columns_per_sample=6)


def test_txt_with_mixed_whitespace(tmp_path):
    """仪器导出的 txt 常用「多个空格对齐」或空格、制表符混用，都应按一个分隔符处理。"""
    path = tmp_path / 'aligned.txt'
    path.write_text(
        "S0    Frequency(Hz)   Zs'(ohm)\tZs''(ohm)\n"
        "-     1.0             10.0\t\t-1.0\n"
        "-     10.0            20.0  \t-2.0\n",
        encoding='utf-8',
    )
    ds = load_file(path, columns_per_sample=4)

    assert ds.units == EIS_UNITS
    np.testing.assert_array_equal(ds.data, [[1, 10, -1], [10, 20, -2]])


def test_unsupported_extension_raises(tmp_path):
    """不支持的扩展名：报错信息里写出这个文件名（方便看出是哪个文件），并列出支持的格式。"""
    path = tmp_path / 'data.json'
    path.write_text('{}', encoding='utf-8')
    with pytest.raises(ValueError, match=r"data\.json.*\.csv.*\.xlsx.*\.txt"):
        load_file(path, columns_per_sample=4)


@pytest.mark.parametrize("fmt", ['CSV', 'Xlsx', 'TXT'])
def test_extension_case_insensitive(tmp_path, fmt):
    """扩展名不区分大小写（步骤 7.1）：仪器或 Windows 导出的 .CSV 也能读。"""
    path = write_samples_file(tmp_path / f'data.{fmt.lower()}', EIS_UNITS, {'S0': [[1, 2, 3]]})
    path = path.rename(tmp_path / f'DATA.{fmt}')
    ds = load_file(path, columns_per_sample=4)
    np.testing.assert_array_equal(ds.data, [[1, 2, 3]])


def test_reused_loader_keeps_no_state(tmp_path):
    """
    同一个 loader 先后读两个文件，各得各的数据（步骤 7.1：中间结果是局部变量，loader 只记每个样品的列数）；
    路径只从参数传入，loader 上没有 file_path 之类的属性可以赋值。
    """
    from plotlib.dataloader import Dataloader

    loader = Dataloader(columns_per_sample=4)
    first = loader.load_data(write_samples_file(tmp_path / 'a.csv', EIS_UNITS, {'A': [[1, 2, 3]]}))
    second = loader.load_data(write_samples_file(tmp_path / 'b.csv', EIS_UNITS,
                                                 {'B': [[4, 5, 6]], 'C': [[7, 8, 9]]}))
    assert first.names == ['A'] * 3 and second.names == ['B'] * 3 + ['C'] * 3
    np.testing.assert_array_equal(first.data, [[1, 2, 3]])
    assert vars(loader) == {'columns_per_sample': 4}


def test_columns_per_sample_is_required():
    """每个样品的列数没有默认值（步骤 7.1：以前默认 6 只适合 piezo）；旧参数名不再接受。"""
    from plotlib.dataloader import Dataloader

    with pytest.raises(TypeError):
        Dataloader()  # pyright: ignore[reportCallIssue]  故意不传
    with pytest.raises(TypeError):
        Dataloader(COLUMNS_PER_DATASET=6)  # pyright: ignore[reportCallIssue]  旧参数名
    for bad in (1, 2.5, True):             # 至少 1 列标识 + 1 列数据；要整数
        with pytest.raises(ValueError, match='columns_per_sample'):
            Dataloader(columns_per_sample=bad)  # pyright: ignore[reportArgumentType]


def test_import_does_not_need_tkinter():
    """
    导入数据模块不导入 tkinter（步骤 7.1）：没有图形界面的环境（服务器、CI）也能用 Dataloader 读文件。
    在新的 Python 进程里检查：当前进程可能早已被别的模块导入过 tkinter。
    """
    import subprocess
    import sys

    code = "import sys, plotlib.dataloader; print('tkinter' in sys.modules)"
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'False'


def test_sample_count_exact_for_any_width(make_dataset):
    """
    回归（第三方审查 A）：每样品 49 列、共 98 列时，int(98 * (1/49)) 得 1，
    第二个样品被静默丢掉，后面的校验也照着错的样品数通过。样品数应由整数除法得出。
    """
    units = [f"U{i}" for i in range(48)]
    row = list(range(48))
    ds = make_dataset(units, {'A': [row], 'B': [row]})

    assert ds.num_samples == 2
    assert ds.data.shape == (1, 96)


# ──────────────────────────────────────────────
# monkeypatch：临时替换掉「弹窗选文件」
# 不传路径时 Dataloader 会弹出文件对话框——测试里不能等人点。
# monkeypatch.setattr 在本测试内把它换成直接返回路径的函数，测试结束自动还原。
# ──────────────────────────────────────────────
def test_load_without_path_uses_file_dialog(tmp_path, monkeypatch):
    from plotlib.dataloader import Dataloader

    path = write_samples_file(tmp_path / 'picked.csv', EIS_UNITS, {'S0': [[1, 2, 3]]})
    monkeypatch.setattr(Dataloader, 'select_data_file', staticmethod(lambda: str(path)))

    ds = Dataloader(columns_per_sample=4).load_data()
    assert ds.names == ['S0'] * 3


class _FakeTk:
    """代替 tkinter.Tk：测试里不建真窗口。"""
    def withdraw(self):
        pass

    def destroy(self):
        pass


def test_cancel_file_dialog_raises(monkeypatch):
    """
    取消选择文件 → NoFileSelected（步骤 7.1），不再调用 exit() 把调用它的程序一起退出；
    它不是 OSError，和「文件读不了」（FileNotFoundError 等）区分得开。
    tkinter 改在函数里导入，所以替换的是 tkinter 模块上的属性：函数每次执行时才从模块里取。
    """
    import tkinter
    from tkinter import filedialog

    from plotlib.dataloader import Dataloader, NoFileSelected

    monkeypatch.setattr(tkinter, 'Tk', _FakeTk)
    monkeypatch.setattr(filedialog, 'askopenfilename', lambda **kwargs: '')
    with pytest.raises(NoFileSelected):
        Dataloader(columns_per_sample=4).load_data()
    assert not issubclass(NoFileSelected, OSError)


def test_missing_file_raises_file_not_found(tmp_path):
    """路径写错（文件不存在）→ FileNotFoundError，与取消选择的 NoFileSelected 不同。"""
    with pytest.raises(FileNotFoundError):
        load_file(tmp_path / 'missing.csv', columns_per_sample=4)
