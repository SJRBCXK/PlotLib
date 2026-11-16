# PlotLib 结构评估与整理方案

> 评估日期：2026-11-16，基线提交 `5cb8d4d`，测试基线 `python -m pytest` → **206 passed**。
> 评估范围：`src/`、`scripts/` 逐行阅读；`tools/`、`gui/`、`tests/`、配置与文档看了结构和接口。
> 本文分三部分：A 评估结论与问题清单；B 下一步开发方向；C 整理任务。
> **状态（2026-11-16）**：包改名、`html_export` 入包、依赖声明已完成并验证（见 C.0）；C.3 ~ C.5 交给执行者（Opus 5.5）。
> 执行者只做 C.3 ~ C.5。A、B 是背景，其中 B 的内容不在本次执行范围内。
> A 部分描述的是基线提交时的状态，文件路径按当时的 `src/xxx.py` 书写，这些文件现在位于 `src/plotlib/xxx.py`。

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

> 第 1 ~ 5 条已解决（见 C.0）。第 6、7 条要改函数行为，留在 B 部分第 5 步。

| # | 问题 | 证据 | 后果 |
|---|---|---|---|
| 1 | 可导入的包名叫 `src`，发行名叫 `plotlib`，`import plotlib` 不存在 | `pyproject.toml` 的 `include = ["src*"]`；全项目都是 `from src.xxx import` | `src` 是通用目录名，不是包名；安装后会在环境里占用顶层名字 `src` |
| 2 | 包当前**没有安装**，导入靠三种机制各自补救 | `pip show plotlib` 找不到（根目录的 `plotlib.egg-info` 是残留）；pytest 靠 `pythonpath = ["."]`；5 个脚本靠 `sys.path.insert`；库文件 `src/interactive.py:5-6` 自己也 `sys.path.insert` | 换个目录运行就可能失败；库代码修改 `sys.path` 会影响调用方 |
| 3 | `scripts/eis_bode.py` 没有 `sys.path.insert`，其余脚本都有 | 在 `scripts/` 目录下 `import src` 实测 `ModuleNotFoundError` | `python scripts/eis_bode.py` 直接运行会在导入处失败 |
| 4 | `tools/html_export.py` 是库代码，却放在不打包的 `tools/` 里 | 被 `scripts/piezo_interactive` 导入、被 `tests/test_html_export.py` 测试；`tools/` 没有 `__init__.py`，也不在打包范围 | 安装后用不到；与同目录的独立 GUI 程序性质完全不同 |
| 5 | 实际用到的依赖没有声明 | `scipy`（`eis_bode.py` 的 `find_peaks`）；`PySide6`（`tools/*_qt.py`、`gui/`、`tests/test_data_reorder_qt.py`）；`pytest-cov`（`tests/README.md` 推荐的命令） | 新环境装完跑不起来，且看不出缺什么 |
| 6 | `import src` 必须有 Tk | `src/dataloader.py:3-4` 在模块顶层导入 `tkinter`，`src/__init__.py` 又导入 `Dataloader` | 无界面环境下连数据模块都导入不了；与「Plotly 按需导入」的做法不一致 |
| 7 | 库函数里调用 `exit()` | `src/dataloader.py:100`，用户取消选文件时直接退出进程 | 被 GUI 或其他程序调用时会把整个程序带走 |

### A.3 目录职责混杂

> 已解决：`html_export.py` 及模板移入包内；根目录残留的 `plotlib.egg-info/` 和空目录 `Aligned_Results/` 已删除。其余见 C.3 ~ C.5。

