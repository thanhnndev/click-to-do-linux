"""Zero-Scroll Niri Floating Overlay with Live Screen Search, Color Picker, and Rich Click-to-Do UX."""

import math
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image
from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QConicalGradient,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
    QShortcut,
)
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget
from qfluentwidgets import LineEdit, PillPushButton

from ..ai.entities import EntityDetector, LinkEntity, QREntity
from ..ai.screen_cache import screen_analysis_cache
from ..ai.llm import LLMService
from ..ai.ocr import OCREngine, TextBox
from ..ai.segmentation import SegmentationEngine
from ..capture.screen import CapturedScreen
from ..config import Config, load_config
from ..utils.clipboard import ClipboardManager
from .action_bar import ActionBar
from .ai_dialog import AIDialog
from .aurora import COPILOT_PALETTE, AuroraSpec, _phase_color, draw_aurora_border
from ..i18n import t
from .icons import get_icon
from .theme import overlay_style
from .palette import apply_input_palette, theme_color


# Tunables of the animated border, shared by the overlay and the tests.
AURORA = AuroraSpec()


class ImageTaskWorker(QThread):
    finished = pyqtSignal(str, object)

    def __init__(self, task_name: str, image: Image.Image):
        super().__init__()
        self.task_name = task_name
        self.image = image

    def run(self):
        if self.task_name == "remove_bg":
            res = SegmentationEngine.remove_background(self.image)
        else:
            res = SegmentationEngine.blur_background(self.image)
        self.finished.emit(self.task_name, res)


