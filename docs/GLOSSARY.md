# 词汇表

> 定于 2026-11-16（`STRUCTURE_REVIEW.md` 步骤 1），步骤 2 已按此改名。新写的代码、注释、文档都按这里的说法。

## 三个词

| 词 | 含义 | 代码名字（括号内为步骤 2 之前的旧名） |
|---|---|---|
| **样品**（sample） | 一个来源的一次测量，对应 DataSet 里连续的若干列 | `sample_idx`（`groups_idx`、`Column.group_idx`）；`num_samples`（`num_datagroups`）；`select('samples', […])`（`select('group', …)`，现在只认这一个写法）；`iter('samples')`（`iter('groups')`）；`DataTransformer` 的 `new_sample`（`New_group`） |
| **通道**（channel） | 样品里的第几列，如 Freq、Zs'、Voltage | `channel_idx`（`group_local_idx`）；`iter('channels')`；取数函数 `plot_common.get_xy_data(dataset, sample_idx, channel_x, channel_y)`；绘图参数 `plotdataRowNum_x` / `_y` 实际也是通道号（暂不改名） |
| **分组**（group） | 按分析需要挑出若干样品、起一个名字组成的集合 | 不变：`data_groups` 字典、`Group` 类、`group_plotter`、`merge_groups` |

DataSet 可以看成一张「样品 × 通道」的表，行是样品，列是通道：

```text
              通道0(Freq)  通道1(Zs')  通道2(Zs'')
样品0 (S0)       列0          列1          列2
样品1 (S1)       列3          列4          列5
样品2 (S2)       列6          列7          列8
```

- 同一通道在所有样品里列标题相同（`_channel_units_unify_check` 保证）；但各样品的通道数可以不同，例如 `DataTransformer` 生成的结果样品常常只有 1 列。
- 一个样品可以同时属于多个分组（合并模式下只画一次，用第一个包含它的分组的样式）。
- `Group.apply` 中每个分组的计算结果，在结果 DataSet 里成为**一个新样品**。
- **分组计算**（`Group.apply`）：先用分组把参与计算的样品挑好，再对**每个分组内部**的几个样品做计算（如 `slices[1] / slices[0]`），每组得到一个结果样品。
  它不是「组和组之间」的计算（如批次 1 的平均减批次 2 的平均），那种计算目前没有。文档里统一叫「分组计算」，不叫「组间计算」。

## 容易混的地方

- **`DataSet.local_idx` 不是通道号**，是列在整张表里的位置（0 ~ 总列数−1）。
- **样品号 ≠ 样品名。** 代码按样品号（整数）查找；`names` 里的 `'S2'` 只是给人看的标签，可以重复，也可以是 `Results_0_of_S0_S1` 这类自动生成的名字。
- **`names` 存的是样品名，`units` 存的是列标题**（物理量加单位，如 `"Zs'(ohm)"`）。这两个名字与含义不符，但出现太多，这一轮不改。
- 分组里样品的**书写顺序**是否重要，取决于分组的用途。

## 两个例子

| 脚本 | 分组 | 含义 |
|---|---|---|
| `scripts/eis_bode.py` | `'1st': [0, 1]` … `'9th': [16, 17]` | **有顺序的配对**。同一份配置既用来画图，又交给 `Group.apply(rev_camp)` 计算 `slices[1] / slices[0]`，写成 `[1, 0]` 就得到倒数，顺序就是角色 |
| `scripts/piezo.py` | `'1st': [0, 1, 2]`，`'2nd': [7, 8, 9]` | **无顺序的批次**。只用于分组绘图，顺序只影响合并模式的组首色 |

分组没有固定规律，按当次的分析需要来编。