| 目录 | 现状 | 问题 |
|---|---|---|
| `scripts/` | 5 个实验分析脚本 + 1 个调试脚本 `select_test.py` + 1 个空文件 `SMU.py` + `assets/` | `piezo_interactive`、`tensile` **没有 `.py` 扩展名**，编辑器、类型检查、按 `*.py` 的搜索都看不到它们；`select_test.py` 不是测试却叫 test；`SMU.py` 是 0 字节 |
| `tools/` | 4 个独立 GUI 程序（Tk 与 Qt 各一对）+ 库代码 `html_export.py` + 它的模板 | GUI 程序共 3670 行，比整个 `src/`（3170 行）还多；Tk 版与 Qt 版的逻辑层是复制的（`data_collector` 两版逻辑层逐行相似度约 70%）；工具里的类叫 `DataLoader` / `DataPlotter`，与库里的 `Dataloader` / `DataPlotter` 几乎同名但毫无关系 |
| `gui/` | PySide6 学习步骤 `step1~4` + `widgets/plot_canvas.py` + 学习路线图 | 是教程，却占着顶层的 `gui/` 这个产品位置；将来真正的桌面程序没地方放 |
| `tests/` | 测试 + `README.md` + `LEARNING_PLAN.md` | 学习路线图混在测试目录；`README.md` 写的是 161 个测试，实际 206 个，文件对照表缺 4 个测试文件 |
| 根目录 | `matplotlibrc`、`Aligned_Results/Data/`、`plotlib.egg-info/`、`.coverage` | `matplotlibrc`（`backend: TkAgg`）只在「当前目录是项目根」时生效，行为取决于从哪里启动；`Aligned_Results/` 是空的遗留目录；`scripts/piezo_interactive` 把 `output.html` 写到当前目录，而 `.gitignore` 没有忽略它 |
| `docs/` | 只有 `BACKEND_PLAN.md` | — |

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

| 方法 | 键 | 值里的曲线字段 |
|---|---|---|
| `plot_objects` | `'main'` | `'artists'`：列表 |
| `group_plotter` | 组名或 `'main'` | `'artists'`：`{组号: artist}` |
| `subplotter_yy` | 组号 | `'artist'`：单个 |
| `subplotter_xyy` | 组号 | `'artist_Y1'` / `'artist_Y2'`，`'ax1'` / `'ax2'` |

没有稳定的结果约定，测试和后处理（滑块、导出）只能按方法分别写。这正是「绘图计划」要解决的问题。

**3. 分组配置把数据语义和 matplotlib 样式放在一个字典里**

`{'num': [0, 1], 'linestyle': (0, (3, 5))}` 中，`num` 是与后端无关的数据选择，
`linestyle` 的元组写法是 matplotlib 专有的，Plotly 无法翻译。
另外 `resolve_num` 定义在 `group.py`（组间计算模块），`plotter.py` 为了解析配置去导入计算模块。
这个约定需要在 `BACKEND_PLAN.md` 第 3 步（交互图补分组模式）**之前**定下来，否则会被原样复制进第二个后端。

**4. `formatters.py` 两个后端写在同一个函数体里**

三个工厂都是 `if backend == "matplotlib": … 否则 Plotly …` 的结构，471 行里两套实现交错。
`XxxFactory.create` 是只有一个静态方法的类，外面再套一层 `make_xxx(**kwargs)`，编辑器因此看不到参数列表。
参数名不统一：坐标轴用 `custom_formation`，线条和图例用 `custom_formations`。
matplotlib 坐标轴回调把刻度线宽写死为 3（`formatters.py:134`、`146`），会覆盖 `DataPlotter(ticker_width=...)`。

**5. 名字与实际含义不符**

| 名字 | 实际含义 |
|---|---|
| `DataSet.names` | 样品（组）名，同一组的各列相同 |
| `DataSet.units` | 列标题，如 `"Zs'(ohm)"`，是「物理量 + 单位」；`select("Zs'(ohm)")` 和坐标轴标题用的都是它 |
| `plotdataRowNum_x` / `_y` | 组内**列**序号，不是行 |
| `NegLogScale_x` / `_y` | 对数据取绝对值，并在刻度文字前加负号；不设置对数刻度 |
| `DataSet.status` | 注释写 `empty, selected, processed`，实际取值是 `empty` / `loaded` / `written`，且 `processor.py:232` 用它做流程判断 |

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

## B. 下一步开发方向

按顺序推进，每一步都有可运行的终点。除第 1 步外都由用户主导，延续 `BACKEND_PLAN.md` 的「先具体、后合并」。

1. **整理外壳（本文 C 部分）。** 不改任何行为，只解决 A.2、A.3。地基部分已完成，剩余的交给执行者。
2. **修稀疏组号配色，作为第一块公共代码。** 写一个函数「完整组号集合 → {组号: 颜色位置}」，两个绘图器都调用它。
   这是 `BACKEND_PLAN.md` 第 0 步的遗留，也是最小的一次「提取公共部分」练习，先补两个会失败的测试再改。
3. **定下分组配置的样式约定**（A.4 第 3 条），然后做 `BACKEND_PLAN.md` 第 3 步。
   建议：公共线型只用 `'-'`、`'--'`、`':'`、`'-.'` 四种名字；元组写法视为 matplotlib 原生设置，Plotly 遇到时明确报错（符合原则 5）。
4. **`BACKEND_PLAN.md` 第 4 步：绘图计划。** 建议从最简单的 `plot_objects` 一种模式开始，
   先让两个后端共用取数（A.4 第 1 条的三个方法），再逐个模式迁移；顺带把 `axesset` 统一成一种形状（A.4 第 2 条）。
5. **补接口缺口**（小而独立，可穿插进行）：
   - `Dataloader`：只保留「每组列数」一个参数，`load_data(path=None)` 直接接收路径；`tkinter` 改为用到时再导入；取消选择时抛异常而不是 `exit()`；
   - 提供「逐组变换」的公开方法，替代脚本里重复 5 次的循环；
   - 把 `_rearrange_columns` 改成公开方法。
6. **让脚本可复现。** 每个脚本包成 `main(path=None)`，可传入文件路径；用测试里的合成数据给每个脚本加一个「能跑完」的冒烟测试。
7. **工具收敛。** 确定 Tk 与 Qt 哪一套是今后维护的，把两版共用的逻辑层提取出来，另一套归档。
8. **桌面程序。** 多后端稳定后，再把 `learning/gui` 学到的内容做成真正的 `gui/` 应用。

暂不建议做：批量重命名公共接口（A.4 第 5 条）；降低 `requires-python`；拆分 `formatters.py`（等第 4 步建 `backends/` 时一起拆）。

---

## C. 整理任务

### C.0 已完成的部分（2026-11-16，已验证，尚未提交）

地基部分已经做完，执行者**不要重做**，只需知道现状：

| 内容 | 结果 |
|---|---|
| 包改名 | `src/*.py` → `src/plotlib/*.py`（`git mv`）；`tests/` 11 个文件和 `scripts/` 6 个文件的导入已改为 `from plotlib...` |
| `html_export` 入包 | `tools/html_export.py` → `src/plotlib/html_export.py`；模板 → `src/plotlib/templates/ppt_fit_shell.html`；`pyproject.toml` 已加 `package-data` |
| 库内路径补丁 | `src/plotlib/interactive.py` 里的 `sys.path.insert` 已删除 |
| `pyproject.toml` | `packages.find` 改为 `where = ["src"]`；pytest `pythonpath = ["src", "."]`；新增可选依赖 `gui`（PySide6）、`analysis`（scipy），`test` 增加 `pytest-cov` |
| 安装 | 已执行 `python -m pip install -e ".[interactive,test,gui,analysis]"`，任意目录下 `import plotlib` 可用 |
| 清理 | 删除了残留的根目录 `plotlib.egg-info/` 和空目录 `Aligned_Results/` |

已做的验证：

- `python -m pytest` → 206 passed；
- 构建出的安装包里只有 `plotlib/` 的 9 个模块和 `templates/ppt_fit_shell.html`，装到临时目录后在项目外能导入并生成页面；
- 在项目外、不借助任何 `sys.path` 补丁，6 个脚本的全部 import 语句都能执行成功（包括原先会失败的 `eis_bode.py`）；
- 代码中已搜不到 `from src`、`import src`、`tools.html_export`。

