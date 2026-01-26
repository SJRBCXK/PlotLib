"""
绘图格式化器工厂模块

提供常用的 axes_formatter 回调函数工厂，用于 DataPlotter 的定制化绘图。

使用方式:
    # 1. 创建格式化器
    axes_fmt = make_axes_formatter(
        xlim_left=0, xlim_right=10,
        custom_formation=[
            lambda ax: ax.set_title("My Plot"),
            lambda ax: ax.grid(True)
        ]
    )

    lines_fmt = make_lines_formatter(
        linewidth=2,
        linecolor='red',
        custom_formations=[
            lambda line: line.set_alpha(0.7)
        ]
    )

    legend_fmt = make_legend_formatter(
        legend_fontsize=12,
        custom_formations=[
            lambda legend: legend.set_shadow(True)
        ]
    )

    # 2. 应用到 Plotter
    plotter.plot_lines(
        axes_formatter=axes_fmt,
        lines_formatter=lines_fmt,
        legend_formatter=legend_fmt
    )

注意事项:
    - lines_formatter 接收的是 lines 列表参数
    - legend_formatter 接收的是 legends 列表参数
    - custom_formation/custom_formations 中的函数会自动接收 ax/line/legend 参数
"""

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogFormatter, LogLocator, MultipleLocator
import numpy as np


class AxesFormatterFactory:
    """坐标格式化器工厂类"""

    @staticmethod
    def create(
               xlim_left = None,
               xlim_right = None,
               ylim_bottom = None,
               ylim_top = None,
               xscale_type='linear',
               yscale_type='linear',
               xscaler=1.0,
               yscaler=1.0, 
               x_format='{x:.2f}', 
               y_format='{y:.2f}',
               hide_spines=True,
               custom_formation = []
               ):
        """
        创建坐标格式化器

        参数:
            xlim_left: X轴左边界
            ylim_bottom: Y轴下边界
            x_format: X轴数字格式（使用占位符 {x}）
            y_format: Y轴数字格式（使用占位符 {y}）
            hide_spines: 是否隐藏上/右边框

        返回:
            formatter函数，用作axes_formatter回调
        """
        def formatter(ax, fig, *_args, **_kwargs):
            _ = _args, _kwargs  # 标记为有意未使用

            # X轴：格式化
            ax.set_xscale(xscale_type)
            if xscale_type == 'log':
                ax.xaxis.set_major_locator(LogLocator(base=10))
            if xlim_left is not None:
                ax.set_xlim(left=xlim_left)
            if xlim_right is not None:
                ax.set_xlim(right=xlim_right)
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: x_format.format(x=x*xscaler)))
            ax.xaxis.set_tick_params(which='both', width=3, direction='out')

            # Y轴：格式化
            ax.set_yscale(yscale_type)
            if yscale_type == 'log':
                ax.yaxis.set_major_locator(LogLocator(base=10))
            if ylim_bottom is not None:
                ax.set_ylim(bottom=ylim_bottom)
            if ylim_top is not None:
                ax.set_ylim(top=ylim_top)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: y_format.format(y=y*yscaler)))
            ax.tick_params(axis='y', which='both', width=3, direction='out')

            # 隐藏上/右边框
            if hide_spines:
                ax.spines['right'].set_visible(False)
                ax.spines['top'].set_visible(False)

            # 执行自定义回调
            if custom_formation:
                for func in custom_formation:
                    func(ax, fig)

        return formatter


class LinesFormatterFactory:
    """线条格式化器工厂类"""

    @staticmethod
    def create(
                linewidth = 3,
                linecolor = 'blue',
                linestyle = '-',
                linemarker = None,
                linemarkersize = 6,
                custom_formations = [],
                *args,
                **kwargs    
                ):
        """
        创建线性坐标格式化器

        参数:
            xlim: X轴范围 (left, right) 或 None
            ylim: Y轴范围 (bottom, top) 或 None
            yscale: Y轴缩放因子
            x_format: X轴数字格式
            y_format: Y轴数字格式
            grid: 是否显示网格
            hide_spines: 是否隐藏上/右边框

        返回:
            formatter函数，用作axes_formatter回调
        """
        def formatter(lines, *_args, **_kwargs):
            _ = _args, _kwargs

            # 设置坐标轴范围

            # 格式化坐标轴
            for line in lines:
                line.set_linewidth(linewidth)
                line.set_color(linecolor)
                line.set_linestyle(linestyle)
                line.set_marker(linemarker)
                if linemarker is not None:
                    line.set_markersize(linemarkersize)
                if custom_formations:
                    for func in custom_formations:
                        func(line)

        return formatter


class LegendsFormatterFactory:
    """图例格式化器工厂类"""

    @staticmethod
    def create(
                legend_location='best',
                legend_fontsize=12,
                legend_frameon=False,
                legend_draggable=True,
                custom_formations = [],
                *args,
                **kwargs
                ):
        """
        创建高度自定义的格式化器

        参数 (所有参数都是可选的):
            - xscale: 'linear', 'log', 'symlog', 'logit'
            - yscale: 'linear', 'log', 'symlog', 'logit'
            - xlim: (left, right)
            - ylim: (bottom, top)
            - xlabel: X轴标签
            - ylabel: Y轴标签
            - title: 图表标题
            - grid: True/False
            - grid_alpha: 网格透明度
            - hide_spines: ['top', 'right', 'left', 'bottom'] 列表
            - tick_width: 刻度线宽度
            - tick_direction: 'in', 'out', 'inout'

        返回:
            formatter函数
        """
        def formatter(legends, *_args, **_kwargs):
            _ = _args, _kwargs

            for legend in legends:
                legend.set_fontsize(legend_fontsize)
                legend.set_frameon(legend_frameon)
                legend.set_draggable(legend_draggable)
                legend.set_loc(legend_location)
                
                if custom_formations:
                    for func in custom_formations:
                        func(legend)



        return formatter
    


# 便捷函数（简化常用场景的调用）
def make_axes_formatter(**kwargs):
    """便捷函数：创建ax格式化器"""
    return AxesFormatterFactory.create(**kwargs)


def make_lines_formatter(**kwargs):
    """便捷函数：创建线性格式化器"""
    return LinesFormatterFactory.create(**kwargs)


def make_legend_formatter(**kwargs):
    """便捷函数：创建自定义格式化器"""
    return LegendsFormatterFactory.create(**kwargs)