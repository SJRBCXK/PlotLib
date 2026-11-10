"""
第 4 步：把 matplotlib 画布嵌入 Qt —— PlotLib 项目真正要用的核心技能。

学习目标：
    1. FigureCanvasQTAgg：matplotlib 和 Qt 之间的桥梁控件
    2. 把画布封装成独立的自定义 Widget 类（见 widgets/plot_canvas.py）
    3. 用 Step 3 学的信号与槽，把"控制面板"和"画布"两个独立组件连起来
    4. 图表随窗口缩放自动调整大小（因为画布本质就是个普通 QWidget，
       会被布局管理器正常对待）

架构（对应上一节聊的"真实项目怎么拆类"）：
    MainWindow          —— 只负责拼装，不关心内部细节
      ├── ControlPanel   —— 左侧控制面板，发出自定义信号
      └── PlotCanvas     —— 右侧画布，提供 plot_data() 方法给外部调用

    ControlPanel 和 PlotCanvas 互相不知道对方的存在，
    MainWindow 负责把两者的信号和槽连接起来——这就是"解耦"的意义：
    以后想把 ControlPanel 换成别的控件，或者把画布换成别的实现，
    互相都不用改代码。

运行：
    python gui/step4_matplotlib.py
"""
import sys

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
)

from widgets.plot_canvas import PlotCanvas


class ControlPanel(QWidget):
    """左侧控制面板：选波形类型、点按钮触发重新绘图。

    自定义信号 plot_requested：
        面板自己不画图，只负责"收集用户的选择，然后广播一个信号"。
        携带的参数是 (波形名称: str)，外部谁关心就自己去 connect。
    """

    plot_requested = Signal(str)   # 自定义信号，参数类型是 str

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        title = QLabel("控制面板")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        wave_row = QHBoxLayout()
        wave_row.addWidget(QLabel("波形："))
        self.wave_combo = QComboBox()
        self.wave_combo.addItems(["sin", "cos", "random noise"])
        wave_row.addWidget(self.wave_combo)
        layout.addLayout(wave_row)

        self.plot_btn = QPushButton("绘制")
        layout.addWidget(self.plot_btn)

        layout.addStretch()

        # 按钮点击 → 发出自定义信号，而不是自己直接去操作画布。
        # ControlPanel 完全不 import PlotCanvas，两者零耦合。
        self.plot_btn.clicked.connect(self._emit_plot_requested)

    def _emit_plot_requested(self):
        wave_name = self.wave_combo.currentText()
        self.plot_requested.emit(wave_name)   # emit = 把信号真正"发出去"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlotLib — Step 4")
        self.resize(900, 600)

        container = QWidget()
        root_layout = QHBoxLayout(container)   # 左右布局：左边控制面板，右边画布

        self.control_panel = ControlPanel()
        self.plot_canvas = PlotCanvas()

        # 给左侧面板一个较小的比例、右侧画布更大比例
        # addWidget(widget, stretch) 的第二个参数是"伸缩权重"
        root_layout.addWidget(self.control_panel, 1)
        root_layout.addWidget(self.plot_canvas, 3)

        self.setCentralWidget(container)

        # 关键的一行：MainWindow 负责把两个互不相识的组件"牵线搭桥"。
        self.control_panel.plot_requested.connect(self.on_plot_requested)

    def on_plot_requested(self, wave_name: str):
        """接收 ControlPanel 的信号，生成对应数据，调用 PlotCanvas 的公开方法。"""
        x = np.linspace(0, 2 * np.pi, 300)
        if wave_name == "sin":
            y = np.sin(x)
        elif wave_name == "cos":
            y = np.cos(x)
        else:  # random noise
            y = np.random.randn(len(x))

        self.plot_canvas.plot_data(x, y, label=wave_name)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
