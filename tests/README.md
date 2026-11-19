# PlotLib 测试说明

这份文档告诉你**测试保证了什么**，不用逐行读测试代码。
想看某条行为具体怎么测的，再按测试名去对应文件里找。

当前状态：**385 个全部通过**，`plotlib` 包语句覆盖率 95%。曾记录的 13 个 bug 已全部修复（见文末「已修复的 bug」）。

> 覆盖率高 ≠ 测得好。一次外部审查发现：有测试只检查了对象类型、只检查了各样品都相同的单位，
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
| `python -m pytest --cov=plotlib --cov-report=term-missing` | 覆盖率：每个文件哪些行没被测到 |
| `python -m pytest -m "not render"` | 跳过需要 Chrome 的渲染测试 |

VS Code：侧边栏烧杯图标 → 顶部 ▶ 跑全部；列表不全时点 🔄 刷新。

配置在 `pyproject.toml` 的 `[tool.pytest.ini_options]`。
依赖：`pip install -e ".[test]"`（pytest、pytest-cov、plotly、kaleido）。
渲染测试（标记 `render`）还需要本机装有 Chrome；Qt 工具的测试需要另装 `".[gui]"`（PySide6），没装时自动跳过。

结果里如果出现 `x`，是标了 `xfail` 的「已知会失败」测试，不算失败（目前没有）。

## 文件与被测模块

| 测试文件 | 被测代码 | 一句话 |
|---|---|---|
| `conftest.py` | — | 共享的测试数据与环境（见下节），不含测试 |
| `test_dataloader.py` | `src/plotlib/dataloader.py` | 数据文件能正确读成 DataSet |
| `test_dataset.py` | `src/plotlib/dataset.py` | DataSet 的创建、拼接、列视图、遍历、重排 |
| `test_processor.py` | `src/plotlib/processor.py` 的 `DataProcessLayer` | `select` / `by` 按样品号、名字、单位、索引选列 |
| `test_transformer.py` | `src/plotlib/processor.py` 的 `DataTransformer` | `apply` / `Norm` 的计算结果与自动命名 |
| `test_group.py` | `src/plotlib/group.py` 的 `Group` | `num` 各种写法的格式化；创建时校验、读接口返回副本、增删改先校验再修改 |
| `test_group_apply.py` | `src/plotlib/group.py` 的 `Group` | 分组计算结果、命名、结果样品号正确 |
| `test_plot_common.py` | `src/plotlib/plot_common.py` | 两个绘图器共用的函数：样品号 → 色带位置；分组参数检查 `resolve_groups`；共用取数 |
| `test_plot_plan.py` | `src/plotlib/plot_common.py` 的 `plan_figures` | 分组绘图计划：不分组 / 分离 / 合并各画几张图、哪些线、归哪个分组、色带位置、样式；不开图窗 |
| `test_style.py` | `src/plotlib/style.py` | 样式标准写法（线型、标记、颜色）的校验，以及到 matplotlib / Plotly 的翻译 |
| `test_plotter.py` | `src/plotlib/plotter.py` | 四种绘图方法画出的线、标签、样式正确 |
| `test_formatters.py` | `src/plotlib/formatters.py` | 三种格式化器工厂设置的坐标轴、线条、图例属性（matplotlib 与 Plotly） |
| `test_interactive.py` | `src/plotlib/interactive.py` | Plotly 曲线的数据与标签、滑块档位（single / cumulative）与默认外观、报错 |
| `test_plotly_groups.py` | `src/plotlib/interactive.py` 的按计划绘图 | Plotly 按绘图计划画：不分组与计划一致；分组（合并模式）与 matplotlib 对照、组首色、分组样式翻译 |
| `test_html_export.py` | `src/plotlib/html_export.py` | 导出页面的画框尺寸、侧边面板位置、占位符全部填写、不修改 Figure |
| `test_data_reorder_app.py` | `tools/data_reorder_app.py`（Tk 版） | 直接改序号插入并保留勾选、非法输入不移动、取消与失焦；没有显示环境时跳过 |
| `test_data_reorder_qt.py` | `tools/data_reorder_qt.py`（Qt 版） | 插入与勾选保留、中点吸附、改序号、鼠标拖动；没装 PySide6 时跳过 |
| `test_groups_code.py` | 两个重排工具生成的 groups 代码 | 生成的代码能执行且被 `Group` 接受；线型是标准写法（前 4 组 solid / dash / dashdot / dot，之后自定义虚线）；两个工具的序数词组名一致（1st、2nd、11th、21st…） |