尚未改动、留给下面任务的：文档里的旧路径和旧导入（`README.md` 14 处 `from src.`，`tests/README.md`、`docs/BACKEND_PLAN.md`、两份学习路线图里的 `src/…` 路径）；
脚本里已经没有作用的 `sys.path.insert`；A.3、A.5 列出的其余问题。

### C.1 给执行者的说明

- 环境：Windows 10，系统 Python 3.14.3（无虚拟环境），项目根 `g:\Code\Python\PlotLib`，分支 `main`。`plotlib` 已以可编辑方式安装。
- **目标：只移动文件、清理脚本、更新文档。不改 `src/plotlib/` 中任何函数的行为，不改公共接口的名字和参数，不改 `pyproject.toml` 的打包与 pytest 配置。**
- 每个任务结束后运行 `python -m pytest`，结果必须是 **206 passed**（数量不变）。数量变了说明有测试没被收集到，先查原因。
- 移动文件一律用 `git mv`，保留历史。
- 每个任务做完停下来，向用户说明改了什么；是否提交由用户决定，不要自行提交或推送。
- 修改代码时用编辑工具逐处修改，让用户能看到 diff；不要用脚本批量替换后只报告结果。
- 代码注释和文档保持中文，风格与现有文件一致。
- 不在范围内：`BACKEND_PLAN.md` 第 3、4 步；合并 Tk / Qt 工具；修改脚本里的绘图与计算逻辑；B 部分第 2 步以后的任何内容。
  发现本文没列出的 bug，记下来告诉用户，不要顺手修。

### C.2 目标结构

`src/plotlib/` 与 `tools/` 已是最终状态；标 ← 的是待办。

```text
PlotLib/
├── pyproject.toml
├── README.md                       ← 任务 3 更新
├── matplotlibrc
├── src/
│   └── plotlib/                    # 唯一的可安装包：import plotlib
│       ├── __init__.py
│       ├── dataset.py
│       ├── dataloader.py
│       ├── processor.py
│       ├── group.py
│       ├── plotter.py
│       ├── interactive.py
│       ├── formatters.py
│       ├── html_export.py
│       └── templates/ppt_fit_shell.html
├── scripts/                        # 按实验的分析脚本
│   ├── eis_bode.py
│   ├── eis_nyquist.py
│   ├── piezo.py
│   ├── piezo_interactive.py        ← 任务 1：补扩展名
│   ├── tensile.py                  ← 任务 1：补扩展名
│   ├── select_demo.py              ← 任务 1：原 select_test.py
│   └── assets/piezo_panel.html
├── tools/                          # 独立 GUI 预处理工具
│   ├── data_collector.py
│   ├── data_collector_qt.py
│   ├── data_reorder_app.py
│   └── data_reorder_qt.py
├── learning/                       ← 任务 2：学习材料，不属于产品代码
│   ├── gui/                        #   原 gui/ 整个目录
│   └── testing/LEARNING_PLAN.md    #   原 tests/LEARNING_PLAN.md
├── docs/
│   ├── BACKEND_PLAN.md             ← 任务 3：只更新路径
│   └── STRUCTURE_REVIEW.md
└── tests/
    └── README.md                   ← 任务 3 更新
```

`backends/`、`plot_spec.py` 现在**不要建**，`BACKEND_PLAN.md` 明确要求到第 4 步再建。

### C.3 任务 1：整理 `scripts/`

1. `git mv scripts/piezo_interactive scripts/piezo_interactive.py`，`git mv scripts/tensile scripts/tensile.py`。
2. `git mv scripts/select_test.py scripts/select_demo.py`。
3. 删除 0 字节的 `scripts/SMU.py`（`git rm`）。
4. 删除 5 个脚本里的 `sys.path.insert(...)` 及随之不用的 `sys`、`Path`、`os` 导入
   （`piezo_interactive.py` 里 `Path` 仍用于定位 `assets`，要保留；`eis_bode.py` 本来就没有这段）。
