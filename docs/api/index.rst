PlotLib 1.0
===========

PlotLib 是多样品实验数据的读取、计算和批量绘图库。同一份数据、同一套代码，
换一个参数就能输出 matplotlib 静态图或 Plotly 交互图。

典型流程是「读数据 → 选列、计算 → 分组 → 画图」：

.. code-block:: python

   from plotlib import Dataloader, DataPlotter, Group, AxisStyle, make_axes_formatter

   data = Dataloader(columns_per_sample=4).load_data('eis.csv')       # 每个样品 4 列（含 1 列标识）
   groups = Group(data, {'Ref': {'num': [0, 1]}, 'Doped': {'num': [2, 3], 'linestyle': 'dash'}})

   fmt = make_axes_formatter(x=AxisStyle(scale='log'))
   DataPlotter(data, groups=groups, channel_x=0, channel_y=1).plot_groups(axes_formatter=fmt)

   # 交互图：只换后端，再加一个滑块
   fig = DataPlotter(data, backend='plotly').plot_multiline().add_slider()

使用说明、各绘图方法的效果和完整示例见项目根目录的 ``README.md``；
本文档是从源码文档字符串生成的 API 参考。

.. toctree::
   :maxdepth: 2

   reference
   internals
