"""PlotLib 桌面程序入口：``plotlib-gui`` 或 ``python -m plotlib_gui``。

这里只负责启动；以后建 Session、把 Session 和主窗口接起来也放在这里。
"""

import sys

from PySide6.QtWidgets import QApplication

from plotlib_gui.main_window import MainWindow
from plotlib_gui.theme.qt_theme import configure_fonts


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    configure_fonts(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
