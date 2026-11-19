# PlotLib 第三方代码审查

2026-11-20 · 审查对象为 `main` 工作树，基点 `e0799fd`，包含尚未提交的后端重构。审查覆盖 `src/plotlib/`、`tests/` 和 `scripts/`，并核对了两份规划文档、包配置和上游数据归集工具。

**PlotLib 已实现以 DataSet 和 Group 为基础、面向多样品批处理的双后端绘图 API。** 同一份实验数据可以经过选择、分组计算和绘图计划，交给 Matplotlib 或 Plotly。通用性成立于约定好的“样品 × 通道”表格和公共绘图配置。入口可能少读样品，EIS 脚本可能配错频点，部分公共配置切换后端后还会改变图上的量程与标注。

## 四项目标的判定

| 目标 | 当前判断 | 可验证的边界 |
|---|---|---|
| 通用格式入口 | **规定表格布局内已实现。** 相同的两样品数据分别写成 CSV、XLSX、XLS、TXT、DAT，五次读取均得到相同的数值矩阵、样品名、列标题、样品号和通道号。 | 每个样品占固定列宽，第一列标识样品，其余列首行给出通道标题。原始仪器表可先用归集工具选列并拼成此格式。绘图格式也有公共入口，线型、标记、颜色等使用标准写法，原生回调按后端编写。[读取器](../src/plotlib/dataloader.py#L19) · [归集工具](../tools/data_collector.py#L110) · [样式约定](BACKEND_PLAN.md#L103) |
| 以 DataSet、Group 为基础 | **已实现。** DataSet 持有数据及列元信息，Group 维护具名、有序的样品集合。计算和绘图能共用同一个 Group，绘图入口会拒绝来自另一份 DataSet 的 Group。 | Group 可省略。分组计算按配置顺序把样品交给回调，每组产生一个新样品。分组绘图的重复样品归属和顺序由计划层决定一次。[分组计算](../src/plotlib/group.py#L225) · [数据集身份检查](../src/plotlib/plan.py#L23) · [合并规则](../src/plotlib/plan.py#L212) |
| 植根于批量处理 | **单数据集内已实现，多文件分析流程部分实现。** 一次调用能叠加全部样品、按组出图或逐样品出图，Group.apply 能批量计算。 | 上游工具能遍历目录并归集多个文件。六个分析脚本仍各自在模块顶层加载一个输入，逐样品变换重复出现，交互脚本使用固定输出名。连续运行不同输入需要调用方编排。[目录归集](../tools/data_collector.py#L65) · [逐样品迭代](../src/plotlib/dataset.py#L335) · [交互脚本输出](../scripts/piezo_interactive.py#L9) |
| 多后端绘图界面 | **Python API 已实现。** 同一个 DataPlotter 提供多线、分组、逐样品 XY 和双 Y 轴四种方法，分组又有合并和分离两种模式。两个后端读取相同的 FigureSpec，返回相同形状的 DrawnFigure。 | 已有跨后端测试覆盖五个场景的图键、曲线数量、标签、顺序及坐标。最终坐标轴、图例和交互还要各自验收。Plotly 曲线滑块与 HTML 导出可用，分组翻页待做。若“界面”指桌面绘图应用，结构评估将它列为步骤 10。[绘图入口](../src/plotlib/plotter.py#L132) · [计划与结果](../src/plotlib/plot_spec.py#L26) · [跨后端断言](../tests/test_backend_parity.py#L70) · [桌面路线](STRUCTURE_REVIEW.md#L1007) |

## 应优先修复的问题

以下问题在当前工作树通过公开入口或实际脚本复现。优先级按“读取或计算出错误数据”“绘图能否正确表达结果”“批量运行能否完成”判断。

### 1. 读取器会静默丢样品，也可能把上一份数据当作本次结果

两个样品、每样品 49 列，同时正确传入宽度 49 和系数 `1/49`。98 列通过整除检查，但 `int(98 * (1/49))` 得到 1，最终只有第一个样品的 48 个通道。后续维度校验沿用这个错误的样品数，仍会通过。另一个复现是同一 loader 先读合法 CSV，再将 `file_path` 改为 `other.json` 并调用 `load_data()`。未知后缀没有读取分支，缓存的上一个 DataFrame 被重新解析成“成功”的结果。[格式分派和计数](../src/plotlib/dataloader.py#L145) · [事后校验](../src/plotlib/dataloader.py#L195)

**建议并入步骤 7.1。** 以每样品列宽为唯一参数，整除校验后用整数除法计数。每次读取使用本次调用的局部表，对未知后缀立即报错，并接受直接传入的路径。验收至少包括两个 49 列样品都被读入、同一实例依次读 A/坏后缀/B、大小写后缀，以及选文件时取消不会终止宿主程序。Tk 可延至打开对话框时导入，方便仅装有数据处理依赖的环境使用。[当前对话框](../src/plotlib/dataloader.py#L73) · [现有错误格式测试](../tests/test_dataloader.py#L108) · [7.1 设计](STRUCTURE_REVIEW.md#L953)

### 2. 两个 EIS 脚本按行配对，频率变化后仍会输出结果

Bode 的电导率比和 Nyquist 的阻抗差都按行相除或相减，并直接复制第一个样品的频率。假设两个样品分别在频率 `[100, 10]`、`[10, 100]` 上测得 `[1, 10]`、`[2, 20]`。实测 Bode 回调给出比值 `[2, 2]`。按第一个样品的频率顺序配对，结果应为 `[20, 0.2]`。Bode 也没有为结果指定 `naming`，使无量纲比值继承了输入的 `S/cm` 列标题，并被用作轴标题。[Bode 比值](../scripts/eis_bode.py#L135) · [Nyquist 差值](../scripts/eis_nyquist.py#L206) · [单位继承](../src/plotlib/group.py#L376)

**建议在 EIS 回调中处理频率，在 Group 中保留通用计算能力。** 对相同频点的逆序扫描可先对齐。对缺失、重复或不同的频点，在确定实验配对规则前应指出出错的样品对。Bode 显式标出比值无量纲，频率列保留 Hz。回归测试同时断言数值、频率、单位和最终轴标题。

### 3. 无峰样品会中断批处理，失败的拼接还会改变原数据集

单调的损耗角正切序列会返回形状为 `(0, 2)` 的峰表。它有两个通道，只是没有峰。下一次拼接时，`expandata` 因 `self.data.size == 0` 替换了原矩阵，却继续追加旧元数据，最终报维度不匹配。另一条路径是追加同一通道标题冲突的新样品，方法先修改目标再校验，抛错后目标已包含此次追加的列。多峰结果也需要明确选峰规则。测试序列找到幅值 3、4 两个峰，摘要图固定取第 0 行，只画出幅值 3。[数据集拼接](../src/plotlib/dataset.py#L181) · [峰值提取与汇总](../scripts/eis_bode.py#L175)

**建议分两层验收。** 容器按列数区分“尚无列”和“有列、零行”，在更新目标前验证待拼接的数据和元信息。测试首样品无峰、全部无峰，以及失败后原对象可继续正确追加。脚本需明确展示全部峰还是某一代表峰，并为无峰样品定义可读的输出。

### 4. 同名的右轴格式参数在两个后端有不同的作用范围

用 `plot_dual_y` 只给右轴配置范围 10～25、线色绿色。Matplotlib 保持左轴原范围和红线，右侧单独变更。Plotly 把两个 Y 轴都设为 10～25、两条线都设为绿色。原因是 Plotly 按左右轴遍历回调时始终传入整个 Figure，公共工厂再更新全部 Y 轴或全部 Scatter。另一条边界是 Matplotlib 的双 Y 布局仅创建左图例，对右侧调用图例字号工厂时会收到 `None` 并报错。[Plotly 回调分发](../src/plotlib/backends/plotly_backend.py#L89) · [轴工厂](../src/plotlib/formatters.py#L207) · [线工厂](../src/plotlib/formatters.py#L293) · [Matplotlib 图例](../src/plotlib/backends/matplotlib_backend.py#L158)

**建议把规划中的“目标轴”提升为正确性修复。** 公共工厂应能定位具体轴和所属曲线，原生整图回调继续接收 Figure。用左右量程相差一个数量级的样例，分别断言两侧的范围、线色，并让不支持的图例目标给出明确结果。

### 5. Matplotlib 对象属性正确时，最终图上的刻度和图例仍可能不可读

- **负号刻度丢失数值。** 两点负 X 数据使用 `plot_xy(neglog_x=True)`，调用 Agg 的 `canvas.draw()` 后，X 刻度文字全部为 `-`。当前包装函数直接调用原 ScalarFormatter，原 formatter 没有收到本轮刻度位置。双 Y 图同时启用两个 X 标志还可能重复添加负号。应在实际绘制后断言数字及负号，并只处理一次共享 X 轴。[负号刻度实现](../src/plotlib/backends/matplotlib_backend.py#L230) · [现有负号测试](../tests/test_plotter.py#L419)
- **更新线样式会把图例移出画布。** 在 1000 × 800 像素的图上使用 `lines_formatter` 后，图例左下角从约 `(757, 383)` 移到 `(468882, 244011)`。重建图例时，已经转换过的包围框又被当作锚点转换。两个 EIS 脚本的分组图都使用这一入口。验收需要同时检查图例句柄样式和渲染后的图例位置。[图例重建](../src/plotlib/backends/matplotlib_backend.py#L220) · [当前样式断言](../tests/test_plotter.py#L170) · [Bode 分组图](../scripts/eis_bode.py#L118)

## 对照 backend plan 和 structure review 的进度

| 原定事项 | 当前工作树 | 建议验收点 |
|---|---|---|
| 步骤 1～5、6.1～6.7，统一分组、计划、结果和后端 | 架构主干已成立。旧 InteractivePlotter 已移除，`import plotlib` 实测未加载 pyplot 或 Plotly。4.5“结果自动配 Group”已明确取消。 | 保留“入口 → 计划 → 两个渲染器”分工，在公共工厂和后端补上上述行为断言。[结构确认](STRUCTURE_REVIEW.md#L894) · [后端工厂](../src/plotlib/backends/__init__.py#L12) |
| 6.8，Plotly 分组翻页 | **待实现。** 分离模式当前每组一个独立 Figure。`add_slider` 控制单张图中的曲线，尚无 `add_group_slider`。旧入口的 10 条 xfail 随迁移删除，进度总表仍保留旧标记说明。 | 按已定设计将每个 FigureSpec 作为一页。用交叠分组验证页内顺序和样式、初始可见性、滑块掩码和两类滑块的误用提示。跨后端按页比较，不再假设两边原生 Figure 数量相同。[6.8 验收约定](STRUCTURE_REVIEW.md#L913) · [当前滑块](../src/plotlib/plotter.py#L147) · [现有对照测试](../tests/test_backend_parity.py#L77) |
| 7.1～7.3，数据入口、逐样品变换、公开排序 | **仍待完成。** 当前 4 个脚本共有 5 处 `iter('samples')` 循环手工拼接，两个 EIS 脚本还直接调用私有列排序。现有 Group.apply 已能做组内多样品运算。 | 7.1 同时修正读取正确性。7.2 用手写循环作参照，验证逐样品变换保留原样品号、顺序、列标题和数值，包括零行结果。7.3 给现有排序一个公开入口。[7.2 与 7.3](STRUCTURE_REVIEW.md#L978) · [Bode 调用](../scripts/eis_bode.py#L158) · [Nyquist 调用](../scripts/eis_nyquist.py#L184) |
| 8，脚本可复现 | **人工控制输入后可跑，尚无常规脚本测试。** 脚本在导入时开始工作，交互脚本会向当前目录的 `output/output.html` 写入。 | 提取可传路径的 `main`，给有导出的脚本传输出路径，保留现有交互用法。用仓库测试运行六个样例，再串行处理两个输入，检查结果可区分。[步骤 8](STRUCTURE_REVIEW.md#L996) · [测试范围说明](../tests/README.md#L322) |

## 其余值得排期的改进

- **Plotly 最低版本。** 包声明 `plotly>=6.1`，后端初始化模板时无条件写入 `minorloglabels`。上游文档标明该字段从 6.3 开始提供。本轮在 7.1.0 运行，低版本结论来自依赖声明、调用路径和上游版本说明。可提高下限或为旧版本省略该字段，给声明的最低版本加一次构造和绘图测试。[包配置](../pyproject.toml#L19) · [模板](../src/plotlib/backends/plotly_backend.py#L207) · [Plotly 版本说明](https://plotly.com/python/log-plot/#controlling-minor-log-labels)
- **批量取列随样品数二次增长。** 每样品两通道、只生成普通多线计划时，50、100、200 个样品分别产生 5,053、20,103、80,203 次列视图访问。每条线都从头寻找 X、Y，计算色带位置时还对每个样品重建集合。可在每次建计划时建立一次“样品号、通道号 → 列”的索引并复用有序样品表。用访问次数和输出等价性验收，避免硬件计时干扰。[取数与配色](../src/plotlib/plan.py#L19)
- **选样和改单位会绕过部分约束。** 只有样品 0 时，`select('samples', [0, 7])` 成功返回 0。直接改一个样品的 `Column.unit` 也能打破同通道列标题一致的约定，绘图仍用第一列标题标整条轴。建议明确选择缺失编号时的语义，为统一修改通道标题或拒绝冲突提供公开路径。[选择逻辑](../src/plotlib/processor.py#L165) · [单位 setter](../src/plotlib/dataset.py#L50) · [计划取轴标题](../src/plotlib/plan.py#L66) · [术语约定](GLOSSARY.md#L22)
- **补齐公共样式的适用范围。** 分组 `color` 已用于线、散点和柱，分组 `marker` 用于散点时仍被忽略。Plotly 的线工厂给纯散点指定 `linecolor` 时改的是隐藏的线色，点仍显示原色。两种后端的轴工厂还都会写死刻度宽度 3。建议按画法核对实际可见的属性，并让工厂缺省值保留构造器的 `tick_width`。规划中的 Plotly 上 X 轴和跨后端组合 formatter 可独立排期。[分组样式](../src/plotlib/backends/plotly_backend.py#L79) · [刻度宽度](../src/plotlib/formatters.py#L137) · [散点格式](../src/plotlib/formatters.py#L279) · [已知待办](BACKEND_PLAN.md#L188)

## 本次验证记录

- **仓库测试。** Windows，Python 3.14.3、Matplotlib 3.10.8、Plotly 7.1.0。运行 `python -m pytest -q -p no:cacheprovider -ra`，指定独立临时目录，得到 **428 passed**，无跳过或预期失败。其中 6 项通过 Kaleido 实际渲染 Plotly.js 以检查轴界。另以 `--cov=plotlib --cov-branch` 重跑仍全部通过，语句与分支合并覆盖率为 **96%**。现有文件格式参数化测试覆盖 CSV、XLSX、TXT，本轮额外使用小型旧版二进制 XLS 和空白分隔 DAT 验证相同布局。[格式用例](../tests/test_dataloader.py#L61) · [渲染用例](../tests/test_formatters.py#L225)
- **从文件到两种图。** 写入三样品 CSV，以有交叠的 `[2, 0]` 与 `[0, 1]` 建组，按书写顺序计算“第二个减第一个”。将结果 DataSet 直接绘图，两边实际 artist/trace 都得到 `[-7, -14]`、`[3, 6]`。Matplotlib 完成画布渲染，Plotly 加单曲线滑块后生成 HTML。这条链同时核对了样品角色、派生元数据和曲线数值。
- **六个现有脚本。** 在临时目录写真实 CSV，运行原脚本，仅替换文件选择和 `plt.show()`，Matplotlib 使用 Agg。两类 EIS 各用 18 个样品，压电和选择示例各 10 个，拉伸 2 个。Bode、Nyquist、压电静态、拉伸分别生成 **13、56、49、2** 张图。选择示例完成计算，压电交互脚本写出并读回含 **10 条 trace、10 档滑块**的 HTML。脚本验证覆盖文件读写和图对象，使用合成数据，未人工操作桌面窗口或浏览器中的侧栏联动。

**建议顺序。** 先修复丢样品、EIS 错配与误标、零行拼接，并用最终渲染结果锁定刻度、图例和右轴行为。随后按 6.8 的既定设计实现分组翻页，将步骤 7～8 的路径入口和脚本测试接入日常回归。现有计划层和两个渲染器可以承载这些修改。
