"""
第 3 步：信号与槽（Signals & Slots）—— 让控件真正"活起来"。

学习目标：
    1. 信号（signal）：控件发生某个动作时会"广播"一个信号
    2. 槽（slot）：一个普通的函数/方法，用来接收信号、执行响应逻辑
    3. connect()：把信号和槽绑在一起
    4. 信号可以带参数，把"发生了什么"的信息一并传给槽函数

和 MATLAB App Designer 回调函数的对应关系：
    MATLAB 里你在 App Designer 的属性面板给按钮的 ButtonPushedFcn 绑定一个
    回调函数，点击按钮时 MATLAB 自动调用它。
    Qt 的写法本质一样，只是要你自己手写"绑定"这一步：
        button.clicked.connect(self.on_button_clicked)
    "clicked" 就是信号，"on_button_clicked" 就是槽（其实就是个普通方法）。

运行：
    python gui/step3_signals.py
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
        self.setWindowTitle("PlotLib — Step 3")
        self.resize(800, 600)

        container = QWidget()
        root_layout = QVBoxLayout(container)

        title = QLabel("参数设置示例")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        root_layout.addWidget(title)

        # --- 姓名输入行 ---
        name_row = QHBoxLayout()
        name_label = QLabel("样品名称：")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如 Sample-01")
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_edit)
        root_layout.addLayout(name_row)

        # --- 模式下拉框 ---
        mode_row = QHBoxLayout()
        mode_label = QLabel("测量模式：")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Bode", "Nyquist", "Raw"])
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.mode_combo)
        root_layout.addLayout(mode_row)

        # --- 确认按钮 ---
        self.confirm_btn = QPushButton("确认")
        root_layout.addWidget(self.confirm_btn)

        # --- 用来显示反馈信息的 label ---
        # 这是本节新加的控件：所有交互的结果都会显示在这里，
        # 方便直观看到"信号触发了槽函数"这件事真的发生了。
        self.status_label = QLabel("状态：等待操作……")
        self.status_label.setStyleSheet("color: #555;")
        root_layout.addWidget(self.status_label)

        root_layout.addStretch()
        self.setCentralWidget(container)

        # ------------------------------------------------------------
        # 核心：信号与槽的连接。
        # 语法固定是：<控件实例>.<信号名>.connect(<槽函数>)
        #
        # 注意这里传的是 self.on_confirm_clicked 这个"方法对象本身"，
        # 不要写成 self.on_confirm_clicked()（多了括号就变成"立刻调用"，
        # 而不是"把这个函数交给 Qt，以后再调用"——这是最常见的新手错误）。
        # ------------------------------------------------------------
        self.confirm_btn.clicked.connect(self.on_confirm_clicked)

        # QLineEdit 的 textChanged 信号：每次输入框内容变化都会触发，
        # 并且会把"变化后的新内容"作为参数传给槽函数。
        self.name_edit.textChanged.connect(self.on_name_changed)

        # QComboBox 的 currentTextChanged 信号：切换下拉选项时触发，
        # 参数是"新选中的文字"。
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)

    # ------------------------------------------------------------
    # 槽函数们：本质就是普通的实例方法，命名上习惯用 on_xxx 前缀，
    # 但这只是约定，不是强制语法要求。
    # ------------------------------------------------------------

    def on_confirm_clicked(self):
        """按钮被点击时触发。clicked 信号本身不带参数，所以这里不用写参数。"""
        name = self.name_edit.text()          # 主动去读输入框当前的值
        mode = self.mode_combo.currentText()   # 主动去读下拉框当前选中项
        if not name:
            self.status_label.setText("状态：请先填写样品名称！")
            self.status_label.setStyleSheet("color: red;")
            return
        self.status_label.setText(f"状态：已确认 —— 样品「{name}」，模式「{mode}」")
        self.status_label.setStyleSheet("color: green;")

    def on_name_changed(self, new_text: str):
        """输入框内容变化时触发，new_text 由信号自动传入，不用自己去 .text() 取。"""
        print(f"[textChanged] 当前输入：{new_text!r}")

    def on_mode_changed(self, new_mode: str):
        """下拉框选项变化时触发。"""
        self.status_label.setText(f"状态：模式切换为「{new_mode}」")
        self.status_label.setStyleSheet("color: #555;")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
