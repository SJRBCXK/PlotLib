# PlotLib 结构评估与分步开发指南

> 评估日期：2026-11-16，评估时的基线提交 `5cb8d4d`。
> 评估范围：`src/`、`scripts/` 逐行阅读；`tools/`、`gui/`、`tests/`、配置与文档看了结构和接口。
> 本文分三部分：A 评估结论与问题清单（背景）；**B 分步开发指南（当前要做的）**；C 整理工作的记录（已完成）。
> **状态**：C 部分已全部完成并提交（`92bbde6`，206 passed）。接下来由执行者（Opus 5.5）按 B 部分**指导用户**一步步做，先读 B.0。
> **进度（2026-11-18）**：B 部分步骤 1 ~ 4.2 已提交（`a36503b`）；步骤 4.3「样式约定」、4.4「结果带分组名」已提交（`813da17`；355 passed）。4.5 已取消；步骤 4 已验收。步骤 5 已完成（5.1、5.2 未提交；364 passed）。**下一步是步骤 6.1「分组绘图计划」**。
> **2026-11-18 路线调整**：步骤 5、6 按「先抽绘图计划、两个后端按同一份计划画」重排，不再先在 Plotly 里复制一份 `group_plotter`（理由见步骤 5 的「讲」）。
> 4.3 引入了标准样式写法（`src/plotlib/style.py`，见 4.3 执行记录）。步骤 5 开始时注意 4.2 推迟过来的 `InteractivePlotter` 改动（见 4.2 执行记录第 5 条）。
> 新文件 `src/plotlib/style.py`、`tests/test_style.py` 提交时需要 `git add`。
> A 部分描述的是基线提交时的状态，文件路径按当时的 `src/xxx.py` 书写，这些文件现在位于 `src/plotlib/xxx.py`；
> 其中的行号、以及 A.2、A.3、A.5 里已经解决的条目，不代表现状。

---

## A. 评估

### A.1 总体结论

数据层是扎实的：`DataSet` / `Dataloader` / `select().by()` / `DataTransformer` / `Group.apply` 职责清楚，
有 206 个测试保护，「取数 → 绘图 → 格式化」三层分离的方向也是对的。

问题主要不在算法，而在**项目外壳**：包没有真正的名字、导入靠三种不同的补丁撑着、
库代码和独立工具混放、教程代码和产品代码混放、文档落后于代码。
这些问题目前还不疼，但 `BACKEND_PLAN.md` 第 3、4 步要新增 `plot_spec.py`、`backends/`，
在现在的外壳上继续加文件，会把每个问题都放大一遍。所以建议**先整理、再继续多后端**。

代码层面最大的结构性问题是两个绘图器的重复，这已经在 `BACKEND_PLAN.md` 的计划内，
本文只补充几条该计划没有记录的事实（见 A.4）。

### A.2 包与导入（最基础，优先级最高）

> 第 1 ~ 5 条已解决（见 C 部分）。第 6、7 条要改函数行为，在 B 部分步骤 7.1。

| # | 问题                                                                    | 证据                                                                                                                                                                                                | 后果                                                                 |
| - | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 1 | 可导入的包名叫 `src`，发行名叫 `plotlib`，`import plotlib` 不存在 | `pyproject.toml` 的 `include = ["src*"]`；全项目都是 `from src.xxx import`                                                                                                                    | `src` 是通用目录名，不是包名；安装后会在环境里占用顶层名字 `src` |
| 2 | 包当前**没有安装**，导入靠三种机制各自补救                        | `pip show plotlib` 找不到（根目录的 `plotlib.egg-info` 是残留）；pytest 靠 `pythonpath = ["."]`；5 个脚本靠 `sys.path.insert`；库文件 `src/interactive.py:5-6` 自己也 `sys.path.insert` | 换个目录运行就可能失败；库代码修改 `sys.path` 会影响调用方         |
| 3 | `scripts/eis_bode.py` 没有 `sys.path.insert`，其余脚本都有          | 在 `scripts/` 目录下 `import src` 实测 `ModuleNotFoundError`                                                                                                                                  | `python scripts/eis_bode.py` 直接运行会在导入处失败                |
| 4 | `tools/html_export.py` 是库代码，却放在不打包的 `tools/` 里         | 被 `scripts/piezo_interactive` 导入、被 `tests/test_html_export.py` 测试；`tools/` 没有 `__init__.py`，也不在打包范围                                                                       | 安装后用不到；与同目录的独立 GUI 程序性质完全不同                    |
| 5 | 实际用到的依赖没有声明                                                  | `scipy`（`eis_bode.py` 的 `find_peaks`）；`PySide6`（`tools/*_qt.py`、`gui/`、`tests/test_data_reorder_qt.py`）；`pytest-cov`（`tests/README.md` 推荐的命令）                     | 新环境装完跑不起来，且看不出缺什么                                   |
| 6 | `import src` 必须有 Tk                                                | `src/dataloader.py:3-4` 在模块顶层导入 `tkinter`，`src/__init__.py` 又导入 `Dataloader`                                                                                                     | 无界面环境下连数据模块都导入不了；与「Plotly 按需导入」的做法不一致  |
| 7 | 库函数里调用 `exit()`                                                 | `src/dataloader.py:100`，用户取消选文件时直接退出进程                                                                                                                                             | 被 GUI 或其他程序调用时会把整个程序带走                              |

### A.3 目录职责混杂

> 本节除 `tools/` 一行（Tk / Qt 两套并存，见 B 部分步骤 9）外均已解决，见 C 部分。

