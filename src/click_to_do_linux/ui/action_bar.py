"""Floating Pill Action Bar for Click to Do Linux."""

from typing import Callable, Optional
from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMenu,
    QToolButton,
    QWidget,
)


class ActionBar(QFrame):
    """Contextual floating pill toolbar offering actions for text, images, or QR codes."""

    # Signals
    action_triggered = pyqtSignal(str, object)  # action_name, payload

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("ActionBar")
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(8, 6, 8, 6)
        self.layout.setSpacing(6)

        self.current_mode = None
        self.current_data = None

    def clear_actions(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def show_for_text(self, text: str, urls: list[str] = None, emails: list[str] = None):
        """Builds action pill for text selection."""
        self.clear_actions()
        self.current_mode = "text"
        self.current_data = text

        # 1. Copy button
        copy_btn = QToolButton(self)
        copy_btn.setText("📋 Sao chép")
        copy_btn.setObjectName("PrimaryAction")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_text", text))
        self.layout.addWidget(copy_btn)

        # 2. Open URL button (if text has URL)
        if urls:
            url_btn = QToolButton(self)
            url_btn.setText("🌐 Mở liên kết")
            url_btn.clicked.connect(lambda: self.action_triggered.emit("open_url", urls[0]))
            self.layout.addWidget(url_btn)

        # 3. Email button (if email)
        if emails:
            email_btn = QToolButton(self)
            email_btn.setText("✉️ Gửi Email")
            email_btn.clicked.connect(lambda: self.action_triggered.emit("open_email", emails[0]))
            self.layout.addWidget(email_btn)

        # 4. Search Web button
        search_btn = QToolButton(self)
        search_btn.setText("🔍 Tìm kiếm")
        search_btn.clicked.connect(lambda: self.action_triggered.emit("search_web", text))
        self.layout.addWidget(search_btn)

        # 5. AI Assistant Dropdown Menu
        ai_btn = QToolButton(self)
        ai_btn.setText("🤖 Trợ lý AI ▾")
        ai_btn.setObjectName("AiAction")
        
        ai_menu = QMenu(self)
        
        act_sum = ai_menu.addAction("📝 Tóm tắt nội dung")
        act_sum.triggered.connect(lambda: self.action_triggered.emit("ai_summarize", text))

        act_exp = ai_menu.addAction("💡 Giải thích nội dung / mã")
        act_exp.triggered.connect(lambda: self.action_triggered.emit("ai_explain", text))

        act_trans = ai_menu.addAction("🌐 Dịch sang Tiếng Việt")
        act_trans.triggered.connect(lambda: self.action_triggered.emit("ai_translate", text))

        act_rew = ai_menu.addAction("✨ Viết lại & trau chuốt câu")
        act_rew.triggered.connect(lambda: self.action_triggered.emit("ai_rewrite", text))

        ai_btn.setMenu(ai_menu)
        ai_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.layout.addWidget(ai_btn)

        self.adjustSize()
        self.show()

    def show_for_image(self, crop_image):
        """Builds action pill for image / crop selection."""
        self.clear_actions()
        self.current_mode = "image"
        self.current_data = crop_image

        # 1. Copy Image
        copy_btn = QToolButton(self)
        copy_btn.setText("📋 Sao chép ảnh")
        copy_btn.setObjectName("PrimaryAction")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_image", crop_image))
        self.layout.addWidget(copy_btn)

        # 2. Cutout / Remove Background (Signature Windows 11 Copilot+ feature)
        rmbg_btn = QToolButton(self)
        rmbg_btn.setText("✂️ Tách nền (NPU/AI)")
        rmbg_btn.setObjectName("AiAction")
        rmbg_btn.clicked.connect(lambda: self.action_triggered.emit("remove_bg", crop_image))
        self.layout.addWidget(rmbg_btn)

        # 3. Blur Background
        blur_btn = QToolButton(self)
        blur_btn.setText("🌫️ Làm mờ nền")
        blur_btn.clicked.connect(lambda: self.action_triggered.emit("blur_bg", crop_image))
        self.layout.addWidget(blur_btn)

        # 4. Visual Search (Google Lens)
        lens_btn = QToolButton(self)
        lens_btn.setText("🔍 Tìm ảnh")
        lens_btn.clicked.connect(lambda: self.action_triggered.emit("visual_search", crop_image))
        self.layout.addWidget(lens_btn)

        # 5. Save to File
        save_btn = QToolButton(self)
        save_btn.setText("💾 Lưu file")
        save_btn.clicked.connect(lambda: self.action_triggered.emit("save_image", crop_image))
        self.layout.addWidget(save_btn)

        self.adjustSize()
        self.show()

    def show_for_qr(self, qr_text: str, is_url: bool):
        """Builds action pill for detected QR Code."""
        self.clear_actions()
        self.current_mode = "qr"
        self.current_data = qr_text

        if is_url:
            open_btn = QToolButton(self)
            open_btn.setText("🌐 Mở liên kết QR")
            open_btn.setObjectName("PrimaryAction")
            open_btn.clicked.connect(lambda: self.action_triggered.emit("open_url", qr_text))
            self.layout.addWidget(open_btn)

        copy_btn = QToolButton(self)
        copy_btn.setText("📋 Sao chép nội dung QR")
        copy_btn.clicked.connect(lambda: self.action_triggered.emit("copy_text", qr_text))
        self.layout.addWidget(copy_btn)

        self.adjustSize()
        self.show()

    def reposition(self, anchor_rect: tuple[int, int, int, int], screen_w: int, screen_h: int):
        """Positions the floating action bar relative to anchor rectangle."""
        rx, ry, rw, rh = anchor_rect
        bar_w = self.width() or 300
        bar_h = self.height() or 45

        # Place horizontally centered with anchor rect
        x = rx + (rw - bar_w) // 2
        x = max(10, min(screen_w - bar_w - 10, x))

        # Try placing directly below anchor rect
        y = ry + rh + 12
        if y + bar_h > screen_h - 10:
            # Place directly above anchor rect
            y = ry - bar_h - 12
        y = max(10, min(screen_h - bar_h - 10, y))

        self.move(int(x), int(y))
