# PlotLib 工作计划

> 2026-11-23 起的唯一计划与记录文档，由原 `STRUCTURE_REVIEW.md`（结构评估与分步开发指南）和 `BACKEND_PLAN.md`（多后端绘图规划）合并整理而成。
> 用词按 `GLOSSARY.md`：样品（一次测量）、通道（样品内的列）、分组（若干样品的集合）。
> 新的规划、决定、执行记录都写在这里：规划写进第 4、5 节，做完把记录追加到第 7 节，并更新顶部状态和第 5 节进度表。

**当前状态（2026-11-23）**：plotlib 1.0.0，最新提交 `0098a2f`，591 passed（工作区，未提交），pyright 0 错误，API 文档零警告。
第三方只读审查的 14 项已修（见第 7 节最后一小节），未提交。
**进行中**：第 4 节「柱状图、散点图」，按 4.7 的顺序做。第一步（样式对象和 spec 按画法拆开、`plot_scatter`）已完成，未提交；
**下一步**：第二步柱状图 `plot_bars`；之后是步骤 8「让脚本可复现」。

---

## 1. 协作方式

用户的要求：**逻辑与架构修改必须让用户知晓并学习清楚，不能在用户没弄懂的情况下把改动做完。**机械性、可自动验证的工作直接做。
6.6b 起的分工是「用户定、执行者写、用户看 diff」。

每个逻辑小节按七个动作走，一次只走一个小节：

| 动作 | 做什么 |
| ---- | ------ |
| 讲 | 用几句话说明这一节解决什么问题、为什么现在做 |
| 读 | 指出要读的代码（文件 + 函数名），回答问题 |
| 定 | 列出要用户决定的事，给出建议和理由，等用户定下来；用户改了主意就按用户的来，并写回本文 |
| 测 | 先写测试，先确认它在改之前是失败的 |
| 改 | 实现；每处行为变化都讲清原因 |
| 验 | `python -m pytest -q`、`pyright src/plotlib tests`、`sphinx-build -W --keep-going -b html docs/api docs/api/_build/html`，逐条对照验收条件 |
| 记 | 更新本文顶部状态、第 5 节进度表，把执行记录追加到第 7 节 |

其他约定：

- 设计取舍属于用户：给一次理由，之后按用户的决定执行；不连环提问，测试期望一次列好再确认。
- **测试要克制**（2026-11-23 用户定）：「能保证运行就行」。一类行为一条测试，场景在测试里循环，不逐个 parametrize；
  边界和回归作为同一测试里的断言保留。重构途中旧测试是安全网；结构变了以后，测已消失结构或多层重复的测试经用户同意清理。
- 修改代码用编辑工具逐处修改，让用户能看到 diff；注释和文档用中文。文档字符串按 numpydoc（英文节标题、中文正文），不写开发历史。
- 不运行 `scripts/` 里的分析脚本（会弹文件对话框）；检查导入用 ast 只执行 `import` 节点。步骤 8 完成后改用测试覆盖。
- 是否提交、何时提交由用户决定，执行者不提醒、不自己提交（用户明确要求时除外）。
- 不跨步骤，不顺手修本文没列出的问题；发现了就记下来告诉用户。本文与代码不一致时以代码为准，并告诉用户。

## 2. 目标与原则

**目标**：同一份数据、同一套绘图模式（普通叠加、分组、逐样品关系图、双 Y 轴，以及第 4 节的柱状图、散点图），
可以选择不同 backend 渲染：matplotlib 出静态图，Plotly 出交互图 / HTML。只保留一个绘图器作为数据与模式入口，配多个渲染实现。

**原则**（原 BACKEND_PLAN 第 3 节，未经重新讨论不要改动）：

1. **职责分层**：取数 → 绘图 → 格式化，三者分开。不要把取数和渲染绑在一起。
2. **模式只实现一次**：分组顺序、重复样品去重、样式归属、曲线属于哪张图 / 哪个轴，都在公共层（绘图计划）决定，不在每个 backend 各写一份。
3. **滑块是画完之后的可选交互**，不是一种新的绘图模式。它只控制已有曲线的显隐，不重新取数，也不做 Python 端计算。
4. **公共配置翻译，原生回调不翻译**：常用设置用样式对象（标准写法），由各 backend 翻译；
   `ax.spines`、`FuncFormatter`、`fig.update_*` 这类原生操作保留为各后端自己的回调，使用原生回调就表示这部分不保证跨后端兼容。
5. **扩展能力显式检查**：某个 backend 不支持的功能要明确报错，不要悄悄忽略或改成别的效果。
6. **回调统一约定**：接收对象并原地修改，返回值忽略。执行顺序固定为：默认格式 → 用户 formatter → 保存结果。
7. **翻译不只是改参数名**：例如 Plotly 对数轴的 `range` 用 log10 值，需要 backend 换算；`scaler` 只改变刻度显示，不等于把数据乘以系数。

**补充原则**（2026-11-23 用户要求，依据当天几轮第三方审查补充；11-24 按审查「修复收益与维护成本」一节放宽，
用户定：边缘情况不追求面面俱到。同样未经重新讨论不要改动）：

**先看值不值得修**：按使用频率、出错后果、修复成本决定投入，下面 8～14 都在这个前提下执行。

- 会**静默**算错、读错、画错的（数值、单位、样品归属、图上的数据）：即使少见也修，并核对最终结果、跑全量测试；
- 改一两行就能堵住的边界（如 `np.asarray` 收标量、空 `tickformat`）：顺手修，一条针对性断言即可；
- 罕见组合要加层次、专用流程或依赖库的私有接口才能做到的：先问有没有实际用途；没有就用后端原生默认行为，
  在文档字符串里写明适用范围，不为它长期背维护负担。收窄已公开的行为要当接口变更处理。

8. **以实际状态为准**：回调先读后端对象的实际状态，不按我们记的推断；前面的回调（含原生回调）改过什么都要认。
   后端会丢掉的信息（如空心后丢的填充色）才由我们另记一份，作为补充。逐点的值（颜色数组）整组读写，不只看第一个。
9. **写法的三种含义分清**：字段没写 = 保持现状；写了值 = 改成这个值；明确写「自动」（如 `limits` 的 `None` 端）= 交回后端自动计算，
   之后加的数据也要能撑开。任意先后组合回调时都按这三条解释；空值（如 `tickformat=''`）与没写相同。
10. **两个后端效果对齐**：常用的公共写法在两个后端效果一致；后端语义不同（单侧范围、线形标记）由翻译层补齐。
    补齐成本高的（见上面「先看值不值得修」）用后端原生行为，差异写进这个选项的文档字符串，或按原则 5 报错。
11. **尽早报错**：单个字段的错误在创建样式或翻译时报（格式字符串先试格式化一次、尺寸拒绝 NaN 和无穷大），
    不拖到渲染、保存图片或导出时才报；选项之间的组合冲突（如 Plotly 对数轴的 `tickformat` 与 `minor_labels='short'`）
    在回调都执行完、最终配置确定后再查。
12. **失败不留半成品**：一次操作要么全部生效，要么什么都不变。先在局部算好、校验通过再写回（`select`、`update_attributes` 的列索引）；
    画图出错时关掉这次建的图窗，`self.figures` 保持上一次的结果。
13. **现读不缓存，入口同校验**：持有数据集的对象每次读数据集的当前状态（先 `ensure_updated`），不在创建时复制引用；
    同一件事的不同入口（按位置取列、按 `Column` 取列）走同一套校验，校验各自读取的数据集。
    位置、样品号、通道号分清：负数位置在入口换成真实位置；`father_idx` 记直接来源、`initial_idx` 记原始位置；
    分配新样品号时在源数据集当前的、实际输入的、已有结果的样品号里查重。
14. **数值稳健**：计算前提升到足够的精度（整数、单精度、`complex64` → 双精度，精度更高的不降），保留类型的语义（复数取模），
    避免中间步骤溢出或下溢（按阶数选缩放）。改数值算法时，用随机数据与原公式对照。

对应的测试约定（仍守「测试要克制」，验收深度按风险定）：

- 写测试前先写清一条能手算的样例：输入、预期输出、出错时抛什么、失败后对象是什么状态；
- 用有区分度的数据：稀疏、无序的样品号，数值不对称的列，不同单位（如样品号 0、3 再追加 4）；
- bug 大多藏在组合里：每种回调留一条组合测试，在测试里循环几种「先 A 再 B」（含原生回调夹在中间、逐点数组）；
- 断言用户看得到的结果：涉及刻度文字、偏移、格式的先 `canvas.draw()` 再检查，Plotly 的轴范围用 Kaleido 渲染核对；两个后端都测；
- 回归测试要先确认在修复前是失败的；覆盖率只用来找没跑到的分支，验收看输出和失败后的状态。

**用户偏好**（设计时参照）：依赖显式（`functools.partial`）；数据流在调用处看得见；接口统一；可调的渲染值要显式（如 dpi），不写死魔法数；
自由传参，不给特殊情况加多余限制；结构一致性（一个主题一个样式对象）。

**暂不做**：

- 不自动翻译任意 matplotlib 回调；不引入 Dash 或自定义 JavaScript（如滑块的任意区间筛选）；
- 不把峰值汇总图这类特殊绘图强行纳入普通多线模式；
- `names`、`units` 改名；降低 `requires-python`；
- DataSet 的元数据不合成「元数据表」（用户 2026-11-23 定：平行列表是有意的设计，见 3.3）。

## 3. 当前架构

> 2026-11-20 定稿（步骤 6），之后的增补随记录更新。以后改结构要重新讨论。

```text
Dataloader → DataSet → 按需 select / by / DataTransformer / Group.apply
        │              │
        │              ▼
        │        Group(dataset, config)：分组的唯一主人（3.1）
        ▼              ▼
DataPlotter(dataset, groups, channel_x, channel_y, 外观样式对象, figsize, dpi, backend)   ← 唯一入口（plotter.py）
   plot_multiline / plot_groups / plot_scatter / plot_xy / plot_dual_y：计划 → _render → figures；add_slider / add_page_slider（Plotly）
        │ ① 生成计划（plan.py：规则；每份计划取一次 dataset.column_positions）
        ▼
   list[FigureSpec]（plot_spec.py：约定）
   图：key、名字、单位、neglog、版式；线：数据、标签、色带位置、样式（标准写法）、画法、左 / 右轴
        │ ② backend.draw(spec, figsize, formatters, figure_formatter)
   ┌────┴─────────────────────┐
   ▼                          ▼
MatplotlibBackend          PlotlyBackend          （backends/：只管渲染，两份逐段对应）
   读：layouts.py（排版预设）、style.py（翻译层：标准写法 → 原生值，按 dpi 换算单位）
   用：matplotlib_styles.py / plotly_styles.py（把样式用到图上，后端与格式化器共用）
        │ ③ 交回 DrawnFigure(spec, fig, axes, artists)
        ▼
DataPlotter.figures = {FigureSpec.key: DrawnFigure}；取线 figures[key].artist(样品号, 轴)
   （多张计划时 Plotly 用 draw_pages 画成一个 Figure 多页；add_slider 一条线一档，add_page_slider 一页一档）
```

| 模块 | 职责 | 依赖 |
|---|---|---|
| `dataset.py` | `DataSet`（数值矩阵 + 平行的列元数据列表）、`Column` / `ColumnList` 视图；检查点 `update_attributes`、使用时自动检查 `ensure_updated`、列位置索引 `column_positions`（3.3） | numpy |
| `dataloader.py` | `Dataloader(columns_per_sample=N).load_data(path=None)`；取消选择抛 `NoFileSelected`；读入后走检查点，状态记 `'loaded'` | dataset、pandas |
| `processor.py` | 选列 `DataProcessLayer`（`select` / `by` / `getdata`）、变换 `DataTransformer`（`apply` / `Norm`） | dataset |
| `group.py` | `Group`：分组的唯一主人，校验、读写接口、`apply` 分组计算（3.1） | dataset、style |
| `plotter.py` | `DataPlotter`：唯一入口。选计划函数、定默认尺寸、把用户回调按轴打包、交给后端、存结果；不导入绘图库 | plan、plot_spec、backends |
| `plan.py` | 规则：`plan_multiline_figures` / `plan_scatter_figures`（共用 `_plan_samples`）/ `plan_xy_figures` / `plan_dual_y_figures`，以及 `color_positions`、`resolve_groups`、取数（按列位置索引）；画法只决定建哪种 spec、怎么读分组样式（`_KINDS`） | plot_spec、DataSet、Group |
| `plot_spec.py` | 约定：样式对象 `LineStyle` / `ScatterStyle` / `AxisStyle` / `FrameStyle` / `LegendStyle` / `TickStyle` 与库默认 `DEFAULT_*`；曲线 `CurveBase` → `LineSpec` / `ScatterSpec`（并集 `Curve`，画法由类型决定）、`FigureSpec`、`DrawnFigure`、`Appearance`、`AxesFormatter`；不含规则、不导入绘图库 | numpy |
| `layouts.py` | 排版预设：每种版式的图例、边框、各轴（刻度格式、着色）、边距；`resolve_*` 是唯一写叠加顺序的地方（库默认 < 预设 < 全局 < 分组 < 格式化器） | plot_spec |
| `style.py` | 翻译层：线型 / 标记 / 颜色 / 图例位置 / 刻度格式 / 刻度的标准写法 → 各后端原生值；磅、英寸按 dpi 换算 | plot_spec |
| `backends/` | `get_backend(name, appearance, cmap)`；`MatplotlibBackend`、`PlotlyBackend`：`draw`（一张计划一张图），Plotly 另有 `draw_pages`、`add_slider` / `add_page_slider`；`matplotlib_styles.py`（应用翻译好的样式）、`plotly_styles.py`（收样式对象、应用时才翻译：dpi、对数轴边界、`apply_log_format`）；只依赖约定 | plot_spec、layouts、style |
| `formatters.py` | 用户回调工厂 `make_axes_formatter(x=, y=, frame=, ticks=, custom=)`、`make_lines_formatter(LineStyle, custom=)`、`make_legend_formatter(LegendStyle, custom=)`、`combine_formatters`；按 `backend` 参数区分 | style、*_styles |
| `html_export.py` | 把 Plotly Figure 导出成随窗口缩放的 HTML | plotly |

依赖只朝一个方向：入口 → 计划 → 约定 ← 后端；后端不认识 `DataSet`、`Group`、`DataPlotter`，也不依赖规则。
`import plotlib` 不加载 Plotly 和 pyplot：后端在 `get_backend` 里用到时才导入。

公开接口的命名（2026-11-20 统一）：构造参数 `dataset`、`channel_x` / `channel_y`、样式对象 `lines` / `frame` / `legend` / `ticks`、`dpi`、`backend`；
方法名「plot_ + 版式」；方法参数 `neglog_x` / `neglog_y`（双 Y 轴再有 `neglog_x2` / `neglog_y2`）、`plot_kind`（双 Y 轴 `plot_kinds`）、
双 Y 轴 `left=(X, Y)` / `right=(X, Y)`、按轴回调 `axes_formatter` 等（右轴 `right_axes_formatter` 等）、整图回调 `figure_formatter(fig, axes)`。

**文档**：文档字符串（numpydoc）→ `docs/api/`（Sphinx + pydata-sphinx-theme）。`docs/api/sync_api.py` 在构建前从 `pyproject.toml` 读版本、
把 `plotlib.__all__` 新增的名字登记进 `reference.rst`；push 到 main 后 `.github/workflows/docs.yml` 构建（`-W`）并发布到 GitHub Pages。

### 3.1 分组输入约定（`Group`，2026-11-18 定稿）

分组（若干样品组成的、有名字的集合）只由 `Group` 解析和校验；后端只通过下面的接口读取，不自己解析配置字典。

**配置写法（唯一一种）**：`{分组名: {'num': 样品号, 其余字段...}}`。`num` 可写 int / list / tuple / range / ndarray；
样式字段 `linestyle` / `marker` / `color` 只收标准写法（3.2），创建时校验、原样保存；其余字段不检查，原样保存。
简写 `{'A': [0, 1]}` 不支持，报 `TypeError` 并提示正确写法。字段拼写不检查（`options` 返回全部字段，写错一眼能看出）。

**创建时**：逐个分组校验（是否字典 → 有无 `num` → 类型 → 元素是否整数 → 是否为空 → 是否重复 → 是否在数据集中），类型错报 `TypeError`、值错报 `ValueError`，
信息带分组名。样品号每次现查（先自动检查数据集），不存快照。**原地格式化**（用户决定）：把每个分组配置里的 `num` 改为 `list[int]`。

**读接口**（都返回副本）：`names`、`for name in group`、`sample_ids(name)`（保持书写顺序，顺序就是角色）、`options(name)`、
`linestyle` / `marker` / `color(name)`、`to_config()`。**修改接口**（先校验全部再改，返回 `self`）：`add` / `set` / `delete`。
**计算**：`group.apply(callback, select, naming)`，每个分组的结果成为新样品，不传 `naming` 时名为「组名_函数名」。

**绘图器的约定**：`groups` 只接受 `Group` 对象，且必须建在同一个数据集上（`is`）；不传时为空 `Group`，退回普通多线图。
配色用 `color_positions(dataset.sample_idx)`，按整个数据集排名一次；合并模式的组首色 = `sample_ids(name)[0]` 的颜色。
样式优先级：默认 < 预设 < `DataPlotter` 全局 < 分组 < `lines_formatter`。图例显示样品名（计划里的曲线带 `group_name`，改不改由用户定，至今未改）。

### 3.2 样式的标准写法（`style.py`，2026-11-18 定稿，11-20 样式对象化）

程序入口（样式对象、分组配置、formatter 工厂）只接受一套与后端无关的标准写法，不认识就报错，也不替用户改写；后端渲染时由翻译层翻译。

