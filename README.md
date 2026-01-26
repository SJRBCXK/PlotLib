# PlotLib

面向科研人员的 Python 科学数据批量绘图库，专为多组实验数据的快速可视化设计。

## 与 Origin 等工具的对比

| 特性 | PlotLib | Origin / Excel |
|------|---------|----------------|
| **数据集管理** | 自动解析分组结构，统一管理多组数据 | 手动逐列选择，重复操作 |
| **批量绘图** | 一行代码绘制所有数据组 | 逐个添加数据系列 |
| **迭代选择** | 链式语法 `.select().by()` 灵活筛选 | 鼠标点选，无法复用 |
| **分组绘图** | `group_plotter()` 自动按组绘制/合并 | 手动分组，样式逐个设置 |
| **格式复用** | 格式化器可复用于任意图表 | 模板系统复杂，难以迁移 |
| **版本控制** | 纯代码，Git 友好 | 二进制文件，无法 diff |
| **自动化** | 脚本可批量处理多个文件 | 需要手动重复操作 |

### 核心优势

1. **智能数据集管理**：自动识别数据分组结构，通过 `group_idx` 和 `group_local_idx` 追踪每列的归属
2. **声明式迭代选择**：`select('group', [0,1]).by('Pa')` 链式筛选，告别手动选列
3. **一键分组绘图**：`group_plotter()` 支持分离/合并模式，自动应用组内样式
4. **格式化器系统**：`axes_formatter`、`lines_formatter`、`legend_formatter` 三层定制

## 安装

```bash
git clone https://github.com/YOUR_USERNAME/PlotLib.git
cd PlotLib
pip install -e .
```

## 快速开始

```python
from src.dataloader import Dataloader
from src.plotter import DataPlotter
from src.formatters import make_axes_formatter

# 1. 加载数据（弹出文件选择对话框）
data = Dataloader(
    COLUMNS_PER_DATASET=6  # 每组数据的列数
).load_data()

# 2. 一行代码绘制所有数据组
DataPlotter(
    input_dataset=data,
    plotdataRowNum_x=0,  # X轴：第0列
    plotdataRowNum_y=1   # Y轴：第1列
).plot_lines()

plt.show()
```

## 数据格式

输入文件按固定列宽分组，每组包含标识列 + 数据列：

```
| 标识列  | 数据列1 | 数据列2 | 数据列3 | 标识列  | 数据列1 | ...
|---------|---------|---------|---------|---------|---------|----
| Sample1 | Hz      | Ohm     | Ohm     | Sample2 | Hz      | ...  <- 第0行：单位
| -       | 1000    | 50.2    | -10.5   | -       | 1000    | ...  <- 第1行起：数据
```

## 核心模块

### Dataloader - 数据加载器

```python
from src.dataloader import Dataloader

# 自动弹出文件选择对话框
data = Dataloader(
    COLUMNS_PER_DATASET=6,      # 每组列数（含标识列）
    DATASET_FRACTION=1/6        # 组数计算系数
).load_data()

# 返回 DataSet 对象，包含：
# - data: np.ndarray        数值矩阵
# - names: list[str]        各列的组名
# - units: list[str]        各列的单位
# - groups_idx: list[int]   各列所属的组索引
# - group_local_idx: list   各列在组内的位置索引
```

### DataPlotter - 绘图器

#### plot_lines() - 多线图

将所有数据组绘制在同一坐标系：

```python
DataPlotter(
    input_dataset=data,
    plotdataRowNum_x=0,  # X轴数据的组内列索引
    plotdataRowNum_y=1   # Y轴数据的组内列索引
).plot_lines(
    axes_formatter=my_formatter,  # 可选：坐标轴格式化
    NegLogScale_y=True            # 可选：Y轴负对数显示
)
```

#### group_plotter() - 分组绘图

按配置分组绘制，支持分离或合并模式：

```python
# 定义分组配置
data_groups = {
    'Group A': {'num': [0, 1, 2], 'linestyle': '-'},
    'Group B': {'num': [3, 4, 5], 'linestyle': '--'},
}

DataPlotter(
    input_dataset=data,
    plot_data_groups=data_groups,
    plotdataRowNum_x=0,
    plotdataRowNum_y=1
).group_plotter(
    merge_groups=False,  # False: 每组单独一张图; True: 合并到一张图
    lines_formatter=my_lines_formatter
)
```

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
from src.processor import DataProcessLayer

layer = DataProcessLayer(data)

# 选择全部数据
layer.select('all').Selected_data

# 按组索引选择
layer.select('group', [0, 1, 2]).Selected_data

# 按单位筛选
layer.select('Pa').Selected_data

# 链式二次筛选
layer.select('all').by(0, 1, 2).Selected_data

# 混合选择
layer.select('group', [0, 1], 'Ohm', (3, 4, 5)).Selected_data
```

### Formatters - 格式化器

#### 坐标轴格式化器

```python
from src.formatters import make_axes_formatter

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
from src.formatters import make_lines_formatter

formatter = make_lines_formatter(
    linewidth=2,
    linecolor='red',
    linestyle='--',
    linemarker='o',
    custom_formations=[
        lambda line: line.set_alpha(0.7)
    ]
)
```

#### 图例格式化器

```python
from src.formatters import make_legend_formatter

formatter = make_legend_formatter(
    legend_location='upper right',
    legend_fontsize=12,
    legend_frameon=False,
    legend_draggable=True
)
```

## 完整示例

### EIS 电化学阻抗谱

```python
from src.dataloader import Dataloader
from src.plotter import DataPlotter
from src.formatters import make_axes_formatter
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
).plot_lines(
    axes_formatter=nyquist_fmt,
    NegLogScale_y=True
)

# 分组绘制
data_groups = {
    'Low freq': {'num': [0, 1], 'linestyle': '-'},
    'High freq': {'num': [2, 3], 'linestyle': '--'},
}

DataPlotter(
    input_dataset=data,
    plot_data_groups=data_groups,
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
from src.dataloader import Dataloader
from src.plotter import DataPlotter
from src.formatters import make_axes_formatter
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
).plot_lines(axes_formatter=dv_fmt)

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
├── src/
│   ├── __init__.py      # 包入口
│   ├── dataloader.py    # 数据加载器
│   ├── dataset.py       # 数据集容器
│   ├── plotter.py       # 绘图器
│   ├── processor.py     # 数据选择与处理
│   └── formatters.py    # 格式化器工厂
├── scripts/
│   ├── eis_bode.py      # EIS Bode 图示例
│   ├── eis_nyquist.py   # EIS Nyquist 图示例
│   └── piezo.py         # 压电测试示例
├── tools/
│   └── data_reorder_app.py  # 数据重排工具
├── pyproject.toml       # 项目配置
└── README.md
```

## 依赖

- Python >= 3.8
- matplotlib
- numpy
- pandas

## License

MIT
