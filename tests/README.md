# PlotLib 测试说明

这份文档告诉你**测试保证了什么**，不用逐行读测试代码。
想看某条行为具体怎么测的，再按测试名去对应文件里找。

当前状态：**161 个全部通过**，`src/` 语句覆盖率 97%。曾记录的 13 个 bug 已全部修复（见文末「已修复的 bug」）。

> 覆盖率高 ≠ 测得好。一次外部审查发现：有测试只检查了对象类型、只检查了各组都相同的单位，
> 或者两侧用了同一列数据，这样即使代码选错了、画错了也照样通过。
> 所以断言要能**区分对错**：查具体数值、列顺序、原始位置，并且数据要设计得让「选错」显现出来。

## 运行

在项目根目录 `PlotLib/` 下：

| 命令 | 作用 |
|---|---|
| `python -m pytest` | 跑全部测试 |
| `python -m pytest -v` | 逐条列出测试名和结果 |
| `python -m pytest tests/test_plotter.py` | 只跑一个文件 |
| `python -m pytest -k merge` | 只跑名字里含 `merge` 的测试 |
| `python -m pytest -x` | 遇到第一个失败就停 |
| `python -m pytest -rx` | 额外列出每个 xfail（已知 bug）的原因 |
| `python -m pytest --co -q` | 只列出所有测试名，不运行（最新、最全的清单） |
| `python -m pytest --cov=src --cov-report=term-missing` | 覆盖率：每个文件哪些行没被测到 |

VS Code：侧边栏烧杯图标 → 顶部 ▶ 跑全部；列表不全时点 🔄 刷新。

配置在 `pyproject.toml` 的 `[tool.pytest.ini_options]`。
依赖：`pytest`；`openpyxl`（xlsx 测试）；`pytest-cov`（可选，仅覆盖率命令需要）。

结果里如果出现 `x`，是标了 `xfail` 的「已知会失败」测试，不算失败（目前没有）。

## 文件与被测模块

| 测试文件 | 被测代码 | 一句话 |
|---|---|---|
| `conftest.py` | — | 共享的测试数据与环境（见下节），不含测试 |
| `test_dataloader.py` | `src/dataloader.py` | 数据文件能正确读成 DataSet |
| `test_dataset.py` | `src/dataset.py` | DataSet 的创建、拼接、列视图、遍历、重排 |
| `test_processor.py` | `src/processor.py` 的 `DataProcessLayer` | `select` / `by` 按组、名字、单位、索引选列 |
| `test_transformer.py` | `src/processor.py` 的 `DataTransformer` | `apply` / `Norm` 的计算结果与自动命名 |
| `test_group.py` | `src/group.py` 的 `resolve_num` | 分组配置里的 `num` 能正确解析，写错能报出是哪组 |
| `test_group_apply.py` | `src/group.py` 的 `Group` | 组间计算结果、命名、分组编号正确 |
| `test_plotter.py` | `src/plotter.py` | 四种绘图方法画出的线、标签、样式正确 |
| `test_formatters.py` | `src/formatters.py` | 三种格式化器工厂设置的坐标轴、线条、图例属性 |

## 测试数据与环境（conftest.py）

测试**不使用真实实验数据**，而是在临时目录里现场生成一个和 `tools/` 输出同格式的小文件，
再用真实的 `Dataloader` 读进来。

| 名称 | 类型 | 提供什么 |
|---|---|---|
| `eis_dataset` | fixture | 3 组 × 3 行 EIS 数据（见下表）；**S1 = S0×2，S2 = S0×3**，期望结果可心算 |
| `make_dataset(units, groups, fmt)` | fixture（工厂） | 按需造任意列数、任意格式（`csv`/`xlsx`/`txt`）的数据集 |
| `write_grouped_file` / `load_file` | 普通函数 | 写文件 / 读文件，需要单独控制文件时用 |
| `close_figures` | 自动 fixture | 每个测试后关闭所有图窗 |
| — | 全局设置 | matplotlib 切到 `Agg` 后端，不弹窗口 |