| 字段 | 标准写法 | matplotlib | Plotly |
|---|---|---|---|
| 线型 | `'solid'`、`'dash'`、`'dot'`、`'dashdot'` | `'-'`、`'--'`、`':'`、`'-.'` | 同名 |
| 自定义虚线 | `(实线长, 空白长, ...)`，正数、偶数个，单位是线宽的倍数 | `(0, (…))` | `'9px,15px'`（段长 × 线宽） |
| 标记 | `'circle'`、`'square'`、`'triangle-up'`、`'triangle-down'`、`'diamond'`、`'cross'`、`'x'` | `'o'`、`'s'`、`'^'`、`'v'`、`'D'`、`'+'`、`'x'` | 同名 |
| 颜色 | CSS 颜色名、`'#rrggbb'`、RGB 三个 0~255 的整数 | 原样 / ÷255 | 原样 / `'rgb(r,g,b)'` |

加新词：在 `style.py` 的表里加一行，两个后端各写一个原生值。样式对象的字段默认 None 表示「不改，沿用下面一层」。

### 3.3 数据集约定（`DataSet`，2026-11-23）

- **平行列表是有意的设计**（用户定）：`names`、`units`、`sample_idx` 等可以整列替换、分步修改，中途允许暂时不一致；
  `update_attributes()` 是统一的检查点：补全编号、重算派生属性（`channel_idx`、`num_samples`、`column_positions`）、校验长度和「同一通道各样品单位相同」。
- **使用时自动检查**（用户在 5 种做法里选定）：检查点记下快照（列数 + 7 个元数据列表的副本）；使用数据集的入口先调用 `ensure_updated()`，
  列表变了就自动执行完整的检查点。入口：`column_positions`、`Column.channel_idx`、各 `plan_*`、`Group` 校验、`select` / `getdata`、
  `DataTransformer()`、`iter` / `for sample in dataset`、`sort_columns`。**新增使用数据集的入口时，开头要先调用 `ensure_updated()`。**
- **列视图是带保护的入口**：`column.sample_idx = …`、`column.unit = …` 改完即校验，失败时恢复值和状态；直接改列表是不校验的自由入口。
- **列位置索引** `column_positions`：只读 `{(样品号, 通道号): 列位置}`，在检查点里原地重建；随用随取（直接改了列表、还没被使用前视图是旧的）。
- 快照不用哈希：CPython 里 `hash(-1) == hash(-2)`；快照占数值矩阵的比例约 7 ÷ 行数，与列数无关。

## 4. 下一阶段：柱状图、散点图（2026-11-23 设计）

> 用户提出：在脚本复现之前先加完整的柱状图、散点图，顺便检验现在结构的兼容性和扩展性。下面是和用户讨论后定下的设计。

### 4.1 现状

- 计划里的线已带 `kind`（`'line'` / `'scatter'` / `'bar'`），两个后端都能画；颜色对三种画法都生效。
- 问题：样式只有 `LineStyle`，散点只取标记、柱状只取颜色（靠 `STYLE_FIELDS_BY_KIND` 过滤），柱宽、边框、空心点都没地方写；
  多个样品的柱在同一 x 叠在一起；线条回调对柱图在 matplotlib 报 `AttributeError`（11-20 记下的「柱状图、散点图的格式化从 `draw` 里独立出去」）。

### 4.2 样式对象按画法拆开（用户同意）

```python
LineStyle(width, color, linestyle, marker, marker_size)            # 折线，不变
ScatterStyle(marker, size, color, edge_color, edge_width, filled)  # 散点：filled=False 画空心点
BarStyle(color, edge_color, edge_width, width, ...)                # 柱状图：width 是柱宽占间距的比例；误差棒线宽、端帽长度
```

连带：计划里每条线的样式按画法存对应的对象；分组配置按画法检查字段；线条回调按画法分派（11-20 的待办随之完成）。

### 4.3 spec 按画法拆开（用户同意）

```python
CurveBase(label, group_name, color_position, axis)                 # 共有：图例、分组、配色、所在的轴
LineSpec(CurveBase):    sample_idx, x, y, style: LineStyle
ScatterSpec(CurveBase): sample_idx, x, y, style: ScatterStyle, sizes=None, colors=None   # 第三通道映射只在这里
BarSpec(CurveBase):     key, categories, heights, errors=None, series_index, series_count, mode, style: BarStyle
```

- 画法由 spec 的类型决定，`kind` 字段去掉；后端用 `match` 按类型分派，取代 `_plot_data` 里按字符串分派。
- **柱的摆放（用户定 B）**：计划决定「画什么」（类别、系列顺序、模式、高度、误差、柱宽比例），后端决定「怎么摆」：
  Plotly 翻译成 `barmode` / `bargap` 由它自动排（隐藏系列后自动重排）；matplotlib 后端用一个小函数算偏移
  （第 i 个系列偏移 `(i - (n-1)/2) × 柱宽`）和堆叠底部（前面系列的累加），误差棒画在柱中心。两后端由对照测试保证一致。
  matplotlib 3.11 新增的 `Axes.grouped_bar` 是临时接口、只有并排、无误差棒，先不用（第 6 节待办）。
- **扩展性检验点**：`BarSpec` 的一组柱可能不是「一个样品」，所以用通用的 `key: int | str`（样品号、通道号或组名）。
  现在默认「一条线 = 一个样品号」的三处要检查：`DrawnFigure.artist(样品号)`、Plotly 滑块按样品切换、按样品取色。

### 4.4 柱状图：一张表（用户同意）

柱状图是一张二维表：x 轴上的**类别**是一维，每个类别里并排或堆叠的**系列**是另一维，格子是高度 + 误差。两维从数据集已有的
**样品**、**分组**、**通道**里挑，DataSet 不加字段：类别名用 `names`，通道的标签用 `unit`（也是图例文字），误差来自另一个通道或多行统计。

| x 轴 | 系列（图例） | 例子 |
|---|---|---|
| 样品 | 通道 | 每个样品一组柱，比较它的各项指标 |
| 通道 | 样品 | 每个单位一组柱，比较各样品 |
| 通道 | 分组 | 每个单位一组柱，比较各组（组内跨样品汇总） |
| 分组 | 通道 | 每个组一组柱，比较它的各项指标 |

```python
DataPlotter(data, groups=groups).plot_bars(
    channels=[0, 1, 2],             # 画哪几个通道（标签）
    x='channel', series='group',    # 两维各取什么：'sample' | 'group' | 'channel'
    errors='std',                   # 'std' / 'sem'（由多行或组内样品算出），或 {值通道: 误差通道}
    reduce='mean',                  # 一列多行时怎么得到一个值：'mean' | 'first' | 函数
    mode='group',                   # 'group' 并排、'stack' 堆叠（重叠模式不做，用户定可被堆叠取代）
)
```

- 用到分组时跨样品汇总：先把每个样品的多行汇总成一个值，再在组内跨样品汇总；误差默认是组内样品之间的标准差。
- 摆放按 4.3 的 B：计划给类别、系列序号、模式、柱宽比例，Plotly 用原生 `barmode`，matplotlib 后端自己算偏移和底部。
- `plot_bars` 是新方法，不放进 `plot_kind`：取数方式和曲线完全不同。
- 自己用 `select` / 变换器预先算出数据集（如加权平均）再画，仍然可以，作为库没有提供的汇总方式的兜底。

### 4.5 散点图：第三通道映射（用户同意）

`plot_multiline(plot_kind='scatter', size_channel=..., color_channel=...)`：大小、颜色由另一个通道决定，只绑定在 `ScatterSpec` 上；
颜色映射需要新增颜色条（`FigureSpec` 记录颜色条标题 = 颜色通道的单位、色带、范围）。不写这两个参数时就是普通散点。

### 4.6 轴线位置（蝴蝶图四象限）：用回调，库不加功能（用户定）

已验证现有 `make_axes_formatter(custom=[...])` 足够：

```python
def origin_axes(ax, fig):                       # matplotlib：轴线移到原点，刻度跟着移
    for side in ('left', 'bottom'):
        ax.spines[side].set_position('zero')
    ax.spines[['top', 'right']].set_visible(False)

def zero_lines(axis, fig):                      # Plotly：零线分四象限，刻度留在外框，缩放正常
    fig.update_xaxes(zeroline=True, zerolinecolor='black', zerolinewidth=1.5)
    fig.update_yaxes(zeroline=True, zerolinecolor='black', zerolinewidth=1.5)
```

Plotly 没有「轴线放在数据值上」的功能（只能在范围写死时按比例放，缩放不跟随）。做完柱状图、散点图后把这两段写进 README 的示例。

### 4.7 顺序

1. ✅ 样式对象和 spec 按画法拆开（结构改动，后两项依赖它），线条回调按画法分派（记录见第 7 节最后一小节）。
   用户定：散点走单独的 `plot_scatter` / `plan_scatter_figures`（与折线共用规则）；曲线方法去掉 `plot_kind`，
   双 Y 轴保留 `plot_kinds`（`'line'` / `'scatter'`）；分组配置每种画法只读自己用得上的字段；
   线条回调和散点回调解耦（`make_lines_formatter` / `make_scatter_formatter`）；默认外观等方法跑通后再加；
2. 柱状图：`plot_bars`、一张表的计划、并排 / 堆叠、误差棒、类别刻度；`BarStyle` 和柱状图回调按第 2 节原则 8～14 设计
   （回调先读实际状态、三种写法分清、两个后端对齐、尽早报错），测试期望里列出组合场景；
3. 散点图：`ScatterStyle` 的完整样式、第三通道映射、颜色条；
4. README 示例（含蝴蝶图回调）、API 文档登记。

**第二步柱状图的细节（2026-11-23 列出，⏳ 待用户确认；括号里是备选）**：

- 接口：`plot_bars(channels, x='sample', series='channel', reduce='mean', errors=None, mode='group', axes_formatter, bars_formatter, legend_formatter, figure_formatter, legend_title)`。
  ① `x` / `series` 必须恰好一个是 `'channel'`，另一个是 `'sample'` 或 `'group'`（4.4 表的 4 种），其余报错（或改成单参数 `by=`）；
  ② 默认 `x='sample', series='channel'`；③ 用到样品维时画全部样品、忽略分组，写 `'group'` 时才用分组，没有分组报错；
  ④ `plotrange` 生效（汇总只取前几行）；⑤ 不加 `neglog`。
- 汇总：⑥ `reduce` 默认 `'mean'`，可选 `'median' / 'first' / 'last' / 'max' / 'min'` 或函数（或默认 `'first'`）；⑦ 忽略 NaN（拼接补的 NaN）；
  ⑧ 分组时两步：样品内多行 → 一个值，组内跨样品 → 平均；样品同属两组时各算一次。
- 误差：⑨ `'std'`：分组时是组内样品之间，否则是同一列多行之间，`ddof=1`，只有一个值时不画（或 `ddof=0`）；⑩ `'sem'` = std / √n；
  ⑪ `{值通道: 误差通道}` 按同一 `reduce` 汇总，分组汇总时用它报错（或组内取平均）；⑫ 堆叠时误差画在每段顶端（或不允许）；⑬ 只做对称误差。
- `BarStyle`：⑭ `color`、`edge_color`、`edge_width`（磅）、`width`（一个类别里全部柱子占间距的比例，默认 0.8）；
  ⑮ `error_color`（默认黑）、`error_width`（磅）、`capsize`（磅）；⑯ 花纹、透明度以后再加。分组配置只读 `color`；`make_bar_formatter` 对应 `bars_formatter`。
- 显示：⑰ 颜色：系列是样品 → 样品色；是分组 → 组色，没写用组首样品色；是通道 → 按通道排名取色带（或后端默认配色）；
  ⑱ 类别刻度文字是样品名 / 组名 / 通道单位，旋转用回调；⑲ Y 轴标题：一个通道时是它的单位，多个通道时不写（或拼接）；
  ⑳ 堆叠时正负分开叠（Plotly `'relative'`，matplotlib 照规则算底部）；㉑ 新版式 `'bars'`：图例图内右上、无框、Y 轴不预设格式、默认 (10, 8)。
- 结果：㉒ 一张 `'main'` 图，`figures['main'].artist(key)` 按系列的键取（样品号 / 通道号 / 组名）（或另加 `series(key)`）；㉓ 滑块暂不支持，报错说明。

每一步先写测试（一类行为一条），用户看 diff。用户手头暂时没有柱状图、散点图的真实数据：做的时候用 conftest 的小数据，
真实数据到手后再按实际格式核对 4.4 的「通道 = 标签」理解。

## 5. 路线与进度

| 步骤 | 内容 | 性质 | 状态 |
| ---- | ---- | ---- | ---- |
| 1 | 定词汇表：样品、通道、分组 | 讨论 | ✅ 2026-11-16（`docs/GLOSSARY.md`），基线 206 → 209 |
| 2 | 第一层改名：`group` → `sample` | 机械 | ✅ 2026-11-16 |
| 3 | 稀疏样品号配色 `color_positions` | 逻辑，小 | ✅ 2026-11-17，218 |
| 4 | `Group` 成为分组的唯一主人（4.1 校验、4.2 绘图器只认 `Group`、4.3 样式约定、4.4 结果带分组名；4.5 取消） | 逻辑，中 | ✅ 2026-11-18，355 |
| 5 | 交互图接上 `Group`，两个绘图器共用取数 | 机械 + 逻辑 | ✅ 2026-11-18，364 |
| 6 | 绘图计划与后端（6.1 ~ 6.8）：计划 → 两个后端 → 统一入口；之后第三方审查修复、`TickStyle`、样式对象化 | 架构，大 | ✅ 2026-11-20，520（`55576fb`） |
| 7 | 补接口缺口：`Dataloader`、逐样品遍历、`sort_columns`；之后全面评审、1.0 发布前复审 | 逻辑，小 | ✅ 2026-11-20，564，**plotlib 1.0.0**（`5b14df5`） |
| 1.0 之后 | 文档字符串 numpydoc + API 文档；Plotly 对数轴格式；API 文档发布与同步；DataSet 列视图校验、列位置索引、使用时自动检查；测试精简 | 逻辑 + 文档 | ✅ 2026-11-23，573（`0098a2f`） |
| **柱 / 散** | **第 4 节：样式对象与 spec 拆分、柱状图、散点映射** | 架构 + 逻辑 | ⏳ 第一步 ✅（573，未提交）；第二步柱状图未开始 |
| 8 | 让脚本可复现（见下） | 逻辑，小 | 未开始 |
| 9 | 工具收敛（Tk / Qt）：先由用户决定维护哪一套，再提取共用逻辑层 | 待定 | — |
| 10 | 桌面程序：把 `learning/gui` 学到的内容做成真正的应用 | 待定 | — |

**步骤 8：让脚本可复现。** 脚本现在导入即执行、数据靠弹窗选，改了库之后只能逐个手动点。
改法：每个脚本的主体包进 `main(path=None)`，末尾 `if __name__ == "__main__": main()`，路径交给 `load_data(path)`。
测试：每个脚本一条冒烟测试，用 conftest 的 `make_dataset` 造列数相符的小数据（压电 6 列、EIS 8 或 10 列、拉伸 5 列，列标题和脚本里 `select(...)` 用到的一致），
调用 `main(path)`，断言能跑完、图的数量符合预期。教学点：`plt.show()` 在测试里怎么处理。

**测试基线变化**：206 → 209 → 218 → 236 → 242 → 350 → 354 → 355 → 359 → 364 → 370 → 374 → 385 → 426 → 428 → 438 → 451 → 472 → 484 → 507 → 520 → 539
→ 547 → 550 → 549 → 564（1.0.0）→ 572 → 605 → 573（2026-11-23 精简）。

各步骤里用户做出的、与建议不同的决定，见第 7 节对应小节和附录 B 的原进度表。

## 6. 待办与遗留问题

- **柱状图、散点图的格式化从 `draw` 独立出去**（11-20 记录）→ 已并入第 4 节。
- **子集与全集颜色一致**（暂不做）：配色按本次绘图的数据集排名，从全集挑部分样品单独画时颜色与画全集时不同；这是有意的默认（子集对比度更好）。
  需要时给绘图器加可选参数（如 `color_reference=全集样品号`）。
- **Plotly 上轴 `x2`**；参照脚本做「前端模板」。
- **Plotly 次刻度文字字号**：Plotly 没有这个属性，只能在导出的 HTML 里用 JS 改；真需要时作为 `html_export` 的增强。
- **标记过密**：数据点很密时标记会糊成一片，以后可能需要 `markevery` 类参数；分组配置可考虑支持 `width` / `marker_size`。
- **作用在绘图计划上的样式调整**（方向）：画之前按标准写法改某条曲线的样式，两个 backend 都生效（现在的 `lines_formatter` 是原生回调，只对一个 backend 有效）。
- **多线图预设的 Y 轴 `'{y:.2f}'`**：Y 轴改成对数轴时同样会把小数写成 0.00（X 轴已于 11-23 去掉预设格式，Y 轴用户定暂不改）。
- **超大列数**：到十万、百万列时，DataSet 的 Python 列表和逐列循环会成为瓶颈，届时元数据改用 NumPy 数组、校验向量化（11-23 实测记录）。
- **发布**：PyPI 发行名；sdist 是否打包测试。
- **logit / symlog 次刻度的私有接口（⏳ 待用户定）**：11-23 审查 ⑪ 的修复借了 matplotlib 私有的 `axis._scale`。
  按第 2 节「先看值不值得修」可以放宽成：这类轴开次刻度时不动定位器，保留刻度类型的原生默认（默认绘图配置下的问题照样解决），
  代价是「先关次刻度再打开」在这类轴上打不开，写进文档字符串。建议放宽；改动是删掉 `_scale_minor_locator`、测试改一条。
- **来自不同数据集的列混用时样品号怎么解释（未定）**：`apply(column=[...])` 的列可以来自别的数据集，两边的样品 0 未必是同一个样品；
  现在按「样品号相同就是同一样品」处理。审查建议把规则写进接口说明和测试，遇到实际用法再定。
- **matplotlib `Axes.grouped_bar`**（3.11 新增，2026-11-23 查）：目前是临时接口（provisional），只有并排、没有堆叠和 `yerr`；
  转正并支持堆叠后，可考虑把 matplotlib 后端的柱子摆放换成它（届时依赖要升到 `matplotlib>=3.11`）。

---

## 7. 执行记录

