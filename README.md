# PlotLib

面向科研人员的 Python 科学数据批量绘图库，专为多样品实验数据的快速可视化设计。

## 与 Origin 等工具的对比

| 特性 | PlotLib | Origin / Excel |
|------|---------|----------------|
| **数据集管理** | 自动解析「样品 × 通道」结构，统一管理多个样品 | 手动逐列选择，重复操作 |
| **批量绘图** | 一行代码绘制所有样品 | 逐个添加数据系列 |
| **迭代选择** | 链式语法 `.select().by()` 灵活筛选 | 鼠标点选，无法复用 |
| **分组绘图** | `plot_groups()` 自动按组绘制/合并 | 手动分组，样式逐个设置 |
| **格式复用** | 格式化器可复用于任意图表 | 模板系统复杂，难以迁移 |
| **版本控制** | 纯代码，Git 友好 | 二进制文件，无法 diff |
| **自动化** | 脚本可批量处理多个文件 | 需要手动重复操作 |

### 核心优势

1. **智能数据集管理**：自动识别「样品 × 通道」结构，通过 `sample_idx` 和 `channel_idx` 追踪每列的归属
2. **声明式迭代选择**：`select('samples', [0,1]).by('Pa')` 链式筛选，告别手动选列
3. **一键分组绘图**：`plot_groups()` 支持分离/合并模式，自动应用组内样式
4. **格式化器系统**：`axes_formatter`、`lines_formatter`、`legend_formatter` 三层定制

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/PlotLib.git
cd PlotLib
pip install -e .
```

安装后在任意目录都能 `import plotlib`。按需加装可选依赖，可以组合，如 `pip install -e ".[interactive,test]"`：

| 可选依赖 | 包含 | 用途 |
|---|---|---|
| `interactive` | plotly | Plotly 交互绘图：`DataPlotter(backend='plotly')`、格式化器的 `backend="plotly"`、`html_export` |
| `gui` | PySide6 | `tools/` 下的 `*_qt.py` 工具和 `learning/gui/` 的 PySide6 学习示例 |
| `analysis` | scipy | 分析脚本用到的科学计算（`scripts/eis_bode.py` 的寻峰） |
| `test` | pytest、pytest-cov、plotly、kaleido | 运行测试；渲染测试（`pytest -m render`）还需要本机装有 Chrome |

## 快速开始

```python
import matplotlib.pyplot as plt

from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter

# 1. 加载数据（弹出文件选择对话框）
data = Dataloader(
    COLUMNS_PER_DATASET=6  # 每个样品在文件中占的列数（含标识列）
).load_data()

# 2. 一行代码绘制所有样品
DataPlotter(
    dataset=data,
    channel_x=0,  # X轴：通道 0
    channel_y=1   # Y轴：通道 1
).plot_multiline()

plt.show()
```

> 图窗尺寸：`DataPlotter(..., figsize=(宽, 高))` 对所有绘图方法生效；不传时 `plot_multiline` 为 (10, 8)、`plot_groups` 为 (16, 12)、`plot_xy` / `plot_dual_y` 为 (12, 8)。
> 绘图后端：`DataPlotter(..., backend='matplotlib')`（默认）或 `backend='plotly'`（交互图，见下文）；`dpi`（默认 100）是显式的渲染分辨率。
> 格式：`DataPlotter(..., lines=LineStyle(...), frame=FrameStyle(...), legend=LegendStyle(...), ticks=TickStyle(...))`，
> 默认无框（双 Y 轴除外）、显示次刻度，见下文「样式对象」。

> 根目录的 `matplotlibrc`（`backend: TkAgg`）只在从项目根目录启动 Python 时生效，从其他目录启动时不会读取它。

## 数据格式

输入文件按固定列宽排列，每个样品占「标识列 + 数据列」：

```
| 标识列  | 数据列1 | 数据列2 | 数据列3 | 标识列  | 数据列1 | ...
|---------|---------|---------|---------|---------|---------|----
| Sample1 | Hz      | Ohm     | Ohm     | Sample2 | Hz      | ...  <- 第0行：单位
| -       | 1000    | 50.2    | -10.5   | -       | 1000    | ...  <- 第1行起：数据
```

## 核心模块

### Dataloader - 数据加载器

```python
from plotlib.dataloader import Dataloader

