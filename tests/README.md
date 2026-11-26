# PlotLib 测试说明

这份文档告诉你**测试保证了什么**，不用逐行读测试代码。
想看某条行为具体怎么测的，再按测试名去对应文件里找。

当前状态：**621 个全部通过**（2026-11-26，含柱状图、散点映射和实验脚本的冒烟测试）。曾记录的 bug 已全部修复（见文末「已修复的 bug」）。

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
依赖：`pip install -e ".[test]"`（pytest、pytest-cov、plotly、scipy、kaleido）。
渲染测试（标记 `render`）还需要本机装有 Chrome；Qt 工具的测试需要另装 `".[gui]"`（PySide6），没装时自动跳过。

结果里如果出现 `x`，是标了 `xfail` 的「已知会失败」测试，不算失败（目前没有）。

## 文件与被测模块

| 测试文件 | 被测代码 | 一句话 |
|---|---|---|
| `conftest.py` | — | 共享的测试数据与环境（见下节），不含测试 |
| `test_dataloader.py` | `src/plotlib/dataloader.py` | 数据文件能正确读成 DataSet |
| `test_dataset.py` | `src/plotlib/dataset.py` | DataSet 的创建、拼接、列视图（改样品号、单位都校验并回滚）、遍历、重排；列位置索引 `column_positions` 与逐列扫描对拍；直接改列表后「使用时自动检查」（各入口、失败不留旧索引、没改不重查） |
| `test_processor.py` | `src/plotlib/processor.py` 的 `DataProcessLayer` | `select` / `by` 按样品号、名字、单位、索引选列 |
| `test_transformer.py` | `src/plotlib/processor.py` 的 `DataTransformer` | `apply` / `Norm` / `Reduce` 的计算结果与自动命名 |
| `test_group.py` | `src/plotlib/group.py` 的 `Group` | `num` 各种写法的格式化；创建时校验、读接口返回副本、增删改先校验再修改 |
| `test_group_apply.py` | `src/plotlib/group.py` 的 `Group` | 分组计算（`apply`、组内汇总 `reduce`）结果、命名、结果样品号正确 |
| `test_plan_helpers.py` | `src/plotlib/plan.py` 的公共函数 | 生成计划用的函数：样品号 → 色带位置；分组参数检查 `resolve_groups`；共用取数 |
| `test_plot_plan.py` | `src/plotlib/plan.py` 的 `plan_figures`、`plan_bars` | 绘图计划：`by` 三种分图（不分组 / 分离 / 合并各画几张图、哪些线、归哪个分组、色带位置、样式；每样品一张）、多个图层、双 Y 轴；图层面的单位、neglog、版式；入口校验；柱状图的「类别 × 系列」表、误差、样式；不开图窗 |
| `test_bars.py` | `DataPlotter.plot_bars` 与两个后端的柱状图 | 入口校验（含回调与画法不配、柱状图不接滑块）；matplotlib 的并排偏移、缺数据保留位置、堆叠底部、误差棒位置；Plotly 的 `barmode` 与 Kaleido 实际渲染（柱位置、缺误差的系列无端帽、图例纹理）；同名类别不合并；颜色、纹理、回调组合；Y 轴标题、图例；`artist(key)`、失败后的状态 |
| `test_scatter_map.py` | 散点第三通道映射（`ScatterMap`、`ColorbarStyle`）与两个后端 | 两个后端照计划着色（共用 norm / `coloraxis`、描边跟随、对数色标、等值取中间色、悬停标明列标题）和定大小；颜色条不压右轴和图例、也不浪费右边距，含 Plotly 图例回调、matplotlib 整图回调里 `tight_layout()`、放不下时绘图区宽度下限（matplotlib 量边界框，Plotly 用 Kaleido 渲染核对）；映射层上回调不能写颜色 / 大小；`axes['colorbar']`、分页共用颜色轴、全缺颜色的样品和空页仍有图例和颜色条、SVG / PDF 后端、失败后的状态 |
| `test_style.py` | `src/plotlib/style.py` | 样式标准写法（线型、标记、颜色）的校验，以及到 matplotlib / Plotly 的翻译 |
| `test_plotter.py` | `src/plotlib/plotter.py` | matplotlib 把计划画对（每张计划一张图、位置 → 颜色、样式翻译）；formatter、图例、`linestyle`、`figsize`、负对数刻度、x-y 单线图 / 双 Y 轴 |
| `test_formatters.py` | `src/plotlib/formatters.py` | 三种格式化器工厂设置的坐标轴、线条、图例属性（matplotlib 与 Plotly） |
| `test_plotly_backend.py` | `src/plotlib/backends/plotly_backend.py` | Plotly 后端把计划画对；排版预设、外观（按 dpi 换算）、双 Y 轴、回调、滑块 |
| `test_docs_sync.py` | `docs/api/sync_api.py` | API 文档同步：reference.rst 登记齐全；新名字放进同模块分节（导出的优先）或「其他」节；版本号来自 pyproject.toml |
| `test_backend_parity.py` | `DataPlotter` 换 `backend` 对照 | 两个后端的分组参数约定相同；同一个 `Group` 画出的图和曲线一致（五种画法） |
| `test_html_export.py` | `src/plotlib/html_export.py` | 导出页面的画框尺寸、侧边面板位置、占位符全部填写、不修改 Figure |
| `test_scripts.py` | `scripts/` 下的 6 个实验脚本 | 每个脚本用列标题相符的小数据跑完 `main(path, show=False)`，图的数量对、不关调用方的图窗；导入不画图；Bode 全部无峰时跳过峰图并提示，多峰时柱状图与汇总图用同一个峰；交互图脚本把页面写到指定位置 |
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
| `write_samples_file` / `load_file` | 普通函数 | 写文件 / 读文件，需要单独控制文件时用（步骤 7.1 起参数叫 `samples`、`columns_per_sample`） |
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
- 列数不是每个样品列数的整数倍 → `ValueError`；不支持的扩展名 → `ValueError`，信息里有文件名
- 每样品 49 列时两个样品都读到（样品数用整数除法）
- 不给文件路径时走「选择文件」对话框（测试中用 `monkeypatch` 替换掉弹窗）
- 接口（步骤 7.1）：`Dataloader(columns_per_sample=N).load_data(path)` 直接读；`columns_per_sample` 必填、不小于 2 的整数，旧参数名 `TypeError`；扩展名不区分大小写（`.CSV`、`.Xlsx`、`.TXT`）；不支持的扩展名报错里有文件名和支持的格式；文件不存在 `FileNotFoundError`
- 不传路径时弹窗：取消选择抛 `NoFileSelected`（不是 `OSError`，不再 `exit()`；替换 `tkinter.filedialog` 的属性模拟取消）；导入 `plotlib.dataloader` 不导入 tkinter（新进程里检查）
- 同一个加载器先后读两个文件各得各的数据，加载器上只有 `columns_per_sample`
- 三种格式的数字样品名都原样是文本：`'101'`、`'1.50'` 不变成 `101.0`、`1.5`，数据照常是数字（55576fb 复审 1）

