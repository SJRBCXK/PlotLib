# 多后端绘图规划（matplotlib / Plotly）

> 记录时间：2026-11-13。来源：与 Claude 的架构讨论。
> 进度表请随实现更新；架构原则未经重新讨论不要改动。
> 用词按 `GLOSSARY.md`：样品（一次测量，原「数据组」「实际组号」）、通道（样品内的列）、分组（若干样品的集合）。2026-11-16 起统一。

## 1. 目标

同一份数据、同一套绘图模式（普通叠加、分组、逐样品关系图、双 Y 轴），可以选择不同 backend 渲染：
matplotlib 出静态图，Plotly 出交互图 / HTML。

**不维护两个相似的完整绘图类**：只保留一个绘图器作为数据与模式入口，配多个渲染实现。

## 2. 当前架构（2026-11-20 定稿）

> 原「目标架构」已全部实现（STRUCTURE_REVIEW 步骤 6.1 ~ 6.7，以及 6.7 之后的结构确认）。以后改结构要重新讨论。

```text
Dataloader → DataSet → 按需 select / by / DataTransformer / Group.apply
        │              │
        │              ▼
        │        Group(dataset, config)：分组的唯一主人（2.1 节）
        ▼              ▼
DataPlotter(dataset, groups, channel_x, channel_y, 外观参数, figsize, dpi, backend)   ← 唯一入口（plotter.py）
   plot_multiline / plot_groups / plot_xy / plot_dual_y：计划 → _render → figures；add_slider（Plotly）
        │ ① 生成计划（plan.py：规则）
        ▼
   list[FigureSpec]（plot_spec.py：约定）
   图：key、单位、neglog、版式；线：数据、标签、色带位置、样式（标准写法）、画法、左 / 右轴
        │ ② backend.draw(spec, figsize, formatters, figure_formatter)
   ┌────┴─────────────────────┐
   ▼                          ▼
MatplotlibBackend          PlotlyBackend          （backends/：只管渲染，两份逐段对应）
   读：layouts.py（排版预设）、style.py（翻译层：标准写法 → 原生值，按 dpi 换算单位）
        │ ③ 交回 DrawnFigure(spec, fig, axes, artists)
        ▼
DataPlotter.figures = {FigureSpec.key: DrawnFigure}；取线 figures[key].artist(样品号, 轴)
   （多张计划时 Plotly 用 draw_pages 画成一个 Figure 多页，各页共用 fig；add_slider 一条线一档，add_page_slider 一页一档）
```

| 模块 | 职责 | 依赖 |
|---|---|---|
| `plotter.py` | `DataPlotter`：唯一入口。选计划函数、定默认尺寸、把用户回调按轴打包、交给后端、存结果；不导入绘图库 | plan、plot_spec、backends |
| `plan.py` | 规则：`plan_multiline_figures` / `plan_xy_figures` / `plan_dual_y_figures`，以及 `color_positions`、`resolve_groups`、取数 | plot_spec、DataSet、Group |
| `plot_spec.py` | 约定：样式对象 `LineStyle` / `AxisStyle` / `FrameStyle` / `LegendStyle` / `TickStyle` 与库默认 `DEFAULT_*`（2026-11-20 样式对象化）；`CurveSpec`（`style` 是 `LineStyle`）、`FigureSpec`、`DrawnFigure`、`Appearance`（用户写的那一层样式、`dpi`）、`AxesFormatter`；不含规则、不导入绘图库 | numpy |
| `layouts.py` | 排版预设：每种版式的图例（`LegendStyle`）、边框（`FrameStyle`）、各轴（`AxisStyle`：刻度格式、着色）、边距；`resolve_legend` / `resolve_frame` 是唯一写叠加顺序的地方（库默认 < 预设 < 全局） | plot_spec |
| `style.py` | 翻译层：线型 / 标记 / 颜色 / 图例位置 / 刻度格式 / 刻度（`TickStyle`）的标准写法 → 各后端原生值；磅、英寸按 dpi 换算 | plot_spec |
| `backends/` | `get_backend(name, appearance, cmap)`；`MatplotlibBackend`、`PlotlyBackend`：公开方法 `draw`（一张计划一张图）；Plotly 另有 `draw_pages`（多张计划画成一个 Figure 多页，6.8）、`add_slider` / `add_page_slider`；`DataPlotter` 按「后端有没有这个方法」决定用不用；只依赖约定，不依赖规则；`matplotlib_styles.py` 把翻译好的样式用到 matplotlib 对象上（后端与格式化器共用，不导入 pyplot）；`plotly_styles.py` 是 Plotly 一侧的对应（`apply_axis` / `apply_frame` / `apply_ticks`、`figure_dpi`；与 matplotlib 不同，收样式对象、应用时才翻译：磅按这张图的 dpi 换算、对数轴边界按轴的实际类型换算；不导入 plotly） | plot_spec、layouts、style |
| `formatters.py` | 用户回调工厂 `make_*_formatter(backend=...)`、`combine_formatters`（前端接口，按 backend 参数区分，不按后端拆文件）。回调由后端按轴调用，两个后端形状对应：axes `(ax \| 轴名, fig)`、lines（这根轴的线）、legend（图例列表） | style |
| `html_export.py` | 把 Plotly Figure 导出成随窗口缩放的 HTML | plotly |

