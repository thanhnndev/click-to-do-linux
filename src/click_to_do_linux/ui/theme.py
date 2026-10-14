"""Modern Fluent / Glassmorphism theme styles for Click to Do Linux."""

GLASS_STYLE = """
/* Main Overlay Canvas */
QWidget#OverlayRoot {
    background-color: transparent;
}

/* Floating Action Bar Pill */
QFrame#ActionBar {
    background-color: rgba(24, 25, 30, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 14px;
}

/* Action Buttons */
QToolButton {
    background-color: transparent;
    color: #f0f0f4;
    border: none;
    border-radius: 8px;
    padding: 6px 12px;
    font-size: 13px;
    font-weight: 500;
}

QToolButton:hover {
    background-color: rgba(255, 255, 255, 0.12);
    color: #ffffff;
}

QToolButton:pressed {
    background-color: rgba(255, 255, 255, 0.20);
}

/* Primary Highlight Button */
QToolButton#PrimaryAction {
    background-color: #0078d4;
    color: #ffffff;
}

QToolButton#PrimaryAction:hover {
    background-color: #1084d8;
}

/* AI Action Submenu Button */
QToolButton#AiAction {
    background-color: rgba(147, 51, 234, 0.25);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #e9d5ff;
}

QToolButton#AiAction:hover {
    background-color: rgba(147, 51, 234, 0.45);
    color: #ffffff;
}

/* Top Hardware Badge */
QLabel#HardwareBadge {
    background-color: rgba(15, 20, 25, 0.88);
    color: #38bdf8;
    border: 1px solid rgba(56, 189, 248, 0.35);
    border-radius: 12px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

/* Hint Label */
QLabel#HintLabel {
    background-color: rgba(15, 20, 25, 0.75);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
}

/* AI Response Modal */
QFrame#AiDialog {
    background-color: rgba(20, 22, 28, 0.98);
    border: 1px solid rgba(168, 85, 247, 0.5);
    border-radius: 16px;
}

QTextBrowser#AiTextOutput {
    background-color: rgba(12, 14, 18, 0.7);
    color: #f1f5f9;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 12px;
    font-size: 13px;
    line-height: 1.5;
}

/* Menus */
QMenu {
    background-color: rgba(28, 30, 36, 0.98);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
    padding: 4px;
    color: #f1f5f9;
}

QMenu::item {
    padding: 6px 20px 6px 10px;
    border-radius: 6px;
}

QMenu::item:selected {
    background-color: rgba(255, 255, 255, 0.12);
}
"""
