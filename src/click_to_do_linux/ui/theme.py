"""Sleek Windows 11 Acrylic / Obsidian dark theme.

Only the shell of the floating overlay is styled here. Every interactive
control inside it is a Fluent widget and keeps the stylesheet shipped by the
library, so this file must not try to repaint them.
"""

GLASS_STYLE = """
QWidget#OverlayRoot {
    background-color: transparent;
    font-family: "Inter", "Noto Sans", system-ui, sans-serif;
}

/* Floating search bar (plain frame, no acrylic behind it) */
QFrame#SearchBar {
    background-color: rgba(20, 20, 24, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
}

/* The action bar paints its own acrylic, the frame stays transparent */
QFrame#ActionBar {
    background-color: transparent;
    border: none;
}

/* Divider line inside pill bar */
QFrame#PillDivider {
    background-color: rgba(255, 255, 255, 0.12);
    max-width: 1px;
    min-width: 1px;
    margin: 4px 2px;
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


# The AI panel carries its own rules, a parent stylesheet does not reach the
# text browser inside a translucent top level widget.
AI_DIALOG_STYLE = """
QFrame#AiDialog {
    background-color: transparent;
    border: none;
}

QTextBrowser#AiTextOutput {
    background-color: rgba(10, 10, 14, 0.90);
    color: #e4e4e7;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
}
"""