### 数据容器 — `test_dataset.py`
- `form_array`：自动补全样品号、通道号、father/initial 索引；标量和一维数组转成二维
- 未指定样品号（None）的列共用一个新样品（已有最大样品号 + 1），样品数与通道号与之一致
- 元数据长度与数据列数不一致 → `RuntimeError`
- `expandata`：横向拼接列和元数据；行数不同时短的一方补 NaN；零行样品（有列、没有行）照常拼接；拼接失败后原对象不变、还能继续拼接
- 同一通道在不同样品里单位不同 → `RuntimeError`
- `column[i]` 是视图：改名字、单位、数据都直接写回 DataSet；`to_dict()` 是副本
- 通过 `column[i].sample_idx` 改样品号：样品数、通道号随之更新；破坏单位约束时报错并回滚
- 字典式访问 `col['unit']`；未知键、只读键 → `KeyError`
- `column` 支持负索引、切片、迭代；越界 → `IndexError`
- `iter('units')` 按单位产出子数据集；不支持的方式 → `ValueError`（按样品见下一条）
- 零行数据集（有列、没有行）：`column` 的长度是列数，照样能按列、按样品遍历（回归：曾按元素个数算成 0）
- `for sample in dataset`（步骤 7.2）：与 `iter('samples')` 相同，样品号不连续时保留原号；空数据集不执行；逐样品用 `DataTransformer.Norm` 计算再拼回，结果仍按原样品号对应
- `columns_to_dataset`：`extended=False` 生成新数据集并记住原位置，`True` 追加到自身
- `sort_columns`（步骤 7.3，原 `_rearrange_columns`）按「样品号 → 通道号」原地排序并返回自己

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

### 计划的公共函数 — `test_plan_helpers.py`
- `color_positions`：去重、排序后，位置 = 排名 ÷ 样品数。`[0, 5, 9]` 与 `[0, 1, 2]` 得到相同的 0、1/3、2/3；
  乱序、重复不影响结果；单个样品为 0；空输入得到空字典
- 样品号连续时与旧公式「样品号 ÷ 样品数」结果相同，已有图的颜色不变
- `resolve_groups`：合法的 `Group` 原样返回，不复制（三种情况的报错在 `test_backend_parity.py` 里对两个后端一起测）
- `get_column_data`：按样品号 + 通道号取一列，返回数据、列名（样品名）、单位；`plotrange` 只取前几行；样品号或通道号不存在 → `RuntimeError`（`未找到对应的列数据`）
- `get_xy_data`：`neglog_y` 只对 Y 取绝对值，X 不变；返回 X、Y 各自的列名和单位

### 绘图计划 — `test_plot_plan.py`
- 不分组：一张 `'main'` 图，全部样品按样品号排序，色带位置 0、1/3、2/3，没有分组名和样式
- 分离模式：每个分组一张图（key 为分组名），同一样品可出现在两张图里，颜色按样品，样式只属于写了它的分组
- 合并模式：同一样品只画一次、归第一个包含它的分组（先到先得）；书写顺序即优先级（B 写在前面，重叠样品就归 B）；同组用组首色——组首按本组配置，即使组首样品已归别的组
- 曲线的数据、标签、单位与 `get_xy_data` 一致，`plotrange`、`neglog` 照样传下去；分组样式按标准写法原样装进 `LineStyle`，不翻译（没写样式是 `LineStyle()`）
- 样品号 0、5、9：色带位置按整个数据集排名；分离模式各样品各自的位置（1/3、2/3），合并模式统一为组首位置 1/3（回归：组首色曾取 `cmap(5/3)` 被截断）
- 生成计划只读分组：前后 `groups.to_config()` 不变（后端不读 `Group`，所以只在这里测）
- 图层面的信息（6.4）：三种多线 / 分组计划的图都带 `x_unit`、`y_unit`（`y2_unit` 为 None）、`layout='multiline'`；线默认 `kind='line'`、`axis='left'`，曲线上不再有单位；`kind` 原样传到每条线，`neglog` 记在图上（如 `{'x'}`）
- `by='sample'`：每个样品一张图、一条线，key 是样品号，`layout='xy'`；色带位置为 `None`（用后端默认色）；`neglog_y` 时 Y 取绝对值、图上记 `{'y'}`
- 左右两个图层（双 Y 轴）：每个样品一张图、两条线；左线挂左轴（红）、右线挂右轴（蓝），色带位置为 `None`，两侧 `kind` 可不同；图的单位为左 X、左 Y、右 Y，`layout='dual_y'`；
  负对数按轴：共用 X 轴的负号只看左侧，右侧图层的 `neglog_x` 只把自己的 X 取绝对值；左右 Y 轴各看本侧；两条线的标签是各自的单位，图例标题是样品名（2026-11-20）