## 测试数据与环境（conftest.py）

测试**不使用真实实验数据**，而是在临时目录里现场生成一个和 `tools/` 输出同格式的小文件，
再用真实的 `Dataloader` 读进来。

| 名称 | 类型 | 提供什么 |
|---|---|---|
| `eis_dataset` | fixture | 3 个样品 × 3 行 EIS 数据（见下表）；**S1 = S0×2，S2 = S0×3**，期望结果可心算 |
| `sparse_dataset` | fixture | 样品号不连续（0、5、9）的数据集，每个样品 2 个通道；测试配色用 |
| `make_dataset(units, groups, fmt)` | fixture（工厂） | 按需造任意列数、任意格式（`csv`/`xlsx`/`txt`）的数据集 |
| `write_grouped_file` / `load_file` | 普通函数 | 写文件 / 读文件，需要单独控制文件时用 |
| `close_figures` | 自动 fixture | 每个测试后关闭所有图窗 |
| — | 全局设置 | matplotlib 切到 `Agg` 后端，不弹窗口 |

`eis_dataset` 的 9 列：

| 列号 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|---|
| 样品 | S0 | S0 | S0 | S1 | S1 | S1 | S2 | S2 | S2 |
| 单位 | Freq | Zs' | Zs'' | Freq | Zs' | Zs'' | Freq | Zs' | Zs'' |

频率都是 1 / 10 / 100；S0 的 Zs' = 10 / 20 / 30，Zs'' = −1 / −2 / −3。

## 测试清单（测试保证的行为）

### 数据加载 — `test_dataloader.py`
- 每列的样品名、单位、样品号、通道号按「样品 × 通道」正确展开；标识列和单位行不进入数值矩阵
- 每个样品 6 / 8 / 10 列（piezo / eis_nyquist / eis_bode）都能读
- **csv、xlsx、txt 三种格式读出完全相同的结果**
- 空单元格读成 NaN，不影响其他数值
- txt 中多个空格、制表符混用都当作一个分隔符（pandas 3 兼容的回归测试）
- 列数不是每个样品列数的整数倍 → `ValueError`；不支持的扩展名 → `RuntimeError`
- 不给文件路径时走「选择文件」对话框（测试中用 `monkeypatch` 替换掉弹窗）

### 数据容器 — `test_dataset.py`
- `form_array`：自动补全样品号、通道号、father/initial 索引；标量和一维数组转成二维
- 未指定样品号（None）的列共用一个新样品（已有最大样品号 + 1），样品数与通道号与之一致
- 元数据长度与数据列数不一致 → `RuntimeError`
- `expandata`：横向拼接列和元数据；行数不同时短的一方补 NaN
- 同一通道在不同样品里单位不同 → `RuntimeError`
- `column[i]` 是视图：改名字、单位、数据都直接写回 DataSet；`to_dict()` 是副本
- 通过 `column[i].sample_idx` 改样品号：样品数、通道号随之更新；破坏单位约束时报错并回滚
- 字典式访问 `col['unit']`；未知键、只读键 → `KeyError`
- `column` 支持负索引、切片、迭代；越界 → `IndexError`
- `iter('samples' / 'units')` 按样品 / 按单位产出子数据集；不支持的方式 → `ValueError`
- `columns_to_dataset`：`extended=False` 生成新数据集并记住原位置，`True` 追加到自身
- `_rearrange_columns` 按「样品号 → 通道号」排序

