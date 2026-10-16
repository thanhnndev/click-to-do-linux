"""Shared high-contrast color themes for the application shell and settings."""

from __future__ import annotations

import re


LIGHT_REPLACEMENTS = {
    "#38bdf833": "#0369a133",
    "#38bdf8": "#0369a1",
    "#0ea5e9": "#075985",
    "#7dd3fc": "#075985",
    "#082f49": "#ffffff",
    "#123044": "#e0f2fe",
    "#155e75": "#0284c7",
    "#09090b": "#f8fafc",
    "#0c0c0f": "#ffffff",
    "#121215": "#ffffff",
    "#141418": "#ffffff",
    "#18181b": "#f1f5f9",
    "#27272a": "#cbd5e1",
    "#303036": "#cbd5e1",
    "#62626b": "#64748b",
    "#303037": "#cbd5e1",
    "#3f3f46": "#94a3b8",
    "#52525b": "#475569",
    "#71717a": "#475569",
    "#a1a1aa": "#334155",
    "#a5f3fc": "#075985",
    "#e4e4e7": "#1e293b",
    "#f4f4f5": "#0f172a",
    "#fafafa": "#0f172a",
    "#ffffff": "#0f172a",
    "#f87171": "#b91c1c",
    "#3f1d1d": "#fecaca",
    "#2a1212": "#fee2e2",
    "#fbbf24": "#a16207",
    "#4ade80": "#15803d",
}


LIGHT_OVERRIDES = """
QPushButton:hover { background-color: #e2e8f0; }
QPushButton#Primary:hover { background-color: #075985; border-color: #075985; color: #ffffff; }
QPushButton#Quiet:hover { background-color: #e2e8f0; color: #0f172a; }
QComboBox::drop-down { background-color: #e2e8f0; }
QComboBox QAbstractItemView { selection-background-color: #dbeafe; selection-color: #075985; }
QTabBar::tab:selected { color: #075985; border-bottom-color: #0369a1; }
QCheckBox::indicator:checked { background-color: #0369a1; border-color: #0369a1; }
QProgressBar::chunk { background-color: #0369a1; }
"""


def theme_stylesheet(stylesheet: str, theme: str) -> str:
    """Apply the selected palette to a stylesheet authored with the dark tokens."""
    result = stylesheet if theme != "light" else f"{theme_colors(stylesheet, theme)}\n{LIGHT_OVERRIDES}"
    from ..config import get_config_dir
    check = get_config_dir() / f"check-{theme}.svg"
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{primary_ink(theme)}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12 4 4L19 6"/></svg>'
    if not check.exists() or check.read_text(encoding="utf-8") != svg:
        check.write_text(svg, encoding="utf-8")
    return result + f'\nQCheckBox::indicator:checked {{ image: url("{check.as_posix()}"); }}'


def theme_color(color: str, theme: str) -> str:
    return LIGHT_REPLACEMENTS.get(color.lower(), color) if theme == "light" else color


def theme_colors(source: str, theme: str) -> str:
    if theme != "light":
        return source
    # One pass prevents a newly substituted white from being remapped as dark text.
    return re.sub(r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b", lambda match: theme_color(match.group(), theme), source)


def accent(theme: str) -> str:
    return "#0369a1" if theme == "light" else "#38bdf8"


def primary_ink(theme: str) -> str:
    return "#ffffff" if theme == "light" else "#082f49"


def apply_input_palette(widget, theme):
    """Qt placeholders use QPalette, rather than CSS pseudo-elements."""
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtWidgets import QLineEdit, QPlainTextEdit
    for control in widget.findChildren(QLineEdit) + widget.findChildren(QPlainTextEdit):
        palette = control.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#475569" if theme == "light" else "#a1a1aa"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        control.setPalette(palette)