| 目录         | 现状                                                                                     | 问题                                                                                                                                                                                                                                            |
| ------------ | ---------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/` | 5 个实验分析脚本 + 1 个调试脚本 `select_test.py` + 1 个空文件 `SMU.py` + `assets/` | `piezo_interactive`、`tensile` **没有 `.py` 扩展名**，编辑器、类型检查、按 `*.py` 的搜索都看不到它们；`select_test.py` 不是测试却叫 test；`SMU.py` 是 0 字节                                                                  |
| `tools/`   | 4 个独立 GUI 程序（Tk 与 Qt 各一对）+ 库代码 `html_export.py` + 它的模板               | GUI 程序共 3670 行，比整个 `src/`（3170 行）还多；Tk 版与 Qt 版的逻辑层是复制的（`data_collector` 两版逻辑层逐行相似度约 70%）；工具里的类叫 `DataLoader` / `DataPlotter`，与库里的 `Dataloader` / `DataPlotter` 几乎同名但毫无关系 |
| `gui/`     | PySide6 学习步骤 `step1~4` + `widgets/plot_canvas.py` + 学习路线图                   | 是教程，却占着顶层的 `gui/` 这个产品位置；将来真正的桌面程序没地方放                                                                                                                                                                          |
| `tests/`   | 测试 + `README.md` + `LEARNING_PLAN.md`                                              | 学习路线图混在测试目录；`README.md` 写的是 161 个测试，实际 206 个，文件对照表缺 4 个测试文件                                                                                                                                                 |
| 根目录       | `matplotlibrc`、`Aligned_Results/Data/`、`plotlib.egg-info/`、`.coverage`        | `matplotlibrc`（`backend: TkAgg`）只在「当前目录是项目根」时生效，行为取决于从哪里启动；`Aligned_Results/` 是空的遗留目录；`scripts/piezo_interactive` 把 `output.html` 写到当前目录，而 `.gitignore` 没有忽略它                    |
| `docs/`    | 只有 `BACKEND_PLAN.md`                                                                 | —                                                                                                                                                                                                                                              |

`README.md` 也已落后：写着 Python >= 3.8（实际 `requires-python = ">=3.14"`）；项目结构里没有
`group.py`、`interactive.py`、`tests/`、`gui/`、`docs/` 和 5 个工具中的 4 个；快速开始的例子用了 `plt.show()` 却没有导入 `plt`；
没有提 Plotly 和 HTML 导出；写着 MIT 许可但仓库里没有 `LICENSE` 文件。

### A.4 `src/` 内部的结构性问题

**1. 两个绘图器重复，且已经开始走样（计划内，补充事实）**

- `interactive.py:66-111` 的 `_ensure_ready` / `_get_data` / `_get_column_data` 是 `plotter.py:152-178` 的副本。
- 配色逻辑两边各写了一份，**组号不连续时两边都不对**（已实测）：
  - matplotlib（`plotter.py:368`、`481`、`490`，`cmap(i / num_datagroups)`）：组号 0 / 5 / 9 时，5 和 9 得到同一个颜色（比值超过 1 被截断），不报错，图是错的；
  - Plotly（`interactive.py:114-116`）：组号 0 / 5 时 `IndexError`。
    `BACKEND_PLAN.md` 第 7 节只记录了 Plotly 一侧，matplotlib 一侧是静默错误，更隐蔽。
- `InteractivePlotter.__init__` 的第一个参数 `plot_data_group` 是必填位置参数，但从未使用；
  `plot_data_groups`、`axesset`、`plot_artists` 也只保存不使用；样式写死在 `_create_template` 里，而 `DataPlotter` 的样式是构造参数。

**2. `DataPlotter` 的四个方法把同一条流水线写了五遍**

「取数 → 画 → 默认格式 → 用户格式 → 负号刻度 → 存入 `axesset`」在 `plot_objects`、`group_plotter`（分离与合并各一遍）、
`subplotter_yy`、`subplotter_xyy` 中各出现一次。结果容器 `axesset` 每个方法的形状都不同：

| 方法               | 键                | 值里的曲线字段                                           |
| ------------------ | ----------------- | -------------------------------------------------------- |
| `plot_objects`   | `'main'`        | `'artists'`：列表                                      |
| `group_plotter`  | 组名或 `'main'` | `'artists'`：`{组号: artist}`                        |
| `subplotter_yy`  | 组号              | `'artist'`：单个                                       |
| `subplotter_xyy` | 组号              | `'artist_Y1'` / `'artist_Y2'`，`'ax1'` / `'ax2'` |

没有稳定的结果约定，测试和后处理（滑块、导出）只能按方法分别写。这正是「绘图计划」要解决的问题。

**3. 分组配置把数据语义和 matplotlib 样式放在一个字典里**

`{'num': [0, 1], 'linestyle': (0, (3, 5))}` 中，`num` 是与后端无关的数据选择，
`linestyle` 的元组写法是 matplotlib 专有的，Plotly 无法翻译。
另外 `resolve_num` 定义在 `group.py`（分组计算模块），`plotter.py` 为了解析配置去导入计算模块。
这个约定需要在 `BACKEND_PLAN.md` 第 3 步（交互图补分组模式）**之前**定下来，否则会被原样复制进第二个后端。

**4. `formatters.py` 两个后端写在同一个函数体里**

三个工厂都是 `if backend == "matplotlib": … 否则 Plotly …` 的结构，471 行里两套实现交错。
`XxxFactory.create` 是只有一个静态方法的类，外面再套一层 `make_xxx(**kwargs)`，编辑器因此看不到参数列表。
参数名不统一：坐标轴用 `custom_formation`，线条和图例用 `custom_formations`。
matplotlib 坐标轴回调把刻度线宽写死为 3（`formatters.py:134`、`146`），会覆盖 `DataPlotter(ticker_width=...)`。

**5. 名字与实际含义不符**

| 名字                          | 实际含义                                                                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `DataSet.names`             | 样品（组）名，同一组的各列相同                                                                                                 |
| `DataSet.units`             | 列标题，如 `"Zs'(ohm)"`，是「物理量 + 单位」；`select("Zs'(ohm)")` 和坐标轴标题用的都是它                                  |
| `plotdataRowNum_x` / `_y` | 组内**列**序号，不是行                                                                                                   |
| `NegLogScale_x` / `_y`    | 对数据取绝对值，并在刻度文字前加负号；不设置对数刻度                                                                           |
| `DataSet.status`            | 注释写 `empty, selected, processed`，实际取值是 `empty` / `loaded` / `written`，且 `processor.py:232` 用它做流程判断 |

此外大小写和拼写不统一：`Selected_data`、`New_group`、`Norm`、`indicies`、`expandata`。
这些名字已被脚本大量使用，**不建议现在批量改名**；但新写的公共层（绘图计划）应当用准确的名字，不要沿用。

**6. 其余（按文件）**

- `dataloader.py`：`DATASET_FRACTION` 与 `COLUMNS_PER_DATASET` 是同一个信息（前者恒等于后者的倒数），
  每个脚本都手算一遍 `1/N`；两者不一致时组数会算错且不报错。文件路径只能靠弹窗或事后给属性赋值（测试里就是 `loader.file_path = ...`）。
  扩展名不支持时报的是笼统的「数据集加载失败」；`.CSV` 这类大写扩展名不识别。
- `dataset.py`：元数据是 7 个平行列表，靠 `update_attributes()` 维持一致，`Dataloader._formatter` 逐个赋值并带 `# type: ignore`；
  `_get_group_local_idx` 在 `Dataloader` 和 `DataSet` 中各有一份；`columns_to_dataset(extended=False)` 里有 `self = local_dataset`（`dataset.py:329`）；
  校验失败时先 `print` 再抛异常；`re`、`copy` 导入后未使用。
- `processor.py`：一个文件放了「选列」和「变换」两件不相关的事；`DataProcessLayer.__init__` 有 4 个不使用的参数，
  `Processed_data`、`called_process` 也未使用；`DataTransformer.__init__` 把数据集的 10 个属性各复制了一份。
- 脚本暴露出的接口缺口：
  - 「按组遍历 → 变换 → 拼回」的三行循环在脚本里出现了 5 次（`eis_bode.py:159`、`186`，`eis_nyquist.py:191`，`tensile:68`，`select_test.py:33`）；
  - 脚本直接调用私有方法 `_rearrange_columns()`（`eis_bode.py:162`、`eis_nyquist.py:194`）；
  - `src/` 与 `scripts/` 中共有 83 处 `# type: ignore`，多数（如 `input_dataset=data`）早已不需要。

### A.5 `scripts/` 的问题

- 所有脚本都在模块顶层直接执行，数据靠弹窗选择：无法复现、无法自动检查，改了库之后只能逐个手动点一遍。
- 每个脚本都重复同一段样板：`INPUT_COLUMNS_PER_DATASET`、`INPUT_DATASET_FRACTION`、`dataRowNum_unit1…N`、三个 formatter 的导入。
- 未使用的导入较多（如 `tensile` 里的 `scipy`、`FuncFormatter`、`LogLocator`）；`eis_bode.py` 的文件说明是从 `eis_nyquist.py` 复制的。
- `eis_nyquist.py` 中 `Nyquist_formatter` 与 `NegLog_formatter` 完全相同。

---

## B. 分步开发指南（执行者指导用户完成）

### B.0 指导方式（执行者先读）

这一部分和 C 部分不同：C 是机械工作，做完即可；B 是逻辑与架构修改。
用户的要求是：**逻辑与架构修改必须让用户知晓并学习清楚，不能在用户没弄懂的情况下把改动做完。**

每个小节固定按七个动作走，一次只走一个小节，走完停下：

| 动作 | 做什么                                                                                   |
| ---- | ---------------------------------------------------------------------------------------- |
| 讲   | 用几句话说明这一节解决什么问题、为什么现在做                                             |
| 读   | 指出要读的代码（文件 + 函数名），等用户读完，回答问题                                    |
| 定   | 列出要用户决定的事，给出建议和理由，等用户定下来                                         |
| 测   | 先写测试。**期望值由用户说出**，再落成代码；先确认它在改之前是失败的               |
| 改   | 实现。由谁敲代码当场问用户；无论谁写，每处行为变化都要讲清原因                           |
| 验   | 运行 `python -m pytest`，并逐条对照该节的验收条件                                      |
| 记   | 更新 B.10 进度表（涉及多后端的还要更新 `BACKEND_PLAN.md` 第 5 节）；是否提交由用户决定 |

其他约定：

- 标注「机械」的小节不需要七个动作，讲清结果、给用户看 diff 即可。
- 不跨步骤，不顺手修本文没列出的问题；发现了就记下来告诉用户。
- 本文的行号对应提交 `92bbde6`，改动后会漂移，**以函数名为准**。本文与代码不一致时以代码为准，并告诉用户。
- 测试数量只增不减（经用户同意删除的除外）。基线是 364 passed（步骤 5.2 之后；此前依次为 206 → 209 → 218 → 236 → 242 → 350 → 354 → 355 → 359）。
- 本文给出的名字、签名都是建议。「定」这个动作里用户改了主意，就按用户的来，并把决定写回本文对应小节。
- 修改代码用编辑工具逐处修改，让用户能看到 diff。注释和文档保持中文。

### B.1 路线总览

| 步骤 | 内容                                            | 性质                   | 前置 |
| ---- | ----------------------------------------------- | ---------------------- | ---- |
| 1    | 定词汇表：样品、通道、分组                      | 讨论，不写代码         | —   |
| 2    | 第一层改名：`group` → `sample`             | 机械                   | 1    |
| 3    | 稀疏样品号配色：第一块公共代码                  | 逻辑，小               | 2    |
| 4    | 让 `Group` 成为分组的唯一主人                 | 逻辑，中               | 2    |
| 5    | 交互图接上 `Group`，两个绘图器共用取数        | 机械 + 逻辑，小        | 3、4 |
| 6    | 绘图计划，从分组模式开始（`BACKEND_PLAN.md` 第 3、4 步） | 架构，大      | 5    |
| 7    | 补接口缺口：`Dataloader`、逐样品变换、列排序  | 逻辑，小，三项互相独立 | 2    |
| 8    | 让脚本可复现                                    | 逻辑，小               | 7    |
| 9    | 工具收敛（Tk / Qt）                             | 待定                   | —   |
| 10   | 桌面程序                                        | 待定                   | 6    |

步骤 7 的三项可以穿插在 3 ~ 6 之间做，适合在大步骤之间换换脑子。

---

### 步骤 1：定词汇表

