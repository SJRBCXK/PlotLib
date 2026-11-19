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

分组的 `linestyle` / `marker` / `color` 写了就应用（两种模式一样，目前仅 `plot_kind='line'`），
`color` 写了时这组所有样品都用它；优先级：默认样式 < 分组样式 < `lines_formatter`。

#### 样式的标准写法

分组配置、`make_lines_formatter` 和 `DataPlotter(linestyle=...)` 只接受一套与后端无关的标准写法
（`src/plotlib/style.py`），由 matplotlib / Plotly 各自翻译；`'--'`、`'o'` 这类后端写法会直接报错。

| 字段 | 标准写法 |
|---|---|
| 线型 | `'solid'`、`'dash'`、`'dot'`、`'dashdot'`；或自定义虚线 `(实线长, 空白长, ...)`，单位是线宽的倍数 |
| 标记 | `'circle'`、`'square'`、`'triangle-up'`、`'triangle-down'`、`'diamond'`、`'cross'`、`'x'` |
| 颜色 | CSS 颜色名（W3C 标准 148 个，如 `'red'`；注意 `'green'` 是深绿，纯绿叫 `'lime'`）、`'#rrggbb'`、RGB 三个 0~255 的整数 |

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

每个样品一张图，左右两根 Y 轴共用 X 轴（左红右蓝）：

```python
DataPlotter(dataset=data).plot_dual_y(
    left=(0, 1),    # 左线：(X 通道, Y 通道)
    right=(0, 2),   # 右线：(X 通道, Y 通道)
    right_axes_formatter=my_right_axis_formatter,       # 右轴的回调；左轴用 axes_formatter
    figure_formatter=lambda fig, axes: ...,             # 整图回调：axes = {'left': ax1, 'right': ax2}
)
```

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

```python
from plotlib.formatters import make_axes_formatter

formatter = make_axes_formatter(
    xlim_left=0,
    xlim_right=100,
    ylim_bottom=0,
    xscale_type='log',      # 'linear', 'log', 'symlog'
    yscale_type='linear',
    x_format='{x:.2e}',     # 科学计数法
    y_format='{y:.1f}',
    hide_spines=True,       # 隐藏上/右边框
    custom_formation=[      # 自定义回调
        lambda ax, fig: ax.grid(True),
        lambda ax, fig: ax.set_title('My Plot')
    ]
)
```

#### 线条格式化器

```python
from plotlib.formatters import make_lines_formatter

formatter = make_lines_formatter(
    linewidth=2,
    linecolor='red',          # 标准写法，见上面「样式的标准写法」
    linestyle='dash',
    linemarker='circle',
    custom_formations=[
        lambda line: line.set_alpha(0.7)
    ]
)
```

#### 图例格式化器

```python
from plotlib.formatters import make_legend_formatter

formatter = make_legend_formatter(
    legend_location='upper right',
    legend_fontsize=12,
    legend_frameon=False,
    legend_draggable=True
)
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

data = Dataloader(COLUMNS_PER_DATASET=6).load_data()

# Plotly 版坐标轴格式化器：参数与 matplotlib 版相同，另加 backend="plotly"
axes_fmt = make_axes_formatter(backend="plotly", xlim_left=0.001, xscale_type='log', x_format='{x:.0e}')

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

- **滑块** `add_slider(mode=...)`：`"single"` 每档只显示当前一条曲线；`"cumulative"`（默认）显示第一条到当前一条。
  拖动时标题变为当前曲线名；档位名称太长、放不下时，滑块的刻度标签自动隐藏。返回 `go.Figure`。
  只有 Plotly 后端有；只能用于只有一张图的结果（`plot_multiline`、合并模式的 `plot_groups`），按组翻页见开发计划。
- **尺寸与字号**：`figsize`（英寸）和字号、线宽（磅）按 `dpi`（默认 100）换成像素，与 matplotlib 后端画出来比例一致；
  例如多线图默认 (10, 8) 英寸 → 1000 × 800 像素，字号 22 磅 → 约 31 像素。
- **默认排版**与 matplotlib 共用排版预设（`layouts.py`）：图例位置、刻度格式、双 Y 轴左红右蓝；双 Y 轴的右轴是 `yaxis2`。
- **自定义外观**：Plotly 的回调都收 `fig` 并原地修改，`axes_formatter` / `lines_formatter` / `legend_formatter` 三个参数都可以用；
  整图回调 `figure_formatter(fig, axes)` 里的 `axes` 是 Plotly 配置里的轴名 `{'left': 'yaxis', 'right': 'yaxis2'}`（用 `fig.layout[axes['right']]` 修改右轴）。
  `add_slider(slider_formatter=fn)` 中 `fn(slider)` 原地修改滑块。多个 Plotly 回调可用 `combine_formatters(...)` 合成一个。
- **Plotly 版格式化器的限制**：不支持 `xscaler` / `yscaler`；坐标轴只支持 `'linear'` 和 `'log'`；
  刻度格式只支持 `'{x:.Nf}'`、`'{x:.Ne}'`、`'{x:.Ng}'`、`'{x:.N%}'`。不支持的设置在创建格式化器时直接报错。
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
    xscale_type='linear',
    yscale_type='linear',
    x_format='{x:.1e}',
    y_format='{y:.1e}'
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
import matplotlib.pyplot as plt

# 加载数据
data = Dataloader(COLUMNS_PER_DATASET=6).load_data()

# Displacement-Voltage 格式化器
dv_fmt = make_axes_formatter(
    xlim_left=0.001,
    xscale_type='log',
    yscaler=10,  # Y轴缩放因子
    x_format='{x:.1e}',
    y_format='{y:.1e}'
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
│       ├── plot_spec.py        # 绘图约定：计划、结果、外观、回调的数据类型
│       ├── layouts.py          # 排版预设：每种版式的默认排版（两个后端共用）
│       ├── style.py            # 翻译层：标准写法 → 各后端原生值（样式、图例、刻度格式、按 dpi 换算）
│       ├── backends/           # 绘图后端，只管渲染：matplotlib_backend.py、plotly_backend.py
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
