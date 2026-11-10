"""
第 2 步：布局管理器 与 基础控件。

学习目标：
    1. 布局管理器（Layout）—— 控件自动排版，而不是像素定位
    2. 几个最常用的输入/触发控件：QPushButton / QLabel / QLineEdit / QComboBox
    3. 布局的嵌套：横向布局里再塞一个纵向布局

和 MATLAB App Designer 的区别：
    App Designer 里你是"拖控件到画布上的固定坐标"，控件位置写死。
    Qt 的布局管理器是"声明控件之间的相对关系"（谁在谁上面/左边），
    具体像素位置由布局在窗口大小变化时自动重新计算——这也是为什么
    Qt 窗口可以随意拖动缩放而不会错位。

运行：
    python gui/step2_layout.py
"""
import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PlotLib — Step 2")
        self.resize(800, 600)

        # ------------------------------------------------------------
        # 关键点：QMainWindow.setCentralWidget() 只接受"一个"控件。
        # 想放多个控件，标准做法是：
        #   ① 造一个空白的 QWidget 当"容器"
        #   ② 给这个容器装上一个布局（QVBoxLayout / QHBoxLayout / ...）
        #   ③ 把其他控件 addWidget 进这个布局
        #   ④ 把这个容器设为 central widget
        # ------------------------------------------------------------
        container = QWidget()
        root_layout = QVBoxLayout(container)   # 传 container 进去 = 直接把这个布局绑定给它

        # --- 第一行：标题 label，占满宽度 ---
        title = QLabel("参数设置示例")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root_layout.addWidget(title)

        # --- 第二行：一个横向布局，放"标签 + 输入框" ---
        # QHBoxLayout 让子控件从左到右排列，QVBoxLayout 则是从上到下。
        # 布局是可以嵌套的：外层 root_layout 是纵向的，
        # 里面这一行是横向的 name_row，本身作为"一整行"被塞进纵向布局。
        name_row = QHBoxLayout()
        name_label = QLabel("样品名称：")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如 Sample-01")   # 输入框为空时的灰色提示文字
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_edit)
        root_layout.addLayout(name_row)   # 注意：塞布局用 addLayout，塞控件用 addWidget

        # --- 第三行：下拉框，选测量模式 ---
        mode_row = QHBoxLayout()
        mode_label = QLabel("测量模式：")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Bode", "Nyquist", "Raw"])
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.mode_combo)
        root_layout.addLayout(mode_row)

        # --- 第四行：按钮 ---
        # 目前按钮还没接任何逻辑（那是 Step 3 信号与槽的内容），
        # 这里先只关心"摆上去、排好版"。
        self.confirm_btn = QPushButton("确认")
        root_layout.addWidget(self.confirm_btn)

        # --- 用一个可伸缩的空白撑开剩余空间 ---
        # 不加这个的话，几个控件会紧挨着堆在窗口顶部；
        # addStretch() 相当于在布局末尾加一段"弹簧"，把上面内容顶住、
        # 把下方空间让出来，是 Qt 布局里常见的排版技巧。
        root_layout.addStretch()

        self.setCentralWidget(container)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