**讲。** 代码里「组」这个字指两件不同的事，这是分组概念模糊的根源：

|            | 第一层                                                                                                  | 第二层                                                                      |
| ---------- | ------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| 实际含义   | 一个样品，或一次测量                                                                                    | 若干个样品组成的、有名字的集合                                              |
| 现在的名字 | `groups_idx`、`num_datagroups`、`select('group', …)`、`iter('groups')`、绘图里的 `group_idx` | `data_groups` 字典、`Group` 类、`plot_data_groups`、`group_plotter` |
| 归属       | `DataSet`                                                                                             | 目前是裸字典，计算和绘图各自解析                                            |

`DataSet` 本质是一张「样品 × 通道」的表：每一列属于某个样品，是该样品的第几个通道。
`_group_local_indices_unify_check` 保证了同一通道在所有样品里列标题相同，所以它确实是一张规整的表。

**读。** `dataset.py` 的 `DataSet.__init__`、`update_attributes`；`group.py` 的 `resolve_num`、`Group.apply` 开头的循环；
`plotter.py` 的 `group_plotter`（重点看 `group_indices`、`indices`、`i` 三个变量分别是哪一层）。

**定。**

| # | 要定的事                          | 建议                                                                            | 理由                                                                                           |
| - | --------------------------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| 1 | 第一层叫什么                      | 样品，`sample`                                                                | 与实验语言一致；`names` 里存的本来就是样品名                                                 |
| 2 | 「样品内的第几列」叫什么          | 通道，`channel`（备选 `quantity`、`field`）                               | 需要一个不含 group 的词                                                                        |
| 3 | 第二层叫什么                      | 分组，`group`，保持不变                                                       | 现有的 `Group`、`group_plotter` 本来就指这一层，不用动                                     |
| 4 | `names`、`units` 这一轮改不改 | 不改，只在词汇表里写明：`names` 是样品名，`units` 是列标题（物理量 + 单位） | 出现约 140 处，`.names` 这种写法太通用，无法靠搜索安全替换                                   |
| 5 | 旧名字留不留别名                  | 不留，仓库内一次改完                                                            | 别名会让两个名字长期并存，正是现在的问题。前提：用户没有仓库以外的脚本在用旧名字，需向用户确认 |

**用户练习（不写代码）。** 打开 `scripts/eis_bode.py` 的 `data_groups`，用一两句话写下：每个分组在实验里代表什么；
组内第 0 个和第 1 个样品各是什么角色（`rev_camp` 用 `slices[1]` 除以 `slices[0]`）。
再对 `scripts/piezo.py` 做一遍。两者一个是「有顺序的配对」，一个是「无顺序的批次」，这个区别步骤 4 会用到。

**产出。** 新建 `docs/GLOSSARY.md`，一页以内：三个词的定义、各自对应的代码名字、上面练习写下的两个例子。

**验收。** 用户不看代码能说出：样品和分组的区别；一个样品能不能同时属于两个分组（能，合并模式已经支持）。

---

### 步骤 2：第一层改名（机械）

按步骤 1 定下的名字执行。下表按建议的名字（`sample`、`channel`）写，用户改了名字就相应替换。

| 旧名字                                                                                                                     | 新名字                                                                      | 出现次数（src / tests / scripts）                                              |
| -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `groups_idx`                                                                                                             | `sample_idx`                                                              | 85 / 31 / 3                                                                    |
| `num_datagroups`                                                                                                         | `num_samples`                                                             | 42 / 11 / 0                                                                    |
| `group_local_idx`                                                                                                        | `channel_idx`                                                             | 35 / 13 / 2                                                                    |
| `Column.group_idx`，及字典键 `'group_idx'`                                                                             | `sample_idx`                                                              | 见 `dataset.py` 的 `_ALLOWED_KEYS`、`plotter.py` 的 `_get_column_data` |
| `select('group', [...])` 的关键字                                                                                        | `'sample'`                                                                | `processor.py` 的 `re.match(r'group\w*', …)`；测试里约 14 处              |
| `iter('groups')`                                                                                                         | `iter('samples')`                                                         | `dataset.py` 的 `iter`；scripts 5 处、tests 1 处                           |
| `New_group`、`input_groups_idx`、`norm_groups_idx`、`TransformMetadata['groups_idx']`                              | `new_sample`、`input_sample_idx`、`norm_sample_idx`、`'sample_idx'` | `processor.py` 的 `DataTransformer`                                        |
| `form_array(group_idx=…)`                                                                                               | `sample_idx=`                                                             | `dataset.py`                                                                 |
| `_get_data(group_idx=…)`、`_get_column_data(group_idx, group_local_idx, …)`                                          | `sample_idx`、`channel_idx`                                             | `plotter.py`、`interactive.py`                                             |
| 同含义的私有方法：`get_groupnumber`、`_get_group_local_idx`、`_group_local_indices_unify_check`、`_next_new_group` | 一并改成 sample / channel 的说法                                            | `dataset.py`、`dataloader.py`、`processor.py`                            |

**不改的（它们本来就是第二层）：** `Group`、`group_config`、`groups_config`、`plot_data_groups`、`group_plotter`、
`merge_groups`、`apply_group_linestyle`、`group_name`、`resolve_num`、`resolve_group_indices`。

**也不改的：** `COLUMNS_PER_DATASET`、`DATASET_FRACTION` 留到步骤 7.1 和 `Dataloader` 接口一起改。

**做法。** 一次改一个名字：在全仓库（`src/`、`tests/`、`scripts/`）改完这一个名字，运行测试，通过后再改下一个。
不要按文件改，否则中途测试会一直是红的，出了问题无法定位。

**必须人工逐行看的两处**（两层在这里相遇，不能整体替换）：

- `group.py` 的 `Group.apply`：`group_indices`、`g_idx` 是样品号；`result_group_idx` 是结果的样品号；`group_name` 是分组名。
- `plotter.py` 的 `group_plotter` 和 `_configure_lines`：`group_indices`（分组名 → 样品号列表）、`indices`、`i` 是样品号；`group_name`、`group_config` 是分组。

改完后把这两处的 diff 单独给用户看，让用户确认每个变量属于哪一层。这是这一步唯一需要用户动脑的地方，也是对步骤 1 的检验。

**文档。** `README.md`、`tests/README.md`、`docs/GLOSSARY.md` 里的旧名字同步更新。
`docs/BACKEND_PLAN.md` 里的「实际组号」等说法是否改成「样品号」，问用户（该文件规定架构内容未经讨论不改，这里只涉及用词）。

**验收。** 206 passed；`git grep -nE "groups_idx|num_datagroups|group_local_idx"` 无结果；
`git grep -n "iter('groups')"` 无结果；脚本只执行 import 语句能通过（做法见 C 部分记录）。

**执行记录（2026-11-16，与上表不同处）：**

- `select` 的关键字定为 **`'samples'`，必须完全一致**（原来是前缀正则 `group\w*`，`'Group1'` 等写法也认）。
  原因：关键字判断排在按名字查找之前，前缀匹配会把以 sample 开头的样品名误当成关键字。
  测试 `test_select_group_keyword_is_case_insensitive` 改为 `test_select_samples_keyword_must_match_exactly`（4 个用例），基线变为 **209 passed**。
- 私有方法：`get_groupnumber` → `count_samples`，`_group_local_indices_unify_check` → `_channel_units_unify_check`，`_get_group_local_idx` → `_get_channel_idx`。
- 两层相遇处的局部变量一并改名：`Group.apply` 中 `group_indices` → `sample_ids`、`g_idx` → `sample`；
  `group_plotter` 中 `group_indices` → `sample_ids_of`、`indices` → `sample_ids`、`i` → `sample`；`_configure_lines` 同理。
- 用户追加：`_get_data` 的 `local_idx_x` / `local_idx_y` → `channel_x` / `channel_y`（与 `DataSet.local_idx` 同词异义）；`iter('channel_idx')` → `iter('channels')`。
- `src/`、`tests/` 中表示样品的注释与文档字符串统一为「样品」「样品号」「通道号」；表示分组的不变。
- 留到步骤 7.1：`tests/conftest.py` 的 `write_grouped_file(groups=…)`、`load_file(columns_per_group=…)` 参数名，
  以及脚本里 `INPUT_COLUMNS_PER_DATASET` 旁「每组数据集的列数」的注释，与 `COLUMNS_PER_DATASET` 改名一起处理。

---

### 步骤 3：稀疏样品号配色

**讲。** 样品号不连续时两个绘图器的颜色都是错的。这是第一块两个绘图器共用的代码，
也是「提取公共部分」的最小练习：先用测试把行为钉住，再让两边调用同一个函数。

复现（改名后参数名相应变化）：

```python
import numpy as np
from plotlib.dataset import DataSet
from plotlib.plotter import DataPlotter

ds = DataSet()
for sample in (0, 5, 9):
    part = DataSet().form_array(np.arange(6.0).reshape(3, 2), [f'S{sample}'] * 2, ['x', 'y'], sample, repeat_times=2)
    ds.expandata(part)
DataPlotter(ds).plot_objects()      # 样品 5 和 9 颜色相同，不报错
```

