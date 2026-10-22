"""Clean, minimalist Settings & Local AI Model Manager (Raycast/Linear inspired, zero AI slop)."""

import os
import shutil
import subprocess
from pathlib import Path
from PyQt6.QtCore import QSignalBlocker, QSize, QTime, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CheckBox,
    ComboBox,
    EditableComboBox,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    SpinBox,
    TabCloseButtonDisplayMode,
    TabWidget,
    TimeEdit,
    TogglePushButton,
)

from ..ai.llm import LLMService
from .. import npu as npu_mod
from ..ai.ocr import OCREngine, download_tessdata, tesseract_ready
from ..i18n import set_lang, t
from ..ai.segmentation import SegmentationEngine
from ..config import Config, get_config_dir, load_config, save_config
from .. import compositor as comp_mod

DEFAULT_CAPTURE = comp_mod.DEFAULT_CAPTURE_KEY
DEFAULT_COLOR = comp_mod.DEFAULT_COLOR_KEY
from .icons import get_icon
from .fluent_theme import sync_fluent_theme
from .typography import label as app_label
try:
    from qfluentwidgets import InfoBar, InfoBarPosition
except Exception:  # pragma: no cover
    InfoBar = None
    InfoBarPosition = None
from .palette import apply_input_palette, theme_color, theme_colors, theme_stylesheet

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
    theme_changed = pyqtSignal(str)

    def __init__(self, embedded=False, productivity_service=None):
        super().__init__()
        self.embedded = embedded
        self.productivity_service = productivity_service
        self.config: Config = load_config()
        self.theme = self.config.ui_theme if self.config.ui_theme in ("light", "dark") else "dark"
        set_lang(self.config.ui_language)
        self.setObjectName("SettingsPage")
        self.setWindowTitle(t("set_title"))
        if not embedded:
            self.setMinimumSize(640, 560)
            self.resize(780, 760)

        # Layout, cards and typography only. Every control is a Fluent widget
        # and keeps the stylesheet shipped by the library.
        self._base_stylesheet = """
            QWidget {
                color: #f4f4f5;
            }
            QWidget#SettingsPage { background-color: #09090b; }
            QStackedWidget { background: transparent; }
            QLabel { background: transparent; }
            ScrollArea > QWidget > QWidget { background: transparent; }
            QFrame#Card {
                background-color: #121215;
                border: 1px solid #27272a;
                border-radius: 12px;
            }
            QLabel#HeaderTitle { font-size: 16px; font-weight: 600; }
            QLabel#HeaderSub { font-size: 12px; }
            QLabel#CardTitle { font-size: 12px; font-weight: 600; background: transparent; }
            QLabel#Muted { font-size: 11px; background: transparent; }
        """
        self._build_ui()
        self.set_theme(self.theme)
        QTimer.singleShot(0, self._refresh_ollama)

    def _set_icon(self, button, name, color, size):
        button.setProperty("theme_icon", (name, color, size))
        button.setIcon(get_icon(name, theme_color(color, self.theme), size))

    def _set_rich_text(self, label, source):
        label.setProperty("rich_source", source)
        label.setText(theme_colors(source, self.theme))

    def set_theme(self, theme):
        self.theme = "light" if theme == "light" else "dark"
        self.config.ui_theme = self.theme
        sync_fluent_theme(self.theme)
        style = theme_stylesheet(self._base_stylesheet, self.theme)
        self.setStyleSheet(style)
        apply_input_palette(self, self.theme)
        for button in self.findChildren(PushButton):
            metadata = button.property("theme_icon")
            if metadata:
                name, color, size = metadata
                button.setIcon(get_icon(name, theme_color(color, self.theme), size))
        for label in self.findChildren(QLabel):
            source = label.property("rich_source")
            if source:
                label.setText(theme_colors(source, self.theme))
        for name, button in getattr(self, "theme_choices", {}).items():
            blocker = QSignalBlocker(button)
            button.setChecked(name == self.theme)
            del blocker

    def _choose_theme(self, theme):
        self.set_theme(theme)
        config = load_config()
        config.ui_theme = self.theme
        save_config(config)
        self.theme_changed.emit(self.theme)

    def _scroll_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 8, 10)
        layout.setSpacing(14)
        scroll = ScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        # The viewport fills with the palette colour unless it is turned off.
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(page)
        return scroll, layout

    def _build_appearance_tab(self):
        page, layout = self._scroll_page()
        card, content = self._make_card()
        title = app_label(t("theme_heading"), "card_title")
        content.addWidget(title)
        hint = app_label(t("theme_hint"), "muted")
        hint.setWordWrap(True)
        content.addWidget(hint)
        choices = QHBoxLayout()
        self.theme_choices = {}
        for theme, text, icon in (("light", "theme_light", "sun"), ("dark", "theme_dark", "moon")):
            button = TogglePushButton(t(text))
            button.setMinimumHeight(40)
            self._set_icon(button, icon, "#38bdf8", 18)
            button.clicked.connect(lambda checked=False, selected=theme: self._choose_theme(selected))
            choices.addWidget(button)
            self.theme_choices[theme] = button
        content.addLayout(choices)
        layout.addWidget(card)
        layout.addStretch()
        self.tabs.insertTab(0, page, t("tab_appearance"))

    def _settings_row(self, layout, label, control):
        row = QHBoxLayout()
        row.setSpacing(18)
        text = app_label(label, "body")
        text.setWordWrap(True)
        row.addWidget(text, 1)
        row.addWidget(control)
        layout.addLayout(row)

    def _build_workday_tab(self):
        service = self.productivity_service
        page, layout = self._scroll_page()
        card, content = self._make_card()
        title = app_label(t("office_focus_section"), "card_title")
        content.addWidget(title)
        hint = app_label(t("workday_autosave"), "muted")
        hint.setWordWrap(True)
        content.addWidget(hint)
        self.duration_spins = {}
        for mode, key, low, high in (("focus", "office_focus_duration", 10, 90), ("short_break", "office_short_duration", 3, 30), ("long_break", "office_long_duration", 10, 45)):
            spin = SpinBox()
            spin.setRange(low, high)
            spin.setSuffix(" " + t("office_minutes"))
            spin.setValue(service.timer_minutes(mode))
            spin.valueChanged.connect(lambda value, selected=mode: service.set_timer_minutes(selected, value))
            self.duration_spins[mode] = spin
            self._settings_row(content, t(key), spin)
        self.long_break_spin = SpinBox()
        self.long_break_spin.setRange(2, 8)
        self.long_break_spin.setSuffix(" " + t("office_sessions"))
        self.long_break_spin.setValue(service.long_break_every)
        self.long_break_spin.valueChanged.connect(service.set_long_break_every)
        self._settings_row(content, t("office_long_every"), self.long_break_spin)
        layout.addWidget(card)
        card, content = self._make_card()
        title = app_label(t("office_health_section"), "card_title")
        content.addWidget(title)
        self.reminder_controls = {}
        for key, label in (("water", "office_water"), ("movement", "office_movement")):
            row = QHBoxLayout()
            enabled = CheckBox(t(label))
            enabled.toggled.connect(lambda checked, selected=key: service.set_reminder_enabled(selected, checked))
            interval = SpinBox()
            interval.setRange(15, 240)
            interval.setSingleStep(5)
            interval.setPrefix(t("office_every") + " ")
            interval.setSuffix(" " + t("office_minutes"))
            interval.valueChanged.connect(lambda value, selected=key: service.set_reminder_interval(selected, value))
            row.addWidget(enabled, 1)
            row.addWidget(interval)
            content.addLayout(row)
            self.reminder_controls[key] = (enabled, interval)
        layout.addWidget(card)
        card, content = self._make_card()
        self.schedule_enabled = CheckBox(t("office_schedule"))
        self.schedule_enabled.toggled.connect(service.set_schedule_enabled)
        content.addWidget(self.schedule_enabled)
        self.weekdays_only = CheckBox(t("office_weekdays"))
        self.weekdays_only.toggled.connect(service.set_weekdays_only)
        content.addWidget(self.weekdays_only)
        self.work_start = TimeEdit()
        self.work_end = TimeEdit()
        for edit in (self.work_start, self.work_end):
            edit.setDisplayFormat("HH:mm")
            edit.timeChanged.connect(self._set_work_hours)
        self._settings_row(content, t("workday_start"), self.work_start)
        self._settings_row(content, t("workday_end"), self.work_end)
        layout.addWidget(card)
        background = app_label(t("shell_background_hint"), "muted")
        background.setWordWrap(True)
        layout.addWidget(background)
        layout.addStretch()
        self.tabs.insertTab(0, page, t("tab_workday"))
        self.tabs.setCurrentIndex(0)
        service.state_changed.connect(self._refresh_workday)
        self._refresh_workday()

    def _set_work_hours(self):
        self.productivity_service.set_work_hours(self.work_start.time().toString("HH:mm"), self.work_end.time().toString("HH:mm"))

    def _refresh_workday(self):
        service = self.productivity_service
        for mode, spin in self.duration_spins.items():
            blocker = QSignalBlocker(spin)
            if not spin.hasFocus():
                spin.setValue(service.timer_minutes(mode))
            spin.setEnabled(not service.timer_running)
            del blocker
        blocker = QSignalBlocker(self.long_break_spin)
        self.long_break_spin.setValue(service.long_break_every)
        self.long_break_spin.setEnabled(not service.timer_running)
        del blocker
        for key, (enabled, interval) in self.reminder_controls.items():
            data = service.reminder(key)
            blockers = (QSignalBlocker(enabled), QSignalBlocker(interval))
            enabled.setChecked(data["enabled"])
            if not interval.hasFocus():
                interval.setValue(data["interval_minutes"])
            interval.setEnabled(data["enabled"])
            del blockers
        schedule = service.schedule
        for control, value in ((self.schedule_enabled, schedule["enabled"]), (self.weekdays_only, schedule["weekdays_only"])):
            blocker = QSignalBlocker(control)
            control.setChecked(value)
            del blocker
        for control, key in ((self.work_start, "start"), (self.work_end, "end")):
            blocker = QSignalBlocker(control)
            if not control.hasFocus():
                control.setTime(QTime.fromString(schedule[key], "HH:mm"))
            control.setEnabled(schedule["enabled"])
            del blocker
        self.weekdays_only.setEnabled(schedule["enabled"])

    def _make_card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("Card")
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(14, 12, 14, 12)
        vbox.setSpacing(8)
        return card, vbox

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24 if self.embedded else 20, 16, 24 if self.embedded else 20, 18)
        root.setSpacing(12)

        # Header
        hdr = QVBoxLayout()
        hdr.setSpacing(2)
        title = app_label("Click to Do", "title")
        sub = app_label(t("set_sub"), "caption")
        hdr.addWidget(title)
        hdr.addWidget(sub)
        if not self.embedded:
            root.addLayout(hdr)

        self.tabs = TabWidget()
        # The tabs are static, the close and add buttons would only confuse.
        self.tabs.tabBar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)
        self.tabs.tabBar.addButton.hide()
        root.addWidget(self.tabs, stretch=1)
        pages = []
        for title_key in ("tab_general", "tab_shortcuts", "tab_system"):
            page = QWidget()
            lay = QVBoxLayout(page)
            lay.setContentsMargins(0, 12, 0, 0)
            lay.setSpacing(12)
            scroll = ScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            # The viewport fills with the palette colour unless it is turned off.
            scroll.viewport().setAutoFillBackground(False)
            scroll.setWidget(page)
            self.tabs.addTab(scroll, t(title_key))
            if title_key == "tab_general":
                self._general_page = scroll
            pages.append(lay)
        p_general, p_keys, p_system = pages

        # Card 1: Vision & Cutout Model
        c1, l1 = self._make_card()
        t1 = app_label(t("card_cutout"), "card_title")
        l1.addWidget(t1)

        self.bg_combo = ComboBox()
        self.bg_combo.setMinimumHeight(32)
        self.bg_combo.addItem(t("cutout_fast"), "u2netp")
        self.bg_combo.addItem(t("cutout_precise"), "isnet-general-use")
        idx = self.bg_combo.findData(self.config.bg_removal_model)
        if idx >= 0:
            self.bg_combo.setCurrentIndex(idx)
        l1.addWidget(self.bg_combo)
        # OCR text-line detection backend: the NPU choice only exists on machines with an NPU
        if npu_mod.detect().present or self.config.ocr_det_backend == "npu":
            self.det_combo = ComboBox()
            self.det_combo.setMinimumHeight(32)
            self.det_combo.addItem(t("ocr_det_cpu"), "cpu")
            self.det_combo.addItem(t("ocr_det_npu"), "npu")
            self.det_combo.setCurrentIndex(max(0, self.det_combo.findData(self.config.ocr_det_backend)))
            l1.addWidget(self.det_combo)
        else:
            self.det_combo = None
        p_general.addWidget(c1)

        # Card 2: Vietnamese Local LLM (Ollama)
        c2, l2 = self._make_card()
        t2 = app_label(t("card_llm"), "card_title")
        l2.addWidget(t2)

        row_be = QHBoxLayout()
        self.backend_combo = ComboBox()
        self.backend_combo.setMinimumHeight(32)
        self.backend_combo.addItem(t("llm_backend_ollama"), "ollama")
        # The NPU choice is offered only on machines that actually expose an NPU (or if already selected)
        if npu_mod.detect().present or self.config.llm_backend == "openai":
            self.backend_combo.addItem(t("llm_backend_npu"), "openai")
        be_idx = self.backend_combo.findData(self.config.llm_backend)
        self.backend_combo.setCurrentIndex(max(0, be_idx))
        self.backend_combo.currentIndexChanged.connect(self._on_backend_changed)
        row_be.addWidget(self.backend_combo, stretch=1)
        self.keep_combo = ComboBox()
        self.keep_combo.setMinimumHeight(32)
        for val, lbl in (("0", t("keep_now")), ("2m", "2 min"), ("10m", "10 min"), ("-1", t("keep_never"))):
            self.keep_combo.addItem(f"{t('llm_keepalive')}: {lbl}", val)
        k_idx = self.keep_combo.findData(self.config.llm_keep_alive)
        self.keep_combo.setCurrentIndex(k_idx if k_idx >= 0 else 1)
        row_be.addWidget(self.keep_combo, stretch=1)
        l2.addLayout(row_be)

        row_llm = QHBoxLayout()
        self.ollama_combo = EditableComboBox()
        self.ollama_combo.setMinimumHeight(32)
        row_llm.addWidget(self.ollama_combo, stretch=1)

        ref_btn = PushButton(t("refresh"))
        self._set_icon(ref_btn, "refresh", "#e4e4e7", 13)
        ref_btn.setIconSize(QSize(13, 13))
        ref_btn.setMinimumHeight(32)
        ref_btn.setMinimumWidth(110)
        ref_btn.clicked.connect(self._refresh_ollama)
        row_llm.addWidget(ref_btn)
        l2.addLayout(row_llm)

        rec_lbl = app_label(t("llm_hint"), "body")
        self.llm_hint_lbl = rec_lbl
        rec_lbl.setObjectName("Muted")
        rec_lbl.setWordWrap(True)
        l2.addWidget(rec_lbl)
        p_general.addWidget(c2)

        # Card 3: Target Language & Search Engine
        c3, l3 = self._make_card()
        t3 = app_label(t("card_prefs"), "card_title")
        l3.addWidget(t3)

        pref_row = QHBoxLayout()
        self.lang_combo = ComboBox()
        self.lang_combo.setMinimumHeight(32)
        self.lang_combo.addItem(f"{t('pref_target')}: Tiếng Việt", "vi")
        self.lang_combo.addItem(f"{t('pref_target')}: English", "en")
        l_idx = self.lang_combo.findData(self.config.target_language)
        if l_idx >= 0:
            self.lang_combo.setCurrentIndex(l_idx)
        pref_row.addWidget(self.lang_combo)

        self.engine_combo = ComboBox()
        self.engine_combo.setMinimumHeight(32)
        self.engine_combo.addItem(f"{t('pref_search')}: Google", "google")
        self.engine_combo.addItem(f"{t('pref_search')}: DuckDuckGo", "duckduckgo")
        self.engine_combo.addItem(f"{t('pref_search')}: Bing", "bing")
        e_idx = self.engine_combo.findData(self.config.search_engine)
        if e_idx >= 0:
            self.engine_combo.setCurrentIndex(e_idx)
        pref_row.addWidget(self.engine_combo)
        l3.addLayout(pref_row)

        self.ui_lang_combo = ComboBox()
        self.ui_lang_combo.setMinimumHeight(32)
        self.ui_lang_combo.addItem(f"{t('pref_ui')}: {t('ui_auto')}", "auto")
        self.ui_lang_combo.addItem(f"{t('pref_ui')}: Tiếng Việt", "vi")
        self.ui_lang_combo.addItem(f"{t('pref_ui')}: English", "en")
        u_idx = self.ui_lang_combo.findData(self.config.ui_language)
        if u_idx >= 0:
            self.ui_lang_combo.setCurrentIndex(u_idx)
        l3.addWidget(self.ui_lang_combo)
        p_general.addWidget(c3)

        # Card 4: Model Cache & System Integration
        c4, l4 = self._make_card()
        t4 = app_label(t("card_cache"), "card_title")
        l4.addWidget(t4)

        self.progress_bar = ProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        l4.addWidget(self.progress_bar)

        self.status_lbl = app_label(t("status_ready"), "muted")
        self.status_lbl.setWordWrap(True)
        l4.addWidget(self.status_lbl)

        act_row = QHBoxLayout()
        self.warmup_btn = PushButton(t("btn_warmup"))
        self._set_icon(self.warmup_btn, "download", "#e4e4e7", 13)
        self.warmup_btn.setMinimumHeight(36)
        self.warmup_btn.clicked.connect(self._start_warmup)
        act_row.addWidget(self.warmup_btn)

        self.install_btn = PushButton(t("btn_install"))
        self._set_icon(self.install_btn, "settings", "#e4e4e7", 13)
        self.install_btn.setMinimumHeight(36)
        self.install_btn.clicked.connect(self._install_desktop_app)
        act_row.addWidget(self.install_btn)
        l4.addLayout(act_row)

        act_row2 = QHBoxLayout()
        self.uninstall_btn = PushButton(t("btn_uninstall"))
        self._set_icon(self.uninstall_btn, "power", "#f87171", 13)
        self.uninstall_btn.setObjectName("Danger")
        self.uninstall_btn.setMinimumHeight(36)
        self.uninstall_btn.clicked.connect(self._uninstall_desktop_app)
        act_row2.addWidget(self.uninstall_btn)

        self.about_btn = PushButton(t("btn_about"))
        self._set_icon(self.about_btn, "sparkles", "#e4e4e7", 13)
        self.about_btn.setMinimumHeight(36)
        self.about_btn.clicked.connect(self._show_about)
        act_row2.addWidget(self.about_btn)
        l4.addLayout(act_row2)
        p_system.addWidget(self._build_diag_card())
        p_system.addWidget(c4)
        p_general.addStretch()
        p_system.addStretch()
        self._build_shortcuts_tab(p_keys)

        self._build_appearance_tab()
        if self.productivity_service is not None:
            self._build_workday_tab()

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = PushButton(t("btn_cancel"))
        close_btn.setMinimumHeight(32)
        close_btn.clicked.connect(self.close)
        if not self.embedded:
            footer.addWidget(close_btn)

        self.apply_btn = PushButton(t("btn_apply")) if not self.embedded else PrimaryPushButton(t("btn_apply"))
        self.apply_btn.setMinimumHeight(32)
        self.apply_btn.clicked.connect(self._apply)
        footer.addWidget(self.apply_btn)

        save_btn = PrimaryPushButton(t("btn_save"))
        save_btn.setMinimumHeight(32)
        save_btn.clicked.connect(self._save_and_close)
        if not self.embedded:
            footer.addWidget(save_btn)
        root.addLayout(footer)
        if self.embedded:
            self.tabs.currentChanged.connect(self._sync_apply_action)
            self._sync_apply_action()

    def _sync_apply_action(self, index=None):
        self.apply_btn.setVisible(self.tabs.currentWidget() is self._general_page)

    def _on_backend_changed(self):
        npu_mode = self.backend_combo.currentData() == "openai"
        self.keep_combo.setEnabled(not npu_mode)
        self.llm_hint_lbl.setText(t("llm_npu_hint") if npu_mode else t("llm_hint"))
        self.config.llm_backend = self.backend_combo.currentData()
        self._refresh_ollama()

    def _refresh_ollama(self):
        llm = LLMService.from_config(self.config)
        npu_mode = self.config.llm_backend == "openai"
        self.keep_combo.setEnabled(not npu_mode)
        self.llm_hint_lbl.setText(t("llm_npu_hint") if npu_mode else t("llm_hint"))
        self.ollama_combo.clear()
        installed = llm.get_models() if llm.is_available() else []
        if self.config.llm_backend == "openai":
            for m in installed:
                self.ollama_combo.addItem(f"{m} ({t('installed_tag')})", m)
            idx = self.ollama_combo.findData(self.config.openai_model)
            if idx >= 0:
                self.ollama_combo.setCurrentIndex(idx)
            else:
                self.ollama_combo.setText(self.config.openai_model)
            return

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
            self.ollama_combo.setText(self.config.ollama_model)

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

    # ------------------------------------------------------------ diagnostics
    def _build_diag_card(self) -> QFrame:
        card, lay = self._make_card()
        ttl = app_label(t("card_diag"), "card_title")
        lay.addWidget(ttl)
        self.diag_lbl = app_label("", "muted")
        self.diag_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.diag_lbl.setWordWrap(True)
        lay.addWidget(self.diag_lbl)
        rb = PushButton(t("refresh"))
        self._set_icon(rb, "refresh", "#e4e4e7", 13)
        rb.clicked.connect(self._refresh_diag)
        lay.addWidget(rb)
        self._refresh_diag()
        return card

    def _refresh_diag(self):
        def row(ok: bool, label: str, hint: str = "") -> str:
            mark = '<span style="color:#4ade80">●</span>' if ok else '<span style="color:#f87171">●</span>'
            extra = f' <span style="color:#a1a1aa">— {hint}</span>' if (hint and not ok) else ""
            return f"{mark}&nbsp; {label}{extra}"

        c = comp_mod.detect()
        llm = LLMService(host=self.config.ollama_host)
        ollama_up = shutil.which("ollama") is not None and llm.is_available()
        npu = npu_mod.detect()
        service_on = False
        try:
            service_on = subprocess.run(
                ["systemctl", "--user", "is-active", "--quiet", "click-to-do.service"], timeout=2
            ).returncode == 0
        except Exception:
            pass
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")).expanduser()
        service_on = service_on or (config_home / "autostart" / "click-to-do.desktop").is_file()
        rows = [
            row(c.id != "generic", f"{t('diag_compositor')}: <b>{c.label}</b>", t("diag_unknown")),
            row(bool(shutil.which("grim")), "grim", t("diag_install", p="grim")),
            row(bool(shutil.which("wl-copy")), "wl-clipboard", t("diag_install", p="wl-clipboard")),
            row(bool(shutil.which("tesseract")), "Tesseract (OCR tiếng Việt)", t("diag_install", p="tesseract")),
            row(tesseract_ready(), t("diag_tessdata"), t("diag_tessdata_hint")),
            row(ollama_up, "Ollama", t("diag_ollama_hint")),
            row(npu.present, f"{t('diag_npu')}: <b>{npu.name or '—'}</b> ({npu.driver or '?'})", t("diag_npu_none")),
        ]
        if npu.present and npu.name.startswith("AMD"):
            rows += [
                row(npu.flm, t("diag_flm"), t("diag_flm_hint")),
                row(npu.memlock_ok, t("diag_memlock"), t("diag_memlock_hint")),
            ]
        rows += [
            row(service_on, t("diag_service"), t("diag_service_hint")),
        ]
        self._set_rich_text(self.diag_lbl, "<br>".join(rows))

    # ------------------------------------------------------------ shortcuts tab
    def _build_shortcuts_tab(self, layout: QVBoxLayout):
        self.comp = comp_mod.detect()

        card, lay = self._make_card()
        ttl = app_label(t("card_detect"), "card_title")
        lay.addWidget(ttl)
        self.comp_lbl = app_label("", "body")
        self.comp_lbl.setTextFormat(Qt.TextFormat.RichText)
        self.comp_lbl.setWordWrap(True)
        lay.addWidget(self.comp_lbl)

        self.comp_combo = ComboBox()
        self.comp_combo.setMinimumHeight(32)
        for cid, nm in (
            ("niri", "Niri"), ("umbriel", "Umbriel"), ("hyprland", "Hyprland"), ("sway", "Sway"),
            ("river", "River"), ("labwc", "labwc"), ("wayfire", "Wayfire"),
            ("kde", "KDE Plasma"), ("gnome", "GNOME"), ("cosmic", "COSMIC"), ("generic", t("other")),
        ):
            self.comp_combo.addItem(nm, cid)
        self.comp_combo.setCurrentIndex(max(0, self.comp_combo.findData(self.comp.id)))
        self.comp_combo.currentIndexChanged.connect(self._on_comp_changed)
        lay.addWidget(self.comp_combo)
        layout.addWidget(card)

        card2, lay2 = self._make_card()
        t2 = app_label(t("card_keys"), "card_title")
        lay2.addWidget(t2)
        row = QHBoxLayout()
        self.cap_key = LineEdit()
        self.cap_key.setText(DEFAULT_CAPTURE)
        self.cap_key.setPlaceholderText(t("key_capture"))
        self.col_key = LineEdit()
        self.col_key.setText(DEFAULT_COLOR)
        self.col_key.setPlaceholderText(t("key_color"))
        for lab, edit in ((t("key_capture"), self.cap_key), (t("key_color"), self.col_key)):
            col = QVBoxLayout()
            m = app_label(lab, "muted")
            col.addWidget(m)
            col.addWidget(edit)
            row.addLayout(col)
            edit.textChanged.connect(self._refresh_snippet)
        lay2.addLayout(row)
        self.key_note = app_label("", "muted")
        self.key_note.setTextFormat(Qt.TextFormat.RichText)
        self.key_note.setWordWrap(True)
        lay2.addWidget(self.key_note)
        layout.addWidget(card2)

        card3, lay3 = self._make_card()
        t3 = app_label(t("card_snippet"), "card_title")
        lay3.addWidget(t3)
        self.snippet_view = PlainTextEdit()
        self.snippet_view.setReadOnly(True)
        self.snippet_view.setMinimumHeight(140)
        lay3.addWidget(self.snippet_view)
        btns = QHBoxLayout()
        self.copy_snip_btn = PushButton(" " + t("copy"))
        self._set_icon(self.copy_snip_btn, "copy", "#e4e4e7", 13)
        self.copy_snip_btn.clicked.connect(self._copy_snippet)
        btns.addWidget(self.copy_snip_btn)
        self.apply_keys_btn = PrimaryPushButton(" " + t("keys_apply"))
        self._set_icon(self.apply_keys_btn, "check", "#09090b", 13)
        self.apply_keys_btn.clicked.connect(self._apply_keys)
        btns.addWidget(self.apply_keys_btn)
        self.remove_keys_btn = PushButton(" " + t("keys_remove"))
        self.remove_keys_btn.clicked.connect(self._remove_keys)
        btns.addWidget(self.remove_keys_btn)
        lay3.addLayout(btns)
        self.keys_status = app_label("", "muted")
        self.keys_status.setWordWrap(True)
        lay3.addWidget(self.keys_status)
        layout.addWidget(card3)
        layout.addStretch()
        self._on_comp_changed()

    def _current_comp(self) -> "comp_mod.Compositor":
        cid = self.comp_combo.currentData()
        if cid == self.comp.id:
            return self.comp
        paths = {
            "niri": comp_mod.CONFIG_HOME / "niri" / "config.kdl",
            "umbriel": comp_mod.CONFIG_HOME / "umbriel" / "config.toml",
            "hyprland": comp_mod.CONFIG_HOME / "hypr" / "hyprland.conf",
            "sway": comp_mod.CONFIG_HOME / "sway" / "config",
            "river": comp_mod.CONFIG_HOME / "river" / "init",
        }
        return comp_mod.Compositor(cid, self.comp_combo.currentText(), paths.get(cid), cid in paths)

    def _on_comp_changed(self):
        c = self._current_comp()
        detected = c.id == self.comp.id
        tag = t("detected_auto") if detected else t("detected_manual")
        cfg = f"<br><span style='color:#a1a1aa'>{t('config_file')}: {c.config_path}</span>" if c.config_path else ""
        self._set_rich_text(self.comp_lbl, f"<b>{c.label}</b> &nbsp;<span style='color:#38bdf8'>{tag}</span>{cfg}")
        self.apply_keys_btn.setEnabled(c.can_apply)
        self.remove_keys_btn.setEnabled(c.can_apply)
        self._refresh_snippet()

    def _refresh_snippet(self):
        c = self._current_comp()
        cap = self.cap_key.text().strip() or DEFAULT_CAPTURE
        col = self.col_key.text().strip() or DEFAULT_COLOR
        self.snippet_view.setPlainText(comp_mod.snippet(c.id, cap, col))
        notes = []
        for key in (cap, col):
            for hit in comp_mod.find_conflicts(c, key):
                notes.append(f"<span style='color:#fbbf24'>{t('key_conflict', k=key)}</span> <code>{hit}</code>")
        for hit in comp_mod.existing_click_to_do_binds(c):
            notes.append(f"<span style='color:#4ade80'>{t('key_existing')}</span> <code>{hit}</code>")
        self._set_rich_text(self.key_note, "<br>".join(notes) or t("key_ok"))
        self.key_note.setVisible(True)

    def _copy_snippet(self):
        from ..utils.clipboard import ClipboardManager

        ClipboardManager.copy_text(self.snippet_view.toPlainText())
        self.keys_status.setText(t("copied"))

    def _apply_keys(self):
        c = self._current_comp()
        ok, msg = comp_mod.apply(
            c, self.cap_key.text().strip() or DEFAULT_CAPTURE, self.col_key.text().strip() or DEFAULT_COLOR
        )
        self.keys_status.setText(msg)
        if ok:
            self._on_comp_changed()

    def _remove_keys(self):
        done = comp_mod.remove(self._current_comp())
        self.keys_status.setText(t("keys_removed", n=len(done)))

    def _uninstall_desktop_app(self):
        from ..installer import uninstall_system_integration

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(t("uninstall_title"))
        box.setText(t("uninstall_confirm"))
        purge = CheckBox(t("uninstall_purge"))
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
        self.config.ui_theme = self.theme
        self.config.ui_language = self.ui_lang_combo.currentData()
        self.config.bg_removal_model = self.bg_combo.currentData()
        self.config.llm_backend = self.backend_combo.currentData()
        self.config.llm_keep_alive = self.keep_combo.currentData()
        if self.det_combo is not None:
            self.config.ocr_det_backend = self.det_combo.currentData()
        if self.config.llm_backend == "openai":
            self.config.openai_model = self._get_selected_ollama_model()
        else:
            self.config.ollama_model = self._get_selected_ollama_model()
        self.config.target_language = self.lang_combo.currentData()
        self.config.search_engine = self.engine_combo.currentData()
        save_config(self.config)

    def _apply(self):
        """Saves the settings and keeps the window open."""
        self.config.setup_completed = True
        self._save_config_data()
        self.apply_btn.setText(t("btn_applied"))
        if InfoBar is not None:
            InfoBar.success(
                t("set_title"), t("btn_applied"), duration=1500,
                position=InfoBarPosition.TOP_RIGHT, parent=self,
            )
        QTimer.singleShot(1500, lambda: self.apply_btn.setText(t("btn_apply")))

    def _save_and_close(self):
        self.config.setup_completed = True
        self._save_config_data()
        if InfoBar is not None:
            InfoBar.success(
                t("set_title"), t("btn_applied"), duration=1500,
                position=InfoBarPosition.TOP_RIGHT, parent=self,
            )
        if not self.embedded:
            self.close()
