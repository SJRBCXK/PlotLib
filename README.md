# PlotLib

面向科研人员的 Python 科学数据批量绘图库，专为多样品实验数据的快速可视化设计。

## 与 Origin 等工具的对比

| 特性 | PlotLib | Origin / Excel |
|------|---------|----------------|
| **数据集管理** | 自动解析「样品 × 通道」结构，统一管理多个样品 | 手动逐列选择，重复操作 |
| **批量绘图** | 一行代码绘制所有样品 | 逐个添加数据系列 |
| **迭代选择** | 链式语法 `.select().by()` 灵活筛选 | 鼠标点选，无法复用 |
| **分组绘图** | `group_plotter()` 自动按组绘制/合并 | 手动分组，样式逐个设置 |
| **格式复用** | 格式化器可复用于任意图表 | 模板系统复杂，难以迁移 |
| **版本控制** | 纯代码，Git 友好 | 二进制文件，无法 diff |
| **自动化** | 脚本可批量处理多个文件 | 需要手动重复操作 |

### 核心优势

1. **智能数据集管理**：自动识别「样品 × 通道」结构，通过 `sample_idx` 和 `channel_idx` 追踪每列的归属
2. **声明式迭代选择**：`select('samples', [0,1]).by('Pa')` 链式筛选，告别手动选列
3. **一键分组绘图**：`group_plotter()` 支持分离/合并模式，自动应用组内样式
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
| `interactive` | plotly | Plotly 交互绘图：`InteractivePlotter`、格式化器的 `backend="plotly"`、`html_export` |
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
    input_dataset=data,
    plotdataRowNum_x=0,  # X轴：通道 0
    plotdataRowNum_y=1   # Y轴：通道 1
).plot_objects()

plt.show()
```

> 图窗尺寸：`DataPlotter(..., figsize=(宽, 高))` 对所有绘图方法生效；不传时 `plot_objects` 为 (10, 8)、`group_plotter` 为 (16, 12)。

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

#### plot_objects() - 多线图

将所有样品绘制在同一坐标系：

```python
DataPlotter(
    input_dataset=data,
    plotdataRowNum_x=0,  # X轴数据的通道号
    plotdataRowNum_y=1   # Y轴数据的通道号
).plot_objects(
    axes_formatter=my_formatter,  # 可选：坐标轴格式化
    NegLogScale_y=True            # 可选：Y轴负对数显示
)
```

#### group_plotter() - 分组绘图

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
    input_dataset=data,
    groups=groups,
    plotdataRowNum_x=0,
    plotdataRowNum_y=1
).group_plotter(
    merge_groups=False,  # False: 每组单独一张图; True: 合并到一张图
    lines_formatter=my_lines_formatter
)
```

分组的 `linestyle` / `marker` / `color` 写了就应用（两种模式一样，目前仅 `plot_kind='line'`），
`color` 写了时这组所有样品都用它；优先级：默认样式 < 分组样式 < `lines_formatter`。

#### 样式的标准写法

分组配置、`make_lines_formatter` 和 `DataPlotter(plot_style=...)` 只接受一套与后端无关的标准写法
（`src/plotlib/style.py`），由 matplotlib / Plotly 各自翻译；`'--'`、`'o'` 这类后端写法会直接报错。

| 字段 | 标准写法 |
|---|---|
| 线型 | `'solid'`、`'dash'`、`'dot'`、`'dashdot'`；或自定义虚线 `(实线长, 空白长, ...)`，单位是线宽的倍数 |
| 标记 | `'circle'`、`'square'`、`'triangle-up'`、`'triangle-down'`、`'diamond'`、`'cross'`、`'x'` |
| 颜色 | CSS 颜色名（W3C 标准 148 个，如 `'red'`；注意 `'green'` 是深绿，纯绿叫 `'lime'`）、`'#rrggbb'`、RGB 三个 0~255 的整数 |

#### subplotter_yy() - Y-Y 关系图

绘制两个变量的相关性（如 Nyquist 图）：

```python
DataPlotter(input_dataset=data).subplotter_yy(
    plotdataRowNum_Y1=1,  # X方向的Y变量
    plotdataRowNum_Y2=2,  # Y方向的Y变量
    NegLogScale_Y2=True
)
```

#### subplotter_xyy() - X-YY 双轴图

共享 X 轴的双 Y 轴显示：

