"""Bounded, memory-only screen analysis shared by every overlay in a process."""

import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import replace
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QApplication

from .entities import EntityDetector
from .ocr import OCREngine, TESS_LANGS


class ScreenAnalysisCache(QObject):
    """Keep six analyses for five minutes, without retaining screenshots.

    Workers belong to the application, so closing an overlay neither interrupts
    analysis nor destroys a running QThread. Repeated requests join the same job.
    All cache access happens on the GUI thread; workers only emit their results.
    """

    ready = pyqtSignal(str, object)
    _completed = pyqtSignal(str, object)

    def __init__(self, parent=None, *, capacity=6, ttl=300):
        super().__init__(parent)
        self.capacity = capacity
        self.ttl = ttl
        self._entries = OrderedDict()
        self._pending = set()
        self._completed.connect(self._finish)

    @staticmethod
    def key(captured, config):
        image = captured.image
        # Model downloads/replacements invalidate results without a restart.
        model_dir = Path.home() / '.local/share/click-to-do/tessdata'
        model_versions = []
        for lang in TESS_LANGS:
            try:
                stat = (model_dir / f'{lang}.traineddata').stat()
                model_versions.append((stat.st_size, stat.st_mtime_ns))
            except OSError:
                model_versions.append(None)
        context = (
            image.size, image.mode, captured.physical_w, captured.physical_h,
            captured.logical_w, captured.logical_h, captured.scale_factor,
            captured.output_name, config.auto_detect_qr, config.ocr_det_backend,
            config.ryzenai_dir, tuple(model_versions),
        )
        digest = hashlib.blake2b(digest_size=24)
        digest.update(repr(context).encode())
        digest.update(image.tobytes())
        return digest.hexdigest()

    @staticmethod
    def clone_result(result):
        return tuple([replace(item) for item in items] for items in result)

    def lookup(self, key):
        now = time.monotonic()
        for expired in [k for k, (deadline, _) in self._entries.items() if deadline <= now]:
            del self._entries[expired]
        entry = self._entries.get(key)
        if entry is None:
            return None
        self._entries.move_to_end(key)
        return self.clone_result(entry[1])

    def start(self, key, captured, config):
        if key in self._pending:
            return
        self._pending.add(key)
        # Retain only PIL data in the worker, never Qt pixmaps/screens/widgets.
        threading.Thread(
            target=self._analyze,
            args=(key, captured.image, captured.scale_factor, config.auto_detect_qr),
            name='click-to-do-screen-analysis', daemon=True,
        ).start()

    def _analyze(self, key, image, scale, detect_qr):
        try:
            qr = EntityDetector.detect_qr_codes(image, scale) if detect_qr else []
            boxes = OCREngine.get_instance().detect(image, scale, raise_errors=True)
            result = (boxes, qr)
        except Exception as exc:
            print(f'[ScreenCache] Analysis failed: {exc}')
            result = None
        try:
            self._completed.emit(key, result)
        except RuntimeError:
            # The application may have exited while a daemon worker completed.
            pass

    @pyqtSlot(str, object)
    def _finish(self, key, result):
        self._pending.discard(key)
        if result is not None:
            self._entries[key] = (time.monotonic() + self.ttl, self.clone_result(result))
            self._entries.move_to_end(key)
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)
        self.ready.emit(key, result)


def screen_analysis_cache():
    """Application ownership keeps jobs alive after an overlay is deleted."""
    app = QApplication.instance()
    if not hasattr(app, '_screen_analysis_cache'):
        app._screen_analysis_cache = ScreenAnalysisCache(app)
    return app._screen_analysis_cache