同样的数据交给 `InteractivePlotter` 会 `IndexError`。

**读。** `plotter.py` 里三处 `self.cmap(… / self.num_datagroups)`（`plot_objects` 一处，`group_plotter` 两处，其中一处是合并模式的组首色）；
`interactive.py` 的 `_get_color`。让用户自己算一遍：3 个样品、样品号 0 / 5 / 9 时，这两段代码各得到什么。

**定。**

| # | 要定的事                                             | 建议                                  | 理由                                                                                                                  |
| - | ---------------------------------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1 | 样品号 0 / 5 / 9 应该得到色带上的哪三个位置          | 0、1/3、2/3，即「排名 ÷ 样品数」     | 样品号连续时与现在的结果完全相同，已有的图颜色不变。备选「排名 ÷ (样品数 − 1)」能用满色带，但会改变所有现有图的颜色 |
| 2 | 函数放在哪                                           | 新文件 `src/plotlib/plot_common.py` | 它是公共层的第一块，步骤 6 会继续往里放；`plot_spec.py` 按 `BACKEND_PLAN.md` 留到第 4 步再建                      |
| 3 | 两个绘图器构造函数里的 `num_datagroups` 参数怎么办 | 删除                                  | 修好后配色不再用它；测试和脚本里没有任何地方传这个参数                                                                |
| 4 | 从全集里选出一部分样品再画，颜色要不要和全集里一致   | 这一步不做，记为遗留                  | 现在也不支持；需要时再设计「传入完整样品号列表」的入口                                                                |

**测。** 先写、先看到失败：

- 纯函数（新文件 `tests/test_plot_common.py`）：输入 `[0, 1, 2]` 和 `[0, 5, 9]` 得到相同的三个位置；输入乱序、有重复时结果不变；空输入得到空字典。期望的具体数值由用户按第 1 项决定来写。
- matplotlib：上面复现用的数据，`plot_objects()` 后三条线颜色互不相同。
- Plotly：样品号 0 / 5 的数据不报错，两条曲线颜色不同。
- 已有的 `test_group_merge_mode`（组首色）保持通过，不用改。

**改。**

- `plot_common.py`：一个函数，输入样品号的集合，输出 `{样品号: 色带位置}`。建议签名 `color_positions(sample_ids) -> dict[int, float]`。
- `plotter.py`：在 `__init__` 里对数据集的全部样品号建一次映射，三处 `self.cmap(…)` 改为查映射。
- `interactive.py`：`_get_color` 改为查同一个映射，再用 `plotly.colors.sample_colorscale` 取色。
- 按第 3 项决定处理 `num_datagroups` 参数。

**验收。** 新测试通过，原有 206 个不变；`git grep -n "/ self.num_"` 在 `plotter.py` 中无结果。
更新 `BACKEND_PLAN.md` 第 5 节第 0 步的状态和第 7 节的遗留问题。

---

### 步骤 4：让 `Group` 成为分组的唯一主人

**讲。** 现在分组是一个裸字典，被传到两个地方各自解析：`Group(data, cfg)` 用它算，`DataPlotter(plot_data_groups=cfg)` 用它画。
`Group` 类已经存在，`InteractivePlotter` 的第一个参数 `plot_data_group: Group | None` 也已经留好了位置，只是从没用过。
这一步把这条线接通：分组只在 `Group` 里解析和校验一次，其他地方只向它要结果。分四个小节，每节单独走七个动作。

#### 4.1 `Group` 在创建时规范化并校验

**读。** `group.py` 的 `Group.__init__`（现在只保存两个参数）、`resolve_num`；再找出配置在哪些地方被重复解析：
`Group.apply`、`plotter.py` 的 `group_plotter` 和 `_configure_lines`。

**定。**

| # | 要定的事                     | 建议                                                                                                                                                                               |
| - | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | 接受哪些写法                 | 两种都收：简写 `{'A': [0, 1]}`；完整 `{'A': {'num': [0, 1], 'linestyle': 'dash'}}`。重排工具生成的是后一种（`tools/data_reorder_qt.py` 的 `generate_groups_code`），不能废弃 |
| 2 | 对外提供什么                 | 分组名列表（保持书写顺序）；按名字取样品号列表（保持书写顺序，顺序就是角色）；按名字取样式字典（`num` 以外的键）；遍历                                                           |
| 3 | 创建时校验什么               | `num` 的类型（已有）；样品号是否存在于数据集。现在样品号写错要到绘图时才报「未找到对应的列数据」，看不出是哪个分组                                                               |
| 4 | 同一分组里样品号重复算不算错 | 报错                                                                                                                                                                               |

**测。** 每个分组名对应的样品号顺序与书写一致；两种写法结果相同；样品号不存在时创建即报错，且报错信息里有分组名；
已有的 `tests/test_group.py`、`tests/test_group_apply.py` 保持通过（`test_group_index_out_of_range_raises` 的报错时机会提前，期望可能要调整，由用户判断）。

**改。** 只动 `group.py`。`Group.apply` 改为使用创建时规范化好的结果，不再自己调用 `resolve_num`。

**执行记录（2026-11-17 ~ 18，已完成，236 passed；与上表不同处）：**

- **定**：
  1. 只收完整写法 `{分组名: {'num': [...], 其余字段...}}`，不支持简写（用户：组配置应放在一起，且以后要扩展字段）。简写 → `TypeError`，提示正确写法。
  2. 读接口：`names`（property）、`for name in group`、`sample_ids(name)`、`options(name)`（`num` 以外的全部字段，原名 `style` 因要扩展字段而改）、`to_config()`（当前配置的新字典）。全部返回副本。`resolve_group_indices` 删除。
  3. 创建时校验样品号存在（报错含分组名、不存在的、已有的样品号）；4. 同一分组内重复 → `ValueError`。
  5. 用户追加修改接口：`add(config)` 只新增（已存在报错）、`set(config)` 整体替换已有分组且位置不变（不存在报错）、`delete(name)`；
     参数格式与构造函数相同，先校验全部再修改，返回 `self`。
  6. 字段拼写检查（如 `linestlye`）留到 4.3。
  7. **传入配置原地格式化**（用户的设计决定，推翻了最初「传入字典不改动」的约定）：创建 `Group` 时把每个分组的 `num` 原地改为 `list[int]`，
     `Group` 的外层字典是自己的，各分组的配置对象与传入的字典共用；增删改只改外层字典，不往原字典里加、删分组。读接口仍返回副本。
     已知取舍：创建后在脚本里直接改分组配置会绕过校验（已写进 `Group` 文档字符串）。
- **测**：`tests/test_group.py` 新增 19 条 Group 测试（含后补的「num 为空」回归测试），`test_group_apply.py` 改写 `test_sample_index_out_of_range_raises`、删除 `test_resolve_group_indices`。
- **改**：执行者写大纲与 `Group` 类；**用户写模块级函数 `_check_group`**：字典判断 → 调用 `resolve_num` → `Counter` 查重复 → 集合差查不存在 → 原地写回并返回 `{分组名: 配置}`。
  过程中 `_check_group` 曾复制 `resolve_num` 的检查并漏掉「为空」，由新增测试发现后改为直接调用 `resolve_num`。
  讨论后决定 `resolve_num` 暂不加字典判断、两个函数暂不合并（见步骤 4.2）。

#### 4.2 绘图器只认 `Group`

**读。** `plotter.py` 的 `__init__`（`plot_data_groups`、`self.groups_config`）和三处 `resolve_num(…)`；
`interactive.py` 的 `__init__` 前两个参数。

**定。**

| # | 要定的事                                          | 建议                                                                                                                                                                  |
| - | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | 绘图器参数收什么                                  | `Group` 或字典都收；传字典时内部立即包成 `Group`。旧脚本不用改                                                                                                    |
| 2 | 两个绘图器的参数名                                | 统一成一个名字（如 `groups`），`DataPlotter` 的 `plot_data_groups` 是否保留为旧名由用户定                                                                       |
| 3 | `InteractivePlotter` 那个必填却没用的第一个参数 | 去掉，分组改为可选的关键字参数。测试里 `InteractivePlotter(None, eis_dataset)` 这种调用有 11 处，脚本一处（`piezo_interactive.py`），随之更新（这部分是机械工作） |

**测。** 传字典和传 `Group` 画出的结果相同（曲线数、数据、标签、顺序）；已有的分组绘图测试不变。

**改。** `plotter.py` 不再导入 `resolve_num`，改为向 `Group` 要样品号和样式。`interactive.py` 调整构造参数。

**4.1 留下的事（放在 4.2 末尾做）：** 绘图器切换到 `Group` 之后，`resolve_num` 只剩 `_check_group` 一个调用方。
用户的方案：把 `resolve_num` 的全部校验并进 `_check_group`，`resolve_num` 只负责把 `num` 转成列表（或直接并入，届时再定）；
`test_group.py` 中直接测 `resolve_num` 报错的测试改为通过 `Group` 测。**顺序不能反**：在绘图器切换之前删掉 `resolve_num` 的校验，
`group_plotter` 会失去配置校验（`test_group_bad_config_raises_before_any_figure` 会失败）。
在此之前，`group_plotter` 遇到简写配置仍报「缺少 'num' 键」，切换到 `Group` 后自动改善。