```python
DataPlotter(input_dataset=data).subplotter_xyy(
    plotdataRowNum_X1=0,  # 左Y轴的X数据
    plotdataRowNum_Y1=1,  # 左Y轴数据
    plotdataRowNum_X2=0,  # 右Y轴的X数据
    plotdataRowNum_Y2=2,  # 右Y轴数据
    custom_formatter=my_dual_axis_formatter
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

需要可选依赖 `pip install -e ".[interactive]"`。用法与 `scripts/piezo_interactive.py` 一致：

```python
from plotlib.dataloader import Dataloader
from plotlib.interactive import InteractivePlotter
from plotlib.formatters import make_axes_formatter
from plotlib.html_export import write_fit_html

data = Dataloader(COLUMNS_PER_DATASET=6).load_data()

# Plotly 版坐标轴格式化器：参数与 matplotlib 版相同，另加 backend="plotly"
axes_fmt = make_axes_formatter(backend="plotly", xlim_left=0.001, xscale_type='log')

plot = InteractivePlotter(
    input_dataset=data,   # 分组参数 groups 与 DataPlotter 相同（Group 对象，可省略）
    plotrange=300,
    plotdataRowNum_x=2,   # Displacement
    plotdataRowNum_y=4,   # Voltage
)
# 每个样品画成一条曲线，再加一个控制曲线显示的滑块
fig = plot.plot_plotly_object(figure_formatter=axes_fmt).add_slider(mode="cumulative")

# 导出随窗口等比缩放的 HTML（嵌入 PPT 等页面时不出现滚动条）
write_fit_html(fig, "plot.html", title="压电极化测试")
```

- **滑块** `add_slider(mode=...)`：`"single"` 每档只显示当前一条曲线；`"cumulative"`（默认）显示第一条到当前一条。
  拖动时标题变为当前曲线名；档位名称太长、放不下时，滑块的刻度标签自动隐藏。
- **自定义外观**：`plot_plotly_object(figure_formatter=fn)` 中 `fn(fig)` 原地修改 Figure；
  `add_slider(slider_formatter=fn)` 中 `fn(slider)` 原地修改滑块。多个 Plotly 回调可用 `combine_formatters(...)` 合成一个。
- **Plotly 版格式化器的限制**：不支持 `xscaler` / `yscaler`；坐标轴只支持 `'linear'` 和 `'log'`；
  刻度格式只支持 `'{x:.Nf}'`、`'{x:.Ne}'`、`'{x:.Ng}'`、`'{x:.N%}'`。不支持的设置在创建格式化器时直接报错。
- **HTML 导出** `write_fit_html(fig, path, side_html=None, side_width=300, gap=24, title=..., include_plotlyjs=True)`：
  - 页面按图的固定尺寸排版（`InteractivePlotter` 的默认模板为 1200 × 800），打开时按窗口大小整体等比缩放并居中；
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
    input_dataset=data,
    plotdataRowNum_x=5,  # Real Z'
    plotdataRowNum_y=6   # -Imaginary Z''
).plot_objects(
    axes_formatter=nyquist_fmt,
    NegLogScale_y=True
)

# 分组绘制
data_groups = {
    'Low freq': {'num': [0, 1], 'linestyle': 'solid'},
    'High freq': {'num': [2, 3], 'linestyle': 'dash'},
}

DataPlotter(
    input_dataset=data,
    groups=Group(data, data_groups),
    plotdataRowNum_x=5,
    plotdataRowNum_y=6
).group_plotter(
    axes_formatter=nyquist_fmt,
    NegLogScale_y=True,
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
    input_dataset=data,
    plotrange=299,       # 只绘制前299个点
    plotdataRowNum_x=2,  # Displacement
    plotdataRowNum_y=4   # Voltage
).plot_objects(axes_formatter=dv_fmt)

# 双轴图：位移和电压随时间变化
DataPlotter(
    input_dataset=data,
    plotrange=299
).subplotter_xyy(
    plotdataRowNum_X1=0,  # Time
    plotdataRowNum_Y1=2,  # Displacement
    plotdataRowNum_X2=3,  # Time
    plotdataRowNum_Y2=4   # Voltage
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
│       ├── plotter.py          # matplotlib 绘图器
│       ├── interactive.py      # Plotly 交互绘图器（滑块）
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
