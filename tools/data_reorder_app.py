import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any


class DraggableItem(ttk.Frame):
    """
    可拖拽的列表项,包含序号、勾选框和文本标签
    """
    def __init__(self, parent, text, original_idx, on_drag_start, on_drag_motion, on_drag_end, on_click):
        super().__init__(parent, relief=tk.RAISED, borderwidth=5)
        self.parent = parent
        self.original_idx = original_idx
        self.on_drag_start = on_drag_start
        self.on_drag_motion = on_drag_motion
        self.on_drag_end = on_drag_end
        self.on_click_callback = on_click

        # 配置空心边框样式
        self.configure(style='Hollow.TFrame')

        # 勾选框变量
        self.checked = tk.BooleanVar(value=True)

        # 创建序号标签
        self.index_label = ttk.Label(self, text="1.", font=("Arial", 10, "bold"), width=4, anchor=tk.E)
        self.index_label.pack(side=tk.LEFT, padx=(5, 2))

        # 创建勾选框
        self.checkbutton = ttk.Checkbutton(
            self,
            variable=self.checked,
            command=self.on_check_changed
        )
        self.checkbutton.pack(side=tk.LEFT, padx=5)

        # 创建文本标签 - 加粗字体
        self.label = ttk.Label(self, text=text, font=("Arial", 11, "bold"), cursor="hand2")
        self.label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 绑定拖拽事件到标签
        self.label.bind("<Button-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.do_drag)
        self.label.bind("<ButtonRelease-1>", self.end_drag)

        self.drag_start_y = 0

    def start_drag(self, event):
        """开始拖拽"""
        self.drag_start_y = event.y_root
        self.on_drag_start(self)
        self.on_click_callback(self)

    def do_drag(self, event):
        """拖拽中"""
        self.on_drag_motion(self, event.y_root)

    def end_drag(self, event):
        """结束拖拽"""
        self.on_drag_end(self, event.y_root)

    def on_check_changed(self):
        """勾选状态改变"""
        # 可以在这里添加额外的逻辑
        pass

    def is_checked(self):
        """返回是否被勾选"""
        return self.checked.get()

    def set_checked(self, value):
        """设置勾选状态"""
        self.checked.set(value)

    def get_text(self):
        """获取显示文本"""
        return self.label.cget("text")

    def set_index(self, index):
        """设置序号"""
        self.index_label.config(text=f"{index}.")

    def highlight(self, on=True):
        """高亮显示"""
        if on:
            self.configure(relief=tk.SUNKEN, borderwidth=5)
        else:
            self.configure(relief=tk.RAISED, borderwidth=5)


class DraggableList(ttk.Frame):
    """
    可拖拽的列表容器,管理多个DraggableItem
    """
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)

        # 创建滚动区域
        self.canvas = tk.Canvas(self, bg="white")
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 存储所有item
        self.items = []
        self.drag_item = None
        self.drag_placeholder = None

        # 外部点击回调
        self.external_click_callback = None

    def add_item(self, text, original_idx):
        """添加一个可拖拽项"""
        item = DraggableItem(
            self.scrollable_frame,
            text,
            original_idx,
            self.on_drag_start,
            self.on_drag_motion,
            self.on_drag_end,
            self.on_item_click
        )
        item.pack(fill=tk.X, padx=5, pady=2)
        self.items.append(item)
        self.update_indices()

    def clear(self):
        """清空所有项"""
        for item in self.items:
            item.destroy()
        self.items.clear()

    def on_drag_start(self, item):
        """开始拖拽"""
        self.drag_item = item
        item.highlight(True)

    def on_drag_motion(self, item, y):
        """拖拽移动中"""
        if self.drag_item is None:
            return

        # 找到鼠标下的item
        for i, target_item in enumerate(self.items):
            if target_item == self.drag_item:
                continue

            bbox = target_item.winfo_rooty()
            height = target_item.winfo_height()

            if bbox <= y <= bbox + height:
                # 交换位置
                drag_index = self.items.index(self.drag_item)
                target_index = i

                if drag_index != target_index:
                    # 更新列表
                    self.items[drag_index], self.items[target_index] = \
                        self.items[target_index], self.items[drag_index]

                    # 重新排列UI
                    if drag_index < target_index:
                        self.drag_item.pack_forget()
                        self.drag_item.pack(
                            before=self.items[target_index + 1] if target_index + 1 < len(
                                self.items) else None,
                            fill=tk.X, padx=5, pady=2
                        )
                    else:
                        self.drag_item.pack_forget()
                        self.drag_item.pack(
                            before=target_item,
                            fill=tk.X, padx=5, pady=2
                        )
                break

    def on_drag_end(self, item, y):
        """结束拖拽"""
        if self.drag_item:
            self.drag_item.highlight(False)
        self.drag_item = None
        self.update_indices()

    def on_item_click(self, item):
        """点击item"""
        # 取消其他item的高亮
        for i in self.items:
            if i != item:
                i.highlight(False)

        # 调用外部回调函数
        if self.external_click_callback:
            self.external_click_callback(item)

    def get_items(self):
        """获取所有item"""
        return self.items

    def size(self):
        """返回item数量"""
        return len(self.items)

    def update_indices(self):
        """更新所有item的序号"""
        for idx, item in enumerate(self.items, start=1):
            item.set_index(idx)