# 自动弹出文件选择对话框
data = Dataloader(
    COLUMNS_PER_DATASET=6,      # 每个样品的列数（含标识列）
    DATASET_FRACTION=1/6        # 样品数计算系数
).load_data()

# 返回 DataSet 对象，包含：
# - data: np.ndarray        数值矩阵
# - names: list[str]        各列的样品名
# - units: list[str]        各列的单位
# - sample_idx: list[int]   各列所属的样品号
# - channel_idx: list[int]  各列在样品内的通道号
```

### DataPlotter - 绘图器

#### plot_multiline() - 多线图

将所有样品绘制在同一坐标系：

```python
DataPlotter(
    dataset=data,
    channel_x=0,  # X轴数据的通道号
    channel_y=1   # Y轴数据的通道号
).plot_multiline(
    axes_formatter=my_formatter,  # 可选：坐标轴格式化
    neglog_y=True            # 可选：Y轴负对数显示
)
```

#### plot_groups() - 分组绘图

按分组绘制，支持分离或合并模式。分组先用 `Group` 创建（创建时校验样品号），绘图器只接受 `Group` 对象：

```python
from plotlib.group import Group

# 定义分组配置：{分组名: {'num': [样品号, ...], 其余字段...}}
data_groups = {
    'Group A': {'num': [0, 1, 2], 'linestyle': 'solid'},
    'Group B': {'num': [3, 4, 5], 'linestyle': 'dash', 'marker': 'circle', 'color': 'red'},
}
groups = Group(data, data_groups)   # 与绘图器使用同一个数据集

DataPlotter(
    dataset=data,
    groups=groups,
    channel_x=0,
    channel_y=1
).plot_groups(
    merge_groups=False,  # False: 每组单独一张图; True: 合并到一张图
    lines_formatter=my_lines_formatter
)
```

分组的 `linestyle` / `marker` / `color` 写了就应用（两种模式一样）：`linestyle` 只对折线，`marker` 对折线和散点，
`color` 对所有画法；`color` 写了时这组所有样品都用它；优先级：默认样式 < 分组样式 < `lines_formatter`。

#### 图例标题（四种绘图方法都有 `legend_title` 参数）

默认不加（双 Y 轴除外，见下）。写固定文字在任何图里都照用；`'{name}'` 会换成每张图自己的名字：
`plot_xy` / `plot_dual_y` 是样品名，`plot_groups` 分离模式是组名；只有一张图（多线图、合并模式）时没有这个名字，原样保留。

```python
plotter.plot_groups(legend_title='Group {name}')     # 每组一张图：Group A、Group B
plotter.plot_multiline(legend_title='S1 (highlighted)')
```

#### 样式的标准写法

分组配置、样式对象和格式化器只接受一套与后端无关的标准写法
（`src/plotlib/style.py`），由 matplotlib / Plotly 各自翻译；`'--'`、`'o'` 这类后端写法会直接报错。

| 字段 | 标准写法 |
|---|---|
| 线型 | `'solid'`、`'dash'`、`'dot'`、`'dashdot'`；或自定义虚线 `(实线长, 空白长, ...)`，单位是线宽的倍数 |
| 标记 | `'circle'`、`'square'`、`'triangle-up'`、`'triangle-down'`、`'diamond'`、`'cross'`、`'x'` |
| 颜色 | CSS 颜色名（W3C 标准 148 个，如 `'red'`；注意 `'green'` 是深绿，纯绿叫 `'lime'`）、`'#rrggbb'`、RGB 三个 0~255 的整数 |
| 图例位置 | 图内 `'upper right'`、`'upper left'`、`'lower right'`、`'lower left'`、`'upper center'`、`'lower center'`、`'center left'`、`'center right'`、`'center'`、`'best'`；图外 `'outside right'`、`'outside top right'` |

#### 样式对象（线、轴、边框、图例、刻度）

格式设置按主题打包成 5 个样式对象（`from plotlib import LineStyle, AxisStyle, FrameStyle, LegendStyle, TickStyle`）。
长度、宽度、字号的单位都是磅，Plotly 按 `dpi` 换成像素；**只写要改的字段**，没写的（`None`）沿用下一层：

**库默认 < 版式预设 < `DataPlotter(...)` 全局 < 分组样式 < 单根轴 / 单条线的格式化器**

全局写了的盖过版式预设（如 `DataPlotter(frame=FrameStyle(top=True))` 让所有版式都画上边框）。

```python
from plotlib import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle

