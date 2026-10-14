"""Clean, minimalist Settings & Local AI Model Manager (Raycast/Linear inspired, zero AI slop)."""

import shutil
import subprocess
from pathlib import Path
from PyQt6.QtCore import QSize, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..ai.llm import LLMService
from ..ai.ocr import OCREngine
from ..ai.segmentation import SegmentationEngine
from ..config import Config, load_config, save_config
from .icons import get_icon

RECOMMENDED_VI_MODELS = [
    ("qwen2.5:3b", "Qwen 2.5 3B  —  Fastest & Best Vietnamese (1.9 GB)"),
    ("gemma3:4b", "Gemma 3 4B  —  Strong Vietnamese & Code Analysis (3.1 GB)"),
    ("qwen2.5:1.5b", "Qwen 2.5 1.5B  —  Ultra-light CPU/iGPU Instant (980 MB)"),
    ("qwen2.5:7b", "Qwen 2.5 7B  —  High-Accuracy Translation & Rewrite (4.7 GB)"),
]


class ModelWarmupWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, bg_model: str, pull_ollama_model: str = ""):
        super().__init__()
        self.bg_model = bg_model
        self.pull_ollama_model = pull_ollama_model

    def run(self):
        try:
            self.progress.emit("Initializing RapidOCR (PP-OCRv4 ONNX)...", 25)
            OCREngine.warmup()

            self.progress.emit(f"Loading Cutout Engine ({self.bg_model})...", 60)
            SegmentationEngine.get_session(self.bg_model)

            if self.pull_ollama_model and shutil.which("ollama"):
                self.progress.emit(f"Pulling Ollama model '{self.pull_ollama_model}'...", 80)
                subprocess.run(["ollama", "pull", self.pull_ollama_model], check=False)

            self.progress.emit("Ready", 100)
            self.finished.emit(True, "All local models initialized and cached.")
        except Exception as e:
            self.finished.emit(False, str(e))