依赖只朝一个方向：入口 → 计划 → 约定 ← 后端；后端不认识 `DataSet`、`Group`、`DataPlotter`，也不依赖规则。
`import plotlib` 不加载 Plotly 和 pyplot：后端在 `get_backend` 里用到时才导入。

公开接口的命名（2026-11-20 统一，与计划层、`Appearance`、GLOSSARY 一致）：
构造参数 `dataset`、`channel_x` / `channel_y`、样式对象 `lines` / `frame` / `legend` / `ticks`（2026-11-20 起替换 `line_width`、`linestyle`、`axis_width`、`legend_font_size`、`tick_width`）、`dpi`、`backend`；
方法名「plot_ + 版式」；方法参数 `neglog_x` / `neglog_y`（双 Y 轴再有 `neglog_x2` / `neglog_y2`）、`plot_kind`（双 Y 轴 `plot_kinds`）、
双 Y 轴 `left=(X, Y)` / `right=(X, Y)`、按轴回调 `axes_formatter` 等（右轴 `right_axes_formatter` 等）、整图回调 `figure_formatter(fig, axes)`。

### 2.1 分组输入约定（`Group`，2026-11-18 定稿）

分组（若干样品组成的、有名字的集合）只由 `src/plotlib/group.py` 的 `Group` 解析和校验；两个后端都只通过下面的接口读取，不自己解析配置字典。
用词见 `GLOSSARY.md`：样品号 = `sample_idx`，通道号 = `channel_idx`，分组 = `Group`。

**配置写法（唯一一种）**：`{分组名: {'num': 样品号, 其余字段...}}`。
`num` 可写 int / list / tuple / range / ndarray；样式字段 `linestyle` / `marker` / `color` 只收标准写法（见 2.2 节），创建时校验、原样保存；
其余字段（如 `label`）不检查，原样保存，留给以后的 `group_style_applyer`。
简写 `{'A': [0, 1]}` 不支持，报 `TypeError` 并提示正确写法。

**创建 `Group(dataset, config)` 时**：
- 逐个分组校验：是否为字典 → 有无 `num` → `num` 类型 → 元素是否为整数 → 是否为空 → 样品号是否重复 → 是否在数据集中。
  类型错报 `TypeError`，值错报 `ValueError`，信息都带分组名；样品不存在时还列出全部不存在的和已有的样品号。
- 数据集里的样品号每次现查（`set(dataset.sample_idx)`），不存快照，因为 `DataSet` 可能被 `expandata` 扩充。
- **原地格式化**（用户的设计决定）：把每个分组配置里的 `num` 改为 `list[int]`。`Group` 的外层字典是自己的，各分组的配置对象与传入的字典共用。
  已知取舍：创建后在脚本里直接改分组配置会绕过校验。

**读接口**（都返回副本，改返回值不影响 `Group`）：

| 接口 | 返回 |
|---|---|
| `group.names`（property） | 分组名列表，保持书写顺序 |
| `for name in group` | 按书写顺序遍历分组名（遍历的是 `names` 的副本，循环中增删分组不会出错） |
| `group.sample_ids(name)` | 该分组的样品号列表，**保持书写顺序**：顺序就是角色，如 `apply` 里的 `slices[1] / slices[0]` |
| `group.options(name)` | `num` 以外的全部字段，如 `{'linestyle': 'dash'}`；没有则为 `{}` |
| `group.linestyle(name)` / `marker(name)` / `color(name)` | 用户写的标准写法；没写为 `None`。翻译成后端原生值是绘图器的事 |
| `group.to_config()` | 当前配置的新字典（`num` 为列表），用于保存或打印；绘图器**不用**它读取分组 |

