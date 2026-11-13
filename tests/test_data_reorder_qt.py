"""Qt reorder interactions; runnable headlessly without experimental data."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

pytest.importorskip('PySide6')
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSpinBox

from tools.data_reorder_qt import CheckableListWidget, BorderDelegate


@pytest.fixture
def widget():
    app = QApplication.instance() or QApplication([])
    view = CheckableListWidget()
    view.resize(400, 300)
    for i in range(5):
        view.add_item(f'Group {i}', i, checked=i != 1)
    view.show()
    app.processEvents()
    yield view
    view.close()
    view.deleteLater()
    app.processEvents()


def test_insert_and_preserve_checks(widget):
    widget.move_item(0, 3)
    assert widget.get_all_indices() == [1, 2, 3, 0, 4]
    assert widget.get_checked_indices() == [2, 3, 0, 4]
    assert widget.get_checked_positions() == [1, 2, 3, 4]
    widget.move_item(3, 0)
    assert widget.get_all_indices() == list(range(5))
    widget.move_item(0, -1)
    widget.move_item(0, 5)
    assert widget.get_all_indices() == list(range(5))


def test_snap_at_midpoint(widget):
    widget._pressed_item = widget.item(0)
    center = widget.visualItemRect(widget.item(1)).center()
    widget._snap_to_position(center - QPoint(0, 1))
    assert widget.get_all_indices() == list(range(5))
    widget._snap_to_position(center + QPoint(0, 1))
    assert widget.get_all_indices() == [1, 0, 2, 3, 4]
    widget._snap_to_position(widget.visualItemRect(widget.item(4)).center() + QPoint(0, 1))
    assert widget.get_all_indices() == [1, 2, 3, 4, 0]
    widget._snap_to_position(widget.visualItemRect(widget.item(0)).center() - QPoint(0, 1))
    assert widget.get_all_indices() == list(range(5))


def test_edit_number(widget):
    pos = widget.visualItemRect(widget.item(0)).topLeft() + QPoint(20, 18)
    QTest.mouseDClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    QApplication.processEvents()
    editor = widget.findChild(QSpinBox)
    assert editor is not None
    assert (editor.minimum(), editor.maximum()) == (1, 5)
    editor.selectAll()
    QTest.keyClicks(editor, '4')
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert widget.get_all_indices() == [1, 2, 3, 0, 4]
    assert widget.get_checked_indices() == [2, 3, 0, 4]


def test_mouse_drag(widget):
    start = widget.visualItemRect(widget.item(0)).center()
    end = widget.visualItemRect(widget.item(3)).center() + QPoint(0, 2)
    QTest.mousePress(widget.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(widget.viewport(), end)
    QTest.mouseRelease(widget.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert widget.get_all_indices() == [1, 2, 3, 0, 4]
    assert not widget._scroll_timer.isActive()
