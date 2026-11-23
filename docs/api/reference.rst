API 参考
========

以下对象都可以直接从 ``plotlib`` 导入（``html_export`` 除外）。

.. currentmodule:: plotlib

读取数据
--------

.. autosummary::
   :toctree: generated
   :nosignatures:

   Dataloader
   NoFileSelected

数据容器
--------

.. autosummary::
   :toctree: generated
   :nosignatures:

   DataSet
   dataset.Column
   dataset.ColumnList

选择与计算
----------

.. autosummary::
   :toctree: generated
   :nosignatures:

   DataProcessLayer
   DataTransformer

``DataTransformer`` 命名回调的返回值（一个 TypedDict，不列出继承自 dict 的方法）：

.. autoclass:: plotlib.processor.TransformMetadata
   :no-members:

分组
----

.. autosummary::
   :toctree: generated
   :nosignatures:

   Group

绘图
----

.. autosummary::
   :toctree: generated
   :nosignatures:

   DataPlotter
   plot_spec.DrawnFigure

样式对象
--------

样式对象的字段默认为 None，表示「不改，沿用下面一层」。叠加顺序：
库默认 < 版式预设 < ``DataPlotter`` 全局 < 分组样式 < 单轴 formatter。

.. autosummary::
   :toctree: generated
   :nosignatures:

   LineStyle
   AxisStyle
   FrameStyle
   LegendStyle
   TickStyle

格式化回调
----------

.. autosummary::
   :toctree: generated
   :nosignatures:

   make_axes_formatter
   make_lines_formatter
   make_legend_formatter
   combine_formatters

导出 HTML
---------

.. autosummary::
   :toctree: generated
   :nosignatures:

   html_export.write_fit_html
   html_export.build_fit_html
   html_export.figure_size
