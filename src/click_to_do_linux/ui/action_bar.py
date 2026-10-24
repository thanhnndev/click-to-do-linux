"""Rich, minimalist Windows 11 Click to Do Context Pill Bar with inline Ask AI."""

from PyQt6.QtCore import QPoint, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    FluentIcon,
    CheckBox,
    LineEdit,
    PillPushButton,
    RoundMenu,
    TransparentToolButton,
)
from qfluentwidgets.components.material.acrylic_widget import AcrylicWidget
from ..ai.entities import merge_text_lines
from ..i18n import t
from ..config import load_config
from .palette import theme_color
from .icons import get_icon


class ActionBar(QFrame, AcrylicWidget):
    action_triggered = pyqtSignal(str, object)

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.theme = load_config().ui_theme
        self.setObjectName("ActionBar")
        self.acrylicBrush.blurRadius = 18
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
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
        self.ask_input = LineEdit(self.ask_row)
        self.ask_input.setObjectName("QuickInput")
        self.ask_input.setPlaceholderText(t("ask_placeholder"))
        self.ask_input.setMinimumWidth(240)
        self.ask_input.returnPressed.connect(self._submit_custom_ask)
        ask_layout.addWidget(self.ask_input)

        send_btn = TransparentToolButton(self.ask_row)
        send_btn.setIcon(get_icon("send", theme_color("#38bdf8", self.theme), 14))
        send_btn.setIconSize(QSize(14, 14))
        send_btn.clicked.connect(self._submit_custom_ask)
        ask_layout.addWidget(send_btn)
        self.ask_row.hide()
        self.main_layout.addWidget(self.ask_row)

        self._current_text = ""
        self._anchor = None
        self.copy_text_group = QWidget(self)
        copy_layout = QHBoxLayout(self.copy_text_group)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(4)
        self.copy_text_btn = self._make_btn(t("copy_region_text"), "copy", "PrimaryAction", "#ffffff")
        self.copy_text_btn.clicked.connect(
            lambda: self.action_triggered.emit("copy_text", self.text_for_copy(self._current_text))
        )
        copy_layout.addWidget(self.copy_text_btn)
        self.merge_lines = CheckBox(t("merge_paragraph"), self.copy_text_group)
        self.merge_lines.setToolTip(t("merge_paragraph_hint"))
        copy_layout.addWidget(self.merge_lines)
        self.merge_lines.hide()
        self.copy_text_group.hide()

    def acrylicClipPath(self):
        from PyQt6.QtCore import QRectF as _R
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        return path

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self._drawAcrylic(painter)
        super().paintEvent(e)

    def clear_actions(self):
        self._anchor = None
        self.setToolTip("")
        self._current_text = ""
        self.ask_row.hide()
        self.merge_lines.hide()
        self.ask_input.clear()
        while self.row_layout.count():
            item = self.row_layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                if w is not self.copy_text_group:
                    w.deleteLater()

    def _add_text_copy(self, text: str, label: str, *, region: bool):
        self._current_text = text
        self.copy_text_btn.setText(" " + label)
        self.copy_text_btn.show()
        self.merge_lines.setVisible(region)
        self.row_layout.addWidget(self.copy_text_group)

    def text_for_copy(self, text: str) -> str:
        return merge_text_lines(text) if not self.merge_lines.isHidden() and self.merge_lines.isChecked() else text

    def show_for_link(self, url: str):
        self.clear_actions()
        copy_btn = self._make_btn(t("copy_link"), "copy", "PrimaryAction", "#ffffff")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_text", url))
        self.row_layout.addWidget(copy_btn)
        open_btn = self._make_btn(t("open_link"), "link")
        open_btn.clicked.connect(lambda: self.action_triggered.emit("open_url", url))
        self.row_layout.addWidget(open_btn)
        self.setToolTip(url)
        self._show_bar()

    def _resize_to_contents(self):
        self.main_layout.invalidate()
        self.main_layout.activate()
        # The cached size hint is stale when a row was hidden before it was shown.
        self.resize(self.main_layout.sizeHint())
        if self._anchor is not None:
            self.reposition(*self._anchor)

    def _show_bar(self):
        # New children of an already visible toolbar start hidden. Show them
        # before measuring, so switching selection never uses an empty layout.
        for i in range(self.row_layout.count()):
            widget = self.row_layout.itemAt(i).widget()
            if widget:
                widget.show()
        self._resize_to_contents()
        self.show()
        self.raise_()

    def _add_divider(self):
        div = QFrame(self)
        div.setObjectName("PillDivider")
        self.row_layout.addWidget(div)

    def _make_btn(self, text: str, icon_name: str, obj_name: str = "", icon_color: str = "#e4e4e7") -> PillPushButton:
        btn = PillPushButton(self)
        btn.setCheckable(False)
        btn.setText(f" {text}" if text else "")
        btn.setIcon(get_icon(icon_name, color=theme_color(icon_color, self.theme), size=14))
        btn.setIconSize(QSize(14, 14))
        if obj_name:
            btn.setObjectName(obj_name)
        return btn

    def show_for_text(self, text: str, emails: list[str] = None, *, region: bool = False):
        self.clear_actions()
        # 1. Copy text and its formatting option share one group.
        self._add_text_copy(text, t("copy"), region=region)

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

        # 5. Mail / Search
        if emails:
            email_btn = self._make_btn(t("email"), "mail")
            email_btn.clicked.connect(lambda: self.action_triggered.emit("open_email", emails[0]))
            self.row_layout.addWidget(email_btn)

        search_btn = self._make_btn(t("search"), "search")
        search_btn.clicked.connect(lambda: self.action_triggered.emit("search_web", text))
        self.row_layout.addWidget(search_btn)

        # 6. More AI Menu
        more_btn = TransparentToolButton(self)
        more_btn.setIcon(FluentIcon.MORE)
        ai_menu = RoundMenu(parent=self)
        for label, action in ((t("summarize"), "ai_summarize"), (t("rewrite"), "ai_rewrite")):
            item = Action(label)
            item.triggered.connect(lambda _checked=False, act=action: self.action_triggered.emit(act, text))
            ai_menu.addAction(item)
        # The menu is shown manually, a native menu button would add a second
        # indicator arrow next to the Fluent "more" glyph.
        more_btn.clicked.connect(lambda: self._popup_menu(ai_menu, more_btn))
        self.row_layout.addWidget(more_btn)

        self._show_bar()

    @staticmethod
    def _popup_menu(menu: RoundMenu, button) -> None:
        origin = button.mapToGlobal(QPoint(button.width() // 2, button.height() + 4))
        menu.exec(origin)

    def _toggle_ask_input(self):
        if self.ask_row.isVisible():
            self.ask_row.hide()
        else:
            self.ask_row.show()
            self.ask_input.setFocus()
        self._resize_to_contents()

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
            self._add_text_copy(text_inside, t("copy_region_text"), region=True)

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

        self._show_bar()

    def show_for_result(self, result_image, source_image, task_name: str):
        """Toolbar for a processed result: copy / save / retry / other quick action / close."""
        self.clear_actions()

        copy_btn = self._make_btn(t("copy_image"), "copy", "PrimaryAction", "#ffffff")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_image", result_image))
        self.row_layout.addWidget(copy_btn)

        save_btn = self._make_btn(t("save"), "save")
        save_btn.clicked.connect(lambda: self.action_triggered.emit("save_image", result_image))
        self.row_layout.addWidget(save_btn)

        self._add_divider()

        retry_btn = self._make_btn(t("retry"), "refresh")
        retry_btn.clicked.connect(lambda: self._emit_async(retry_btn, t("cutting") if task_name == "remove_bg" else t("blurring"), task_name, source_image))
        self.row_layout.addWidget(retry_btn)

        if task_name == "remove_bg":
            other, label, icon, busy = "blur_bg", t("blur_bg"), "blur", t("blurring")
        else:
            other, label, icon, busy = "remove_bg", t("cutout"), "cutout", t("cutting")
        other_btn = self._make_btn(label, icon)
        other_btn.clicked.connect(lambda: self._emit_async(other_btn, busy, other, source_image))
        self.row_layout.addWidget(other_btn)

        self._add_divider()

        close_btn = self._make_btn(t("close_btn"), "close")
        close_btn.setToolTip(t("close_result"))
        close_btn.clicked.connect(lambda: self.action_triggered.emit("close", None))
        self.row_layout.addWidget(close_btn)

        self._show_bar()

    def _emit_async(self, btn: PillPushButton, busy_label: str, action: str, payload):
        btn.setText(f" {busy_label}")
        btn.setEnabled(False)
        self._resize_to_contents()
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

        self._show_bar()

    def reposition(self, anchor_rect: tuple[int, int, int, int], screen_w: int, screen_h: int):
        self._anchor = (anchor_rect, screen_w, screen_h)
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
