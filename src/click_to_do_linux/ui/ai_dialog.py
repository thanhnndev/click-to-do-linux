"""Clean, minimal AI Streaming Panel without emojis."""

from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ..utils.clipboard import ClipboardManager
from ..i18n import t
from .icons import get_icon
from ..config import load_config
from .palette import theme_color
from .theme import overlay_style


class StreamWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, generator_func):
        super().__init__()
        self.generator_func = generator_func

    def run(self):
        try:
            for chunk in self.generator_func():
                self.chunk_received.emit(chunk)
            self.finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))


class AIDialog(QFrame):
    def __init__(self, title: str, generator_func, parent: QWidget = None):
        super().__init__(parent)
        self.theme = load_config().ui_theme
        self.setObjectName("AiDialog")
        self.setFixedSize(500, 320)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)

        header = QHBoxLayout()
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(overlay_style(self.theme, "color: #f4f4f5; font-weight: 600; font-size: 13px;"))
        header.addWidget(self.title_label)
        header.addStretch()

        self.status_label = QLabel(t("generating"))
        self.status_label.setStyleSheet(overlay_style(self.theme, "color: #a1a1aa; font-size: 12px;"))
        header.addWidget(self.status_label)

        self.close_btn = QToolButton()
        self.close_btn.setIcon(get_icon("close", theme_color("#a1a1aa", self.theme), 14))
        self.close_btn.setIconSize(QSize(14, 14))
        self.close_btn.clicked.connect(self.hide)
        header.addWidget(self.close_btn)
        self.layout.addLayout(header)

        self.text_browser = QTextBrowser()
        self.text_browser.setObjectName("AiTextOutput")
        self.layout.addWidget(self.text_browser)

        footer = QHBoxLayout()
        self.copy_btn = QPushButton(" " + t("copy"))
        self.copy_btn.setIcon(get_icon("copy", theme_color("#ffffff", self.theme), 13))
        self.copy_btn.setStyleSheet(overlay_style(self.theme, """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.12);
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.20); }
        """))
        self.copy_btn.clicked.connect(self._copy_result)
        footer.addWidget(self.copy_btn)
        footer.addStretch()
        self.layout.addLayout(footer)

        self.worker = StreamWorker(generator_func)
        self.worker.chunk_received.connect(self._on_chunk)
        self.worker.finished.connect(self._on_finished)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.start()

    def _on_chunk(self, chunk: str):
        self.text_browser.moveCursor(self.text_browser.textCursor().MoveOperation.End)
        self.text_browser.insertPlainText(chunk)
        self.text_browser.moveCursor(self.text_browser.textCursor().MoveOperation.End)

    def _on_finished(self):
        self.status_label.setText(t("done"))

    def _on_error(self, err: str):
        self.status_label.setText(t("error"))
        self.text_browser.insertPlainText(f"\n[Error: {err}]")

    def _copy_result(self):
        text = self.text_browser.toPlainText()
        if text:
            ClipboardManager.copy_text(text)
            self.copy_btn.setText(" " + t("copied"))
            self.copy_btn.setIcon(get_icon("check", "#4ade80", 13))