plotter = DataPlotter(data,
                      lines=LineStyle(width=2),                      # 所有图的线
                      frame=FrameStyle(width=2),                     # 所有图的边框
                      legend=LegendStyle(font_size=12),              # 所有图的图例
                      ticks=TickStyle(length=8, minor_length=4))     # 所有图的刻度
right = make_axes_formatter(y=AxisStyle(limits=(0, None)), ticks=TickStyle(minor=False))   # 只改这一根轴
plotter.plot_dual_y(right_axes_formatter=right)
```

| 对象 | 字段 | 库默认 | 用在 |
|---|---|---|---|
| `LineStyle` 线 | `width`、`color`、`linestyle`、`marker`、`marker_size` | 线宽 3、实线、标记 6 | `DataPlotter(lines=)`（不收颜色：颜色按样品配色）、`make_lines_formatter(LineStyle(...))`；分组配置的 `linestyle` / `marker` / `color` 也装进它 |
| `AxisStyle` 一个方向的轴 | `scale`（`'linear'` / `'log'`，matplotlib 另有 `'symlog'` / `'logit'`）、`limits=(下限, 上限)`（某侧不限写 `None`）、`format`（`'{x:.2f}'`）、`scaler`（显示值 = 刻度值 × scaler，只有 matplotlib）、`color`（轴标题、刻度、轴线同色） | 不改 | `make_axes_formatter(x=..., y=...)`；版式预设的刻度格式和左红右蓝 |
| `FrameStyle` 边框 | `width`（轴线宽）、`top` / `right`（画不画上、右边） | 线宽 3、**无框**；双 Y 轴预设画完整的框 | `DataPlotter(frame=)`、`make_axes_formatter(frame=)` |
| `LegendStyle` 图例 | `position`（写法见上表）、`font_size`、`frame`（边框和白底）、`draggable`（只有 matplotlib） | 字号 10、无边框；位置由版式预设定 | `DataPlotter(legend=)`、`make_legend_formatter(LegendStyle(...))` |
| `TickStyle` 刻度 | 见下表 | 见下表 | `DataPlotter(ticks=)`、`make_axes_formatter(ticks=)` |

2026-11-20 样式对象化起，旧参数不再接受：`line_width` / `linestyle` → `lines=LineStyle(width=, linestyle=)`，`axis_width` → `frame=FrameStyle(width=)`，
`legend_font_size` → `legend=LegendStyle(font_size=)`，`tick_width` → `ticks=TickStyle(width=)`。

**刻度 `TickStyle` 的字段：**

| 字段 | 含义 | 默认 | 说明 |
|---|---|---|---|
| `direction` | 朝向 `'out'` / `'in'` | `'out'` | 主、次刻度一起 |
| `length` / `width` | 主刻度长、宽 | 6 / 3 | 原 `DataPlotter(tick_width=...)` 并入 `width` |
| `minor` | 是否显示次刻度 | `True` | 线性轴、对数轴都显示 |
| `minor_length` / `minor_width` | 次刻度长、宽 | 3 / 3 | |
| `label_font` / `label_size` | 刻度文字的字体、字号 | 沿用 `font_family` / `font_size` | |
| `label_pad` | 刻度文字离刻度线的距离 | 后端默认 | |
| `minor_labels` | 次刻度写什么：`'none'` / `'short'`（对数轴只写首位数字 2、5）/ `'full'`（完整数值） | `'none'` | `'short'` 只对对数轴；Plotly 线性轴上次刻度不写文字 |
| `minor_label_font` / `minor_label_size` / `minor_label_pad` | 次刻度文字单独的字体、字号、间距 | 与主刻度文字相同 | **只有 matplotlib**，Plotly 下报错（Plotly 的次刻度没有文字属性；对数轴的 `'short'` 由 Plotly 自动画小一号） |

单轴覆盖时，左轴回调连 X 轴一起改；双 Y 轴的右轴回调里，刻度、边框只改右侧（右侧 Y 轴、右轴自己的轴线），
`x=AxisStyle(...)` 作用在左右共用的 X 轴上。

#### plot_xy() - x-y 单线图（原 subplotter_yy）

每个样品一张图、一条线，绘制两个通道的关系（如 Nyquist 图）；线用 matplotlib 默认色：

```python
DataPlotter(dataset=data).plot_xy(
    channel_x=1,  # X方向的Y变量
    channel_y=2,  # Y方向的Y变量
    neglog_y=True
)
```

#### plot_dual_y() - 双 Y 轴图

每个样品一张图，左右两根 Y 轴共用 X 轴（左红右蓝），画完整的框。图例放在图外上方、右对齐，两条线都在里面，
每条写自己的单位，图例标题是样品名（`legend_title='{name}'`，传 `None` 不加）：

```python
DataPlotter(dataset=data).plot_dual_y(
    left=(0, 1),    # 左线：(X 通道, Y 通道)
    right=(0, 2),   # 右线：(X 通道, Y 通道)
    right_axes_formatter=my_right_axis_formatter,       # 右轴的回调；左轴用 axes_formatter
    figure_formatter=lambda fig, axes: ...,             # 整图回调：axes = {'left': ax1, 'right': ax2}
)
```

图例只有一个，归 `legend_formatter`；给 `right_legend_formatter` 会报错。

### DataProcessLayer - 数据选择器

链式语法筛选数据列：

```python
from plotlib.processor import DataProcessLayer

