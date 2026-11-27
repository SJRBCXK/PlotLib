# PlotLib

PlotLib 是一个用于多样品实验数据处理和批量绘图的 Python 库。它按「样品 × 通道」组织数据，支持按条件选列、逐样品变换和分组计算，并使用同一套绘图接口生成 Matplotlib 静态图和 Plotly 交互图。

[在线 API 文档](https://sjrbcxk.github.io/PlotLib/)

## 安装

需要 Python 3.14 或更新版本。克隆仓库后可使用可编辑模式安装。

```bash
git clone https://github.com/SJRBCXK/PlotLib.git
cd PlotLib
python -m pip install -e .
```

基础依赖包括 Matplotlib、NumPy、pandas，以及读取 Excel 文件所需的 openpyxl 和 xlrd。可选依赖可以组合安装，例如 `python -m pip install -e ".[interactive,test]"`。

| 可选依赖 | 用途 |
| --- | --- |
| `interactive` | 启用 Plotly 后端和交互式 HTML 导出 |
| `analysis` | 安装 SciPy，供 `scripts/eis_bode.py` 等分析脚本使用 |
| `gui` | 安装 PySide6，供 `tools/` 中的 Qt 工具使用 |
| `test` | 运行测试和覆盖率检查。Plotly 渲染测试需要本机安装 Chrome |
| `docs` | 使用 Sphinx 生成 API 文档 |

## 快速开始

以下示例读取每个样品占 6 列的文件（含 1 列标识），并在同一坐标系中绘制全部样品。通道号从 `0` 开始，仅计算数据列。

```python
import matplotlib.pyplot as plt

from plotlib import Dataloader, DataPlotter

data = Dataloader(columns_per_sample=6).load_data("experiment.csv")
plotter = DataPlotter(data, channel_x=0, channel_y=1).plot()
plt.show()
```

省略 `load_data()` 的路径参数可打开文件选择对话框。取消选择会引发 `NoFileSelected`。从仓库根目录运行示例时，项目的 `matplotlibrc` 默认使用 `TkAgg`。

## 输入数据

支持 `.csv`、`.xlsx`、`.xls`、`.txt` 和 `.dat` 文件，扩展名不区分大小写。文件按列横向排列样品。每个样品占相同列数，第一列为标识列，其余为数据列。首行记录样品名和通道单位，从第二行起读取数据。下表的表头用于说明列的用途，无需写入文件。

| 标识列 | 通道 0 | 通道 1 | 标识列 | 通道 0 | 通道 1 |
| --- | --- | --- | --- | --- | --- |
| Sample 1 | Hz | Ohm | Sample 2 | Hz | Ohm |
| | 1000 | 50.2 | | 1000 | 48.7 |
| | 2000 | 44.9 | | 2000 | 42.1 |

这个示例对应 `columns_per_sample=3`。同一通道在各样品中的单位应一致。`Dataloader.load_data()` 返回 `DataSet`，其中 `data` 是数值矩阵，`names`、`units`、`sample_idx` 和 `channel_idx` 分别记录各列的样品名、单位、样品号和通道号。

### 选择与变换

`DataProcessLayer.select()` 选择数据列，`by()` 可对本次选择的结果继续筛选。通过 `Selected_data` 取得结果。

```python
from plotlib import DataProcessLayer

layer = DataProcessLayer(data)
selected = layer.select("samples", [0, 1]).by("Ohm").Selected_data
```

选择条件可以是 `"all"`、`"samples"` 加样品号序列、列名、单位或列索引。传入多个条件时按输入顺序组合选列。

`for sample in dataset` 逐样品返回子数据集，等同于 `dataset.iter("samples")`。`dataset.column` 提供按列访问的视图，也可以通过 `dataset.iter()` 按名称、单位或通道遍历。

```python
from plotlib import DataSet, DataTransformer

impedance = DataSet()
for sample in selected:
    result = DataTransformer(sample).Norm(norm_unit="|Z|(ohm)")
    impedance.expandata(result)
```

`DataTransformer.apply()` 接受自定义计算函数。需要把同一分组中的多个样品作为一组输入时，可使用 `Group.apply()`，每个分组生成一个结果样品。

## 绘图

`plot()` 用 `by` 指定样品的分图方式，用 `layers` 指定各样品绘制的图层。`Layer(x, y, kind, side)` 的前两个参数指定 X、Y 通道，`kind` 选择折线（`'line'`）或散点（`'scatter'`），`side` 选择左轴（`'left'`）或右轴（`'right'`）。省略通道时使用构造 `DataPlotter` 时指定的 `channel_x` 和 `channel_y`。

| `by` | 用途 | 图的键 | 默认尺寸（英寸） |
| --- | --- | --- | --- |
| `'all'`（默认） | 在同一坐标系中绘制所有样品 | `'main'` | 10 × 8 |
| `'group'` | 按组绘制。`merge_groups=True` 时将各组合并到同一张图 | 组名或 `'main'` | 16 × 12 |
| `'sample'` | 每个样品一张图，如显示两个通道之间的关系 | 样品号 | 12 × 8 |

```python
from plotlib import DataPlotter, Layer

plotter = DataPlotter(data, channel_x=0, channel_y=1)
plotter.plot()                                      # 全部样品一张折线图
plotter.plot(Layer(kind="scatter"))                 # 同样的两个通道画成散点
plotter.plot(Layer(1, 2), by="sample")              # 每个样品一张：通道 1 对通道 2
plotter.plot([Layer(0, 1, kind="scatter"), Layer(0, 3)], by="sample")   # 每个样品：实测点 + 拟合线
```

绘制多个图层时须使用 `by='sample'`。每条曲线的图例条目采用对应 Y 通道的列标题，图例标题默认使用样品名。

`DataPlotter(figsize=(宽, 高), dpi=100)` 可统一指定图尺寸和绘图分辨率。`plotrange` 可限制每条曲线使用的数据点数。`plot()` 返回绘图器自身，绘图结果通过 `plotter.figures` 获取，每项是一个 `DrawnFigure`。例如，`by='all'` 的结果可通过 `plotter.figures["main"].fig` 获取。

### 分组绘图

`Group` 在创建时校验样品号。分组对象与绘图器使用同一个 `DataSet`。

```python
from plotlib import DataPlotter, Group

groups = Group(data, {
    "Group A": {"num": [0, 1], "linestyle": "solid"},
    "Group B": {"num": [2, 3], "linestyle": "dash", "marker": "circle", "color": "red"},
})

plotter = DataPlotter(data, groups=groups, channel_x=0, channel_y=1)
plotter.plot(by="group", legend_title="{name}")
```

分组线型适用于折线，标记适用于折线和散点。指定的分组颜色应用于组内样品，启用散点颜色映射时由映射值决定点色。
合并绘图时，重复出现的样品采用第一个所属分组的样式。未指定分组颜色时，合并图按各组首个样品的颜色配色，独立分组图按样品配色。

### 散点颜色与大小映射

在散点图层中用 `ScatterMap` 指定颜色或大小通道。以下示例假设通道 0 是正值频率，通道 1、2 分别是实部和虚部。

```python
from plotlib import ColorbarStyle, DataPlotter, Layer, ScatterMap

plotter = DataPlotter(data)
plotter.plot(
    Layer(1, 2, kind="scatter", mapping=ScatterMap(color=0)),
    colorbar=ColorbarStyle(scale="log"),
)
```

一次 `plot()` 仅支持一个颜色映射图层，各张图共用颜色范围。默认线性着色，颜色条标题取颜色通道的列标题。设置 `limits=(下限, 上限)` 可固定范围，某一端也可设为 `None` 以自动取值。对数色标要求用于着色的值和范围端点均为正。

`ScatterMap(size=3, size_range=(4, 16))` 将通道 3 映射为散点大小。映射值与点的面积呈线性关系，`size_range` 指定最小和最大直径，单位为磅。颜色和大小可同时映射。

如需自定义颜色条，可在整图回调中读取 `axes['colorbar']`。Matplotlib 返回 `Colorbar` 对象，Plotly 返回布局中的轴名 `'coloraxis'`。

图例按样品列出，不说明点的大小对应的数值。需要大小图例时可在整图回调中自行添加。以下为 Matplotlib 示例，按面积线性的规则由数值算出直径：

```python
import numpy as np
from matplotlib.lines import Line2D

lo, hi = 4, 16                                           # 与 ScatterMap 的 size_range 相同
values = data.data[:, np.array(data.channel_idx) == 3]   # 大小通道的全部数据
values = values[~np.isnan(values)]

def size_legend(fig, axes):
    if values.size == 0:                                 # 没有有效值时不添加大小图例
        return
    vmin, vmax = values.min(), values.max()
    if vmin == vmax:                                     # 数值全部相同时，点取面积区间的中点
        levels, diameters = [vmin], [np.sqrt((lo**2 + hi**2) / 2)]
    else:                                                # 直径的平方随数值线性变化
        levels = np.linspace(vmin, vmax, 3)
        diameters = np.sqrt(lo**2 + (levels - vmin) / (vmax - vmin) * (hi**2 - lo**2))
    ax = axes["left"]
    samples = ax.get_legend()                            # 先取出样品图例，添加大小图例后再放回
    handles = [Line2D([], [], linestyle="none", marker="o", markersize=d, color="gray", label=f"{v:.3g}")
               for v, d in zip(levels, diameters)]
    ax.legend(handles=handles, title="S(%)", loc="lower right")
    if samples is not None:
        ax.add_artist(samples)

plotter.plot(Layer(1, 2, kind="scatter", mapping=ScatterMap(size=3)), figure_formatter=size_legend)
```

大小范围按实际画出的点计算。数据含有 X、Y 非有限值，或设置了 `plotrange` 时，`vmin`、`vmax` 应从画出的点中取得。

### 双 Y 轴和图例

```python
from plotlib import AxesFormatter, AxisStyle, DataPlotter, Layer, make_axes_formatter

DataPlotter(data).plot(
    [Layer(0, 2),                   # 左侧曲线的 X、Y 通道
     Layer(3, 4, side="right")],    # 右侧曲线的 X、Y 通道
    by="sample",
    formatters={"right": AxesFormatter(axes=make_axes_formatter(y=AxisStyle(scale="log")))},
)
```

双 Y 轴图的两条曲线可以取自不同的 X 通道，这些通道的数据应能在同一 X 轴上解释。默认将左、右 Y 轴及其对应曲线分别设为红色和蓝色，整图使用一个图例。回调按轴打包成 `AxesFormatter`，用 `{"left": ..., "right": ...}` 分别给两侧；图例回调只能放在左侧。X 轴两侧共用，任一侧改 X 都作用在同一根轴上。

`legend_title` 中的 `{name}` 在分组独立绘制时替换为组名，每个样品一张图时替换为样品名；多线图和合并分组图会原样显示传入的文本。默认 `'auto'`：一个样品画多个图层（如双 Y 轴图）时使用样品名，否则不加标题；传入 `None` 可隐藏标题。

### 柱状图

`plot_bars()` 将数据排成一张表：X 轴上的类别是一维，每个类别中并排或堆叠的系列是另一维，系列显示在图例中。两维中恰有一维是通道，另一维是样品或分组。

| `x` | `series` | 用途 |
| --- | --- | --- |
| `'sample'`（默认） | `'channel'`（默认） | 每个样品一组柱，比较该样品的各项指标 |
| `'channel'` | `'sample'` | 每个通道一组柱，比较各样品 |
| `'channel'` | `'group'` | 每个通道一组柱，比较各分组 |
| `'group'` | `'channel'` | 每个分组一组柱，比较该分组的各项指标 |

```python
from plotlib import BarStyle, DataPlotter

plotter = DataPlotter(data, groups=groups)
plotter.plot_bars([1, 2], reduce="mean", errors="std")           # 柱高取各列均值，误差棒为多行之间的标准差
plotter.plot_bars([1, 2], x="channel", series="group", reduce="max", errors="sem")
plotter.plot_bars([1, 2], reduce="mean", mode="stack", styles={   # 黑白堆叠图，用纹理区分通道
    1: BarStyle(color="white", edge_color="black", hatch="slash"),
    2: BarStyle(color="white", edge_color="black", hatch="dot"),
})
```

- `reduce` 将每格的多行数据汇总为柱高，可选值见 `DataTransformer.Reduce`。省略时每格至多一个有效值。涉及分组时，先汇总每个样品，再对组内各样品取均值。
- `errors` 绘制对称误差棒。`'std'` 和 `'sem'` 在分组时以组内各样品的汇总值计算，按样品绘制时以同一列的多行数据计算，并要求 `reduce='mean'`。按样品绘制还可以用 `{值通道: 误差通道}` 指定误差来源。
- `mode='stack'` 时正负值分别累加。叠加的通道应单位相同。
- `styles` 传入一个 `BarStyle` 时作用于全部系列，传入 `{系列键: BarStyle}` 时逐个指定。键为样品号、通道号或组名。误差棒端帽长度 `capsize` 只能在这里设置。

柱状图使用单个 Y 轴，绘图结果保存在 `figures["main"]`。若要在绘制过程中调整系列样式，可向 `plot_bars()` 传入 `formatters=AxesFormatter(bars=make_bar_formatter(...))`。Y 轴标题使用共用的通道列标题，列标题不一致时留空。

## 样式与格式化

通过 `DataPlotter` 设置全局样式，通过格式化器更新图中指定坐标轴、曲线和图例。每层只覆盖明确提供的字段。样式优先级由低到高依次为库默认值、版式预设、`DataPlotter` 全局设置、分组样式和格式化器。

| 样式对象 | 主要字段 | 使用位置 |
| --- | --- | --- |
| `LineStyle` | `width`、`color`、`linestyle`、`marker`、`marker_size` | `DataPlotter(lines=...)` 和 `make_lines_formatter()`。全局颜色由样品配色决定，单组或单轴曲线颜色可单独配置 |
| `ScatterStyle` | `color`、`marker`、`size`、`filled`、`edge_color`、`edge_width`、`alpha` | `make_scatter_formatter()` |
| `BarStyle` | `color`、`edge_color`、`edge_width`、`hatch`、`error_color`、`error_width`、`capsize` | `plot_bars(styles=...)` 和 `make_bar_formatter()` |
| `ColorbarStyle` | `cmap`、`limits`、`scale`、`title` | `plot(colorbar=...)` |
| `AxisStyle` | `scale`、`limits`、`format`、`scaler`、`color` | `make_axes_formatter(x=..., y=...)` |
| `FrameStyle` | `width`、`top`、`right` | `DataPlotter(frame=...)` 和 `make_axes_formatter(frame=...)` |
| `LegendStyle` | `position`、`font_size`、`frame`、`draggable` | `DataPlotter(legend=...)` 和 `make_legend_formatter()` |
| `TickStyle` | 主、次刻度的方向、尺寸及标签 | `DataPlotter(ticks=...)` 和 `make_axes_formatter(ticks=...)` |

线宽、长度和字号以磅为单位。Plotly 按 `dpi` 将它们转换为像素，例如默认的 10 × 8 英寸多线图对应 1000 × 800 像素。
默认线宽和轴线宽度均为 3 磅，图例字号为 10 磅。双 Y 轴图默认显示完整边框。

### 样式取值

- 线型可选 `'solid'`、`'dash'`、`'dot'`、`'dashdot'`，也可以用 `(3, 5)` 等元组自定义虚线。虚线段长和间隔以线宽的倍数表示。
- 标记可选 `'circle'`、`'square'`、`'triangle-up'`、`'triangle-down'`、`'diamond'`、`'cross'` 和 `'x'`。
- 颜色支持 CSS 颜色名、`'#rrggbb'` 或由三个 0–255 整数组成的 RGB 元组。
- 图内图例位置支持 `'upper right'`、`'upper left'`、`'lower right'`、`'lower left'`、`'upper center'`、`'lower center'`、`'center left'`、`'center right'`、`'center'` 和 `'best'`。图外支持 `'outside right'` 和 `'outside top right'`。

PlotLib 会把这些跨后端取值转换为绘图库的原生参数。无效取值会引发异常。

### 刻度

| 字段 | 含义 | 默认 |
| --- | --- | --- |
| `direction` | 主、次刻度朝外 `'out'` 或朝内 `'in'` | `'out'` |
| `length` / `width` | 主刻度的长度和线宽 | 6 / 3 磅 |
| `minor` | 是否显示次刻度线 | `True` |
| `minor_length` / `minor_width` | 次刻度的长度和线宽 | 3 / 3 磅 |
| `label_font` / `label_size` / `label_pad` | 刻度标签的字体、字号及与刻度线的间距 | 字体、字号沿用全局设置，间距采用后端默认值 |
| `minor_labels` | `'none'` 隐藏标签，`'short'` 在对数轴显示首位数字，`'full'` 显示完整数值 | `'none'` |
| `minor_label_font` / `minor_label_size` / `minor_label_pad` | 单独设置次刻度标签的字体、字号和间距，仅 Matplotlib 支持 | 沿用主刻度标签样式 |

Plotly 仅在对数轴上支持次刻度标签。对数轴同时使用显式 `AxisStyle.format` 和 `minor_labels='none'` 时，PlotLib 默认每个数量级放置一个主刻度。局部放大到不含整数量级的范围时，可能看不到主刻度标签。若要自定义主刻度间距，可在 Plotly 的 `custom` 回调中设置 `dtick` 或 `tickmode`。Plotly 对数轴的显式格式与 `minor_labels='short'` 同时使用会在绘图时引发 `ValueError`。

### 格式化器

```python
from plotlib import (
    AxesFormatter, AxisStyle, DataPlotter, FrameStyle, LegendStyle, LineStyle, TickStyle,
    make_axes_formatter, make_legend_formatter, make_lines_formatter,
)

axes_fmt = make_axes_formatter(
    x=AxisStyle(scale="log", limits=(0.001, 100), format="{x:.2e}"),
    y=AxisStyle(limits=(0, None), format="{y:.1f}"),
    frame=FrameStyle(top=True, right=True),
    custom=[lambda ax, fig: ax.grid(True)],
)
lines_fmt = make_lines_formatter(LineStyle(width=2, linestyle="dash", marker="circle"))
legend_fmt = make_legend_formatter(LegendStyle(position="upper right", font_size=12))

DataPlotter(data, ticks=TickStyle(length=8)).plot(
    formatters=AxesFormatter(axes=axes_fmt, lines=lines_fmt, legend=legend_fmt),
)
```

`AxisStyle.limits` 使用数据坐标，`None` 表示该侧边界自动计算。对数轴的显式边界必须为正值。`AxisStyle.scaler` 只缩放 Matplotlib 的刻度显示值。

格式化器按轴打包成 `AxesFormatter(axes=..., lines=..., scatter=..., legend=...)`，交给 `plot(formatters=...)`：只给一个时作用于左轴，`{"left": ..., "right": ...}` 分别给两侧。柱状图用 `plot_bars(formatters=AxesFormatter(axes=..., bars=..., legend=...))`，只有左轴。坐标轴格式化器在 Matplotlib 中接收 `(ax, fig)`，在 Plotly 中接收 `(轴名, fig)`，例如 `('yaxis2', fig)`。曲线和图例格式化器分别接收对象序列。通过工厂的 `custom` 参数传入的曲线或图例回调，会在样式应用后逐个接收原生对象。同类回调可用 `combine_formatters()` 按顺序组合。

`figure_formatter(fig, axes)` 在各轴回调之后执行。`axes` 按 `'left'` 和 `'right'` 索引，值为 Matplotlib 的轴对象或 Plotly 的轴名。

### 轴线过原点（蝴蝶图）

蝴蝶曲线等数据跨越四个象限时，可在坐标轴回调中用原生代码移动轴线。

```python
from plotlib import AxesFormatter, DataPlotter, make_axes_formatter

def origin_axes(ax, fig):            # Matplotlib：轴线移到原点，刻度随之移动
    for side in ("left", "bottom"):
        ax.spines[side].set_position("zero")
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.set_label_coords(0.5, -0.08)       # 坐标轴标题留在图框外侧，不随轴线移动
    ax.yaxis.set_label_coords(-0.1, 0.5)

def zero_lines(axis, fig):           # Plotly：零线划分四象限，刻度留在外框
    fig.update_xaxes(zeroline=True, zerolinecolor="black", zerolinewidth=1.5)
    fig.update_yaxes(zeroline=True, zerolinecolor="black", zerolinewidth=1.5)

DataPlotter(data).plot(formatters=AxesFormatter(axes=make_axes_formatter(custom=[origin_axes])))
DataPlotter(data, backend="plotly").plot(
    formatters=AxesFormatter(axes=make_axes_formatter(custom=[zero_lines], backend="plotly")),
)
```

Plotly 不能把轴线固定在某个数据值上，示例改用零线。零线在缩放和平移时跟随数据。

## Plotly 交互图与 HTML 导出

安装 `interactive` 后，可使用 `backend='plotly'` 生成交互图。格式化器也应指定相同的后端。

```python
from plotlib import AxesFormatter, AxisStyle, Dataloader, DataPlotter, make_axes_formatter
from plotlib.html_export import write_fit_html

data = Dataloader(columns_per_sample=6).load_data("piezo.csv")
axes_fmt = make_axes_formatter(
    x=AxisStyle(scale="log", limits=(0.001, None), format="{x:.0e}"),
    backend="plotly",
)
plotter = DataPlotter(data, channel_x=2, channel_y=4, plotrange=300, backend="plotly")
fig = plotter.plot(formatters=AxesFormatter(axes=axes_fmt)).add_slider(mode="cumulative")
write_fit_html(fig, "plot.html", title="压电极化测试")
```

### 滑块和分页

`add_slider()` 为单页图添加曲线滑块，一个档位对应一条曲线，默认模式为 `'cumulative'`。
分组独立绘制（`by='group'`）和每个样品一张（`by='sample'`）的多页结果可以用 `add_page_slider()` 翻页，默认模式为 `'single'`。多页图共用坐标轴，格式化回调作用于整个 Figure。

`'single'` 只显示当前曲线或页面，`'cumulative'` 从第一档累加到当前档。滑块方法均返回 `go.Figure`，可用 `slider_formatter` 调整外观。整图回调附加的参考线等保留各自的可见性。

### 后端限制

Plotly 支持 `'linear'` 和 `'log'`，刻度格式支持 `.Nf`、`.Ne`、`.Ng` 和 `.N%`，其中 `N` 为精度。`scaler` 和单独设置次刻度标签样式仅由 Matplotlib 支持。Plotly 图例的拖动设置通过 `fig.show(config=...)` 或导出时的 `config` 传入显示端。

### 离线页面

`write_fit_html()` 默认内嵌 Plotly.js。页面按图的固定像素尺寸排版，并随宿主窗口等比缩放和居中。可通过 `side_html` 附加右侧面板，通过 `side_width` 和 `gap` 设置面板宽度和间距。面板脚本可监听 `plotly_sliderchange` 事件。 [联动面板示例](scripts/assets/piezo_panel.html)

## 实验示例

### 电化学阻抗谱

以下示例假设每个样品占 8 列，通道 5 为阻抗实部，通道 6 为阻抗虚部。`Layer(neglog_y=True)` 会绘制 Y 数据的绝对值，并为刻度标签添加负号。

```python
import matplotlib.pyplot as plt

from plotlib import AxesFormatter, AxisStyle, Dataloader, DataPlotter, Group, Layer, make_axes_formatter

data = Dataloader(columns_per_sample=8).load_data("eis.csv")
axes_fmt = make_axes_formatter(
    x=AxisStyle(format="{x:.1e}"),
    y=AxisStyle(format="{y:.1e}"),
)
groups = Group(data, {
    "Group A": {"num": [0, 1], "linestyle": "solid"},
    "Group B": {"num": [2, 3], "linestyle": "dash"},
})
plotter = DataPlotter(data, groups=groups, channel_x=5, channel_y=6)
plotter.plot(Layer(neglog_y=True), formatters=AxesFormatter(axes=axes_fmt))
plotter.plot(Layer(neglog_y=True), by="group", formatters=AxesFormatter(axes=axes_fmt))
plt.show()
```

### 压电测试

以下示例先绘制位移与电压的关系，再生成一个双 Y 轴图，对照两者随时间的变化。通道 0 和 3 分别是位移记录与电压记录的时间通道。

```python
import matplotlib.pyplot as plt

from plotlib import AxesFormatter, AxisStyle, Dataloader, DataPlotter, Layer, make_axes_formatter

data = Dataloader(columns_per_sample=6).load_data("piezo.csv")
axes_fmt = make_axes_formatter(
    x=AxisStyle(scale="log", limits=(0.001, None), format="{x:.1e}"),
    y=AxisStyle(format="{y:.1e}", scaler=10),
)
plotter = DataPlotter(data, channel_x=2, channel_y=4, plotrange=299)
plotter.plot(formatters=AxesFormatter(axes=axes_fmt))
plotter.plot([Layer(0, 2), Layer(3, 4, side="right")], by="sample")
plt.show()
```

更多用法见 [实验脚本](scripts/)。直接运行脚本（如 `python scripts/eis_bode.py`）时弹窗选择数据文件；在代码中可调用 `main(path, show=False)` 指定文件并且不显示图窗。

## 项目结构

| 路径 | 内容 |
| --- | --- |
| `src/plotlib/` | 数据读取、选择与变换、分组、绘图计划及公开接口 |
| `src/plotlib/backends/` | Matplotlib 和 Plotly 渲染及样式应用 |
| `scripts/` | 阻抗谱、压电和拉伸实验的示例脚本 |
| `tools/` | 使用 Tk 或 Qt 的数据预处理工具 |
| `learning/` | GUI 和测试相关的学习示例 |
| `docs/api/` | Sphinx API 文档源文件 |
| `docs/KERNEL_WORK_PLAN.md` | 库的工作计划：协作方式、架构、下一阶段设计、进度和执行记录 |
| `docs/GUI_WORK_PLAN.md` | 桌面程序的工作计划：架构、待定决定、进度和执行记录 |
| `docs/GUI_COMPONENTS.md` | 桌面程序的前端组件清单（被动视图约定、选项标准写法、各组件的信号和方法） |
| `tests/` | 自动化测试。 [测试说明](tests/README.md) |

## API 文档

在线文档从源码中的 NumPy 风格文档字符串生成。在仓库根目录可以构建本地版本。

```bash
python -m pip install -e ".[docs,interactive]"
sphinx-build -b html docs/api docs/api/_build/html
```

构建后打开 `docs/api/_build/html/index.html`。API 参考列出公开对象，内部结构页按模块介绍实现。构建会读取 `pyproject.toml` 中的版本号，并将 `plotlib.__all__` 中尚未登记的公开对象写入 `docs/api/reference.rst`。删除公开对象时，应同步移除对应条目。

## 许可证

[MIT](LICENSE)。