5. 删除未使用的导入；删除已经不需要的 `# type: ignore`（删之前确认该行确实不再报类型错误，拿不准就保留）。
6. `eis_bode.py` 顶部的文件说明改成与内容相符（Bode 图、组间电导比、损耗峰）。
7. `piezo_interactive.py` 的输出改到 `output/output.html`，写入前创建目录；`.gitignore` 增加 `output/`。
8. 不改任何绘图调用、计算函数和参数值。`eis_nyquist.py` 里两个相同的 formatter 保留原样。

验收：206 passed；`python -m compileall -q scripts` 无错误；`git grep -n "sys.path.insert"` 无结果。
脚本会弹出文件选择框，**不要实际运行它们**。确认导入正确的办法：只取出每个脚本的 import 语句执行（用 `ast` 解析后筛出 `Import` / `ImportFrom` 节点），在项目根以外的目录运行。

### C.4 任务 2：学习材料归位

1. `git mv gui learning/gui`，`git mv tests/LEARNING_PLAN.md learning/testing/LEARNING_PLAN.md`。
2. 更新两份路线图以及 `step*.py` 文件说明里的运行命令和路径
   （`python gui/step1_hello.py` → `python learning/gui/step1_hello.py`；路线图里的 `src/group.py` 等 → `src/plotlib/group.py`）。
3. `learning/gui/step4_matplotlib.py` 的 `from widgets.plot_canvas import ...` 依赖「脚本所在目录在导入路径中」，移动后仍然成立，不用改。

验收：206 passed；`git grep -n "gui/step"` 的结果都指向 `learning/gui/`。

### C.5 任务 3：文档对齐

1. `README.md`：
   - 安装：`pip install -e .`，并列出可选依赖 `interactive` / `gui` / `analysis` / `test` 各自的用途（以 `pyproject.toml` 的注释为准）；
   - 所有示例的导入改为 `from plotlib...`；快速开始补上 `import matplotlib.pyplot as plt`；
   - 「项目结构」按 C.2 重写；
   - 「依赖」改为 Python >= 3.14，并与 `pyproject.toml` 一致；
   - 增加一小节介绍 `InteractivePlotter`、滑块和 `write_fit_html`，内容以 `scripts/piezo_interactive.py` 为准，不要编造未实现的功能；
   - 用一句话说明根目录的 `matplotlibrc`（`backend: TkAgg`）只在「从项目根目录启动」时生效。
2. `tests/README.md`：
   - 测试数量改为实际值；
   - 「文件与被测模块」表里的 `src/xxx.py` 改为 `src/plotlib/xxx.py`，并补上 `test_interactive.py`、`test_html_export.py`、`test_data_reorder_app.py`、`test_data_reorder_qt.py`；
   - 命令里的 `--cov=src` 改为 `--cov=plotlib`；依赖说明改为 `pip install -e ".[test]"`。
3. `docs/BACKEND_PLAN.md`：只更新文件路径（`src/` → `src/plotlib/`）。
   **架构、原则、进度表的内容不要改**（该文件开头有明确要求）。可在第 7 节补一句：matplotlib 一侧在组号不连续时也有配色错误（见本文 A.4 第 1 条）。
4. `LICENSE`：README 声称 MIT 但没有许可文件。是否添加、署名写什么，问用户，不要自行决定。

验收：206 passed；README 里的每条 import 都能执行成功；`git grep -nE "from src[. ]|cov=src"` 无结果。

### C.6 需要用户确认的事项

| 事项 | 默认做法 | 说明 |
|---|---|---|
| 删除 `scripts/SMU.py` | 删除 | 0 字节的空文件 |
| Tk 版工具 `data_collector.py`、`data_reorder_app.py` | 原地保留，不动 | 若确认今后只维护 Qt 版，可移到 `tools/legacy_tk/`，同时更新 `tests/test_data_reorder_app.py` 的导入 |
| `LICENSE` | 不动，询问用户 | — |
