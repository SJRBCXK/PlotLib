"""
第 1 步：最小可运行窗口。

学习目标：
    1. QApplication 与事件循环
    2. 控件树（父子关系）
    3. 一个窗口从创建到显示的完整生命周期

运行：
    python gui/step1_hello.py
"""
import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QLabel


class MainWindow(QMainWindow):
    """主窗口。

    继承 QMainWindow 而不是 QWidget，是因为 QMainWindow 自带
    菜单栏、工具栏、状态栏、以及一个「中央控件」的插槽——
    这正是一个正经桌面应用的标准骨架。
    """

    def __init__(self):
        super().__init__()

        # 窗口自身的属性
        self.setWindowTitle("PlotLib — Step 1")
        self.resize(800, 600)          # 初始大小（不是固定大小，用户仍可拖动缩放）

        # 造一个子控件，并把它设为「中央控件」。
        # setCentralWidget 这一步同时做了两件事：
        #   ① 布局：让 label 占满窗口中央区域
        #   ② 认亲：label 的 parent 变成本窗口
        label = QLabel("Hello, PlotLib GUI")
        label.setStyleSheet("font-size: 24px;")
        self.setCentralWidget(label)


def main():
    # ① 每个 Qt 程序有且只有一个 QApplication，它持有事件循环、
    #    全局样式、屏幕信息。必须在任何控件创建之前实例化。
    app = QApplication(sys.argv)

    # ② 创建窗口。注意：此时窗口对象存在于内存中，但屏幕上什么都没有。
    window = MainWindow()

    # ③ show() 只是把窗口标记为「可见」并投递一个绘制事件，
    #    它自己立刻返回——真正画到屏幕上是事件循环干的活。
    window.show()

    # ④ 进入事件循环。这一行会阻塞，直到最后一个窗口关闭。
    #    循环内部做的事：等待系统事件 → 找到目标控件 → 调用处理函数 → 重绘 → 继续等
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
