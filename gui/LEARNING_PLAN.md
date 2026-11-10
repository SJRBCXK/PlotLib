# PySide6 GUI 学习路线图

背景：有 MATLAB GUIDE/App Designer 经验（拖控件 + 写回调）。Qt 的思路一致——
控件树 + 事件回调——区别是布局靠布局管理器自动排版（不是像素拖拽），
回调机制叫「信号与槽」。

最终目标：做一个能加载数据、画图、交互调整的桌面工具，服务于 PlotLib 项目。

节奏：由学习者自己掌控，想学哪一步就说「开始 Step N」，每一步给出可独立
运行、带详细中文注释的示例代码。

## 进度

- [x] Step 1 — 最小窗口（`step1_hello.py`）
- [ ] Step 2 — 布局与基础控件
- [ ] Step 3 — 信号与槽（事件响应）
- [ ] Step 4 — 把 matplotlib 画布嵌入 Qt
- [ ] Step 5 — 文件对话框与数据加载
- [ ] Step 6 — 菜单栏、工具栏、状态栏
- [ ] Step 7 — 多窗口/对话框与应用状态管理
- [ ] Step 8（可选）— 打包与分发

## 各步骤内容

### Step 1 — 最小窗口
`QApplication` + `QMainWindow` + 事件循环。理解一个 Qt 程序从创建到显示、
到进入事件循环的完整生命周期。

文件：`step1_hello.py`

### Step 2 — 布局与基础控件
`QVBoxLayout` / `QHBoxLayout` / `QGridLayout`，配合 `QPushButton`、
`QLabel`、`QLineEdit`、`QComboBox`。

对应 MATLAB 里"摆控件"，但这里用布局管理器自动排版，而不是像素定位——
窗口缩放时控件会自动重新排布。

### Step 3 — 信号与槽（事件响应）
`clicked.connect(...)` 等机制，让按钮点击、输入框内容变化真正触发代码
逻辑。这是 Qt 版的"回调函数"，和 MATLAB App Designer 的 callback 概念
一一对应。

### Step 4 — 把 matplotlib 画布嵌入 Qt
`FigureCanvasQTAgg`，让图表变成窗口里的一个控件，能随窗口缩放、能通过
按钮刷新。这是 PlotLib 项目真正要用到的核心技能。

### Step 5 — 文件对话框与数据加载
`QFileDialog` 打开数据文件，结合已有的 `scripts/eis_bode.py` 或
`tools/data_reorder_qt.py` 里的数据处理逻辑，做「选文件 → 处理 → 画图」
的完整链路。

### Step 6 — 菜单栏、工具栏、状态栏
用 `QMainWindow` 自带的骨架做一个更「正式」的应用外观。

### Step 7 — 多窗口/对话框与应用状态管理
弹窗、设置面板，以及如何在控件之间共享数据而不写一堆全局变量。

### Step 8（可选）— 打包与分发
用 `PyInstaller` 把脚本打包成 exe，方便分发给不装 Python 环境的人。