> 以下是原 `STRUCTURE_REVIEW.md` B 部分的逐步记录，原样保留（只合并了文档）。其中的引用按下面对照：
> 「本文」「B.0」→ 本文第 1 节；「B.1」「B.10」→ 第 5 节和附录 B；「B.9」→ 第 2 节「暂不做」；
> 「`BACKEND_PLAN.md` 第 N 节 / 第 N 步」→ 第 2、3 节（原则、架构）和附录 C（推进方式与早期进度）；「A 部分」「C 部分」→ 附录 A、附录 B。

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

**执行记录（2026-11-18，已完成，370 passed）：** 「定」全按建议。
- 「读」：用户口述 `group_plotter` 的规则，两处更正——合并模式是**先到先得**（不是最后一次）；分组样式两种模式都应用（不只是分离模式）。
  另补：分离模式下同一样品出现在多张图里；坐标轴单位取每张图最后一条线；退回普通绘图时 `artists` 是列表（6.5 统一）。
- 讨论「重复样品听谁的」：这是多对多关系里的单值属性冲突，没有标准答案（先到先得 / 后到覆盖 / 报错 / 按属性分别判定 / 画多次 / 让用户选）。
  用户决定保持先到先得（重构不改行为）；把归属单独写成一步（`owner.setdefault`），以后换策略只改这一步。组首色只看本组配置（局部性）。
  其他策略（如 `on_duplicate='first'/'error'/'repeat'`）记为以后的选项。
- 讨论「计划和 `go.Figure` / `Axes` 是否重复」：计划是领域层的决定（样品、归属、色带位置、标准样式），后两者是渲染层；计划要保持薄，不放坐标轴、刻度、字体。
- 测试 6 条（新文件 `tests/test_plot_plan.py`）：不分组、分离、合并先到先得、书写顺序即优先级、数据与 `get_xy_data` 一致、样式原样带入。
- 用户写 `CurveSpec` / `FigureSpec`（`dataclass`）和第一版 `plan_figures`（三种情况放在一个循环里，有 8 处问题）；用户提出拆成三个函数更直观，
  执行者按此写定版：`plan_figures` 分派给 `_plan_all_samples` / `_plan_separate` / `_plan_merged`，取数参数先写成闭包，用户觉得「看不清带过去哪些变量」，改为 `functools.partial` 绑定模块级的 `_make_curve`（教学点：闭包、偏应用、依赖要显式）；
  `_written_style` 只取写了的样式、不翻译；每条线的 `style` 是副本；`groups` 也经 `resolve_groups` 检查。
- 记录未改：线性扫描（`get_column_data` 每次扫全部列）仍未优化，计划生成时每条线取两列；需要时在 `plan_figures` 里先建「(样品号, 通道号) → 列」的表。

#### 6.2 matplotlib 按计划画

`group_plotter` 和 `plot_objects` 改为「生成计划 → 按计划画」。**旧测试一条不改，全部通过**才算完成——旧测试就是这次重构的安全网。

**执行记录（2026-11-19，已完成，374 passed）：** 旧测试一条未改，全部通过。
- 新增 `_draw_figure(spec, plot_kind, figsize, ...)`：按一张 `FigureSpec` 建图、画线（`self.cmap(curve.color_position)`）、折线应用分组样式、默认格式、
  三个 formatter、负对数刻度，整段在 `rc_context` 里；返回 `(fig, ax, {样品号: artist})`。只读计划，不读 `Group`。
- `plot_objects`：`plan_figures(dataset, None, ...)`（不看 `self.groups`），`artists` 仍为列表（6.5 统一）。
- `group_plotter`：空分组仍转交 `plot_objects`；其余生成计划后一个循环画完——**合并 / 分离的分支消失**（合并计划只有一张 `'main'`）。
- 样式翻译：`_group_style(分组名)`（读 `Group`）换成 `_native_style(style)`（翻译计划里的样式）；`_group_style` 删除。
  `_configure_lines` / `_default_plot_formatter` 的「按分组挑线」参数删除（一张图上的线就是这张计划的全部线）。
- 用户决定：
  - 第 7 条选 A：合并模式柱状图统一为组首色（行为变化；以前因 `BarContainer` 没有 `set_color` 各用各的样品色）。新测试 `test_bar_group_colors_follow_plan`。
  - 新增构造参数 `figsize: tuple | None = None`（用户提出，选 B）：None 时保持各方法原来的尺寸。新测试 `test_figsize`；README 补一句。
  - 删除 `DataPlotter.plot_artists`（用户提出）：与 `axesset['main']['artists']` 重复，仓库内无人读取；artist 统一从 `axesset` 取。
    `InteractivePlotter.plot_artists` 有测试在用，留到 6.3 / 6.5 一起定。
- 分工：用户写 `_draw_figure`、`plot_objects`、`group_plotter` 的初版（几处错误由测试和审阅指出，后由执行者按用户要求改定）；执行者写 `_native_style`、两条新测试与收尾。
- 读代码时确认：同一通道的单位在所有样品里相同（`DataSet._channel_units_unify_check`），所以一张图的坐标轴单位取任意一条线都一样。
- **记到 6.5**：`plot_objects` 的 `artists` 是列表、`group_plotter` 是字典；单位是整张图共有的，可移到 `FigureSpec`；
  `DataPlotter.color_positions` 属性已无人读取（颜色由计划给出）；`subplotter_yy` / `subplotter_xyy` 仍是旧写法。

#### 6.3 Plotly 按同一份计划画（原步骤 5 的目标）

**开始前必读（2026-11-19 记录，6.2 提交后的现状）：**
- **计划**：`plot_common.plan_figures(dataset, groups, channel_x, channel_y, *, merge_groups, plotrange, neglog_x, neglog_y) -> list[FigureSpec]`。
  `FigureSpec(key, curves)`；`CurveSpec(sample_idx, x, y, label, x_unit, y_unit, group_name, color_position, style)`。
  颜色是色带位置（合并模式已是组首位置），`style` 是标准写法、只含写了的字段；数据已按 neglog 取过绝对值。规则全在计划里（`tests/test_plot_plan.py`）。
- **matplotlib 对照**：`DataPlotter._draw_figure`（建图 → 画线 → 折线应用 `_native_style(curve.style)` → 默认格式 → formatter → neglog，返回 `(fig, ax, {样品号: artist})`），
  `group_plotter` 只剩「空分组转交 `plot_objects`；生成计划 → 循环画」。Plotly 一侧照这个形状写 `_draw_figure` 的对应物，**后端只读计划、不读 `Group`**。
- **Plotly 现状**（`interactive.py`）：`plot_plotly_object(figure_formatter)` 自己按样品循环画（颜色 `_get_color(i)` = `sample_colorscale(cmap, [color_positions[i]])`），
  只产出一个 `self.asset: go.Figure`；`self.plot_artists` 是 trace 列表（`test_interactive.py` 有 3 处断言）；`add_slider` 按 **trace 位置** 控制显隐（按分组翻页见 6.8）。
  `self.groups` 已接上（5.1）但没用。模板 `_create_template` 里 Scatter 线宽 3 —— 翻译自定义虚线 `translate_linestyle(v, 'plotly', linewidth=3)` 要传线宽。
- **样式翻译**：Plotly 写在 trace 上：`line=dict(color=..., dash=...)`、`marker=dict(symbol=...)`；分组写了 marker 时折线 `mode` 要变成 `'lines+markers'`。
  可仿照 `DataPlotter._native_style` 写一个 Plotly 版（`style.translate_*(v, 'plotly')`）。分组样式仍只对折线生效（与 matplotlib 一致）。
- **建议的第一步**：先让 `plot_plotly_object` 改为「`plan_figures(dataset, None, …)` → 按计划画」，旧测试全过（与 6.2 的 `plot_objects` 同一手法）；再加分组入口（合并模式）。
- **用户习惯**：喜欢先看清整体流程再动手；累了会让执行者直接改、自己看 diff。测试期望由执行者先列好、用户确认。

**定。**

| # | 要定的事                   | 建议                                                                                                                 |
| - | -------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| 1 | 先做哪种模式               | 合并模式。它对应一个 Figure，和现有的 `self.asset` 吻合                                                            |
| 2 | 分离模式在 Plotly 里是什么 | 两个选项：返回 `{分组名: Figure}`；或一张图加「按分组切换」的滑块。后者是 `BACKEND_PLAN.md` 里写的方向，建议采用 |

样式用 `style.translate_*(value, 'plotly')` 翻译（自定义虚线要传线宽）；`DataPlotter._native_style` 是 matplotlib 一侧的对照（`_group_style` 已在 6.2 删除）。

**测。** `BACKEND_PLAN.md` 第 3 步的验收：相同的选列和分组配置下，两个后端得到相同的数据、标签和分组顺序。
写成一组对照测试，**同一个 `Group` 对象**分别交给两个绘图器（两者用同一个数据集），再比较。重叠样品只出现一次、组首色、线型各一条测试。

**执行记录（2026-11-19，已完成，385 passed，`b0d65dd`）：** 旧测试一条未改，全部通过；新增 `tests/test_plotly_groups.py`（11 条；随后的测试整理中拆进 `test_interactive.py` 和 `test_backend_parity.py`）。
- 「定」全按建议：先做合并模式；分离模式 = 一张图按组翻页（原 6.4，现 6.8）；入口名 `plot_plotly_group`；只画折线。
  另定：新增类常量 `_LINE_WIDTH = 3`，模板线宽和自定义虚线的像素换算共用（否则改模板线宽后虚线间距悄悄对不上）。
- `_draw_figure(spec, plot_kind='line', figure_formatter=None)`：建图（模板）→ 逐条画线 → 折线应用分组样式 → 轴标题 → formatter，
  返回 `(fig, {样品号: trace})`。画线循环与 matplotlib 逐行对应：
  `color = sample_colorscale(cmap, [curve.color_position])`，画线时写进 `line` 和 `marker`（不写的话点会用 Plotly 默认配色）；
  写了样式时 `artist.update(**_native_style(curve.style))`，对应 matplotlib 的 `artist.set(...)`。
- `_native_style(style)`：只翻译分组写了的字段，返回 `line_color / marker_color / line_dash / marker_symbol / mode`；
  写了 marker 时 `mode` 改为 `'lines+markers'`（matplotlib 没有这一步）。
- `plot_plotly_object`：`plan_figures(dataset, None, ...)` → `_draw_figure`；`plot_plotly_group`：空分组转交 `plot_plotly_object`，
  否则 `plan_figures(..., merge_groups=True)` → `_draw_figure`。两者都用 `_store(fig, artists)` 存 `self.asset` 和 `self.plot_artists`（列表，旧测试不动）。
- 删除 `_get_color(sample)`：它按样品号查位置，合并模式会取错色（应取组首位置），新流程里已无人调用。
- 过程：用户写了 `_draw_figure` 初版后在「颜色从哪来」上卡住。执行者画了三层调用关系图（入口 → 计划 → 后端），
  并改写了代码。第一版把色带颜色和分组样式合进一个函数、建 trace 时一次传入，调用处看不见颜色，和 matplotlib 结构也不同。
  按用户反馈改成与 matplotlib 相同的「画时写颜色，画完覆盖样式」。
- 讨论后记到 6.5：参数对照表、结果容器形状、颜色赋值统一为一次赋值（用户决定，见 6.5）。

#### 6.3 之后：绘图测试按层整理（2026-11-19，用户提出）

用户指出：代码结构已经变了，测试应跟着需求走，过期的清理掉。整理原则：**每条规则只在一层测**。

| 文件 | 测什么 |
| --- | --- |
| `test_plot_common.py` | 公共函数：色带位置、`resolve_groups`、取数 |
| `test_plot_plan.py` | 分组规则（去重、先到先得、组首色、样式归属、色带位置）——唯一测规则的地方 |
| `test_plotter.py` | matplotlib 把计划画对 + 它独有的功能（formatter、图例、`plot_style`、`figsize`、neglog 刻度、yy / xyy） |
| `test_interactive.py` | Plotly 把计划画对 + 模板、两种滑块 |
| `test_backend_parity.py`（新） | 两个绘图器的分组参数约定（对两个类参数化）；同一个 `Group` 画出的曲线一致 |

处理（394 → 385，其中 17 条是原 6.4（现 6.8）先写、待实现的测试）：
- 删除：`test_plot_objects_line_data`（与 `test_plot_kind[line]` 重复）、`test_column_index_out_of_range_raises`（与 `test_get_column_data_missing_raises` 重复）、
  `test_group_merge_mode`（去重、先到先得、组首色已在计划里测）。
- 合并：matplotlib 的分组线型、marker、颜色测试 × 两种模式（7 条）→ 一条参数化的 `test_group_style_translated`（5 种情况，只用分离模式）；
  `plot_style`、formatter 优先级、柱状图颜色测试去掉「× 两种模式」；分离模式「每组一张图」改为 `test_one_figure_per_spec`（分离 / 合并参数化）。
- 搬到计划测试：「画图不修改 Group」、稀疏样品号的分组颜色（改测位置）。
- 两个文件各 3 条分组参数测试 → `test_backend_parity.py` 里 3 条，对两个绘图器参数化；`test_plotly_groups.py` 拆掉。
- B.0 的「测试只增不减」改为「测试跟着需求走」；`tests/README.md` 约定加第 1 条（按层放）和第 10 条。

#### 路线调整：先建后端，再加新功能（2026-11-19，用户提出）

用户指出：原 6.4（Plotly 按组翻页）是新功能，要动的「一个 Figure 画多页」「结果存哪、什么形状」正是建后端时要定的接口；
照现有结构先写，接口一换就得重写。所以**先完成后端重构，再加新功能**。

执行者对照 `src` 与 `BACKEND_PLAN.md` 后补充：**后端的接口就是计划**（每个后端只做 `draw(计划)`），所以计划要先补全、定型，
否则建完后端再给计划加字段（如双 Y 轴的左 / 右轴），两个后端都要再改。

原 6.4 的方向和「定」保留，挪到 6.8；它的 17 条测试已写好（`test_interactive.py`、`test_backend_parity.py`），
**6.4 开始时先标 `xfail(strict=True, reason='6.8')`**，让 6.4 ~ 6.7 每一步结束都是全绿，6.8 实现时去掉标记、按新入口改调用。
用户在 `plot_plotly_group` 上已加的 `merge_groups` 参数（未提交）在 6.7 随入口一起搬走。

**用户已定（2026-11-19）：**

| # | 问题 | 决定 |
| - | ---- | ---- |
| 1 | `InteractivePlotter` 最后怎么办 | **删除**，统一用 `DataPlotter(backend='plotly')`；`scripts/piezo_interactive.py`、README、测试随之更新（机械） |
| 2 | 外观参数（字号、线宽、图例字号、`figsize`） | **公共参数、各后端翻译**（`BACKEND_PLAN` 原则 4）：matplotlib → `rc_params`，Plotly → 模板；`figsize` 英寸，到 Plotly × 100 成像素 |
| 3 | formatter 参数 | **统一为 `axes_formatter / lines_formatter / legend_formatter`**，各后端用原生对象调用：matplotlib 传 `ax, fig` / `lines` / `legends`，Plotly 三个都传 `fig`（`make_*_formatter(backend='plotly')` 生成的本来就是 `fn(fig)`）；Plotly 的 `figure_formatter` 去掉 |

**目标结构：**

```text
DataPlotter(dataset, groups, backend='matplotlib' | 'plotly', 外观参数...)   ← 唯一入口
   plot_objects / group_plotter / subplotter_yy / subplotter_xyy
      │ ① 生成计划（plot_common，不碰绘图库）
      ▼
   list[FigureSpec]    图：key、单位、neglog、版式（单轴 / 双 Y 轴）
                       线：数据、标签、色带位置、样式、图的种类、左 / 右轴
      │ ② 交给后端
      ▼
backends/matplotlib_backend.py      backends/plotly_backend.py
   每张 FigureSpec 一张图              所有 FigureSpec 画进一个 Figure，每张是一页（6.8）
      │ ③ 结果统一存进 self.axesset（键是 FigureSpec.key）
      ▼
滑块：只有 Plotly 有，matplotlib 后端调用时明确报错（BACKEND_PLAN 原则 3、5）
```

| 步 | 做什么 | 结束时 |
| -- | ------ | ------ |
| 6.4 计划补全 | 曲线加「图的种类、左 / 右轴」，图加「单位、neglog、版式」；新增 Y-Y、双 Y 轴计划；`subplotter_yy/xyy` 按计划画 | 四种模式全走计划，**计划定型** |
| 6.5 统一结果与清理 | 结果形状统一；删无人读的 `color_positions` 属性；颜色一次赋值（用户定的 B） | 一种结果形状 |
| 6.6 matplotlib 后端 | 画图代码搬进 `backends/matplotlib_backend.py`；`DataPlotter` 只剩「计划 → 后端 → 存结果」；`backend` 参数 | matplotlib 行为不变 |
| 6.7 Plotly 后端 | `InteractivePlotter` 的画图、模板、滑块搬进 `plotly_backend.py`；删除 `InteractivePlotter` | 两个后端同一入口 |
| 6.8 Plotly 按组翻页（原 6.4） | 分离模式按组翻页、分组滑块 | 功能齐全 |

每一步结束全绿、可单独提交。

#### 6.4 计划补全（计划定型）

**讲。** 现在的计划只覆盖不分组、分组两种模式；Y-Y、双 Y 轴还直接调 `get_xy_data`；图的单位挂在每条曲线上（后端取 `curves[-1]`），neglog 靠参数传给后端。
把这些都放进计划，后端才能只读计划。

**定（开始时逐条问，下面是建议）：**

| # | 要定的事 | 建议 |
| - | -------- | ---- |
| 1 | 曲线新增字段 | `kind`（`'line'` / `'scatter'` / `'bar'`，即 `plot_kind`；双 Y 轴两侧可不同）、`axis`（`'left'` / `'right'`） |
| 2 | 图新增字段 | `x_unit`、`y_unit`、`y2_unit`（没有右轴为 None）；`neglog`（哪些轴补负号刻度）；`layout`（`'multiline'`（6.4 时叫 `'single'`）/ `'dual_y'`）。曲线上的单位是否保留由用户定 |
| 3 | Y-Y 的计划 | 每个样品一张 FigureSpec、一条线，`key` 为样品号（与现在 `axesset` 的键一致） |
| 4 | 双 Y 轴的计划 | 每个样品一张 FigureSpec、两条线（左轴、右轴），`layout='dual_y'` |
| 5 | 各模式不同的默认格式（Y-Y 图例右下、Y 轴 4 位小数；双 Y 轴左红右蓝） | 由 `layout` 区分还是统一成一种默认格式（会是行为变化），用户定 |

