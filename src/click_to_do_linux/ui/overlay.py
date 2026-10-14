"""Fullscreen Interactive Overlay Canvas for Click to Do Linux."""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
from PyQt6.QtCore import QPoint, QRect, Qt, QThread, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QWidget,
)

from ..ai.entities import EntityDetector, QREntity
from ..ai.llm import LLMService
from ..ai.ocr import OCREngine, TextBox
from ..ai.segmentation import SegmentationEngine
from ..capture.screen import CapturedScreen
from ..config import Config, load_config
from ..hardware import HardwareDetector, HardwareReport
from ..utils.clipboard import ClipboardManager
from .action_bar import ActionBar
from .ai_dialog import AIDialog
from .theme import GLASS_STYLE


class OCRWorker(QThread):
    finished = pyqtSignal(list)

    def __init__(self, image: Image.Image):
        super().__init__()
        self.image = image

    def run(self):
        try:
            boxes = OCREngine.get_instance().detect(self.image)
            self.finished.emit(boxes)
        except Exception as e:
            print(f"[OCRWorker] Error: {e}")
            self.finished.emit([])


class OverlayWindow(QWidget):
    """Main interactive screen overlay."""

    def __init__(self, captured: CapturedScreen):
        super().__init__()
        self.setObjectName("OverlayRoot")
        self.setStyleSheet(GLASS_STYLE)

        self.captured = captured
        self.config: Config = load_config()
        self.hw_report: HardwareReport = HardwareDetector.detect()

        self.ocr_boxes: List[TextBox] = []
        self.qr_entities: List[QREntity] = []

        # Selection state
        self.selection_start: Optional[QPoint] = None
        self.selection_end: Optional[QPoint] = None
        self.selected_rect: Optional[QRect] = None
        self.hovered_box: Optional[TextBox] = None
        self.selected_box: Optional[TextBox] = None
        self.is_dragging = False

        self._setup_window()
        self._init_widgets()
        self._detect_entities_and_ocr()

    def _setup_window(self):
        # Configure frameless fullscreen
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        # Cover entire screen
        screen_geo = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, self.captured.width, self.captured.height)

        # Hotkeys
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)
        QShortcut(QKeySequence("Ctrl+C"), self, self._handle_copy_shortcut)

    def _init_widgets(self):
        # Top-right Hardware Badge
        self.hw_badge = QLabel(self)
        self.hw_badge.setObjectName("HardwareBadge")
        self.hw_badge.setText(f"{self.hw_report.badge_text}  •  Click to Do")
        self.hw_badge.adjustSize()
        self.hw_badge.move(self.width() - self.hw_badge.width() - 24, 20)

        # Bottom Hint Label
        self.hint_label = QLabel(self)
        self.hint_label.setObjectName("HintLabel")
        self.hint_label.setText("💡 Kéo để chọn vùng • Bấm chữ để chọn • Esc để thoát")
        self.hint_label.adjustSize()
        self.hint_label.move((self.width() - self.hint_label.width()) // 2, self.height() - 48)

        # Floating Action Bar
        self.action_bar = ActionBar(self)
        self.action_bar.action_triggered.connect(self._on_action_triggered)
        self.action_bar.hide()

        # Active AI Dialog
        self.ai_dialog = None

    def _detect_entities_and_ocr(self):
        # 1. Fast QR Detection
        if self.config.auto_detect_qr:
            self.qr_entities = EntityDetector.detect_qr_codes(self.captured.image)

        # 2. Async OCR
        self.ocr_worker = OCRWorker(self.captured.image)
        self.ocr_worker.finished.connect(self._on_ocr_finished)
        self.ocr_worker.start()

    def _on_ocr_finished(self, boxes: List[TextBox]):
        self.ocr_boxes = boxes
        self.update()

    # --- Mouse & Drawing Events ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Draw captured screen
        painter.drawPixmap(0, 0, self.captured.pixmap)

        # 2. Draw subtle dark freeze backdrop
        painter.fillRect(self.rect(), QColor(0, 0, 0, 40))

        # 3. Draw OCR text highlights (subtle boxes)
        for box in self.ocr_boxes:
            bx, by, bw, bh = box.rect
            if box == self.hovered_box or box == self.selected_box:
                # Active/hovered glow
                painter.setPen(QPen(QColor(56, 189, 248, 220), 2))
                painter.setBrush(QBrush(QColor(56, 189, 248, 55)))
                painter.drawRoundedRect(bx - 2, by - 2, bw + 4, bh + 4, 4, 4)
            else:
                # Faint text presence indicator
                painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
                painter.setBrush(QBrush(QColor(255, 255, 255, 12)))
                painter.drawRoundedRect(bx, by, bw, bh, 3, 3)

        # 4. Draw QR Code boxes
        for qr in self.qr_entities:
            qx, qy, qw, qh = qr.rect
            painter.setPen(QPen(QColor(168, 85, 247, 240), 2))
            painter.setBrush(QBrush(QColor(168, 85, 247, 45)))
            painter.drawRoundedRect(qx, qy, qw, qh, 6, 6)

        # 5. Draw active selection rectangle
        if self.selected_rect and not self.selected_rect.isNull():
            rect = self.selected_rect.normalized()

            # Cutout original clear image in selection area (no dark tint)
            painter.drawPixmap(rect, self.captured.pixmap, rect)

            # Draw glowing selection border
            painter.setPen(QPen(QColor(56, 189, 248, 255), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 4, 4)

            # Draw dimensions label (e.g. 640 x 360)
            dim_text = f"{rect.width()} × {rect.height()}"
            painter.setFont(QFont("sans-serif", 10, QFont.Weight.Medium))
            painter.setPen(QPen(QColor(255, 255, 255, 220)))
            painter.drawText(rect.x() + 6, max(20, rect.y() - 6), dim_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            
            # Check if clicked on QR Code
            for qr in self.qr_entities:
                qx, qy, qw, qh = qr.rect
                if QRect(qx, qy, qw, qh).contains(pos):
                    self.action_bar.show_for_qr(qr.text, qr.is_url)
                    self.action_bar.reposition((qx, qy, qw, qh), self.width(), self.height())
                    return

            # Check if clicked directly on an OCR text box
            box = OCREngine.find_box_at(self.ocr_boxes, pos.x(), pos.y())
            if box:
                self.selected_box = box
                self.selected_rect = QRect(box.rect[0], box.rect[1], box.rect[2], box.rect[3])
                self._show_actions_for_text(box.text, box.rect)
                self.update()
                return

            # Start drag-to-select
            self.is_dragging = True
            self.selection_start = pos
            self.selection_end = pos
            self.selected_rect = QRect(pos, pos)
            self.selected_box = None
            self.action_bar.hide()
            self.update()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.is_dragging:
            self.selection_end = pos
            self.selected_rect = QRect(self.selection_start, self.selection_end).normalized()
            self.update()
        else:
            # Check hover over text boxes
            new_hover = OCREngine.find_box_at(self.ocr_boxes, pos.x(), pos.y())
            if new_hover != self.hovered_box:
                self.hovered_box = new_hover
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            if self.selected_rect and (self.selected_rect.width() > 10 and self.selected_rect.height() > 10):
                rect = self.selected_rect.normalized()
                r_tuple = (rect.x(), rect.y(), rect.width(), rect.height())

                # Check if there is text inside the selection
                text_inside = OCREngine.get_text_in_selection(
                    self.ocr_boxes, rect.x(), rect.y(), rect.width(), rect.height()
                )

                if text_inside and len(text_inside.strip()) > 3:
                    # Show Text actions
                    self._show_actions_for_text(text_inside, r_tuple)
                else:
                    # Show Image actions
                    crop_img = SegmentationEngine.crop_region(self.captured.image, r_tuple)
                    self.action_bar.show_for_image(crop_img)
                    self.action_bar.reposition(r_tuple, self.width(), self.height())
            self.update()

    def _show_actions_for_text(self, text: str, rect_tuple: Tuple[int, int, int, int]):
        urls = EntityDetector.extract_urls(text)
        emails = EntityDetector.extract_emails(text)
        self.action_bar.show_for_text(text, urls=urls, emails=emails)
        self.action_bar.reposition(rect_tuple, self.width(), self.height())

    def _handle_copy_shortcut(self):
        if self.selected_box:
            ClipboardManager.copy_text(self.selected_box.text)
            self.close()
        elif self.selected_rect and not self.selected_rect.isNull():
            rect = self.selected_rect.normalized()
            r_tuple = (rect.x(), rect.y(), rect.width(), rect.height())
            text = OCREngine.get_text_in_selection(self.ocr_boxes, *r_tuple)
            if text:
                ClipboardManager.copy_text(text)
            else:
                crop = SegmentationEngine.crop_region(self.captured.image, r_tuple)
                ClipboardManager.copy_image(crop)
            self.close()

    # --- Action Bar Handler ---

    def _on_action_triggered(self, action_name: str, payload):
        if action_name == "copy_text":
            ClipboardManager.copy_text(str(payload))
            self.close()

        elif action_name == "copy_image":
            ClipboardManager.copy_image(payload)
            self.close()

        elif action_name == "open_url":
            EntityDetector.open_url(str(payload))
            self.close()

        elif action_name == "open_email":
            EntityDetector.open_email(str(payload))
            self.close()

        elif action_name == "search_web":
            EntityDetector.search_web(str(payload), engine=self.config.search_engine)
            self.close()

        elif action_name == "remove_bg":
            # Cutout subject (Windows 11 Copilot+ feature)
            cutout = SegmentationEngine.remove_background(payload)
            if cutout:
                ClipboardManager.copy_image(cutout)
                # Also save copy if configured
                save_dir = Path(self.config.save_directory)
                save_dir.mkdir(parents=True, exist_ok=True)
                fn = save_dir / f"cutout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                cutout.save(fn)
            self.close()

        elif action_name == "blur_bg":
            blurred = SegmentationEngine.blur_background(payload)
            if blurred:
                ClipboardManager.copy_image(blurred)
            self.close()

        elif action_name == "visual_search":
            EntityDetector.visual_search_google_lens("")
            self.close()

        elif action_name == "save_image":
            save_dir = Path(self.config.save_directory)
            save_dir.mkdir(parents=True, exist_ok=True)
            fn = save_dir / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            payload.save(fn)
            self.close()

        # AI Assistant Actions
        elif action_name.startswith("ai_"):
            llm = LLMService(host=self.config.ollama_host, model=self.config.ollama_model)
            text = str(payload)

            if action_name == "ai_summarize":
                gen = lambda: llm.summarize(text, lang=self.config.target_language)
                title = "Tóm tắt nội dung"
            elif action_name == "ai_explain":
                gen = lambda: llm.explain(text, lang=self.config.target_language)
                title = "Giải thích"
            elif action_name == "ai_translate":
                gen = lambda: llm.translate(text, target_lang=self.config.target_language)
                title = "Dịch văn bản"
            elif action_name == "ai_rewrite":
                gen = lambda: llm.rewrite(text)
                title = "Viết lại câu"
            else:
                return

            if self.ai_dialog:
                self.ai_dialog.deleteLater()

            self.ai_dialog = AIDialog(title, gen, self)
            # Center dialog on screen
            cx = (self.width() - self.ai_dialog.width()) // 2
            cy = (self.height() - self.ai_dialog.height()) // 2
            self.ai_dialog.move(cx, cy)
            self.ai_dialog.show()