- 多个图层（4.8）：同一侧「散点 + 折线」每样品一张，曲线按「样品 → 图层」顺序，标签是单位、图例标题自动是样品名、`layout='xy'`
- 规则推导（4.8）：`all` / `group` / `sample` 单层和 `sample` 左右双层各自的版式、是否按色带取色、`legend_title='auto'` 的结果
- 入口校验（4.8）：空图层、只有右侧、`merge_groups` 配错 `by`、`by='group'` 没有分组、写错 `by` / `kind` / `side`、图层没写通道、
  `by='all'` / `'group'` 画多个图层、同一根轴上负对数写法不一致，都报 `ValueError`
- 每张图自己的名字 `FigureSpec.name`（6.8）：每样品一张时是样品名，分离模式是组名，只有一张图时 `None`
- 图例标题 `legend_title`：默认 `'auto'`，只有一个样品画多层时是样品名，否则不加；`'{name}'` 在每样品一张时换成样品名、分离模式换成组名，前后可加文字；
  只有一张图（不分组、合并）时自由文字照用，`'{name}'` 不替换也不报错（用户定：不给单图加限制）
- 柱状图 `plan_bars`（4.7，数据见 conftest 的 `bar_data`）：4 种「类别 × 系列」组合的类别、系列键（原通道号）、高度、配色位置；
  先截 `plotrange` 行再汇总；Y 轴标题三种情况；缺数据保留位置；分组配置与 `styles` 的优先级、样式在汇总前校验；
  误差：两种模式的 std / sem、误差通道按原行对齐（first / max / mean）、端帽标记、不可哈希的汇总对象、汇总后误差的校验、分组时每个样品只汇总一次
- 散点映射（4.5，数据见 conftest 的 `map_data`）：大小按面积线性换成直径（`[0, 5, 10]` → `[4, √136, 16]`）、整列相同取中间；
  一次绘图共用一个范围（含分组分图）；X、Y 非有限或映射值是 NaN 的点一起去掉，范围按画出的点算；`plotrange` 先截行；
  颜色条自动扩展前的端点量级超过 ±1e300 时报错，等值范围的线性和对数扩展无溢出警告，复数映射值会报错；
  颜色条的范围（只写一端时另一端自动、对数色标）、标题（默认列标题、`''` 不加）；颜色映射层不读分组 `color`、照读 `marker`；
  入口校验 19 种写错（折线写映射、`size_range`、无穷大、对数遇到不为正、色带词、`limits`、有 `colorbar` 没颜色映射、两个颜色映射层）

### 样式标准写法 — `test_style.py`
- 合法：线型 `'solid'` / `'dash'` / `'dot'` / `'dashdot'` 与自定义虚线 `(3, 5)`、`[3, 5]`；7 个标记名；
  颜色为 CSS 颜色名（不区分大小写）、`'#rrggbb'`（大小写都行）、RGB 三个 0~255 的整数
- 非法：后端写法（`'--'`、`'dashed'`、`'o'`、`'tab:red'`、`'r'`、`'C0'`）、未知名字、三位色号 → `ValueError`；
  类型不对、自定义虚线元素不是数字（含旧写法 `(0, (3, 5))`）、RGB 元素不是整数 → `TypeError`；
  虚线段数为奇数或为空、段长 ≤ 0、RGB 不是三个或超出 0~255 → `ValueError`。线型的报错信息列出可用的标准词
- 翻译：四种线型、七种标记到两个后端的原生值；自定义虚线到 matplotlib 补偏移量 `(0, (3, 5))`、到 Plotly 按线宽换算像素 `'9px,15px'`；
  颜色名和色号原样，RGB 到 matplotlib 为 0~1、到 Plotly 为 `'rgb(255,0,0)'`
- 翻译前先校验（非标准写法不能绕过）；未知 backend → `ValueError`
- 翻译层（6.7）：刻度格式 `'{x:.2f}'` → matplotlib 格式函数 / Plotly `'.2f'`（Plotly 对应不了的报错）；图例位置（含图外上方 `'outside top right'`）→ 两个后端的参数；磅、英寸按显式 dpi 换算（matplotlib 原样，Plotly：磅 × dpi / 72、英寸 × dpi）
- 刻度 `TickStyle`（2026-11-20）：默认 `DEFAULT_TICKS`（朝外、主 6 × 3、显示次刻度 3 × 3、次刻度不写文字），`Appearance().ticks` 是空的一层；`updated` 按层叠加（写了的覆盖）；
  翻译成 matplotlib 的主 / 次 `tick_params`、次刻度开关和文字写法（次刻度文字没单独写时同主刻度），翻译成 Plotly 的轴配置（磅 × dpi / 72，`minor.ticks` 关掉为 `''`，
  `minor_labels` → `minorloglabels`）；只出现写了的字段；Plotly 下单独设次刻度文字的字体 / 字号 / 间距 → `ValueError`；`'inout'`、未知写法、非正长度、非布尔开关 → 报错