**执行记录（2026-11-18，已完成，242 passed；与上表不同处）：**

- **定**：
  1. 绘图器的分组参数**只接受 `Group` 对象**，不接受字典（用户：后续标准化流程更方便）。传字典 → `TypeError`，提示先 `Group(dataset, config)`。
     类型标注 `Group | None` 只在编辑器里提醒，运行时用 `isinstance` 检查。
  2. 参数名 `groups`，不留旧名 `plot_data_groups`；属性名 `self.groups`（用户命名）。不传时为空 `Group`。
  3. 一个绘图器只对应一个数据集和一个 `Group`：`groups.dataset is not input_dataset` → `ValueError`。不复制、不重建 `Group`（用户：绘图器只处理传入的那一份配置）。
  4. 通过 `Group` 的接口读取（`for name in groups`、`sample_ids`、`options`），不用 `to_config()`（会产生第二份配置）。
  5. **`InteractivePlotter` 这一步不动**，删第一个参数、加 `groups` 参数都推迟到步骤 5，届时把上面的检查移进 `plot_common.py` 共用。
  6. `test_group_bad_config_raises_before_any_figure` 删除（配置校验属于 `Group`，在 `test_group.py` 覆盖）；`test_group_config_is_not_modified` 改为「画图前后 `to_config()` 不变」。
- **改**：构造函数三个分支、`group_plotter` 与 `_configure_lines` 改用接口由执行者编写（用户逐处看 diff）。
  三个脚本改为数据加载后建一个 `groups = Group(data, data_groups)`，绘图与 `apply` 都用它；README 同步。
- **合并 `resolve_num`（4.1 留下的事）**：校验全部并入 `_check_group`；`resolve_num` 改为内部函数 `_resolve_num(num)`，只做转换。
  这是重构：先把 `test_group.py` 中直接测 `resolve_num` 的测试改为通过 `Group` 测（并给「报错带分组名」补了简写、重复、样品不存在 3 个用例），
  改实现前后都是 242 passed。`resolve_num` 原来「不修改配置」的测试改为「原地格式化只改 num」。

#### 4.3 样式约定

**讲。** 分组说的是「谁和谁一组」，线型说的是「这组怎么画」。线型可以继续写在分组配置里，但要定清楚哪些写法是两个后端都认的。

**定。**

| # | 要定的事                                     | 建议                                                                                                                   |
| - | -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| 1 | 公共线型                                     | 只有 `'-'`、`'--'`、`':'`、`'-.'` 四种                                                                         |
| 2 | 元组写法（如 `(0, (3, 5))`，EIS 脚本在用） | 视为 matplotlib 原生设置：matplotlib 照常使用；Plotly 遇到时明确报错，报错信息指出分组名（`BACKEND_PLAN.md` 原则 5） |
| 3 | 线型的翻译表放哪                             | `formatters.py` 的线条工厂里已有一份 `dashes` 字典，提成模块级常量，两处共用                                       |

**测。** 四种公共线型在两个后端各自得到对应的原生值；元组线型在 Plotly 报错。Plotly 一侧的测试要等步骤 5 有了分组绘图才能写完整，这里先测翻译函数本身。

**从 4.1、4.2 带过来的现状与待办（开始 4.3 前先读）：**

- 分组的其余字段通过 `Group.options(name)` 读取（返回副本）；`DataPlotter` 在 `group_plotter` 和 `_configure_lines` 里用 `options.get('linestyle', ...)` 读线型。
- **字段拼写检查**（4.1 第 6 项）在这一步决定：如 `'linestlye'` 写错时现在会被静默忽略。要定由谁检查（`Group` 创建时，还是使用字段的后端）、用白名单还是只检查已知字段。用户希望以后能扩展字段（如 `label`），白名单要考虑扩展方式。
- `InteractivePlotter` 还没有分组参数（推迟到步骤 5），所以这一步只能先测翻译函数本身。
- `Group` 的配置是原地格式化的（用户决定）；如果这一步要翻译或校验线型，注意它是否也要原地改写，按同一原则由用户定。

**执行记录（2026-11-18，已完成，350 passed；与上表不同处）：**

讨论中方向变了两次：先考虑过把样式移出 `Group`（绘图器参数按分组顺序轮换），用户决定仍放在分组配置里；
再从「以 matplotlib 写法为公共写法」改为**一套与后端无关的标准词汇**——程序入口只收标准写法，后端各自翻译（用户：「这个标准化就是我们的特点和约定」）。

- **新模块 `src/plotlib/style.py`**（执行者编写，用户更想练习偏逻辑的部分）：
  `check_linestyle / check_marker / check_color` 只校验（类型错 `TypeError`，值错 `ValueError`，信息带写错的值）；
  `translate_linestyle / translate_marker / translate_color(value, backend)` 先校验再翻译。`Backend` 类型与 backend 校验也挪到这里，`formatters.py` 从这里导入。
- **标准写法**（后端写法如 `'--'`、`'o'`、`'tab:red'` 一律报错，不设别名，也不替用户改写）：
  - 线型 `'solid' / 'dash' / 'dot' / 'dashdot'`（Plotly / Origin 的叫法）；自定义虚线 `(实线长, 空白长, ...)`，单位是线宽的倍数，
    matplotlib 翻译为 `(0, (…))`，Plotly 翻译为 `'9px,15px'`（段长 × 线宽，未给线宽用 Plotly 默认 2；偏移量不支持，丢弃）。
  - 标记 `'circle' / 'square' / 'triangle-up' / 'triangle-down' / 'diamond' / 'cross' / 'x'`。
  - 颜色：CSS 颜色名（W3C 148 个，不区分大小写；用 `matplotlib.colors.CSS4_COLORS` 校验，已核对与 Plotly 的颜色名完全相同，所以颜色名、色号两边原样使用）、
    `'#rrggbb'`、RGB 三个 0~255 的整数（matplotlib 翻译为 0~1，Plotly 为 `'rgb(r,g,b)'`）。注意 CSS 的 `'green'` 是 #008000，纯绿叫 `'lime'`。
- **`Group`**：`_check_group` 校验三个样式字段（错误信息补上分组名和字段名）；新增读接口 `linestyle(name) / marker(name) / color(name)`，没写返回 `None`（不打印）；
  `options(name)` 不变，仍返回 `num` 以外全部字段（用户：写错的字段纵向对比一眼能看出来，拼写不检查）。样式字段**不改写**，翻译只在后端渲染时做、不写回。
- **`DataPlotter`**：删掉 `apply_group_linestyle`——写了就应用，两种模式一样；`color` 写了时整组同色。没写时线型用 `plot_style`（合并模式以前写死 `'-'`）。
  优先级：默认样式 < 分组样式 < `lines_formatter`。`plot_style` 默认改为 `'solid'`，也只收标准写法。新增 `_group_style(name)`，`_configure_lines` 只管线宽。
- **formatter 工厂**：`make_lines_formatter` 的 `linestyle / linemarker / linecolor` 走同一套词汇，创建时就翻译（非标准写法立刻报错）；删掉工厂里的局部翻译表。
- 三个脚本、README 改为标准写法；EIS 的 `(0, (3, 5))` 改为 `(3, 5)`。原生回调里的 `ax.grid(linestyle='-')` 不翻译（原则 4）。
- 测试：新增 `tests/test_style.py`（75 个），`test_group.py`、`test_plotter.py`、`test_formatters.py` 改写法并补用例；没有删除测试。
- **重排工具**（用户追加）：`tools/data_reorder_qt.py` 的 `generate_groups_code` 与 `tools/data_reorder_app.py` 的 `_get_linestyle_for_group` 改为生成标准写法
  （顺序不变：`'solid' / 'dash' / 'dashdot' / 'dot'`，之后 `(on, off)`，以前是 `(0, (on, off))`）。新增 `tests/test_groups_code.py`（3 个）：执行生成的代码，用 `Group` 校验。
  同时修了 Tk 版 `_get_ordinal_name`：原来用从 0 开始的序号算后缀，生成 `'1th' / '2st' / '3nd'`；现在按 `index + 1` 算，与 Qt 版一致（补 1 个测试，含 11~13、21~23、111 等特例）。354 passed。
  三个脚本和 `docs/GLOSSARY.md` 里旧工具生成的组名 `'1th' / '2st' / '3nd' / '4rd'` 改为 `'1st' / '2nd' / '3rd' / '4th'`（用户要求；步骤 4.4 起组名会进图例）。
- **遗留（未做）**：① 分组样式目前只对 `plot_kind='line'` 生效，scatter / bar 写了也不应用；② 数据点很密时（EIS）标记会糊成一片，以后可能需要 `markevery` 类参数；
  ③ 其余字段（如 `label`、`linewidth`）暂不处理，留给以后的 `group_style_applyer`（组内精调也由它做）。

