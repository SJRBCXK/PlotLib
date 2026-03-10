"""
Data Collector - PySide6 版本

架构：三层分离
- Logic 层：DataLoader / DataProcessor / DataPlotter（纯 Python，不依赖 Qt）
- View 层：各 Widget 类（只负责布局和控件）
- Signal/Slot 层：MainWindow 连接 View 事件与 Logic 调用

"""

import os
import sys
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QWizard, QWizardPage,
    QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QRadioButton, QButtonGroup, QFileDialog,
    QMessageBox, QScrollArea, QGroupBox, QStatusBar,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal


# ============================================================================
# Logic 层 — 纯 Python，不依赖 Qt
# ============================================================================

# 中文字体设置
for fname in ("SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Arial Unicode MS"):
    if any(fname.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [fname]
        break
plt.rcParams["axes.unicode_minus"] = False


class DataLoader:
    """负责从文件中读取数据，支持跳过前 N 行。"""

    def __init__(self, folder_path: str, file_type: str, skip_lines: int = 0):
        self.folder_path = folder_path
        self.file_type = file_type
        self.skip_lines = skip_lines

    def get_file_list(self) -> list[str]:
        ext = self.file_type.replace("*", "")
        files = [f for f in os.listdir(self.folder_path) if f.lower().endswith(ext.lower())]
        files.sort()
        return files

    def load_file(self, filename: str) -> list[list]:
        file_path = os.path.join(self.folder_path, filename)
        ext = Path(filename).suffix.lower()
        if ext in (".csv", ".txt"):
            return self._load_text_file(file_path)
        elif ext in (".xlsx", ".xls"):
            return self._load_excel_file(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")

    def load_all_files(self) -> list[tuple[str, list[list]]]:
        return [(fname, self.load_file(fname)) for fname in self.get_file_list()]

    def _load_text_file(self, file_path: str) -> list[list]:
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                df = pd.read_csv(file_path, sep=None, engine="python",
                                 header=None, skiprows=self.skip_lines, encoding=encoding)
                return df.values.tolist()
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法读取文件: {file_path}")

    def _load_excel_file(self, file_path: str) -> list[list]:
        df = pd.read_excel(file_path, header=None, skiprows=self.skip_lines)
        return df.values.tolist()


class DataProcessor:
    """负责提取列、合并数据、数据转换。"""

    def __init__(self, data_collection: list[tuple[str, list[list]]], column_config: list[tuple[str, int]]):
        self.data_collection = data_collection
        self.column_config = column_config

    def extract_columns(self) -> list[list]:
        num_files = len(self.data_collection)
        num_cols = len(self.column_config)
        max_rows = max(len(d[1]) for d in self.data_collection) if self.data_collection else 0
        total_cols = (num_cols + 1) * num_files
        result = [[None] * total_cols for _ in range(max_rows + 1)]

        col_idx = 0
        for i in range(num_files):
            filename = self.data_collection[i][0]
            data = self.data_collection[i][1]
            data_rows = len(data)
            result[0][col_idx] = filename  # type: ignore
            for j in range(num_cols):
                col_name = self.column_config[j][0]
                col_num = self.column_config[j][1]
                result[0][col_idx + j + 1] = col_name  # type: ignore
                if col_num - 1 < (len(data[0]) if data else 0):
                    for row in range(data_rows):
                        if col_num - 1 < len(data[row]):
                            result[row + 1][col_idx + j + 1] = data[row][col_num - 1]
            col_idx += num_cols + 1
        return result

    def export_to_csv(self, output_path: str, data_set: list[list]):
        with open(output_path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            for row in data_set:
                writer.writerow(row)

    def get_column_data(self, data_set: list[list], column_name: str) -> np.ndarray:
        num_files = len(self.data_collection)
        num_data_cols = len(self.column_config)
        max_rows = len(data_set) - 1
        col_data = np.zeros((max_rows, num_files))

        col_idx = 0
        for i in range(num_files):
            for j in range(num_data_cols):
                header = data_set[0][col_idx + j + 1]
                if header == column_name:
                    for k in range(max_rows):
                        val = data_set[k + 1][col_idx + j + 1]
                        if val is not None:
                            try:
                                col_data[k, i] = float(val)
                            except (ValueError, TypeError):
                                pass
                    break
            col_idx += num_data_cols + 1
        return col_data


class DataPlotter:
    """负责绘制图表、保存图片。"""

    def __init__(self, output_folder: str, x_log: bool = False, y_log: bool = False):
        self.output_folder = output_folder
        self.x_log = x_log
        self.y_log = y_log

    def plot_single(self, x_data, y_data, title_text, x_label, y_label, filename):
        valid_idx = (x_data != 0) & (y_data != 0)
        x_plot, y_plot = x_data[valid_idx], y_data[valid_idx]
        if len(x_plot) == 0:
            return

        fig, ax = plt.subplots()
        ax.plot(x_plot, y_plot, linewidth=3)
        ax.set_title(title_text)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(3)
        ax.tick_params(width=3, labelsize=16)
        if self.x_log: ax.set_xscale("log")
        if self.y_log: ax.set_yscale("log")
        ax.set_xlim(self._get_axis_limits(x_plot))
        ax.set_ylim(self._get_axis_limits(y_plot))
        ax.set_xlabel(x_label, fontsize=16, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=16, fontweight="bold")
        fig.savefig(os.path.join(self.output_folder, f"{filename}.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    def plot_overlay(self, x_data_matrix, y_data_matrix, filenames, x_label, y_label):
        fig, ax = plt.subplots()
        for i in range(x_data_matrix.shape[1]):
            x_data, y_data = x_data_matrix[:, i], y_data_matrix[:, i]
            valid_idx = (x_data != 0) & (y_data != 0)
            x_plot, y_plot = x_data[valid_idx], y_data[valid_idx]
            if len(x_plot) > 0:
                ax.plot(x_plot, y_plot, linewidth=3)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(3)
        ax.tick_params(width=3, labelsize=16)
        if self.x_log: ax.set_xscale("log")
        if self.y_log: ax.set_yscale("log")
        all_x = x_data_matrix[x_data_matrix != 0]
        all_y = y_data_matrix[y_data_matrix != 0]
        if len(all_x) > 0: ax.set_xlim(self._get_axis_limits(all_x))
        if len(all_y) > 0: ax.set_ylim(self._get_axis_limits(all_y))
        ax.set_xlabel(x_label, fontsize=16, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=16, fontweight="bold")
        fig.savefig(os.path.join(self.output_folder, "total.png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    @staticmethod
    def _get_axis_limits(data):
        min_val, max_val = float(np.min(data)), float(np.max(data))
        upper = max_val * 0.95 if max_val < 0 else max_val * 1.1
        lower = min_val * 1.1 if min_val < 0 else min_val * 0.95
        return (lower, upper)


# ============================================================================
# View 层 — 向导页面（只负责布局和控件，不含业务逻辑）
# ============================================================================

class FolderPage(QWizardPage):
    """第 1 页：选择文件夹。"""

    def __init__(self):
        super().__init__()
        self.setTitle("选择数据文件夹")
        self.setSubTitle("请选择包含数据文件的文件夹路径")

        layout = QHBoxLayout(self)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("点击右侧按钮选择文件夹...")
        self.browse_btn = QPushButton("浏览...")
        layout.addWidget(self.path_edit, stretch=1)
        layout.addWidget(self.browse_btn)

        # 注册字段供后续页面读取
        self.registerField("folder_path*", self.path_edit)

    def browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择数据文件夹")
        if path:
            self.path_edit.setText(path)


class SkipLinesPage(QWizardPage):
    """第 2 页：跳过行设置。"""

    def __init__(self):
        super().__init__()
        self.setTitle("跳过行设置")
        self.setSubTitle("是否需要跳过文件前 N 行？")

        layout = QVBoxLayout(self)

        # 单选按钮
        self.btn_group = QButtonGroup(self)
        self.radio_no = QRadioButton("否，不跳过")
        self.radio_yes = QRadioButton("是，跳过前 N 行")
        self.radio_no.setChecked(True)
        self.btn_group.addButton(self.radio_no)
        self.btn_group.addButton(self.radio_yes)
        layout.addWidget(self.radio_no)
        layout.addWidget(self.radio_yes)

        # 行数输入
        row_layout = QHBoxLayout()
        self.skip_label = QLabel("跳过行数:")
        self.skip_spin = QSpinBox()
        self.skip_spin.setRange(1, 9999)
        self.skip_spin.setValue(1)
        self.skip_spin.setEnabled(False)
        self.skip_label.setEnabled(False)
        row_layout.addWidget(self.skip_label)
        row_layout.addWidget(self.skip_spin)
        row_layout.addStretch()
        layout.addLayout(row_layout)
        layout.addStretch()

    def toggle_skip(self, enabled: bool):
        self.skip_label.setEnabled(enabled)
        self.skip_spin.setEnabled(enabled)

    def get_skip_lines(self) -> int:
        return self.skip_spin.value() if self.radio_yes.isChecked() else 0


class ColumnConfigPage(QWizardPage):
    """第 3 页：文件类型和列配置。"""

    def __init__(self):
        super().__init__()
        self.setTitle("文件配置")
        self.setSubTitle("设置文件类型和要提取的数据列")

        main_layout = QVBoxLayout(self)

        # 顶部：列数 + 文件类型
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("数据列数:"))
        self.col_num_spin = QSpinBox()
        self.col_num_spin.setRange(1, 30)
        self.col_num_spin.setValue(1)
        top_layout.addWidget(self.col_num_spin)

        top_layout.addSpacing(20)
        top_layout.addWidget(QLabel("文件类型:"))
        self.filetype_combo = QComboBox()
        self.filetype_combo.addItems(["*.csv", "*.txt", "*.xlsx"])
        top_layout.addWidget(self.filetype_combo)

        self.update_btn = QPushButton("更新列")
        top_layout.addWidget(self.update_btn)
        top_layout.addStretch()
        main_layout.addLayout(top_layout)

        # 可滚动的列配置区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        scroll.setWidget(self.scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.save_config_btn = QPushButton("保存配置")
        self.load_config_btn = QPushButton("加载配置")
        btn_layout.addWidget(self.save_config_btn)
        btn_layout.addWidget(self.load_config_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 存储列控件
        self.col_widgets: list[tuple[QLineEdit, QSpinBox]] = []

    def rebuild_columns(self, n: int | None = None):
        """重建列配置输入行。"""
        if n is None or isinstance(n, bool):
            n = self.col_num_spin.value()

        # 清空旧控件
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():#type: ignore
                child.widget().deleteLater() #type: ignore
        self.col_widgets.clear()

        # 表头
        header = QHBoxLayout()
        lbl_name = QLabel("数据类型")
        lbl_name.setStyleSheet("font-weight: bold;")
        lbl_col = QLabel("列号 (1-based)")
        lbl_col.setStyleSheet("font-weight: bold;")
        header_widget = QWidget()
        header_widget.setLayout(header)
        header.addWidget(lbl_name, stretch=1)
        header.addWidget(lbl_col, stretch=0)
        self.scroll_layout.addWidget(header_widget)

        for _ in range(n):
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            name_edit = QLineEdit()
            name_edit.setPlaceholderText("列名称")
            col_spin = QSpinBox()
            col_spin.setRange(0, 9999)
            col_spin.setValue(0)
            row_layout.addWidget(name_edit, stretch=1)
            row_layout.addWidget(col_spin, stretch=0)
            self.scroll_layout.addWidget(row_widget)
            self.col_widgets.append((name_edit, col_spin))

        self.scroll_layout.addStretch()

    def get_file_type(self) -> str:
        return self.filetype_combo.currentText()

    def get_column_config(self) -> list[tuple[str, int]]:
        result = []
        col_numbers = []
        for name_edit, col_spin in self.col_widgets:
            name = name_edit.text().strip()
            col_no = col_spin.value()
            result.append((name, col_no))
            col_numbers.append(col_no)
        return result

    def set_from_config(self, config: dict):
        """从 JSON 配置填充控件。"""
        self.filetype_combo.setCurrentText(config.get("file_type", "*.csv"))
        columns = config.get("columns", [])
        self.col_num_spin.setValue(len(columns))
        self.rebuild_columns(len(columns))
        for i, col_info in enumerate(columns):
            if i < len(self.col_widgets):
                self.col_widgets[i][0].setText(col_info.get("name", ""))
                self.col_widgets[i][1].setValue(col_info.get("col", 0))

    def to_config_dict(self) -> dict:
        """导出为 JSON 配置字典。"""
        columns = []
        for name_edit, col_spin in self.col_widgets:
            columns.append({"name": name_edit.text().strip(), "col": col_spin.value()})
        return {"file_type": self.filetype_combo.currentText(), "columns": columns}


class PlotConfigPage(QWizardPage):
    """第 4 页：绘图设置。"""

    def __init__(self):
        super().__init__()
        self.setTitle("绘图设置")
        self.setSubTitle("选择是否绘制图像及 X/Y 轴配置")

        layout = QVBoxLayout(self)

        # 是否绘图
        self.btn_group = QButtonGroup(self)
        self.radio_no = QRadioButton("否，不绘图")
        self.radio_yes = QRadioButton("是，绘制图像")
        self.radio_no.setChecked(True)
        self.btn_group.addButton(self.radio_no)
        self.btn_group.addButton(self.radio_yes)
        layout.addWidget(self.radio_no)
        layout.addWidget(self.radio_yes)

        # X/Y 轴选择
        self.config_group = QGroupBox("轴配置")
        self.config_group.setEnabled(False)
        form = QFormLayout(self.config_group)

        self.x_combo = QComboBox()
        self.x_log_cb = QCheckBox("X 对数")
        x_row = QHBoxLayout()
        x_row.addWidget(self.x_combo, stretch=1)
        x_row.addWidget(self.x_log_cb)
        form.addRow("X 轴:", x_row)

        self.y_combo = QComboBox()
        self.y_log_cb = QCheckBox("Y 对数")
        y_row = QHBoxLayout()
        y_row.addWidget(self.y_combo, stretch=1)
        y_row.addWidget(self.y_log_cb)
        form.addRow("Y 轴:", y_row)

        layout.addWidget(self.config_group)
        layout.addStretch()

    def set_column_names(self, names: list[str]):
        self.x_combo.clear()
        self.y_combo.clear()
        self.x_combo.addItems(names)
        self.y_combo.addItems(names)

    def toggle_config(self, enabled: bool):
        self.config_group.setEnabled(enabled)

    def get_plot_config(self) -> dict:
        return {
            "should_plot": self.radio_yes.isChecked(),
            "x_col": self.x_combo.currentText(),
            "y_col": self.y_combo.currentText(),
            "x_log": self.x_log_cb.isChecked(),
            "y_log": self.y_log_cb.isChecked(),
        }


# ============================================================================
# Signal/Slot 层 — 向导主窗口，连接 View 与 Logic
# ============================================================================

class CollectorWizard(QWizard):
    """数据收集向导：连接四个页面与后端逻辑。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Collector")
        self.setMinimumSize(650, 500)

        # 创建页面
        self.folder_page = FolderPage()
        self.skip_page = SkipLinesPage()
        self.column_page = ColumnConfigPage()
        self.plot_page = PlotConfigPage()

        self.addPage(self.folder_page)
        self.addPage(self.skip_page)
        self.addPage(self.column_page)
        self.addPage(self.plot_page)

        # ---- 连接信号 ----

        # 第 1 页：浏览按钮
        self.folder_page.browse_btn.clicked.connect(self.folder_page.browse)

        # 第 2 页：跳过行切换
        self.skip_page.radio_yes.toggled.connect(self.skip_page.toggle_skip)

        # 第 3 页：更新列 / 保存 / 加载配置
        self.column_page.update_btn.clicked.connect(self.column_page.rebuild_columns)
        self.column_page.save_config_btn.clicked.connect(self._on_save_config)
        self.column_page.load_config_btn.clicked.connect(self._on_load_config)

        # 第 4 页：绘图开关
        self.plot_page.radio_yes.toggled.connect(self.plot_page.toggle_config)

        # 向导完成
        self.finished.connect(self._on_finished)

        # 初始化列配置
        self.column_page.rebuild_columns()

    # ---- 页面切换钩子 ----

    def initializePage(self, page_id: int):
        """页面初始化时的回调（QWizard 内置机制）。"""
        super().initializePage(page_id)
        page = self.page(page_id)

        if page is self.plot_page:
            # 进入绘图页时，用列配置填充下拉框
            col_config = self.column_page.get_column_config()
            names = [c[0] for c in col_config if c[0]]
            self.plot_page.set_column_names(names)

    # ---- Slot：配置文件保存/加载 ----

    def _on_save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存配置文件", "column_config.json", "JSON 文件 (*.json)")
        if not path:
            return
        config = self.column_page.to_config_dict()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "成功", "配置已保存！")

    def _on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载配置文件", "", "JSON 文件 (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                config = json.load(fh)
            self.column_page.set_from_config(config)
            QMessageBox.information(self, "成功", "配置已加载！")
        except Exception:
            QMessageBox.critical(self, "错误", "配置文件加载失败！")

    # ---- 校验：点击"完成"前拦截 ----

    def validateCurrentPage(self) -> bool:
        """在最后一页点"完成"时校验列号重复。"""
        if self.currentPage() is self.plot_page:
            column_config = self.column_page.get_column_config()
            col_numbers = [c[1] for c in column_config]
            if len(set(col_numbers)) != len(col_numbers):
                QMessageBox.critical(self, "错误", "存在重复的列号，请返回列配置页修改！")
                return False
        return super().validateCurrentPage()

    # ---- Slot：向导完成 → 执行数据处理 ----

    def _on_finished(self, result: int):
        if result != QWizard.DialogCode.Accepted:
            return

        folder_path = self.folder_page.path_edit.text()
        skip_lines = self.skip_page.get_skip_lines()
        file_type = self.column_page.get_file_type()
        column_config = self.column_page.get_column_config()
        plot_config = self.plot_page.get_plot_config()

        try:
            # 1. 加载数据
            loader = DataLoader(folder_path, file_type, skip_lines)
            data_collection = loader.load_all_files()
            if not data_collection:
                QMessageBox.warning(self, "提示", "未找到符合条件的文件")
                return

            # 2. 提取列
            processor = DataProcessor(data_collection, column_config)
            data_set = processor.extract_columns()

            # 3. 导出 CSV
            output_file = os.path.join(folder_path, "data_Set.csv")
            processor.export_to_csv(output_file, data_set)

            # 4. 绘图（可选）
            if plot_config["should_plot"]:
                plotter = DataPlotter(folder_path, plot_config["x_log"], plot_config["y_log"])
                x_matrix = processor.get_column_data(data_set, plot_config["x_col"])
                y_matrix = processor.get_column_data(data_set, plot_config["y_col"])
                file_list = loader.get_file_list()

                for i in range(len(file_list)):
                    plotter.plot_single(
                        x_matrix[:, i], y_matrix[:, i],
                        file_list[i], plot_config["x_col"], plot_config["y_col"],
                        Path(file_list[i]).stem
                    )
                plotter.plot_overlay(x_matrix, y_matrix, file_list,
                                     plot_config["x_col"], plot_config["y_col"])

            QMessageBox.information(self, "完成",
                                    f"数据已导出到:\n{output_file}"
                                    + ("\n图表已保存" if plot_config["should_plot"] else ""))

        except Exception as e:
            QMessageBox.critical(self, "错误", f"处理失败:\n{e}")


# ============================================================================
# 入口
# ============================================================================

def main():
    app = QApplication(sys.argv)
    wizard = CollectorWizard()
    wizard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()