**修改接口**（参数格式与构造函数相同；先校验全部、再修改，任何一个分组不合法就一个都不改；返回 `self`）：
`add(config)` 只新增（已存在报错）；`set(config)` 整体替换已有分组，旧字段不保留，位置不变（不存在报错）；`delete(name)`。

**计算**：`group.apply(callback, select, naming)` 每个分组的结果成为结果数据集里的一个新样品（样品号从 0 起）。

**绘图器的约定**：
- 分组参数名 `groups`，**只接受 `Group` 对象**（传字典报 `TypeError`，类型标注只在编辑器里提醒，运行时用 `isinstance` 检查）。
- 一个绘图器只对应一个数据集和一个 `Group`：`groups.dataset is not input_dataset` 时报 `ValueError`。不复制、不重建 `Group`。
- 不传时为空 `Group`（`names == []`），`group_plotter` 退回普通多线图。
- 配色用 `plan.color_positions(dataset.sample_idx)`，按整个数据集排名一次，同一样品在各张图里颜色一致；合并模式的组首色 = `sample_ids(name)[0]` 的颜色。
- 分组样式写了就应用（两种模式一样，目前仅折线）；`color` 写了时整组同色。没写线型用 `plot_style`。优先级：默认样式 < 分组样式 < `lines_formatter`。
- 现状：两个绘图器都按此接收 `groups`（属性 `self.groups`），三种情况的检查共用 `plan.resolve_groups`；
  两个后端都按同一份绘图计划（`plan.plan_multiline_figures`）分组绘图，样式翻译各自在 `_native_style`；6.7 起只有一个入口 `DataPlotter(backend=...)`；Plotly 分离模式现在每组一个 Figure，按组翻页见 STRUCTURE_REVIEW 6.8。

字段拼写不检查（2026-11-18 用户决定：`options` 返回全部字段，写错时一眼能看出来）。

### 2.2 样式的标准写法（`style.py`，2026-11-18 定稿）

程序入口（分组配置、`make_lines_formatter`、`DataPlotter(plot_style=...)`）只接受一套与后端无关的标准写法，不认识就报错，也不替用户改写；
后端渲染时用 `style.translate_*(value, backend)` 翻译。这是原则 4 的具体化：前端一套词，后端各自翻译。

| 字段 | 标准写法 | matplotlib | Plotly |
|---|---|---|---|
| 线型 | `'solid'`、`'dash'`、`'dot'`、`'dashdot'` | `'-'`、`'--'`、`':'`、`'-.'` | 同名 |
| 自定义虚线 | `(实线长, 空白长, ...)`，正数、偶数个，单位是线宽的倍数 | `(0, (…))` | `'9px,15px'`（段长 × 线宽；偏移量不支持） |
| 标记 | `'circle'`、`'square'`、`'triangle-up'`、`'triangle-down'`、`'diamond'`、`'cross'`、`'x'` | `'o'`、`'s'`、`'^'`、`'v'`、`'D'`、`'+'`、`'x'` | 同名 |
| 颜色 | CSS 颜色名（148 个，不区分大小写）、`'#rrggbb'` | 原样 | 原样 |
| 颜色 | RGB 三个 0~255 的整数 | 各分量 ÷ 255 | `'rgb(r,g,b)'` |

加新词：在 `style.py` 的表里加一行，两个后端各写一个原生值。matplotlib 的 `CSS4_COLORS` 与 Plotly 的颜色名是同一套，颜色名不用翻译。

## 3. 原则

1. **职责分层**：取数 → 绘图 → 格式化，三者分开。不要把取数和渲染绑在一起。
2. **模式只实现一次**：分组顺序、重复样品去重、样式归属、曲线属于哪张图 / 哪个轴，都在公共层决定。不在每个 backend 各写一份 `group_plotter`。
3. **滑块是画完之后的可选交互**，不是一种新的绘图模式。它只控制已有曲线的显隐，不重新取数，也不做 Python 端计算。
4. **公共配置翻译，原生回调不翻译**：
   - 常用设置（范围、尺度、线型、线宽、字号、图例位置）用同名参数，由各 backend 翻译；
   - `ax.spines`、`FuncFormatter`、`fig.update_*` 这类原生操作，保留为各后端自己的回调。使用原生回调，就表示这部分不保证跨后端兼容。