- 样式对象化（2026-11-20）：库默认（线宽 3 实线、标记 6；**无框**、轴线宽 3；图例字号 10、无边框）；`Appearance()` 各样式是空的一层；
  叠加顺序 库默认 < 版式预设 < 全局（全局写了的图例位置盖过预设，没写的拖动仍用预设；双 Y 轴预设完整的框，全局 `top=False` 盖过它）；
  `LineStyle` → Line2D 属性 / Plotly 扁平写法（磅 → 像素，点跟着线色）；`AxisStyle` → 刻度类型、范围、格式函数（× scaler）、着色 / Plotly 轴配置，
  Plotly 的 `scaler`、`symlog` 报错，对数轴边界 ≤ 0 报错；`FrameStyle` → 线宽与上 / 右边；`LegendStyle` → 两个后端的图例参数，位置同一张表，写错报错
- 色带（4.5）：5 个标准词名 → matplotlib 原名 / Plotly 首字母大写；后端原生名、`'Greys'`、未知词报错并列出可选词

### 绘图 — `test_plotter.py`
分组规则不在这里测（见 `test_plot_plan.py`）；这里只测 matplotlib 把计划画对，以及它独有的功能。

绘图只有一个入口 `DataPlotter.plot`（4.8）：`by` 决定分图（`'all'` / `'group'` / `'sample'`），图层 `Layer` 决定画什么，
回调按轴打包成 `AxesFormatter`。

**`by='all'`**
- 每个样品一条线，全部在一张图上；X/Y 轴标题是单位，图例是样品名
- `plotrange` 限制绘制点数
- `Layer(neglog_x=…, neglog_y=…)`：数据取绝对值，刻度文字带负号；两轴同时启用时各保留自己的格式；
  **渲染后**默认刻度格式也是「一个负号 + 数字」（每样品一张的 X、双 Y 轴的左 Y；双 Y 轴共用的 X 轴只加一次负号）
- 图层 `kind='line'` / `'scatter'` 生成对应类型的对象（`Line2D` / `PathCollection`），且数据正确；
  散点与折线共用分组规则（不分组、分离、合并），两个后端一致；双 Y 轴两侧可以分别是折线、散点
- 线条回调只改折线、散点回调只改散点（`make_lines_formatter` / `make_scatter_formatter`，两个后端都验证）
- `AxesFormatter` 的 `axes` / `lines` / `legend` 都会被调用，拿到正确的对象
- 线条回调改线型后，图例同步更新；**渲染后**图例位置和能否拖动不变（图外右侧、图内右下两种）
- `figsize`：不传时按 `by`：`'all'` (10, 8)、`'group'` (16, 12)、`'sample'` (12, 8)；传了都用它

**`by='group'`**
- 计划里每张 `FigureSpec` 画成一张图：分离模式 `figures` 的键是 `'A'`、`'B'`，合并模式是 `'main'`；每张图的线与计划的曲线一一对应
- 分组样式翻译成 matplotlib 原生值：`'dash'` → `'--'`、`'circle'` → `'o'`、RGB 和色号 → 对应颜色；没写样式时实线、无标记
- 分组没写线型时用全局的 `lines=LineStyle(linestyle=...)`（经 `rc_context` 生效）；默认实线、线宽 3，只收标准写法；`lines` 不收颜色
- 优先级：线条回调最后执行，能覆盖分组线型
- 没有分组时报错（原 `plot_groups` 会退回画全部样品，4.8 起 `by='group'` 是明确的意思）

**结果形状（6.5）**
- 各种 `by` 的结果都是 `figures = {计划的 key: DrawnFigure}`：`spec`、`fig`、`axes`（单轴 `{'left'}`，双 Y 轴 `{'left', 'right'}`）、`artists`（与 `spec.curves` 一一对应）
- 按样品号取线：`figures['B'].artist(1)`；双 Y 轴 `artist(0, 'right')` 是蓝色；取不存在的样品 → `KeyError`
- 颜色一次赋值：分组写的 `color` 对散点图、柱状图也生效（以前只对折线）

**matplotlib 后端（6.6）**
- 后端只读计划：手工写一张 `FigureSpec`（不经过数据集、分组）交给 `MatplotlibBackend.draw`，画出的数据、标签、颜色、轴标题、尺寸就是计划写的
- `backend` 参数：默认 `'matplotlib'`；`'plotly'` → `NotImplementedError`（6.7）；写错 → `ValueError` 并列出可选值
- 外观（`Appearance`，后端无关）由后端翻译成 `rc_params`：`font_size=30` → `font.size`，`LineStyle(linestyle='dash')` → `'--'`；
  样式对象按「库默认 < 用户写的那一层」叠加（只写线型时线宽仍是 3），边框宽、图例字号（含标题）也进 rc

**默认排版（6.6b 起由 `layouts.py` 的排版预设决定）**
- 图例：多线图在图外右侧、可拖动；xy 在右下角；一张图只有一个图例，建在左轴上
- 双 Y 轴图例（2026-11-20，参照 Origin 图，**渲染后**断言）：左右两条线都在（红、蓝），写各自的单位，标题是样品名；
  在绘图区上方、右边对齐、不超出画布；右轴 `lines_formatter` 改色后图例跟着变，左轴 `legend_formatter` 设的字号和标题不被重建冲掉