`eis_dataset` 的 9 列：

| 列号 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| 组 | S0 | S0 | S0 | S1 | S1 | S1 | S2 | S2 | S2 |
| 单位 | Freq | Zs' | Zs'' | Freq | Zs' | Zs'' | Freq | Zs' | Zs'' |

频率都是 1 / 10 / 100；S0 的 Zs' = 10 / 20 / 30，Zs'' = −1 / −2 / −3。

## 测试清单（测试保证的行为）

### 数据加载 — `test_dataloader.py`
- 每列的组名、单位、组号、组内序号按「组 × 列」正确展开；标识列和单位行不进入数值矩阵
- 每组 6 / 8 / 10 列（piezo / eis_nyquist / eis_bode）都能读
- **csv、xlsx、txt 三种格式读出完全相同的结果**
- 空单元格读成 NaN，不影响其他数值
- txt 中多个空格、制表符混用都当作一个分隔符（pandas 3 兼容的回归测试）
- 列数不是每组列数的整数倍 → `ValueError`；不支持的扩展名 → `RuntimeError`
- 不给文件路径时走「选择文件」对话框（测试中用 `monkeypatch` 替换掉弹窗）

### 数据容器 — `test_dataset.py`
- `form_array`：自动补全组号、组内序号、father/initial 索引；标量和一维数组转成二维
- 未指定组号（None）的列共用一个新组（已有最大组号 + 1），组数与组内序号与之一致
- 元数据长度与数据列数不一致 → `RuntimeError`
- `expandata`：横向拼接列和元数据；行数不同时短的一方补 NaN
- 同一组内位置在不同组里单位不同 → `RuntimeError`
- `column[i]` 是视图：改名字、单位、数据都直接写回 DataSet；`to_dict()` 是副本
- 通过 `column[i].group_idx` 改组号：组数、组内序号随之更新；破坏单位约束时报错并回滚
- 字典式访问 `col['unit']`；未知键、只读键 → `KeyError`
- `column` 支持负索引、切片、迭代；越界 → `IndexError`
- `iter('groups' / 'units')` 按组 / 按单位产出子数据集；不支持的方式 → `ValueError`
- `columns_to_dataset`：`extended=False` 生成新数据集并记住原位置，`True` 追加到自身
- `_rearrange_columns` 按「组号 → 组内序号」排序

### 选列 — `test_processor.py`
- `select('all')` 选全部列；`by('all')` 时 `initial_idx` 仍指向原始数据
- `select('group', [1, 2])` 按组选；`'Group1'`、`'groups'` 等写法都认（大小写不敏感）
- 名字/单位找不到 → `ValueError`（指出是哪个）；不支持的条件类型（如 float）→ `TypeError`
- 按组名、按单位、按单个索引 / 索引列表 / 多个索引选列
- 多个条件依次累加；`extended=False` 只保留最后一个条件
- 元组表示嵌套条件
- 选出的数据是副本，修改不影响原数据
- `initial_idx` 记住在原始数据中的位置
- `by()` 在已选结果上再筛：`father_idx` 指上一层位置，`initial_idx` 仍指原始位置
- `'group'` 后不是整数列表 → `ValueError`；跨组选出单位错位的列 → `RuntimeError`
- 未先 `select` 就 `by` → `RuntimeError`；`getdata` 参数不全 → `ValueError`

### 变换 — `test_transformer.py`
- `apply`：结果数值正确；可传 `indicies`（int / list，支持负索引）、`column`，或都不传（全部列）
- func 即使原地修改收到的数组（`data *= 0`），原始数据也不变
- 跨组、单位不同的多列结果归为同一组，不报单位冲突
- 自动命名：一列 → 沿用原名；多列同名 → `Results_i_of_<名>`；否则名字拼接
- 自动单位：输入单位相同 → 沿用，否则 `unitless_i`
- `input_name` / `input_unit` / `naming_func` 可覆盖自动值（`naming_func` 返回 None 的字段保持自动）；`input_name` 传字符串时按列数重复
- 同一个 `DataTransformer` 多次调用：`extended=True` 累加，`False` 只留最后一次
- 不修改原始数据
- `Norm`：L1、L2 范数数值正确；可指定单位、组号
- `New_group=True`：新组号 = 已有最大组号 + 1，再次分配继续 + 1；组号不连续（如 `[0, 3]`）也不撞号