**测。** 计划测试新增 Y-Y、双 Y 轴两种计划；`test_plotter.py` 里 Y-Y、双 Y 轴的旧测试保持通过（安全网）。

**执行记录（2026-11-19，已完成，386 passed + 10 xfailed）：**
- 开始前：原 6.4 的测试标 `xfail(strict=True)`（`PENDING_6_8`）。用户已给 `plot_plotly_group` 加了 `merge_groups`，其中 7 条已通过，只剩 10 条标记。
- 用户的决定（与上表不同处）：
  - **Y-Y 改名为 xy**：它就是最基本的「每个样品一张 x-y 单线图」，不是特殊模式。公开方法 `subplotter_yy` → `subplotter_xy`（3 个脚本、README、测试随之改），
    计划函数 `plan_xy_figures`、版式 `'xy'`；参数名 `plotdataRowNum_Y1/Y2` 留到 6.6 统一入口时整理。
  - **xy 的颜色不变**（第 2 条不按建议）：一张图一条线，不需要按样品换色。计划里色带位置允许为 `None`，表示「用后端默认色」（matplotlib 默认颜色序列第一个色）。
  - **线和图分清**：属于线的放 `CurveSpec`（数据、标签、色带位置、样式、`kind`、`axis`），属于图的放 `FigureSpec`（key、单位、`neglog`、`layout`）。
    左右轴跨两层（线挂哪根轴 / 那根轴的设置），6.6、6.7 实现后端时按需要调整；已写进 `plot_common.py` 的注释。
  - **双 Y 轴照旧模板**；排版设置要有地方存（见 6.6「排版预设」）。默认格式照旧，由 `layout` 区分。
  - `neglog` 保留 `'x2'`（拼图时上轴可能用到），取值 `{'x', 'y', 'x2', 'y2'}`。
  - 修 `figsize`：xy、双 Y 轴以前写死 (12, 8)，现在也用构造参数，不传时仍是 (12, 8)。
- 计划（`plot_common.py`）：
  - `CurveSpec` 删去 `x_unit / y_unit`，加 `kind`（默认 `'line'`）、`axis`（默认 `'left'`），`color_position` 可为 `None`；
  - `FigureSpec` 加 `x_unit`、`y_unit`、`y2_unit`、`neglog: frozenset`（不可变，多张图共用同一份也安全）、`layout`；
  - 新增 `channel_unit(dataset, 通道号)`、`plan_xy_figures`、`plan_dual_y_figures(left=(X, Y), right=(X, Y), kinds=...)`；
  - `plan_figures` 加 `kind` 参数；三个内部函数多收一个 `make_figure`（与 `make_curve` 同样用 `partial` 绑定单位、neglog、版式）
  - 完成后用户提出改名：`plan_figures` → **`plan_multiline_figures`**（多线图，与 `plan_xy_figures`、`plan_dual_y_figures` 按「画出来的样子」并列），版式 `'single'` → **`'multiline'`**（`'single'` 原想表达单轴，但 xy 图也是单轴，易误会）。之前的执行记录保留旧名。
- matplotlib：`_draw_figure` 不再收 `plot_kind`、`neglog_*`，改读 `curve.kind`、`spec.x_unit`、`spec.neglog`；`_default_plot_formatter` 去掉 `plot_kind`
  （散点、柱不在 `ax.get_lines()` 里，不用判断）；`subplotter_xy/xyy` 改为「生成计划 → 按计划画」，颜色用新的 `_curve_color(curve)`
  （分组写了用它，否则色带位置，位置为 None 不传）——这就是 6.5「颜色一次赋值」的写法，6.5 时 `_draw_figure` 也改用它。
- Plotly：`_draw_figure` 读 `curve.kind`、`spec.x_unit / y_unit`，不再取 `curves[-1]` 的单位。
- 新增测试 11 条（计划 8、matplotlib 3；改 1 条单位断言）；类型检查 0 错误。

#### 6.5 统一结果与清理

- **结果形状**：`{FigureSpec.key: {'fig', 'artists', ...}}`（A.4 第 2 条的四种形状合为一种）。要定：
  `artists` 的键——双 Y 轴同一样品有左右两条线，单靠样品号会冲突（可用 `(样品号, 轴)` 或按曲线顺序的列表）；
  matplotlib 的坐标轴放 `'ax'` 还是 `'axes'`（双 Y 轴有两个）；容器名是否从 `axesset` 改名（Plotly 没有 axes）；
  Plotly 分离模式各键的 `'fig'` 指向**同一个** Figure（6.8）。
- **颜色一次赋值（用户决定）**：先定这条线的最终颜色（分组写了就用它，否则色带位置换算），画线时一次传入、画完不再覆盖。
  执行者曾建议保留「先画再覆盖」（优先级写在代码顺序里；颜色对所有 `kind` 生效而样式只对折线生效），改时注意别让颜色跟着 `kind == 'line'` 的条件走。
  如果计划给出最终颜色来源（例如 `CurveSpec` 带上分组写的颜色），后端只剩「取色 → 赋值」。
- 删除两个绘图器上无人读取的 `color_positions` 属性（颜色由计划给出）。
- 读取 `axesset` 的测试和脚本随之修改。

**执行记录（2026-11-19，已完成，393 passed + 10 xfailed）：** 「定」全按建议。
- 新增 `plot_common.DrawnFigure(spec, fig, axes, artists)` 与 `artist(样品号, axis='left')`（找不到报 `KeyError`）；
  `artists` 是与 `spec.curves` 对齐的列表，解决了双 Y 轴同一样品两条线的键冲突。
- `DataPlotter.axesset` → **`figures = {计划的 key: DrawnFigure}`**，四种方法同一形状，不留别名；`_draw_figure` 返回 `DrawnFigure`。
  双 Y 轴 `axes={'left': ax1, 'right': ax2}`，`artists=[左线, 右线]`。
- 颜色一次赋值（用户定的 B）：两个后端的 `_draw_figure` 都在画线时用 `_curve_color(curve)` 给出最终颜色；`_native_style` 只翻译线型和标记，不再碰颜色。
  **行为变化**：分组写的 `color` 现在对散点图、柱状图也生效（BACKEND_PLAN 第 7 节「分组样式只对折线生效」的颜色部分解决；线型、标记仍只对折线）。
  顺手修：Plotly 的 `go.Bar` 没有 `line` 属性，柱状图只写 `marker` 颜色（入口还只画折线，6.7 开放 `plot_kind` 时会用到）。
- 删除两个绘图器的 `color_positions` 属性、`InteractivePlotter.axesset`（都无人读取）。Plotly 的 `asset`、`plot_artists` 按决定 5 留到 6.7。
- 测试：读 `axesset` 的 36 处改成 `figures` 写法（断言内容不变）；新增 7 条（结果形状 4 种方法、按样品取线、分组颜色作用于散点 / 柱）。
  Plotly 散点 / 柱的颜色测试留到 6.7 开放 `plot_kind` 时补。

#### 6.6 matplotlib 后端

- 建 `backends/__init__.py`、`backends/matplotlib_backend.py`；`DataPlotter` 的建图、画线、默认格式、formatter、neglog 搬过去，`DataPlotter` 只剩「生成计划 → 交给后端 → 存结果」。
- `DataPlotter` 加 `backend='matplotlib'` 参数；外观参数由后端翻译成 `rc_params`（决定 2）。
- 行为不变：`test_plotter.py` 全过。拆 `formatters.py`（按后端）可在本步或 6.7 一起做。
- **排版预设（6.4 时用户提出）**：现在写死在 `_default_plot_formatter`、`_default_xy_formatter`、`_default_xyy_formatter` 里的设置
  （图例位置、刻度小数位、双 Y 轴左红右蓝、`subplots_adjust`）抽到一处存放（如 `layouts.py`，按 `FigureSpec.layout` 取），用标准写法，各后端翻译；
  参照 `scripts/eis_*.py`、`scripts/piezo.py` 里常用的 formatter 设置做一份前端模板。双 Y 轴两条线的红、蓝从计划的 `style` 改为从预设读。

**6.6a 执行记录（2026-11-19，已完成，396 passed + 10 xfailed）：** 用户要求「一步步指导迁移」（这一步思想上最重要），按 6 小步走：
1. **分类练习**（用户做）：判断标准「换成 Plotly 要不要重写」→ 要重写就搬进后端。用户对了大半；`_draw_figure`、`_curve_color` 判成「留」
   （证据：Plotly 也各有一份），`subplotter_xy/xyy` 只搬了格式那几行（建图、画线也要搬），标准收紧为「碰不碰绘图库」。
   用户提出「计划交给后端渲染、入口与后端解耦」——落实为入口新增 `_render(specs, ...)`，后端只有一个公开方法 `draw(spec, ...)`。
   用户问「翻译要不要放在 plotter 与后端之间单独一层」：不单独成层（翻译结果的形状因后端而异：rc_params / Template；部分翻译需要后端状态；
   加后端要改两处），翻译规则集中在 `style.py`，后端内部分「翻译 / 渲染」两段。
2. `plot_common` 新增两个 `frozen` dataclass（用户写）：`Appearance`（字体、字号、字重、`line_width`、`axis_width`、`linestyle`、`legend_font_size`、`tick_width`，
   默认值与 DataPlotter 构造参数一致）、`AxesFormatter`（一根轴的一组回调：`axes` / `lines` / `legend`，没给为 None；用户定名）。
3. `backends/matplotlib_backend.py` 的 `MatplotlibBackend.__init__`（用户写）：Appearance → `rc_params`、解析色带名。
4. 画图方法原样搬进后端（执行者搬），分「翻译」（`_curve_color`、`_native_style`）与「渲染」两段。
5. `draw(spec, figsize, formatters=None, figure_formatter=None) -> DrawnFigure`（用户写分派与三个 `_draw_*`，执行者按用户要求收尾）：
   `formatters = {'left': AxesFormatter(...), 'right': ...}` 按轴取；`_apply_optional_formatters` 改为直接收一组 `AxesFormatter`（两层取值易错，用户写错多次后改接口）；
   **整图回调三种版式都支持**（用户选 B），签名统一为 `figure_formatter(fig, axes)`，`axes = {'left': ax, 'right': ax2}`；未知版式报 `ValueError`。
6. 接线（执行者写，用户去吃饭）：`backends/__init__.py` 的 `get_backend(name, appearance, cmap)`（各后端用到时才导入；`'plotly'` → `NotImplementedError`，
   写错 → `ValueError` 列出可选值）；`DataPlotter` 加 `backend='matplotlib'`，外观参数打包成 `Appearance` 交给后端，删掉 `rc_params`、`cmap` 属性；
   新增 `_render`；四个绘图方法都成了「计划 → 打包回调 → `_render`」；`subplotter_xyy` 把旧的 `custom_formatter(ax1, ax2, fig)` 包成新签名，脚本不用改。
   `plotter.py` 637 → 396 行，不再导入 matplotlib。
- 公开签名未变，脚本不用改；新增测试 3 条（后端只读计划、`backend` 参数、外观翻译）。
- 记到 6.6b / 6.7：刻度标签字号（用户在写 rc_params 时想加，未加，会改变现有图）；`Appearance` 是否补字段等 Plotly 需要时定。

**6.6b 执行记录（2026-11-20，已完成，407 passed + 10 xfailed）：** 「定」全按建议；用户定节奏「你定、我写、我讲」，执行者写、用户看 diff。
- 先写排版安全网测试 11 条（图例位置与可拖动、刻度格式、边距、双 Y 轴轴色与线色），在旧代码上全部通过，再重构。
- 新增 `layouts.py`：`LayoutPreset(legend, legend_draggable, tick_formats, axis_colors, margins)`（frozen，标准写法）与 `LAYOUTS = {'multiline', 'xy', 'dual_y'}`。
- 后端三个 `_draw_*` 合成一个 `_draw`：有挂右轴的线才 `twinx`；每条线画在 `axes[curve.axis]` 上；`_apply_layout` 按预设设图例（只放左轴）、
  轴标题、刻度格式（`_tick_formatter` 单独成函数，避开循环里 lambda 的晚绑定）、轴着色、边距；各轴回调只拿到挂在本轴的线。
  删除写死的 `_default_plot_formatter`、`_default_xy_formatter`、`_default_xyy_formatter` 及 `_configure_*`（其中线宽、刻度宽、刻度朝外与 rc_params 重复，本就不起作用）。
- 双 Y 轴红蓝只由预设定：计划不再写 `style={'color': ...}`；`_curve_color` 优先级为 分组颜色 > 色带位置 > 预设里这根轴的颜色 > 默认色。
- 后端 250 行（6.6a 时 ~330 行）；行为不变。参照脚本做「前端模板」（命名的 formatter 组合）是新功能，留到以后。

#### 6.7 Plotly 后端

- `InteractivePlotter` 的画图、模板、`_native_style`、滑块搬进 `backends/plotly_backend.py`；`DataPlotter(backend='plotly')` 可用；删除 `InteractivePlotter`（决定 1）。
- formatter 用三个统一名字调用（决定 3）；外观参数翻译成模板（决定 2）。
- 滑块是画完之后的可选交互：放在 `DataPlotter` 上（如 `add_slider`），matplotlib 后端调用时报错。
- 要定：Plotly 的负号刻度（建议 `tickprefix='-'`）；双 Y 轴在 Plotly 里怎么画（`yaxis2`）还是先明确报错；`plot_kind` 开放；`asset` 是否保留。
- 双 Y 轴（6.4 后用户问到，记录）：Plotly 没有 `ax2` 这样的轴对象，右轴是 layout 里的 `yaxis2=dict(overlaying='y', side='right')`，
  trace 写 `yaxis='y2'`（或 `make_subplots(specs=[[{"secondary_y": True}]])`）；计划的 `axis='right'`、`y2_unit`、`neglog` 的 `'y2'` 两边都能翻译，
  上轴 `'x2'` 同理（`xaxis2=dict(overlaying='x', side='top')`）。不能直接对应的是**按轴的 formatter**：matplotlib 的 `axes_formatter_ax2` 拿到 `ax2`，
  Plotly 的 formatter 只拿到整个 `fig`，不知道改哪根轴。执行者倾向给 Plotly 的格式化器工厂加「目标轴」参数（如 `axis='y2'`，只改 `yaxis2`），
  与 `axes_formatter_ax2` 一一对应；另一种是双 Y 轴只收整图 formatter、由用户自己写 `yaxis2`。另：matplotlib 默认只给左轴建图例，Plotly 两条线共用一个图例，要定是否一致。
- 对照测试改为同一个 `DataPlotter` 换 `backend`；`scripts/piezo_interactive.py`、README、`test_html_export.py` 随之更新。
- **`plot_common` 拆分或改名（6.6a 后用户问到，待定）**：用户问 plotter 与 plot_common 能否合并——不能（plot_common 是入口与后端之间的约定，
  并进 plotter 会让后端反过来导入入口，形成循环导入）。但名字已跟不上内容：它现在是「规则层」（`plan_*`），用户读 plotter 时找不到规则在哪。
  建议改名（如 `plan.py`），或按 BACKEND_PLAN 的规划拆出 `plot_spec.py`（约定类型）+ 计划函数；时机由用户定（6.7 前改只多改 InteractivePlotter 一行导入）。
- 回调每个位置只收一个函数，多个用 `combine_formatters` 合成（6.6 时讨论）。现在的 `combine_formatters` 类型标注是 Plotly 专用、只转发 `fig`，
  统一 formatter 时改成两个后端都能用（转发全部参数，如 matplotlib 的 `(ax, fig)`）。

**6.7 执行记录（2026-11-20，已完成，426 passed）：** 用户定节奏「你定、我写」；分 6.7a（建 Plotly 后端，新旧并存）、6.7b（切换入口、删除 `InteractivePlotter`）。
- 用户改定（与执行者建议不同处）：
  - **dpi 显式化**：`Appearance` 加 `dpi=100`，`DataPlotter` 加同名参数；磅（字号、线宽、刻度宽）和英寸（figsize）由翻译函数按 dpi 换成后端单位，
    不在后端里写死「× 100」。matplotlib 设成 `figure.dpi`（默认值本来就是 100，行为不变）。
  - **翻译层**：能通用的换算都放进 `style.py`（「后端专注渲染」）：新增 `translate_points`、`translate_figsize`、`translate_legend`、`translate_tick_format`；
    formatters.py 里重复的 Plotly 刻度格式翻译、matplotlib 后端 6.6b 写在内部的图例 / 刻度格式翻译都改用它们。
  - **Plotly 的轴**：没有轴对象，`DrawnFigure.axes` 放 Plotly 配置里的轴名 `{'left': 'yaxis', 'right': 'yaxis2'}`（共用 'xaxis'），用 `fig.layout[轴名]` 读写。
- 其余按建议：`PlotlyBackend(appearance, cmap).draw(spec, figsize, formatters, figure_formatter)`，与 matplotlib 后端逐段对应（翻译 / `_draw` / `_apply_layout` / neglog）；
  模板由 `Appearance` 生成（像素）；预设的图例位置、刻度格式、轴着色照用，边距和可拖动不用（Plotly 自动给图外图例留边）；
  双 Y 轴 `yaxis2=dict(overlaying='y', side='right')`、右线 `yaxis='y2'` 且不进图例；回调都收 `fig`；neglog → `tickprefix='-'`。
- **行为变化（Plotly 一侧）**：字号 24 → 约 31 像素（22 磅 × 100/72）、图例 18 → 约 14；线宽 3 → 约 4.2 像素；多线图 1200×800 → 1000×800（figsize × dpi）；
  多线图默认刻度两位小数（预设）——`scripts/piezo_interactive.py` 的对数 X 轴补了 `x_format='{x:.0e}'`。