- 刻度格式：多线图 y 两位小数（x 不写格式，常改成对数轴）；xy 的 y、双 Y 轴的右轴四位小数
- 边距：多线图左 0.18、右 0.75，xy 左 0.18，双 Y 轴右 0.85、上 0.85（给图例让位）
- 默认字号下 Y 刻度文字是 `8000.00`、`8000.0000`、`-800.00` 时，渲染后多线图和 xy 的 Y 轴标题不被左边裁掉
- 双 Y 轴：左轴（标题、刻度文字、轴线）和左线红，右轴和右线蓝（计划里不写颜色，由预设给）
- 边框（样式对象化，2026-11-20）：多线、xy 默认无框；双 Y 轴完整的框，右边是右轴自己的蓝色轴线，右轴的左边不画（不盖住左轴的红线）
- 全局样式盖过预设：`DataPlotter(frame=FrameStyle(top=True), legend=LegendStyle(position='upper left'))` 照全局画，没写的（拖动）仍用预设
- 轴工厂只改写了的：只把 X 轴改成对数，Y 轴仍是预设的两位小数（回归：曾总调用 `set_yscale` 冲掉预设格式）

**刻度 TickStyle（2026-11-20，渲染后断言）**
- 默认主刻度 6 × 3 磅、线性轴也有次刻度、次刻度不写文字；`DataPlotter(ticks=...)` 只写要改的，其余沿用默认（长 10、宽仍 3；文字 12 磅 serif）
- 关掉次刻度后，轴工厂把 X 轴改成对数也不冒出次刻度（改刻度类型会重置次刻度，后端在回调之后只补还是默认值的）
- 对数轴次刻度文字：`none` 不写、`short` 只写 2 ~ 9、`full` 每个都写；线性轴 `full` 也能写且可单独设字号，`short` 不写

**配色**
- 柱状图也按计划的位置上色：合并模式同组的柱子统一为组首色（步骤 6.2 起；以前 `BarContainer` 没有 `set_color`，各用各的样品色）

**`by='sample'`（原 `plot_xy` / `subplotter_yy`）和左右两个图层（原 `plot_dual_y`）**（都按计划画）
- 每个样品一张图，以样品号为键
- 一个图层：X/Y 数据与轴标题对应所选两列（如 Nyquist 图）；线仍是 matplotlib 默认色 `#1f77b4`（不按样品换色）
- 左右两个图层：两侧各用自己的 X、Y 列；左轴红、右轴蓝，两轴共享 X 轴，`twinx` 不新开图窗；整图回调 `figure_formatter(fig, axes)` 每个样品调用一次
- 多个图层（`test_backend_parity.py`，两个后端）：每页 `artists` 的顺序与 `layers` 一致，`artist(样品号, 轴)` 是这根轴上的第一层；
  线条、散点回调只收到对应轴、对应画法的对象；右侧坐标轴回调改 X 也作用在共用的 X 轴上

### 格式化器 — `test_formatters.py`
样式对象化（2026-11-20）起参数都是样式对象：`make_axes_formatter(x=AxisStyle, y=AxisStyle, frame=FrameStyle, ticks=TickStyle, custom=)`、
`make_lines_formatter(LineStyle, custom=)`、`make_legend_formatter(LegendStyle, custom=)`；没写的字段不改。

**matplotlib（默认 backend）**
- axes：什么都不给就什么都不改——刻度类型、已有的刻度格式（如预设的两位小数）、边框保持原样
  （回归：以前刻度类型默认 `'linear'` 且总调用 `set_*scale`，会重置已有格式；边框默认隐藏上 / 右边）
- axes：可设对数刻度、坐标范围、刻度格式与换算倍数（`AxisStyle.scaler`）；只给 `scaler` 不给格式时按 `{x:g}` 显示换算后的值
- axes：`frame=FrameStyle(...)` 只改写了的（上边、线宽）；`custom` 里的函数以 `(ax, fig)` 调用；可直接交给 `DataPlotter` 使用
- lines：线宽、颜色、线型、marker 与大小（标准写法，翻译成 matplotlib 原生值；RGB 换成 0~1）；没写 marker 时保持无标记；`custom` 逐条线调用
- lines：后端写法（`'--'`、`'o'`、`'tab:red'`）在创建 formatter 时就报错，两个 backend 一样
- legend：字号、边框、可拖拽、位置（与预设同一张位置表）；可直接交给 `DataPlotter` 使用

**Plotly（`backend="plotly"`）**
- 不传刻度格式时不写 `tickformat`（保留 Plotly 自动格式）；传入时翻译成 d3 格式（如 `'{x:.1e}'` → `.1e`）
- 坐标轴边界：两侧都给时固定 `range`；只给一侧时用 `autorangeoptions.minallowed` / `maxallowed`，另一侧自动；对数轴边界取 log10；只影响设置了边界的那根轴（没写的轴根本不写）
- 渲染测试（标记 `render`）：用 kaleido 调真实的 Plotly.js，断言实际画出的坐标范围。
  回归：只给一侧边界时曾用 `autorange="min"/"max"`，模板开了 automargin，扩边重绘后被重置成完全自动，边界失效
- `limits` 永远写数据值：刻度类型和范围分两个回调设、先设哪个、改回线性，两侧和单侧边界结果都一样；分步时对数轴边界 ≤ 0 在应用时报错；
  渲染测试断言分步设置后实际范围就是写的数据值（55576fb 复审 3）
- 三种回调与 matplotlib 形状对应：axes `(轴名, fig)`，Y 轴设置只写到这根轴、X 轴写到共用的 `xaxis`，`custom` 也收 `(轴名, fig)`；
  lines 收 trace 列表；legend 收 `[fig.layout.legend]`
