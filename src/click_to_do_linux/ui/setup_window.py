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
from ..ai.ocr import OCREngine, download_tessdata, tesseract_ready
from ..i18n import set_lang, t
from ..ai.segmentation import SegmentationEngine
from ..config import Config, get_config_dir, load_config, save_config
from .icons import get_icon

# (ollama tag, display label). Sizes are Ollama q4_K_M downloads; see README for the full table.
RECOMMENDED_VI_MODELS = [
    ("qwen3:4b", "Qwen3 4B  —  Cân bằng nhất / Best balance (2.5 GB)"),
    ("qwen2.5:3b", "Qwen2.5 3B  —  Nhanh, nhẹ / Fast & light (1.9 GB)"),
    ("gemma3:4b", "Gemma3 4B  —  Văn phong tự nhiên / Natural phrasing (3.4 GB)"),
    ("qwen3:1.7b", "Qwen3 1.7B  —  Siêu nhẹ CPU / Ultra-light CPU (1.4 GB)"),
    ("sailor2:1b", "Sailor2 1B  —  Tối ưu Đông Nam Á / SEA-tuned (1.1 GB)"),
    ("qwen3:8b", "Qwen3 8B  —  Chính xác cao / High accuracy (5.2 GB)"),
    ("sailor2:8b", "Sailor2 8B  —  Tiếng Việt tốt nhất ≤ 8B / Best ≤ 8B Vietnamese (5.2 GB)"),
    ("gemma3:12b", "Gemma3 12B  —  Chất lượng cao / High quality (8.2 GB)"),
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
            self.progress.emit(t("warm_ocr"), 15)
            OCREngine.warmup()

            if shutil.which("tesseract"):
                if not tesseract_ready():
                    self.progress.emit(t("warm_tess"), 35)
                    download_tessdata()
            else:
                self.progress.emit(t("warm_no_tess"), 35)

            self.progress.emit(t("warm_cutout", m=self.bg_model), 60)
            SegmentationEngine.get_session(self.bg_model)

            if self.pull_ollama_model and shutil.which("ollama"):
                self.progress.emit(t("warm_pull", m=self.pull_ollama_model), 80)
                subprocess.run(["ollama", "pull", self.pull_ollama_model], check=False)

            self.progress.emit(t("warm_ready"), 100)
            self.finished.emit(True, t("warm_done"))
        except Exception as e:
            self.finished.emit(False, str(e))


class SetupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.config: Config = load_config()
        set_lang(self.config.ui_language)
        self.setWindowTitle(t("set_title"))
        self.setFixedSize(600, 700)

        arrow_path = get_config_dir() / "chevron-down.svg"
        if not arrow_path.exists():
            arrow_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#a1a1aa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>',
                encoding="utf-8",
            )
        arrow_url = arrow_path.as_posix()

        self.setStyleSheet(f"""
            QWidget {{
                background-color: #09090b;
                color: #f4f4f5;
                font-family: "Inter", "Noto Sans", system-ui, sans-serif;
                font-size: 13px;
            }}
            QFrame#Card {{
                background-color: #121215;
                border: 1px solid #27272a;
                border-radius: 8px;
            }}
            QLabel#HeaderTitle {{
                font-size: 16px;
                font-weight: 600;
                color: #ffffff;
            }}
            QLabel#HeaderSub {{
                font-size: 12px;
                color: #71717a;
            }}
            QLabel#CardTitle {{
                font-size: 12px;
                font-weight: 600;
                color: #a1a1aa;
                background: transparent;
            }}
            QLabel#Muted {{
                font-size: 11px;
                color: #71717a;
                background: transparent;
            }}
            QComboBox {{
                background-color: #18181b;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 6px 30px 6px 12px;
                color: #e4e4e7;
                font-size: 12px;
                min-height: 24px;
            }}
            QComboBox:hover {{
                border: 1px solid #3f3f46;
            }}
            QComboBox:focus {{
                border: 1px solid #38bdf8;
            }}
            QComboBox:editable {{
                background: #18181b;
            }}
            QComboBox QLineEdit {{
                background: transparent;
                color: #e4e4e7;
                border: none;
                font-size: 12px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid #27272a;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
                background-color: #18181b;
            }}
            QComboBox::down-arrow {{
                image: url("{arrow_url}");
                width: 12px;
                height: 12px;
            }}
            QComboBox::down-arrow:hover {{
                image: url("{arrow_url}");
            }}
            QComboBox QAbstractItemView {{
                background-color: #18181b;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                selection-background-color: #27272a;
                selection-color: #38bdf8;
                color: #e4e4e7;
                padding: 4px;
                outline: none;
            }}
            QPushButton {{
                background-color: #f4f4f5;
                color: #09090b;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
                min-height: 22px;
            }}
            QPushButton:hover {{
                background-color: #ffffff;
            }}
            QPushButton:disabled {{
                background-color: #27272a;
                color: #71717a;
            }}
            QPushButton#Secondary {{
                background-color: #18181b;
                color: #e4e4e7;
                border: 1px solid #27272a;
                font-weight: 500;
                min-height: 22px;
            }}
            QPushButton#Secondary:hover {{
                background-color: #27272a;
                color: #ffffff;
                border: 1px solid #3f3f46;
            }}
            QPushButton#Danger {{
                background-color: #18181b;
                color: #f87171;
                border: 1px solid #3f1d1d;
                font-weight: 500;
                min-height: 22px;
            }}
            QPushButton#Danger:hover {{
                background-color: #2a1212;
                border: 1px solid #f87171;
            }}
            QProgressBar {{
                border: 1px solid #27272a;
                border-radius: 4px;
                background-color: #18181b;
                max-height: 6px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: #38bdf8;
                border-radius: 3px;
            }}
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
        sub = QLabel(t("set_sub"))
        sub.setObjectName("HeaderSub")
        hdr.addWidget(title)
        hdr.addWidget(sub)
        root.addLayout(hdr)

        # Card 1: Vision & Cutout Model
        c1, l1 = self._make_card()
        t1 = QLabel(t("card_cutout"))
        t1.setObjectName("CardTitle")
        l1.addWidget(t1)

        self.bg_combo = QComboBox()
        self.bg_combo.setMinimumHeight(32)
        self.bg_combo.addItem(t("cutout_fast"), "u2netp")
        self.bg_combo.addItem(t("cutout_precise"), "isnet-general-use")
        idx = self.bg_combo.findData(self.config.bg_removal_model)
        if idx >= 0:
            self.bg_combo.setCurrentIndex(idx)
        l1.addWidget(self.bg_combo)
        root.addWidget(c1)

        # Card 2: Vietnamese Local LLM (Ollama)
        c2, l2 = self._make_card()
        t2 = QLabel(t("card_llm"))
        t2.setObjectName("CardTitle")
        l2.addWidget(t2)

        row_llm = QHBoxLayout()
        self.ollama_combo = QComboBox()
        self.ollama_combo.setEditable(True)
        self.ollama_combo.setMinimumHeight(32)
        row_llm.addWidget(self.ollama_combo, stretch=1)

        ref_btn = QPushButton(t("refresh"))
        ref_btn.setObjectName("Secondary")
        ref_btn.setIcon(get_icon("refresh", "#e4e4e7", 13))
        ref_btn.setIconSize(QSize(13, 13))
        ref_btn.setMinimumHeight(32)
        ref_btn.setFixedWidth(96)
        ref_btn.clicked.connect(self._refresh_ollama)
        row_llm.addWidget(ref_btn)
        l2.addLayout(row_llm)

        rec_lbl = QLabel(t("llm_hint"))
        rec_lbl.setObjectName("Muted")
        rec_lbl.setWordWrap(True)
        l2.addWidget(rec_lbl)
        root.addWidget(c2)

        # Card 3: Target Language & Search Engine
        c3, l3 = self._make_card()
        t3 = QLabel(t("card_prefs"))
        t3.setObjectName("CardTitle")
        l3.addWidget(t3)

        pref_row = QHBoxLayout()
        self.lang_combo = QComboBox()
        self.lang_combo.setMinimumHeight(32)
        self.lang_combo.addItem(f"{t('pref_target')}: Tiếng Việt", "vi")
        self.lang_combo.addItem(f"{t('pref_target')}: English", "en")
        l_idx = self.lang_combo.findData(self.config.target_language)
        if l_idx >= 0:
            self.lang_combo.setCurrentIndex(l_idx)
        pref_row.addWidget(self.lang_combo)

        self.engine_combo = QComboBox()
        self.engine_combo.setMinimumHeight(32)
        self.engine_combo.addItem(f"{t('pref_search')}: Google", "google")
        self.engine_combo.addItem(f"{t('pref_search')}: DuckDuckGo", "duckduckgo")
        self.engine_combo.addItem(f"{t('pref_search')}: Bing", "bing")
        e_idx = self.engine_combo.findData(self.config.search_engine)
        if e_idx >= 0:
            self.engine_combo.setCurrentIndex(e_idx)
        pref_row.addWidget(self.engine_combo)
        l3.addLayout(pref_row)

        self.ui_lang_combo = QComboBox()
        self.ui_lang_combo.setMinimumHeight(32)
        self.ui_lang_combo.addItem(f"{t('pref_ui')}: {t('ui_auto')}", "auto")
        self.ui_lang_combo.addItem(f"{t('pref_ui')}: Tiếng Việt", "vi")
        self.ui_lang_combo.addItem(f"{t('pref_ui')}: English", "en")
        u_idx = self.ui_lang_combo.findData(self.config.ui_language)
        if u_idx >= 0:
            self.ui_lang_combo.setCurrentIndex(u_idx)
        l3.addWidget(self.ui_lang_combo)
        root.addWidget(c3)

        # Card 4: Model Cache & System Integration
        c4, l4 = self._make_card()
        t4 = QLabel(t("card_cache"))
        t4.setObjectName("CardTitle")
        l4.addWidget(t4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        l4.addWidget(self.progress_bar)

        self.status_lbl = QLabel(t("status_ready"))
        self.status_lbl.setObjectName("Muted")
        self.status_lbl.setWordWrap(True)
        l4.addWidget(self.status_lbl)

        act_row = QHBoxLayout()
        self.warmup_btn = QPushButton(t("btn_warmup"))
        self.warmup_btn.setIcon(get_icon("download", "#e4e4e7", 13))
        self.warmup_btn.setObjectName("Secondary")
        self.warmup_btn.setMinimumHeight(36)
        self.warmup_btn.clicked.connect(self._start_warmup)
        act_row.addWidget(self.warmup_btn)

        self.install_btn = QPushButton(t("btn_install"))
        self.install_btn.setIcon(get_icon("settings", "#e4e4e7", 13))
        self.install_btn.setObjectName("Secondary")
        self.install_btn.setMinimumHeight(36)
        self.install_btn.clicked.connect(self._install_desktop_app)
        act_row.addWidget(self.install_btn)
        l4.addLayout(act_row)

        act_row2 = QHBoxLayout()
        self.uninstall_btn = QPushButton(t("btn_uninstall"))
        self.uninstall_btn.setIcon(get_icon("power", "#f87171", 13))
        self.uninstall_btn.setObjectName("Danger")
        self.uninstall_btn.setMinimumHeight(36)
        self.uninstall_btn.clicked.connect(self._uninstall_desktop_app)
        act_row2.addWidget(self.uninstall_btn)

        self.about_btn = QPushButton(t("btn_about"))
        self.about_btn.setIcon(get_icon("sparkles", "#e4e4e7", 13))
        self.about_btn.setObjectName("Secondary")
        self.about_btn.setMinimumHeight(36)
        self.about_btn.clicked.connect(self._show_about)
        act_row2.addWidget(self.about_btn)
        l4.addLayout(act_row2)
        root.addWidget(c4)

        root.addStretch()

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton(t("btn_cancel"))
        close_btn.setObjectName("Secondary")
        close_btn.setMinimumHeight(32)
        close_btn.clicked.connect(self.close)
        footer.addWidget(close_btn)

        save_btn = QPushButton(t("btn_save"))
        save_btn.setMinimumHeight(32)
        save_btn.clicked.connect(self._save_and_close)
        footer.addWidget(save_btn)
        root.addLayout(footer)

    def _refresh_ollama(self):
        llm = LLMService(host=self.config.ollama_host)
        self.ollama_combo.clear()
        installed = llm.get_models() if llm.is_available() else []

        added = set()
        for m in installed:
            self.ollama_combo.addItem(f"{m} ({t('installed_tag')})", m)
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
        raw = self.ollama_combo.currentText().split("—")[0].replace(f"({t('installed_tag')})", "").strip()
        return raw or "qwen3:4b"

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
        self.status_lbl.setText(msg if ok else t("status_error") + msg)
        if ok:
            self.config.setup_completed = True
            self._save_config_data()
            self._refresh_ollama()

    def _install_desktop_app(self):
        from ..installer import install_system_integration
        ok, msg = install_system_integration()
        self.status_lbl.setText(msg)
        if ok:
            QMessageBox.information(self, t("install_done"), msg)

    def _uninstall_desktop_app(self):
        from ..installer import uninstall_system_integration

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(t("uninstall_title"))
        box.setText(t("uninstall_confirm"))
        purge = QCheckBox(t("uninstall_purge"))
        box.setCheckBox(purge)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        ok, msg = uninstall_system_integration(purge_data=purge.isChecked())
        self.status_lbl.setText(msg)
        QMessageBox.information(self, t("uninstall_done"), msg)

    def _show_about(self):
        QMessageBox.information(self, t("about_title"), t("about_body"))

    def _save_config_data(self):
        self.config.ui_language = self.ui_lang_combo.currentData()
        self.config.bg_removal_model = self.bg_combo.currentData()
        self.config.ollama_model = self._get_selected_ollama_model()
        self.config.target_language = self.lang_combo.currentData()
        self.config.search_engine = self.engine_combo.currentData()
        save_config(self.config)

    def _save_and_close(self):
        self.config.setup_completed = True
        self._save_config_data()
        self.close()