- 滑块：`DataPlotter.add_slider(mode, slider_formatter) -> go.Figure`，实现搬进 `PlotlyBackend.add_slider(fig, ...)`；
  按「后端有没有这个能力」判断（matplotlib → `NotImplementedError`），只有一张图时可用（否则 `RuntimeError` 说明原因）。
- 删除：`src/plotlib/interactive.py`、`plotlib.InteractivePlotter`（`__init__` 的按需导入）、`tests/test_interactive.py`（有效期望迁到 `test_plotly_backend.py`）、
  6.8 那 10 条 xfail 测试（期望保留在 6.8 小节，6.8 按新入口重写）。计划函数开头加「数据集为空」的明确报错（原由 InteractivePlotter 自己检查）。
- 测试：`test_backend_parity.py` 改为同一个 `DataPlotter` 换 `backend`，五种画法（含分离模式、xy、双 Y 轴）都对照；新增 `test_plotly_backend.py`（29 条）、翻译层 3 条、dpi 1 条。
- 记到以后：`plot_common` 改名 / 拆分（用户待定）；formatter 工厂「目标轴」参数（右轴回调）；`combine_formatters` 两后端通用；
  Plotly 的 `'x2'` 上轴（neglog 暂跳过）；参照脚本做「前端模板」。

#### 6.7 之后：结构确认（2026-11-20，用户提出「趁热打铁把结构完全确认」）

**盘点**：旧 `InteractivePlotter` 的功能全部有对应；matplotlib 行为不变；两个后端五种画法对照一致；覆盖率 97%（新模块只剩防御性报错分支）；
脚本、README 无旧接口；`import plotlib` 不加载 Plotly / pyplot；`plotter.py` 无绘图库导入；两个后端前 7 个方法逐一对应。

**确认的五件事（全按建议）：**
1. `plot_common.py` 拆成 **`plot_spec.py`**（约定类型）+ **`plan.py`**（规则）：两个后端从它导入的全是约定类型，拆开后「后端只依赖约定、不依赖规则」体现在导入上。
   测试 `test_plot_common.py` 改名 `test_plan_helpers.py`。
2. **公开接口统一命名**（用户：上下文够就今天一起改）：构造参数 `input_dataset` → `dataset`、`plotdataRowNum_x/_y` → `channel_x/_y`、
   `plot_lw` / `axis_lw` / `ticker_width` / `legend_fontsize` / `plot_style` → `line_width` / `axis_width` / `tick_width` / `legend_font_size` / `linestyle`；
   方法 `plot_objects` / `group_plotter` / `subplotter_xy` / `subplotter_xyy` → **`plot_multiline` / `plot_groups` / `plot_xy` / `plot_dual_y`**；
   `NegLogScale_*` → `neglog_*`；xy 图通道 `channel_x/_y`（默认用构造时的值）；双 Y 轴 `left=(X, Y)`、`right=(X, Y)`、`neglog_x2/_y2`、`plot_kinds`、
   右轴回调 `right_axes_formatter` 等；`custom_formatter(ax1, ax2, fig)` → 四个方法都有的 **`figure_formatter(fig, axes)`**；删除常量 `dataRowNum_unit1~4`。
   不留别名；脚本、测试、README 用迁移脚本替换（双 Y 轴单独处理），eis_nyquist 的 lambda 手工改写。
3. `formatters.py` 不按后端拆（工厂用 `backend` 参数区分，是前端接口）；记下遗留：matplotlib axes formatter 写死刻度宽 3。
4. 删除 `DataPlotter.data / sample_idx / column`（无人读取）。
5. Plotly `_apply_neglog` 改名 `_apply_neglog_formatter`（与 matplotlib 对齐）；两个后端补「版式 / 画法写错报错」的测试。
- 结果：428 passed；类型检查 0 错误；BACKEND_PLAN 第 2 节改为「当前架构（定稿）」与模块职责表。

#### 6.7 之后：第三方审查修复（2026-11-20，插在 6.8 之前）

**来源：** `docs/ThirdPary_review.md`。执行者逐条复现，库代码相关的结论全部成立；报告第 2 条（EIS 按行配对）和第 3 条的脚本部分（多峰选峰、无峰输出）**用户定先不管**，留给步骤 8 或单独处理。
**教训：** C、D 两个问题一直没被发现，是因为测试只断言对象属性（直接调用格式器、只看图例句柄样式），没有渲染。**以后刻度文字、图例位置这类结果，要 `canvas.draw()` 之后再断言**（写进 `tests/README.md` 约定）。

| # | 问题（复现） | 来源 | 分组 |
|---|---|---|---|
| A | `Dataloader`：`int(98 * (1/49))` 得 1，静默丢样品；未知后缀不报错，沿用 `self.dataset` 里上一次的表 | 重构前就有 | 第一组（最小修复） |
| B | `DataSet.expandata`：零行结果 `(0, 2)` 的 `size == 0` 被当成空容器而替换矩阵；元数据先改后校验，报错时原对象已改坏 | 重构前就有（脚本触发，错在库里） | 第一组 |
| C | matplotlib `neglog`：渲染后刻度文字全是 `'-'`。包装的 `ScalarFormatter` 收不到本轮刻度位置；双 Y 轴两个 X 标志会重复加负号 | 重构前就有 | 第一组 |
| D | matplotlib `lines_formatter` 后重建图例：`get_bbox_to_anchor()` 已是像素坐标又被当锚点再转换一次，图例 (757, 362) → (468882, 243990) | 重构前就有 | 第一组 |
| E | 右轴回调范围：Plotly 回调都收整个 `fig`，公共工厂改全部轴 / 全部线（只配右轴，左轴也变）；matplotlib 右轴没有图例，图例回调收到 `None` 报错 | 即 BACKEND_PLAN 第 7 节「目标轴」 | 第二组（先定设计） |
| F | `pyproject` 写 `plotly>=6.1`，模板用的 `minorloglabels` 从 6.3 才有 | — | 第三组 |
| G | 样式适用范围：两个后端轴工厂写死刻度宽 3；分组 `marker` 对散点无效；Plotly 线工厂 `linecolor` 对纯散点改的是隐藏线色 | — | 第三组（随 E） |
| — | 取列随样品数平方增长；选择缺失样品号、单改某样品单位的语义 | — | 暂缓到步骤 7 |

**第一组的修法（用户定：按建议，执行者写、用户看 diff）：**
1. C：负号刻度不再包原格式器，改为包装后把刻度位置一并交给原格式器；共享的 X 轴只加一次负号。测试渲染后断言刻度文字。
2. D：不重建图例，把线的新样式同步到现有图例句柄（`handle.update_from(line)`），位置、拖动、字号原样保留，也不再读私有 `_loc`。测试渲染后断言图例位置不变。
3. B：「空容器」改看有没有列；先校验待拼接的数据与元信息，再修改对象。测试首样品无峰、全部无峰、失败后原对象可继续正确追加。
4. A：整数除法计数；本次读到的表用局部变量；未知后缀立即报错。其余接口调整（只留每样品列宽、直接传路径、取消不退出、Tk 延迟导入）仍在 7.1。

**顺序：** 第一组 → 讨论定 E 的设计，E 与 G 一起改 → F 顺手 → 6.8。

**第一组执行记录（2026-11-20 完成，438 passed）：** 先写 10 条回归测试（全部按预期失败），再修：
- D 的修法与上面写的不同：实验发现 `update_from` 会把线的坐标变换也复制到图例句柄上，句柄画错位置，不能用。
  改为把「按预设建图例」抽成 `MatplotlibBackend._make_legend(ax, preset)`，排版时建一次，`lines_formatter` 之后按同一预设重建；
  删除 `_refresh_legend`（不再读私有 `_loc`）；`_apply_optional_formatters` 改收 `preset`，图例回调拿到的是重建后的图例。
- C：新增 `_NegativeFormatter(Formatter)`，前缀负号，`set_locs` / `set_axis` / `get_offset` 转交原格式器。
  **行为变化**：matplotlib 的 `'x2'` 不再作用在双 Y 轴共用的 X 轴上（约定里 `'x2'` 是上轴，与 Plotly 一致）；以前只给 `neglog_x2` 也会给共用 X 轴加负号。
- B：`expandata` 用「列数为 0」判断空；先记原状，`update_attributes` 失败就恢复再抛出（与 `Column.sample_idx` 的 setter 同一做法）。
- A：样品数 `total_cols // COLUMNS_PER_DATASET`；`DATASET_FRACTION` 不再参与计算（参数保留到 7.1）；未知后缀 `ValueError`（以前是 `RuntimeError`「数据集加载失败」）。
- 遗留（外观，未改）：负号刻度下落在 0 处的刻度显示为 `-0`，与多线图预设格式下的 `-0.00` 相同，原来就有。

**第二组 E + G 执行记录（2026-11-20 完成，451 passed）：**
- 讨论：三种做法——①后端传轴名、工厂自己筛 trace；②后端交出这根轴的东西（轴名 + 这根轴的 trace + 图例列表）；③创建工厂时指定目标轴。
  **用户选做法 2**：「找哪根轴的东西」只在后端做一次（与 matplotlib 后端挑线同一行），工厂只管「怎么改」。
  `figure_formatter(fig, axes)` 拿整个轴字典，按轴回调拿字典里的一项，两层分工不变。
- 回调形状（两个后端对应）：axes `(ax | 轴名, fig)`、lines（这根轴的线 / trace）、legend（`[Legend]` / `[fig.layout.legend]`）。
  Plotly 轴工厂：Y 设置写到给定轴名，X 设置写到共用的 `xaxis`；`custom_formation` 收 `(轴名, fig)`。
- **用户定：没有图例的轴配图例回调 → 报错**（两个后端同一句，`layouts.NO_LEGEND_MESSAGE`；一张图一个图例，归左轴）。
- `combine_formatters` 改为合并同一种回调、参数原样转交，两个后端通用（以前 Plotly 专用，可把三种回调合成一个 `fn(fig)`——这个用法没有了；脚本没用到）。
- G：两个轴工厂不再写刻度宽（由 `tick_width` 决定；未加工厂参数）；新增翻译层 `style.STYLE_FIELDS_BY_KIND`（折线：线型 + 标记，散点：标记，柱：无），
  两个后端的 `_native_style(curve)` 按它取字段，样式改为**画线时一次给出**（与颜色一样；matplotlib 散点的标记画完改不了）；Plotly 线工厂 `linecolor` 点也一起改。
- 行为变化：Plotly 用轴工厂时刻度宽从 3px 变为模板换算值（约 4.2px，与不用工厂时一致）；matplotlib 默认 `tick_width` 也是 3，效果不变。

**双 Y 轴版式与图例标题（用户 2026-11-20 提出，参照 Origin 图；完成，472 passed）。** 用户记得「双 Y 轴图例有红蓝两条」，
实测重构前后（及去年的旧脚本）都只有左线一条，那是 Origin 画的图；用户要求按 Origin 的样子改默认版式。定下的事：
1. 图例放图外上方、右对齐（翻译层新增 `'outside top right'`；matplotlib 要 `borderaxespad=0` 才右对齐）；左右两条线都进图例；上边距 0.85。
2. 图例标签：**图例标题写样品名，每条线写自己的单位**（用户选第三种：只写单位会丢样品名，样品名 + 单位太长）。
3. 约定 `FigureSpec.legend_title`；**四种绘图方法都有 `legend_title` 参数**（用户要求）：多线 / 分组 / xy 默认 None，双 Y 轴默认 `'{name}'`。
   `'{name}'` 换成每张图自己的名字（xy、双 Y 轴是样品名，分离模式是组名）。只有一张图时：执行者原提议写 `'{name}'` 报错，
   **用户改为不报错、不替换**（「都允许自由传参了，没必要给单图加限制」；如突出一个样品时直接写它的名字）。
4. 右轴仍没有自己的图例：`right_legend_formatter` 照旧报错，图例归 `legend_formatter`。
5. Origin 图里的次刻度不在这次范围（会影响所有版式），需要时单独提。

**F（2026-11-20 完成）**：`pyproject.toml` 的 `interactive` 改为 `plotly>=6.3`（模板的 `minorloglabels` 从 6.3 起才有；本机 7.1，旧版本未实测）。第三方审查修复全部完成，接 6.8。

（上面双 Y 轴版式的实现细节：）
- 实现：计划层新增 `_make_figure(key, curves, name, *, legend_title, **图信息)`，与 `_make_curve` 一样用 `partial` 绑定；`_make_curve` 加 `label_from='name' | 'unit'`；
  新增 `plan.sample_name`。两个后端的图例收所有轴上的线（matplotlib 手动收 `twinx` 的句柄；Plotly 去掉右线 `showlegend=False`）并加标题；
  matplotlib rc 加 `legend.title_fontsize`（不设时标题用正文字号 22）。
- **回调顺序调整（两个后端）**：以前按轴逐个「轴 → 线 → 图例」；图例里有右线后，右轴线回调触发的重建会冲掉左轴图例回调的设置。
  改为两遍：各轴的轴、线回调 → 线改过就重建一次图例（matplotlib）→ 图例回调。单轴图不受影响。
- 行为变化：双 Y 轴图例从图内右下（只有左线、写样品名）变为图外上方（两条线、写单位、标题样品名）；`CurveSpec.label` 在双 Y 轴里是单位。

#### 6.8 Plotly 分离模式：按组翻页（原 6.4）

**方向（6.3 时定）：** 分离模式 = 一张 Figure 按组翻页，**每一页就是计划里的一张 `FigureSpec`**：
`plan_multiline_figures(..., merge_groups=False)` 给出几张图，就把它们的曲线依次画进同一个 Figure，滑块的每一档显示一页的 trace。
这样每一页和 matplotlib 那组的图完全一致（同一样品在 B 组那页用 B 组的样式和样品色），滑块也只读计划、不读 `Group`。
原写法「曲线登记为样品号 → trace，分组名 → 样品号向 `self.groups.sample_ids` 要」作废：它让每个样品只有一条 trace，B 组那页会显示 A 组的样式，且后端又去读 `Group`。

**已定（2026-11-19，全按建议）：** `merge_groups` 默认 False（与 `group_plotter` 一致）；刚画完只显示第一页；
曲线滑块 `add_slider` 与分组滑块 `add_group_slider` 是两个方法（用户强调解耦），共用私有的「装滑块 → 判断标签放不放得下 → 默认外观 → formatter」；
多页图上调用 `add_slider`、一页图上调用 `add_group_slider` → `RuntimeError` 并提示该用哪个；分组滑块当前值前缀 `'Group: '`。
结果按页登记 `{FigureSpec.key: {样品号: trace}}`，即 6.5 统一形状里的 `artists`。

**测（6.7 后更新）：** 原先按 `InteractivePlotter` 写的 10 条 xfail 测试已随它删除，6.8 按新入口 `DataPlotter(backend='plotly')` 重写，期望不变：默认分离模式 4 条 trace、每页与 matplotlib 对应分组那张图一致、同一样品各页样式不同、
分离模式按样品上色、初始只显示第一页、分组滑块的档位与可见性、两种方法用错报错。实现时按 6.7 的新入口改调用。
跨后端对照按「页」比较（matplotlib 一页一张 Figure，Plotly 多页同一个 Figure），不要假设两边原生 Figure 数量相同（第三方审查的提醒）。

**执行记录（2026-11-20 完成，484 passed）：**
- 定（全按建议，用户另加一条）：
  1. **凡是一次画出多张计划的都翻页**（分组分离模式、xy、双 Y 轴）：后端只认计划、不认绘图方法；只让分组翻页就得让后端知道「这是分组图」。
  2. Plotly 后端新增 `draw_pages(specs, ...)`，每页一个 `DrawnFigure`（共用 `fig`、`axes`，`artists` 只有这页的）；
     `draw` 就是只有一页的 `draw_pages`。`DataPlotter._render` 按「后端有没有 `draw_pages`、计划是否多于一张」分支（与滑块一样按能力判断）。
  3. 各页来自同一次计划、只有一套轴：排版按第一页，按轴回调、整图回调对整个 Figure 只调一次，线回调拿到这根轴上所有页的 trace。
  4. 原定 `add_group_slider` + 前缀 `'Group: '` 改为 **`add_page_slider`**、前缀默认为空（组名、样品名都会出现）；档位标签是每页的名字，
     为此约定新增 **`FigureSpec.name`**（`_make_figure` 本来就算出了它，用来替换 `'{name}'`）。翻页时标题、图例标题换成这一页的。
  5. **用户加：翻页滑块也支持 `single` / `cumulative`**。用户指出翻页与曲线滑块原理相同（Plotly 一个 Figure 装不下多个 Figure，只能切换 trace 显隐），
     于是两种滑块共用 `_install_slider(fig, steps, mode, prefix, formatter)`：steps 是每档的 (标签, trace 位置, 翻到时改的 layout)，
     曲线滑块一档一条 trace，翻页滑块一档一页。`add_page_slider` 默认 `'single'`，`add_slider` 仍默认 `'cumulative'`。
- 滑块改 layout 改用带点的路径（`'title.text'`、`'legend.title.text'`）：只改这一项，不会把图例位置等设置冲掉；曲线滑块的测试随之更新。
- 用错：多页图用 `add_slider` / 一页图用 `add_page_slider` → `RuntimeError` 并提示另一个；两者共用 `DataPlotter._slider_method` 做能力和「已绘图」检查。
- 行为变化：Plotly 的分组分离模式、xy、双 Y 轴不再是多个 Figure，而是一个 Figure 多页、只显示第一页（以前全部各自显示）。
- 验证：kaleido 渲染多页双 Y 轴图 + 翻页滑块，初始只显示第一页，标题、图例标题、两档的显隐与图例标题都对；导出 HTML 正常。

#### 6.8 之后：刻度 TickStyle（2026-11-20，用户试 piezo_interactive 时提出，507 passed）