layer = DataProcessLayer(data)

# 选择全部数据
layer.select('all').Selected_data

# 按样品号选择（关键字必须写成 'samples'）
layer.select('samples', [0, 1, 2]).Selected_data

# 按单位筛选
layer.select('Pa').Selected_data

# 链式二次筛选
layer.select('all').by(0, 1, 2).Selected_data

# 混合选择
layer.select('samples', [0, 1], 'Ohm', (3, 4, 5)).Selected_data
```

### Formatters - 格式化器

#### 坐标轴格式化器

三个工厂的参数都是样式对象（见上文「样式对象」），**只改写了的字段**，没写的沿用全局设置和版式预设
（比如只给 `x=AxisStyle(scale='log')` 时，Y 轴仍是预设的刻度格式）。`custom` 是自定义回调列表，收各后端的原生对象。

```python
from plotlib import AxisStyle, FrameStyle, LegendStyle, LineStyle, TickStyle
from plotlib.formatters import make_axes_formatter, make_legend_formatter, make_lines_formatter

axes_fmt = make_axes_formatter(
    x=AxisStyle(scale='log', limits=(0, 100), format='{x:.2e}'),   # 刻度类型、范围、刻度格式
    y=AxisStyle(limits=(0, None), format='{y:.1f}'),
    frame=FrameStyle(top=True, right=True),     # 这根轴画完整的框
    ticks=TickStyle(length=10),                 # 这根轴的刻度
    custom=[lambda ax, fig: ax.grid(True)],     # 自定义回调：matplotlib (ax, fig)，Plotly (轴名, fig)
)
lines_fmt = make_lines_formatter(LineStyle(width=2, color='red', linestyle='dash', marker='circle'),
                                 custom=[lambda line: line.set_alpha(0.7)])
