# 多后端绘图规划（matplotlib / Plotly）

> 记录时间：2026-11-13。来源：与 Claude 的架构讨论。
> 进度表请随实现更新；架构原则未经重新讨论不要改动。
> 用词按 `GLOSSARY.md`：样品（一次测量，原「数据组」「实际组号」）、通道（样品内的列）、分组（若干样品的集合）。2026-11-16 起统一。

## 1. 目标

同一份数据、同一套绘图模式（普通叠加、分组、逐样品关系图、双 Y 轴），可以选择不同 backend 渲染：
matplotlib 出静态图，Plotly 出交互图 / HTML。

**不维护两个相似的完整绘图类**：只保留一个绘图器作为数据与模式入口，配多个渲染实现。

## 2. 目标架构

```text
Dataloader → DataSet → 按需 select / by / DataTransformer / Group.apply
        │              │
        │              ▼
        │        Group(dataset, config)：分组的唯一主人（见 2.1 节）
        │              │
        ▼              ▼
DataPlotter(dataset, groups=Group)（唯一的数据与模式入口）
   取列、行范围、样品排序、稳定配色、分组 / 去重，
   决定几张图、每张图有哪些曲线
        │
        ▼
绘图计划（与后端无关的小数据结构）
   每张图：坐标轴配置 + 曲线列表
   每条曲线：X / Y、标签、样品号、左 / 右轴、样式
        │
   ┌────┴────┐
   ▼         ▼
MatplotlibBackend    PlotlyBackend
   创建图 → 绘制 → 默认格式 → 用户 formatter（后端原生回调）
                        │
                        ▼
                可选交互（Plotly 曲线滑块）
```

设想中的文件组织（第 4 步时再建，不要提前铺开；标「已有」的已经存在）：

```text
src/plotlib/
├── group.py              # 已有：Group，分组的唯一主人（2.1 节）
├── plot_common.py        # 已有：两个绘图器共用的函数（color_positions；步骤 5 起继续往里放）
├── style.py              # 已有：样式标准写法的校验与到各后端的翻译（2.2 节）
├── plotter.py            # DataPlotter：公共入口与模式组织
├── plot_spec.py          # 绘图计划
├── formatters.py         # 格式化器工厂（已支持 backend 参数）
└── backends/
    ├── matplotlib_backend.py
    └── plotly_backend.py   # 由现在的 interactive.py 收敛而来
```

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
- 配色用 `plot_common.color_positions(dataset.sample_idx)`，按整个数据集排名一次，同一样品在各张图里颜色一致；合并模式的组首色 = `sample_ids(name)[0]` 的颜色。
- 分组样式写了就应用（两种模式一样，目前仅折线）；`color` 写了时整组同色。没写线型用 `plot_style`。优先级：默认样式 < 分组样式 < `lines_formatter`。
- 现状：`DataPlotter` 已按此实现（属性 `self.groups`，翻译见 `_group_style`）；**`InteractivePlotter` 尚未改**，见第 7 节。

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

## 5. 进度

| 步骤 | 内容 | 状态 |
|---|---|---|
| 0 | 恢复测试基线；稀疏样品号的稳定配色 | ✅ 配色于 2026-11-17 完成：`plot_common.color_positions`，两个绘图器共用 |
| 1 | `plot_plotly_object(figure_formatter=...)`、`add_slider(slider_formatter=...)` 两个回调入口 | ✅ |
| 2 | 格式化器收进 `formatters.py` | ✅ 三个工厂支持 `backend="plotly"`，另有 `combine_formatters`；滑块 formatter 工厂暂未做 |
| 3 | 交互绘图补分组模式：复用 `Group`（绘图器只接受 `Group` 对象，见 STRUCTURE_REVIEW 步骤 4.2），对齐分离 / 合并 / 重叠样品去重规则；改为保存“样品号 → traces”映射，滑块按分组控制 | ⏳ |
| 4 | 提取公共部分（取列、行范围、样品排序、稳定配色、分组组织）为绘图计划；创建图、绘制、默认格式、原生回调交给 backend | ⏳ |

第 3 步验收：相同选列与分组配置下，两个 backend 得到相同的数据、标签和分组顺序。
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
- **`InteractivePlotter` 还没有接上 `Group`**（2026-11-18 记录，在第 3 步开始时处理）：构造函数第一个参数 `plot_data_group` 必填却未使用，
  `plot_data_groups` 只保存不使用。要按 2.1 节的绘图器约定改：删掉第一个参数，改为可选的 `groups: Group | None`，三种情况的检查与 `DataPlotter` 相同；
  届时把检查移进 `plot_common.py`（如 `resolve_groups(groups, dataset) -> Group`），两个绘图器共用。随之更新测试中 12 处 `InteractivePlotter(None, ...)`、
  `scripts/piezo_interactive.py` 和 README。
- **分组样式只对折线生效**（2026-11-18 记录）：scatter / bar 写了 linestyle / marker / color 也不应用（scatter 创建后改不了 marker，bar 没有 `set_color`）。
  按原则 5 以后应改为明确报错或在创建时传入。数据点很密时标记会糊成一片，以后可能需要 `markevery` 类参数。
- ~~**Plotly 依赖未声明**~~（2026-11-14 已解决）：`pyproject.toml` 增加可选依赖 `interactive`（plotly）和 `test`（pytest、plotly、kaleido）；`src/plotlib/__init__.py` 改为首次访问 `InteractivePlotter` 时才导入，没装 Plotly 也能使用数据模块和 matplotlib 绘图。
