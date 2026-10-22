"""App typography mapped onto Fluent label components.

Every label of the shell is a Fluent label, so the type scale, the text colour
and the light/dark behaviour come from the library instead of hand written
CSS. Only the sizes that differ from the Fluent scale stay in the app
stylesheet.
"""

from __future__ import annotations

from PyQt6.QtGui import QColor
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    LargeTitleLabel,
    PixmapLabel,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)

# role: (fluent label class, light theme colour, dark theme colour)
ROLES: dict[str, tuple[type, str, str]] = {
    "display": (LargeTitleLabel, "#0f172a", "#fafafa"),
    "title": (TitleLabel, "#0f172a", "#fafafa"),
    "subtitle": (SubtitleLabel, "#0f172a", "#fafafa"),
    "heading": (StrongBodyLabel, "#1e293b", "#f4f4f5"),
    "brand": (StrongBodyLabel, "#0f172a", "#f4f4f5"),
    "body": (BodyLabel, "#1e293b", "#e4e4e7"),
    "caption": (CaptionLabel, "#475569", "#a1a1aa"),
    "muted": (CaptionLabel, "#475569", "#71717a"),
    "eyebrow": (CaptionLabel, "#0369a1", "#38bdf8"),
    "success": (CaptionLabel, "#15803d", "#4ade80"),
    "danger": (CaptionLabel, "#b91c1c", "#f87171"),
    "card_title": (StrongBodyLabel, "#334155", "#a1a1aa"),
}


def label(text: str = "", role: str = "body", parent=None):
    """Create a Fluent label using one of the app typography roles."""
    widget_class, light, dark = ROLES[role]
    widget = widget_class(text, parent)
    widget.setTextColor(QColor(light), QColor(dark))
    return widget