legend_fmt = make_legend_formatter(LegendStyle(position='upper right', font_size=12, frame=False, draggable=True))
```

## 交互图与 HTML 导出（Plotly）

需要可选依赖 `pip install -e ".[interactive]"`。交互图和静态图是**同一个入口**：`DataPlotter(..., backend='plotly')`，
四种绘图方法、分组规则、结果形状（`figures = {key: DrawnFigure}`）都与 matplotlib 相同，只是画成 Plotly 的 `go.Figure`。
用法与 `scripts/piezo_interactive.py` 一致：

```python
from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.html_export import write_fit_html
from plotlib.plot_spec import AxisStyle

data = Dataloader(COLUMNS_PER_DATASET=6).load_data()

# Plotly 版坐标轴格式化器：参数与 matplotlib 版相同，另加 backend="plotly"
axes_fmt = make_axes_formatter(x=AxisStyle(scale='log', limits=(0.001, None), format='{x:.0e}'), backend="plotly")

plot = DataPlotter(
    dataset=data,   # 分组参数 groups、外观参数、figsize、dpi 都与 matplotlib 后端相同
    plotrange=300,
    channel_x=2,   # Displacement
    channel_y=4,   # Voltage
    backend='plotly',
)
# 每个样品画成一条曲线，再加一个控制曲线显示的滑块
fig = plot.plot_multiline(axes_formatter=axes_fmt).add_slider(mode="cumulative")

