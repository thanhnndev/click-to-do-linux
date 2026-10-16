"""Rich, minimalist Windows 11 Click to Do Context Pill Bar with inline Ask AI."""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ..i18n import t
from ..config import load_config
from .palette import theme_color
from .icons import get_icon


class ActionBar(QFrame):
    action_triggered = pyqtSignal(str, object)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.theme = load_config().ui_theme
        self.setObjectName("ActionBar")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(6, 5, 6, 5)
        self.main_layout.setSpacing(5)

        self.row_layout = QHBoxLayout()
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(4)
        self.main_layout.addLayout(self.row_layout)

        # Inline Ask AI input bar (hidden until user clicks 'Ask')
        self.ask_row = QWidget(self)
        ask_layout = QHBoxLayout(self.ask_row)
        ask_layout.setContentsMargins(2, 2, 2, 2)
        ask_layout.setSpacing(4)
        self.ask_input = QLineEdit(self.ask_row)
        self.ask_input.setObjectName("QuickInput")
        self.ask_input.setPlaceholderText(t("ask_placeholder"))
        self.ask_input.setMinimumWidth(240)
        self.ask_input.returnPressed.connect(self._submit_custom_ask)
        ask_layout.addWidget(self.ask_input)

        send_btn = QToolButton(self.ask_row)
        send_btn.setIcon(get_icon("send", theme_color("#38bdf8", self.theme), 14))
        send_btn.setIconSize(QSize(14, 14))
        send_btn.clicked.connect(self._submit_custom_ask)
        ask_layout.addWidget(send_btn)
        self.ask_row.hide()
        self.main_layout.addWidget(self.ask_row)

        self._current_text = ""

    def clear_actions(self):
        self.ask_row.hide()
        self.ask_input.clear()
        while self.row_layout.count():
            item = self.row_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_divider(self):
        div = QFrame(self)
        div.setObjectName("PillDivider")
        self.row_layout.addWidget(div)

    def _make_btn(self, text: str, icon_name: str, obj_name: str = "", icon_color: str = "#e4e4e7") -> QToolButton:
        btn = QToolButton(self)
        btn.setText(f" {text}" if text else "")
        btn.setIcon(get_icon(icon_name, color=theme_color(icon_color, self.theme), size=14))
        btn.setIconSize(QSize(14, 14))
        btn.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon if text else Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        if obj_name:
            btn.setObjectName(obj_name)
        return btn

    def show_for_text(self, text: str, urls: list[str] = None, emails: list[str] = None):
        self.clear_actions()
        self._current_text = text

        # 1. Copy
        copy_btn = self._make_btn(t("copy"), "copy", "PrimaryAction", "#ffffff")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_text", text))
        self.row_layout.addWidget(copy_btn)

        # 2. Direct Translate (1-click most used action)
        trans_btn = self._make_btn(t("translate"), "translate", "AiAction", "#38bdf8")
        trans_btn.clicked.connect(lambda: self.action_triggered.emit("ai_translate", text))
        self.row_layout.addWidget(trans_btn)

        # 3. Direct Explain / Summarize
        exp_btn = self._make_btn(t("explain"), "sparkles")
        exp_btn.clicked.connect(lambda: self.action_triggered.emit("ai_explain", text))
        self.row_layout.addWidget(exp_btn)

        # 4. Ask AI custom prompt
        ask_btn = self._make_btn(t("ask"), "send")
        ask_btn.clicked.connect(self._toggle_ask_input)
        self.row_layout.addWidget(ask_btn)

        self._add_divider()

        # 5. Smart Entity Actions (URL / Mail / Search)
        if urls:
            url_btn = self._make_btn(t("open_link"), "link")
            url_btn.clicked.connect(lambda: self.action_triggered.emit("open_url", urls[0]))
            self.row_layout.addWidget(url_btn)

        if emails:
            email_btn = self._make_btn(t("email"), "mail")
            email_btn.clicked.connect(lambda: self.action_triggered.emit("open_email", emails[0]))
            self.row_layout.addWidget(email_btn)

        search_btn = self._make_btn(t("search"), "search")
        search_btn.clicked.connect(lambda: self.action_triggered.emit("search_web", text))
        self.row_layout.addWidget(search_btn)

        # 6. More AI Menu
        more_btn = QToolButton(self)
        more_btn.setText("▾")
        ai_menu = QMenu(self)
        ai_menu.addAction(t("summarize"), lambda: self.action_triggered.emit("ai_summarize", text))
        ai_menu.addAction(t("rewrite"), lambda: self.action_triggered.emit("ai_rewrite", text))
        more_btn.setMenu(ai_menu)
        more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.row_layout.addWidget(more_btn)

        self.adjustSize()
        self.show()
        self.raise_()

    def _toggle_ask_input(self):
        if self.ask_row.isVisible():
            self.ask_row.hide()
        else:
            self.ask_row.show()
            self.ask_input.setFocus()
        self.adjustSize()

    def _submit_custom_ask(self):
        q = self.ask_input.text().strip()
        if q and self._current_text:
            self.action_triggered.emit("ai_custom", (self._current_text, q))

    def show_for_image(self, crop_image, text_inside: str = ""):
        self.clear_actions()

        copy_btn = self._make_btn(t("copy_image"), "copy", "PrimaryAction", "#ffffff")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_image", crop_image))
        self.row_layout.addWidget(copy_btn)

        if text_inside:
            text_btn = self._make_btn(t("copy_region_text"), "text", "PrimaryAction", "#ffffff")
            text_btn.clicked.connect(lambda: self.action_triggered.emit("copy_text", text_inside))
            self.row_layout.addWidget(text_btn)

        rmbg_btn = self._make_btn(t("cutout"), "cutout", "AiAction", "#38bdf8")
        rmbg_btn.clicked.connect(lambda: self._emit_async(rmbg_btn, t("cutting"), "remove_bg", crop_image))
        self.row_layout.addWidget(rmbg_btn)

        blur_btn = self._make_btn(t("blur_bg"), "blur")
        blur_btn.clicked.connect(lambda: self._emit_async(blur_btn, t("blurring"), "blur_bg", crop_image))
        self.row_layout.addWidget(blur_btn)

        redact_btn = self._make_btn(t("redact"), "redact")
        redact_btn.clicked.connect(lambda: self.action_triggered.emit("redact_region", crop_image))
        self.row_layout.addWidget(redact_btn)

        self._add_divider()

        save_btn = self._make_btn(t("save"), "save")
        save_btn.clicked.connect(lambda: self.action_triggered.emit("save_image", crop_image))
        self.row_layout.addWidget(save_btn)

        self.adjustSize()
        self.show()
        self.raise_()

    def _emit_async(self, btn: QToolButton, busy_label: str, action: str, payload):
        btn.setText(f" {busy_label}")
        btn.setEnabled(False)
        self.adjustSize()
        self.action_triggered.emit(action, payload)

    def show_for_qr(self, qr_text: str, is_url: bool):
        self.clear_actions()
        if is_url:
            open_btn = self._make_btn(t("open_link"), "link", "PrimaryAction", "#ffffff")
            open_btn.clicked.connect(lambda: self.action_triggered.emit("open_url", qr_text))
            self.row_layout.addWidget(open_btn)

        copy_btn = self._make_btn(t("copy_qr"), "copy")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_text", qr_text))
        self.row_layout.addWidget(copy_btn)

        self.adjustSize()
        self.show()
        self.raise_()

    def reposition(self, anchor_rect: tuple[int, int, int, int], screen_w: int, screen_h: int):
        rx, ry, rw, rh = anchor_rect
        bar_w = self.width() or 320
        bar_h = self.height() or 40

        x = rx + (rw - bar_w) // 2
        x = max(10, min(screen_w - bar_w - 10, x))

        y = ry + rh + 8
        if y + bar_h > screen_h - 12:
            y = ry - bar_h - 8
        y = max(10, min(screen_h - bar_h - 10, y))

        self.move(int(x), int(y))