**起因**：用户要精调主 / 次刻度的长短和显示，现状没有接口：刻度宽只有 `tick_width`（主次一样），刻度长 Plotly 模板写死 6 / 3 px、matplotlib 用默认 3.5 / 2 磅，
次刻度 Plotly 一律显示、matplotlib 线性轴不显示，两边都对不上。用户又问「以后参数越来越多怎么办」。
**定（全按建议，用户另加）：**
1. **按主题打包成对象**：一个主题一个冻结 dataclass（标准写法、磅）+ 翻译层一个 `translate_*`；字段 None 表示不改，按层叠加
   （默认 `DEFAULT_TICKS` < `DataPlotter(ticks=...)` < `make_axes_formatter(ticks=...)`）。刻度是第一个；工厂其余参数照此抽象是下一步（用户提出，方案待定）。
2. 字段（用户要求做完整，后面写文档一气呵成）：`direction`（只有 out / in，Plotly 没有 inout）、`length` / `width`、`minor`（**默认显示，有开关**，用户定）、
   `minor_length` / `minor_width`、`label_font` / `label_size` / `label_pad`、`minor_labels`（none / short / full）、`minor_label_font` / `_size` / `_pad`。不分 x、y，分开用单轴覆盖。
3. `tick_width` 并入 `ticks.width`，不留别名。全局和单轴两层一起做。
4. Plotly 做不到的：单独设次刻度文字的字体 / 字号 / 间距 → 报错（Plotly 次刻度没有文字属性）；线性轴上的次刻度文字不报错、只在对数轴生效。
   用户提议直接改 JS 控制次刻度字号：只对导出的 HTML 有效、重画会被冲掉，记入 BACKEND_PLAN 待办。
- 实现：`plot_spec.TickStyle`（`updated` 叠加）/ `DEFAULT_TICKS`，`Appearance.ticks`；`style.check_ticks` / `translate_ticks`；
  matplotlib 新增 `backends/matplotlib_ticks.py`（样式对象化时改名 `matplotlib_styles.py`；后端与工厂共用，不导入 pyplot）：线和文字用 `tick_params`（改刻度类型后保留）建轴时应用；
  次刻度的定位器 / 格式器会被 `set_xscale` 重置，所以在用户回调之后只补还是默认值的（`isDefault_minloc / minfmt`），不覆盖单轴设置；
  只动看得见的 Axis（`twinx` 的 X 轴隐藏且与左轴共用定位器）。Plotly：模板里写全局刻度；`fig.layout.meta['dpi']` 记 dpi，单轴工厂按它换算；
  只改朝向时不把关掉的次刻度打开（Plotly 的 `minor.ticks` 同时管显示和朝向）。两个工厂去掉写死的朝外。
- 实际渲染后改了一处：线性轴上的 `'short'` 原定等同 `'full'`，画出来每个次刻度都标数、挤成一片，改为线性轴不写（与 Plotly 一致）。
- 行为变化：两个后端默认都显示次刻度；默认刻度长统一为主 6 / 次 3 磅（matplotlib 原 3.5 / 2 磅，Plotly 原 6 / 3 像素）；`DataPlotter(tick_width=...)` 改为 `ticks=TickStyle(width=...)`。
- 顺带发现（原来就有，记入 BACKEND_PLAN 第 7 节）：matplotlib 轴工厂总调用 `set_yscale`，会冲掉排版预设的刻度格式。

#### 6.8 之后：样式对象化（2026-11-20，用户提出「工厂里的其它参数也一起抽象出来管理，保持结构一致」，520 passed）

**定（全按建议，用户另加）：**
1. 照 `TickStyle` 的做法，格式参数按主题打包成冻结 dataclass：`LineStyle`（线，合并 `line_width` / `linestyle`、线条工厂参数、分组样式）、
   `AxisStyle`（一个方向的轴：`scale` / `limits` / `format` / `scaler` / `color`，按方向拆开，`make_axes_formatter(x=, y=)`）、
   `FrameStyle`（边框：`width` / `top` / `right`，合并 `axis_width`、`hide_spines`）、`LegendStyle`（`position` / `font_size` / `frame` / `draggable`）。
   公共部分 `StyleLayer.updated`（写了的覆盖、None 沿用）。
2. **默认无框**（用户定）；**双 Y 轴预设画完整的框**（左右各有一根轴，不封口太难看）。
3. **版式预设也用样式对象写**（用户：「后面用统一的 plot_spec 对象，结构上完美很多」）：`LayoutPreset(legend=LegendStyle, frame=FrameStyle, axes={轴名: AxisStyle}, margins)`。
4. 旧参数不留（`line_width`、`linestyle`、`axis_width`、`legend_font_size`，工厂的 `xlim_*`、`*scale_type`、`*_format`、`*scaler`、`hide_spines`、`line*`、`legend_*`、`custom_formation(s)` → `custom`）。
- **叠加顺序**（执行者补充说明，用户同意按规划改）：库默认 < 版式预设 < **DataPlotter 全局** < 分组样式 < 格式化器。
  用户明确写的全局设置盖过预设，否则 `DataPlotter(frame=FrameStyle(top=True))` 会被多线图的「无框」悄悄盖掉。
  为此 `Appearance` 只存用户写的那一层，库默认和预设由后端在画每张图时叠（`layouts.resolve_legend / resolve_frame`，唯一写顺序的地方）；`ticks` 一并改成这样。
- 实施：原计划分四步、每步全绿；但 `Appearance` 一去掉旧参数，中间状态就跑不起来，所以四步一起写完再迁移测试（已告知用户）。
  脚本和测试里 41 处工厂调用用 ast 迁移脚本改写（再把过长的一行拆成每个参数一行），带 `**kwargs` 的 3 处和其余测试手改。
- 翻译层新增 `check_* / translate_line_style / translate_axis_style / translate_frame / translate_legend_style`；图例位置合成一张表 `LEGEND_POSITIONS`
  （原图例工厂自带的 Plotly 对照表删掉，图内位置离边 0.02）；`STYLE_FIELDS_BY_KIND` 加上 `width` / `marker_size`。
  matplotlib 的 `matplotlib_ticks.py` 改名 `matplotlib_styles.py`，加 `apply_axis` / `apply_frame` / `apply_legend`；双 Y 轴右轴（twin）的左、下边不画，免得盖住左轴的红色轴线。
  Plotly 的线宽、标记大小、图例字号在格式化器里也改成磅（按 `fig.layout.meta['dpi']` 换算；trace / legend 用 `.figure` 找到所在的图）。
- 顺带修：`set_yscale` 冲掉预设刻度格式（`AxisStyle.scale` 没写就不调用）；**Plotly 双 Y 轴右轴刻度不整齐**（渲染时发现，原来就有：Plotly 对叠加轴默认
  `tickmode='sync'` 对齐左轴，刻度值成了 1.0007、0.9022；改为 `'auto'`，与 matplotlib twinx 一致）。
- 行为变化：默认无框（以前 matplotlib 不用工厂时四面都有，用了工厂只剩 L 形；Plotly 是 L 形），双 Y 轴两个后端都是完整的框；
  空的轴工厂什么都不改（以前默认隐藏上 / 右边、重置刻度类型）；Plotly 格式化器里的线宽、字号单位从像素改为磅；Plotly 图例图内位置离边 0.02。

#### 6.8 之后：55576fb 复审修复（2026-11-20，`docs/ThirdPary_review.md`「55576fb 复审」，538 passed）

样式对象化提交（`55576fb`）后第三方复审列了 4 条回归，执行者逐条复现全部属实，另补了两处同类问题；用户定：四条先修。
流程照旧：先写测试（18 条，新失败 15 条：txt 格式、matplotlib 全局标记原本就对），再改代码。

1. **数字样品名**（高）：标识列除了第 0 行全空，pandas 把整列推断成浮点数，`'101'` 读成 `101.0`，双 Y 轴替换 `'{name}'`（两个后端）、
   Plotly 翻页滑块取标签长度都报 `TypeError`；执行者补：多线图的曲线滑块同样会报错。复审建议在计划层转字符串，但那里只能得到 `'101.0'`，
   所以改在源头：`Dataloader` 三种格式都 `dtype=str` 读，样品名、单位原样是文本（`'1.50'` 也不会变 `1.5`），数据列照旧 `pd.to_numeric`。
2. **Plotly 全局 marker**（高）：模板重复传 `marker_symbol`，绘图器建不起来；修好后折线仍是纯线。改为：全局 marker 不进模板（模板的默认样式也作用于散点，散点固定圆点，
   与 matplotlib 的 rc `lines.marker` 不管 scatter 一致），折线在 `_native_style` 里按「全局 < 分组」叠上，有标记就 `lines+markers`。
3. **Plotly 对数轴分步设范围**（高）：先设对数、再单独设 `limits=(10, 1000)`，range 写成 `[10, 1000]`（Plotly 当 log10，即 10¹⁰ ~ 10¹⁰⁰⁰）；
   执行者补：反过来先设范围再改对数也错（已写的范围没换算）；实测单侧边界 `minallowed / maxallowed` 在对数轴上同样用 log10。
   改为：新建 `backends/plotly_styles.py`（对照 `matplotlib_styles.py`）的 `apply_axis(fig, 轴名, AxisStyle, 方向)`，应用时按这根轴「应用后的类型」翻译，
   改了类型（线性 ↔ 对数）时把轴上已写的边界一起换算；`translate_axis_style` 加参数 `log`（Plotly 用）。轴工厂和后端的预设都走它。
   约定统一成「`limits` 永远写数据值，分几个回调设、先设哪个结果都一样」，与 matplotlib 相同。分步时对数轴边界 ≤ 0 在应用时报错。
4. **翻页隐藏共享参考线**（中）：整图回调加的参考线不属于任何一页，翻页滑块每档都把它设成隐藏。改为：不在任何一档里的 trace 每档保持原来的显隐
   （含 `'legendonly'`）。曲线滑块同理（执行者建议，一并改）：`add_slider` 加参数 `curves`，`DataPlotter` 传计划画出的曲线，参考线不再多出一档。

- **随后搬家**（用户同意）：`formatters.py` 里 Plotly 的边框、刻度应用（`_apply_plotly_frame` / `_apply_plotly_ticks` / `_minor_ticks_shown`）和 `_figure_dpi`
  挪进 `plotly_styles.py`（`apply_frame` / `apply_ticks` / `figure_dpi`），与 `matplotlib_styles.py` 结构对应；全部收样式对象、按这张图的 dpi 应用时翻译。
  后端自己的 `_apply_frame` 删掉，改为逐根轴调 `apply_frame`（对照 matplotlib 后端逐个 ax 调）。
  搬家时发现一个原有的 bug：判断有没有右轴时直接读 `fig.layout.yaxis2`，单轴图上 `make_axes_formatter(frame=FrameStyle(right=True), backend='plotly')` 抛 `AttributeError`
  （后端以前靠 `'right' in axes` 绕开了）；先补回归测试再改成 `getattr`。539 passed。

**未闭环、暂不做（用户定）：**
- **柱状图、散点图的格式化从 `draw` 里独立出去**（用户提出）：它们有自己的格式参数和设置方式，现在跟折线共用一套（线条回调对柱图改色时 matplotlib 报 `AttributeError`，
  Plotly 跳过 Bar，复审「尚未闭环」第 1 条）。用户手头没有这两种数据，不直观，等有需要时把两者对应的格式化流程从 `draw` 中分出去（记在 BACKEND_PLAN 第 7 节）。
- Bode 脚本全部样品无峰时 `IndexError`：脚本问题，按原计划留到步骤 8。

#### 6.4 ~ 6.8 期间的记录

**参数对照（6.3 时讨论；决定 2、3 已定处理方式）：**

| DataPlotter 参数 | 属于哪层 | Plotly 现状（6.3 时） | 处理 |
| --- | --- | --- | --- |
| X/Y 通道、`plotrange`、`groups` | 计划 | 构造器已有 | 已统一（都交给 `plan_multiline_figures`） |
| `merge_groups` | 计划 | 用户已加（未提交） | 6.7 随入口统一；Plotly 分离模式 = 按组翻页（6.8） |
| `NegLogScale_x/y` | 计划（取绝对值）+ 后端（刻度补负号） | 无 | 6.4 进计划；Plotly 的负号刻度 6.7 定 |
| `plot_kind` | 计划（`CurveSpec.kind`）+ 后端绘制 | `_plot_data_plotly` 已支持，入口未开放 | 6.4 进计划，6.7 开放 |
| `figsize`、字号、线宽等 | 外观，公共参数 | 模板里写死 | 决定 2：各后端翻译 |
| `axes/lines/legend_formatter` | 后端原生回调 | 只有 `figure_formatter` | 决定 3：三个统一名字，各后端用原生对象调用 |

**方向（记录，不在本轮做）：作用在计划上的样式调整。** 有了计划，就可以在「画之前」按标准写法改某条曲线的 `style`，两个后端都生效；
现在的 `lines_formatter` 是后端原生回调，只对一个后端有效。以后的 `group_style_applyer`、组内精调、「计算结果各用各的样式」（4.5 取消时的需求）都可以做成这种形式。
「在某一页里再按曲线滑动」（两个滑块）也留到以后。

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
（第三方审查修复已先做了最小修复：整数除法计数、本次读取用局部表、未知后缀报错，见 6.7 之后的「第三方审查修复」A。）
**教学点：** `tkinter` 改为函数内导入后，`tests/test_dataloader.py` 末尾用 `monkeypatch` 替换弹窗的那条测试的替换目标会变，让用户自己想清楚为什么。

**一起处理（步骤 2 留下的，2026-11-18 补记）：** `tests/conftest.py` 的 `write_grouped_file(path, units, groups)`、`load_file(path, columns_per_group)`、
`make_dataset(units, groups, fmt)` 里的 `groups` 实际是 `{样品名: 数据行}`，`columns_per_group` 实际是每个样品的列数，随 `columns_per_sample` 一起改名
（`groups` 这个词现在专指 `Group`，不要再用于样品）；`tests/test_dataloader.py` 的 `test_various_group_widths`、`columns_per_group` 参数同理；
脚本里 `INPUT_COLUMNS_PER_DATASET` 旁「每组数据集的列数」的注释改为「每个样品」。
三个分组脚本在数据加载后紧接着写 `groups = Group(data, data_groups)`，改加载写法时保持这个顺序。

**7.1 执行记录（2026-11-20，547 passed）。** 用户：「这个好懂，直接改」，全按建议：
1. 写法 `Dataloader(columns_per_sample=6).load_data(path=None)`：传路径直接读，不传才弹窗。`columns_per_sample` 必填（原默认 6 只适合 piezo），
   不小于 2 的整数，写错 `ValueError`。
2. `DATASET_FRACTION` 删除，`COLUMNS_PER_DATASET` 改名 `columns_per_sample`，不留别名；6 个脚本改成 `COLUMNS_PER_SAMPLE = N` + 一行加载
   （实际每个脚本 4 处，不是估计的约 50 处）；README 5 处示例同步。
3. 取消选择抛 `NoFileSelected`（继承 `Exception`，不继承 `OSError`，与 `FileNotFoundError` 区分开；包顶层导出）；隐藏的 Tk 主窗口用完 `destroy`。
4. 扩展名不区分大小写（`Path.suffix.lower()`），报错列出支持的格式（`SUPPORTED_SUFFIXES`，对话框的过滤条件也用它）；`tkinter` 改到 `select_data_file` 里导入。
5. （执行者补充）加载器只存 `columns_per_sample`：中间结果都是局部变量，`load_data` 拆成 `_read_table`（按扩展名读表）和 `_to_dataset`（按列宽拆开装进 DataSet）；
   `file_path` 属性删除。原来的维度一致性校验随之删掉（列表由同一个 `range` 生成，不会不一致）。列数不整除的报错改成中文并写出总列数和 `columns_per_sample`。
- 测试辅助一起改名：`write_grouped_file` → `write_samples_file`、`groups` → `samples`、`columns_per_group` → `columns_per_sample`。
- **教学点的答案**：现有测试替换的是 `Dataloader.select_data_file`（类上的属性，调用时才查找），与 tkinter 在哪里导入无关，不用改；
  若替换的是 `plotlib.dataloader.filedialog.askopenfilename`，挪进函数后模块上已没有 `filedialog` 这个名字，替换会失败，要改成替换 `tkinter.filedialog` 模块本身的属性
  （新测试 `test_cancel_file_dialog_raises` 就是这样做的，函数每次执行时才从 tkinter 模块里取）。
- 顺带修（测试隔离）：改完后全量测试从 11 秒变 55 秒并多一条 warning。原因是 `test_data_reorder_app.py` 建的 tk 变量挂在循环引用里，
  自动回收碰巧落在 Kaleido 渲染的后台线程，tk 对象在非主线程析构要等主线程的事件循环，卡住约 45 秒后报 "main thread is not in main loop"。
  该 fixture 销毁窗口后立即在主线程 `gc.collect()`，恢复到 15 秒、无 warning。

#### 7.2 逐样品变换

**读。** 脚本里出现 5 次的三行循环（行号会漂移，搜 `iter('samples')`）：`eis_bode.py` 两处，`eis_nyquist.py`、`tensile.py`、`select_demo.py` 各一处。
步骤 2 之后循环写作 `for dataslice in Selected_data.iter('samples'):`，每次产出一个样品的子数据集。

**定。** 这个能力放在哪、叫什么：`DataTransformer` 的一个参数，还是 `DataSet` 的一个方法。让用户比较两种写法在脚本里读起来哪个更顺。
命名按 `GLOSSARY.md`（「逐样品」用 sample，不用 group）。注意与 `Group.apply`（逐分组计算）区分：逐样品变换的结果仍按原样品号对应，逐分组计算的结果是新样品。

**测。** 新方法的结果与手写循环的结果完全相同（数值、名字、样品号）。**改。** 实现后把 5 处循环换掉。

