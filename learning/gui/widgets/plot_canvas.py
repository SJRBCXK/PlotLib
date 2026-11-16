"""
PlotCanvas —— 把 matplotlib 画布封装成一个独立的 Qt 控件。

设计原则（对应上一节聊的"真实项目怎么拆类"）：
    这个类只关心"怎么画图"，完全不知道数据从哪来、外面有哪些控件。
    谁需要图表，就 new 一个 PlotCanvas 塞进自己的布局里即可，
    这就是"组件化"——PlotCanvas 可以被任何窗口复用，不和某个具体界面绑死。
"""
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QWidget, QVBoxLayout


class PlotCanvas(QWidget):
    """内嵌 matplotlib 图表的控件。

    继承 QWidget（不是 QMainWindow）：因为这不是一个独立窗口，
    而是要被"装进"别的窗口/布局里的一个组件——这是自定义控件的标准写法。
    """

    def __init__(self, parent=None):
        # 把 parent 转发给 QWidget 的构造函数：
        # 这样当这个 PlotCanvas 被 addWidget() 进某个布局时，
        # Qt 能正确建立父子关系（涉及内存管理、显示层级）。
        super().__init__(parent)

        # ------------------------------------------------------------
        # matplotlib 侧：Figure 是"画布数据模型"（图表内容、坐标轴等），
        # FigureCanvasQTAgg 是"把 Figure 渲染成 Qt 控件"的桥梁类。
        # 桥梁类本身就是一个 QWidget 的子类，所以可以直接塞进布局。
        # ------------------------------------------------------------
        self.figure = Figure(figsize=(5, 4))
        self.canvas = FigureCanvasQTAgg(self.figure)

        # 预先建好一个坐标轴对象，后面刷新数据时反复复用它，
        # 而不是每次都创建新的 Axes（那样旧的坐标轴设置会丢失、也更慢）。
        self.axes = self.figure.add_subplot(111)

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        # 注意这里没有 addStretch()——因为我们希望画布占满这个控件的
        # 全部空间，而不是被挤到一角。

        self._plot_placeholder()

    def _plot_placeholder(self):
        """初始状态：画一条示例曲线，方便直观看到画布已经工作。"""
        x = np.linspace(0, 2 * np.pi, 200)
        y = np.sin(x)
        self.axes.plot(x, y, label="sin(x)")
        self.axes.set_title("PlotCanvas 示例")
        self.axes.legend()
        self.canvas.draw()   # 关键：改完 axes 之后必须手动调用 draw() 才会重绘到屏幕

    def plot_data(self, x, y, label: str = ""):
        """外部调用的公开方法：清空旧图，画新数据。

        这就是"外壳"该有的样子——外部代码不需要知道 matplotlib 的
        Figure/Axes 细节，只需要调用 plot_data(x, y) 就行。
        """
        self.axes.clear()          # 清掉旧曲线，否则会一条条叠加上去
        self.axes.plot(x, y, label=label or None)
        if label:
            self.axes.legend()
        self.axes.set_title("PlotCanvas 示例")
        self.canvas.draw()         # 每次改完数据都要重新 draw()，否则屏幕不会更新