#### 4.4 分组计算的结果带上分组名

**读。** `group.py` 的 `_auto_naming`，以及 `tests/test_group_apply.py` 里断言名字的那一行（现在的期望是 `'subtract_S0_S1'`：函数名加样品名）。

**讲。** 分组名（如 `'1st'`）现在只出现在报错信息里，算完就丢了。`DataSet.names` 存的是样品名，
而分组计算的每个结果在后续绘图里就是一个新的样品，它最自然的名字就是分组名。这样图例直接显示用户起的名字。

**定。** 不传 `naming` 时，结果的名字用什么。建议：直接用分组名。传了 `naming` 的行为不变。
这会改变一条已有测试的期望值，新的期望值由用户写。

**已定（2026-11-18）：**
- 范围只改命名：不传 `naming` 时，结果每一列都叫「组名_函数名」（如 `'diff_subtract'`），去掉原来的样品名；`units` 不变。
  保留函数名是用户的决定：图例一眼看出算的是什么，不用每次手改图例（执行者原建议只用组名）。
- `_auto_naming` 增加 `group_name` 参数，`callback` 参数保留（取函数名）。
- 结果仍是新的 `DataSet`，不并回原数据集（会改动输入、样品号要续编、已建绘图器的配色过期、结果单位可能与原数据不同）。
- 给结果配一个新 `Group`（带上组名与样式）放到步骤 4.5（后取消，见 4.5）。
- 用词：`Group.apply` 是「先分组挑好参与计算的样品，再对每组内部计算」，文档统一叫「分组计算」（原来叫「组间计算」，已全部改名，见 `GLOSSARY.md`）。真正的组与组之间的计算目前没有需求，不做。
- 分工：测试期望与 `group.py` 的修改由用户写；执行者验证、更新文档。

**执行记录（2026-11-18，已完成，355 passed）：** 用户改了 `test_subtract_two_groups` 的期望（`'diff_subtract'`），新增 `test_multigroups_ratio`（多个分组各用自己的组名）；
两条测试先失败（旧名 `'subtract_S0_S1'`），用户改 `_auto_naming` 与调用处后通过。执行者更新 `apply` 的 docstring 与 `tests/README.md`。
两个 EIS 脚本没传 `naming`，结果图例从「`rev_camp_样品A_样品B`」变为「`1st_rev_camp`」等。

#### 4.5 分组计算的结果配上新 Group

**讲。** 4.4 之后，结果的第 i 个样品就是第 i 个分组的结果，名字是分组名。再给结果配一个 `Group`
（配置为 `{分组名: {'num': [i], 原来的样式…}}`），结果就能直接交给 `group_plotter`，线型、颜色与原始数据的图一致（如 EIS 比值图里 `1st` 实线、`2nd` 虚线）。

**定。**

| # | 要定的事                         | 建议                                                                                              |
| - | -------------------------------- | ------------------------------------------------------------------------------------------------- |
| 1 | 改 `apply` 的返回值，还是新增方法 | 新增方法（如 `apply_as_group`，返回 `Group`，其 `.dataset` 就是结果）；`apply` 返回值不变，两个 EIS 脚本不用改 |
| 2 | 带过去哪些字段                   | 样式字段 `linestyle / marker / color` 带过去；其余字段（如 `label`）待定                           |
| 3 | 传了 `naming` 时组名还对不对得上 | 组名与配置一致，样品名由 `naming` 决定，两者可以不同                                               |

**已取消（2026-11-18，用户决定）。** 曾按上表建议定下 `apply_as_group`，写测试前用户提出：`DataSet` 本来就不带样式，计算结果一般就是最终要画的东西，很少再分组。
真需要让结果的线型与原始数据图一致时，不加代码也能做到——结果的第 i 个样品就是第 i 个分组的结果，手动套一个 `Group` 即可：

```python
result = groups.apply(rev_camp, select=...)
styled = Group(result, {'1st': {'num': [0], 'linestyle': 'solid'}, '2nd': {'num': [1], 'linestyle': 'dash'}})
DataPlotter(input_dataset=result, groups=styled).group_plotter(merge_groups=True)
```

「每条曲线各用各的样式」作为方向，归入步骤 6 的「作用在绘图计划上的样式调整」，不在 `Group` 上做。

**步骤 4 整体验收。** 分组配置只在 `group.py` 里被解析（`git grep -n "resolve_num" src/` 只剩 `group.py`）；
`scripts/eis_bode.py`、`eis_nyquist.py`、`piezo.py` 不改也能用；用户能说清楚 `Group` 对外回答哪几个问题。

**验收记录（2026-11-18）：**
- `_resolve_num`、`_check_group` 和对 `'num'` 的读取都只在 `group.py`；`InteractivePlotter` 的 `plot_data_groups` 只保存不解析（步骤 5.1 删除）。
- 三个分组脚本：用 `ast` 取出 `data_groups`，按其样品号造小数据集建 `Group`，全部通过校验（组名 `1st`…，线型为标准写法）；6 个脚本的导入检查通过。脚本没有实际运行（会弹窗）。
- 第三条（用户说清 `Group` 对外回答哪几个问题）在步骤 5 开始时由用户口述：分组名与顺序、每组的样品号（有序）、样式与其余字段、配置副本、增删改、分组计算。

---

### 步骤 5：交互图接上 `Group`，两个绘图器共用取数

**讲（2026-11-18 路线调整）。** 原计划是「先具体、后合并」：步骤 5 在 Plotly 里照 `group_plotter` 再写一份分组模式，步骤 6 再对比合并。
规划时分组规则还没定，需要两份具体实现才看得出公共部分。现在情况变了：`Group`、标准样式写法（`style.py`）、配色（`color_positions`）都已公共，
分组规则（去重、组首色、样式优先级）已定并有测试保护——matplotlib 的分组模式就是那份「具体实现」，Plotly 的普通模式也已存在。
再在 Plotly 里抄一份分组规则，等于写一遍再在步骤 6 删掉，也违反 `BACKEND_PLAN.md` 原则 2「模式只实现一次」。
所以改为：步骤 5 只做两个绘图器的公共准备（接上 `Group`、共用取数），分组规则在步骤 6 抽成绘图计划，两个后端按同一份计划画。

**开始前：** 用户口述 `Group` 对外回答哪几个问题（步骤 4 验收第三条）。`Group` 的完整设计和绘图器约定在 `BACKEND_PLAN.md` 2.1 节。

#### 5.1 `InteractivePlotter` 接上 `Group`（步骤 4.2 推迟过来的，机械为主）

1. `InteractivePlotter.__init__` 删掉必填却未用的第一个参数 `plot_data_group`，`plot_data_groups: dict` 改为可选的 `groups: Group | None`，属性名 `self.groups`；
2. 三种情况的检查（`None` → 空 `Group`；非 `Group` → `TypeError`；`groups.dataset is not input_dataset` → `ValueError`）从 `DataPlotter.__init__`
   提取到 `plot_common.py`（建议 `resolve_groups(groups, dataset) -> Group`），两个绘图器共用；
3. 测试仿照 `test_plotter.py` 的 `test_groups_must_be_group_object`、`test_groups_from_other_dataset_raises`、`test_default_groups_is_empty_group` 各写一份；
   更新 12 处 `InteractivePlotter(None, ...)`、`scripts/piezo_interactive.py`、README。

这一步只接上，不画分组（分组绘图在 6.3）。

**执行记录（2026-11-18，已完成，359 passed）：** 全按建议（函数名 `resolve_groups(groups, dataset)`；数据集成为第一个参数；旧参数不留别名）。
- 测试先写、先失败：`test_interactive.py` 仿照 `test_plotter.py` 加 3 条（传字典 `TypeError`、别的数据集 `ValueError`、默认空 `Group` 且建在本数据集上），
  `test_plot_common.py` 加 1 条（合法 `Group` 原样返回，不复制）。
- 用户编写 `plot_common.resolve_groups`，并把 `DataPlotter.__init__` 的三段检查换成一行调用。
- 执行者改 `InteractivePlotter.__init__`：删掉 `plot_data_group`、`plot_data_groups`、`self.group`、`self.groups_config`，新增 `groups` 参数与 `self.groups`；
  更新测试中 12 处 `InteractivePlotter(None, ...)`、`scripts/piezo_interactive.py`（导入检查通过）、README、`tests/README.md`。

#### 5.2 共用取数（原 6.1）

**读。** 两个绘图器的 `_ensure_ready`、`_get_data`、`_get_column_data`：逐行比较，两边是副本（步骤 2 已把参数统一为 `_get_data(sample_idx, channel_x, channel_y, ...)`、
`_get_column_data(sample_idx, channel_idx, plotrange)`）。顺带讲清一个细节：`_get_column_data` 每取一列都要从头扫描所有列。

**定。** 移到 `plot_common.py` 后的函数签名：它们现在读 `self.column`、`self.plotrange`，变成模块级函数后要显式传入什么（建议传 `dataset` 和 `plotrange`）；
`neglog` 取绝对值留在取数里还是交给计划（建议暂留取数里，行为不变）。

**测 / 验。** 有现成测试保护：移动前后 `test_plotter.py`、`test_interactive.py` 全部通过，测试数不减；为新的公共函数各补一条直接测试。

**执行记录（2026-11-18，已完成，364 passed）：** 全按建议，参数顺序按用户写法（`plotrange` 放在 `neglog_*` 之后，调用处用关键字传）。
- 读的发现：`_ensure_ready` 的 `data is None or column is None` 永远不成立（`DataSet()` 的 `data` 是 `np.empty((0, 0))`，`column` 每次现造），
  补全 `plotrange` 也多余（`[:None]` 就是全部行）。所以两边的 `_ensure_ready` 直接删除，不搬；`self.plotrange` 不再被改写成行数。
- 用户编写 `plot_common.get_column_data(dataset, sample_idx, channel_idx, plotrange=None)` 与 `get_xy_data(dataset, sample_idx, channel_x, channel_y, neglog_x, neglog_y, plotrange)`。
  第一版是原样搬过来的方法（仍以 `self` 为第一个参数）——测试暴露出来后改为显式传 `dataset`、`plotrange`。教学点：模块级函数的 `self` 只是普通参数名。
- 测试 5 条（`test_plot_common.py`）：取列的数据 / 名字 / 单位、`plotrange`、样品号或通道号不存在报错（2 种）、`neglog_y` 只影响 Y。
- 执行者删掉两个类的 `_ensure_ready`、`_get_data`、`_get_column_data`，替换 6 处调用（`plotter.py` 5、`interactive.py` 1），删去不再使用的 `numpy` 导入；更新 `GLOSSARY.md`、`tests/README.md`。
- 记录未改：线性扫描（每取一列扫一遍所有列）留到 6.1 考虑；`DataPlotter` 遇到空数据集时不报错、画出空图（`InteractivePlotter` 会报错），两者不一致，属于行为变化，暂不改。

---

### 步骤 6：绘图计划，从分组模式开始（`BACKEND_PLAN.md` 第 3、4 步）

**讲。** 「画几张图、每张图有哪些曲线、每条曲线用什么颜色和样式」这些决定与后端无关，现在写死在 `group_plotter` 的循环里，和 matplotlib 调用缠在一起。
把它抽成一个**不碰任何绘图库的纯函数**，返回绘图计划；两个后端各写一个「按计划画」。分组规则只写一次，测试不用开图窗，Plotly 的分组模式也就几乎不用额外工作。

**已经是公共的（2026-11-18）：** 分组 = `Group`（`BACKEND_PLAN.md` 2.1 节）；配色 = `plot_common.color_positions`；样式 = `style.py` 的标准写法（2.2 节）；
步骤 5 之后还有 `resolve_groups` 和共用取数。绘图计划只读 `Group` 的接口，不读配置字典，也不用 `to_config()`。

计划的大致形状（字段在 6.1 的「定」里由用户列出后确定）：

```python
FigureSpec(key='1st' 或 'main', curves=[...], x_unit, y_unit)
CurveSpec(sample_idx, x, y, label, color_position, group_name,
          style={'linestyle': 'dash', 'color': 'red'})   # 标准写法，翻译留给后端
```

#### 6.1 分组绘图计划（纯函数，用户编写）

**读 + 用户练习。** 读 `plotter.py` 的 `group_plotter`，让用户用自己的话把规则逐条写下来，再对照下面的清单补漏：

1. 没有分组时（空 `Group`，`names == []`），退回普通多线图（一张图，所有样品，默认样式）。
2. 建图之前先校验所有分组（已由 `Group` 在创建时保证，计划里不再校验）。
3. 分离模式：每个分组一张图；颜色按样品。
4. 合并模式：所有分组一张图；被多个分组引用的样品只画一次，用第一个包含它的分组的样式；同一分组的线统一为组首色；柱状图保留各自颜色。
4'. 两种模式共同（步骤 4.3 起）：分组写了 linestyle / marker / color 就应用（仅折线），color 覆盖上面的默认颜色；没写线型用 `plot_style`；`lines_formatter` 最后执行、优先级最高。
5. 结果按「分组名 → {样品号: 曲线}」保存，合并模式的键是 `'main'`。

然后让用户列出：画一条线，matplotlib 和 Plotly 各自需要知道什么（参照 `group_plotter` 与 `plot_plotly_object`）。两边都需要的就是计划的字段。

**定。**

| # | 要定的事 | 建议 |
| - | -------- | ---- |
| 1 | 函数名、位置、签名 | `plot_common.plan_figures(dataset, groups, channel_x, channel_y, plotrange, merge_groups, ...)` |
| 2 | 计划用什么结构 | `dataclass`（字段名在编辑器里有提示，比字典不易写错）；新字段用准确的名字：`sample_idx`、`channel_idx`，不叫 `RowNum`（A.4 第 5 条、`GLOSSARY.md`） |
| 3 | 计划里放不放数据 | 放 X / Y（取数在 5.2 已公共），后端只管画 |
| 4 | 颜色与样式在计划里是什么 | 颜色存色带位置（各后端用自己的色带取色），分组写了 `color` 时存标准写法；样式存标准写法，翻译留给后端 |
| 5 | 「仅折线应用分组样式」这条规则归谁 | 计划照实给出样式，由后端决定能否应用；scatter / bar 的处理属于遗留问题，按原则 5 以后改为明确报错 |
| 6 | 图例显示什么 | 现在是样品名，分组名不出现；计划里的曲线带着 `group_name`，这一步先保持样品名，是否改由用户定 |

**测。** 纯函数测试，不开图窗：分离 / 合并各自的图数和曲线；重叠样品只出现一次且归第一个分组；组首色的色带位置；样式原样带入；空 `Group` 退回一张图。
注意 `Group` 会原地格式化传入的配置，测试里每次新建配置字典（参考 `test_plotter.py` 的 `make_groups`）。

#### 6.2 matplotlib 按计划画

`group_plotter` 和 `plot_objects` 改为「生成计划 → 按计划画」。**旧测试一条不改，全部通过**才算完成——旧测试就是这次重构的安全网。

#### 6.3 Plotly 按同一份计划画（原步骤 5 的目标）

**定。**

| # | 要定的事                   | 建议                                                                                                                 |
| - | -------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| 1 | 先做哪种模式               | 合并模式。它对应一个 Figure，和现有的 `self.asset` 吻合                                                            |
| 2 | 分离模式在 Plotly 里是什么 | 两个选项：返回 `{分组名: Figure}`；或一张图加「按分组切换」的滑块。后者是 `BACKEND_PLAN.md` 里写的方向，建议采用 |

样式用 `style.translate_*(value, 'plotly')` 翻译（自定义虚线要传线宽）；`DataPlotter._group_style` 是 matplotlib 一侧的对照。

**测。** `BACKEND_PLAN.md` 第 3 步的验收：相同的选列和分组配置下，两个后端得到相同的数据、标签和分组顺序。
写成一组对照测试，**同一个 `Group` 对象**分别交给两个绘图器（两者用同一个数据集），再比较。重叠样品只出现一次、组首色、线型各一条测试。

#### 6.4 滑块按分组控制

曲线登记为「样品号 → trace」；「分组名 → 样品号列表」直接向 `self.groups.sample_ids(name)` 要，不另存一份。滑块按分组控制显隐，不再按 trace 的位置。

#### 6.5 之后

- **Y-Y、双 Y 轴迁移。** 一次一个模式，计划里加「左轴 / 右轴」字段；每次迁移后旧测试保持通过。
- **统一结果的形状。** `axesset` 现在四种形状（A.4 第 2 条），需要用户定一种。这会改动读取 `axesset` 的测试。
  其中 `group_plotter` 的形状是 `{分组名或 'main': {'ax', 'fig', 'artists': {样品号: artist}}}`，`artists` 的键在步骤 2 已明确为样品号。
- **建 `backends/`、拆 `formatters.py`。** 前面都稳定后再搬文件。

**方向（记录，不在本步骤做）：作用在计划上的样式调整。** 有了计划，就可以在「画之前」按标准写法改某条曲线的 `style`，两个后端都生效；
现在的 `lines_formatter` 是后端原生回调，只对一个后端有效。以后的 `group_style_applyer`、组内精调、「计算结果各用各的样式」（4.5 取消时的需求）都可以做成这种形式。

验收见 `BACKEND_PLAN.md` 第 3、4 步：旧的 matplotlib 测试行为不变；同一份计划交给两个后端，曲线数量、数据、标签、顺序一致。

---

### 步骤 7：补接口缺口

三项互相独立，每项单独走七个动作。

#### 7.1 `Dataloader` 的接口

**读。** `dataloader.py` 的 `__init__`、`select_data_file`、`load_data` 开头；任意一个脚本的加载部分；`tests/conftest.py` 的 `load_file`。

**讲。** 四个问题：`DATASET_FRACTION` 和 `COLUMNS_PER_DATASET` 是同一个信息，每个脚本都要手算 `1/N`，两者不一致时样品数算错且不报错；
文件路径只能靠弹窗或事后给属性赋值；模块顶层导入 `tkinter`，没有图形界面的环境连数据模块都导入不了；用户取消选择时调用 `exit()`，会把调用它的程序一起退出。