- lines：标准写法翻译成 Plotly 的 `line.dash` / `marker.symbol` / `line.color`；线宽是磅、按 dpi 换成像素，自定义虚线按换算后的线宽算像素；
  颜色点也一起改（回归：纯散点曾只改了隐藏的线色）
- legend：字号是磅、按 dpi 换成像素；图内位置离边 0.02；`draggable=True` → 创建时报错并提示在显示时设置
- `combine_formatters`：按传入顺序调用、跳过 `None`、参数原样转交（两个后端通用，只合并同一种回调）

### Plotly 后端 — `test_plotly_backend.py`
分组规则不在这里测（见 `test_plot_plan.py`）；翻译（字号、尺寸、图例位置、刻度格式）在 `test_style.py`。这里只测 Plotly 把计划画对、把排版预设和外观应用上。

**按计划画**
- 后端只读计划：手工写一张 `FigureSpec` 交给 `PlotlyBackend.draw`，trace 的数据、名字、颜色、轴标题，以及图尺寸（figsize × dpi）就是计划写的；`axes` 是 `{'left': 'yaxis'}`
- 每条 trace 与不分组计划的曲线一一对应；重复调用生成新的 Figure
- 合并模式用组首色
- 分组样式翻译到 trace：`'dash'` → `line.dash`；`(3, 5)` 按线宽（3 磅 → 像素）换算成像素；`'square'` → `marker.symbol` 且 `mode` 变 `'lines+markers'`；RGB → `'rgb(255,0,0)'`；写了 marker 时点色等于线色
- 散点、柱状图也按计划上色（`go.Bar` 只写 marker 颜色）
- 空数据集 → 明确的 `RuntimeError`（`数据集为空`）

**排版与外观**
- 双 Y 轴：右轴 `yaxis2` 叠在左轴上、放在右侧，按自己的数据选刻度（`tickmode='auto'`，Plotly 默认 `'sync'` 对齐左轴会让刻度值不整齐），
  右线 `yaxis='y2'`；左红右蓝（线和轴标题）；右轴四位小数；
- 边框：多线图默认不镜像；双 Y 轴上边是 X 轴镜像、左 Y 轴不镜像（右边是右轴的线）；全局 `frame` 盖过预设
- 全局线宽、图例字号（磅 → 像素）写进模板 / 图例；全局图例位置盖过预设
  图例（2026-11-20）两条线都在、trace 名是单位、标题是样品名，图外上方右对齐
- 排版预设：多线图图例在图外右侧、纵轴两位小数（横轴不写格式）；xy 纵轴四位小数、图例在右下角
- 对数轴写了刻度格式（Plotly 下 `minorloglabels` 失效）：次刻度不写文字时补 `dtick=1`，主刻度只在整数量级；自己设了 `dtick` 不动；`'full'` 不改；`'short'` 报错；线性轴、不写格式的对数轴不改
- 外观按显式 dpi 换成像素：字号 22 磅 → 22 × 100 / 72 像素；dpi 加倍像素也加倍；模板关闭对数轴的小号次刻度标签
- 刻度写进模板（磅 → 像素）：默认朝外、主 6 × 3、次刻度显示 3 × 3、`minorloglabels='none'`；改了的照改、没写的沿用默认；
  全局或单轴设了次刻度文字字号 → 创建时 `ValueError`
- 负对数：对应的轴 `tickprefix='-'`

**回调与滑块**
- 按轴回调只拿到这根轴的东西：左右轴回调分别收 `('yaxis', fig)`、`('yaxis2', fig)`，线回调只有这根轴上的 trace，
  图例回调 `[fig.layout.legend]`（回归：三种回调曾都只收 `fig`）；双 Y 轴的整图回调拿到 Plotly 配置里的轴名（用 `fig.layout['yaxis2']` 改右轴）
- `DataPlotter.add_slider`：`single` / `cumulative` 的档位与可见性、档位标签和标题是样品名（标题用带点的路径 `'title.text'`）、重复添加只保留一个；默认外观与 `slider_formatter` 覆盖；名称太长时隐藏刻度标签
- 报错：未绘图、图中没有曲线、`mode` 写错（不改动已有的图）、matplotlib 后端
- 两种滑块只管计划登记的曲线：整图回调加的参考线不分档，每档保持原来的显隐（含 `'legendonly'`）（回归：翻页滑块曾每档隐藏它，曲线滑块曾多出一档；55576fb 复审 4）

**多页与翻页滑块（6.8）**
- 分组分离模式：两页共用一个 Figure、共 4 条 trace，每页的 `artists` 只有自己那页的；刚画完只显示第一页
- 每页就是那张计划：同一样品在 A、B 两页是两条 trace，各用各组的样式，颜色按样品（两页同色）
- xy、双 Y 轴每个样品一页（后端只认计划，不认绘图方法）；只有一张计划的多线图不分页、全部显示
- 多页时按轴回调、整图回调对整个 Figure 只调一次，线回调拿到这根轴上所有页的 trace
- `add_page_slider`：每页一档，档位标签是组名 / 样品名；翻页时 `'title.text'`、`'legend.title.text'` 换成这一页的；
  `single`（默认）/ `cumulative` 两种模式；当前值默认不加前缀；重复添加只保留一个；`slider_formatter` 最后执行
- 两种滑块用错 → `RuntimeError` 并提示该用哪个；`mode` 写错 → `ValueError`；未绘图 → `RuntimeError`；matplotlib → `NotImplementedError`