### 选列 — `test_processor.py`
- `select('all')` 选全部列；`by('all')` 时 `initial_idx` 仍指向原始数据
- `select('samples', [1, 2])` 按样品号选；关键字必须完全一致，`'Samples'`、`'group'` 等其他写法按名字查找，找不到报错
- 名字/单位找不到 → `ValueError`（指出是哪个）；不支持的条件类型（如 float）→ `TypeError`
- 按样品名、按单位、按单个索引 / 索引列表 / 多个索引选列
- 多个条件依次累加；`extended=False` 只保留最后一个条件
- 元组表示嵌套条件
- 选出的数据是副本，修改不影响原数据
- `initial_idx` 记住在原始数据中的位置
- `by()` 在已选结果上再筛：`father_idx` 指上一层位置，`initial_idx` 仍指原始位置
- `'samples'` 后不是整数列表 → `ValueError`；跨样品选出单位错位的列 → `RuntimeError`
- 未先 `select` 就 `by` → `RuntimeError`；`getdata` 参数不全 → `ValueError`

### 变换 — `test_transformer.py`
- `apply`：结果数值正确；可传 `indicies`（int / list，支持负索引）、`column`，或都不传（全部列）
- func 即使原地修改收到的数组（`data *= 0`），原始数据也不变
- 跨样品、单位不同的多列结果归为同一样品，不报单位冲突
- 自动命名：一列 → 沿用原名；多列同名 → `Results_i_of_<名>`；否则名字拼接
- 自动单位：输入单位相同 → 沿用，否则 `unitless_i`
- `input_name` / `input_unit` / `naming_func` 可覆盖自动值（`naming_func` 返回 None 的字段保持自动）；`input_name` 传字符串时按列数重复
- 同一个 `DataTransformer` 多次调用：`extended=True` 累加，`False` 只留最后一次
- 不修改原始数据
- `Norm`：L1、L2 范数数值正确；可指定单位、样品号
- `new_sample=True`：新样品号 = 已有最大样品号 + 1，再次分配继续 + 1；样品号不连续（如 `[0, 3]`）也不撞号

### 分组 — `test_group.py`
全部通过 `Group` 测试；校验与格式化的内部函数 `_check_group` / `_resolve_num` 不直接测。

**`num` 的写法与格式化**
- `num` 写成 list / tuple / int / range / numpy 整数 / ndarray 都格式化为 `list[int]`，元素是 Python `int`
- 样品号 `0` 是合法值（不会被当成「空」跳过）
- 缺 `num` 或 `num` 为空 → `ValueError`；类型不对（str、None、float…）→ `TypeError`
- 容器里的元素不是整数（`[1.9]`、`['2']`、浮点 ndarray）→ `TypeError`，不会被悄悄截断
- 原地格式化只改 `num`，其余字段原样保留（样式字段只校验、不改写，RGB 元组不会被改成色号）

**样式字段（`linestyle` / `marker` / `color`）**
- 只收标准写法（见 `test_style.py`）：后端写法 `'--'`、`'o'`、`'tab:red'`、matplotlib 原生元组 `(0, (3, 5))` 等在创建时就报错，信息含分组名和写错的值
- `linestyle(name)` / `marker(name)` / `color(name)` 按原样返回写的值，没写返回 `None`；`options(name)` 仍包含这三项
- 自定义虚线 `(3, 5)` 原样保存；`set` 时样式不合法也是先校验、不改动

**`Group` 的校验与接口**
- 只接受完整写法 `{分组名: {'num': [...], 其余字段}}`；简写 `{'A': [0, 1]}` → `TypeError`，提示正确写法
- 样品号重复 → `ValueError`；样品号不在数据集里 → `ValueError`，信息含分组名、全部不存在的样品号、已有样品号
- 各种配置错误（缺 num、为空、类型、简写、重复、样品不存在、样式不是标准写法）的报错信息都带出错的分组名
- 读接口：`names` / `for name in group` 保持书写顺序；`sample_ids(name)` 保持书写顺序；`options(name)` 是 `num` 以外的全部字段；
  都返回副本，改返回值不影响 `Group`；`to_config()` 返回当前配置的新字典；查询不存在的分组 → `ValueError`
- 传入的配置：每个分组的 `num` 被原地格式化为 `list[int]`（设计决定）；增删改不往原字典里加、删分组
- `add` 只新增（已存在报错）、`set` 整体替换已有分组且位置不变（不存在报错）、`delete` 删除（不存在报错）；都返回 `self`
- 修改先校验全部再生效：任何一个分组不合法，`Group` 保持原样

