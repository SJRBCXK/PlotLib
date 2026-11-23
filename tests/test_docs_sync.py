"""
测试对象：docs/api/sync_api.py（API 文档的自动同步，构建前由 docs/api/conf.py 调用）

- 版本号从 pyproject.toml 读，conf.py 用它设 release 和网页标题；
- plotlib.__all__ 里没写进 reference.rst 的名字自动登记：放进同一模块的对象所在的分节（导出的对象优先），
  没有同模块分节的放进末尾的「其他」节；已登记的不动。
"""
import runpy

from docs.api import sync_api

REFERENCE_TEXT = sync_api.REFERENCE.read_text(encoding='utf-8')


def test_reference_is_in_sync():
    """当前的 reference.rst 已登记 plotlib.__all__ 的全部名字：同步不改任何东西（漏登记时这条先失败）。"""
    text, added = sync_api.sync_reference(REFERENCE_TEXT)
    assert added == []
    assert text == REFERENCE_TEXT


def test_new_name_goes_to_section_of_same_module():
    """
    漏登记的名字放进同一模块的对象所在分节的末尾。plot_spec 里既有样式对象（导出）又有 DrawnFigure（未导出，在「绘图」节），
    导出的同模块对象优先，所以新的样式对象进「样式对象」节，不进「绘图」节。
    """
    text = REFERENCE_TEXT.replace('   LineStyle\n', '')
    synced, added = sync_api.sync_reference(text)
    assert added == ['LineStyle']
    assert '   TickStyle\n   LineStyle\n' in synced
    assert synced.count('   LineStyle\n') == 1

    text = REFERENCE_TEXT.replace('   make_lines_formatter\n', '')
    synced, _ = sync_api.sync_reference(text)
    assert '   combine_formatters\n   make_lines_formatter\n' in synced


def test_name_without_section_goes_to_other():
    """没有同模块分节的名字放进末尾的「其他」节：没有就新建，有了就接着放；再同步一次不再改动。"""
    synced, added = sync_api.sync_reference(REFERENCE_TEXT, names=['color_positions'])
    assert added == ['color_positions']
    body = REFERENCE_TEXT.rstrip('\n')
    assert synced.startswith(body)
    tail = synced[len(body):]
    assert '\n其他\n----\n' in tail and '.. autosummary::' in tail
    assert synced.endswith('   color_positions\n')

    again, added_again = sync_api.sync_reference(synced, names=['color_positions'])
    assert (again, added_again) == (synced, [])

    # 「其他」节里已有别的对象时，接着放进去，不再新建一节
    existing = synced.replace('   color_positions\n', '   html_export.figure_size\n')
    reused, _ = sync_api.sync_reference(existing, names=['color_positions'])
    assert reused.count('\n其他\n') == 1
    assert reused.endswith('   html_export.figure_size\n   color_positions\n')


def test_version_from_pyproject(tmp_path):
    """版本号从 pyproject.toml 读；conf.py 的 release 和标题跟着它走，改版本只改 pyproject 一处。"""
    pyproject = tmp_path / 'pyproject.toml'
    pyproject.write_text('[project]\nname = "x"\nversion = "1.2.3"\n', encoding='utf-8')
    assert sync_api.read_version(pyproject) == '1.2.3'

    conf = runpy.run_path(str(sync_api.REFERENCE.parent / 'conf.py'))
    release = sync_api.read_version()
    assert conf['release'] == release
    assert conf['version'] == '.'.join(release.split('.')[:2])
    assert conf['html_title'] == f"PlotLib {conf['version']} 文档"
