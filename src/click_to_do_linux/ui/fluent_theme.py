"""Keeps the qfluentwidgets theme in sync with the application palette.

Fluent controls ship their own stylesheet, so the shell palette cannot be
layered on top of them with QSS. Instead the app theme and brand accent are
pushed into the library, which makes every Fluent control follow the same
light/dark mode and the same accent colour as the surrounding shell.
"""

from __future__ import annotations

from PyQt6.QtGui import QFont
from qfluentwidgets import Theme, setFontFamilies, setTheme, setThemeColor

from .palette import accent

# The app type stack, shared by the shell and by every Fluent control.
FONT_FAMILIES = ["Inter", "Noto Sans", "DejaVu Sans", "sans-serif"]
BASE_FONT_SIZE = 13


def apply_app_font(app) -> None:
    """Set the shell font on the application, Fluent widgets keep their own scale."""
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPixelSize(BASE_FONT_SIZE)
    app.setFont(font)


def sync_fluent_theme(theme: str) -> None:
    """Apply the app theme and brand accent to every Fluent control."""
    mode = "light" if theme == "light" else "dark"
    setFontFamilies(FONT_FAMILIES)
    setTheme(Theme.LIGHT if mode == "light" else Theme.DARK)
    setThemeColor(accent(mode))
