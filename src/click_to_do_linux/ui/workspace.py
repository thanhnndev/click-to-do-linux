"""Personal workday dashboard for Click to Do."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QSignalBlocker, QSize, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    CheckBox,
    LineEdit,
    PlainTextEdit,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    ScrollArea,
    TogglePushButton,
    TransparentPushButton,
    TransparentToolButton,
)

from ..config import load_config, save_config
from ..i18n import current_lang, t
from ..productivity import ProductivityService
from .fluent_theme import sync_fluent_theme
from .typography import PixmapLabel, label as app_label
from .icons import get_icon
from .palette import apply_input_palette, accent, primary_ink, theme_stylesheet
from PyQt6.QtGui import QIcon
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
)
from PyQt6.QtGui import QColor


class OfficeWindow(FluentWindow):
    """One resident app shell for Workbench and Settings."""

    theme_changed = pyqtSignal(str)

    def __init__(
        self,
        service: ProductivityService,
        on_capture=None,
        on_quit=None,
    ):
        super().__init__()
        self.service = service
        self.on_capture = on_capture or (lambda color_mode=False: None)
        self.on_quit = on_quit or (lambda: None)
        self.theme = load_config().ui_theme
        if self.theme not in ("light", "dark"):
            self.theme = "dark"
        self.settings_page = None
        self._page = "workbench"
        self._language = current_lang()
        self._shown_running: bool | None = None
        self._rendered_tasks: tuple | None = None
        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(350)
        self._note_timer.timeout.connect(lambda: self.service.set_note(self.notes_edit.toPlainText()))

        self.setWindowTitle(t("office_title"))
        self.setMinimumSize(820, 620)
        self.resize(1220, 820)
        self._build_ui()
        self.set_theme(self.theme, persist=False)
        self.service.state_changed.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _style() -> str:
        # Only layout, card and typography live here. Every interactive control
        # is a Fluent widget and keeps its own stylesheet.
        return """
        QFrame#Topbar { border-bottom: 1px solid #27272a; }
        QLabel#Brand { font-size: 16px; font-weight: 650; }
        QWidget {
            color: #f4f4f5;
        }
        QWidget#WorkbenchPage { background-color: #09090b; }
        QLabel { background: transparent; }
        ScrollArea > QWidget > QWidget { background: transparent; }
        QFrame#Card {
            background-color: #121215;
            border: 1px solid #27272a;
            border-radius: 12px;
        }
        QFrame#ReminderItem {
            background-color: #18181b;
            border: 1px solid #27272a;
            border-radius: 9px;
        }
        QLabel#MainTitle { font-size: 23px; font-weight: 650; }
        QLabel#MainSub { font-size: 12px; }
        QLabel#CardTitle { font-size: 14px; font-weight: 650; }
        QLabel#CardHint { font-size: 12px; }
        QLabel#Eyebrow { font-size: 12px; font-weight: 700; letter-spacing: 1.1px; }
        QLabel#TimerText {
            font-family: "Noto Sans Mono", "DejaVu Sans Mono", monospace;
            font-size: 60px;
            font-weight: 600;
        }
        QLabel#TimerStatus { font-size: 12px; }
        QLabel#ReminderStatus { font-size: 12px; }
        QLabel#TaskText { font-size: 12px; }
        QLabel#EmptyState { font-size: 12px; padding: 16px 8px; }
        """

    def _build_ui(self) -> None:
        # Workbench page hosted in FluentWindow's stacked widget.
        self.workbench_page = QWidget()
        self.workbench_page.setObjectName("WorkbenchPage")

        page_layout = QVBoxLayout(self.workbench_page)
        page_layout.setContentsMargins(24, 18, 24, 24)
        page_layout.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("Topbar")
        header = QHBoxLayout(topbar)
        header.setContentsMargins(0, 0, 0, 0)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        brand_row = QHBoxLayout()
        self.brand_icon = PixmapLabel()
        brand_row.addWidget(self.brand_icon)
        self.brand_label = app_label("Click to Do", "brand")
        self.brand_label.setObjectName("Brand")
        brand_row.addWidget(self.brand_label)
        titles.addLayout(brand_row)
        self.page_title = app_label(t("office_heading"), "subtitle")
        self.page_title.setObjectName("MainTitle")
        self.page_subtitle = app_label(t("office_subtitle"), "caption")
        self.page_subtitle.setObjectName("MainSub")
        self.page_subtitle.setWordWrap(True)
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        header.addLayout(titles, 1)
        self.capture_button = PrimaryPushButton(t("office_capture"))
        self.capture_button.setToolTip(t("office_capture"))
        self.capture_button.clicked.connect(lambda: self.on_capture(False))
        self.color_button = PushButton(t("office_color"))
        self.color_button.setToolTip(t("office_color"))
        self.color_button.clicked.connect(lambda: self.on_capture(True))
        header.addWidget(self.capture_button)
        header.addWidget(self.color_button)
        page_layout.addWidget(topbar)

        self.date_label = app_label("", "caption")
        self.date_label.setObjectName("MainSub")
        page_layout.addWidget(self.date_label)

        scroll = ScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # The viewport fills with the palette colour unless it is turned off.
        scroll.viewport().setAutoFillBackground(False)
        content = QWidget()
        self.dashboard_grid = QGridLayout(content)
        self.dashboard_grid.setContentsMargins(0, 0, 6, 0)
        self.dashboard_grid.setSpacing(14)
        self.cards = {}
        card, layout = self._make_card(t("office_focus_section"), t("office_focus_desc"), True)
        self._build_focus(layout)
        self.cards["focus"] = card
        card, layout = self._make_card(t("office_health_section"), "", True)
        self._build_health(layout)
        self.cards["health"] = card
        card, layout = self._make_card(t("office_tasks_section"))
        self._build_tasks(layout)
        self.cards["tasks"] = card
        card, layout = self._make_card(t("office_notes_section"), t("office_notes_hint"))
        self.notes_edit = PlainTextEdit()
        self.notes_edit.setPlaceholderText(t("office_notes_placeholder"))
        self.notes_edit.setMinimumHeight(120)
        self.notes_edit.textChanged.connect(self._note_timer.start)
        layout.addWidget(self.notes_edit)
        self.cards["notes"] = card
        self.left_column = QWidget()
        self.right_column = QWidget()
        for column, keys in ((self.left_column, ("focus", "tasks")), (self.right_column, ("health", "notes"))):
            column_layout = QVBoxLayout(column)
            column_layout.setContentsMargins(0, 0, 0, 0)
            column_layout.setSpacing(14)
            for key in keys:
                column_layout.addWidget(self.cards[key])
            column_layout.addStretch(1)
        scroll.setWidget(content)
        page_layout.addWidget(scroll, 1)

        self.addSubInterface(self.workbench_page, FluentIcon.HOME, t("office_heading"))

        # Settings page created upfront so its nav entry is visible.
        from .setup_window import SetupWindow
        self.settings_page = SetupWindow(embedded=True, productivity_service=self.service)
        self.settings_page.setObjectName("SettingsPage")
        self.settings_page.theme_changed.connect(self.set_theme)
        self.settings_page.set_theme(self.theme)
        self.addSubInterface(self.settings_page, FluentIcon.SETTING, t("office_settings"))

        # Footer navigation items (bottom).
        color = accent(self.theme)
        self.theme_nav_item = self.navigationInterface.addItem(
            routeKey="theme_toggle",
            icon=get_icon("sun" if self.theme == "dark" else "moon", color, 17),
            text=t("theme_to_light" if self.theme == "dark" else "theme_to_dark"),
            onClick=lambda: self.set_theme("light" if self.theme == "dark" else "dark"),
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )
        self.quit_nav_item = self.navigationInterface.addItem(
            routeKey="quit",
            icon=get_icon("power", color, 17),
            text=t("shell_quit"),
            onClick=self.on_quit,
            selectable=False,
            position=NavigationItemPosition.BOTTOM,
        )

        self.show_page("workbench")
        self._layout_dashboard()

    def show_page(self, page: str) -> None:
        if page == "settings" and self.settings_page is None:
            from .setup_window import SetupWindow
            self.settings_page = SetupWindow(embedded=True, productivity_service=self.service)
            self.settings_page.setObjectName("SettingsPage")
            self.settings_page.theme_changed.connect(self.set_theme)
            self.settings_page.set_theme(self.theme)
            self.addSubInterface(self.settings_page, FluentIcon.SETTING, t("office_settings"))
        self._page = page
        target = self.settings_page if page == "settings" else self.workbench_page
        self.switchTo(target)
        if page == "workbench":
            self.page_title.setText(t("office_heading"))
            self.page_subtitle.setText(t("office_subtitle"))

    def show_settings(self) -> None:
        self.show_page("settings")

    def set_theme(self, theme: str, persist: bool = True) -> None:
        self.theme = "light" if theme == "light" else "dark"
        sync_fluent_theme(self.theme)
        if hasattr(self, "workbench_page"):
            self.workbench_page.setStyleSheet(theme_stylesheet(self._style(), self.theme))
        apply_input_palette(self, self.theme)
        if persist:
            config = load_config()
            config.ui_theme = self.theme
            save_config(config)
        if self.settings_page is not None:
            self.settings_page.set_theme(self.theme)
        color = accent(self.theme)
        self.brand_icon.setPixmap(get_icon("app_logo", color, 28).pixmap(28, 28))
        self.capture_button.setIcon(get_icon("app_logo", color, 16))
        self.color_button.setIcon(get_icon("pipette", color, 16))
        self.reset_button.setIcon(get_icon("refresh", color, 15))
        for widgets in self.reminder_widgets.values():
            widgets["done"].setIcon(get_icon("check", color, 16))
            widgets["snooze"].setIcon(get_icon("clock", color, 15))
        # Update footer nav items.
        if hasattr(self, "theme_nav_item"):
            self.theme_nav_item.setText(t("theme_to_light" if self.theme == "dark" else "theme_to_dark"))
            self.theme_nav_item.setIcon(get_icon("sun" if self.theme == "dark" else "moon", color, 17))
        if hasattr(self, "quit_nav_item"):
            self.quit_nav_item.setIcon(get_icon("power", color, 17))
        self._shown_running = None
        self._rendered_tasks = None
        self.refresh()
        self._layout_dashboard()
        if persist:
            InfoBar.success(
                t("office_title"),
                t("theme_to_light" if self.theme == "dark" else "theme_to_dark"),
                duration=1500,
                position=InfoBarPosition.TOP_RIGHT,
                parent=self,
            )
        self.theme_changed.emit(self.theme)

    def _layout_dashboard(self) -> None:
        if not hasattr(self, "dashboard_grid"):
            return
        self.capture_button.setText(t("office_capture"))
        self.color_button.setText(t("office_color"))
        grid = self.dashboard_grid
        if not hasattr(self, "left_column"):
            return
        grid.removeWidget(self.left_column)
        grid.removeWidget(self.right_column)
        if self.width() < 1120:
            grid.addWidget(self.left_column, 0, 0)
            grid.addWidget(self.right_column, 1, 0)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 0)
        else:
            grid.addWidget(self.left_column, 0, 0)
            grid.addWidget(self.right_column, 0, 1)
            grid.setColumnStretch(0, 6)
            grid.setColumnStretch(1, 4)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._layout_dashboard()

    def _make_card(self, eyebrow: str, hint: str = "", configurable: bool = False) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 15, 17, 16)
        layout.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(10)
        title_stack = QVBoxLayout()
        title_stack.setSpacing(3)
        label = app_label(eyebrow, "eyebrow")
        label.setObjectName("CardTitle")
        title_stack.addWidget(label)
        if hint:
            subtitle = app_label(hint, "caption")
            subtitle.setObjectName("CardHint")
            subtitle.setWordWrap(True)
            title_stack.addWidget(subtitle)
        header.addLayout(title_stack, stretch=1)
        if configurable:
            settings = TransparentPushButton(t("office_settings"))
            settings.clicked.connect(self.show_settings)
            header.addWidget(settings)
        layout.addLayout(header)
        return card, layout

    def _build_focus(self, layout: QVBoxLayout) -> None:
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_buttons = {}
        for mode, key in (("focus", "office_mode_focus"), ("short_break", "office_mode_short"), ("long_break", "office_mode_long")):
            button = TogglePushButton(t(key))
            button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, current=mode: self.service.select_timer_mode(current))
            self.mode_group.addButton(button)
            self.mode_buttons[mode] = button
            mode_row.addWidget(button)
        mode_row.addStretch()
        layout.addLayout(mode_row)
        clock_row = QHBoxLayout()
        clock_row.setSpacing(12)
        self.clock = app_label("25:00", "title")
        self.clock.setObjectName("TimerText")
        clock_row.addWidget(self.clock, 1)
        self.timer_toggle = PrimaryPushButton(t("office_start"))
        self.timer_toggle.clicked.connect(self.service.start_or_pause_timer)
        reset = TransparentToolButton()
        reset.setFixedSize(34, 34)
        reset.setToolTip(t("office_reset"))
        reset.setAccessibleName(t("office_reset"))
        reset.clicked.connect(self.service.reset_timer)
        self.reset_button = reset
        clock_row.addWidget(self.timer_toggle)
        clock_row.addWidget(reset)
        layout.addLayout(clock_row)
        self.cycle_label = app_label("", "caption")
        self.cycle_label.setObjectName("ReminderStatus")
        layout.addWidget(self.cycle_label)
        self.timer_status = app_label("", "caption")
        self.timer_status.setObjectName("TimerStatus")
        self.timer_status.setWordWrap(True)
        layout.addWidget(self.timer_status)
        self.timer_progress = ProgressBar()
        self.timer_progress.setRange(0, 1000)
        self.timer_progress.setTextVisible(False)
        self.timer_progress.setFixedHeight(4)
        layout.addWidget(self.timer_progress)

    def _build_health(self, layout: QVBoxLayout) -> None:
        self.reminder_widgets = {}
        for key, title, hint in (("water", "office_water", "office_water_hint"), ("movement", "office_movement", "office_movement_hint")):
            frame = QFrame()
            frame.setObjectName("ReminderItem")
            item = QHBoxLayout(frame)
            item.setContentsMargins(11, 11, 11, 11)
            item.setSpacing(7)
            text = QVBoxLayout()
            text.setSpacing(5)
            name = app_label(t(title), "heading")
            name.setObjectName("CardTitle")
            name.setWordWrap(True)
            name.setToolTip(t(hint))
            text.addWidget(name)
            status = app_label("", "caption")
            status.setObjectName("ReminderStatus")
            status.setWordWrap(True)
            text.addWidget(status)
            item.addLayout(text, 1)
            done = TransparentToolButton()
            done.setFixedSize(34, 34)
            done.setToolTip(t("office_mark_done"))
            done.setAccessibleName(t("office_mark_done") + ": " + t(title))
            done.clicked.connect(lambda checked=False, current=key: self.service.mark_reminder_done(current))
            snooze = TransparentToolButton()
            snooze.setFixedSize(34, 34)
            snooze.setToolTip(t("office_snooze"))
            snooze.setAccessibleName(t("office_snooze") + ": " + t(title))
            snooze.clicked.connect(lambda checked=False, current=key: self.service.snooze_reminder(current))
            item.addWidget(done)
            item.addWidget(snooze)
            layout.addWidget(frame)
            self.reminder_widgets[key] = {"status": status, "done": done, "snooze": snooze}
        self.schedule_summary = app_label("", "caption")
        self.schedule_summary.setObjectName("CardHint")
        self.schedule_summary.setWordWrap(True)
        layout.addWidget(self.schedule_summary)
        self.reminders_pause_btn = TransparentPushButton(t("office_pause_reminders"))
        self.reminders_pause_btn.clicked.connect(self._toggle_reminder_pause)
        layout.addWidget(self.reminders_pause_btn)
        self.reminders_pause_status = app_label("", "caption")
        self.reminders_pause_status.setObjectName("CardHint")
        layout.addWidget(self.reminders_pause_status)

    def _build_tasks(self, layout: QVBoxLayout) -> None:
        top_row = QHBoxLayout()
        self.task_count = app_label("", "caption")
        self.task_count.setObjectName("CardHint")
        top_row.addStretch(1)
        top_row.addWidget(self.task_count)
        layout.insertLayout(1, top_row)

        input_row = QHBoxLayout()
        self.task_input = LineEdit()
        self.task_input.setPlaceholderText(t("office_task_placeholder"))
        self.task_input.returnPressed.connect(self._add_task)
        add_btn = PrimaryPushButton(t("office_add_task"))
        add_btn.clicked.connect(self._add_task)
        input_row.addWidget(self.task_input, stretch=1)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        self.task_list = QVBoxLayout()
        self.task_list.setSpacing(4)
        layout.addLayout(self.task_list)
        layout.addStretch(1)

    def _add_task(self) -> None:
        self.service.add_task(self.task_input.text())
        self.task_input.clear()
        self.task_input.setFocus()

    def _toggle_reminder_pause(self) -> None:
        if self.service.reminders_paused:
            self.service.resume_reminders()
        else:
            self.service.pause_reminders(60)

    def _format_duration(self, seconds: int) -> str:
        hours, remainder = divmod(max(0, seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _format_date(self) -> str:
        today = datetime.now()
        if self._language == "vi":
            weekdays = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật")
            return f"{weekdays[today.weekday()]} · {today.day:02d} tháng {today.month}"
        return today.strftime("%A · %d %B")

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()

    def refresh(self) -> None:
        self.date_label.setText(self._format_date())
        for mode, button in self.mode_buttons.items():
            blocker = QSignalBlocker(button)
            button.setChecked(mode == self.service.timer_mode)
            button.setEnabled(not self.service.timer_running)
            del blocker
        remaining = self.service.timer_remaining()
        minutes, seconds = divmod(remaining, 60)
        self.clock.setText(f"{minutes:02d}:{seconds:02d}")
        self.timer_progress.setValue(round(self.service.timer_progress * 1000))
        if self._shown_running != self.service.timer_running:
            self.timer_toggle.setText(t("office_pause") if self.service.timer_running else t("office_start"))
            self.timer_toggle.setIcon(get_icon("pause" if self.service.timer_running else "play", primary_ink(self.theme), 14))
            self._shown_running = self.service.timer_running
        self.timer_status.setText(
            t("office_timer_running") if self.service.timer_running
            else (t("office_timer_paused") if remaining < self.service.timer_minutes() * 60 else t("office_timer_ready"))
        )
        self.cycle_label.setText(t(
            "office_cycle",
            done=self.service.focuses_in_cycle,
            total=self.service.long_break_every,
        ))
        for key, widgets in self.reminder_widgets.items():
            reminder = self.service.reminder(key)
            widgets["done"].setEnabled(reminder["enabled"])
            widgets["snooze"].setEnabled(reminder["enabled"])
            seconds_left = self.service.reminder_remaining(key)
            if seconds_left is None:
                widgets["status"].setText(t("office_reminder_off"))
            elif self.service.reminders_paused:
                widgets["status"].setText(t("office_reminders_paused", time=self._format_duration(seconds_left)))
            elif self.service.schedule["enabled"] and not self.service.in_reminder_window:
                widgets["status"].setText(t("office_next_work_window"))
            else:
                widgets["status"].setText(t("office_next_in", time=self._format_duration(seconds_left)))

        schedule = self.service.schedule
        if schedule["enabled"]:
            days = t("office_weekdays") if schedule["weekdays_only"] else t("shell_every_day")
            self.schedule_summary.setText(f"{days} · {schedule['start']}–{schedule['end']}")
        else:
            self.schedule_summary.setText(t("shell_all_day"))
        paused = self.service.reminders_paused
        self.reminders_pause_btn.setText(t("office_resume_reminders" if paused else "office_pause_reminders"))
        self.reminders_pause_status.setVisible(paused)
        self.reminders_pause_status.setText(
            self._format_duration(self.service.reminders_pause_remaining)
            if paused else ""
        )

        self.task_count.setText(t("office_tasks_count", done=self.service.completed_tasks, total=len(self.service.tasks)))
        task_signature = tuple(
            (task.get("id"), task.get("text", ""), bool(task.get("done")))
            for task in self.service.tasks
        )
        if task_signature != self._rendered_tasks:
            self._clear_layout(self.task_list)
            if not self.service.tasks:
                empty = app_label(t("office_no_tasks"), "muted")
                empty.setObjectName("EmptyState")
                empty.setWordWrap(True)
                self.task_list.addWidget(empty)
            else:
                for task in self.service.tasks:
                    row = QHBoxLayout()
                    row.setSpacing(8)
                    check = CheckBox()
                    check.setChecked(bool(task.get("done")))
                    check.toggled.connect(lambda _checked, task_id=task["id"]: self.service.toggle_task(task_id))
                    label = app_label(str(task.get("text", "")), "muted" if task.get("done") else "body")
                    label.setObjectName("TaskText")
                    task_font = label.font()
                    task_font.setStrikeOut(bool(task.get("done")))
                    label.setFont(task_font)
                    label.style().unpolish(label)
                    label.style().polish(label)
                    label.setWordWrap(True)
                    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                    delete = TransparentToolButton()
                    delete.setIcon(get_icon("close", "#475569" if self.theme == "light" else "#a1a1aa", 13))
                    delete.setFixedSize(34, 34)
                    delete.setToolTip(t("office_delete_task"))
                    delete.clicked.connect(lambda _checked=False, task_id=task["id"]: self.service.delete_task(task_id))
                    row.addWidget(check, alignment=Qt.AlignmentFlag.AlignTop)
                    row.addWidget(label, stretch=1)
                    row.addWidget(delete, alignment=Qt.AlignmentFlag.AlignTop)
                    self.task_list.addLayout(row)
            self._rendered_tasks = task_signature

        note = self.service.note
        if self.notes_edit.toPlainText() != note and not self.notes_edit.hasFocus() and not self._note_timer.isActive():
            blocker = QSignalBlocker(self.notes_edit)
            self.notes_edit.setPlainText(note)
            del blocker

    def flush_pending_note(self) -> None:
        self._note_timer.stop()
        self.service.set_note(self.notes_edit.toPlainText())

    def closeEvent(self, event) -> None:
        self.flush_pending_note()
        self.hide()
        event.ignore()
