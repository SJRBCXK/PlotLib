"""
Sphinx 配置：从 src/plotlib 的文档字符串（numpydoc 格式）生成 API 文档。

构建（在项目根目录）::

    pip install -e ".[docs,interactive]"
    sphinx-build -b html docs/api docs/api/_build/html

生成的网页在 docs/api/_build/html/index.html。
"""
import sys
from pathlib import Path

# 直接从源码导入，不要求先安装
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

project = 'PlotLib'
author = 'PlotLib'
release = '1.0.0'
language = 'zh_CN'

extensions = [
    'sphinx.ext.autodoc',        # 从文档字符串生成说明
    'sphinx.ext.autosummary',    # 汇总表，每个对象一页
    'sphinx.ext.napoleon',       # 解析 numpydoc 格式（Parameters / Returns / Notes ...）
    'sphinx.ext.viewcode',       # 每页附「源码」链接
]

# ── autodoc / autosummary ─────────────────────────────────────
autosummary_generate = True                 # 自动生成每个对象的页面（generated/ 目录）
autoclass_content = 'both'                  # 类页面同时显示类说明和 __init__ 的参数说明
autodoc_member_order = 'bysource'           # 成员按源码顺序排列
autodoc_typehints = 'none'                  # 类型已写在 Parameters 里，签名不再重复显示
autodoc_default_options = {
    'members': True,
    'show-inheritance': False,
}

# ── napoleon（numpydoc 格式）──────────────────────────────────
napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_rtype = False                  # Returns 节里的类型和说明写在一起
napoleon_preprocess_types = True            # 类型里的 {'a', 'b'} 取值当字面量显示，类型名生成链接
napoleon_attr_annotations = True

# 文档字符串里用单反引号 `name` 引用对象（numpydoc 惯例），找得到就生成链接
default_role = 'py:obj'

# ── HTML ──────────────────────────────────────────────────────
html_theme = 'pydata_sphinx_theme'          # numpy、pandas 使用的主题
html_title = 'PlotLib 1.0 文档'
html_theme_options = {
    'navigation_with_keys': False,
    'show_toc_level': 2,
}
templates_path = ['_templates']
exclude_patterns = ['_build']
