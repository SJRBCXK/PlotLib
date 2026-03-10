"""
Data Reorder App - PySide6 版本

架构：三层分离
- Logic 层：ReorderLogic（纯 Python，数据加载/重排/导出/分组代码生成）
- View 层：CheckableListWidget / Dialogs 布局
- Signal/Slot 层：MainWindow 连接 View 事件与 Logic

"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QComboBox,
    QCheckBox, QFileDialog, QMessageBox, QScrollArea,
    QGroupBox, QSplitter, QTextEdit, QFrame,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QDialog, QDialogButtonBox, QPlainTextEdit, QStatusBar,
    QToolBar, QSizePolicy, QStyledItemDelegate, QStyleOptionViewItem
)
from PySide6.QtCore import Qt, Signal, QMimeData, QSize
from PySide6.QtGui import QFont, QAction, QPen, QPainter


# ============================================================================
# Logic 层 — 纯 Python，不依赖 Qt
# ============================================================================

class ReorderLogic:
    """数据加载、重排、导出的纯逻辑。"""

    def __init__(self):
        self.file_path: str | None = None
        self.data: pd.DataFrame | None = None
        self.names: list[Any] | None = None
        self.units: list[Any] | None = None
        self.columns_per_group: int = 4
        self.original_columns_per_group: int = 4
        self.is_new_format: bool = False
        self.group_column_structure: list[dict] | None = None
        self.header_skip_states: dict[int, bool] = {}

    def load_file(self, file_path: str, columns_per_group: int) -> tuple[int, list[str]]:
        """
        加载文件，返回 (组数, 组名列表)。

        Raises ValueError 如果文件有问题。
        """
        ext = file_path.lower().split('.')[-1]
        if ext in ('xlsx', 'xls'):
            df = pd.read_excel(file_path, header=None)
        else:
            for enc in ('utf-8', 'gbk', 'gb2312'):
                try:
                    df = pd.read_csv(file_path, low_memory=False, header=None, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("无法读取文件（编码不支持）")

        if df.empty or len(df) < 2:
            raise ValueError("文件为空或数据行数不足（至少需要 2 行）")
        if len(df.columns) == 0:
            raise ValueError("文件没有任何列数据")
        if columns_per_group <= 0:
            raise ValueError("每组列数必须大于 0")

        self.file_path = file_path
        self.columns_per_group = columns_per_group
        self.original_columns_per_group = columns_per_group

        # 检测格式
        try:
            pd.to_numeric(df.iloc[1, 0], errors='raise')
            self.is_new_format = True
        except (ValueError, TypeError, IndexError):
            self.is_new_format = False

        if self.is_new_format:
            self.units = df.iloc[0].tolist()
            self.names = df.iloc[0].tolist()
            self.data = df.iloc[1:].reset_index(drop=True).apply(pd.to_numeric, errors='coerce')  # type: ignore
        else:
            self.units = df.iloc[0].tolist()
            self.names = df.iloc[1].tolist()
            self.data = df.iloc[2:].reset_index(drop=True).apply(pd.to_numeric, errors='coerce')  # type: ignore

        total_cols = len(df.columns)
        num_groups = total_cols // columns_per_group
        remainder = total_cols % columns_per_group

        # 构建组名列表
        group_names = []
        for i in range(num_groups):
            col_idx = columns_per_group * i
            name = self.names[col_idx] if col_idx < len(self.names) else f"列组 {i}"
            group_names.append(str(name))

        if remainder > 0:
            return num_groups, group_names  # 调用者可以发出警告

        return num_groups, group_names

    def get_group_detail(self, original_idx: int, current_pos: int) -> str:
        """获取指定组的详细信息文本。"""
        if self.data is None or self.names is None:
            return ""

        col_start = self.columns_per_group * original_idx
        lines = [
            f"=== 数据组 {original_idx} 详细信息 ===\n",
            f"当前位置: {current_pos}",
            f"原始位置: {original_idx}",
            f"列范围: {col_start} - {col_start + self.columns_per_group - 1}\n",
        ]

        for offset in range(self.columns_per_group):
            col_idx = col_start + offset
            if col_idx < len(self.names):
                lines.append(f"列 {col_idx}:")
                lines.append(f"  名称: {self.names[col_idx]}")
                if self.units:
                    lines.append(f"  单位: {self.units[col_idx]}")
                col_data = self.data.iloc[:5, col_idx]
                lines.append(f"  样本数据 (前5行):")
                for j, val in enumerate(col_data):
                    lines.append(f"    [{j}] {val}")
                lines.append("")

        return "\n".join(lines)

    def save_reordered(self, save_path: str, selected_order: list[int]):
        """按照选中顺序保存数据。"""
        if self.file_path is None:
            raise RuntimeError("未加载文件")

        ext = self.file_path.lower().split('.')[-1]
        if ext in ('xlsx', 'xls'):
            df_original = pd.read_excel(self.file_path, header=None)
        else:
            for enc in ('utf-8', 'gbk', 'gb2312'):
                try:
                    df_original = pd.read_csv(self.file_path, low_memory=False, header=None, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("无法读取原始文件")

        new_columns = []
        for group_idx in selected_order:
            col_start = self.original_columns_per_group * group_idx
            if self.group_column_structure is not None:
                for col_info in self.group_column_structure:
                    if col_info['enabled']:
                        col_idx = col_start + col_info['index']
                        if col_idx < len(df_original.columns):
                            new_columns.append(df_original.iloc[:, col_idx])
            else:
                for offset in range(self.columns_per_group):
                    col_idx = col_start + offset
                    if col_idx < len(df_original.columns):
                        new_columns.append(df_original.iloc[:, col_idx])

        if not new_columns:
            raise ValueError("没有有效的数据列可以保存")

        df_reordered = pd.concat(new_columns, axis=1)
        df_reordered.columns = range(len(new_columns))

        # 更新表头行
        new_header_row = []
        for group_idx in selected_order:
            col_start = self.original_columns_per_group * group_idx
            if self.group_column_structure is not None:
                for col_info in self.group_column_structure:
                    if col_info['enabled']:
                        original_col_idx = col_start + col_info['index']
                        if self.names and original_col_idx < len(self.names):
                            new_header_row.append(self.names[original_col_idx])
                        else:
                            new_header_row.append(f"列{len(new_header_row)}")
            else:
                for offset in range(self.columns_per_group):
                    original_col_idx = col_start + offset
                    if self.names and original_col_idx < len(self.names):
                        new_header_row.append(self.names[original_col_idx])
                    else:
                        new_header_row.append(f"列{len(new_header_row)}")

        df_reordered.iloc[0] = new_header_row[:len(df_reordered.columns)]

        save_ext = save_path.lower().split('.')[-1]
        if save_ext == 'xlsx':
            df_reordered.to_excel(save_path, index=False, header=False)
        else:
            df_reordered.to_csv(save_path, index=False, header=False, encoding='utf-8-sig')

    @staticmethod
    def generate_groups_code(user_groups: list[list[int]]) -> str:
        """根据用户分组生成 groups 字典代码。"""
        basic_styles = ["-", "--", "-.", ":"]
        ordinals = lambda i: f"{i+1}{'th' if 10 <= (i+1) % 100 <= 20 else {1:'st',2:'nd',3:'rd'}.get((i+1)%10,'th')}"

        lines = ["groups = {"]
        for i, group_indices in enumerate(user_groups):
            name = ordinals(i)
            if i < 4:
                ls = f'"{basic_styles[i]}"'
            else:
                p = i - 4
                on = 3 + (p % 3) * 2
                off = 5 + (p % 4) * 2
                ls = f'(0, ({on}, {off}))'
            line = f"    '{name}': {{'num': {group_indices}, 'linestyle': {ls}}}"
            if i < len(user_groups) - 1:
                line += ","
            lines.append(line)
        lines.append("}")
        return "\n".join(lines)


# ============================================================================
# View 层 — 带边框和序号的可拖拽列表
# ============================================================================

class BorderDelegate(QStyledItemDelegate):
    """为每个列表项绘制边框和序号。"""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        # 先画默认内容（勾选框 + 文本）
        super().paint(painter, option, index)

        # 画边框
        painter.save()
        pen = QPen(Qt.GlobalColor.gray, 2)
        painter.setPen(pen)
        rect = option.rect.adjusted(1, 1, -1, -1)
        painter.drawRect(rect)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(size.height(), 36))


class CheckableListWidget(QListWidget):
    """
    支持拖拽排序 + 勾选 + 序号 + 边框的列表。

    每个 item 存储:
      - Qt.UserRole: original_idx (int)
      - Qt.UserRole+1: 原始名称 (str)
      - Qt.CheckStateRole: 勾选状态
    """

    item_clicked = Signal(int, int)  # (original_idx, current_row)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.setSpacing(2)
        self.setItemDelegate(BorderDelegate(self))
        self.setAutoScroll(True)
        self.setAutoScrollMargin(40)
        self.currentRowChanged.connect(self._on_row_changed)
        self.model().rowsMoved.connect(self._update_indices)

    def dragMoveEvent(self, event):
        """拖拽时靠近边缘自动滚动。"""
        super().dragMoveEvent(event)
        pos = event.position().toPoint()
        margin = 40
        if pos.y() < margin:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - 20)
        elif pos.y() > self.viewport().height() - margin:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + 20)

    def add_item(self, text: str, original_idx: int, checked: bool = True):
        pos = self.count()
        display_text = f"{pos + 1}.  {text}"
        item = QListWidgetItem(display_text)
        item.setData(Qt.ItemDataRole.UserRole, original_idx)
        item.setData(Qt.ItemDataRole.UserRole + 1, text)  # 保存原始名称
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsDragEnabled)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.addItem(item)

    def _update_indices(self):
        """拖拽后更新所有序号。"""
        for i in range(self.count()):
            item = self.item(i)
            if item:
                raw_name = item.data(Qt.ItemDataRole.UserRole + 1)
                item.setText(f"{i + 1}.  {raw_name}")

    def get_checked_indices(self) -> list[int]:
        """返回勾选项的 original_idx 列表（按当前显示顺序）。用于保存数据。"""
        result = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def get_checked_positions(self) -> list[int]:
        """返回勾选项的当前行号列表。用于 Groups 导出（重排后的位置索引）。"""
        result = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(i)
        return result

    def get_all_indices(self) -> list[int]:
        """返回所有项的 original_idx 列表。"""
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count()) if self.item(i)]

    def set_all_checked(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.count()):
            item = self.item(i)
            if item:
                item.setCheckState(state)

    def invert_checks(self):
        for i in range(self.count()):
            item = self.item(i)
            if item:
                item.setCheckState(
                    Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )

    def _on_row_changed(self, row: int):
        if row < 0:
            return
        item = self.item(row)
        if item:
            self.item_clicked.emit(item.data(Qt.ItemDataRole.UserRole), row)


# ============================================================================
# View 层 — 编辑组结构对话框
# ============================================================================

class GroupStructureDialog(QDialog):
    """编辑组内列结构：勾选保留/删除列，修改表头。"""

    def __init__(self, logic: ReorderLogic, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑组内列结构")
        self.resize(550, 650)
        self.logic = logic

        layout = QVBoxLayout(self)

        # 顶部：列数设置 + 刷新
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("每组列数:"))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 100)
        self.cols_spin.setValue(logic.columns_per_group)
        top_layout.addWidget(self.cols_spin)
        self.refresh_btn = QPushButton("刷新列表")
        top_layout.addWidget(self.refresh_btn)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 说明
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        # 表头编辑区
        self.header_group = QGroupBox("修改表头（应用到所有组）")
        self.header_layout = QVBoxLayout(self.header_group)
        layout.addWidget(self.header_group)

        # 列结构列表（勾选保留/删除，可拖拽排序）
        self.struct_list = CheckableListWidget()
        layout.addWidget(self.struct_list, stretch=1)

        # 底部按钮
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.reset_btn = QPushButton("重置")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # 存储表头输入控件
        self._header_widgets: list[dict] = []
        self._header_frames: list[QWidget] = []

        # 信号连接
        self.refresh_btn.clicked.connect(self._refresh_all)
        self.save_btn.clicked.connect(self._on_save)
        self.reset_btn.clicked.connect(self._on_reset)
        self.cancel_btn.clicked.connect(self.reject)
        self.struct_list.model().dataChanged.connect(self._update_header_inputs)

        # 初始化
        self._update_structure_list()
        self._update_header_inputs()

    def _update_structure_list(self):
        """根据当前列数更新结构列表。"""
        cols = self.cols_spin.value()
        self.info_label.setText(f"定义每组的 {cols} 列结构：\n勾选保留，取消勾选删除，可拖动调整顺序")

        # 保存当前勾选状态
        current_state = {}
        for i in range(self.struct_list.count()):
            item = self.struct_list.item(i)
            if item:
                current_state[item.data(Qt.ItemDataRole.UserRole)] = \
                    item.checkState() == Qt.CheckState.Checked

        self.struct_list.clear()

        # 构建结构
        if (self.logic.group_column_structure is not None
                and len(self.logic.group_column_structure) == cols):
            structure = self.logic.group_column_structure
        else:
            structure = []
            for i in range(cols):
                old_col = None
                if self.logic.group_column_structure is not None:
                    for col in self.logic.group_column_structure:
                        if col['index'] == i:
                            old_col = col
                            break
                if old_col:
                    structure.append(old_col.copy())
                else:
                    structure.append({'index': i, 'name': f'列{i}', 'enabled': True})

        for col_info in structure:
            text = f"列 {col_info['index']}: {col_info['name']}"
            checked = current_state.get(col_info['index'], col_info['enabled'])
            self.struct_list.add_item(text, col_info['index'], checked=checked)

    def _update_header_inputs(self):
        """根据勾选保留的列更新表头输入框。"""
        # 清空旧控件
        for frame in self._header_frames:
            frame.setParent(None)  # type: ignore
            frame.deleteLater()
        self._header_widgets.clear()
        self._header_frames.clear()

        if self.logic.data is None or self.logic.names is None:
            return

        for i in range(self.struct_list.count()):
            item = self.struct_list.item(i)
            if not item or item.checkState() != Qt.CheckState.Checked:
                continue

            original_col_idx = item.data(Qt.ItemDataRole.UserRole)
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)

            label = QLabel(f"列{original_col_idx}:")
            label.setFixedWidth(60)
            row_layout.addWidget(label)

            current_value = (self.logic.names[original_col_idx]
                             if original_col_idx < len(self.logic.names)
                             else f"列{original_col_idx}")
            entry = QLineEdit(str(current_value))
            row_layout.addWidget(entry)

            saved_skip = self.logic.header_skip_states.get(original_col_idx, False)
            skip_cb = QCheckBox("不修改")
            skip_cb.setChecked(saved_skip)
            row_layout.addWidget(skip_cb)

            self.header_layout.addWidget(row_widget)
            self._header_frames.append(row_widget)
            self._header_widgets.append({
                'entry': entry,
                'skip': skip_cb,
                'original_col_idx': original_col_idx
            })

    def _refresh_all(self):
        self._update_structure_list()
        self._update_header_inputs()

    def _on_reset(self):
        self.struct_list.set_all_checked(True)
        self._update_header_inputs()

    def _on_save(self):
        """保存结构和表头修改。"""
        # 收集结构
        new_structure = []
        for i in range(self.struct_list.count()):
            item = self.struct_list.item(i)
            if not item:
                continue
            idx = item.data(Qt.ItemDataRole.UserRole)
            raw_name = item.data(Qt.ItemDataRole.UserRole + 1)
            # 从显示文本中提取 name 部分
            name_part = raw_name.split(': ', 1)[1] if ': ' in raw_name else f'列{idx}'
            new_structure.append({
                'index': idx,
                'name': name_part,
                'enabled': item.checkState() == Qt.CheckState.Checked
            })
        self.logic.group_column_structure = new_structure

        # 应用表头修改（用原始步长定位，因为 names 布局未变）
        original_step = self.logic.original_columns_per_group
        total_cols = self.cols_spin.value()
        if self._header_widgets and self.logic.data is not None and self.logic.names is not None:
            num_groups = len(self.logic.data.columns) // original_step  # type: ignore

            for widget_dict in self._header_widgets:
                skip = widget_dict['skip'].isChecked()
                col_idx = widget_dict['original_col_idx']
                self.logic.header_skip_states[col_idx] = skip

                if skip:
                    continue

                new_header = widget_dict['entry'].text().strip()
                if new_header:
                    for group_idx in range(num_groups):
                        target_idx = group_idx * original_step + col_idx
                        if target_idx < len(self.logic.names):
                            self.logic.names[target_idx] = new_header
                            if self.logic.is_new_format and self.logic.units and target_idx < len(self.logic.units):
                                self.logic.units[target_idx] = new_header

        # 更新列数
        enabled_count = sum(1 for col in new_structure if col['enabled'])
        self.logic.original_columns_per_group = total_cols
        self.logic.columns_per_group = total_cols

        QMessageBox.information(self, "成功",
            f"已保存组结构和表头！\n总列数 {total_cols}，保留 {enabled_count} 列，"
            f"删除 {total_cols - enabled_count} 列")
        self.accept()


# ============================================================================
# View 层 — 分组选择对话框
# ============================================================================

class GroupSelectionDialog(QDialog):
    """分组选择对话框，允许连续添加多个分组。"""

    def __init__(self, list_widget: CheckableListWidget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("分组选择")
        self.resize(700, 500)
        self.list_widget = list_widget
        self.user_groups: list[list[int]] = []

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel('勾选一组数据 → "添加为新组"，重复操作，最后 "完成并导出"'))

        self.groups_label = QLabel("已创建 0 个组")
        self.groups_label.setStyleSheet("font-weight: bold; color: blue;")
        layout.addWidget(self.groups_label)

        # 实时预览
        group_box = QGroupBox("实时预览 Groups 字典")
        gbl = QVBoxLayout(group_box)
        self.preview_text = QPlainTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(QFont("Consolas", 10))
        gbl.addWidget(self.preview_text)
        layout.addWidget(group_box, stretch=1)

        # 按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("添加为新组")
        self.finish_btn = QPushButton("完成并导出")
        self.cancel_btn = QPushButton("取消")
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.finish_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # 信号
        self.add_btn.clicked.connect(self._on_add_group)
        self.finish_btn.clicked.connect(self._on_finish)
        self.cancel_btn.clicked.connect(self.reject)

        self._update_preview()

    def _on_add_group(self):
        selected = self.list_widget.get_checked_positions()
        if not selected:
            QMessageBox.warning(self, "警告", "请至少勾选一项数据")
            return
        if selected in self.user_groups:
            QMessageBox.warning(self, "警告", "该组合已存在")
            return
        self.user_groups.append(selected)
        self.list_widget.set_all_checked(False)
        self.groups_label.setText(f"已创建 {len(self.user_groups)} 个组")
        self._update_preview()

    def _on_finish(self):
        selected = self.list_widget.get_checked_positions()
        if selected:
            reply = QMessageBox.question(
                self, "提示",
                f"当前还有 {len(selected)} 个勾选项，是否添加为最后一组？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.user_groups.append(selected)

        if not self.user_groups:
            QMessageBox.warning(self, "警告", "至少需要创建一个组")
            return
        self.accept()

    def _update_preview(self):
        if not self.user_groups:
            self.preview_text.setPlainText("# 尚未创建任何组\ngroups = {}")
        else:
            self.preview_text.setPlainText(ReorderLogic.generate_groups_code(self.user_groups))

    def get_code(self) -> str:
        return ReorderLogic.generate_groups_code(self.user_groups)


# ============================================================================
# View 层 — 代码展示对话框
# ============================================================================

class CodeDialog(QDialog):
    """显示生成的代码，支持复制。"""

    def __init__(self, code: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("导出的 Groups 代码")
        self.resize(600, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("已生成 groups 字典代码，可直接复制到脚本中使用:"))

        self.text_edit = QPlainTextEdit(code)
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setReadOnly(False)  # 允许选中复制
        layout.addWidget(self.text_edit, stretch=1)

        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("复制到剪贴板")
        close_btn = QPushButton("关闭")
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        copy_btn.clicked.connect(lambda: (
            QApplication.clipboard().setText(code),
            QMessageBox.information(self, "成功", "已复制到剪贴板！")
        ))
        close_btn.clicked.connect(self.accept)


# ============================================================================
# Signal/Slot 层 — 主窗口
# ============================================================================

class ReorderMainWindow(QMainWindow):
    """数据重排序主窗口。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Data Reorder")
        self.resize(900, 650)

        self.logic = ReorderLogic()
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # ---- 工具栏 ----
        toolbar = QToolBar("工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel(" 每组列数: "))
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 100)
        self.cols_spin.setValue(4)
        toolbar.addWidget(self.cols_spin)

        toolbar.addSeparator()
        self.edit_struct_btn = QPushButton("编辑组结构")
        toolbar.addWidget(self.edit_struct_btn)

        toolbar.addSeparator()
        self.load_btn = QPushButton("加载文件")
        self.save_btn = QPushButton("保存选中数据")
        self.reset_btn = QPushButton("重置顺序")
        toolbar.addWidget(self.load_btn)
        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.reset_btn)

        toolbar.addSeparator()
        self.select_all_btn = QPushButton("全选")
        self.deselect_all_btn = QPushButton("取消全选")
        self.invert_btn = QPushButton("反选")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.deselect_all_btn)
        toolbar.addWidget(self.invert_btn)

        toolbar.addSeparator()
        self.export_groups_btn = QPushButton("导出 Groups 代码")
        toolbar.addWidget(self.export_groups_btn)

        # ---- 中心区域：左右分割 ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)

        # 左侧：列表
        left_group = QGroupBox("数据列名称 (勾选 + 拖动排序)")
        left_layout = QVBoxLayout(left_group)
        self.list_widget = CheckableListWidget()
        left_layout.addWidget(self.list_widget)
        splitter.addWidget(left_group)

        # 右侧：详情
        right_group = QGroupBox("列详细信息")
        right_layout = QVBoxLayout(right_group)
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Consolas", 10))
        right_layout.addWidget(self.detail_text)
        splitter.addWidget(right_group)

        splitter.setSizes([400, 500])

        # ---- 状态栏 ----
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _connect_signals(self):
        self.load_btn.clicked.connect(self._on_load)
        self.save_btn.clicked.connect(self._on_save)
        self.reset_btn.clicked.connect(self._on_reset)
        self.edit_struct_btn.clicked.connect(self._on_edit_structure)
        self.select_all_btn.clicked.connect(lambda: self.list_widget.set_all_checked(True))
        self.deselect_all_btn.clicked.connect(lambda: self.list_widget.set_all_checked(False))
        self.invert_btn.clicked.connect(self.list_widget.invert_checks)
        self.export_groups_btn.clicked.connect(self._on_export_groups)
        self.list_widget.item_clicked.connect(self._on_item_clicked)

    # ---- Slots ----

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "请选择数据文件",
            "", "所有支持的文件 (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls);;所有文件 (*.*)"
        )
        if not path:
            return

        try:
            num_groups, group_names = self.logic.load_file(path, self.cols_spin.value())

            # 检查余数
            total_cols = len(self.logic.data.columns) if self.logic.data is not None else 0  # type: ignore
            remainder = total_cols % self.cols_spin.value()
            if remainder > 0:
                QMessageBox.warning(self, "警告",
                    f"总列数 {total_cols} 不能被每组列数 {self.cols_spin.value()} 整除，"
                    f"尾部 {remainder} 列将被忽略。")

            self._populate_list(group_names)

            file_name = Path(path).name
            self.status_bar.showMessage(f"已加载: {file_name} ({num_groups} 组数据)")

        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载文件失败:\n{e}")
            self.status_bar.showMessage("加载失败")

    def _populate_list(self, group_names: list[str]):
        """填充列表（加载或结构编辑后刷新）。"""
        self.list_widget.clear()
        for i, name in enumerate(group_names):
            self.list_widget.add_item(name, i)

    def _on_save(self):
        selected = self.list_widget.get_checked_indices()
        if not selected:
            QMessageBox.warning(self, "警告", "请至少勾选一项数据")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存选中的数据", "",
            "CSV 文件 (*.csv);;Excel 文件 (*.xlsx);;所有文件 (*.*)"
        )
        if not save_path:
            return

        try:
            self.logic.save_reordered(save_path, selected)

            if self.logic.group_column_structure is not None:
                cols_per = sum(1 for c in self.logic.group_column_structure if c['enabled'])
                msg = f"已保存 {len(selected)} 组数据\n每组 {cols_per} 列\n到:\n{save_path}"
            else:
                msg = f"已保存 {len(selected)} 组数据到:\n{save_path}"

            QMessageBox.information(self, "成功", msg)
            self.status_bar.showMessage(f"已保存 {len(selected)} 组数据")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败:\n{e}")

    def _on_reset(self):
        if self.logic.data is None or self.logic.names is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        cols = self.logic.columns_per_group
        num_groups = len(self.logic.data.columns) // cols  # type: ignore
        group_names = []
        for i in range(num_groups):
            col_idx = cols * i
            name = str(self.logic.names[col_idx]) if col_idx < len(self.logic.names) else f"列组 {i}"
            group_names.append(name)
        self._populate_list(group_names)
        self.status_bar.showMessage("已重置为原始顺序")

    def _on_edit_structure(self):
        """打开编辑组结构对话框。"""
        if self.logic.data is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        dlg = GroupStructureDialog(self.logic, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # 刷新主列表
            if self.logic.names is not None and self.logic.data is not None:
                num_groups = len(self.logic.data.columns) // self.logic.original_columns_per_group  # type: ignore
                group_names = []
                for i in range(num_groups):
                    col_idx = self.logic.original_columns_per_group * i
                    name = (str(self.logic.names[col_idx])
                            if col_idx < len(self.logic.names) else f"列组 {i}")
                    group_names.append(name)
                self._populate_list(group_names)

            self.cols_spin.setValue(self.logic.columns_per_group)
            self.status_bar.showMessage("组结构已更新")

    def _on_item_clicked(self, original_idx: int, current_row: int):
        detail = self.logic.get_group_detail(original_idx, current_row)
        self.detail_text.setText(detail)

    def _on_export_groups(self):
        if self.logic.data is None:
            QMessageBox.warning(self, "警告", "请先加载数据文件")
            return

        dlg = GroupSelectionDialog(self.list_widget, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            code = dlg.get_code()
            CodeDialog(code, self).exec()


# ============================================================================
# 入口
# ============================================================================

def main():
    app = QApplication(sys.argv)
    window = ReorderMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