### 分组计算 — `test_group_apply.py`
- 两个样品相减、相除结果正确
- 配置里有几个分组，结果就有几个样品，样品号从 0 依次编号
- 未提供 `naming` 时自动命名为 `组名_函数名`（如 `'diff_subtract'`，多个分组各用自己的组名）；提供时使用自定义名字和单位（含频率透传列、结果列多于输入列）
- callback 返回一维数组 / 标量时自动转成列 / 1×1
- 不修改原始数据集
- 配置引用了不存在的样品号 → 创建 `Group` 时就报错（不等到 `apply`）；各样品列数不同 → 报错（`列数不一致`）

### 绘图公共函数 — `test_plot_common.py`
- `color_positions`：去重、排序后，位置 = 排名 ÷ 样品数。`[0, 5, 9]` 与 `[0, 1, 2]` 得到相同的 0、1/3、2/3；
  乱序、重复不影响结果；单个样品为 0；空输入得到空字典
- 样品号连续时与旧公式「样品号 ÷ 样品数」结果相同，已有图的颜色不变
- `resolve_groups`：合法的 `Group` 原样返回，不复制（三种情况的报错由两个绘图器各自的测试覆盖）
- `get_column_data`：按样品号 + 通道号取一列，返回数据、列名（样品名）、单位；`plotrange` 只取前几行；样品号或通道号不存在 → `RuntimeError`（`未找到对应的列数据`）
- `get_xy_data`：`neglog_y` 只对 Y 取绝对值，X 不变；返回 X、Y 各自的列名和单位

### 绘图计划 — `test_plot_plan.py`
- 不分组：一张 `'main'` 图，全部样品按样品号排序，色带位置 0、1/3、2/3，没有分组名和样式
- 分离模式：每个分组一张图（key 为分组名），同一样品可出现在两张图里，颜色按样品，样式只属于写了它的分组
- 合并模式：同一样品只画一次、归第一个包含它的分组（先到先得）；书写顺序即优先级（B 写在前面，重叠样品就归 B）；同组用组首色——组首按本组配置，即使组首样品已归别的组
- 曲线的数据、标签、单位与 `get_xy_data` 一致，`plotrange`、`neglog` 照样传下去；分组样式按标准写法原样带入，不翻译

### 样式标准写法 — `test_style.py`
- 合法：线型 `'solid'` / `'dash'` / `'dot'` / `'dashdot'` 与自定义虚线 `(3, 5)`、`[3, 5]`；7 个标记名；
  颜色为 CSS 颜色名（不区分大小写）、`'#rrggbb'`（大小写都行）、RGB 三个 0~255 的整数
- 非法：后端写法（`'--'`、`'dashed'`、`'o'`、`'tab:red'`、`'r'`、`'C0'`）、未知名字、三位色号 → `ValueError`；
  类型不对、自定义虚线元素不是数字（含旧写法 `(0, (3, 5))`）、RGB 元素不是整数 → `TypeError`；
  虚线段数为奇数或为空、段长 ≤ 0、RGB 不是三个或超出 0~255 → `ValueError`。线型的报错信息列出可用的标准词
- 翻译：四种线型、七种标记到两个后端的原生值；自定义虚线到 matplotlib 补偏移量 `(0, (3, 5))`、到 Plotly 按线宽换算像素 `'9px,15px'`；
  颜色名和色号原样，RGB 到 matplotlib 为 0~1、到 Plotly 为 `'rgb(255,0,0)'`
- 翻译前先校验（非标准写法不能绕过）；未知 backend → `ValueError`

### 绘图 — `test_plotter.py`
**`plot_objects`**
- 每个样品一条线，全部在一张图上，线上数值等于数据集对应列
- X/Y 轴标题是单位，图例是样品名
- `plotrange` 限制绘制点数
- `NegLogScale_x` / `NegLogScale_y`：数据取绝对值，刻度文字带负号；两轴同时启用时各保留自己的格式
- `plot_kind` 为 line / scatter / bar 时生成对应类型的对象，且点 / 柱的数据正确；不支持的类型报错
- 通道号超出每个样品的通道数 → `RuntimeError`
- `axes_formatter` / `lines_formatter` / `legend_formatter` 都会被调用，拿到正确的对象
- `lines_formatter` 改线型后，图例同步更新
- `figsize`：不传时 `plot_objects` 为 (10, 8)、`group_plotter` 为 (16, 12)；传了则所有绘图方法都用它