# 导出随窗口等比缩放的 HTML（嵌入 PPT 等页面时不出现滚动条）
write_fit_html(fig, "plot.html", title="压电极化测试")
```

- **多页**：一次画出多张图的方法（分组分离模式、`plot_xy`、`plot_dual_y`）在 Plotly 里画成**一个 Figure 多页**，
  每页就是 matplotlib 对应的那张图；刚画完只显示第一页。`figures` 仍按页登记 `{key: DrawnFigure}`，各页共用同一个 `fig`。
- **滑块**（只有 Plotly 后端有，返回 `go.Figure`）：
  - `add_slider(mode=...)`：曲线滑块，一条线一档，用于一页图（`plot_multiline`、合并模式的 `plot_groups`）；默认 `"cumulative"`；
  - `add_page_slider(mode=...)`：翻页滑块，一页一档，用于多页图；档位标签是组名 / 样品名，翻页时标题和图例标题跟着换；默认 `"single"`；
  - 两种 `mode` 一样：`"single"` 每档只显示当前这一条 / 一页；`"cumulative"` 显示第一条 / 页到当前。用错（一页图用翻页滑块，或反过来）会报错并提示该用哪个。
  - 档位名称太长、放不下时，刻度标签自动隐藏；`slider_formatter=fn` 最后执行，可改前缀等（翻页滑块默认不加前缀）。
- **尺寸与字号**：`figsize`（英寸）和字号、线宽（磅）按 `dpi`（默认 100）换成像素，与 matplotlib 后端画出来比例一致；
  例如多线图默认 (10, 8) 英寸 → 1000 × 800 像素，字号 22 磅 → 约 31 像素。
- **默认排版**与 matplotlib 共用排版预设（`layouts.py`）：图例位置与标题、刻度格式、双 Y 轴左红右蓝；双 Y 轴的右轴是 `yaxis2`。
- **自定义外观**：按轴回调与 matplotlib 形状对应，只拿到这根轴自己的东西：`axes_formatter(轴名, fig)`（如 `('yaxis2', fig)`）、
  `lines_formatter(traces)`（这根轴上的 trace）、`legend_formatter([fig.layout.legend])`；所以 `right_axes_formatter` 只改右轴和右线。
  一张图只有一个图例（归左轴），给右轴配图例回调会报错。
  整图回调 `figure_formatter(fig, axes)` 里的 `axes` 是 Plotly 配置里的轴名 `{'left': 'yaxis', 'right': 'yaxis2'}`（用 `fig.layout[axes['right']]` 修改右轴）。
  多页图的回调对整个 Figure 只调一次（各页共用一套轴），线回调拿到这根轴上所有页的线。
  `add_slider(slider_formatter=fn)` 中 `fn(slider)` 原地修改滑块。同一种回调可用 `combine_formatters(...)` 合成一个（两个后端都可以）。
- **Plotly 版格式化器的限制**：不支持 `AxisStyle.scaler`；刻度类型只支持 `'linear'` 和 `'log'`；
  刻度格式只支持 `'{x:.Nf}'`、`'{x:.Ne}'`、`'{x:.Ng}'`、`'{x:.N%}'`；次刻度文字不能单独设字号等；图例拖动在显示时设置。
  不支持的设置在创建格式化器时直接报错。
- **双 Y 轴的右轴**按自己的数据选刻度（Plotly 对叠加的轴默认让刻度位置对齐左轴，刻度值会不整齐；与 matplotlib 的 twinx 一致）。
- **HTML 导出** `write_fit_html(fig, path, side_html=None, side_width=300, gap=24, title=..., include_plotlyjs=True)`：
  - 页面按图的固定尺寸排版（Plotly 后端按 `figsize × dpi` 定尺寸，多线图默认 1000 × 800），打开时按窗口大小整体等比缩放并居中；
  - `include_plotlyjs=True` 把 Plotly.js 内嵌进文件（约 4.5 MB），离线也能打开；
  - `side_html` 在图的右侧附加一段 HTML（可包含自己的 `<style>`、`<script>`）。面板脚本可以通过 `.plotly-graph-div` 找到图、
    监听 `plotly_sliderchange` 事件与滑块联动，示例见 `scripts/assets/piezo_panel.html`（按档位名称是否含 `rev` 切换示意图）。

## 完整示例

### EIS 电化学阻抗谱

```python
from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.group import Group
from plotlib.plot_spec import AxisStyle
import matplotlib.pyplot as plt

# 配置
COLUMNS_PER_DATASET = 8

# 加载数据
data = Dataloader(
    COLUMNS_PER_DATASET=COLUMNS_PER_DATASET,
    DATASET_FRACTION=1/COLUMNS_PER_DATASET
).load_data()

# Nyquist 图格式化器
nyquist_fmt = make_axes_formatter(
    x=AxisStyle(scale='linear', format='{x:.1e}'),
    y=AxisStyle(scale='linear', format='{y:.1e}'),
)

# 绘制 Nyquist 图（Z' vs -Z''）
DataPlotter(
    dataset=data,
    channel_x=5,  # Real Z'
    channel_y=6   # -Imaginary Z''
).plot_multiline(
    axes_formatter=nyquist_fmt,
    neglog_y=True
)

# 分组绘制
data_groups = {
    'Low freq': {'num': [0, 1], 'linestyle': 'solid'},
    'High freq': {'num': [2, 3], 'linestyle': 'dash'},
}

DataPlotter(
    dataset=data,
    groups=Group(data, data_groups),
    channel_x=5,
    channel_y=6
).plot_groups(
    axes_formatter=nyquist_fmt,
    neglog_y=True,
    merge_groups=False
)

plt.show()
```

### 压电测试数据

```python
from plotlib.dataloader import Dataloader
from plotlib.plotter import DataPlotter
from plotlib.formatters import make_axes_formatter
from plotlib.plot_spec import AxisStyle
import matplotlib.pyplot as plt

# 加载数据
data = Dataloader(COLUMNS_PER_DATASET=6).load_data()