**7.2 执行记录（2026-11-20，550 passed）。** 执行者给了两种写法：A `DataTransformer(…, per_sample=True)`、B `DataSet.map_samples(lambda s: …)`（推荐 B）。
用户都没选：B 的 lambda 不直观，A 和现在区别不大；**改为仿照 `Group.__iter__`，给 `DataSet` 加 `__iter__`，用 for 直接遍历样品**：
`for sample in dataset:` 等同于 `iter('samples')`（按样品出现的顺序，子数据集保留原样品号）。逐样品变换仍写成显式的 for + `expandata`，循环在调用处看得见。
- 5 处脚本循环 `for dataslice in X.iter('samples'):` → `for dataslice in X:`；`iter(method)` 保留（按名字、单位、通道遍历还要用）。
- 没加 `__len__`：加了会让空 DataSet 在 `if dataset:` 里变成假值，改变现有判断的含义。
- 用户问「for 只能按样品、其他字段仍用 `iter`，与 B 有区别吗」：执行者答 B 只是把「循环 + 拼接」包起来，同样只管样品；
  for 是默认按最常用的一维遍历（同 dict 遍历键、Group 遍历组名），其他维度用 `iter(...)` 明确指定。
  另提了 `DataSet.concat(… for s in selected)` 把累加写成一行，**用户定不加**：循环里的计算（尤其换成复杂的 `apply`）写开才看得清算了什么、用什么算的。
- 测试：for 与 `iter('samples')` 相同（稀疏样品号 0、5、9）、空数据集、逐样品 `Norm` 拼回后样品号不变（名字是 DataTransformer 的自动命名 `Results_0_of_S0`）。
- README 补「逐样品遍历与变换」一小节，GLOSSARY 样品一行加上 `for sample in dataset`。

#### 7.3 公开的列排序

`DataSet._rearrange_columns` 是私有方法，但脚本在用（`eis_bode.py`、`eis_nyquist.py` 各一处，搜 `_rearrange_columns`）。
它按「样品号 → 通道号」排序（测试 `test_rearrange_columns_sorts_by_sample_then_channel`）。
定一个公开的名字（建议 `sort_columns`），改名并更新 2 处脚本、相关测试。机械工作，只需用户定名字。

**7.3 执行记录（2026-11-20，550 passed）。** 用户同意 `sort_columns`。改名并补 docstring（原地排序、返回自己，可接在 `expandata` 后面）；删掉 `self.num_samples = self.num_samples` 等三行自我赋值；不留旧名（测试断言 `_rearrange_columns` 已不存在）；`eis_bode.py`、`eis_nyquist.py` 各一处、tests/README 同步。

#### 步骤 7 之后：全面评审、测试精简与诊断（2026-11-20，546 passed）

用户：「内部已经构建完，正式进入脚本之前，以客观角度把整个代码完全评审一遍；测试很多，检查必要性去除冗余；修复诊断问题」。

**评审结论（src 共 4500 行，逐文件通读）。** 分层清楚、各层只依赖下层：`DataPlotter` → `plan`（规则）→ `plot_spec`（约定）← `backends`；
样式对象 + 翻译层让两个后端逐段对应，叠加顺序只写在 `layouts.resolve_*`；报错都在创建时、信息带写错的值。绘图这一半结构稳定，可以「拿来用」。
数据层（`DataSet` / `DataProcessLayer` / `DataTransformer`）是最早的代码，接口风格较旧（`Selected_data`、`Norm`、`indicies` 等命名，B.9 已记暂不改）。

**已修（先写测试）：**
- `ColumnList.__len__` 按元素个数算，零行数据集（有列、没有行，如全部样品无峰的峰表）列数为 0，逐样品遍历 `IndexError` → 按列数算。
- `DataSet.update_attributes` 长度不一致时先 `print` 六行再抛异常 → 各项长度写进异常信息，不打印。
- 过时注释：`style.py` 三处（旧参数名 `x_format`、`DataPlotter 的 linestyle`、已改名的 `matplotlib_ticks.py`）、matplotlib 后端「见 `_layer`」、`DataSet.status` 的取值说明；
  matplotlib 后端图例回调循环里的局部变量 `legend` 与同名参数（原生参数字典）混用，改名 `made`。未使用的导入 3 处（`dataset.py` 的 `re` / `copy`、`processor.py` 的 `ColumnList`）。

**诊断（pyright：src / tests / tools / scripts 全部 0 错误）：**
- `tests/test_groups_code.py` 7 个：测试把 `None` 当 `self` 传给工具方法。`DataReorderGUI._get_ordinal_name` / `_get_linestyle_for_group` 不读界面状态，改成 `@staticmethod`
  （调用处 `self._xxx(i)` 不变）；读 `self` 的两个生成方法用替身对象，`cast` 标明（`fake_gui`）。
- `tools/data_reorder_qt.py` 4 个：`self.names` 可能为 None（两个分支都赋值，改读局部变量）；委托的 `parent()` 类型只是 `QObject`（`cast` 成 `CheckableListWidget`）。
- `tests/test_data_reorder_qt.py` 未使用的导入 1 处。

**测试精简（550 → 546；删 13 条用例、合并新增 8 条，另加 2 条回归）。** 按「别处已覆盖」去掉：
- `test_plotter` 的 `test_result_shape_is_uniform`（及 `make_all_kinds`，每个用例都把四种方法全画一遍）与 `test_plotly_backend` 的 `test_dataplotter_with_plotly_backend`
  → 合并为 parity 的 `test_result_shape_is_uniform`（后端 × 方法）；
- `test_plot_multiline_one_line_per_sample`（形状测试已覆盖）；两个后端的 `test_sparse_sample_ids_colors`（位置在计划层测，位置 → 颜色在 `test_backend_draws_only_from_plan`）；
- `test_iter_by_samples`（`test_for_loop_iterates_samples` 已与 `iter('samples')` 对比）；`test_reused_loader_with_unsupported_extension_raises`（加载器不再存状态，这类 bug 不会再有）。
- 其余 500 多条多是参数化的词表与回归测试，各测一件事，保留。

**留给用户定（未改）：**
1. ~~`naming_func` 返回 `sample_idx` 列表时 `TypeError`~~：执行者评估全部计算路径都是「一次计算一个样品」（逐样品沿用原号、跨样品合成一个新样品、`Group.apply` 每组一个），用户定收窄：`TransformMetadata.sample_idx` 只收 `int`，写成列表 / 小数 / 布尔值时给中文 `TypeError`（3 条测试）。
2. ~~`DataProcessLayer.__init__` 的 `input_data` / `input_dataname` / `input_dataunits` / `data_Process_Index` 与 `Processed_data` / `called_process` 全项目无人使用~~：用户定「预估以后用不上就删」——计算已由 `DataTransformer`（逐样品）和 `Group.apply`（逐分组）承担，这一层只管选列，已删；类说明改为「数据选择层」。
3. 柱状图、散点图的格式化从 `draw` 中独立出去（已记 BACKEND_PLAN 第 7 节，有数据时再做；用户确认）。
4. ~~报错语言不统一~~：用户定都改中文。`dataset.py` 的 4 处英文报错（单位不一致、列字段不存在 / 不可改、列号越界）改成中文并补上上下文，4 条测试改按中文匹配。用户问以后组员用能不能换语言：可以，到时把报错文字集中成消息表（或 gettext 的 `_()`）按语言取，现在不做。`plotlib.color_positions` 在包顶层导入但不在 `__all__`（步骤 3 用户暂留）。

#### 1.0 发布前复审修复（2026-11-20，`docs/ThirdPary_review.md`「1.0 发布前复审和建议 diff」，564 passed）

执行者逐条复现全部属实，第三方给的改法也对；用户：「直接修」。先写测试（新增 15 条，含 1 条渲染），全部先失败再改：
1. 双 Y 轴共用 X 轴的约定（不改代码）：左右 X 通道可以不同，但必须同一物理量、同一单位；写进 `plot_dual_y` 的 `left, right` 说明。
2. `select('samples', [0, 77])` 静默只选出 0 → 报「找不到样品号：[77]」并列出已有样品号；
   `DataTransformer` 先显式写到样品 3（`input_sample_idx` / `naming_func`）再 `new_sample=True` 曾也分到 3、两次结果并成一个样品 → 新样品号同时避开已累计的结果。
3. 读取时 pandas 默认把 `NA`、`N/A`、空格子当缺失值，样品名 `NA`、单位 `N/A` 读成 nan（7.1 改文本读取时留下的）→ 三种格式都 `keep_default_na=False`，
   数值区仍由 `pd.to_numeric` 转 NaN；样品名为空直接报错并指出文件第几列。
4. Plotly：`TickStyle(label_pad=...)` 换算后是小数，`ticklabelstandoff` 只收整数，绘图器建不起来 → 取整；
   这次写了 `limits` 时两端整体替换上一次的（写 None 的一端恢复自动），不再换算旧边界——先 `(-1, 30)` 再 `log + (1, 30)` 曾报「边界必须大于 0」，
   `(5, None)` 再 `(None, 30)` 下界曾残留；只改刻度类型时才换算已有边界。
5. 低优先级两项：`expandata` 回滚时连 `status` 一起恢复（`'loaded'` 曾变 `'written'`）；matplotlib 对数轴的单轴 `TickStyle(minor=True)` 盖不过全局 `minor=False`
   （只「保留默认定位器」仍算默认值，被后端补全局时关掉）→ 显式装对数次刻度定位器。
- 未处理（等发布时再说）：PyPI 上 `plotlib` 已被占用（发行名需另起，导入名可不变）；源码包缺 `tests/conftest.py`、`tools/`，包内测试跑不起来。

### 1.0 之后（2026-11-23）

#### 1.0 之后：文档字符串与 API 文档（2026-11-23，564 passed）

用户：「把 src 中所有函数的注释按 matplotlib 这种开源库的标准更新，解释性强一点、具体一点」。用户定：
1. **numpydoc 格式**：英文节标题（Parameters / Returns / Raises / See Also / Notes / Examples）+ 中文正文；
2. **开发历史移出文档字符串**：日期、审查编号、步骤号、「以前 / 曾经」不再写进文档字符串，设计理由写进 Notes；
   函数体里 `#` 开头的实现注释不动（历史线索仍在那里，完整记录在本文件）；
3. **按标准详略**：公开接口写完整并配 Examples，下划线开头的内部函数写简要说明；顺便建立 API 文档。

- 实施：17 个文件逐个用 Edit 改；开始前给 src 拍快照，每改完一个文件就用 ast 比对「去掉文档字符串后的代码」，
  全程确认一行代码没动。补上了原来缺的文档：两个后端类、`DataTransformer.apply`、`Column` 的各个属性、`group.py` 的模块说明。
  文档里写了输出的示例（`LineStyle.updated`、`color_positions`、`translate_points`、`Group`）都实际运行核对过。
- 顺带改正两处原文档的错误：`Group.apply` 的示例按 `names` 找 `"Frequency(Hz)"` 列（应按 `units`，`names` 是样品名）；
  `DataProcessLayer.by` 说「不能连续调用」（实际可以，每次在上一次结果里再筛）。
- API 文档：`docs/api/`（Sphinx + `pydata-sphinx-theme`，与 numpy、pandas 同一主题；napoleon 解析 numpydoc），
  「API 参考」每个公开对象一页，「内部结构」展示各模块说明（不建索引，避免与 API 参考重复）。`pyproject.toml` 加可选依赖 `docs`，
  生成的 `_build/`、`generated/` 加进 `.gitignore`。构建零警告。
- 中文与 reStructuredText 行内标记：标准规则要求标记前后是空格或标点，且结束标记后不能紧跟开括号「（」、开始标记前不能紧挨闭括号「）」。
  试过 docutils 的 `character_level_inline_markup`（不必改注释），但它会吞掉参数名里的下划线（`font_family` 显示成 `fontfamily`）且不报警告，
  所以改用标准规则：32 行在「``代码``」与「（」之间补一个空格；类型 `dict of {键: 值}` 改写成 `dict`（花括号会被当成取值集合）。
  以后写文档字符串：代码标记后面要接中文括号时先空一格。

#### Plotly 对数轴：刻度格式盖掉次刻度文字设置；多线图横轴不写预设格式（2026-11-23，567 passed）

- 现象：`piezo_interactive.py` 的 X 轴 `AxisStyle(scale='log', format='{x:.0e}')` 加 `TickStyle(minor_labels='none')`，
  Plotly 仍在 2e-3、5e-3 等位置写满文字。原因在 plotly.js 本身（7.1.0 的 formatLog）：写了 `tickformat` 就把每个刻度按格式写完整数值，
  跳过 `minorloglabels`；而跨的数量级不多时 Plotly 把 2、5 也当主刻度（matplotlib 里是次刻度）。
- 用户定（方案 1）：`plotly_styles.apply_log_format` 在所有回调之后由后端对每根轴调用一次：对数轴写了格式且次刻度不写文字（`'none'`，库默认）时
  设 `dtick=1`（主刻度只在整数量级，2 ~ 9 交给不写文字的次刻度，与 matplotlib 一致）；轴上已有 `dtick` / `tickmode` 时不动，
  所以跨很多数量级嫌挤可以用 `custom` 回调自己设 `dtick=2`；`'full'` 不用改；`'short'` 加格式 Plotly 做不到，报错。
- 代价：放大到一个数量级以内时轴上没有主刻度文字（用户：同一数量级大概率要看次刻度，不会设 `'none'`）。
- 随后（用户定）：多线图预设不再给 X 轴写 `'{x:.2f}'`（X 轴常改成对数轴，两位小数会把 1e-3 写成 0.00），交给后端自动；
  Y 轴仍是两位小数。`test_neglog_x` 原来靠预设格式直接调用格式器，改成渲染后看刻度文字（默认格式器要收到刻度位置才写得出数字），567 passed。

#### API 文档发布与自动同步（2026-11-23，571 passed）

- 发布：GitHub Pages（仓库公开），`.github/workflows/docs.yml` 在 push 到 main 且源码 / 文档 / 依赖有改动时构建（`-W`，有警告即失败）并发布到
  <https://sjrbcxk.github.io/PlotLib/>；仓库 Settings → Pages 的 Source 需选「GitHub Actions」。
- 同步（用户要求不靠记忆）：`docs/api/sync_api.py` 由 conf.py 在每次构建前调用——版本号从 pyproject.toml 读（`release`、`version`、标题、
  index.rst 的 `|version|`）；`plotlib.__all__` 里没登记的名字自动加进 reference.rst 同模块对象所在的分节（导出的优先），没有就放进「其他」节。
  只增不删：删掉的对象构建时报导入失败。`tests/test_docs_sync.py` 同时检查 reference.rst 登记齐全。

#### DataSet：列视图校验、列位置索引、使用时自动检查（2026-11-23，599 passed）

起因：第三方建议给「(样品号, 通道号) → 列位置」建索引（plan 每取一列都逐列扫描，300 样品时约 85 ms）。用户的设计前提：
元数据用平行列表是有意的（可整列替换、分步修改，中途允许不一致，`update_attributes()` 作统一检查点），不合成元数据表。

- 列视图校验（用户定）：`column.unit = …` 与 `column.sample_idx = …` 一样改完即校验、失败回滚（共用 `Column._set_checked`）。
  多样品数据集里只改一列单位通常会冲突；整体换一个通道的单位走自由入口：改 `dataset.units` 列表，使用时自动检查。
- 删 `generation`（只加 1、没人读）；`local_idx` 保留（用户：本地索引，配合 father / initial 区分前后位置）。
- 索引与自动检查（用户在 5 种做法里选「属性 + 使用时自动检查」）：
  - `DataSet.column_positions`：只读 `{(样品号, 通道号): 列位置}`，派生属性，在 `_get_channel_idx` 里与通道号同一遍扫描建好；
  - `ensure_updated()`：检查点记下快照（列数 + 7 个元数据列表的副本，只复制引用），使用前比对，变了就自动执行完整的
    `update_attributes()` （单位校验照常）；检查点开头先作废快照，检查失败的数据集每次使用都重查，不会因为「改回原样」沿用失败时重建了一半的索引；
  - 快照的写法：曾改用 Python `hash()`（只存一个整数），但 CPython 里 `hash(-1) == hash(-2)`，样品号 -1 改成 -2 检测不到；
    SHA-256 要先 `repr` 成字节，150 万列实测每次 0.3 s、临时占用 186 MB（副本 54 ms、常驻 84 MB），所以改回副本（用户定）。
    快照占数值矩阵的比例约 7 ÷ 行数，与列数无关；
  - 调用入口：`column_positions`、各 `plan_*`（每份计划取一次索引，经 `partial` 给各条线共用）、`Group` 校验、
    `DataProcessLayer.select`、`DataTransformer()`、`iter` / `for sample in dataset`、`sort_columns`；
  - Dataloader 改为走检查点（不再手填派生属性），之后状态仍记 `'loaded'`；没改过的数据集使用时不重查，状态不变。
- `iter` 改用分组索引 `{取值: [列位置]}`（一遍扫描），产出顺序不变；plan 的 `sample_name` 取 (样品, 0)，`channel_unit` 用 `list.index`；
  找不到时报错指明哪个样品、哪个通道。
- 正确性：对拍测试保留旧的逐列扫描作参照答案，在样品号不连续、列交错、拼接补 NaN、改样品号、排序后逐个 (样品, 通道) 比较；
  `iter` 四种分组与旧写法逐组比较；原有计划、取数、两后端对照测试不改全部通过。计时：300 样品 × 5 通道生成多线图计划 85 ms → 2.5 ms。
- 第三方复审的三个边界问题（都属实，605 passed）：
  1. 入口不一致：`Column.channel_idx`（派生值）和 `DataProcessLayer.getdata`（`select` 底下的公开方法）也先 `ensure_updated()`；
  2. 保存的索引过期：重建改为原地 `clear()` 再填，之前取到的只读视图在下次检查后也是新的；
     docstring 写明有效期（直接改了列表、还没被使用之前视图仍是旧的，随用随取）；
  3. 列视图修改失败回滚后状态变成 `'written'`：`Column._set_checked` 回滚时恢复原状态（与 `expandata` 一致）。
- 测试精简（用户：「能保证运行就行」）：今天新增的测试按「一类行为一条、场景在测试里循环」合并，605 → 573
  （索引与自动检查 4 条、Plotly 对数轴格式 1 条、文档同步 3 条、取数辅助 1 条；对拍和各边界断言都保留）。

### 柱状图、散点图（第 4 节）

#### 第一步：样式对象和 spec 按画法拆开（2026-11-23，573 passed）

