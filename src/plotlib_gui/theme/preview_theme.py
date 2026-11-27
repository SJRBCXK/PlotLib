"""运行 python -m plotlib_gui.theme.preview_theme 预览 PlotLib Qt 模板。"""

import sys
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout,
    QMainWindow, QMessageBox, QPushButton, QSlider, QVBoxLayout, QWidget,
)
from matplotlib import font_manager
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from plotlib_gui.theme.qt_theme import apply_theme, configure_fonts, make_label, make_panel, user_inter_fonts

INK = "#0f172a"
BLUE = "#1e40af"
SLATE = "#64748b"
RULE = "#e5e7eb"
SURFACE = "#f8fafc"


class MainWindow(QMainWindow):
    def __init__(self, latin_family="sans-serif"):
        super().__init__()
        self.setWindowTitle("PlotLib GUI 样式预览")
        self.resize(1240, 800)
        self.setMinimumSize(860, 620)

        workspace = QWidget()
        workspace.setObjectName("workspace")
        self.setCentralWidget(workspace)
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        stage = QWidget()
        stage.setMaximumWidth(1280)
        centered = QHBoxLayout()
        centered.setContentsMargins(0, 0, 0, 0)
        centered.setSpacing(0)
        centered.addStretch()
        centered.addWidget(stage, 1)
        centered.addStretch()
        layout.addLayout(centered, 1)

        stage_layout = QVBoxLayout(stage)
        stage_layout.setContentsMargins(24, 32, 24, 32)
        stage_layout.setSpacing(0)

        heading = QHBoxLayout()
        heading.setSpacing(24)
        heading.addWidget(make_label("PlotLib", "display"))
        heading.addStretch()
        export_button = QPushButton("导出预览图")
        export_button.setProperty("variant", "primary")
        export_button.clicked.connect(self.export_plot)
        heading.addWidget(export_button, alignment=Qt.AlignmentFlag.AlignVCenter)
        stage_layout.addLayout(heading)
        stage_layout.addSpacing(24)
        divider = make_panel("sectionRule")
        divider.setFixedHeight(2)
        stage_layout.addWidget(divider)
        stage_layout.addSpacing(32)

        body = QHBoxLayout()
        body.setSpacing(24)
        stage_layout.addLayout(body, 1)

        settings = make_panel("settingsPanel")
        settings.setMinimumWidth(276)
        controls = QVBoxLayout(settings)
        controls.setContentsMargins(32, 32, 32, 32)
        controls.setSpacing(16)
        controls.addWidget(make_label("显示设置", "heading"))
        controls.addSpacing(16)
        mode_label = make_label("显示方式", "label")
        self.mode = QComboBox()
        self.mode.addItems(["累积显示", "仅当前样品"])
        self.mode.setAccessibleName("显示方式")
        mode_label.setBuddy(self.mode)
        mode_column = QVBoxLayout()
        mode_column.setSpacing(0)
        mode_column.addWidget(mode_label)
        mode_column.addWidget(self.mode)
        controls.addLayout(mode_column)

        controls.addSpacing(8)
        sample_row = QHBoxLayout()
        sample_label = make_label("当前样品", "label")
        self.sample_value = make_label("", "value")
        sample_row.addWidget(sample_label)
        sample_row.addStretch()
        sample_row.addWidget(self.sample_value)
        controls.addLayout(sample_row)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(1, 3)
        self.slider.setValue(3)
        self.slider.setAccessibleName("当前样品")
        sample_label.setBuddy(self.slider)
        controls.addWidget(self.slider)
        body.addWidget(settings, 3, Qt.AlignmentFlag.AlignTop)

        plot_panel = make_panel("plotPanel")
        plot_layout = QVBoxLayout(plot_panel)
        plot_layout.setContentsMargins(32, 32, 32, 32)
        plot_layout.setSpacing(16)
        plot_layout.addWidget(make_label("应力–应变曲线", "heading"))
        self.figure = Figure(facecolor=SURFACE, layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.figure)
        plot_layout.addWidget(self.canvas, 1)
        body.addWidget(plot_panel, 9)

        status_strip = make_panel("statusStrip")
        status_strip.setMinimumHeight(40)
        status_layout = QHBoxLayout(status_strip)
        status_layout.setContentsMargins(24, 8, 24, 8)
        self.status = make_label("", "status")
        status_layout.addWidget(self.status)
        layout.addWidget(status_strip)

        ax = self.figure.add_subplot(facecolor="none")
        ax.set(xlabel="Strain (%)", ylabel="Stress (MPa)", xlim=(0, 16), ylim=(0, 1.2))
        plot_fonts = {font.name for font in font_manager.fontManager.ttflist}
        plot_font = next((name for name in (latin_family, "Inter") if name in plot_fonts), "DejaVu Sans")
        for label in (ax.xaxis.label, ax.yaxis.label):
            label.set_fontfamily(plot_font)
            label.set_color(INK)
        ax.tick_params(color=SLATE, labelcolor=INK, labelsize=10, length=3)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_fontfamily(plot_font)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(SLATE)
        ax.set_axisbelow(True)
        ax.grid(color=RULE, linewidth=0.8)
        self.axes = ax
        self.legend_font = font_manager.FontProperties(family=plot_font)

        # 合成数据仅用于对比不同曲线在模板中的可读性。
        strain = np.linspace(0, 16, 240)
        self.lines = []
        sample_styles = [(0.75, "--"), (0.93, ":"), (1.13, "-")]
        for sample, (scale, linestyle) in enumerate(sample_styles, 1):
            stress = scale * (0.8 * (1 - np.exp(-strain / 5)) + 0.00075 * strain**2)
            (line,) = ax.plot(strain, stress, linestyle=linestyle, label=f"Sample {sample:02d}")
            self.lines.append(line)

        self.setTabOrder(self.mode, self.slider)
        self.setTabOrder(self.slider, export_button)
        self.mode.currentIndexChanged.connect(self.update_preview)
        self.slider.valueChanged.connect(self.update_preview)
        apply_theme(self)
        self.update_preview()

    def update_preview(self):
        current = self.slider.value()
        cumulative = self.mode.currentIndex() == 0
        visible_lines = self.lines[:current] if cumulative else [self.lines[current - 1]]
        for sample, line in enumerate(self.lines, 1):
            active = sample == current
            line.set_visible(line in visible_lines)
            line.set_color(BLUE if active else SLATE)
            line.set_linewidth(2.2 if active else 1.5)

        self.sample_value.setText(f"{current:02d} / {len(self.lines):02d}")
        self.status.setText(f"演示数据  ·  显示 {len(visible_lines)} 条曲线")
        self.axes.legend(
            handles=visible_lines, loc="upper left", frameon=False,
            labelcolor=INK, prop=self.legend_font,
        )
        self.canvas.draw_idle()

    def export_plot(self):
        dialog = QFileDialog(self, "导出预览图")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setNameFilter("PNG 图像 (*.png)")
        dialog.setDefaultSuffix("png")
        dialog.selectFile("stress-strain.png")
        if not dialog.exec():
            return

        path = Path(dialog.selectedFiles()[0])
        try:
            self.figure.savefig(path, format="png", dpi=150, facecolor="#ffffff")
        except OSError as error:
            QMessageBox.warning(self, "导出失败", str(error))
            return
        self.status.setText(f"已导出 {path.name}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    latin_family = configure_fonts(app)
    # Matplotlib can miss fonts installed only for the current Windows user.
    for font_file in user_inter_fonts():
        font_manager.fontManager.addfont(font_file)
    window = MainWindow(latin_family)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
