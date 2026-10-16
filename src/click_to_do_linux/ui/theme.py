"""Sleek Windows 11 Acrylic / Obsidian dark theme."""

GLASS_STYLE = """
QWidget#OverlayRoot {
    background-color: transparent;
    font-family: "Inter", "Noto Sans", system-ui, sans-serif;
}

/* Floating Pill Toolbar */
QFrame#ActionBar, QFrame#SearchBar {
    background-color: rgba(20, 20, 24, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
}

QLineEdit#QuickInput {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    padding: 4px 10px;
    color: #f4f4f5;
    font-size: 12px;
}

QLineEdit#QuickInput:focus {
    border: 1px solid rgba(56, 189, 248, 0.55);
    background-color: rgba(255, 255, 255, 0.09);
}

QToolButton {
    background-color: transparent;
    color: #e4e4e7;
    border: none;
    border-radius: 6px;
    padding: 5px 9px;
    font-size: 12px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: rgba(255, 255, 255, 0.10);
    color: #ffffff;
}

QToolButton:pressed {
    background-color: rgba(255, 255, 255, 0.16);
}

QToolButton#PrimaryAction {
    background-color: rgba(255, 255, 255, 0.14);
    color: #ffffff;
    font-weight: 600;
}

QToolButton#PrimaryAction:hover {
    background-color: rgba(255, 255, 255, 0.22);
}

QToolButton#AiAction {
    color: #38bdf8;
    background-color: rgba(56, 189, 248, 0.10);
}

QToolButton#AiAction:hover {
    background-color: rgba(56, 189, 248, 0.20);
    color: #7dd3fc;
}

/* Divider line inside pill bar */
QFrame#PillDivider {
    background-color: rgba(255, 255, 255, 0.12);
    max-width: 1px;
    min-width: 1px;
    margin: 4px 2px;
}

/* AI Output Panel */
QFrame#AiDialog {
    background-color: rgba(18, 18, 22, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 12px;
}

QTextBrowser#AiTextOutput {
    background-color: rgba(10, 10, 14, 0.90);
    color: #e4e4e7;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
}

/* Dropdown Menu */
QMenu {
    background-color: rgba(22, 22, 27, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 8px;
    padding: 4px;
    color: #e4e4e7;
    font-size: 12px;
}

QMenu::item {
    padding: 6px 18px 6px 10px;
    border-radius: 5px;
}

QMenu::item:selected {
    background-color: rgba(255, 255, 255, 0.12);
    color: #ffffff;
}
"""


def overlay_style(theme: str, source: str = GLASS_STYLE) -> str:
    """Theme floating screen tools while keeping the captured pixels untouched."""
    if theme != "light":
        return source
    import re
    from .palette import theme_colors

    result = theme_colors(source, theme)
    result = re.sub(r"rgba\(255,\s*255,\s*255,\s*([0-9.]+)\)", r"rgba(15, 23, 42, \1)", result)
    for original, replacement in {
        "rgba(20, 20, 24, 0.96)": "rgba(255, 255, 255, 0.98)",
        "rgba(18, 18, 22, 0.98)": "rgba(255, 255, 255, 0.98)",
        "rgba(10, 10, 14, 0.90)": "rgba(248, 250, 252, 0.98)",
        "rgba(22, 22, 27, 0.98)": "rgba(255, 255, 255, 0.98)",
    }.items():
        result = result.replace(original, replacement)
    return result