5. **扩展能力显式检查**：某个 backend 不支持的功能要明确报错，不要悄悄忽略或改成别的效果。
6. **回调统一约定**：接收对象并原地修改，返回值忽略。执行顺序固定为：默认格式 → 用户 formatter → 保存结果。
7. **翻译不只是改参数名**：例如 Plotly 对数轴的 `range` 用 log10 值，需要 backend 换算；`xscaler` 只改变刻度显示，不等于把数据乘以系数。

## 4. 推进方式（已选定）

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

## 5. 进度

| 步骤 | 内容 | 状态 |
|---|---|---|
| 0 | 恢复测试基线；稀疏样品号的稳定配色 | ✅ 配色于 2026-11-17 完成：`plot_common.color_positions`，两个绘图器共用 |
| 1 | `plot_plotly_object(figure_formatter=...)`、`add_slider(slider_formatter=...)` 两个回调入口 | ✅ |
| 2 | 格式化器收进 `formatters.py` | ✅ 三个工厂支持 `backend="plotly"`，另有 `combine_formatters`；滑块 formatter 工厂暂未做 |
| 3 | 交互绘图补分组模式：`InteractivePlotter` 接上 `Group`（STRUCTURE_REVIEW 5.1）；按与 matplotlib **同一份绘图计划**画分组（6.3，✅ 合并模式 `plot_plotly_group`）；6.7 ✅ `DataPlotter(backend='plotly')` 五种画法与 matplotlib 对照一致；分离模式 = 一张图按组翻页，每页是计划里的一张 `FigureSpec`（6.8） | ⏳ |
| 4 | 提取公共部分为绘图计划：共用取数（5.2，✅ `plot_common.get_xy_data`）→ **从分组模式开始**抽计划（6.1，✅ `plot_common.plan_figures`，6.4 后改名 `plan_multiline_figures`）→ matplotlib 按计划画（6.2，✅ `DataPlotter._draw_figure`）→ Plotly 按计划画（6.3，✅）→ 计划补全：xy（原 Y-Y）、双 Y 轴、图层面信息（6.4，✅ 四种绘图方法全部按计划画）→ 结果形状（6.5，✅ `figures = {key: DrawnFigure}`，颜色一次赋值）→ 建 `backends/`（6.6 matplotlib，✅ 6.6a `MatplotlibBackend.draw(spec) -> DrawnFigure`、`DataPlotter(backend=...)`；✅ 6.6b 排版预设 `layouts.py`，两个后端共读；✅ 6.7 `PlotlyBackend`，删除 `InteractivePlotter`）；创建图、绘制、默认格式、原生回调交给 backend。分组部分先于第 3 步完成 | ✅ |

第 3 步验收：相同选列与分组配置下，两个 backend 得到相同的数据、标签和分组顺序（同一份计划交给两个 backend）。
第 4 步验收：旧的 matplotlib 测试行为不变；切换 backend 后曲线数量、数据、标签、顺序一致。

## 6. 暂时不做

- 不改 `DataSet`、`DataTransformer` 的职责；
- 不自动翻译任意 matplotlib 回调；
- 不引入 Dash 或自定义 JavaScript（如滑块的任意区间筛选）；
- 不一次性统一全部格式参数；
- 不改旧脚本的三个 formatter 接口；
- 不把峰值汇总图这类特殊绘图强行纳入普通多线模式。

## 7. 已知遗留问题

- ~~**稀疏样品号配色越界**~~（2026-11-17 已解决）：两个绘图器原来都按「样品号 ÷ 样品数」取色，样品号不连续时 Plotly `IndexError`、matplotlib 静默同色。
  现在由 `src/plotlib/plot_common.py` 的 `color_positions` 统一计算：去重排序后，位置 = 排名 ÷ 样品数；映射在构造时按整个数据集建一次。
  matplotlib 用 `cmap(位置)`、Plotly 用 `sample_colorscale(色带, [位置])` 各自取色。两个绘图器的 `num_samples` 构造参数已删除。