### 两个后端对照 — `test_backend_parity.py`
- 分组参数（两个后端各测一遍）：只接受 `Group` 对象，传字典 → `TypeError`；基于别的数据集的 `Group` → `ValueError`；不传时是建在本数据集上的空 `Group`
- 计划里的版式、画法写错时，两个后端都明确报错（`ValueError`）
- 结果同一形状（两个后端 × 原来的四种写法）：`figures` 的键是计划的 key，每张图（页）的线与 `spec.curves` 一一对应，`axes` 单轴 `{left}`、双 Y 轴 `{left, right}`
- **同一个入口、同一个 `Group`，换后端**：多线、合并、分离、xy、双 Y 轴五种画法，图的 key 相同，每张图（Plotly 是每页）的曲线条数、顺序、标签、数据相同；
  按页比较，不比 Figure 个数（多张计划时 Plotly 是一个 Figure 多页）
- 按轴回调只作用在自己那根轴上（第三方审查 E）：只给右轴配范围和线色，左轴范围、左线颜色不变；
  给右轴配图例回调 → `ValueError`（一张图一个图例，归左轴）
- 轴工厂没给 `ticks` 时不改刻度，仍是 `DataPlotter(ticks=TickStyle(width=5))` 的全局设置（回归：两个工厂曾写死 3；matplotlib 渲染后断言）
- 单轴刻度覆盖：右轴回调里的 `ticks` 只改右侧 Y 轴（长 12、关掉次刻度），左轴仍是默认；Plotly 在 `dpi=200` 下按 `fig.layout.meta` 的 dpi 换算
- `combine_formatters` 合并同一种回调，两个后端都能接进绘图器
- 分组 `marker` 对散点图也生效（Plotly 散点仍是 `'markers'`）
- 图例标题：六种情况，每张图画出的标题与计划一致（没有就不画）
- 数字样品名（真实 CSV 的 `'101'`、`'102'`）：双 Y 轴图例标题、Plotly 两种滑块的档位标签都是原样文本（55576fb 复审 1）
- `DataPlotter(lines=LineStyle(marker=...))` 全局标记：折线都带标记（Plotly `lines+markers`），分组写的盖过全局，散点仍是圆点（复审 2）
- 颜色不在这里比：两个库的色带实现不同，各自「位置 → 颜色」分别在 `test_plotter.py`、`test_plotly_backend.py` 里测

### HTML 导出 — `test_html_export.py`
- 图的尺寸先取 layout、再取模板，layout 优先；两处都没有固定宽高 → `ValueError`
- 无侧边面板：画框尺寸等于图的尺寸；页面不出现滚动条；Plotly 的 `responsive` 默认关闭，图只由外壳整体缩放
- 有侧边面板：画框宽 = 图宽 + 间距 + 面板宽；面板位于图之后、画框之内；网页标题经过 HTML 转义
- 模板占位符全部填写，不残留 `$...`；用户传入的 `config` 会合并进去，且保留 `responsive: false`
- 写文件不修改传入的 Figure；与 Plotly 后端配合时（多线图默认 1000 × 800）画框为 1324 × 800

### 实验脚本 — `test_scripts.py`
- 脚本的入口是 `main(path=None, show=True)`：直接运行时弹窗选文件、最后 `plt.show()`；测试传文件路径和 `show=False`，不弹窗、不阻塞
  （Agg 后端的 `plt.show()` 不阻塞，但会警告「不能显示」，所以不调用）
- 一条测试循环 7 个场景：`rows()` 按列标题造数据（第 0 列各样品相同，其余列按样品号放大、都是正值），列标题与脚本里 `select(...)` 用到的一致；
  样品数覆盖分组用到的最大样品号（EIS 18 个、压电 10 个）