# Displacement-Voltage 格式化器
dv_fmt = make_axes_formatter(
    x=AxisStyle(scale='log', limits=(0.001, None), format='{x:.1e}'),
    y=AxisStyle(format='{y:.1e}', scaler=10),   # 刻度文字显示值 = 刻度值 × 10
)

# 绘制 D-V 关系图
DataPlotter(
    dataset=data,
    plotrange=299,       # 只绘制前299个点
    channel_x=2,  # Displacement
    channel_y=4   # Voltage
).plot_multiline(axes_formatter=dv_fmt)

# 双轴图：位移和电压随时间变化
DataPlotter(
    dataset=data,
    plotrange=299
).plot_dual_y(
    left=(0, 2),    # (Time, Displacement)
    right=(3, 4),   # (Time, Voltage)
)

plt.show()
```

## 项目结构

```
PlotLib/
├── pyproject.toml              # 项目配置与依赖
├── README.md
├── matplotlibrc                # matplotlib 后端设置（只在从项目根目录启动时生效）
├── src/
│   └── plotlib/                # 唯一的可安装包：import plotlib
│       ├── __init__.py         # 包入口
│       ├── dataset.py          # 数据集容器
│       ├── dataloader.py       # 数据加载器
│       ├── processor.py        # 数据选择与变换
│       ├── group.py            # 分组配置解析与分组计算
│       ├── plotter.py          # DataPlotter：唯一的绘图入口（计划 → 后端 → 结果）
│       ├── plan.py             # 绘图规则：生成绘图计划（分组、去重、配色、取数）
│       ├── plot_spec.py        # 绘图约定：样式对象（LineStyle 等 5 个）、计划、结果、外观、回调的数据类型
│       ├── layouts.py          # 排版预设：每种版式的默认排版，用样式对象写（两个后端共用）；叠加顺序
│       ├── style.py            # 翻译层：标准写法 / 样式对象 → 各后端原生值（按 dpi 换算）
│       ├── backends/           # 绘图后端，只管渲染：matplotlib_backend.py、plotly_backend.py、
│       │                       #   matplotlib_styles.py（matplotlib 应用样式，后端与格式化器共用）
│       ├── formatters.py       # 格式化器工厂（matplotlib / Plotly）
│       ├── html_export.py      # 导出随窗口缩放的 HTML 页面
│       └── templates/ppt_fit_shell.html   # html_export 的页面外壳
├── scripts/                    # 按实验的分析脚本
│   ├── eis_bode.py             # EIS 介电谱 Bode 图、电导率比、损耗峰
│   ├── eis_nyquist.py          # EIS Nyquist 图
│   ├── piezo.py                # 压电测试（matplotlib）
│   ├── piezo_interactive.py    # 压电测试交互图 + HTML 导出
│   ├── tensile.py              # 拉伸测试
│   ├── select_demo.py          # select().by() 选列演示
│   └── assets/piezo_panel.html # 交互图右侧的压缩示意面板
├── tools/                      # 独立 GUI 预处理工具（Tk 与 Qt 两版）
│   ├── data_collector.py
│   ├── data_collector_qt.py
│   ├── data_reorder_app.py
│   └── data_reorder_qt.py
├── learning/                   # 学习材料，不属于产品代码
│   ├── gui/                    # PySide6 学习步骤与路线图
│   └── testing/LEARNING_PLAN.md   # pytest 学习路线图
├── docs/                       # 设计文档（BACKEND_PLAN.md、STRUCTURE_REVIEW.md）
└── tests/                      # pytest 测试，说明见 tests/README.md
```

## 依赖

- Python >= 3.14
- matplotlib
- numpy
- pandas
- openpyxl（读取 `.xlsx`）
- xlrd（读取旧版 Excel `.xls`）

可选依赖见「安装」一节，以 `pyproject.toml` 为准。

## License

MIT，见 [LICENSE](LICENSE)。
