"""
API 文档的自动同步。每次构建前由 conf.py 调用（本地和 GitHub Actions 都会），也可以单独运行::

    python docs/api/sync_api.py

- 版本号：`read_version` 从 pyproject.toml 读，conf.py 用它设 ``release`` 和网页标题，改版本只改 pyproject 一处；
- 登记新对象：``plotlib.__all__`` 里还没写进 reference.rst 的名字，自动加到同一模块的对象所在的分节末尾
  （同模块里优先找导出的对象，比如 plot_spec 的新样式对象进「样式对象」节而不是 DrawnFigure 所在的「绘图」节）；
  没有同模块分节的，放进末尾的「其他」节（没有就新建），之后可以手动挪到合适的位置。

只增不删：对象删掉了而 reference.rst 里还写着时，构建会报导入失败，按提示删掉那一行。
"""
import importlib
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path(__file__).resolve().parent / 'reference.rst'
PACKAGE = 'plotlib'
OTHER_TITLE = '其他'
_OTHER_SECTION = [
    OTHER_TITLE,
    '----',                     # 两个汉字占四个字符宽，下划线不能比标题短
    '',
    '以下对象由 ``docs/api/sync_api.py`` 自动登记，可以移到合适的分节。',
    '',
    '.. autosummary::',
    '   :toctree: generated',
    '   :nosignatures:',
    '',
]
_HEADING_UNDERLINE = re.compile(r'^([-=~^])\1+$')
_DIRECTIVE_TARGET = re.compile(r'^\.\. auto\w+::\s+(\S+)')
_INDENT = '   '


def read_version(pyproject: Path = ROOT / 'pyproject.toml') -> str:
    """读 pyproject.toml 里 ``[project]`` 的 ``version``。"""
    return tomllib.loads(Path(pyproject).read_text(encoding='utf-8'))['project']['version']


@dataclass
class _Block:
    """reference.rst 里的一个 autosummary 块。"""
    title: str | None                   # 所在分节的标题
    module: str                         # 块所在位置的 currentmodule，条目相对它写
    entries: list[tuple[int, str]] = field(default_factory=list)    # (行号, 条目)


def _parse(lines: list[str]) -> list[_Block]:
    """找出每个 autosummary 块：所在分节、相对的模块、条目及其行号。"""
    blocks: list[_Block] = []
    title, module = None, PACKAGE
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith('.. currentmodule::'):
            module = line.split('::', 1)[1].strip()
        elif line and not line[0].isspace() and i + 1 < len(lines) and _HEADING_UNDERLINE.match(lines[i + 1].rstrip()):
            title = line
        elif line == '.. autosummary::':
            block = _Block(title, module)
            i += 1
            # 选项行（:toctree: 等）和空行之后是条目，条目连续缩进，遇到空行或顶格的行结束
            while i < len(lines) and (lines[i].strip().startswith(':') or not lines[i].strip()):
                if not lines[i].strip() and block.entries:
                    break
                i += 1
            while i < len(lines) and lines[i].startswith(_INDENT) and lines[i].strip():
                block.entries.append((i, lines[i].strip()))
                i += 1
            blocks.append(block)
            continue
        i += 1
    return blocks


def _resolve(path: str) -> Any:
    """按点号路径取出对象：最长的能导入的前缀当模块，其余逐级取属性。"""
    parts = path.split('.')
    for cut in range(len(parts), 0, -1):
        try:
            obj = importlib.import_module('.'.join(parts[:cut]))
        except ImportError:
            continue
        for attr in parts[cut:]:
            obj = getattr(obj, attr)
        return obj
    raise ImportError(f"找不到 {path}")


def _registered(lines: list[str], blocks: list[_Block]) -> set[str]:
    """已经写进 reference.rst 的名字（autosummary 条目和 auto* 指令的目标，只看最后一段）。"""
    names = {entry.rsplit('.', 1)[-1] for block in blocks for _, entry in block.entries}
    names |= {m.group(1).rsplit('.', 1)[-1] for line in lines if (m := _DIRECTIVE_TARGET.match(line))}
    return names


def _target_block(blocks: list[_Block], module: str, exported: set[str]) -> _Block | None:
    """
    选一个块放新名字：块里有同模块的对象（导出的优先）；都没有就用「其他」节的块；还没有「其他」节返回 None。
    """
    best, best_score = None, 0
    for block in blocks:
        for _, entry in block.entries:
            if getattr(_resolve(f'{block.module}.{entry}'), '__module__', None) != module:
                continue
            score = 2 if entry in exported else 1
            if score > best_score:
                best, best_score = block, score
    if best is not None:
        return best
    return next((block for block in blocks if block.title == OTHER_TITLE), None)


def sync_reference(text: str, names: list[str] | None = None) -> tuple[str, list[str]]:
    """
    把还没登记的名字加进 reference.rst 的文本。

    Parameters
    ----------
    text : str
        reference.rst 的内容。
    names : list of str, optional
        要确认登记的名字（``plotlib`` 下的属性名）；默认是 ``plotlib.__all__``。

    Returns
    -------
    text : str
        同步后的内容；没有要加的就原样返回。
    added : list of str
        这次新登记的名字。
    """
    package = importlib.import_module(PACKAGE)
    exported = set(package.__all__)
    names = list(package.__all__) if names is None else names
    ends_with_newline = text.endswith('\n')
    lines = text.rstrip('\n').split('\n')
    added = []
    for name in names:
        blocks = _parse(lines)              # 每加一个重新解析：插入会挪动后面的行号
        if name in _registered(lines, blocks):
            continue
        module = getattr(package, name).__module__
        block = _target_block(blocks, module, exported)
        if block is None:
            lines += [''] + _OTHER_SECTION + [_INDENT + name]
        else:
            lines.insert(block.entries[-1][0] + 1, _INDENT + name)
        added.append(name)
    return '\n'.join(lines) + ('\n' if ends_with_newline else ''), added


def sync_reference_file(path: Path = REFERENCE) -> list[str]:
    """同步 reference.rst 文件：有新登记的才写回。返回新登记的名字。"""
    text = path.read_text(encoding='utf-8')
    synced, added = sync_reference(text)
    if added:
        path.write_text(synced, encoding='utf-8')
    return added


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT / 'src'))       # 没安装包也能导入 plotlib
    print(f"版本：{read_version()}")
    new = sync_reference_file()
    print(f"已登记到 reference.rst：{'、'.join(new)}" if new else "reference.rst 已是最新，无需登记")
