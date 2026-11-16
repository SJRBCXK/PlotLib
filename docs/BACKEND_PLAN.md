# 多后端绘图规划（matplotlib / Plotly）

> 记录时间：2026-11-13。来源：与 Claude 的架构讨论。
> 进度表请随实现更新；架构原则未经重新讨论不要改动。

## 1. 目标

同一份数据、同一套绘图模式（普通叠加、分组、逐组关系图、双 Y 轴），可以选择不同 backend 渲染：
matplotlib 出静态图，Plotly 出交互图 / HTML。

**不维护两个相似的完整绘图类**：只保留一个绘图器作为数据与模式入口，配多个渲染实现。

## 2. 目标架构

```text
Dataloader → DataSet → 按需 select / by / DataTransformer / Group.apply
        │
        ▼
DataPlotter（唯一的数据与模式入口）
   取列、行范围、组排序、稳定配色、分组 / 去重，
   决定几张图、每张图有哪些曲线
        │
        ▼
绘图计划（与后端无关的小数据结构）
   每张图：坐标轴配置 + 曲线列表
   每条曲线：X / Y、标签、实际组号、左 / 右轴、样式
        │
   ┌────┴────┐
   ▼         ▼
MatplotlibBackend    PlotlyBackend
   创建图 → 绘制 → 默认格式 → 用户 formatter（后端原生回调）
                        │
                        ▼
                可选交互（Plotly 曲线滑块）
```

设想中的文件组织（第 4 步时再建，不要提前铺开）：

```text
src/
├── plotter.py            # DataPlotter：公共入口与模式组织
├── plot_spec.py          # 绘图计划
├── formatters.py         # 格式化器工厂（已支持 backend 参数）
└── backends/
    ├── matplotlib_backend.py
    └── plotly_backend.py   # 由现在的 interactive.py 收敛而来
```

## 3. 原则

1. **职责分层**：取数 → 绘图 → 格式化，三者分开。不要把取数和渲染绑在一起。
2. **模式只实现一次**：分组顺序、重复组去重、样式归属、曲线属于哪张图 / 哪个轴，都在公共层决定。不在每个 backend 各写一份 `group_plotter`。
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
| 0 | 恢复测试基线；稀疏组号的稳定配色 | 测试基线 ✅；配色 ⚠️ 见第 7 节 |
| 1 | `plot_plotly_object(figure_formatter=...)`、`add_slider(slider_formatter=...)` 两个回调入口 | ✅ |
| 2 | 格式化器收进 `formatters.py` | ✅ 三个工厂支持 `backend="plotly"`，另有 `combine_formatters`；滑块 formatter 工厂暂未做 |
| 3 | 交互绘图补分组模式：复用 `resolve_num()`，对齐分离 / 合并 / 重叠组去重规则；改为保存“实际组号 → traces”映射，滑块按组控制 | ⏳ |
| 4 | 提取公共部分（取列、行范围、组排序、稳定配色、分组组织）为绘图计划；创建图、绘制、默认格式、原生回调交给 backend | ⏳ |

第 3 步验收：相同选列与分组配置下，两个 backend 得到相同的数据、标签和组顺序。
第 4 步验收：旧的 matplotlib 测试行为不变；切换 backend 后曲线数量、数据、标签、顺序一致。

## 6. 暂时不做

- 不改 `DataSet`、`DataTransformer` 的职责；
- 不自动翻译任意 matplotlib 回调；
- 不引入 Dash 或自定义 JavaScript（如滑块的任意区间筛选）；
- 不一次性统一全部格式参数；
- 不改旧脚本的三个 formatter 接口；
- 不把峰值汇总图这类特殊绘图强行纳入普通多线模式。

## 7. 已知遗留问题

- **稀疏组号配色越界**：`InteractivePlotter._get_color` 用实际组号作为下标，去取按 `num_datagroups`（组的个数）采样出的颜色列表。组号不连续时（例如筛选后只剩组 0 和 5）会越界。应在完整组集合上一次性建立“实际组号 → 颜色”的映射。
- ~~**Plotly 依赖未声明**~~（2026-11-14 已解决）：`pyproject.toml` 增加可选依赖 `interactive`（plotly）和 `test`（pytest、plotly、kaleido）；`src/__init__.py` 改为首次访问 `InteractivePlotter` 时才导入，没装 Plotly 也能使用数据模块和 matplotlib 绘图。
