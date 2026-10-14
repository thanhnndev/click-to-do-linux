"""AI Response Dialog with asynchronous streaming output."""

from typing import Generator
from PyQt6.QtCore import QPoint, Qt, QThread, pyqtSignal
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
    """Floating dialog for displaying AI responses (Summarize, Explain, Translate)."""

    def __init__(self, title: str, generator_func, parent: QWidget = None):
        super().__init__(parent)
        self.setObjectName("AiDialog")
        self.setFixedSize(540, 360)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(16, 14, 16, 14)
        self.layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        self.title_label = QLabel(f"🤖 {title}")
        self.title_label.setStyleSheet("color: #c084fc; font-weight: 700; font-size: 14px;")
        header_layout.addWidget(self.title_label)

        header_layout.addStretch()

        self.status_label = QLabel("Đang xử lý...")
        self.status_label.setStyleSheet("color: #94a3b8; font-size: 11px;")
        header_layout.addWidget(self.status_label)

        self.close_btn = QToolButton()
        self.close_btn.setText("✕")
        self.close_btn.setStyleSheet("color: #94a3b8; font-size: 14px; padding: 2px 6px;")
        self.close_btn.clicked.connect(self.hide)
        header_layout.addWidget(self.close_btn)

        self.layout.addLayout(header_layout)

        # Text output area
        self.text_browser = QTextBrowser()
        self.text_browser.setObjectName("AiTextOutput")
        self.layout.addWidget(self.text_browser)

        # Footer
        footer_layout = QHBoxLayout()
        self.copy_btn = QPushButton("📋 Sao chép kết quả")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: white;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #6d28d9;
            }
        """)
        self.copy_btn.clicked.connect(self._copy_result)
        footer_layout.addWidget(self.copy_btn)

        footer_layout.addStretch()

        self.done_btn = QPushButton("Xong")
        self.done_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                color: white;
                border-radius: 8px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.18);
            }
        """)
        self.done_btn.clicked.connect(self.hide)
        footer_layout.addWidget(self.done_btn)

        self.layout.addLayout(footer_layout)

        # Start stream worker
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
        self.status_label.setText("Hoàn thành ✓")
        self.status_label.setStyleSheet("color: #4ade80; font-size: 11px;")

    def _on_error(self, err: str):
        self.status_label.setText("Lỗi")
        self.status_label.setStyleSheet("color: #f87171; font-size: 11px;")
        self.text_browser.insertPlainText(f"\n[Lỗi: {err}\nVui lòng kiểm tra lại dịch vụ Ollama.]")

    def _copy_result(self):
        text = self.text_browser.toPlainText()
        if text:
            ClipboardManager.copy_text(text)
            self.copy_btn.setText("✓ Đã sao chép")