class DataReorderGUI:
    """
    数据重排序GUI应用
    允许用户加载CSV文件,查看和重新排序数据列的name
    """

    def __init__(self, root):
        self.root = root
        self.root.title("Data Reorder")
        self.root.geometry("800x600")

        # 数据存储
        self.file_path: Optional[str] = None
        self.data: Optional[pd.DataFrame] = None
        self.names: Optional[List[Any]] = None
        self.units: Optional[List[Any]] = None
        self.original_order: List[int] = []  # 存储原始列索引
        self.columns_per_group: int = 4  # 默认每组4列
        self.is_new_format: bool = False  # 标记是否为新格式（文件名+单位在第0行）

        # 存储用户创建的组
        self.user_groups: List[List[int]] = []  # 每个元素是一个列表，包含该组的索引

        # 组内列结构：list of dict, 每个dict包含 {'index': 原始列索引, 'name': 列名, 'enabled': 是否保留}
        # None表示使用默认结构（保留所有列）
        self.group_column_structure: Optional[List[Dict[str, Any]]] = None

        # 原始每组列数（用于计算col_start，不受组结构影响）
        self.original_columns_per_group: int = 4

        # 存储"不修改"勾选框的状态（key: 列索引, value: True/False）
        self.header_skip_states = {}

        self._create_widgets()

    def _create_widgets(self):
        """创建GUI组件"""

        # 顶部工具栏
        toolbar = ttk.Frame(self.root)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # 分组列数设置
        ttk.Label(toolbar, text="每组列数:").pack(side=tk.LEFT, padx=(5, 2))
        self.columns_per_group_var = tk.IntVar(value=4)
        columns_spinbox = ttk.Spinbox(
            toolbar,
            from_=1,
            to=100,
            width=5,
            textvariable=self.columns_per_group_var
        )
        columns_spinbox.pack(side=tk.LEFT, padx=(0, 5))

        # 编辑组结构按钮
        ttk.Button(toolbar, text="编辑组结构", command=self.edit_group_structure).pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(toolbar, text="加载文件", command=self.load_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="保存选中数据", command=self.save_reordered_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="重置顺序", command=self.reset_order).pack(side=tk.LEFT, padx=5)

        # 添加勾选控制按钮
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="全选", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="取消全选", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="反选", command=self.invert_selection).pack(side=tk.LEFT, padx=5)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="导出 Groups 代码", command=self.export_groups_code).pack(side=tk.LEFT, padx=5)

        # 信息标签
        self.info_label = ttk.Label(toolbar, text="请加载数据文件", foreground="blue")
        self.info_label.pack(side=tk.LEFT, padx=20)

        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 左侧 - 列名列表
        left_frame = ttk.LabelFrame(main_frame, text="数据列名称 (勾选+拖动排序)")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # 可拖拽的列表
        self.draggable_list = DraggableList(left_frame)
        self.draggable_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 保存当前选中的item引用
        self.selected_item = None

        # 右侧 - 详细信息
        right_frame = ttk.LabelFrame(main_frame, text="列详细信息")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # 详细信息文本框
        info_text_frame = ttk.Frame(right_frame)
        info_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar_info = ttk.Scrollbar(info_text_frame, orient=tk.VERTICAL)
        scrollbar_info.pack(side=tk.RIGHT, fill=tk.Y)

        self.info_text = tk.Text(
            info_text_frame,
            yscrollcommand=scrollbar_info.set,
            font=("Consolas", 10),
            wrap=tk.WORD,
            state=tk.DISABLED
        )
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_info.config(command=self.info_text.yview)

        # 底部状态栏
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(status_frame, text="就绪", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, padx=5, pady=2)

    def load_file(self):
        """加载CSV或Excel文件"""
        file_path = filedialog.askopenfilename(
            title="请选择数据文件",
            filetypes=[
                ("所有支持的文件", "*.csv;*.xlsx;*.xls"),
                ("CSV文件", "*.csv"),
                ("Excel文件", "*.xlsx;*.xls"),
                ("所有文件", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            # 根据文件扩展名读取文件
            file_ext = file_path.lower().split('.')[-1]
            if file_ext in ['xlsx', 'xls']:
                # 读取Excel文件
                df = pd.read_excel(file_path, header=None)
            else:
                # 读取CSV文件（尝试不同编码）
                try:
                    df = pd.read_csv(file_path, low_memory=False, header=None, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df = pd.read_csv(file_path, low_memory=False, header=None, encoding='gbk')
                    except UnicodeDecodeError:
                        df = pd.read_csv(file_path, low_memory=False, header=None, encoding='gb2312')

            # 边界检查：确保文件不为空且至少有2行数据
            if df.empty or len(df) < 2:
                messagebox.showerror("错误", "文件为空或数据行数不足（至少需要2行）")
                self.status_label.config(text="加载失败：文件数据不足")
                return

            if len(df.columns) == 0:
                messagebox.showerror("错误", "文件没有任何列数据")
                self.status_label.config(text="加载失败：无列数据")
                return

            # 获取用户设置的每组列数
            self.columns_per_group = self.columns_per_group_var.get()
            self.original_columns_per_group = self.columns_per_group  # 保存原始列数

            # 边界检查：确保每组列数不为0
            if self.columns_per_group <= 0:
                messagebox.showerror("错误", "每组列数必须大于0")
                self.status_label.config(text="加载失败：列数设置错误")
                return

            # 检测文件格式：尝试将第1行转为数值，如果成功说明是新格式
            try:
                pd.to_numeric(df.iloc[1, 0], errors='raise')
                self.is_new_format = True  # 新格式：第0行是文件名+单位，第1行开始是数据
            except (ValueError, TypeError, IndexError):
                self.is_new_format = False  # 旧格式：第0行单位，第1行名称，第2行开始数据

            if self.is_new_format:
                # 新格式处理：第0行包含文件名和单位，第1行开始是数据
                self.units = df.iloc[0].tolist()
                self.names = df.iloc[0].tolist()  # 使用第0行作为名称
                self.data = df.iloc[1:].reset_index(drop=True).apply(pd.to_numeric, errors='coerce')  # type: ignore
            else:
                # 旧格式处理：第0行单位，第1行名称，第2行开始数据
                self.units = df.iloc[0].tolist()
                self.names = df.iloc[1].tolist()
                self.data = df.iloc[2:].reset_index(drop=True).apply(pd.to_numeric, errors='coerce')  # type: ignore

            self.file_path = file_path

            # 计算有多少组数据
            num_groups = len(df.columns) // self.columns_per_group

            # 存储原始顺序
            self.original_order = list(range(num_groups))

            # 清空并填充列表
            self.draggable_list.clear()
            for i in range(num_groups):
                col_idx = self.columns_per_group * i
                name = self.names[col_idx] if col_idx < len(self.names) else f"列组 {i}"  # type: ignore
                # 只显示name,不显示索引号
                self.draggable_list.add_item(name, i)

            # 绑定点击事件显示详细信息
            self.draggable_list.external_click_callback = self.on_item_clicked # type: ignore

            # 更新信息
            file_name = file_path.split('/')[-1].split('\\')[-1]
            self.info_label.config(text=f"已加载: {file_name} ({num_groups} 组数据)")
            self.status_label.config(text=f"成功加载 {num_groups} 组数据列")

        except Exception as e:
            messagebox.showerror("错误", f"加载文件失败:\n{str(e)}")
            self.status_label.config(text="加载失败")

    def on_item_clicked(self, item):
        """点击item时显示详细信息"""
        if self.data is None:
            return

        self.selected_item = item
        original_idx = item.original_idx
        col_start = self.columns_per_group * original_idx

        # 构建详细信息
        items = self.draggable_list.get_items()
        current_pos = items.index(item)

        info = f"=== 数据组 {original_idx} 详细信息 ===\n\n"
        info += f"当前位置: {current_pos}\n"
        info += f"原始位置: {original_idx}\n"
        info += f"列范围: {col_start} - {col_start + self.columns_per_group - 1}\n"
        info += f"勾选状态: {'已选中' if item.is_checked() else '未选中'}\n\n"

        for offset in range(self.columns_per_group):
            col_idx = col_start + offset
            if col_idx < len(self.names):  # type: ignore
                info += f"列 {col_idx}:\n"
                info += f"  名称: {self.names[col_idx]}\n"  # type: ignore
                info += f"  单位: {self.units[col_idx]}\n"  # type: ignore

                # 显示前几行数据
                col_data = self.data.iloc[:5, col_idx]  # type: ignore
                info += f"  样本数据 (前5行):\n"
                for i, val in enumerate(col_data):
                    info += f"    [{i}] {val}\n"
                info += "\n"

        # 更新文本框
        self.info_text.config(state=tk.NORMAL)
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)
        self.info_text.config(state=tk.DISABLED)

    def get_current_order(self):
        """获取当前的列顺序(仅包含勾选的)"""
        current_order = []
        for item in self.draggable_list.get_items():
            if item.is_checked():
                current_order.append(item.original_idx)
        return current_order

    def get_all_order(self):
        """获取所有项的顺序"""
        all_order = []
        for item in self.draggable_list.get_items():
            all_order.append(item.original_idx)
        return all_order

    def select_all(self):
        """全选"""
        for item in self.draggable_list.get_items():
            item.set_checked(True)
        self.update_selection_count()

    def deselect_all(self):
        """取消全选"""
        for item in self.draggable_list.get_items():
            item.set_checked(False)
        self.update_selection_count()

    def invert_selection(self):
        """反选"""
        for item in self.draggable_list.get_items():
            item.set_checked(not item.is_checked())
        self.update_selection_count()

    def update_selection_count(self):
        """更新选中数量"""
        total = self.draggable_list.size()
        selected = sum(1 for item in self.draggable_list.get_items() if item.is_checked())
        self.status_label.config(text=f"已选中 {selected}/{total} 项")

    def reset_order(self):
        """重置为原始顺序"""
        if self.data is None:
            messagebox.showwarning("警告", "请先加载数据文件")
            return

        num_groups = len(self.original_order)
        self.draggable_list.clear()

        for i in range(num_groups):
            col_idx = self.columns_per_group * i
            name = self.names[col_idx] if col_idx < len(self.names) else f"列组 {i}"  # type: ignore
            # 只显示name,不显示索引号
            self.draggable_list.add_item(name, i)

        # 重新绑定点击事件
        self.draggable_list.external_click_callback = self.on_item_clicked # type: ignore

        self.status_label.config(text="已重置为原始顺序")

    def save_reordered_data(self):
        """保存重排序且勾选的数据"""
        if self.data is None:
            messagebox.showwarning("警告", "请先加载数据文件")
            return

        # 获取勾选的顺序
        selected_order = self.get_current_order()

        if not selected_order:
            messagebox.showwarning("警告", "请至少勾选一项数据")
            return

        # 选择保���路径
        save_path = filedialog.asksaveasfilename(
            title="保存选中的数据",
            defaultextension=".csv",
            filetypes=[
                ("CSV文件", "*.csv"),
                ("Excel文件", "*.xlsx"),
                ("所有文件", "*.*")
            ]
        )

        if not save_path:
            return

        try:
            # 读取原始数据（根据文件类型）
            file_ext = self.file_path.lower().split('.')[-1]  # type: ignore
            if file_ext in ['xlsx', 'xls']:
                df_original = pd.read_excel(self.file_path, header=None)
            else:
                # CSV文件（尝试不同编码）
                try:
                    df_original = pd.read_csv(self.file_path, low_memory=False, header=None, encoding='utf-8')
                except UnicodeDecodeError:
                    try:
                        df_original = pd.read_csv(self.file_path, low_memory=False, header=None, encoding='gbk')
                    except UnicodeDecodeError:
                        df_original = pd.read_csv(self.file_path, low_memory=False, header=None, encoding='gb2312')

            new_columns = []

            # 只保存勾选的数据组
            for group_idx in selected_order:
                # 使用原始列数计算col_start（不受组结构影响）
                col_start = self.original_columns_per_group * group_idx

                # 如果有自定义组结构，按结构保存
                if self.group_column_structure is not None:
                    for col_info in self.group_column_structure:
                        if col_info['enabled']:  # 只保留勾选的列
                            col_idx = col_start + col_info['index']
                            if col_idx < len(df_original.columns):
                                new_columns.append(df_original.iloc[:, col_idx])
                else:
                    # 没有自定义结构，保存所有列
                    for offset in range(self.columns_per_group):
                        col_idx = col_start + offset
                        if col_idx < len(df_original.columns):
                            new_columns.append(df_original.iloc[:, col_idx])

            # 边界检查：确保有数据要保存
            if not new_columns:
                messagebox.showerror("错误", "没有有效的数据列可以保存")
                self.status_label.config(text="保存失败：无有效数据")
                return

            # 创建新的DataFrame
            df_reordered = pd.concat(new_columns, axis=1)
            df_reordered.columns = range(len(new_columns))

            # 边界检查：确保DataFrame不为空
            if df_reordered.empty or len(df_reordered) == 0:
                messagebox.showerror("错误", "生成的数据为空")
                self.status_label.config(text="保存失败：数据为空")
                return

            # 更新表头行（第0行）：使用修改后的 self.names 和 self.units
            # 构建新的表头行
            new_header_row = []
            col_counter = 0
            for group_idx in selected_order:
                col_start = self.original_columns_per_group * group_idx

                if self.group_column_structure is not None:
                    # 使用自定义结构
                    for col_info in self.group_column_structure:
                        if col_info['enabled']:
                            original_col_idx = col_start + col_info['index']
                            if original_col_idx < len(self.names):  # type: ignore
                                new_header_row.append(self.names[original_col_idx])  # type: ignore
                            else:
                                new_header_row.append(f"列{col_counter}")
                            col_counter += 1
                else:
                    # 没有自定义结构
                    for offset in range(self.columns_per_group):
                        original_col_idx = col_start + offset
                        if original_col_idx < len(self.names):  # type: ignore
                            new_header_row.append(self.names[original_col_idx])  # type: ignore
                        else:
                            new_header_row.append(f"列{col_counter}")
                        col_counter += 1

            # 用新表头替换第0行（plotter固定读取格式）
            df_reordered.iloc[0] = new_header_row[:len(df_reordered.columns)]

            # 根据保存路径的扩展名决定保存格式
            save_ext = save_path.lower().split('.')[-1]
            if save_ext == 'xlsx':
                # 保存为Excel
                df_reordered.to_excel(save_path, index=False, header=False)
            else:
                # 保存为CSV（使用UTF-8 BOM以支持中文）
                df_reordered.to_csv(save_path, index=False, header=False, encoding='utf-8-sig')

            # 统计信息
            if self.group_column_structure is not None:
                cols_per_group = sum(1 for col in self.group_column_structure if col['enabled'])
                msg = f"已保存 {len(selected_order)} 组数据\n每组 {cols_per_group} 列\n到:\n{save_path}"
            else:
                msg = f"已保存 {len(selected_order)} 组数据到:\n{save_path}"

            messagebox.showinfo("成功", msg)
            self.status_label.config(text=f"已保存 {len(selected_order)} 组数据")

        except Exception as e:
            messagebox.showerror("错误", f"保存失败:\n{str(e)}")
            self.status_label.config(text="保存失败")

    def export_groups_code(self):
        """导出 Groups 代码供 PiezoPlotter 使用"""
        if self.data is None:
            messagebox.showwarning("警告", "请先加载数据文件")
            return

        # 清空之前的分组
        self.user_groups = []

        # 打开分组选择窗口
        self._show_group_selection_window()

    def _generate_groups_dict(self, selected_indices):
        """根据勾选的索引生成 groups 字典代码"""

        # 将连续的索引分组
        groups = []
        if selected_indices:
            current_group = [selected_indices[0]]

            for i in range(1, len(selected_indices)):
                if selected_indices[i] == selected_indices[i-1] + 1:
                    # 连续的索引,加入当前组
                    current_group.append(selected_indices[i])
                else:
                    # 不连续,保存当前组并开始新组
                    groups.append(current_group)
                    current_group = [selected_indices[i]]

            # 添加最后一组
            groups.append(current_group)

        # 生成代码
        code_lines = ["groups = {"]

        for i, group in enumerate(groups):
            start = group[0]
            end = group[-1] + 1  # range 是左闭右开

            # 根据组序号自动生成组名
            group_name = self._get_ordinal_name(i)

            # 根据组序号自动生成 linestyle
            linestyle = self._get_linestyle_for_group(i)

            # 构造这一行
            if len(group) == 1:
                # 单个元素
                line = f"    '{group_name}': {{'num': {start}, 'linestyle': {linestyle}}}"
            else:
                # 多个元素,使用 range
                line = f"    '{group_name}': {{'num': range({start}, {end}), 'linestyle': {linestyle}}}"

            # 添加逗号(除了最后一行)
            if i < len(groups) - 1:
                line += ","

            code_lines.append(line)

        code_lines.append("}")

        return "\n".join(code_lines)

    def _get_ordinal_name(self, index):
        """根据索引自动生成序数词组名"""
        # 特殊情况处理
        if 10 <= index % 100 <= 20:
            suffix = 'th'
        else:
            suffix_map = {1: 'st', 2: 'nd', 3: 'rd'}
            suffix = suffix_map.get(index % 10, 'th')

        return f'{index + 1}{suffix}'

    def _get_linestyle_for_group(self, group_index):
        """根据组序号自动生成 linestyle"""
        # 基础样式循环
        basic_styles = ["-", "--", "-.", ":"]

        if group_index < 4:
            # 前4个使用基础样式
            return f'"{basic_styles[group_index]}"'
        else:
            # 之后的使用自定义虚线样式
            # 生成不同的 (offset, (on, off)) 模式
            pattern_index = group_index - 4

            # 创建多样化的虚线模式
            on = 3 + (pattern_index % 3) * 2  # 3, 5, 7 循环
            off = 5 + (pattern_index % 4) * 2  # 5, 7, 9, 11 循环

            return f'(0, ({on}, {off}))'

    def _show_code_window(self, code):
        """显示代码窗口,允许复制"""
        # 创建新窗口
        code_window = tk.Toplevel(self.root)
        code_window.title("导出的 Groups 代码")
        code_window.geometry("600x400")

        # 说明标签
        info_label = ttk.Label(
            code_window,
            text="已生成 groups 字典代码,可直接复制到 Plot_script.py 中使用:",
            font=("Arial", 10, "bold")
        )
        info_label.pack(padx=10, pady=(10, 5), anchor=tk.W)

        # 文本框框架
        text_frame = ttk.Frame(code_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 滚动条
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 文本框
        text_widget = tk.Text(
            text_frame,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 10),
            wrap=tk.NONE
        )
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)

        # 插入代码
        text_widget.insert(1.0, code)
        text_widget.config(state=tk.NORMAL)  # 允许选择和复制

        # 按钮框架
        button_frame = ttk.Frame(code_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # 复制到剪贴板按钮
        def copy_to_clipboard():
            code_window.clipboard_clear()
            code_window.clipboard_append(code)
            messagebox.showinfo("成功", "已复制到剪贴板!")

        copy_button = ttk.Button(
            button_frame,
            text="复制到剪贴板",
            command=copy_to_clipboard
        )
        copy_button.pack(side=tk.LEFT, padx=5)

        # 关闭按钮
        close_button = ttk.Button(
            button_frame,
            text="关闭",
            command=code_window.destroy
        )
        close_button.pack(side=tk.LEFT, padx=5)

        # 全选文本快捷键
        def select_all(event=None):
            text_widget.tag_add(tk.SEL, "1.0", tk.END)
            text_widget.mark_set(tk.INSERT, "1.0")
            text_widget.see(tk.INSERT)
            return 'break'

        text_widget.bind('<Control-a>', select_all)

    def _show_group_selection_window(self):
        """显示分组选择窗口，允许连续选择多个组"""
        # 创建新窗口
        group_window = tk.Toplevel(self.root)
        group_window.title("分组选择")
        group_window.geometry("700x500")

        # 说明标签
        info_label = ttk.Label(
            group_window,
            text='请勾选一组数据，然��点击"添加为新组"继续选择，或"完成并导出"生成代码',
            font=("Arial", 10),
            wraplength=680
        )
        info_label.pack(padx=10, pady=(10, 5))

        # 显示已选择的组（简单计数）
        groups_display = ttk.Label(
            group_window,
            text=f"已创建 {len(self.user_groups)} 个组",
            font=("Arial", 10, "bold"),
            foreground="blue"
        )
        groups_display.pack(padx=10, pady=5)

        # 实时显示 groups 字典的文本框
        groups_preview_frame = ttk.LabelFrame(group_window, text="实时预览 Groups 字典")
        groups_preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 添加滚动条
        preview_scrollbar = ttk.Scrollbar(groups_preview_frame, orient=tk.VERTICAL)
        preview_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 文本框显示实时的 groups 字典
        groups_preview_text = tk.Text(
            groups_preview_frame,
            yscrollcommand=preview_scrollbar.set,
            font=("Consolas", 10),
            wrap=tk.NONE,
            height=10,
            state=tk.DISABLED
        )
        groups_preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        preview_scrollbar.config(command=groups_preview_text.yview)

        # 更新预览函数
        def update_groups_preview():
            """更新 groups 字典的实时预览"""
            if not self.user_groups:
                preview_code = "# 尚未创建任何组\ngroups = {}"
            else:
                preview_code = self._generate_groups_dict_from_user_groups()

            groups_preview_text.config(state=tk.NORMAL)
            groups_preview_text.delete(1.0, tk.END)
            groups_preview_text.insert(1.0, preview_code)
            groups_preview_text.config(state=tk.DISABLED)

        # 初始化显示
        update_groups_preview()

        # ���钮框架
        button_frame = ttk.Frame(group_window)
        button_frame.pack(fill=tk.X, padx=10, pady=20)

        # 添加为新组按钮
        def add_new_group():
            # 获取当前勾选的索引
            items = self.draggable_list.get_items()
            selected_indices = []
            selected_items = []

            for idx, item in enumerate(items):
                if item.is_checked():
                    selected_indices.append(idx)
                    selected_items.append(item)

            if not selected_indices:
                messagebox.showwarning("警告", "请至少勾选一项数据")
                return

            # 检查是否与已有组重复
            if selected_indices in self.user_groups:
                messagebox.showwarning("警告", f"该���合已存在于第 {self.user_groups.index(selected_indices) + 1} 组中")
                return

            # 添加到用户组列表
            self.user_groups.append(selected_indices)

            # 清空勾选
            self.deselect_all()

            # 取消所有item的高亮
            for item in items:
                item.highlight(False)

            # 高亮最后一个添加的item（选中的最后一个）
            if selected_items:
                selected_items[-1].highlight(True)

            # 更新显示
            groups_display.config(text=f"已创建 {len(self.user_groups)} 个组")

            # 实时更新预览
            update_groups_preview()

        add_group_button = ttk.Button(
            button_frame,
            text="添加为新组",
            command=add_new_group
        )
        add_group_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # 完成并导出按钮
        def finish_and_export():
            # 获取当前勾选的索引（如果有）
            items = self.draggable_list.get_items()
            selected_indices = []

            for idx, item in enumerate(items):
                if item.is_checked():
                    selected_indices.append(idx)

            # 如果还有勾选的项，询问是否添加
            if selected_indices:
                msg = (f"当前还有 {len(selected_indices)} 个勾选项，是否添加为最后一组？\n\n"
                      f'点击"是"添加后导出\n点击"否"不添加直接导出\n点击"取消"返回')
                result = messagebox.askyesnocancel("提示", msg)

                if result is None:  # 取消
                    return
                elif result:  # 是
                    self.user_groups.append(selected_indices)

            # 检查是否有组
            if not self.user_groups:
                messagebox.showwarning("警告", "至少需要创建一个组")
                return

            # 生成代码
            groups_code = self._generate_groups_dict_from_user_groups()

            # 关闭分组窗口
            group_window.destroy()

            # 显示代码窗口
            self._show_code_window(groups_code)

        finish_button = ttk.Button(
            button_frame,
            text="完成并导出",
            command=finish_and_export
        )
        finish_button.pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)

        # 取消按钮
        cancel_button = ttk.Button(
            button_frame,
            text="取消",
            command=group_window.destroy
        )
        cancel_button.pack(side=tk.LEFT, padx=5)

    def _generate_groups_dict_from_user_groups(self):
        """根据用户创建的组生成 groups 字典代码"""
        # 生成代码
        code_lines = ["groups = {"]

        for i, group_indices in enumerate(self.user_groups):
            # 根据组序号自动生成组名
            group_name = self._get_ordinal_name(i)

            # 根据组序号自动生成 linestyle
            linestyle = self._get_linestyle_for_group(i)

            # 直接使用组索引（新格式和旧格式都一样）
            # groups 字典中的 num 是 line_objects 的索引，即组索引
            indices_str = str(group_indices)

            # 构造这一行
            line = f"    '{group_name}': {{'num': {indices_str}, 'linestyle': {linestyle}}}"

            # 添加逗号(除了最后一行)
            if i < len(self.user_groups) - 1:
                line += ","

            code_lines.append(line)

        code_lines.append("}")

        return "\n".join(code_lines)

    def edit_group_structure(self):
        """编辑组内列结构"""
        # 创建编辑窗口
        edit_window = tk.Toplevel(self.root)
        edit_window.title("编辑组内列结构")
        edit_window.geometry("500x650")

        # 顶部框架：列数设置
        top_frame = ttk.Frame(edit_window)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(top_frame, text="每组列数:", font=("Arial", 10)).pack(side=tk.LEFT, padx=(0, 5))

        # 创建本地的列数变量
        local_cols_var = tk.IntVar(value=self.columns_per_group_var.get())
        cols_spinbox = ttk.Spinbox(
            top_frame,
            from_=1,
            to=100,
            width=8,
            textvariable=local_cols_var
        )
        cols_spinbox.pack(side=tk.LEFT, padx=(0, 10))

        # 添加刷新按钮
        refresh_btn = ttk.Button(top_frame, text="刷新列表", command=lambda: None)  # 先占位，后面定义
        refresh_btn.pack(side=tk.LEFT, padx=5)

        # 说明标签（初始化）
        info_label = ttk.Label(
            edit_window,
            text='',
            font=("Arial", 10),
            wraplength=480
        )
        info_label.pack(padx=10, pady=(0, 10))

        # 表头编辑框架
        header_frame = ttk.LabelFrame(edit_window, text="修改表头（应用到所有组）", padding=10)
        header_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 存储每列的表头输入框和标签
        header_widgets = {'entries': [], 'frames': []}

        # 创建可拖拽列表容器
        list_frame = ttk.Frame(edit_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        struct_list = DraggableList(list_frame)
        struct_list.pack(fill=tk.BOTH, expand=True)

        # 更新表头输入框的函数
        def update_header_inputs():
            """根据当前列结构更新表头输入框（只显示勾选保留的列）"""
            # 清空旧的输入框
            for frame in header_widgets['frames']:
                frame.destroy()
            header_widgets['entries'].clear()
            header_widgets['frames'].clear()

            # 获取当前勾选保留的列
            enabled_cols = [item for item in struct_list.get_items() if item.is_checked()]

            # 如果数据已加载且有保留的列
            if self.data is not None and enabled_cols:
                for idx, item in enumerate(enabled_cols):
                    row_frame = ttk.Frame(header_frame)
                    row_frame.pack(fill=tk.X, pady=2)
                    header_widgets['frames'].append(row_frame)

                    # 获取原始列索引
                    original_col_idx = item.original_idx

                    ttk.Label(row_frame, text=f"列{idx} (原列{original_col_idx}):", width=15).pack(side=tk.LEFT, padx=(0, 5))

                    # 从第一组获取当前值
                    current_value = self.names[original_col_idx] if original_col_idx < len(self.names) else f"列{original_col_idx}"  # type: ignore
                    var = tk.StringVar(value=current_value)
                    var.original_idx = original_col_idx  # type: ignore  # 保存原始索引，用于后续更新
                    entry = ttk.Entry(row_frame, textvariable=var, width=40)
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

                    # 添加"不修改"勾选框 - 从保存的状态中恢复值
                    saved_skip_state = self.header_skip_states.get(original_col_idx, False)
                    skip_var = tk.BooleanVar(value=saved_skip_state)
                    skip_var.original_idx = original_col_idx  # type: ignore  # 保存原始索引

                    def create_skip_callback(col_idx, var):
                        """创建勾选框回调，保存状态"""
                        def callback():
                            new_state = var.get()
                            self.header_skip_states[col_idx] = new_state
                        return callback

                    skip_checkbox = ttk.Checkbutton(row_frame, text="不修改", variable=skip_var,
                                                    command=create_skip_callback(original_col_idx, skip_var))
                    skip_checkbox.pack(side=tk.LEFT, padx=(0, 5))

                    # 将 skip_var 和 entry_var 组合存储
                    header_widgets['entries'].append({'entry': var, 'skip': skip_var})

        # 更新列表的函数
        def update_structure_list():
            """根据当前列数更新结构列表"""
            cols_per_group = local_cols_var.get()

            # 更新说明文字
            info_label.config(text=f'定义每组的 {cols_per_group} 列结构：\n勾选保留，取消勾选删除，可拖动调整顺序')

            # 保存当前状态
            current_state = {}
            for item in struct_list.get_items():
                current_state[item.original_idx] = item.is_checked()

            # 清空列表
            struct_list.clear()

            # 根据新的列数重新填充
            # 如果已有自定义结构，尽量保留
            if self.group_column_structure is not None and len(self.group_column_structure) == cols_per_group:
                # 列数没变，使用已有结构
                structure = self.group_column_structure
            else:
                # 列数变了，或者没有自定义结构，创建新的
                structure = []
                for i in range(cols_per_group):
                    # 尝试从旧结构中找到对应列
                    old_col = None
                    if self.group_column_structure is not None:
                        for col in self.group_column_structure:
                            if col['index'] == i:
                                old_col = col
                                break

                    if old_col:
                        structure.append(old_col.copy())
                    else:
                        structure.append({'index': i, 'name': f'列{i}', 'enabled': True})

            # 填充列表
            for col_info in structure:
                item_text = f"列 {col_info['index']}: {col_info['name']}"
                struct_list.add_item(item_text, col_info['index'])
                # 优先使用当前勾选状态，否则使用结构中的状态
                if col_info['index'] in current_state:
                    struct_list.items[-1].set_checked(current_state[col_info['index']])
                else:
                    struct_list.items[-1].set_checked(col_info['enabled'])

        # 初始化列表和表头输入框
        update_structure_list()
        update_header_inputs()

        # 绑定勾选框变化事件 - 当勾选状态改变时刷新表头输入框
        def on_checkbox_changed():
            """当勾选框状态改变时，刷新表头输入框"""
            update_header_inputs()

        # 覆盖 DraggableItem 的 on_check_changed 方法
        for item in struct_list.get_items():
            original_on_check_changed = item.on_check_changed
            def create_callback(orig_callback):
                def callback():
                    orig_callback()
                    on_checkbox_changed()
                return callback
            item.on_check_changed = create_callback(original_on_check_changed)
            # 重新绑定command
            item.checkbutton.config(command=item.on_check_changed)

        # 绑定刷新按钮（同时刷新列表和表头输入框）
        def refresh_all():
            update_structure_list()
            update_header_inputs()
            # 重新绑定勾选框事件
            for item in struct_list.get_items():
                original_on_check_changed = item.on_check_changed
                def create_callback(orig_callback):
                    def callback():
                        orig_callback()
                        on_checkbox_changed()
                    return callback
                item.on_check_changed = create_callback(original_on_check_changed)
                item.checkbutton.config(command=item.on_check_changed)

        refresh_btn.config(command=refresh_all)

        # 按钮框架
        button_frame = ttk.Frame(edit_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def save_structure():
            """保存结构和表头"""
            items = struct_list.get_items()
            new_structure = []

            for item in items:
                new_structure.append({
                    'index': item.original_idx,
                    'name': item.get_text().split(': ')[1] if ': ' in item.get_text() else f'列{item.original_idx}',
                    'enabled': item.is_checked()
                })

            self.group_column_structure = new_structure

            # 应用表头修改到所有组（只修改保留的列）
            total_cols = local_cols_var.get()
            if header_widgets['entries'] and self.data is not None:
                # 使用原始列数计算组数（基于文件加载时的列数，而不是修改后的列数）
                num_groups = len(self.data.columns) // self.original_columns_per_group  # type: ignore

                # 只更新勾选保留的列
                for entry_dict in header_widgets['entries']:
                    entry_var = entry_dict['entry']
                    skip_var = entry_dict['skip']

                    # 如果勾选了"不修改"，跳过这一列
                    if skip_var.get():
                        continue

                    new_header = entry_var.get().strip()
                    if new_header and hasattr(entry_var, 'original_idx'):
                        original_col_idx = entry_var.original_idx
                        # 应用到所有组的对应列（使用修改后的列数）
                        for group_idx in range(num_groups):
                            col_idx = group_idx * total_cols + original_col_idx
                            if col_idx < len(self.names):  # type: ignore
                                self.names[col_idx] = new_header # type: ignore
                                # 如果是新格式，names和units相同
                                if self.is_new_format and col_idx < len(self.units):  # type: ignore
                                    self.units[col_idx] = new_header # type: ignore

                # 刷新主列表显示（使用原始列数来获取每组的第一个列名）
                self.draggable_list.clear()
                for i in range(num_groups):
                    # 使用原始列数计算每组的起始索引
                    col_idx = self.original_columns_per_group * i
                    name = self.names[col_idx] if col_idx < len(self.names) else f"列组 {i}"  # type: ignore
                    self.draggable_list.add_item(name, i)
                self.draggable_list.external_click_callback = self.on_item_clicked  # type: ignore


            # 更新主窗口的列数
            enabled_count = sum(1 for col in self.group_column_structure if col['enabled'])

            # 保存原始列数（用于计算col_start）
            self.original_columns_per_group = total_cols
            # 显示在界面上的列数（主要用于展示）
            self.columns_per_group_var.set(total_cols)
            self.columns_per_group = total_cols

            messagebox.showinfo("成功", f"已保存组结构和表头！\n总列数 {total_cols}，保留 {enabled_count} 列，删除 {total_cols - enabled_count} 列")
            edit_window.destroy()

        def reset_structure():
            """重置为默认（全部保留）"""
            for item in struct_list.items:
                item.set_checked(True)

        ttk.Button(button_frame, text="保存", command=save_structure).pack(side=tk.LEFT, padx=5, expand=True, fill=tk.X)
        ttk.Button(button_frame, text="重置", command=reset_structure).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消", command=edit_window.destroy).pack(side=tk.LEFT, padx=5)


def main():
    """主函数"""
    root = tk.Tk()
    app = DataReorderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()