"""PlotLib 桌面窗口骨架。支持 python -m gui 和直接运行本文件。"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if __package__:
    from .qt_theme import apply_theme, configure_fonts, make_label, make_panel
else:
    from qt_theme import apply_theme, configure_fonts, make_label, make_panel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("abc123")
        self.resize(1240, 800)
        self.setMinimumSize(860, 620)

        self.build_menu_bar()
        self.build_workspace()
        self.build_status_bar()
        apply_theme(self)

    def build_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)
        for title, items in (
            ("abc001", ("abc011", "abc012")),
            ("abc002", ("abc021", "abc022")),
            ("abc003", ("abc031", "abc032")),
        ):
            menu = menu_bar.addMenu(title)
            for text in items:
                menu.addAction(text).setEnabled(False)

    def build_workspace(self):
        workspace = QWidget()
        workspace.setObjectName("workspace")
        self.setCentralWidget(workspace)

        stage = QWidget()
        stage.setMaximumWidth(1280)
        centered = QHBoxLayout(workspace)
        centered.setContentsMargins(0, 0, 0, 0)
        centered.setSpacing(0)
        centered.addStretch()
        centered.addWidget(stage, 1)
        centered.addStretch()

        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(24, 32, 24, 32)
        stage_layout.setSpacing(0)
        stage_layout.addWidget(make_label("abc123", "display"))
        stage_layout.addSpacing(24)
        divider = make_panel("sectionRule")
        divider.setFixedHeight(2)
        stage_layout.addWidget(divider)
        stage_layout.addSpacing(32)

        body = QHBoxLayout()
        body.setSpacing(24)
        stage_layout.addLayout(body, 1)

        body.addWidget(self.build_settings_panel(), 3)
        body.addWidget(self.build_plot_panel(), 9)

    def build_settings_panel(self):
        settings = make_panel("settingsPanel")
        settings.setMinimumWidth(276)
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setSpacing(0)
        heading = make_label("abc456", "heading")
        heading.setContentsMargins(16, 16, 16, 16)
        settings_layout.addWidget(heading)

        tabs = QTabWidget()
        tabs.setObjectName("settingsTabs")
        for tab, sections in (
            ("abc101", (
                ("sourceSection", "abc111"),
                ("sampleSection", "abc112"),
                ("groupSection", "abc113"),
            )),
            ("abc102", (("plotModeSection", "abc121"), ("layerSection", "abc122"))),
            ("abc103", (("styleScopeSection", "abc131"), ("stylePropertiesSection", "abc132"))),
        ):
            scroll = QScrollArea()
            scroll.setObjectName("settingsScroll")
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            page = QWidget()
            page.setObjectName("settingsPage")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(16, 16, 16, 16)
            page_layout.setSpacing(16)

            for name, title in sections:
                section = make_panel(name)
                section.setProperty("role", "section")
                section.setMinimumHeight(80)
                section_layout = QVBoxLayout(section)
                section_layout.setContentsMargins(12, 12, 12, 12)
                section_layout.addWidget(make_label(title, "label"))
                section_layout.addStretch()
                page_layout.addWidget(section)

            page_layout.addStretch()
            scroll.setWidget(page)
            tabs.addTab(scroll, tab)

        settings_layout.addWidget(tabs, 1)
        return settings

    def build_plot_panel(self):
        panel = make_panel("plotPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = make_panel("plotHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 24, 12)
        header_layout.addWidget(make_label("abc789", "heading"))
        layout.addWidget(header)

        canvas = QWidget()
        canvas.setObjectName("plotCanvas")
        layout.addWidget(canvas, 1)
        return panel

    def build_status_bar(self):
        status = self.statusBar()
        status.setObjectName("statusStrip")
        status.setSizeGripEnabled(False)
        status.setMinimumHeight(40)
        status.setContentsMargins(24, 0, 24, 0)
        status.addWidget(make_label("abc901", "status"))
        status.addPermanentWidget(make_label("abc902", "status"))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    configure_fonts(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