- 约定（`plot_spec.py`）：新增 `ScatterStyle(color, marker, size)`；`CurveSpec` 拆成 `CurveBase`（图例、分组、配色、轴，只能按关键字给出）
  + `LineSpec` / `ScatterSpec`（样品号、x、y、各自的样式），去掉 `kind`；`FigureSpec.curves` 的类型是 `Curve = LineSpec | ScatterSpec`
  （加新画法就加进这个并集）；`AxesFormatter` 多一格 `scatter`。`BarStyle` / `BarSpec` 留到第二步。
- 翻译层（`style.py`）：新增 `check_scatter_style` / `translate_scatter_style`（matplotlib 的大小换成面积 `s`）；
  删掉 `STYLE_FIELDS_BY_KIND` 和 `only_fields`，每个样式对象只有自己的字段，后端用 `replace(style, color=None)` 去掉颜色（颜色仍由 `_curve_color` 一次给出）。
- 计划（`plan.py`）：`plan_multiline_figures` 与新的 `plan_scatter_figures` 共用 `_plan_samples`（规则只写一份），
  画法只决定 `_make_curve` 建哪种 spec、怎么从分组读样式（`_KINDS` 表：折线读线型 / 标记 / 颜色，散点只读标记 / 颜色）；
  三个规则函数不再经手样式，`NO_STYLE`、`_written_style` 删除；`plan_xy_figures` 只画折线；双 Y 轴 `kinds` 写错报错并列出可选值。
- 后端：两边的 `_native_style` + `_plot_data` 合成 `_draw_curve`，用 `match` 按 spec 类型选画法，不认识的类型报错；
  按轴回调时线条回调只收折线、散点回调只收散点（`_artists_of`）。
- 入口（`plotter.py`）：`plot_multiline` / `plot_groups` / `plot_xy` 去掉 `plot_kind`；新增 `plot_scatter`（有分组按分组、没有画全部，同 `plot_groups` 规则）；
  `plot_dual_y` 新增 `scatter_formatter` / `right_scatter_formatter`（放在参数最后，不打乱位置参数）。
  回调工厂新增 `make_scatter_formatter`；`make_lines_formatter` 不再处理散点、柱。`ScatterStyle`、`make_scatter_formatter` 加入 `__all__`，
  文档同步测试先报漏登记、构建时自动登记（随后手动挪到折线对应项旁边），自动同步按设计工作。
- 测试：新增 3 条（计划共用规则与按画法取样式、`plot_scatter` 两后端一致、线条 / 散点回调解耦），
  删去走 `plot_kind='bar'` 的 3 条（柱状图在第二步按 `plot_bars` 重测），其余改用新类和新方法；573 passed，pyright 0 错误。
- 扩展性检验的结论：加一种画法要动的地方是 spec 类型、样式对象、翻译函数、计划里 `_KINDS` 一行、两个后端 `match` 各一支、回调一格，
  规则（分组、配色、去重）和结果形状都不用改。`DrawnFigure.artist` 按 `getattr(curve, 'sample_idx')` 取，给第二步不带样品号的 `BarSpec` 留了余地。
- 随后（576 passed）：`ScatterStyle` 补上两个后端都有的 `filled`（空心：填充透明只留描边）、`edge_color`、`edge_width`、`alpha`
  （用户：尽量多兼容）；新增库默认 `DEFAULT_SCATTER(marker='circle', size=6, filled=True, edge_width=1)`，画散点时总是先套上；
  `translate_scatter_style(..., fallback_color=)` 接收后端算好的色带色。修第三方复审 3 条：① 全局 `LineStyle(marker_size / width)`
  曾漏到散点（matplotlib rc、Plotly 模板）→ 套 `DEFAULT_SCATTER` 后大小、描边都写明；② 尺寸写 NaN / 无穷大曾通过校验 →
  `_check_positive` 拒绝非有限值（对所有尺寸生效）；③ 双 Y 轴 `kinds` 长度不是 2 曾 IndexError / 静默忽略 → 报错。
- 再修复审 2 条（578 passed）：① 先 `filled=False` 再 `filled=True`（没写 color）恢复不了实心：空心后对象上只剩透明填充，
  原色丢了 → 后端画散点时用 `style.remember_fill` 把填充色记在对象上（Plotly 记在 `fig.data[-1]`，`add_trace` 会复制），
  散点回调写 color 时更新、只写 `filled=True` 时取回（没记过退回当前描边色），单独写的描边色不受影响；
  ② matplotlib 的 `'x'`、`'cross'` 是线形标记，传 `edgecolors` 会警告（开「警告即错误」就画不出）→ 画的时候先不传，
  画完用 `set_edgecolor` 补上，对象状态和其他标记一致（`style.is_line_marker` 判断）。
- 复审又补 1 条：原生回调（`custom`）改的填充色没被记住，之后 `filled=True` 会换回画图时的颜色 → 填充色以对象上的
  实际状态为准：散点回调开始时当前有填充就先记下；`filled=True` 只在当前空心时才填回，已是实心不动。
  空心的写法收成 `style.HOLLOW_FILL`，翻译和回调共用。

#### 第三方只读审查 14 项（2026-11-23，591 passed）

审查覆盖整个 `src`，14 项都是实现没跟上文档或预期，不涉及新的设计取舍。每类行为补一条回归测试（共 13 条，#8 并进散点回填那条）。

- 数据处理：
  - ① 跨样品计算的结果曾留空样品号，`update_attributes` 每次补成 0 → 按类说明分配新样品号（与 `new_sample` 共用分配器）；
  - ② `DataTransformer` 创建时缓存了数据集的列表，数据集排序后按位置读到旧列 → `data` / `names` / `units` / `sample_idx` / `column`
    改成属性，每次从数据集现读（先 `ensure_updated`）；原来没有用到的 `local_idx` / `father_idx` / `initial_idx` 拷贝去掉；
  - ③ `Norm` 的整数平方在整数类型里溢出、浮点中间平方溢出 → `_row_norm`：先换成浮点，按每行最大绝对值缩放后再算；
  - ④ `select` 某个条件失败时前面的条件已写进 `Selected_data` → 在本地累计，全部成功才写回；`by` 失败时恢复 `called_select`；
  - ⑥ `select(-1)` 把 -1 记进 `father_idx` / `initial_idx` → `getdata` 把负数位置换成真实位置（越界报 `IndexError`）；
    `columns_to_dataset` 的 `father_idx` 曾沿用更早一层 → 改成列在所在数据集里的位置 `col.local_idx`；
  - ⑦ 校验失败时列索引视图已被改写 → `_get_channel_idx` 只计算，单位校验通过后才写回通道号和列索引（仍原地更新）；
  - ⑫ 回调返回 Python 标量时直接访问 `.ndim` 报错 → 先 `np.asarray`（`DataTransformer.apply` 和 `Group.apply`），回调类型标注同步放宽。
- 绘图：
  - ⑤ matplotlib `limits=(None, 15)` 留着之前设过的下界 → 有一端没写时先 `ax.autoscale` 再设写了的一端（与 Plotly 一致）；
  - ⑧ 散点逐点颜色：matplotlib 只记了第一个点的颜色、Plotly 的数组颜色做比较时报错 → 整组读写，只有字符串才和空心写法比较；
  - ⑨ Plotly `tickformat=''` 被当成显式格式 → 空字符串与没写相同；
  - ⑩ 线性轴的负对数标签在文字前拼负号，写出 `-−2.5`、偏移仍是 `+1e6` → 不是对数轴时把取负后的值交给原格式器，
    负号和偏移都由它处理（matplotlib 用 Unicode 的 `−`；对数轴不变，仍加 `-`），两条老测试的正则同步放宽；
  - ⑪ 开次刻度时 logit、symlog 被换成线性细分 → 用刻度类型自带的次刻度定位器（`_scale_minor_locator`，借 `axis._scale` 设一遍默认再放回主刻度）；
  - ⑬ 回调出错后 matplotlib 图窗留在 pyplot 里 → 后端出错时关掉这张图；分组多张时 `DataPlotter` 用后端的 `close` 关掉已画好的前几张；
  - ⑭ 无效的 matplotlib 刻度格式拖到渲染才报错 → 翻译时先用 1.0 试格式化一次。
- 扩展复查又补 4 项（仍 591 passed，场景并进上面的回归测试）：
  - 变换器创建后源数据集又加了样品，自动分配仍撞号 → 分配时避开源数据集当前的、输入列的、已累计结果的样品号；
  - ③ 的修复引入回归：先转浮点丢了复数虚部（`3+4j` 得 3）、负阶按最大值缩放下溢成 0 → 复数先取模；
    负阶按每行最小值缩放（负阶由最小的数主导），缩放后的溢出警告忽略（inf 的负次方是 0）；随机数据与原公式对照，最大相对误差 4e-16；
  - 按 `Column` 取列不校验列所在的数据集（同通道单位冲突照样算）→ 先对各列所在的数据集 `ensure_updated`，与按位置取列一致；
  - ⑤ 两端都写 `None` 时 `set_xlim` 又关掉了自动缩放，之后加的曲线撑不开范围 → 两端都是 None 只开自动缩放、不再设范围。
    只写一端时 matplotlib 没有「单侧自动」，写了的一端固定、另一端按当时的数据算。
- 再补 1 项（低优先级）：`complex64` 的 `3e38+3e38j` 取模在单精度里溢出成 inf（`order=-1` 应得约 2.12e38）→
  取模前用 `np.promote_types` 提升到至少双精度（复数 `complex128`、实数 `float64`，精度更高的不降）。

---

## 附录 A：初始评估（2026-11-16，基线 `5cb8d4d`）

> 原 `STRUCTURE_REVIEW.md` A 部分。描述的是基线提交时的状态，路径按当时的 `src/xxx.py` 书写（现在位于 `src/plotlib/xxx.py`）；
> 其中的行号、以及已经解决的条目，不代表现状。

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

## 附录 B：整理记录与原进度表

### 整理（原 C 部分）


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

### 原进度表（原 B.10，记录到步骤 7.3）

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
| 6 绘图计划与后端 | 完成   | 2026-11-20 | 6.1（`2d87f86`）、6.2（`d6f7af6`）、6.3（`b0d65dd`）已提交；之后绘图测试按层整理（用户提出，B.0 改为「测试跟着需求走」）；路线调整：先建后端（6.4 计划补全 → 6.5 统一结果 → 6.6 matplotlib 后端 → 6.7 Plotly 后端，删除 `InteractivePlotter`），原 6.4 按组翻页挪到 6.8（测试已写，标 xfail）。6.4 完成：计划补全（图层面单位 / neglog / 版式，xy 与双 Y 轴计划），`subplotter_yy` 改名 `subplotter_xy`，xy 颜色不变（色带位置可为 None），`figsize` 对所有方法生效。6.5 完成：结果统一为 `figures = {key: DrawnFigure}`（替换 `axesset`），颜色一次赋值（分组颜色对散点 / 柱也生效），删 `color_positions` 属性。6.6a 完成：建 `backends/`，`MatplotlibBackend.draw` 只读计划，`DataPlotter` 只剩「计划 → `_render` → 存结果」，`Appearance` / `AxesFormatter`，整图回调统一 `(fig, axes)`。6.6b 完成：`layouts.py` 排版预设，后端三种版式合成一段 `_draw`，双 Y 轴红蓝只由预设定。6.7 完成：`PlotlyBackend`、翻译层（`style.py`）、显式 dpi、`DataPlotter.add_slider`，删除 `InteractivePlotter`。之后结构确认：拆出 `plot_spec.py` / `plan.py`，公开接口统一命名。之后第三方审查修复（插在 6.8 前；第一组、第二组、双 Y 轴版式与 `legend_title`、F 全部完成，基线 472）。6.8 完成：凡是多张计划，Plotly 都画成一个 Figure 多页（`draw_pages`），
翻页滑块 `add_page_slider`（原定 `add_group_slider`，范围扩大后改名；用户要求也支持 single / cumulative，两种滑块共用 `_install_slider`），约定新增 `FigureSpec.name`。基线 484。6.1 完成：重复样品保持先到先得、归属单独一步；拆成三个内部函数（用户提出）。6.2 完成：合并模式柱状图改为组首色（选 A）；新增 `figsize`；删除 `plot_artists`。6.3 完成：Plotly 按计划画，新增 `plot_plotly_group`（合并模式）、`_LINE_WIDTH`；删除 `_get_color`；按组翻页改为按 `FigureSpec` 分页（现 6.8）；颜色统一为一次赋值（用户决定，现 6.5）。基线 385 |
| 7.1 `Dataloader` 接口    | 完成   | 2026-11-20 | 全按建议：`Dataloader(columns_per_sample=N).load_data(path=None)`，删 `DATASET_FRACTION`；取消选择抛 `NoFileSelected`；扩展名不区分大小写；tkinter 函数内导入；加载器不存中间状态（见 7.1 执行记录）。基线 547 |
| 7.2 逐样品变换             | 完成   | 2026-11-20 | 用户定：不加新方法，仿照 `Group.__iter__` 给 `DataSet` 加 `__iter__`（`for sample in dataset` 同 `iter('samples')`），5 处循环改成直接 for（见 7.2 执行记录）。基线 550 |
| 7.3 公开的列排序           | 完成   | 2026-11-20 | `_rearrange_columns` → `sort_columns`（用户同意推荐名），不留旧名；删掉三行多余的自我赋值；2 处脚本、测试同步。步骤 7 完成。基线 550 |
| 8 脚本可复现               | 未开始 |          |                                |

## 附录 C：多后端的推进方式与早期进度（原 `BACKEND_PLAN.md` 第 4、5 节）

### 推进方式


抽象方案一开始难以下手，所以选择“先具体、后合并”：

1. 先在 scripts 里跑通滑块图；
2. 把 DataPlotter 的基础结构复制到 `interactive.py`，绘图与格式部分边学边写；
3. 有两个具体实现后，再对比、提取公共部分。

每一步都要有可运行的终点。

**2026-11-18 调整：** 第 1、2 步之后，分组（`Group`）、样式（`style.py`）、配色（`color_positions`）已经公共，分组规则也已定并有测试保护，
matplotlib 的分组模式就是那份「具体实现」。因此第 3 步不再先在 Plotly 里复制一份 `group_plotter`，而是先把分组规则抽成绘图计划（第 4 步的一部分），
再让 Plotly 按同一份计划画。顺序变为：接上 `Group`、共用取数 → 分组绘图计划 → matplotlib 按计划画 → Plotly 按计划画（即第 3 步）→ 其余模式。
对应 `STRUCTURE_REVIEW.md` 步骤 5、6。

**2026-11-19 调整（用户提出）：先建 backend，再加新功能。** Plotly 按组翻页（原 STRUCTURE_REVIEW 6.4）要动「一个 Figure 画多页」「结果存哪」，
正是建 backend 时要定的接口，先写会被重写。backend 的接口就是计划，所以顺序为：
计划补全并定型（Y-Y、双 Y 轴、图层面的单位 / neglog / 版式；6.4）→ 统一结果形状与清理（6.5）→ matplotlib backend（6.6）→
Plotly backend，删除 `InteractivePlotter`（6.7）→ Plotly 按组翻页（6.8）。同时定下：
- 唯一入口 `DataPlotter(..., backend=...)`，`InteractivePlotter` 删除；
- 外观参数（字号、线宽、图例字号、`figsize`）是公共参数，各 backend 翻译（原则 4）：matplotlib → `rc_params`，Plotly → 模板，`figsize` 英寸 × 100 成像素；
- formatter 统一为 `axes_formatter / lines_formatter / legend_formatter` 三个名字，各 backend 用原生对象调用（matplotlib 传 `ax, fig` / `lines` / `legends`，Plotly 都传 `fig`），
  `figure_formatter` 去掉；
- 滑块只属于 Plotly（原则 3），matplotlib backend 调用时明确报错（原则 5）。

### 进度

| 步骤 | 内容 | 状态 |
|---|---|---|
| 0 | 恢复测试基线；稀疏样品号的稳定配色 | ✅ 配色于 2026-11-17 完成：`plot_common.color_positions`，两个绘图器共用 |
| 1 | `plot_plotly_object(figure_formatter=...)`、`add_slider(slider_formatter=...)` 两个回调入口 | ✅ |
| 2 | 格式化器收进 `formatters.py` | ✅ 三个工厂支持 `backend="plotly"`，另有 `combine_formatters`；滑块 formatter 工厂暂未做 |
| 3 | 交互绘图补分组模式：`InteractivePlotter` 接上 `Group`（STRUCTURE_REVIEW 5.1）；按与 matplotlib **同一份绘图计划**画分组（6.3，✅ 合并模式 `plot_plotly_group`）；6.7 ✅ `DataPlotter(backend='plotly')` 五种画法与 matplotlib 对照一致；分离模式 = 一张图按组翻页，每页是计划里的一张 `FigureSpec`（6.8） | ⏳ |
| 4 | 提取公共部分为绘图计划：共用取数（5.2，✅ `plot_common.get_xy_data`）→ **从分组模式开始**抽计划（6.1，✅ `plot_common.plan_figures`，6.4 后改名 `plan_multiline_figures`）→ matplotlib 按计划画（6.2，✅ `DataPlotter._draw_figure`）→ Plotly 按计划画（6.3，✅）→ 计划补全：xy（原 Y-Y）、双 Y 轴、图层面信息（6.4，✅ 四种绘图方法全部按计划画）→ 结果形状（6.5，✅ `figures = {key: DrawnFigure}`，颜色一次赋值）→ 建 `backends/`（6.6 matplotlib，✅ 6.6a `MatplotlibBackend.draw(spec) -> DrawnFigure`、`DataPlotter(backend=...)`；✅ 6.6b 排版预设 `layouts.py`，两个后端共读；✅ 6.7 `PlotlyBackend`，删除 `InteractivePlotter`）；创建图、绘制、默认格式、原生回调交给 backend。分组部分先于第 3 步完成 | ✅ |

第 3 步验收：相同选列与分组配置下，两个 backend 得到相同的数据、标签和分组顺序（同一份计划交给两个 backend）。
第 4 步验收：旧的 matplotlib 测试行为不变；切换 backend 后曲线数量、数据、标签、顺序一致。
