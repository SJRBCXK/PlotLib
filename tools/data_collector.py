"""
AutoDataProcessing_OOP - 面向对象版本的数据处理主程序 (Python版)

架构说明：
- DataLoader: 负责文件读取和跳过行功能
- DataProcessor: 负责数据提取和处理
- DataPlotter: 负责数据可视化
- UIController: 负责用户交互界面
"""

import os
import csv
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 尝试设置中文字体
for fname in ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Arial Unicode MS"]:
    if any(fname.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [fname]
        break
plt.rcParams["axes.unicode_minus"] = False


# ============================================================================
# DataLoader - 数据读取类
# ============================================================================
class DataLoader:
    """负责从文件中读取数据，支持跳过前N行"""

    def __init__(self, folder_path: str, file_type: str, skip_lines: int = 0):
        self.folder_path = folder_path
        self.file_type = file_type  # e.g. "*.csv", "*.txt", "*.xlsx"
        self.skip_lines = skip_lines

    def get_file_list(self) -> list[str]:
        ext = self.file_type.replace("*", "")  # e.g. ".csv"
        files = [
            f for f in os.listdir(self.folder_path)
            if f.lower().endswith(ext.lower())
        ]
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
        file_list = self.get_file_list()
        data_collection = []
        for fname in file_list:
            data = self.load_file(fname)
            data_collection.append((fname, data))
        return data_collection

    # ---- private ----

    def _load_text_file(self, file_path: str) -> list[list]:
        # 使用pandas自动检测分隔符、编码、数据类型
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                df = pd.read_csv(
                    file_path,
                    sep=None,        # 自动检测分隔符
                    engine="python", # sep=None 需要 python engine
                    header=None,     # 不把第一行当表头
                    skiprows=self.skip_lines,
                    encoding=encoding,
                )
                return df.values.tolist()
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法读取文件: {file_path}")

    def _load_excel_file(self, file_path: str) -> list[list]:
        df = pd.read_excel(
            file_path,
            header=None,
            skiprows=self.skip_lines,
        )
        return df.values.tolist()


# ============================================================================
# DataProcessor - 数据处理类
# ============================================================================
class DataProcessor:
    """负责提取列、合并数据、数据转换"""

    def __init__(self, data_collection: list[tuple[str, list[list]]], column_config: list[tuple[str, int]]):
        self.data_collection = data_collection
        self.column_config = column_config  # [(name, col_index_1based), ...]

    def extract_columns(self) -> list[list]:
        """提取指定列的数据，返回二维list (类似MATLAB cell array)"""
        num_files = len(self.data_collection)
        num_cols = len(self.column_config)

        # 计算最大行数
        max_rows = max(len(d[1]) for d in self.data_collection) if self.data_collection else 0

        # 每个文件占 (num_cols + 1) 列：文件名列 + num_cols个数据列
        total_cols = (num_cols + 1) * num_files
        # +1 行用于表头
        result = [[None] * total_cols for _ in range(max_rows + 1)]

        col_idx = 0
        for i in range(num_files):
            filename = self.data_collection[i][0]
            data = self.data_collection[i][1]
            data_rows = len(data)

            # 第一列：文件名
            result[0][col_idx] = filename #type: ignore

            # 后续列：提取配置的列
            for j in range(num_cols):
                col_name = self.column_config[j][0]
                col_num = self.column_config[j][1]  # 1-based

                # 列标题
                result[0][col_idx + j + 1] = col_name  # type: ignore


                # 提取数据
                if col_num - 1 < (len(data[0]) if data else 0):
                    for row in range(data_rows):
                        if col_num - 1 < len(data[row]):
                            result[row + 1][col_idx + j + 1] = data[row][col_num - 1]

            col_idx += num_cols + 1

        return result

    def export_to_csv(self, output_path: str, data_set: list[list]):
        """导出到CSV文件"""
        with open(output_path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            for row in data_set:
                writer.writerow(row)

    def get_column_data(self, data_set: list[list], column_name: str) -> np.ndarray:
        """获取指定列名的数据（用于绘图），返回 (max_rows, num_files) 的矩阵"""
        num_files = len(self.data_collection)
        num_data_cols = len(self.column_config)
        max_rows = len(data_set) - 1  # 减去表头

        col_data = np.zeros((max_rows, num_files))

        col_idx = 0
        for i in range(num_files):
            # 查找匹配的列
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


# ============================================================================
# DataPlotter - 数据可视化类
# ============================================================================
class DataPlotter:
    """负责绘制图表、保存图片"""

    def __init__(self, output_folder: str, x_log: bool = False, y_log: bool = False):
        self.output_folder = output_folder
        self.x_log = x_log
        self.y_log = y_log

    def plot_single(self, x_data: np.ndarray, y_data: np.ndarray,
                    title_text: str, x_label: str, y_label: str, filename: str):
        """绘制单个文件的图表"""
        # 移除零值（用于对数坐标）
        valid_idx = (x_data != 0) & (y_data != 0)
        x_plot = x_data[valid_idx]
        y_plot = y_data[valid_idx]

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

        if self.x_log:
            ax.set_xscale("log")
        if self.y_log:
            ax.set_yscale("log")

        ax.set_xlim(self._get_axis_limits(x_plot))
        ax.set_ylim(self._get_axis_limits(y_plot))

        ax.set_xlabel(x_label, fontsize=16, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=16, fontweight="bold")

        save_path = os.path.join(self.output_folder, f"{filename}.png")
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    def plot_overlay(self, x_data_matrix: np.ndarray, y_data_matrix: np.ndarray,
                     filenames: list[str], x_label: str, y_label: str):
        """绘制所有文件的叠加图"""
        num_files = x_data_matrix.shape[1]

        fig, ax = plt.subplots()
        for i in range(num_files):
            x_data = x_data_matrix[:, i]
            y_data = y_data_matrix[:, i]

            valid_idx = (x_data != 0) & (y_data != 0)
            x_plot = x_data[valid_idx]
            y_plot = y_data[valid_idx]

            if len(x_plot) > 0:
                ax.plot(x_plot, y_plot, linewidth=3)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for spine in ax.spines.values():
            spine.set_linewidth(3)
        ax.tick_params(width=3, labelsize=16)

        if self.x_log:
            ax.set_xscale("log")
        if self.y_log:
            ax.set_yscale("log")

        all_x = x_data_matrix[x_data_matrix != 0]
        all_y = y_data_matrix[y_data_matrix != 0]
        if len(all_x) > 0:
            ax.set_xlim(self._get_axis_limits(all_x))
        if len(all_y) > 0:
            ax.set_ylim(self._get_axis_limits(all_y))

        ax.set_xlabel(x_label, fontsize=16, fontweight="bold")
        ax.set_ylabel(y_label, fontsize=16, fontweight="bold")

        save_path = os.path.join(self.output_folder, "total.png")
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

    # ---- private ----

    @staticmethod
    def _get_axis_limits(data: np.ndarray) -> tuple[float, float]:
        min_val = float(np.min(data))
        max_val = float(np.max(data))

        upper = max_val * 0.95 if max_val < 0 else max_val * 1.1
        lower = min_val * 1.1 if min_val < 0 else min_val * 0.95

        return (lower, upper)


# ============================================================================
# UIController - 用户界面控制类
# ============================================================================
class UIController:
    """处理所有用户交互、显示对话框"""

    @staticmethod
    def select_folder() -> str:
        root = tk.Tk()
        root.withdraw()
        folder_path = filedialog.askdirectory(title="选择数据文件夹")
        root.destroy()
        if not folder_path:
            raise RuntimeError("未选择文件夹")
        return folder_path

    @staticmethod
    def ask_skip_lines() -> int:
        result = {"skip_lines": 0}

        win = tk.Tk()
        win.title("跳过行设置")
        win.geometry("450x220")
        win.resizable(False, False)

        tk.Label(win, text="是否需要跳过文件前N行?", font=("Arial", 16)).pack(pady=15)

        do_skip = tk.BooleanVar(value=False)
        frame_radio = tk.Frame(win)
        frame_radio.pack()
        tk.Radiobutton(frame_radio, text="否", variable=do_skip, value=False,
                        font=("Arial", 12), command=lambda: toggle()).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_radio, text="是", variable=do_skip, value=True,
                        font=("Arial", 12), command=lambda: toggle()).pack(side=tk.LEFT, padx=10)

        frame_lines = tk.Frame(win)
        frame_lines.pack(pady=10)
        lbl = tk.Label(frame_lines, text="跳过行数:", font=("Arial", 12), state=tk.DISABLED)
        lbl.pack(side=tk.LEFT)
        lines_var = tk.IntVar(value=1)
        entry = tk.Entry(frame_lines, textvariable=lines_var, width=8, state=tk.DISABLED)
        entry.pack(side=tk.LEFT, padx=5)

        def toggle():
            state = tk.NORMAL if do_skip.get() else tk.DISABLED
            lbl.config(state=state)
            entry.config(state=state)

        def confirm():
            if do_skip.get():
                result["skip_lines"] = lines_var.get()
            win.destroy()

        tk.Button(win, text="确认", font=("Arial", 12), width=10, command=confirm).pack(pady=10)
        win.mainloop()
        return result["skip_lines"]

    @staticmethod
    def get_file_config() -> tuple[str, list[tuple[str, int]]]:
        result = {"file_type": "*.csv", "column_config": []}

        win = tk.Tk()
        win.title("文件配置")
        win.geometry("600x700")
        win.resizable(False, False)

        tk.Label(win, text="请输入文件类型与数据格式", font=("Arial", 18)).pack(pady=10)

        # 文件类型和列数
        top_frame = tk.Frame(win)
        top_frame.pack(fill=tk.X, padx=20, pady=5)

        tk.Label(top_frame, text="数据列数:", font=("Arial", 12)).pack(side=tk.LEFT)
        col_num_var = tk.IntVar(value=1)
        col_num_entry = tk.Entry(top_frame, textvariable=col_num_var, width=5)
        col_num_entry.pack(side=tk.LEFT, padx=5)

        tk.Label(top_frame, text="文件类型:", font=("Arial", 12)).pack(side=tk.LEFT, padx=(20, 0))
        filetype_var = tk.StringVar(value="*.csv")
        filetype_combo = ttk.Combobox(top_frame, textvariable=filetype_var,
                                       values=["*.csv", "*.txt", "*.xlsx"], width=8, state="readonly")
        filetype_combo.pack(side=tk.LEFT, padx=5)

        # 列配置区域 (可滚动)
        canvas_frame = tk.Frame(win)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        canvas = tk.Canvas(canvas_frame)
        scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        col_widgets = []  # [(name_entry, num_entry), ...]

        def update_columns(*_):
            # 清除旧控件
            for w in scroll_frame.winfo_children():
                w.destroy()
            col_widgets.clear()

            try:
                n = max(1, min(30, col_num_var.get()))
            except (tk.TclError, ValueError):
                n = 1

            # 表头
            header = tk.Frame(scroll_frame)
            header.pack(fill=tk.X, pady=2)
            tk.Label(header, text="数据类型", font=("Arial", 11, "bold"), width=20).pack(side=tk.LEFT)
            tk.Label(header, text="列号", font=("Arial", 11, "bold"), width=10).pack(side=tk.LEFT)

            for i in range(n):
                row_frame = tk.Frame(scroll_frame)
                row_frame.pack(fill=tk.X, pady=2)
                name_entry = tk.Entry(row_frame, width=22)
                name_entry.pack(side=tk.LEFT, padx=5)
                num_entry = tk.Entry(row_frame, width=10)
                num_entry.pack(side=tk.LEFT, padx=5)
                col_widgets.append((name_entry, num_entry))

        col_num_entry.bind("<Return>", update_columns)
        # 也用按钮触发更新
        tk.Button(top_frame, text="更新列", command=update_columns).pack(side=tk.LEFT, padx=5)

        update_columns()

        # 底部按钮
        btn_frame = tk.Frame(win)
        btn_frame.pack(pady=10)

        def save_config():
            config = {
                "file_type": filetype_var.get(),
                "columns": []
            }
            for name_e, num_e in col_widgets:
                try:
                    col_no = int(num_e.get())
                except ValueError:
                    col_no = 0
                config["columns"].append({"name": name_e.get(), "col": col_no})

            path = filedialog.asksaveasfilename(
                title="保存配置文件", defaultextension=".json",
                filetypes=[("JSON文件", "*.json")], initialfile="column_config.json"
            )
            if path:
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(config, fh, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", "配置已保存！")

        def load_config():
            path = filedialog.askopenfilename(
                title="加载配置文件", filetypes=[("JSON文件", "*.json")]
            )
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    config = json.load(fh)
                filetype_var.set(config["file_type"])
                col_num_var.set(len(config["columns"]))
                update_columns()
                for i, col_info in enumerate(config["columns"]):
                    if i < len(col_widgets):
                        col_widgets[i][0].insert(0, col_info["name"])
                        col_widgets[i][1].insert(0, str(col_info["col"]))
                messagebox.showinfo("成功", "配置已加载！")
            except Exception:
                messagebox.showerror("错误", "配置文件加载失败！")

        def confirm_config():
            result["file_type"] = filetype_var.get()
            cols = []
            col_numbers = []
            for name_e, num_e in col_widgets:
                name = name_e.get().strip()
                try:
                    col_no = int(num_e.get())
                except ValueError:
                    col_no = 0
                cols.append((name, col_no))
                col_numbers.append(col_no)

            # 检查重复列号
            if len(set(col_numbers)) != len(col_numbers):
                messagebox.showerror("错误", "存在重复的列号，请检查！")
                return

            result["column_config"] = cols
            win.destroy()

        tk.Button(btn_frame, text="保存配置", command=save_config, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="加载配置", command=load_config, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="确认", command=confirm_config, width=10).pack(side=tk.LEFT, padx=5)

        win.mainloop()
        return result["file_type"], result["column_config"]

    @staticmethod
    def ask_plot_config(column_names: list[str]) -> tuple[bool, str, str, bool, bool]:
        result = {"should_plot": False, "x_col": "", "y_col": "", "x_log": False, "y_log": False}

        win = tk.Tk()
        win.title("绘图设置")
        win.geometry("500x320")
        win.resizable(False, False)

        tk.Label(win, text="是否绘制图像", font=("Arial", 20)).pack(pady=15)

        do_plot = tk.BooleanVar(value=False)
        frame_radio = tk.Frame(win)
        frame_radio.pack()
        tk.Radiobutton(frame_radio, text="否", variable=do_plot, value=False,
                        font=("Arial", 12), command=lambda: toggle()).pack(side=tk.LEFT, padx=10)
        tk.Radiobutton(frame_radio, text="是", variable=do_plot, value=True,
                        font=("Arial", 12), command=lambda: toggle()).pack(side=tk.LEFT, padx=10)

        # X轴
        frame_x = tk.Frame(win)
        frame_x.pack(pady=8)
        tk.Label(frame_x, text="X轴:", font=("Arial", 14)).pack(side=tk.LEFT)
        x_var = tk.StringVar(value=column_names[0] if column_names else "")
        x_combo = ttk.Combobox(frame_x, textvariable=x_var, values=column_names, width=15, state=tk.DISABLED)
        x_combo.pack(side=tk.LEFT, padx=5)
        x_log_var = tk.BooleanVar(value=False)
        x_log_cb = tk.Checkbutton(frame_x, text="X对数", variable=x_log_var, state=tk.DISABLED)
        x_log_cb.pack(side=tk.LEFT, padx=10)

        # Y轴
        frame_y = tk.Frame(win)
        frame_y.pack(pady=8)
        tk.Label(frame_y, text="Y轴:", font=("Arial", 14)).pack(side=tk.LEFT)
        y_var = tk.StringVar(value=column_names[0] if column_names else "")
        y_combo = ttk.Combobox(frame_y, textvariable=y_var, values=column_names, width=15, state=tk.DISABLED)
        y_combo.pack(side=tk.LEFT, padx=5)
        y_log_var = tk.BooleanVar(value=False)
        y_log_cb = tk.Checkbutton(frame_y, text="Y对数", variable=y_log_var, state=tk.DISABLED)
        y_log_cb.pack(side=tk.LEFT, padx=10)

        def toggle():
            state = "readonly" if do_plot.get() else tk.DISABLED
            cb_state = tk.NORMAL if do_plot.get() else tk.DISABLED
            x_combo.config(state=state)
            y_combo.config(state=state)
            x_log_cb.config(state=cb_state)
            y_log_cb.config(state=cb_state)

        def confirm():
            if do_plot.get():
                result["should_plot"] = True
                result["x_col"] = x_var.get()
                result["y_col"] = y_var.get()
                result["x_log"] = x_log_var.get()
                result["y_log"] = y_log_var.get()
            win.destroy()

        tk.Button(win, text="确认", font=("Arial", 12), width=10, command=confirm).pack(pady=15)
        win.mainloop()

        return result["should_plot"], result["x_col"], result["y_col"], result["x_log"], result["y_log"]


# ============================================================================
# 主程序
# ============================================================================
def main():
    # 1. 选择文件夹
    folder_path = UIController.select_folder()

    # 2. 询问是否跳过行
    skip_lines = UIController.ask_skip_lines()

    # 3. 获取文件类型和列配置
    file_type, column_config = UIController.get_file_config()

    # 4. 创建DataLoader并读取数据
    loader = DataLoader(folder_path, file_type, skip_lines)
    data_collection = loader.load_all_files()

    if not data_collection:
        messagebox.showwarning("提示", "未找到符合条件的文件")
        return

    # 5. 创建DataProcessor并提取列
    processor = DataProcessor(data_collection, column_config)
    data_set = processor.extract_columns()

    # 6. 导出数据到CSV
    output_file = os.path.join(folder_path, "data_Set.csv")
    processor.export_to_csv(output_file, data_set)
    print(f"数据已导出到: {output_file}")

    # 7. 询问是否绘图
    column_names = [c[0] for c in column_config]
    should_plot, x_col, y_col, x_log, y_log = UIController.ask_plot_config(column_names)

    # 8. 绘图
    if should_plot:
        plotter = DataPlotter(folder_path, x_log, y_log)

        x_data_matrix = processor.get_column_data(data_set, x_col)
        y_data_matrix = processor.get_column_data(data_set, y_col)

        file_list = loader.get_file_list()
        num_files = len(file_list)

        for i in range(num_files):
            x_data = x_data_matrix[:, i]
            y_data = y_data_matrix[:, i]
            filename_no_ext = Path(file_list[i]).stem
            plotter.plot_single(x_data, y_data, file_list[i], x_col, y_col, filename_no_ext)

        plotter.plot_overlay(x_data_matrix, y_data_matrix, file_list, x_col, y_col)
        print("图表已保存")

    print("处理完成！")


if __name__ == "__main__":
    main()