- 图的数量按样品数、分组数手算（压电 49、Nyquist 56、Bode 有峰 14 / 全部无峰 12 并打印提示、拉伸 3、`select_demo` 0）
- 调用前先开一张名为 `'caller'` 的图，`main()` 之后它还在（按名字查：图号关掉后会被新图重用）
- Bode 两个峰、第一个峰那一行缺频率：柱状图的 tan δ 是第一个峰的值，频率柱不画（不能拼上第二个峰的频率）
- `piezo_interactive` 不开 matplotlib 图，页面写到 `main(path, output=...)` 指定的位置
- 需要 scipy（`eis_bode` 寻峰，`test` 依赖已含 `plotlib[analysis]`）和 plotly；压电脚本一次开约 50 张图，测试里关掉 20 张的提醒

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
| `Dataloader` 样品数（第三方审查 A） | `int(98 * (1/49))` 得 1，静默丢样品 | 列数整除每样品列数 |
| `Dataloader` 未知后缀（第三方审查 A） | 沿用上一次读到的表「成功」返回 | 读进局部变量；未知后缀 `ValueError` |
| `DataSet.expandata`（第三方审查 B） | 零行样品被当成空容器而替换矩阵；失败时原对象已被改 | 看列数判断空；校验失败恢复原状 |
| matplotlib 负号刻度（第三方审查 C） | 渲染后只剩 `'-'`（包装的格式器收不到刻度位置）；双 Y 轴共用 X 轴负号加两次 | `_NegativeFormatter` 转交刻度位置；X 只在左轴加，`'x2'` 跳过 |
| matplotlib 重建图例（第三方审查 D） | 锚点被换算两次，图例移到画布外 | 按排版预设重建（`_make_legend`），不复制旧锚点 |
| matplotlib 轴工厂（样式对象化时修） | 总调用 `set_*scale`，冲掉预设的刻度格式 | `AxisStyle.scale` 没写就不调用 |
| Plotly 双 Y 轴右轴刻度（样式对象化时渲染发现） | 叠加轴默认 `tickmode='sync'`，刻度值成了 1.0007、0.9022 | 右轴 `tickmode='auto'` |
| `Dataloader` 数字样品名（55576fb 复审 1） | `'101'` 读成 `101.0`，双 Y 轴替换 `'{name}'`、Plotly 滑块标签 `TypeError` | 三种格式都按文本读（`dtype=str`），数据列再转数字 |
| Plotly 全局 marker（复审 2） | 模板重复传 `marker_symbol`，绘图器建不起来；折线不显示标记 | 全局 marker 不进模板，折线按「全局 < 分组」叠上并用 `lines+markers` |
| Plotly 对数轴分步设范围（复审 3） | 先设对数再设范围，range 写成数据值（被当 log10）；反过来已写的范围不换算 | `plotly_styles.apply_axis` 按轴的实际类型翻译，改类型时换算已写的边界 |
| Plotly 滑块与参考线（复审 4） | 翻页滑块每档隐藏整图回调加的参考线；曲线滑块把它多算一档 | 只给计划登记的曲线分档，其余 trace 保持原来的显隐 |
| 测试隔离：tk 变量在后台线程回收（步骤 7.1 时出现） | `test_data_reorder_app.py` 的 tk 变量被 Kaleido 线程回收，卡约 45 秒并报 "main thread is not in main loop" | fixture 销毁窗口后在主线程 `gc.collect()` |
| `DataTransformer` 的 `naming_func`（全面评审） | 标注允许 `sample_idx` 写列表，实际传列表在深处报 unhashable | 只收一个整数，写错给中文 `TypeError` |
| `select('samples', …)`（1.0 发布前复审） | 不存在的样品号静默跳过 | 报「找不到样品号」 |
| `DataTransformer` 新样品号（1.0 发布前复审） | 先显式写到某样品再自动分配会撞号 | 同时避开已累计的结果 |
| `Dataloader` 表头（1.0 发布前复审） | 样品名 `NA`、单位 `N/A` 读成 nan；样品名为空不报错 | `keep_default_na=False`；空样品名报出列号 |
| Plotly 刻度间距、轴范围（1.0 发布前复审） | `label_pad` 换算成小数被拒；改对数时换算会被替换的旧边界而报错；单侧边界残留 | 取整；写了 `limits` 就整体替换 |
| `expandata` 回滚状态、对数轴单轴次刻度（1.0 发布前复审） | `'loaded'` 变 `'written'`；单轴 `minor=True` 被全局关掉 | 回滚恢复状态；显式装对数次刻度定位器 |
| `ColumnList` 长度（全面评审） | 按元素个数算，零行数据集的列数是 0，逐样品遍历 `IndexError` | 按列数算（与 `expandata` 判断空的方式一致） |
| `DataSet.update_attributes`（全面评审） | 元数据长度不一致时先 print 六行到标准输出 | 各项长度写进异常信息，不打印 |
| Plotly 轴工厂边框（plotly_styles 搬家时发现） | 单轴图上 `frame=FrameStyle(right=True)` 读 `fig.layout.yaxis2` 抛 `AttributeError` | 用 `getattr` 判断有没有叠加的右轴 |
| Plotly 按轴回调（第三方审查 E） | 回调都只收 `fig`，右轴回调改了左轴和左线；matplotlib 右轴图例回调收到 `None` | 后端按轴交出轴名 / trace / 图例（做法 2）；没有图例的轴报 `ValueError` |
| 轴工厂刻度宽、分组 marker、Plotly `linecolor`（第三方审查 G） | 刻度宽写死 3；散点忽略分组 marker；纯散点只改隐藏线色 | 不写刻度宽；`STYLE_FIELDS_BY_KIND`；点也一起改色 |

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
   **绘图按层放**：分组规则只在 `test_plot_plan.py` 测；后端文件只测「把计划画对」和后端独有的功能；两个后端都要满足的约定写在 `test_backend_parity.py`，对 `backend` 参数化。
2. **命名**：测试名写成「行为」，如 `test_group_config_is_not_modified`，让 `pytest -v` 的输出本身就是一份清单；docstring 写一句「为什么要测」。
3. **数据**：用 `eis_dataset` 或 `make_dataset` 造小数据，数值设计成能心算；不要读真实数据文件。
4. **多组输入**用 `@pytest.mark.parametrize`，并加 `ids` 让输出可读。
5. **报错**用 `pytest.raises(..., match=...)`，一个 `with` 只包一次调用。
6. **绘图**检查 `figures` 里对象的属性（数据、线型、颜色、标签），不比对图片；取线用 `figures[key].artist(样品号)`。
   **刻度文字、图例位置**这类画出来才确定的结果，先 `fig.canvas.draw()` 再断言（2026-11-20，第三方审查：只看属性漏掉了负号刻度和图例位置两个 bug）。
7. **弹窗、文件对话框**等交互用 `monkeypatch.setattr` 临时替换掉。
8. **修 bug**：先写一个会失败的测试复现它（标 `xfail(strict=True)`），修好后删掉标记，留作回归测试。
9. 新增或删除测试后，顺手更新本文件的「测试清单」和「已知 bug」。
10. **测试跟着需求走**：结构变化后，测已消失的结构或在多层重复同一规则的测试，经用户同意清理（2026-11-19 起）。