**定。**

| # | 要定的事   | 建议                                                                                    |
| - | ---------- | --------------------------------------------------------------------------------------- |
| 1 | 新的写法   | `Dataloader(columns_per_sample=6).load_data(path=None)`；不传路径才弹窗               |
| 2 | 旧参数     | `DATASET_FRACTION` 删除；`COLUMNS_PER_DATASET` 改名。脚本里约 50 处随之更新（机械） |
| 3 | 取消选择时 | 抛异常。用哪种异常由用户定，要能和「文件读不了」区分开                                  |
| 4 | 扩展名     | 不区分大小写；不支持时报错信息列出支持的格式                                            |

**测。** 直接传路径能加载；取消选择时抛出约定的异常而不是退出；`.CSV` 能读；不支持的扩展名报错信息含扩展名。
**教学点：** `tkinter` 改为函数内导入后，`tests/test_dataloader.py` 末尾用 `monkeypatch` 替换弹窗的那条测试的替换目标会变，让用户自己想清楚为什么。

**一起处理（步骤 2 留下的，2026-11-18 补记）：** `tests/conftest.py` 的 `write_grouped_file(path, units, groups)`、`load_file(path, columns_per_group)`、
`make_dataset(units, groups, fmt)` 里的 `groups` 实际是 `{样品名: 数据行}`，`columns_per_group` 实际是每个样品的列数，随 `columns_per_sample` 一起改名
（`groups` 这个词现在专指 `Group`，不要再用于样品）；`tests/test_dataloader.py` 的 `test_various_group_widths`、`columns_per_group` 参数同理；
脚本里 `INPUT_COLUMNS_PER_DATASET` 旁「每组数据集的列数」的注释改为「每个样品」。
三个分组脚本在数据加载后紧接着写 `groups = Group(data, data_groups)`，改加载写法时保持这个顺序。

#### 7.2 逐样品变换

**读。** 脚本里出现 5 次的三行循环（行号会漂移，搜 `iter('samples')`）：`eis_bode.py` 两处，`eis_nyquist.py`、`tensile.py`、`select_demo.py` 各一处。
步骤 2 之后循环写作 `for dataslice in Selected_data.iter('samples'):`，每次产出一个样品的子数据集。

**定。** 这个能力放在哪、叫什么：`DataTransformer` 的一个参数，还是 `DataSet` 的一个方法。让用户比较两种写法在脚本里读起来哪个更顺。
命名按 `GLOSSARY.md`（「逐样品」用 sample，不用 group）。注意与 `Group.apply`（逐分组计算）区分：逐样品变换的结果仍按原样品号对应，逐分组计算的结果是新样品。

**测。** 新方法的结果与手写循环的结果完全相同（数值、名字、样品号）。**改。** 实现后把 5 处循环换掉。

#### 7.3 公开的列排序

`DataSet._rearrange_columns` 是私有方法，但脚本在用（`eis_bode.py`、`eis_nyquist.py` 各一处，搜 `_rearrange_columns`）。
它按「样品号 → 通道号」排序（测试 `test_rearrange_columns_sorts_by_sample_then_channel`）。
定一个公开的名字（建议 `sort_columns`），改名并更新 2 处脚本、相关测试。机械工作，只需用户定名字。

---

### 步骤 8：让脚本可复现

**讲。** 脚本现在在导入时就直接执行，数据靠弹窗选，所以改了库之后只能逐个手动点一遍。

**改。** 每个脚本的主体包进 `main(path=None)`，末尾加 `if __name__ == "__main__": main()`；路径交给步骤 7.1 的 `load_data(path)`。

**测。** 给每个脚本一条冒烟测试：用 `tests/conftest.py` 的 `make_dataset` 造一份列数相符的小数据（压电 6 列、EIS 8 或 10 列、拉伸 5 列，列标题要和脚本里 `select(...)` 用到的一致），
调用 `main(path)`，断言能跑完、图的数量符合预期。**教学点：** `plt.show()` 在测试里怎么处理。

---

### 步骤 9、10：待定

- **9 工具收敛。** 先由用户决定 Tk 和 Qt 哪一套今后维护，再提取两版共用的逻辑层。届时另行细化。
- **10 桌面程序。** 步骤 6 完成、绘图计划稳定之后再开始，把 `learning/gui` 学到的内容做成真正的应用。

### B.9 暂不做

- `names`、`units` 改名（步骤 1 第 4 项）。
- `plotdataRowNum_*`、`NegLogScale_*` 等旧参数改名：等步骤 6 的新接口用准确的名字，旧接口届时再决定去留。
- 降低 `requires-python`。
- 拆分 `formatters.py`：并入步骤 6.5 之后的「建 `backends/`」。

### B.10 进度

| 步骤                       | 状态   | 完成日期 | 用户做出的决定（与建议不同处） |
| -------------------------- | ------ | -------- | ------------------------------ |
| 1 词汇表                   | 完成   | 2026-11-16 | 全按建议；仓库外没有脚本使用旧名字，步骤 2 不留别名。产出 `docs/GLOSSARY.md` |
| 2 第一层改名               | 完成   | 2026-11-16 | `select` 关键字为精确的 `'samples'`；局部变量、`channel_x/_y`、`iter('channels')`、注释用词一并统一（见步骤 2 执行记录）。基线 209 |
| 3 稀疏样品号配色           | 完成   | 2026-11-17 | 全按建议。`color_positions` 由用户编写；`plotlib/__init__.py` 中导出了它（建议删除，用户暂留）。基线 218 |
| 4.1 `Group` 规范化与校验 | 完成   | 2026-11-18 | 只收完整写法；`options` 代替 `style`；新增 `add` / `set` / `delete` / `to_config`；传入配置原地格式化（见步骤 4.1 执行记录）。基线 236 |
| 4.2 绘图器只认 `Group`   | 完成   | 2026-11-18 | 只接受 `Group` 对象（不收字典）；必须同一数据集；`InteractivePlotter` 推迟到步骤 5；`resolve_num` 并入 `_check_group`（见执行记录）。基线 242 |
| 4.3 样式约定               | 完成   | 2026-11-18 | 新增 `style.py`：一套与后端无关的标准写法（线型 / 标记 / 颜色），后端各自翻译；`Group` 校验并提供 `linestyle / marker / color` 读接口；删除 `apply_group_linestyle`；formatter 与 `plot_style` 同用标准写法；两个重排工具也生成标准写法，并修了 Tk 版序数词后缀（见执行记录）。基线 354 |
| 4.4 结果带分组名           | 完成   | 2026-11-18 | 不传 `naming` 时结果名为「组名_函数名」；「组间计算」改名为「分组计算」（见执行记录）。基线 355 |
| 4.5 结果配新 Group         | 取消   | 2026-11-18 | 计算结果很少再分组；需要时手动套 `Group`（见 4.5）。步骤 4 已验收 |
| 5 交互图接上 Group、共用取数 | 完成   | 2026-11-18 | 路线调整：原步骤 5 的分组绘图移到 6.3。5.1、5.2 全按建议；`_ensure_ready` 删除不搬（见 5.2 执行记录）。基线 364 |
| 6 绘图计划（从分组模式开始） | 未开始 |          |                                |
| 7.1 `Dataloader` 接口    | 未开始 |          |                                |
| 7.2 逐样品变换             | 未开始 |          |                                |
| 7.3 公开的列排序           | 未开始 |          |                                |
| 8 脚本可复现               | 未开始 |          |                                |

---

## C. 整理（已完成，仅作记录）

已于 2026-11-16 完成并提交（`92bbde6`），测试 206 passed。执行者不需要再做任何事，只需知道现状：

- **包**：`src/plotlib/`，`import plotlib`；以可编辑方式安装在系统 Python 3.14（`pip install -e ".[interactive,test,gui,analysis]"`），改代码不需要重装。
- **配置**：`pyproject.toml` 为 src 布局；pytest 的 `pythonpath = ["src", "."]`（`"."` 是为了让测试能导入 `tools/`）；可选依赖 `interactive`、`gui`、`analysis`、`test`。
- **`html_export`**：在 `src/plotlib/html_export.py`，模板在 `src/plotlib/templates/`，随包安装。
- **`scripts/`**：6 个脚本都有 `.py` 扩展名，不再有 `sys.path.insert`；交互图输出到 `output/`（已忽略）。
- **学习材料**：`learning/gui/`、`learning/testing/`。
- **文档**：`README.md`、`tests/README.md`、`docs/BACKEND_PLAN.md` 的路径和导入已对齐；已有 `LICENSE`。
- **未动**：Tk 版工具仍在 `tools/` 原处。

**不运行脚本而检查其导入的办法**（脚本会弹文件选择框）：用 `ast` 解析脚本，只取出 `Import` / `ImportFrom` 节点执行，在项目根以外的目录运行。
步骤 8 完成后脚本可以直接用测试覆盖，就不需要这个办法了。