- **子集与全集颜色一致**（遗留，暂不做）：配色按「本次绘图的数据集」排名，从全集中挑出部分样品单独画时，颜色与画全集时不同。
  这是有意的默认：子集按自身排名，对比度更好。需要时给绘图器加可选参数（如 `color_reference=全集样品号`），默认 `None` 保持现状。
- ~~**`InteractivePlotter` 还没有接上 `Group`**~~（2026-11-18 已解决，STRUCTURE_REVIEW 步骤 5.1）：构造函数第一个参数 `plot_data_group` 必填却未使用，
  `plot_data_groups` 只保存不使用。要按 2.1 节的绘图器约定改：删掉第一个参数，改为可选的 `groups: Group | None`，三种情况的检查与 `DataPlotter` 相同；
  届时把检查移进 `plot_common.py`（如 `resolve_groups(groups, dataset) -> Group`），两个绘图器共用。随之更新测试中 12 处 `InteractivePlotter(None, ...)`、
  `scripts/piezo_interactive.py` 和 README。
- ~~axes formatter 写死刻度宽 3~~、~~「目标轴」~~、~~`combine_formatters` 两个后端通用~~：2026-11-20 第三方审查修复第二组已完成
  （按轴回调由后端交出这根轴的东西，见 STRUCTURE_REVIEW「第三方审查修复」）。
- **功能待办（不影响结构）**：Plotly 的上轴 `x2`；参照脚本做「前端模板」；~~Plotly 分离模式按组翻页~~（6.8 完成：凡是多张计划都翻页）。
- ~~样式对象化~~（2026-11-20 完成）：格式参数按主题打包成 `LineStyle` / `AxisStyle` / `FrameStyle` / `LegendStyle` / `TickStyle`，全局、预设、分组、格式化器同一种写法（STRUCTURE_REVIEW「6.8 之后：样式对象化」）。
- ~~matplotlib 轴工厂冲掉排版预设的刻度格式~~（随样式对象化修：`AxisStyle.scale` 没写就不调用 `set_*scale`）。
- **柱状图、散点图的格式化从 `draw` 里独立出去**（2026-11-20 用户提出，暂不做）：两者有自己的格式参数和设置方式（柱的填充 / 边框、散点的大小映射等），
  现在跟折线共用 `LineStyle`、共用 `draw` 里的一套流程，线条回调对柱图改色时 matplotlib 还会报 `AttributeError`（Plotly 跳过 Bar）。
  用户手头没有这两种数据、不直观，等有需要时再把两者对应的格式化流程从 `draw` 中分出去（STRUCTURE_REVIEW「55576fb 复审修复」）。
- **Plotly 次刻度文字字号**（2026-11-20 记录）：Plotly 没有这个属性，只能在导出的 HTML 里用 JS 改；静态图、notebook 不生效，缩放重画会被冲掉。真需要时作为 html_export 的增强。
- ~~分组样式只对折线生效~~（第三方审查 G 起标记对散点也生效，样式对象化起按 `STYLE_FIELDS_BY_KIND` 取字段）（2026-11-18 记录；2026-11-19 STRUCTURE_REVIEW 6.5 起颜色已对所有画法生效，下面说的是线型、标记）：scatter / bar 写了 linestyle / marker / color 也不应用（scatter 创建后改不了 marker，bar 没有 `set_color`）。
  按原则 5 以后应改为明确报错或在创建时传入。数据点很密时标记会糊成一片，以后可能需要 `markevery` 类参数。
- **图例显示样品名，不显示分组名**（2026-11-18 记录）：分组绘图的图例来自列名（样品名）。绘图计划的曲线带 `group_name`，是否改为显示组名在 STRUCTURE_REVIEW 6.1 由用户定。
- **作用在绘图计划上的样式调整**（2026-11-18 记录，方向）：有了计划后，可在画之前按标准写法改某条曲线的样式，两个 backend 都生效；
  现在的 `lines_formatter` 是后端原生回调，只对一个 backend 有效。`group_style_applyer`、组内精调、计算结果各用各的样式都可以做成这种形式。
- ~~**Plotly 依赖未声明**~~（2026-11-14 已解决）：`pyproject.toml` 增加可选依赖 `interactive`（plotly）和 `test`（pytest、plotly、kaleido）；`src/plotlib/__init__.py` 改为首次访问 `InteractivePlotter` 时才导入，没装 Plotly 也能使用数据模块和 matplotlib 绘图。
