"""First-Run Setup & Local Model Manager GUI for Click to Do Linux."""

import shutil
import subprocess
from pathlib import Path
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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


class ModelWarmupWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(bool, str)

    def __init__(self, bg_model: str, pull_ollama_model: str = ""):
        super().__init__()
        self.bg_model = bg_model
        self.pull_ollama_model = pull_ollama_model

    def run(self):
        try:
            self.progress.emit("Đang nạp & kiểm tra mô hình RapidOCR (PP-OCRv4)...", 25)
            OCREngine.warmup()

            self.progress.emit(f"Đang tải & khởi tạo mô hình tách nền ({self.bg_model})...", 60)
            SegmentationEngine.get_session(self.bg_model)

            if self.pull_ollama_model and shutil.which("ollama"):
                self.progress.emit(f"Đang tải LLM cục bộ '{self.pull_ollama_model}' qua Ollama...", 80)
                subprocess.run(["ollama", "pull", self.pull_ollama_model], check=False)

            self.progress.emit("Hoàn tất chuẩn bị mô hình cục bộ!", 100)
            self.finished.emit(True, "Tất cả mô hình đã sẵn sàng trong bộ nhớ cache.")
        except Exception as e:
            self.finished.emit(False, str(e))


class SetupWindow(QWidget):
    """GUI Manager for initializing local models, Ollama LLM, and Niri config."""

    def __init__(self):
        super().__init__()
        self.config: Config = load_config()
        self.setWindowTitle("Click to Do Linux — Cài đặt & Quản lý Local AI Models")
        self.setFixedSize(560, 480)
        self.setStyleSheet("""
            QWidget { background-color: #14161c; color: #f1f5f9; font-family: sans-serif; font-size: 13px; }
            QLabel#Title { font-size: 18px; font-weight: bold; color: #38bdf8; }
            QLabel#Section { font-size: 13px; font-weight: bold; color: #c084fc; margin-top: 8px; }
            QComboBox, QLineEdit {
                background-color: #1e222d; border: 1px solid #334155;
                border-radius: 6px; padding: 6px 10px; color: #f8fafc;
            }
            QPushButton {
                background-color: #2563eb; color: white; border: none;
                border-radius: 6px; padding: 8px 14px; font-weight: 600;
            }
            QPushButton:hover { background-color: #1d4ed8; }
            QPushButton#Secondary { background-color: #334155; }
            QPushButton#Secondary:hover { background-color: #475569; }
            QProgressBar {
                border: 1px solid #334155; border-radius: 6px; text-align: center; background: #1e222d;
            }
            QProgressBar::chunk { background-color: #10b981; border-radius: 5px; }
        """)
        self._build_ui()
        self._refresh_ollama()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)

        title = QLabel("⚡ Click to Do Linux — Quản lý Model & Cài đặt")
        title.setObjectName("Title")
        layout.addWidget(title)

        # 1. Cutout Model Selection
        sec1 = QLabel("1. Mô hình Tách nền AI (ONNX Local)")
        sec1.setObjectName("Section")
        layout.addWidget(sec1)

        self.bg_combo = QComboBox()
        self.bg_combo.addItem("u2netp (Siêu nhẹ ~4.7MB - Phản hồi tức thì, khuyên dùng)", "u2netp")
        self.bg_combo.addItem("isnet-general-use (Chính xác cao ~170MB - Tách chi tiết)", "isnet-general-use")
        idx = self.bg_combo.findData(self.config.bg_removal_model)
        if idx >= 0:
            self.bg_combo.setCurrentIndex(idx)
        layout.addWidget(self.bg_combo)

        # 2. Ollama Local LLM
        sec2 = QLabel("2. Mô hình Ngôn ngữ Cục bộ (Ollama Local LLM)")
        sec2.setObjectName("Section")
        layout.addWidget(sec2)

        ollama_row = QHBoxLayout()
        self.ollama_combo = QComboBox()
        self.ollama_combo.setEditable(True)
        ollama_row.addWidget(self.ollama_combo, stretch=1)

        refresh_btn = QPushButton("🔄 Quét Ollama")
        refresh_btn.setObjectName("Secondary")
        refresh_btn.clicked.connect(self._refresh_ollama)
        ollama_row.addWidget(refresh_btn)
        layout.addLayout(ollama_row)

        # 3. Download & Warmup Progress
        sec3 = QLabel("3. Khởi tạo & Tải trước Model (Tránh đơ lần chạy đầu)")
        sec3.setObjectName("Section")
        layout.addWidget(sec3)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("Nhấn 'Tải & Khởi tạo Model' để lưu sẵn model vào máy.")
        self.status_lbl.setStyleSheet("color: #94a3b8; font-size: 12px;")
        layout.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.warmup_btn = QPushButton("⬇️ Tải & Khởi tạo Model ngay")
        self.warmup_btn.clicked.connect(self._start_warmup)
        btn_row.addWidget(self.warmup_btn)

        self.niri_btn = QPushButton("⚙️ Tự động gắn Rule & Phím tắt vào Niri")
        self.niri_btn.setObjectName("Secondary")
        self.niri_btn.clicked.connect(self._inject_niri_config)
        btn_row.addWidget(self.niri_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

        # Footer Save
        footer = QHBoxLayout()
        footer.addStretch()
        save_btn = QPushButton("✓ Lưu cấu hình & Đóng")
        save_btn.clicked.connect(self._save_and_close)
        footer.addWidget(save_btn)
        layout.addLayout(footer)

    def _refresh_ollama(self):
        llm = LLMService(host=self.config.ollama_host)
        self.ollama_combo.clear()
        if llm.is_available():
            models = llm.get_models()
            for m in models:
                self.ollama_combo.addItem(m)
            if self.config.ollama_model in models:
                self.ollama_combo.setCurrentText(self.config.ollama_model)
            elif not models:
                self.ollama_combo.setEditText("qwen2.5:3b")
        else:
            self.ollama_combo.setEditText(self.config.ollama_model)
            self.status_lbl.setText("⚠️ Ollama chưa bật. Bạn vẫn dùng được OCR & Tách nền bình thường.")

    def _start_warmup(self):
        self.warmup_btn.setEnabled(False)
        bg_model = self.bg_combo.currentData()
        ollama_model = self.ollama_combo.currentText().strip()

        self.worker = ModelWarmupWorker(bg_model, ollama_model)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, msg: str, val: int):
        self.status_lbl.setText(msg)
        self.progress_bar.setValue(val)

    def _on_finished(self, ok: bool, msg: str):
        self.warmup_btn.setEnabled(True)
        if ok:
            self.status_lbl.setText(f"✅ {msg}")
            self.config.setup_completed = True
            self._save_config_data()
        else:
            self.status_lbl.setText(f"❌ Lỗi: {msg}")

    def _inject_niri_config(self):
        niri_cfg = Path.home() / ".config" / "niri" / "config.kdl"
        if not niri_cfg.exists():
            QMessageBox.warning(self, "Niri Config", f"Không tìm thấy {niri_cfg}")
            return

        content = niri_cfg.read_text(encoding="utf-8")
        if "click-to-do-overlay" in content:
            QMessageBox.information(self, "Niri Config", "Cấu hình Click to Do đã có sẵn trong config.kdl!")
            return

        bin_path = Path.cwd() / ".venv" / "bin" / "click-to-do"
        cmd_str = str(bin_path) if bin_path.exists() else "click-to-do"

        rule_snippet = f"""
// --- Click to Do Linux Overlay Rule & Daemon ---
spawn-at-startup "{cmd_str}" "daemon"

window-rule {{
    match app-id="^click-to-do-overlay$"
    open-floating true
    open-fullscreen true
    border {{ off; }}
    shadow {{ off; }}
}}
"""
        with open(niri_cfg, "a", encoding="utf-8") as f:
            f.write(rule_snippet)

        QMessageBox.information(
            self,
            "Đã cập nhật Niri",
            f"Đã thêm window-rule và spawn-at-startup vào {niri_cfg}.\n\n"
            f"Hãy thêm dòng sau vào mục binds {{ ... }} của bạn:\n"
            f'Mod+Q {{ spawn "{cmd_str}" "capture"; }}',
        )

    def _save_config_data(self):
        self.config.bg_removal_model = self.bg_combo.currentData()
        self.config.ollama_model = self.ollama_combo.currentText().strip()
        save_config(self.config)

    def _save_and_close(self):
        self.config.setup_completed = True
        self._save_config_data()
        self.close()