**分组参数 `groups`**
- 只接受 `Group` 对象：传字典 → `TypeError`，提示先用 `Group(dataset, config)` 创建
- `Group` 必须建在绘图器的同一个数据集上（`is` 判断），否则 → `ValueError`
- 不传时是空 `Group`
- 配置校验在创建 `Group` 时完成（见 `test_group.py`），绘图器里不再解析配置，也就不会因配置有误留下残缺图窗

**`group_plotter`**
- 分离模式：每个分组一张图，`artists` 以样品号为键
- 分组写了线型就应用（`apply_group_linestyle` 开关已删除），`'dash'` / `'dot'` 翻译成 `'--'` / `':'`
- 分组没写线型时用 `plot_style`（两种模式都是；合并模式以前写死 `'-'`）；`plot_style` 默认 `'solid'`，只收标准写法
- 分组写了 marker 就应用（`'circle'` → `'o'`），没写的分组不加标记
- 分组写了 color（RGB 或色号）时这组所有样品都用它；没写时分离模式按样品配色、合并模式用组首色
- 优先级：`lines_formatter` 最后执行，能覆盖分组线型
- 合并模式：只有一张图；被多个组共用的样品只画一次，沿用第一个组的线型和颜色；同组统一颜色
- 绘图不修改分组：画图前后 `groups.to_config()` 不变
- 没有分组时退回 `plot_objects`
- 两个方法都先生成绘图计划（`plan_figures`，见 `test_plot_plan.py`）再按计划画；分组规则只在计划里

**配色（样品号不连续）**
- 样品号 0、5、9：`plot_objects` 的三条线依次取 plasma 色带 0、1/3、2/3 处的颜色（回归：5、9 曾被截断成同一个末端色）
- `group_plotter`：排名基于整个数据集；分离模式各样品各自取色，合并模式统一为组首样品的颜色
- 柱状图同一规则：合并模式同组的柱子统一为组首色（步骤 6.2 起；以前 `BarContainer` 没有 `set_color`，各用各的样品色）

**`subplotter_yy` / `subplotter_xyy`**
- 每个样品一张图，以样品号为键
- yy：X/Y 数据与轴标题对应所选两列（如 Nyquist 图）
- xyy：左右两侧各用自己的 X、Y 列；左轴红、右轴蓝，两轴共享 X 轴，`twinx` 不新开图窗；`custom_formatter` 每个样品调用一次

### 格式化器 — `test_formatters.py`
**matplotlib（默认 backend）**
- axes：默认线性刻度、隐藏上/右边框；不传 `x_format` / `y_format` 时保留 matplotlib 默认的刻度格式器
- axes：可设对数刻度、坐标范围、刻度格式与换算倍数（`xscaler`）；只给 `xscaler` 不给格式时按 `{x:g}` 显示换算后的值
- axes：`custom_formation` 里的函数以 `(ax, fig)` 调用；可直接交给 `DataPlotter` 使用
- lines：线宽、颜色、线型、marker 与大小（标准写法，翻译成 matplotlib 原生值；RGB 换成 0~1）；不传 marker 时保持无标记；`custom_formations` 逐条线调用
- lines：后端写法（`'--'`、`'o'`、`'tab:red'`）在创建 formatter 时就报错，两个 backend 一样
- legend：字号、边框、可拖拽、位置；可直接交给 `DataPlotter` 使用

**Plotly（`backend="plotly"`）**
- 不传刻度格式时不写 `tickformat`（保留 Plotly 自动格式）；传入时翻译成 d3 格式（如 `'{x:.1e}'` → `.1e`）
- 坐标轴边界：两侧都给时固定 `range`；只给一侧时用 `autorangeoptions.minallowed` / `maxallowed`，另一侧自动；对数轴边界取 log10；只影响设置了边界的那根轴
- 渲染测试（标记 `render`）：用 kaleido 调真实的 Plotly.js，断言实际画出的坐标范围。
  回归：只给一侧边界时曾用 `autorange="min"/"max"`，模板开了 automargin，扩边重绘后被重置成完全自动，边界失效