class OverlayWindow(QWidget):
    closed = pyqtSignal()

    def __init__(self, captured: CapturedScreen):
        super().__init__()
        self.setObjectName("OverlayRoot")
        self.setWindowTitle("Click to Do")

        self.captured = captured
        self.config: Config = load_config()
        self.setStyleSheet(overlay_style(self.config.ui_theme))

        self.ocr_boxes: List[TextBox] = []
        self.qr_entities: List[QREntity] = []
        self.link_entities: List[LinkEntity] = []
        self.selected_link: Optional[LinkEntity] = None
        self.hovered_link: Optional[LinkEntity] = None
        self.region_text_mode = False
        self.redacted_patches: List[Tuple[QRect, Image.Image]] = []

        self.selection_start: Optional[QPoint] = None
        self.selection_end: Optional[QPoint] = None
        self.selected_rect: Optional[QRect] = None
        self.hovered_box: Optional[TextBox] = None
        self.selected_boxes: List[TextBox] = []
        self.search_query: str = ""
        self.is_dragging = False
        self.color_picker_active = False
        self.cursor_pos = QPoint(0, 0)
        self.img_worker: Optional[ImageTaskWorker] = None
        # Image-processing state: keep the capture frame open and show the
        # processed result in place of the original crop (better UX).
        self.processing_image: bool = False
        self.processed_image: Optional[Image.Image] = None
        self.processed_rect: Optional[QRect] = None
        self.processed_pixmap: Optional[QPixmap] = None
        self._image_transition_started: Optional[float] = None
        self._image_transition_rect: Optional[QRect] = None
        self._image_transition_duration = 1.6
        self._selection_animation_active = False
        self._selection_settle_started: Optional[float] = None
        self._selection_settle_duration = 0.52
        self._image_result_transition_started: Optional[float] = None
        self._image_result_transition_duration = 0.52
        self._pending_image_result = None
        self._region_overlay_started: Optional[float] = None
        self._bg_cache: Optional[QPixmap] = None

        # Windows 11 Copilot Glowing Border Aura animation state
        self.glow_phase = 0.0
        self._anim_origin: Optional[float] = None
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(16)  # ~60 FPS; frames are cheap enough to keep up
        self.anim_timer.timeout.connect(self._on_anim_tick)
        self.anim_timer.start()

        self._setup_window()
        self._init_widgets()
        apply_input_palette(self, self.config.ui_theme)
        self._start_ocr()

    def _setup_window(self):
        # IMPORTANT FOR NIRI: We use a regular top-level frameless window with fixed geometry
        # matched to Niri's floating rule (x=0, y=0) instead of showFullScreen() so Niri NEVER scrolls columns!
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(self.captured.logical_w, self.captured.logical_h)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)
        QShortcut(QKeySequence("Ctrl+C"), self, self._handle_copy_shortcut)
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_search_bar)

    def show_exact_overlay(self):
        """Shows as a stationary floating layer at (0,0) without triggering Niri fullscreen column scroll."""
        if self.captured.qt_screen:
            self.setScreen(self.captured.qt_screen)
            self.move(0, 0)
        self.show()
        self.activateWindow()
        self.raise_()

    def _init_widgets(self):
        # Top compact Search & Quick Tool Bar (hidden unless Ctrl+F or top hover)
        self.top_bar = QFrame(self)
        self.top_bar.setObjectName("SearchBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(8, 5, 8, 5)
        top_layout.setSpacing(6)

        self.search_input = LineEdit(self.top_bar)
        self.search_input.setObjectName("QuickInput")
        self.search_input.setPlaceholderText(t("find_placeholder"))
        self.search_input.setFixedWidth(220)
        self.search_input.textChanged.connect(self._on_search_changed)
        top_layout.addWidget(self.search_input)

        # PushButton keeps the icon on the left, a Fluent ToolButton would draw
        # the icon in the middle, on top of the label.
        self.color_btn = PillPushButton(self.top_bar)
        self.color_btn.setCheckable(False)
        self.color_btn.setText(t("pick_color"))
        self.color_btn.setIcon(get_icon("pipette", theme_color("#e4e4e7", self.config.ui_theme), 14))
        self.color_btn.setIconSize(QSize(14, 14))
        self.color_btn.clicked.connect(self._toggle_color_picker)
        top_layout.addWidget(self.color_btn)

        self.copy_all_btn = PillPushButton(self.top_bar)
        self.copy_all_btn.setCheckable(False)
        self.copy_all_btn.setText(t("copy_all"))
        self.copy_all_btn.setIcon(get_icon("text", theme_color("#e4e4e7", self.config.ui_theme), 14))
        self.copy_all_btn.setIconSize(QSize(14, 14))
        self.copy_all_btn.clicked.connect(self._copy_all_screen_text)
        top_layout.addWidget(self.copy_all_btn)

        self.top_bar.adjustSize()
        self.top_bar.move((self.captured.logical_w - self.top_bar.width()) // 2, 14)

        self.action_bar = ActionBar(self)
        self.action_bar.action_triggered.connect(self._on_action_triggered)
        self.action_bar.hide()
        self.ai_dialog: Optional[AIDialog] = None

    def _on_escape(self):
        if self.color_picker_active:
            self.color_picker_active = False
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.update()
            return
        if self.search_input.hasFocus() and self.search_query:
            self.search_input.clear()
            self.setFocus()
            return
        self.close()

    def _toggle_search_bar(self):
        self.top_bar.show()
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _on_search_changed(self, text: str):
        self.search_query = text.strip().lower()
        self.update()

    def _toggle_color_picker(self):
        self.color_picker_active = not self.color_picker_active
        self.action_bar.hide()
        self.update()

    def _copy_all_screen_text(self):
        if self.ocr_boxes:
            full_text = "\n".join(b.text for b in self.ocr_boxes)
            ClipboardManager.copy_text(full_text)
            self.close()

    def _start_ocr(self):
        self.analysis_cache = screen_analysis_cache()
        self.analysis_key = self.analysis_cache.key(self.captured, self.config)
        cached = self.analysis_cache.lookup(self.analysis_key)
        if cached is not None:
            self._on_ocr_finished(*cached)
            return
        self.analysis_cache.ready.connect(self._on_analysis_ready)
        self.analysis_cache.start(self.analysis_key, self.captured, self.config)

    def _on_analysis_ready(self, key, result):
        if key == self.analysis_key and result is not None:
            # Each overlay receives its own data, isolated from cached results.
            self._on_ocr_finished(*self.analysis_cache.clone_result(result))

    def _on_ocr_finished(self, boxes: List[TextBox], qr_list: List[QREntity], links=None):
        self.ocr_boxes = boxes
        self.qr_entities = qr_list
        self.link_entities = links if links is not None else EntityDetector.detect_links(boxes)
        self.update()

    def _on_anim_tick(self):
        # The hue sweep runs on the wall clock, so the speed does not depend
        # on the timer resolution.
        now = time.monotonic()
        if self._anim_origin is None:
            self._anim_origin = now
        self.glow_phase = ((now - self._anim_origin) / AURORA.wave_period) % 1.0
        if self._image_transition_started is not None:
            if now - self._image_transition_started >= self._image_transition_duration:
                self._image_transition_started = None
                self._image_transition_rect = None
                self._selection_settle_started = now
                self._region_overlay_started = now - 1.0  # already at full intensity
                if self._pending_image_result is not None:
                    task_name, result_img = self._pending_image_result
                    self._pending_image_result = None
                    self._complete_image_task(task_name, result_img)
        if (self._selection_settle_started is not None
                and now - self._selection_settle_started >= self._selection_settle_duration
                and not self.processing_image):
            self._selection_settle_started = None
        if (self._image_result_transition_started is not None
                and now - self._image_result_transition_started >= self._image_result_transition_duration):
            self._image_result_transition_started = None
        self.update()

    def _image_transition_progress(self) -> float:
        if self._image_transition_started is None:
            return 1.0
        elapsed = time.monotonic() - self._image_transition_started
        linear = min(1.0, max(0.0, elapsed / self._image_transition_duration))
        return linear * linear * (3.0 - 2.0 * linear)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 1-2. Frozen screen with a subtle dimming backdrop, pre-composited once.
        painter.drawPixmap(0, 0, self._background())

        # 2.5 Keep the ambient screen rim beneath content. Processing flow is
        # drawn after the selection crop so the crop cannot erase its final edge.
        if self._image_transition_started is None:
            self._draw_windows11_glowing_border(painter)

        # 3. Draw OCR text highlights
        for box in self.ocr_boxes:
            bx, by, bw, bh = box.rect
            is_search_match = bool(self.search_query and self.search_query in box.text.lower())

            if is_search_match:
                painter.setPen(QPen(QColor(250, 204, 21, 255), 2))
                painter.setBrush(QBrush(QColor(250, 204, 21, 75)))
                painter.drawRoundedRect(bx - 2, by - 2, bw + 4, bh + 4, 4, 4)
            elif box in self.selected_boxes:
                painter.setPen(QPen(QColor(56, 189, 248, 240), 1.6))
                painter.setBrush(QBrush(QColor(56, 189, 248, 50)))
                painter.drawRoundedRect(bx - 2, by - 1, bw + 4, bh + 2, 4, 4)
            elif box == self.hovered_box:
                painter.setPen(QPen(QColor(255, 255, 255, 180), 1.2))
                painter.setBrush(QBrush(QColor(255, 255, 255, 28)))
                painter.drawRoundedRect(bx - 2, by - 1, bw + 4, bh + 2, 4, 4)
            else:
                painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
                painter.setBrush(QBrush(QColor(255, 255, 255, 8)))
                painter.drawRoundedRect(bx, by, bw, bh, 3, 3)

        # Links are independent screen entities, visible before any selection.
        for link in self.link_entities:
            active = link == self.selected_link or link == self.hovered_link
            painter.setPen(QPen(QColor(56, 189, 248, 255 if active else 190), 2 if active else 1.2))
            painter.setBrush(QBrush(QColor(56, 189, 248, 65 if active else 20)))
            for lx, ly, lw, lh in link.rects:
                painter.drawRoundedRect(lx - 2, ly - 1, lw + 4, lh + 2, 3, 3)
                painter.drawLine(lx, ly + lh, lx + lw, ly + lh)

        # 4. Draw QR boxes
        for qr in self.qr_entities:
            qx, qy, qw, qh = qr.rect
            painter.setPen(QPen(QColor(56, 189, 248, 220), 1.5))
            painter.setBrush(QBrush(QColor(56, 189, 248, 35)))
            painter.drawRoundedRect(qx, qy, qw, qh, 5, 5)

        # 5. Draw drag selection
        if self.selected_rect and not self.selected_rect.isNull() and not self.selected_boxes:
            rect = self.selected_rect.normalized()
            scale_x = self.captured.physical_w / float(max(1, self.width()))
            scale_y = self.captured.physical_h / float(max(1, self.height()))
            src = QRectF(
                rect.x() * scale_x,
                rect.y() * scale_y,
                rect.width() * scale_x,
                rect.height() * scale_y,
            )
            painter.drawPixmap(QRectF(rect), self.captured.pixmap, src)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 4, 4)

        # Aurora overlay over the image inside the selected frame.
        if self.processed_rect is not None:
            r = self.processed_rect
            if self.processed_pixmap is not None and not self.processed_pixmap.isNull():
                painter.drawPixmap(r, self.processed_pixmap)
            if self._image_transition_started is not None:
                # The liquid has reached the frame: it floods inwards from the
                # frame edge, so the outside flow becomes the inside overlay.
                q = min(1.0, max(0.0, (self._image_transition_progress() - 0.45) / 0.45))
                if q > 0.0:
                    self._draw_region_aurora(painter, QRectF(r), 1.0, q)
            elif self._region_overlay_started is not None:
                ramp = min(1.0, (time.monotonic() - self._region_overlay_started) / 0.6)
                ramp = ramp * ramp * (3.0 - 2.0 * ramp)
                # Full-intensity while processing, calmer once the result is shown.
                self._draw_region_aurora(painter, QRectF(r), ramp * (1.0 if self.processing_image else 0.7))

        if self._image_transition_started is not None:
            self._draw_windows11_glowing_border(painter)

        # 6. Draw Color Picker Loupe if active
        if self.color_picker_active:
            self._draw_color_loupe(painter)

    def _background(self) -> QPixmap:
        """Frozen screen + dimming, scaled to the widget once instead of every frame."""
        if self._bg_cache is None:
            dpr = self.devicePixelRatioF()
            bg = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
            bg.setDevicePixelRatio(dpr)
            qp = QPainter(bg)
            qp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            qp.drawPixmap(QRectF(0, 0, self.width(), self.height()), self.captured.pixmap,
                          QRectF(0, 0, self.captured.physical_w, self.captured.physical_h))
            qp.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(9, 9, 12, 60))
            qp.end()
            self._bg_cache = bg
        return self._bg_cache

    def _get_pixel_hex_at(self, pos: QPoint) -> Tuple[str, QColor]:
        px = min(self.captured.image.width - 1, max(0, int(pos.x() * self.captured.scale_factor)))
        py = min(self.captured.image.height - 1, max(0, int(pos.y() * self.captured.scale_factor)))
        r, g, b = self.captured.image.getpixel((px, py))[:3]
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        return hex_code, QColor(r, g, b)

    def _draw_color_loupe(self, painter: QPainter):
        hex_code, qcol = self._get_pixel_hex_at(self.cursor_pos)
        bx = min(self.width() - 120, self.cursor_pos.x() + 18)
        by = max(20, self.cursor_pos.y() - 36)

        pill = QRect(bx, by, 104, 30)
        painter.setPen(QPen(QColor(255, 255, 255, 45), 1))
        painter.setBrush(QBrush(QColor(20, 20, 25, 240)))
        painter.drawRoundedRect(pill, 7, 7)

        swatch = QRect(bx + 7, by + 6, 18, 18)
        painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
        painter.setBrush(QBrush(qcol))
        painter.drawRoundedRect(swatch, 4, 4)

        painter.setPen(QColor("#f4f4f5"))
        painter.setFont(QFont("monospace", 10, QFont.Weight.Bold))
        painter.drawText(bx + 32, by + 20, hex_code)

    def _draw_windows11_glowing_border(self, painter: QPainter):
        """Draw the screen rim feeding a liquid front into the selected image."""
        if self._image_transition_started is not None and self._image_transition_rect is not None:
            progress = self._image_transition_progress()
            # The rim hands over to the liquid: they cross-fade over the same
            # edge, so the flow appears to grow out of the ambient border.
            hand_over = min(1.0, progress / 0.3)
            hand_over = hand_over * hand_over * (3.0 - 2.0 * hand_over)
            painter.save()
            painter.setOpacity(1.0 - hand_over)
            self._draw_rim(painter)
            painter.restore()
            self._draw_liquid_border_flow(
                painter, self._image_transition_rect.normalized(), progress
            )
            return
        # The ambient rim stays on while selecting; only the processing
        # animation (which owns the selection frame) replaces it.
        if self.processing_image or self.processed_pixmap is not None:
            return
        self._draw_rim(painter)

    def _draw_rim(self, painter: QPainter):
        """Screen-edge aurora, rendered at reduced size: it is a soft glow, and
        the per-slice drawing cost scales with the canvas size."""
        k = 0.4
        spec = replace(
            AURORA,
            glow_depth=AURORA.glow_depth * k,
            wave_amplitude=AURORA.wave_amplitude * k,
            second_wave_amplitude=AURORA.second_wave_amplitude * k,
        )
        img = QImage(max(2, int(self.width() * k)), max(2, int(self.height() * k)),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        qp = QPainter(img)
        draw_aurora_border(qp, img.width(), img.height(), self.glow_phase, spec)
        qp.end()
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(QRectF(0, 0, self.width(), self.height()), img)
        painter.restore()

    @staticmethod
    def _lowres_canvas(w: float, h: float, scale: float) -> Tuple[QImage, QPainter]:
        """Transparent low-res canvas; upscaling it smoothly gives a free blur."""
        img = QImage(max(2, int(w * scale)), max(2, int(h * scale)),
                     QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(0)
        qp = QPainter(img)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setPen(Qt.PenStyle.NoPen)
        qp.scale(img.width() / w, img.height() / h)
        return img, qp

    def _draw_liquid_border_flow(self, painter: QPainter, rect: QRect, progress: float):
        """Aurora liquid poured in from the screen edges toward the crop.

        A soft, rippling body whose inner front travels from the screen border
        to the selection frame, brightest at the front. It is painted on a
        low-res canvas and scaled up, so it is smooth with no stroked lines.
        """
        frame = QRectF(rect)
        sw, sh = float(self.width()), float(self.height())
        p = min(1.0, max(0.0, progress / 0.6))
        ease = p * p * p * (p * (p * 6.0 - 15.0) + 10.0)  # smootherstep
        appear = min(1.0, progress / 0.15)
        appear = appear * appear * (3.0 - 2.0 * appear)
        fade = appear * min(1.0, max(0.0, (1.0 - progress) / 0.2))
        if fade <= 0.0:
            return
        # The front starts just inside the screen rim (where the ambient glow
        # lives) and closes in on the frame, each side travelling its own way.
        rim = 22.0
        start = QRectF(rim, rim, sw - 2 * rim, sh - 2 * rim)
        front = QRectF(
            start.left() + (frame.left() - start.left()) * ease,
            start.top() + (frame.top() - start.top()) * ease,
            start.width() + (frame.width() - start.width()) * ease,
            start.height() + (frame.height() - start.height()) * ease,
        )
        radius = 4.0 + 30.0 * (1.0 - ease)
        amp = 16.0 * math.sin(math.pi * p)
        t = time.monotonic() * 0.5

        img, qp = self._lowres_canvas(sw, sh, 0.2)
        grad = QConicalGradient(sw / 2.0, sh / 2.0, -self.glow_phase * 360.0)
        for pos, (r, g, b) in zip((0.0, 0.25, 0.5, 0.75, 1.0), COPILOT_PALETTE + (COPILOT_PALETTE[0],)):
            grad.setColorAt(pos, QColor(r, g, b))
        qp.setBrush(QBrush(grad))

        def hole(expand: float) -> QPainterPath:
            return self._rippled_rrect(front.adjusted(-expand, -expand, expand, expand),
                                       radius + expand, amp, t)

        screen_path = QPainterPath()
        screen_path.addRect(QRectF(-4, -4, sw + 8, sh + 8))
        inner = hole(0.0)
        # Faint body: everything between the screen edge and the front.
        body = QPainterPath(screen_path)
        body.addPath(inner)
        body.setFillRule(Qt.FillRule.OddEvenFill)
        qp.setOpacity(0.10)
        qp.drawPath(body)
        # Crest: thin soft bands hugging the front, accumulating towards it.
        for expand in (130.0, 70.0, 34.0, 12.0):
            band = QPainterPath(hole(expand))
            band.addPath(inner)
            band.setFillRule(Qt.FillRule.OddEvenFill)
            qp.setOpacity(0.13)
            qp.drawPath(band)
        qp.end()

        painter.save()
        painter.setClipRect(QRectF(0, 0, sw, sh))
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(fade)
        painter.drawImage(QRectF(0, 0, sw, sh), img)
        painter.restore()

    @staticmethod
    def _rippled_rrect(rect: QRectF, radius: float, amp: float, t: float) -> QPainterPath:
        """Rounded rect whose outline carries a travelling wave along its normal.

        Points and normals are computed analytically with numpy (edges plus
        corner arcs), so this stays cheap enough to run every frame.
        """
        l, tp, r, b = rect.left(), rect.top(), rect.right(), rect.bottom()
        rad = max(0.5, min(radius, rect.width() / 2.0, rect.height() / 2.0))
        spacing = max(16.0, 2.0 * (rect.width() + rect.height()) / 110.0)
        pts, nrm = [], []

        def edge(p0, p1, normal):
            n = max(2, int(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / spacing))
            k = np.linspace(0.0, 1.0, n, endpoint=False, dtype=np.float32)[:, None]
            pts.append(np.array(p0, np.float32) + k * (np.array(p1, np.float32) - np.array(p0, np.float32)))
            nrm.append(np.tile(np.array(normal, np.float32), (n, 1)))

        def arc(cx, cy, a0, a1):
            n = max(3, int(rad * math.pi / 2.0 / spacing) + 2)
            ang = np.linspace(math.radians(a0), math.radians(a1), n, endpoint=False, dtype=np.float32)
            unit = np.stack([np.cos(ang), np.sin(ang)], axis=1)
            pts.append(np.array([cx, cy], np.float32) + rad * unit)
            nrm.append(unit)

        edge((l + rad, tp), (r - rad, tp), (0, -1))
        arc(r - rad, tp + rad, -90, 0)
        edge((r, tp + rad), (r, b - rad), (1, 0))
        arc(r - rad, b - rad, 0, 90)
        edge((r - rad, b), (l + rad, b), (0, 1))
        arc(l + rad, b - rad, 90, 180)
        edge((l, b - rad), (l, tp + rad), (-1, 0))
        arc(l + rad, tp + rad, 180, 270)

        pts_a, nrm_a = np.concatenate(pts), np.concatenate(nrm)
        seg = np.hypot(*np.diff(np.vstack([pts_a, pts_a[:1]]), axis=0).T)
        f = np.concatenate([[0.0], np.cumsum(seg[:-1])]) / max(float(seg.sum()), 1.0)
        tau = 2.0 * math.pi
        off = amp * (np.sin(tau * (f * 6.0 - t)) + 0.35 * np.sin(tau * (f * 11.0 + t * 0.7)))
        out = pts_a + nrm_a * off[:, None].astype(np.float32)
        poly = QPolygonF([QPointF(float(x), float(y)) for x, y in out])
        path = QPainterPath()
        path.addPolygon(poly)
        path.closeSubpath()
        return path

    _aurora_lut = None

    @classmethod
    def _palette_lut(cls):
        if cls._aurora_lut is None:
            cls._aurora_lut = np.array(
                [[c.red(), c.green(), c.blue()]
                 for c in (_phase_color(i / 255.0, 0.0) for i in range(256))],
                dtype=np.float32,
            )
        return cls._aurora_lut

    def _aurora_field_image(self, w: float, h: float, level: float) -> QImage:
        """Organic aurora: a domain-warped flow field, glowing along its veins.

        Several sine fields travel in different directions at incommensurate
        speeds, so the light drifts and swirls in every direction and never
        repeats. Computed with numpy on a tiny grid and scaled up smoothly.
        """
        gw = max(8, int(w * 0.18))
        gh = max(8, int(h * 0.18))
        t = time.monotonic()
        aspect = w / h
        xs = np.linspace(0.0, aspect, gw, dtype=np.float32)[None, :]
        ys = np.linspace(0.0, 1.0, gh, dtype=np.float32)[:, None]
        # Warp the coordinates so the veins curl instead of forming straight bands.
        wx = xs + 0.18 * np.sin(3.1 * ys + 0.55 * t) + 0.10 * np.sin(5.3 * xs - 0.8 * t)
        wy = ys + 0.18 * np.sin(2.7 * xs - 0.45 * t) + 0.10 * np.sin(4.7 * ys + 0.7 * t)
        n = (np.sin(4.3 * wx + 1.7 * wy + 0.62 * t)
             + np.sin(-3.1 * wx + 3.7 * wy - 0.51 * t + 1.3)
             + np.sin(5.9 * wx - 2.3 * wy + 0.37 * t + 2.9)
             + 0.8 * np.sin(6.0 * np.hypot(wx - 0.5 * aspect, wy - 0.5) - 0.7 * t)) / 3.8
        # Glow along two iso-lines of the field = flowing luminous veins.
        veins = np.exp(-((n - 0.15) / 0.17) ** 2) + 0.8 * np.exp(-((n + 0.38) / 0.2) ** 2)
        haze = 0.5 + 0.5 * n
        # A flowing wash that covers the whole frame, with brighter veins on top.
        strength = (0.42 + 0.42 * np.clip(veins, 0.0, 1.0) + 0.16 * haze) * level
        hue = (0.5 + 0.5 * np.sin(2.2 * wx - 1.6 * wy + 0.33 * t + 2.0 * n)) * 255.0
        rgb = self._palette_lut()[hue.astype(np.int32).clip(0, 255)]
        alpha = np.clip(strength * 0.62, 0.0, 1.0)  # about 0.26 minimum, 0.6 on the veins
        buf = np.empty((gh, gw, 4), dtype=np.uint8)
        buf[..., 0] = rgb[..., 2] * alpha  # premultiplied BGRA
        buf[..., 1] = rgb[..., 1] * alpha
        buf[..., 2] = rgb[..., 0] * alpha
        buf[..., 3] = alpha * 255.0
        return QImage(buf.data, gw, gh, gw * 4,
                      QImage.Format.Format_ARGB32_Premultiplied).copy()

    def _flood_hole(self, w: float, h: float, q: float, layer: int) -> Optional[QPainterPath]:
        """Not-yet-flooded centre (local coords); layers feather its edge.

        At q=0 every layer covers the whole frame (nothing shown); at q=1 every
        layer has collapsed (everything shown).
        """
        q = q * q * (3.0 - 2.0 * q)
        depth = max(0.0, q * (min(w, h) / 2.0 + 52.0) - 52.0 + 13.0 * layer)
        rect = QRectF(depth, depth, w - 2 * depth, h - 2 * depth)
        if rect.width() <= 2 or rect.height() <= 2:
            return None
        return self._rippled_rrect(rect, 10.0, 8.0 * math.sin(math.pi * q), time.monotonic() * 0.5)

    def _draw_region_aurora(self, painter: QPainter, rect: QRectF, level: float,
                            flood: float = 1.0):
        """Aurora light washing over the whole image, clipped to the frame.

        Rendered on a low-res canvas (smooth, no slice seams) and alpha-blended
        so the picture underneath stays readable: drifting colour
        pools, wavy aurora ribbons and a slow sheen.
        """
        if level <= 0.0 or rect.width() < 4 or rect.height() < 4:
            return
        w, h = rect.width(), rect.height()
        tau = 2.0 * math.pi
        img = self._aurora_field_image(w, h, level)

        if flood < 1.0:
            # Erase the not-yet-reached centre with a feathered edge so the
            # liquid seems to seep inwards rather than being cut by a mask.
            qp2 = QPainter(img)
            qp2.setRenderHint(QPainter.RenderHint.Antialiasing)
            qp2.setPen(Qt.PenStyle.NoPen)
            qp2.scale(img.width() / w, img.height() / h)
            qp2.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
            qp2.setBrush(QColor(0, 0, 0))
            qp2.setOpacity(0.2)
            for layer in range(5):
                hole = self._flood_hole(w, h, flood, layer)
                if hole is not None:
                    qp2.drawPath(hole)
            qp2.end()
        mask = QPainterPath()
        mask.addRoundedRect(rect, 4, 4)
        painter.save()
        painter.setClipPath(mask)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(rect, img)
        painter.restore()

    def mouseDoubleClickEvent(self, event):
        """Double-click any text box to immediately copy it and close overlay."""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            link = self._link_at(pos)
            if link and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                ClipboardManager.copy_text(link.text)
                self.close()
                return
            box = OCREngine.find_box_at(self.ocr_boxes, pos.x(), pos.y())
            if box:
                ClipboardManager.copy_text(box.text)
                self.close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
            return

        # Middle click anywhere copies the pixel HEX color immediately
        if event.button() == Qt.MouseButton.MiddleButton:
            hex_code, _ = self._get_pixel_hex_at(event.pos())
            ClipboardManager.copy_text(hex_code)
            self.close()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()
            if self.color_picker_active:
                hex_code, _ = self._get_pixel_hex_at(pos)
                ClipboardManager.copy_text(hex_code)
                self.close()
                return

            self.selection_start = pos
            self.selection_end = pos
            self.is_dragging = False
            # A new interaction clears any previous image-processing result.
            self.processing_image = False
            self.processed_image = None
            self.processed_rect = None
            self.processed_pixmap = None
            self._image_transition_started = None
            self._image_transition_rect = None
            self._selection_animation_active = False
            self._selection_settle_started = None
            self._pending_image_result = None
            self._image_result_transition_started = None
            self._region_overlay_started = None

    def mouseMoveEvent(self, event):
        pos = event.pos()
        self.cursor_pos = pos

        if self.color_picker_active:
            self.update()
            return

        if event.buttons() & Qt.MouseButton.LeftButton and self.selection_start:
            if (pos - self.selection_start).manhattanLength() > 5:
                self.is_dragging = True
                self.selected_boxes.clear()
                self.selected_link = None
                self.hovered_link = None
                self.region_text_mode = False
                self.action_bar.hide()
                self.selection_end = pos
                self.selected_rect = QRect(self.selection_start, self.selection_end).normalized()
                self.update()
            return

        link = self._link_at(pos)
        new_hover = None if link else OCREngine.find_box_at(self.ocr_boxes, pos.x(), pos.y())
        if new_hover != self.hovered_box or link != self.hovered_link:
            self.hovered_box = new_hover
            self.hovered_link = link
            self.setToolTip(link.text if link else "")
            self.setCursor(Qt.CursorShape.PointingHandCursor if link else
                           Qt.CursorShape.IBeamCursor if new_hover else Qt.CursorShape.CrossCursor)
            self.update()

    def _link_at(self, pos):
        return next((link for link in self.link_entities
                     if link.contains_point(pos.x(), pos.y())), None)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.color_picker_active:
            return

        pos = event.pos()

        # 1. Drag Selection
        if self.is_dragging and self.selected_rect:
            self.is_dragging = False
            rect = self.selected_rect.normalized()
            if rect.width() > 8 and rect.height() > 8:
                r_tuple = (rect.x(), rect.y(), rect.width(), rect.height())
                text_inside = OCREngine.get_text_in_selection(self.ocr_boxes, *r_tuple)
                modifiers = event.modifiers()
                # If Shift is held during drag, force Text mode; otherwise show Image bar (with Copy Text button if text exists)
                if (modifiers & Qt.KeyboardModifier.ShiftModifier) and text_inside:
                    self.region_text_mode = True
                    self._show_actions_for_text(text_inside, r_tuple, region=True)
                else:
                    self.region_text_mode = False
                    self.processed_rect = rect
                    crop = SegmentationEngine.crop_logical_region(
                        self.captured.image, r_tuple, self.captured.scale_factor
                    )
                    self.action_bar.show_for_image(crop, text_inside=text_inside)
                    self.action_bar.reposition(r_tuple, self.width(), self.height())
            self.update()
            return

        self.selected_link = None
        self.region_text_mode = False

        # A link takes precedence over OCR line boxes, but Shift still selects text.
        link = self._link_at(pos)
        if link and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.selected_link = link
            self.selected_boxes.clear()
            self.selected_rect = None
            self.action_bar.show_for_link(link.text)
            self.action_bar.reposition(link.rect, self.width(), self.height())
            self.update()
            return

        # 2. Direct Click on QR
        for qr in self.qr_entities:
            qx, qy, qw, qh = qr.rect
            if QRect(qx, qy, qw, qh).contains(pos):
                self.selected_boxes.clear()
                self.selected_rect = None
                self.action_bar.show_for_qr(qr.text, qr.is_url)
                self.action_bar.reposition(qr.rect, self.width(), self.height())
                return

        # 3. Direct Click (or Shift+Click multi-select) on Text Box
        box = OCREngine.find_box_at(self.ocr_boxes, pos.x(), pos.y())
        if box:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                if box in self.selected_boxes:
                    self.selected_boxes.remove(box)
                else:
                    self.selected_boxes.append(box)
            else:
                self.selected_boxes = [box]

            if self.selected_boxes:
                self.selected_boxes.sort(key=lambda b: (b.rect[1] // 14, b.rect[0]))
                combined_text = "\n".join(b.text for b in self.selected_boxes)
                min_x = min(b.rect[0] for b in self.selected_boxes)
                min_y = min(b.rect[1] for b in self.selected_boxes)
                max_x = max(b.rect[0] + b.rect[2] for b in self.selected_boxes)
                max_y = max(b.rect[1] + b.rect[3] for b in self.selected_boxes)
                union_rect = (min_x, min_y, max_x - min_x, max_y - min_y)
                self.selected_rect = QRect(*union_rect)
                self._show_actions_for_text(combined_text, union_rect, region=len(self.selected_boxes) > 1)
            else:
                self.selected_rect = None
                self.action_bar.hide()
            self.update()
        else:
            self.selected_boxes.clear()
            self.selected_rect = None
            self.action_bar.hide()
            self.update()

    def _show_actions_for_text(self, text: str, rect_tuple: Tuple[int, int, int, int], *, region=False):
        emails = EntityDetector.extract_emails(text)
        self.action_bar.show_for_text(text, emails=emails, region=region)
        self.action_bar.reposition(rect_tuple, self.width(), self.height())

    def _handle_copy_shortcut(self):
        if self.selected_link:
            ClipboardManager.copy_text(self.selected_link.text)
            self.close()
        elif self.region_text_mode and self.selected_rect:
            rect = self.selected_rect.normalized()
            text = OCREngine.get_text_in_selection(self.ocr_boxes, rect.x(), rect.y(), rect.width(), rect.height())
            ClipboardManager.copy_text(self.action_bar.text_for_copy(text))
            self.close()
        elif self.selected_boxes:
            ClipboardManager.copy_text(self.action_bar.text_for_copy("\n".join(b.text for b in self.selected_boxes)))
            self.close()
        elif self.selected_rect and not self.selected_rect.isNull():
            rect = self.selected_rect.normalized()
            r_tuple = (rect.x(), rect.y(), rect.width(), rect.height())
            crop = SegmentationEngine.crop_logical_region(
                self.captured.image, r_tuple, self.captured.scale_factor
            )
            ClipboardManager.copy_image(crop)
            self.close()

    def _on_action_triggered(self, action_name: str, payload):
        if action_name == "copy_text":
            ClipboardManager.copy_text(str(payload))
            self.close()
        elif action_name == "copy_image":
            ClipboardManager.copy_image(payload)
            self.close()
        elif action_name == "redact_region":
            redacted = SegmentationEngine.pixelate_image(payload)
            ClipboardManager.copy_image(redacted)
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
        elif action_name in ("remove_bg", "blur_bg"):
            self.processing_image = True
            self.processed_image = None
            self.processed_pixmap = None
            self._selection_animation_active = bool(self.selected_rect and not self.selected_rect.isNull())
            self._selection_settle_started = None
            self._image_result_transition_started = None
            self._region_overlay_started = None
            if self.selected_rect and not self.selected_rect.isNull():
                self.processed_rect = self.selected_rect.normalized()
                self._image_transition_rect = self.processed_rect
                self._image_transition_started = time.monotonic()
            else:
                self._selection_animation_active = False
                self.processed_rect = None
                self._image_transition_rect = None
                self._image_transition_started = None
            self.img_worker = ImageTaskWorker(action_name, payload)
            self.img_worker.finished.connect(self._on_image_task_done)
            self.img_worker.start()
            self.update()
        elif action_name == "save_image":
            save_dir = Path(self.config.save_directory)
            save_dir.mkdir(parents=True, exist_ok=True)
            fn = save_dir / f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            payload.save(fn)
            self.close()
        elif action_name.startswith("ai_"):
            llm = LLMService.from_config(self.config)
            if action_name == "ai_custom":
                ctx_text, question = payload
                title = f"{t('ai_ask_title')}: {question[:28]}"
                gen = lambda: llm.custom_ask(ctx_text, question, lang=self.config.target_language)
            else:
                text = str(payload)
                tasks = {
                    "ai_summarize": (t("summarize"), lambda: llm.summarize(text, lang=self.config.target_language)),
                    "ai_explain": (t("explain"), lambda: llm.explain(text, lang=self.config.target_language)),
                    "ai_translate": (t("translate"), lambda: llm.translate(text, target_lang=self.config.target_language)),
                    "ai_rewrite": (t("rewrite"), lambda: llm.rewrite(text)),
                }
                if action_name not in tasks:
                    return
                title, gen = tasks[action_name]

            if self.ai_dialog:
                self.ai_dialog.deleteLater()
            self.ai_dialog = AIDialog(title, gen, self)
            self.ai_dialog.move(
                (self.width() - self.ai_dialog.width()) // 2,
                (self.height() - self.ai_dialog.height()) // 2,
            )
            self.ai_dialog.show()
            self.ai_dialog.raise_()

    def _on_image_task_done(self, task_name: str, result_img):
        if result_img and self._image_transition_started is not None:
            self._pending_image_result = (task_name, result_img)
            return
        self._complete_image_task(task_name, result_img)

    def _complete_image_task(self, task_name: str, result_img):
        self.processing_image = False
        self._image_transition_started = None
        self._image_transition_rect = None
        self._image_result_transition_started = (
            time.monotonic()
            if result_img and self.processed_rect is not None
            else None
        )
        if not result_img:
            self._selection_animation_active = False
            self._region_overlay_started = None
        if result_img:
            ClipboardManager.copy_image(result_img)
            if task_name == "remove_bg":
                save_dir = Path(self.config.save_directory)
                save_dir.mkdir(parents=True, exist_ok=True)
                fn = save_dir / f"cutout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                result_img.save(fn)
            # Keep the capture frame open and composite the processed result
            # onto the background in place of the original crop.
            self.processed_image = result_img
            try:
                data = result_img.convert("RGBA").tobytes("raw", "RGBA")
                qimg = QImage(data, result_img.width, result_img.height, result_img.width * 4, QImage.Format.Format_RGBA8888)
                self.processed_pixmap = QPixmap.fromImage(qimg)
            except Exception:
                self.processed_pixmap = None
            # Re-show the action bar bound to the result so the user can copy/save.
            if self.processed_rect is not None:
                r = self.processed_rect
                r_tuple = (r.x(), r.y(), r.width(), r.height())
                self.action_bar.show_for_image(result_img)
                self.action_bar.reposition(r_tuple, self.width(), self.height())
        self.update()

    def closeEvent(self, event):
        if hasattr(self, "analysis_cache"):
            try:
                self.analysis_cache.ready.disconnect(self._on_analysis_ready)
            except (TypeError, RuntimeError):
                pass
        if hasattr(self, "anim_timer") and self.anim_timer.isActive():
            self.anim_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
