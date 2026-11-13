"""Tk reorder: direct position editing shares insertion semantics with dragging."""
import tkinter as tk

import pytest

from tools.data_reorder_app import DraggableList


@pytest.fixture
def view():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f'Tk display unavailable: {exc}')
    root.withdraw()
    widget = DraggableList(root)
    widget.pack()
    for i in range(5):
        widget.add_item(f'Group {i}', i)
    widget.items[1].set_checked(False)
    root.update()
    yield widget
    root.destroy()


def order(view):
    return [item.original_idx for item in view.items]


def test_number_edit_inserts_and_preserves_checks(view):
    item = view.items[0]
    item.edit_index()
    editor = item._index_editor
    editor.delete(0, tk.END)
    editor.insert(0, '4')
    editor.event_generate('<Return>')
    # Withdrawn windows do not route keyboard events; use the bound callback.
    if item._index_editor is not None:
        item._commit_index()
    assert order(view) == [1, 2, 3, 0, 4]
    assert [row.index_label.cget('text') for row in view.items] == ['1.', '2.', '3.', '4.', '5.']
    assert [row.original_idx for row in view.items if row.is_checked()] == [2, 3, 0, 4]
    assert item._index_editor is None
    view.move_item(item, 1)
    assert order(view) == list(range(5))


@pytest.mark.parametrize('value', ['0', '6', '-1', '', 'abc', '1.5'])
def test_invalid_number_does_not_move(view, value):
    item = view.items[0]
    item.edit_index()
    item._index_editor.delete(0, tk.END)
    item._index_editor.insert(0, value)
    item._commit_index()
    assert order(view) == list(range(5))
    assert item._index_editor is None


def test_cancel_and_focus_out(view):
    item = view.items[0]
    item.edit_index()
    item._index_editor.delete(0, tk.END)
    item._index_editor.insert(0, '5')
    item._cancel_index()
    assert order(view) == list(range(5))
    item.edit_index()
    item._index_editor.delete(0, tk.END)
    item._index_editor.insert(0, '5')
    item._index_editor.event_generate('<FocusOut>')
    assert order(view) == [1, 2, 3, 4, 0]
