内部结构（给开发者）
====================

使用者只需要「API 参考」里的对象。本页是库内部各模块的说明，供修改源码时查阅
（这里列出的对象不建索引，交叉引用都指向「API 参考」）。

分层与依赖方向：``plotter`` → ``plan`` → ``plot_spec`` ← ``backends``；后端不认识 ``DataSet`` 和 ``Group``。

- ``plotter``：入口，生成计划 → 交给后端 → 存结果；
- ``plan``：绘图规则，生成计划（画几张图、每张图有哪些线）；
- ``plot_spec``：各层之间传递的数据类型；
- ``layouts``：各版式的默认排版和样式叠加顺序；
- ``style``：翻译层，标准写法 → 各后端原生值；
- ``backends``：两个后端，只读计划、只管渲染。

plan：绘图规则
--------------

.. automodule:: plotlib.plan
   :members:
   :private-members:
   :no-index:

``plot_spec``：绘图约定
-----------------------

.. automodule:: plotlib.plot_spec
   :members:
   :no-index:

layouts：版式预设
-----------------

.. automodule:: plotlib.layouts
   :members:
   :no-index:

style：翻译层
-------------

.. automodule:: plotlib.style
   :members:
   :no-index:

backends：后端
--------------

.. automodule:: plotlib.backends
   :members:
   :no-index:

.. automodule:: plotlib.backends.matplotlib_backend
   :members:
   :private-members:
   :no-index:

.. automodule:: plotlib.backends.matplotlib_styles
   :members:
   :no-index:

.. automodule:: plotlib.backends.plotly_backend
   :members:
   :private-members:
   :no-index:

.. automodule:: plotlib.backends.plotly_styles
   :members:
   :no-index:
