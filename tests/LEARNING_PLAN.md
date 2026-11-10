# pytest 测试学习路线图

背景：之前用脚本当测试——运行脚本、看图对不对。脚本适合检查「图好不好看」，
但检查不了「结果对不对」，也没法在每次改代码后快速确认「有没有改坏东西」。
自动化测试补的就是这一块。

最终目标：为 PlotLib 建立一套 `pytest` 一键运行的测试，覆盖数据加载、
分组计算、绘图结果，改代码后几秒钟内就知道有没有回归。

节奏：一步一个概念，每步都在真实项目代码上练习。想学哪一步就说「开始测试 Step N」。

## 进度

- [x] Step 1 — 第一个测试：`assert` 与运行 pytest（`test_group.py`）
- [x] Step 2 — 测试报错：`pytest.raises`（含 `match` 检查报错文字）
- [x] Step 3 — 一个测试跑多组输入：`@pytest.mark.parametrize`（含 `ids` 命名）
- [x] Step 4 — 准备测试数据：fixture 与 `conftest.py`（`test_dataloader.py`、`test_group_apply.py`）
- [x] Step 5 — 测试绘图：Agg 后端，检查 `axesset` 而不是看图（`test_plotter.py`，含 autouse fixture）
- [x] Step 6 — 先写测试再修 bug：用测试复现 `.txt` 读取问题（`xfail(strict=True)` → 修复 → 删标记）
- [ ] Step 7 — 日常使用：VS Code 测试面板、只跑部分测试、看失败信息
- 补充（已用到，可对照代码看）：`monkeypatch` 替换弹窗（`test_dataloader.py` 末尾）、
  覆盖率 `pytest --cov=src --cov-report=term-missing`；全部测试的说明见 `tests/README.md`

## 各步骤内容

### Step 1 — 第一个测试
测试就是一个**以 `test_` 开头的函数**：调用你的代码，用 `assert` 断言结果。
pytest 会自动找到 `tests/` 下所有 `test_*.py` 文件里的 `test_*` 函数并逐个运行。
练习对象：`src/group.py` 的 `resolve_num`（纯函数，输入配置、输出列表，最适合入门）。

### Step 2 — 测试报错
「配置写错时应该报错」也是一种需要被测试的行为。
`with pytest.raises(ValueError):` 表示「这段代码**必须**抛出 ValueError，不抛才算失败」。

### Step 3 — parametrize
同一个测试逻辑、不同的输入，不用复制粘贴 N 个函数，
用 `@pytest.mark.parametrize` 一次列出所有输入。

### Step 4 — fixture 与 conftest.py
很多测试都需要一份数据集。fixture 是「测试的准备工作」，写一次、到处用；
放在 `conftest.py` 里的 fixture 对所有测试文件可见。
测试数据不用真实实验数据（太大、会变、看不出正确答案），而是由 `make_dataset`
工厂 fixture 在 `tmp_path` 里**现场生成**与 tools/ 输出同格式的小 CSV，再用真实的
`Dataloader` 读进来。数值手工设计（S1 = S0 × 2），期望结果可以心算。
一个脚本一种数据 → 换 `units` 和列数即可，不需要为每种数据存一个文件。

### Step 5 — 测试绘图
不弹窗口（Agg 后端），也不比对图片像素，而是检查对象的属性：
`axesset` 里有几个组、线型是什么、图例在哪、`groups_config` 有没有被改。

### Step 6 — 先写测试再修 bug
已知 bug：pandas 3 不再支持 `delim_whitespace`，`.txt` 文件读不了。
先写一个会失败的测试复现它，再修代码让测试通过——以后这个 bug 永远不会悄悄回来。
（复现测试在 Step 4 已经写好：`test_dataloader.py` 里 `[txt]` 两项标了 `xfail(strict=True)`。
修好后它们会「意外通过」而报错，提醒你删掉 `TXT_BUG` 标记。）

### Step 7 — 日常使用
VS Code 侧边栏的测试面板（点一下就跑）、`pytest -k 关键字` 只跑部分测试、
`pytest -x` 遇错即停、读懂失败时的输出。