class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config: Config = load_config()
        self.setWindowTitle("Click to Do — Settings")
        self.setFixedSize(540, 520)
        self.setStyleSheet("""
            QWidget {
                background-color: #09090b;
                color: #f4f4f5;
                font-family: "Inter", "Noto Sans", system-ui, sans-serif;
                font-size: 13px;
            }
            QFrame#Card {
                background-color: #121215;
                border: 1px solid #27272a;
                border-radius: 8px;
            }
            QLabel#HeaderTitle {
                font-size: 16px;
                font-weight: 600;
                color: #ffffff;
            }
            QLabel#HeaderSub {
                font-size: 12px;
                color: #71717a;
            }
            QLabel#CardTitle {
                font-size: 12px;
                font-weight: 600;
                color: #a1a1aa;
                background: transparent;
            }
            QLabel#Muted {
                font-size: 11px;
                color: #71717a;
                background: transparent;
            }
            QComboBox {
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 6px 10px;
                color: #e4e4e7;
                font-size: 12px;
            }
            QComboBox:focus {
                border: 1px solid #52525b;
            }
            QComboBox QAbstractItemView {
                background-color: #18181b;
                border: 1px solid #27272a;
                selection-background-color: #27272a;
                color: #e4e4e7;
            }
            QPushButton {
                background-color: #f4f4f5;
                color: #09090b;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #27272a;
                color: #71717a;
            }
            QPushButton#Secondary {
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #27272a;
                font-weight: 500;
            }
            QPushButton#Secondary:hover {
                background-color: #27272a;
                color: #ffffff;
            }
            QProgressBar {
                border: 1px solid #27272a;
                border-radius: 4px;
                background-color: #18181b;
                max-height: 6px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #e4e4e7;
                border-radius: 3px;
            }
        """)
        self._build_ui()
        self._refresh_ollama()

    def _make_card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("Card")
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)
        return card, vbox

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # Header
        hdr = QVBoxLayout()
        hdr.setSpacing(2)
        title = QLabel("Click to Do")
        title.setObjectName("HeaderTitle")
        sub = QLabel("Screen intelligence overlay, local models, and desktop bar integration")
        sub.setObjectName("HeaderSub")
        hdr.addWidget(title)
        hdr.addWidget(sub)
        root.addLayout(hdr)

        # Card 1: Vision & Cutout Model
        c1, l1 = self._make_card()
        t1 = QLabel("SUBJECT CUTOUT ENGINE (ONNX)")
        t1.setObjectName("CardTitle")
        l1.addWidget(t1)

        self.bg_combo = QComboBox()
        self.bg_combo.addItem("u2netp  —  Ultra-fast (~4.7 MB, <50ms latency)", "u2netp")
        self.bg_combo.addItem("isnet-general-use  —  High precision (~170 MB, fine edges)", "isnet-general-use")
        idx = self.bg_combo.findData(self.config.bg_removal_model)
        if idx >= 0:
            self.bg_combo.setCurrentIndex(idx)
        l1.addWidget(self.bg_combo)
        root.addWidget(c1)

        # Card 2: Vietnamese Local LLM (Ollama)
        c2, l2 = self._make_card()
        t2 = QLabel("LOCAL LANGUAGE MODEL (VIETNAMESE / ENGLISH)")
        t2.setObjectName("CardTitle")
        l2.addWidget(t2)

        row_llm = QHBoxLayout()
        self.ollama_combo = QComboBox()
        self.ollama_combo.setEditable(True)
        row_llm.addWidget(self.ollama_combo, stretch=1)

        ref_btn = QPushButton(" Refresh")
        ref_btn.setObjectName("Secondary")
        ref_btn.setIcon(get_icon("refresh", "#e4e4e7", 13))
        ref_btn.setIconSize(QSize(13, 13))
        ref_btn.clicked.connect(self._refresh_ollama)
        row_llm.addWidget(ref_btn)
        l2.addLayout(row_llm)

        rec_lbl = QLabel("Recommended lightweight Vietnamese models: qwen2.5:3b (1.9GB), gemma3:4b (3.1GB)")
        rec_lbl.setObjectName("Muted")
        l2.addWidget(rec_lbl)
        root.addWidget(c2)

        # Card 3: Target Language & Search Engine
        c3, l3 = self._make_card()
        t3 = QLabel("PREFERENCES")
        t3.setObjectName("CardTitle")
        l3.addWidget(t3)

        pref_row = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Target Language: Tiếng Việt (vi)", "vi")
        self.lang_combo.addItem("Target Language: English (en)", "en")
        l_idx = self.lang_combo.findData(self.config.target_language)
        if l_idx >= 0:
            self.lang_combo.setCurrentIndex(l_idx)
        pref_row.addWidget(self.lang_combo)

        self.engine_combo = QComboBox()
        self.engine_combo.addItem("Web Search: Google", "google")
        self.engine_combo.addItem("Web Search: DuckDuckGo", "duckduckgo")
        self.engine_combo.addItem("Web Search: Bing", "bing")
        e_idx = self.engine_combo.findData(self.config.search_engine)
        if e_idx >= 0:
            self.engine_combo.setCurrentIndex(e_idx)
        pref_row.addWidget(self.engine_combo)
        l3.addLayout(pref_row)
        root.addWidget(c3)

        # Card 4: Model Cache & System Integration
        c4, l4 = self._make_card()
        t4 = QLabel("MODEL CACHE & DESKTOP INTEGRATION")
        t4.setObjectName("CardTitle")
        l4.addWidget(t4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        l4.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Ready to download/verify models or install desktop service.")
        self.status_lbl.setObjectName("Muted")
        l4.addWidget(self.status_lbl)

        act_row = QHBoxLayout()
        self.warmup_btn = QPushButton(" Download & Warmup Models")
        self.warmup_btn.setIcon(get_icon("download", "#e4e4e7", 13))
        self.warmup_btn.setObjectName("Secondary")
        self.warmup_btn.clicked.connect(self._start_warmup)
        act_row.addWidget(self.warmup_btn)

        self.install_btn = QPushButton(" Install App & Systemd Service")
        self.install_btn.setIcon(get_icon("settings", "#e4e4e7", 13))
        self.install_btn.setObjectName("Secondary")
        self.install_btn.clicked.connect(self._install_desktop_app)
        act_row.addWidget(self.install_btn)
        l4.addLayout(act_row)
        root.addWidget(c4)

        root.addStretch()

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Cancel")
        close_btn.setObjectName("Secondary")
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)

        save_btn = QPushButton("Save Changes")
        save_btn.clicked.connect(self._save_and_close)
        footer.addWidget(save_btn)
        root.addLayout(footer)

    def _refresh_ollama(self):
        llm = LLMService(host=self.config.ollama_host)
        self.ollama_combo.clear()
        installed = llm.get_models() if llm.is_available() else []

        added = set()
        for m in installed:
            self.ollama_combo.addItem(f"{m} (Installed)", m)
            added.add(m)

        for code, label in RECOMMENDED_VI_MODELS:
            if code not in added:
                self.ollama_combo.addItem(label, code)

        # Match current config
        idx = self.ollama_combo.findData(self.config.ollama_model)
        if idx >= 0:
            self.ollama_combo.setCurrentIndex(idx)
        else:
            self.ollama_combo.setEditText(self.config.ollama_model)

    def _get_selected_ollama_model(self) -> str:
        data = self.ollama_combo.currentData()
        if data:
            return str(data)
        raw = self.ollama_combo.currentText().split("—")[0].replace("(Installed)", "").strip()
        return raw or "qwen2.5:3b"

    def _start_warmup(self):
        self.warmup_btn.setEnabled(False)
        bg_model = self.bg_combo.currentData()
        ollama_model = self._get_selected_ollama_model()

        self.worker = ModelWarmupWorker(bg_model, ollama_model)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, msg: str, val: int):
        self.status_lbl.setText(msg)
        self.progress_bar.setValue(val)

    def _on_finished(self, ok: bool, msg: str):
        self.warmup_btn.setEnabled(True)
        self.status_lbl.setText(msg if ok else f"Error: {msg}")
        if ok:
            self.config.setup_completed = True
            self._save_config_data()
            self._refresh_ollama()

    def _install_desktop_app(self):
        from ..installer import install_system_integration
        ok, msg = install_system_integration()
        self.status_lbl.setText(msg)
        if ok:
            QMessageBox.information(self, "Installation Complete", msg)

    def _save_config_data(self):
        self.config.bg_removal_model = self.bg_combo.currentData()
        self.config.ollama_model = self._get_selected_ollama_model()
        self.config.target_language = self.lang_combo.currentData()
        self.config.search_engine = self.engine_combo.currentData()
        save_config(self.config)

    def _save_and_close(self):
        self.config.setup_completed = True
        self._save_config_data()
        self.close()