- lines：标准写法翻译成 Plotly 的 `line.dash` / `marker.symbol` / `line.color`；自定义虚线按 `linewidth` 换算像素
- `combine_formatters`：按传入顺序调用，跳过 `None`

### 交互绘图 — `test_interactive.py`
- 分组参数与 `DataPlotter` 相同：传字典 → `TypeError`（提示用 `Group`）；基于别的数据集的 `Group` → `ValueError`；不传时是建在本数据集上的空 `Group`
- 每个样品一条曲线，X/Y 数据等于数据集对应列，曲线名是样品名，坐标轴标题是单位
- 样品号 0、5、9：曲线颜色取 Plasma 色带 0、1/3、2/3 处，与 matplotlib 同一套位置（回归：曾在样品 5 处 `IndexError`）
- 重复调用 `plot_plotly_object` 生成新的 Figure，`plot_artists` 与 Figure 中的 trace 一一对应
- 模板默认关闭对数轴 10ⁿ 之间的小号数字标签（`minorloglabels="none"`）
- 滑块：`single` 每档只显示当前曲线，`cumulative` 显示第一条到当前一条；初始可见性与第 0 档一致；档位标签和标题都是样品名；重复添加只保留一个滑块
- 滑块默认外观：初始标题为第 0 档的名字；短标签可见，名称太长（如 33 条 `Mg10-back-1mm-relax-i`）时隐藏刻度标签、保留当前值文字；`slider_formatter` 可覆盖默认值
- 报错：未绘图就加滑块、图中没有曲线 → `RuntimeError`；`mode` 写错 → `ValueError`，且不改动已有的图；空数据集 → 明确的 `RuntimeError`

### Plotly 按计划画 — `test_plotly_groups.py`
- `plot_plotly_object`：每条 trace 与不分组计划的曲线一一对应（顺序、名字、数据）
- `plot_plotly_group`（合并模式）：**同一个 `Group`** 交给 `DataPlotter.group_plotter(merge_groups=True)`，曲线条数、顺序、标签、数据一致；重叠样品只画一次
- 组首色：样品 0、1 归 A（位置 0），样品 2 归 B、用 B 的组首样品 1 的位置 1/3
- 分组样式翻译到 trace：`'dash'` → `line.dash`；`(3, 5)` → `'9px,15px'`（按线宽 3 换算）；`'square'` → `marker.symbol`，`mode` 变为 `'lines+markers'`；
  RGB → `'rgb(255,0,0)'`；不写样式 → `mode` 保持 `'lines'`；写了 marker 时点色等于线色
- 空分组：`plot_plotly_group` 与 `plot_plotly_object` 画出相同的曲线；`figure_formatter` 调用一次，收到的就是 `self.asset`

### HTML 导出 — `test_html_export.py`
- 图的尺寸先取 layout、再取模板，layout 优先；两处都没有固定宽高 → `ValueError`
- 无侧边面板：画框尺寸等于图的尺寸；页面不出现滚动条；Plotly 的 `responsive` 默认关闭，图只由外壳整体缩放
- 有侧边面板：画框宽 = 图宽 + 间距 + 面板宽；面板位于图之后、画框之内；网页标题经过 HTML 转义
- 模板占位符全部填写，不残留 `$...`；用户传入的 `config` 会合并进去，且保留 `responsive: false`
- 写文件不修改传入的 Figure；与 `InteractivePlotter` 的默认模板配合时画框为 1524 × 800

## 已修复的 bug

下面的问题都按「先写 `xfail(strict=True)` 测试复现 → 修代码 → 测试 XPASS → 删标记」的流程修复，
对应测试现在是回归测试，测试 docstring 里以「回归：」开头说明了原来的问题。