### 分组配置解析 — `test_group.py`
- `num` 写成 list / tuple / int / range / numpy 整数 / ndarray 都统一成 `list[int]`，元素是 Python `int`
- 组号 `0` 是合法值（不会被当成「空」跳过）
- 缺 `num` 或 `num` 为空 → `ValueError`；类型不对（str、None、float…）→ `TypeError`
- 容器里的元素不是整数（`[1.9]`、`['2']`、浮点 ndarray）→ `TypeError`，不会被悄悄截断
- 报错信息里带出错的组名
- 不修改传入的配置字典

### 组间计算 — `test_group_apply.py`
- 两组相减、相除结果正确
- 配置里有几项，结果就有几组，组号从 0 依次编号
- 未提供 `naming` 时自动命名为 `函数名_组名_组名`；提供时使用自定义名字和单位（含频率透传列、结果列多于输入列）
- callback 返回一维数组 / 标量时自动转成列 / 1×1
- 不修改原始数据集
- 配置引用了不存在的组号 → 报错（`无匹配列`）；各组列数不同 → 报错（`列数不一致`）
- `resolve_group_indices` 按组名取组号；组名不存在 → `ValueError`

### 绘图 — `test_plotter.py`
**`plot_objects`**
- 每个数据组一条线，全部在一张图上，线上数值等于数据集对应列
- X/Y 轴标题是单位，图例是组名
- `plotrange` 限制绘制点数
- `NegLogScale_x` / `NegLogScale_y`：数据取绝对值，刻度文字带负号；两轴同时启用时各保留自己的格式
- `plot_kind` 为 line / scatter / bar 时生成对应类型的对象，且点 / 柱的数据正确；不支持的类型报错
- 列索引超出每组列数 → `RuntimeError`
- `axes_formatter` / `lines_formatter` / `legend_formatter` 都会被调用，拿到正确的对象
- `lines_formatter` 改线型后，图例同步更新

**`group_plotter`**
- 分离模式：每个配置组一张图，`artists` 以数据组号为键
- `apply_group_linestyle=True` 用组配置的线型，否则保持默认实线
- 合并模式：只有一张图；被多个组共用的数据组只画一次，沿用第一个组的线型和颜色；同组统一颜色
- 不修改 `groups_config`
- 配置有误时**先报错再画图**，不留下残缺图窗
- 没有分组配置时退回 `plot_objects`

**`subplotter_yy` / `subplotter_xyy`**
- 每个数据组一张图，以组号为键
- yy：X/Y 数据与轴标题对应所选两列（如 Nyquist 图）
- xyy：左右两侧各用自己的 X、Y 列；左轴红、右轴蓝，两轴共享 X 轴，`twinx` 不新开图窗；`custom_formatter` 每组调用一次

### 格式化器 — `test_formatters.py`
- axes：默认线性刻度、两位小数、隐藏上/右边框；可设对数刻度、坐标范围、刻度格式与换算倍数（`xscaler`）
- axes：`custom_formation` 里的函数以 `(ax, fig)` 调用；可直接交给 `DataPlotter` 使用
- lines：线宽、颜色、线型、marker 与大小；不传 marker 时保持无标记；`custom_formations` 逐条线调用
- legend：字号、边框、可拖拽、位置；可直接交给 `DataPlotter` 使用

## 已修复的 bug

下面的问题都按「先写 `xfail(strict=True)` 测试复现 → 修代码 → 测试 XPASS → 删标记」的流程修复，
对应测试现在是回归测试，测试 docstring 里以「回归：」开头说明了原来的问题。

