"""Shared appearance for the desktop window and the theme preview."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QDir
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QFrame, QLabel


THEME_DIR = Path(__file__).resolve().parent
FONT_DIR = THEME_DIR / "fonts"


def user_inter_fonts():
    local_app_data = os.environ.get("LOCALAPPDATA")
    if sys.platform == "win32" and local_app_data:
        user_fonts = Path(local_app_data) / "Microsoft" / "Windows" / "Fonts"
        yield from user_fonts.glob("Inter-VariableFont*.ttf")


def configure_fonts(app):
    source_han = FONT_DIR / "SourceHanSansCN-VF.otf"
    if source_han.is_file():
        QFontDatabase.addApplicationFont(str(source_han))

    for font_file in user_inter_fonts():
        QFontDatabase.addApplicationFont(str(font_file))

    font = app.font()
    available = set(QFontDatabase.families())
    latin_candidates = ["SF Pro", "SF Pro Text", "SF Pro Display", "San Francisco"]
    if sys.platform != "darwin":
        latin_candidates.extend(["Inter", "Segoe UI", "Arial"])
    latin = next((name for name in latin_candidates if name in available), font.family())
    chinese_candidates = [
        "Source Han Sans SC", "Source Han Sans CN", "Source Han Sans CN VF",
        "Source Han Sans SC VF", "思源黑体", "Noto Sans SC", "Noto Sans CJK SC",
    ]
    chinese = next((name for name in chinese_candidates if name in available), None)
    font.setFamilies([latin, chinese] if chinese else [latin])
    app.setFont(font)
    return latin


def apply_theme(window):
    QDir.setSearchPaths("plotlibtheme", [str(THEME_DIR)])
    window.setStyleSheet((THEME_DIR / "plotlib.qss").read_text(encoding="utf-8"))


def make_panel(name):
    panel = QFrame()
    panel.setObjectName(name)
    return panel


def make_label(text, role):
    label = QLabel(text)
    label.setProperty("role", role)
    if role in ("display", "value"):
        font = label.font()
        # The reference tracks the 64 px title at -0.03 em and the 12 px label at 0.12 em.
        tracking = -0.03 * 64 if role == "display" else 0.12 * 12
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
        label.setFont(font)
    return label