| 位置 | 原来的问题 | 修法 |
|---|---|---|
| `dataloader.py` 读 txt | pandas 3 删除了 `delim_whitespace`，txt 读不了 | 改用 `sep=r'\s+'` |
| `processor.select('all')` | 必定报「数据选择未执行」 | 改走 `getdata`，与其他条件同一路径 |
| `processor.select` 名字拼错 | 静默忽略；跟在有效条件后会把上一结果再追加一遍 | 找不到报 `ValueError`，不支持的类型报 `TypeError` |
| `DataTransformer` 取列 | func 原地修改会改掉原始数据；`indicies=-1` 得到空列 | int 也走花式索引（副本、支持负数），全部列时 `.copy()` |
| `DataTransformer` 新样品号 | 按「样品数 + 1」算，样品号不连续时撞号 | 「已有最大样品号 + 1」，每次分配后 + 1 |
| `DataTransformer` `input_name` | 字符串被拆成单个字符 | 字符串按列数重复，与 `input_unit` 一致 |
| `DataSet.update_attributes` | `None` 样品号先统计后补全，元数据自相矛盾 | 先补全再统计；同一批 `None` 共用一个新样品 |
| `Column.sample_idx` 赋值 | 样品数、通道号不更新 | 赋值后重算并校验，失败则回滚 |
| `Group.apply` | 结果列多于输入列时，提供 `naming` 仍 `IndexError` | 提供 `naming` 时不再调用自动命名 |
| `plotter` 负对数 | 两轴同时启用时 X 轴用了 Y 轴格式（闭包晚绑定） | 两轴用各自的变量 |
| 分组 `num` 解析（原 `resolve_num`，现为 `Group` 的创建时校验） | `[1.9]` 被截成 `[1]` | 元素必须是整数，否则 `TypeError` |
| `make_lines_formatter` | 不传 marker 就崩（`set_marker(None)`） | 只在指定 marker 时设置 |
| `make_legend_formatter` | 一调用就崩（`set_fontsize`、`set_frameon` 都不存在） | 逐个设置图例文字字号；改用 `set_frame_on` |

**项目配置**：`pyproject.toml` 的 `requires-python` 已从 `>=3.8` 改为 `>=3.14`
（`match` 语法需 3.10+；类内不加引号的自引用类型标注在 3.14 之前导入即报错）。

仍**待确认**（行为可能是有意的，未改）：
- `num=True` 被当成样品号 1（`bool` 是 `int` 的子类）。
- `column[i].unit = ...` 改单位时不校验「同通道同单位」约束（样品号的 setter 会校验）。
- `formatters.py` 模块文档示例写 `lambda ax: ...`，代码实际以 `(ax, fig)` 调用 `custom_formation`；
  `by()` 文档说「不能连续使用」，代码并未禁止。

## 未覆盖的部分

覆盖率报告中剩下没测到的行：
- `dataloader.py` 的文件对话框本身（需要真实 GUI）
- 各处「理论上走不到」的防御性检查、`__repr__`
- `tools/`（data_reorder 两个工具除外）、`learning/gui/`、`scripts/`：界面和脚本，不做自动化测试，仍靠手动运行检查

## 新增测试时的约定

1. **文件**：测 `src/plotlib/xxx.py` 就写在 `tests/test_xxx.py`；测试函数以 `test_` 开头。
2. **命名**：测试名写成「行为」，如 `test_group_config_is_not_modified`，让 `pytest -v` 的输出本身就是一份清单；docstring 写一句「为什么要测」。
3. **数据**：用 `eis_dataset` 或 `make_dataset` 造小数据，数值设计成能心算；不要读真实数据文件。
4. **多组输入**用 `@pytest.mark.parametrize`，并加 `ids` 让输出可读。
5. **报错**用 `pytest.raises(..., match=...)`，一个 `with` 只包一次调用。
6. **绘图**检查 `axesset` 里对象的属性（数据、线型、颜色、标签），不比对图片。
7. **弹窗、文件对话框**等交互用 `monkeypatch.setattr` 临时替换掉。
8. **修 bug**：先写一个会失败的测试复现它（标 `xfail(strict=True)`），修好后删掉标记，留作回归测试。
9. 新增或删除测试后，顺手更新本文件的「测试清单」和「已知 bug」。