| 位置 | 原来的问题 | 修法 |
|---|---|---|
| `dataloader.py` 读 txt | pandas 3 删除了 `delim_whitespace`，txt 读不了 | 改用 `sep=r'\s+'` |
| `processor.select('all')` | 必定报「数据选择未执行」 | 改走 `getdata`，与其他条件同一路径 |
| `processor.select` 名字拼错 | 静默忽略；跟在有效条件后会把上一结果再追加一遍 | 找不到报 `ValueError`，不支持的类型报 `TypeError` |
| `DataTransformer` 取列 | func 原地修改会改掉原始数据；`indicies=-1` 得到空列 | int 也走花式索引（副本、支持负数），全部列时 `.copy()` |
| `DataTransformer` 新组号 | 按「组数 + 1」算，组号不连续时撞号 | 「已有最大组号 + 1」，每次分配后 + 1 |
| `DataTransformer` `input_name` | 字符串被拆成单个字符 | 字符串按列数重复，与 `input_unit` 一致 |
| `DataSet.update_attributes` | `None` 组号先统计后补全，元数据自相矛盾 | 先补全再统计；同一批 `None` 共用一个新组 |
| `Column.group_idx` 赋值 | 组数、组内序号不更新 | 赋值后重算并校验，失败则回滚 |
| `Group.apply` | 结果列多于输入列时，提供 `naming` 仍 `IndexError` | 提供 `naming` 时不再调用自动命名 |
| `plotter` 负对数 | 两轴同时启用时 X 轴用了 Y 轴格式（闭包晚绑定） | 两轴用各自的变量 |
| `resolve_num` | `[1.9]` 被截成 `[1]` | 元素必须是整数，否则 `TypeError` |
| `make_lines_formatter` | 不传 marker 就崩（`set_marker(None)`） | 只在指定 marker 时设置 |
| `make_legend_formatter` | 一调用就崩（`set_fontsize`、`set_frameon` 都不存在） | 逐个设置图例文字字号；改用 `set_frame_on` |

**项目配置**：`pyproject.toml` 的 `requires-python` 已从 `>=3.8` 改为 `>=3.14`
（`match` 语法需 3.10+；类内不加引号的自引用类型标注在 3.14 之前导入即报错）。

仍**待确认**（行为可能是有意的，未改）：
- `num=True` 被当成组号 1（`bool` 是 `int` 的子类）。
- `column[i].unit = ...` 改单位时不校验「同位置同单位」约束（组号的 setter 会校验）。
- `formatters.py` 模块文档示例写 `lambda ax: ...`，代码实际以 `(ax, fig)` 调用 `custom_formation`；
  `by()` 文档说「不能连续使用」，代码并未禁止。

## 未覆盖的部分

覆盖率报告中剩下没测到的行：
- `dataloader.py` 的文件对话框本身（需要真实 GUI）
- 各处「理论上走不到」的防御性检查、`__repr__`
- `tools/`、`gui/`、`scripts/`：界面和脚本，不做自动化测试，仍靠手动运行检查

## 新增测试时的约定

1. **文件**：测 `src/xxx.py` 就写在 `tests/test_xxx.py`；测试函数以 `test_` 开头。
2. **命名**：测试名写成「行为」，如 `test_group_config_is_not_modified`，让 `pytest -v` 的输出本身就是一份清单；docstring 写一句「为什么要测」。
3. **数据**：用 `eis_dataset` 或 `make_dataset` 造小数据，数值设计成能心算；不要读真实数据文件。
4. **多组输入**用 `@pytest.mark.parametrize`，并加 `ids` 让输出可读。
5. **报错**用 `pytest.raises(..., match=...)`，一个 `with` 只包一次调用。
6. **绘图**检查 `axesset` 里对象的属性（数据、线型、颜色、标签），不比对图片。
7. **弹窗、文件对话框**等交互用 `monkeypatch.setattr` 临时替换掉。
8. **修 bug**：先写一个会失败的测试复现它（标 `xfail(strict=True)`），修好后删掉标记，留作回归测试。
9. 新增或删除测试后，顺手更新本文件的「测试清单」和「已知 bug」。
