"""Persistent workday timer, reminders, tasks, and notes."""

from __future__ import annotations

import json
import math
import time
import uuid
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .config import get_config_dir
from .i18n import t


REMINDER_DEFAULTS = {
    "water": {"enabled": True, "interval_minutes": 60},
    "movement": {"enabled": True, "interval_minutes": 50},
}
TIMER_DEFAULTS = {
    "mode": "focus",
    "running": False,
    "end_at": None,
    "remaining_seconds": 25 * 60,
    "completed_focus": 0,
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "long_break_every": 4,
}
SCHEDULE_DEFAULTS = {
    "enabled": True,
    "weekdays_only": True,
    "start": "09:00",
    "end": "18:00",
}


class ProductivityService(QObject):
    """Owns the persistent state and timers used by the office workspace."""

    state_changed = pyqtSignal()
    notification_requested = pyqtSignal(str, str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.path = get_config_dir() / "office.json"
        self._today = date.today().isoformat()
        self._data = self._load()
        self._ensure_today()
        self._normalize_timer()
        self._normalize_reminders()
        self._normalize_schedule()
        self._last_remaining = self.timer_remaining()

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def _ensure_today(self) -> None:
        daily = self._data.get("daily")
        if not isinstance(daily, dict):
            self._data["daily"] = daily = {}
        today = daily.setdefault(self._today, {"tasks": [], "note": ""})
        if not isinstance(today, dict):
            daily[self._today] = today = {"tasks": [], "note": ""}
        if not isinstance(today.get("tasks"), list):
            today["tasks"] = []
        else:
            today["tasks"] = [
                task for task in today["tasks"]
                if isinstance(task, dict) and isinstance(task.get("text"), str)
            ]
            for task in today["tasks"]:
                task.setdefault("id", uuid.uuid4().hex)
                task["done"] = bool(task.get("done"))
        if not isinstance(today.get("note"), str):
            today["note"] = ""
        if not isinstance(self._data.get("timer"), dict):
            self._data["timer"] = dict(TIMER_DEFAULTS)
        if not isinstance(self._data.get("reminders"), dict):
            self._data["reminders"] = {}
        if not isinstance(self._data.get("reminders_paused"), dict):
            self._data["reminders_paused"] = {}
        if not isinstance(self._data.get("schedule"), dict):
            self._data["schedule"] = dict(SCHEDULE_DEFAULTS)

    def _normalize_timer(self) -> None:
        timer = self._data["timer"]
        for key, default in TIMER_DEFAULTS.items():
            timer.setdefault(key, default)
        if timer.get("mode") not in ("focus", "short_break", "long_break"):
            timer["mode"] = "focus"
        for key, low, high in (
            ("focus_minutes", 10, 90),
            ("short_break_minutes", 3, 30),
            ("long_break_minutes", 10, 45),
            ("long_break_every", 2, 8),
        ):
            try:
                timer[key] = max(low, min(high, int(timer[key])))
            except (TypeError, ValueError):
                timer[key] = TIMER_DEFAULTS[key]
        try:
            timer["completed_focus"] = max(0, int(timer.get("completed_focus", 0) or 0))
        except (TypeError, ValueError):
            timer["completed_focus"] = 0
        timer["running"] = bool(timer.get("running"))
        try:
            timer["remaining_seconds"] = max(0, int(timer.get("remaining_seconds", 0)))
        except (TypeError, ValueError):
            timer["remaining_seconds"] = self._duration_for(timer["mode"])
        if timer["running"] and not isinstance(timer.get("end_at"), (int, float)):
            timer["running"] = False
            timer["remaining_seconds"] = self._duration_for(timer["mode"])

    def _normalize_reminders(self) -> None:
        reminders = self._data["reminders"]
        now = time.time()
        for key, defaults in REMINDER_DEFAULTS.items():
            reminder = reminders.get(key)
            if not isinstance(reminder, dict):
                reminders[key] = reminder = {}
            reminder.setdefault("enabled", defaults["enabled"])
            reminder.setdefault("interval_minutes", defaults["interval_minutes"])
            try:
                reminder["interval_minutes"] = max(15, min(240, int(reminder["interval_minutes"])))
            except (TypeError, ValueError):
                reminder["interval_minutes"] = defaults["interval_minutes"]
            reminder["enabled"] = bool(reminder["enabled"])
            if not isinstance(reminder.get("next_at"), (int, float)):
                reminder["next_at"] = now + reminder["interval_minutes"] * 60

    def _normalize_schedule(self) -> None:
        schedule = self._data["schedule"]
        for key, default in SCHEDULE_DEFAULTS.items():
            schedule.setdefault(key, default)
        schedule["enabled"] = bool(schedule["enabled"])
        schedule["weekdays_only"] = bool(schedule["weekdays_only"])
        for key in ("start", "end"):
            try:
                schedule[key] = datetime.strptime(str(schedule[key]), "%H:%M").strftime("%H:%M")
            except ValueError:
                schedule[key] = SCHEDULE_DEFAULTS[key]

    @property
    def _today_data(self) -> dict:
        return self._data["daily"][self._today]

    @property
    def tasks(self) -> list[dict]:
        return self._today_data["tasks"]

    @property
    def note(self) -> str:
        return self._today_data["note"]

    @property
    def completed_tasks(self) -> int:
        return sum(1 for task in self.tasks if task.get("done"))

    @property
    def timer_mode(self) -> str:
        return self._data["timer"]["mode"]

    @property
    def timer_running(self) -> bool:
        return self._data["timer"]["running"]

    @property
    def completed_focus(self) -> int:
        return self._data["timer"]["completed_focus"]

    @property
    def focuses_in_cycle(self) -> int:
        if self.timer_mode == "long_break":
            return self.long_break_every
        return self.completed_focus % self.long_break_every

    @property
    def long_break_every(self) -> int:
        return self._data["timer"]["long_break_every"]

    def timer_minutes(self, mode: str | None = None) -> int:
        return int(self._data["timer"][self._duration_key(mode or self.timer_mode)])

    @staticmethod
    def _duration_key(mode: str) -> str:
        return {
            "focus": "focus_minutes",
            "short_break": "short_break_minutes",
            "long_break": "long_break_minutes",
        }[mode]

    def _duration_for(self, mode: str) -> int:
        key = self._duration_key(mode)
        try:
            return max(60, int(self._data.get("timer", {}).get(key, TIMER_DEFAULTS[key])) * 60)
        except (TypeError, ValueError):
            return TIMER_DEFAULTS[key] * 60

    def timer_remaining(self) -> int:
        timer = self._data["timer"]
        if timer["running"]:
            return max(0, math.ceil(float(timer["end_at"]) - time.time()))
        return max(0, int(timer["remaining_seconds"]))

    @property
    def timer_progress(self) -> float:
        duration = max(1, self._duration_for(self.timer_mode))
        return max(0.0, min(1.0, 1 - self.timer_remaining() / duration))

    def reminder(self, key: str) -> dict:
        return self._data["reminders"][key]

    @property
    def schedule(self) -> dict:
        return self._data["schedule"]

    @property
    def in_reminder_window(self) -> bool:
        schedule = self.schedule
        if not schedule["enabled"]:
            return True
        now = datetime.now()
        if schedule["weekdays_only"] and now.weekday() >= 5:
            return False
        start_hour, start_minute = map(int, schedule["start"].split(":"))
        end_hour, end_minute = map(int, schedule["end"].split(":"))
        current = now.hour * 60 + now.minute
        start = start_hour * 60 + start_minute
        end = end_hour * 60 + end_minute
        if start == end:
            return True
        if start < end:
            return start <= current < end
        return current >= start or current < end

    @property
    def reminders_paused(self) -> bool:
        return float(self._data["reminders_paused"].get("until", 0) or 0) > time.time()

    @property
    def reminders_pause_remaining(self) -> int:
        return max(0, math.ceil(float(self._data["reminders_paused"].get("until", 0) or 0) - time.time()))

    def reminder_remaining(self, key: str) -> int | None:
        reminder = self.reminder(key)
        if not reminder["enabled"]:
            return None
        paused = self._data["reminders_paused"]
        if float(paused.get("until", 0) or 0) > time.time():
            return max(0, math.ceil(float(paused["until"]) - time.time()))
        return max(0, math.ceil(float(reminder["next_at"]) - time.time()))

    def start_or_pause_timer(self) -> None:
        timer = self._data["timer"]
        if timer["running"]:
            if self.timer_remaining() <= 0:
                self._complete_timer_phase()
                return
            timer["remaining_seconds"] = self.timer_remaining()
            timer["running"] = False
            timer["end_at"] = None
        else:
            if timer["remaining_seconds"] <= 0:
                timer["remaining_seconds"] = self._duration_for(timer["mode"])
            timer["end_at"] = time.time() + timer["remaining_seconds"]
            timer["running"] = True
        self._last_remaining = self.timer_remaining()
        self._save()
        self.state_changed.emit()

    def reset_timer(self) -> None:
        timer = self._data["timer"]
        timer["running"] = False
        timer["end_at"] = None
        timer["remaining_seconds"] = self._duration_for(timer["mode"])
        self._last_remaining = timer["remaining_seconds"]
        self._save()
        self.state_changed.emit()

    def select_timer_mode(self, mode: str) -> None:
        if mode not in ("focus", "short_break", "long_break") or self.timer_running:
            return
        timer = self._data["timer"]
        timer["mode"] = mode
        timer["remaining_seconds"] = self._duration_for(mode)
        timer["end_at"] = None
        self._last_remaining = timer["remaining_seconds"]
        self._save()
        self.state_changed.emit()

    def set_timer_minutes(self, mode: str, minutes: int) -> None:
        if mode not in ("focus", "short_break", "long_break"):
            return
        timer = self._data["timer"]
        limits = {"focus": (10, 90), "short_break": (3, 30), "long_break": (10, 45)}
        low, high = limits[mode]
        timer[self._duration_key(mode)] = max(low, min(high, int(minutes)))
        if timer["mode"] == mode and not timer["running"]:
            timer["remaining_seconds"] = self._duration_for(mode)
            self._last_remaining = timer["remaining_seconds"]
        self._save()
        self.state_changed.emit()

    def set_long_break_every(self, count: int) -> None:
        self._data["timer"]["long_break_every"] = max(2, min(8, int(count)))
        self._save()
        self.state_changed.emit()

    def set_schedule_enabled(self, enabled: bool) -> None:
        self.schedule["enabled"] = bool(enabled)
        self._save()
        self.state_changed.emit()

    def set_weekdays_only(self, enabled: bool) -> None:
        self.schedule["weekdays_only"] = bool(enabled)
        self._save()
        self.state_changed.emit()

    def set_work_hours(self, start: str, end: str) -> None:
        try:
            start = datetime.strptime(start, "%H:%M").strftime("%H:%M")
            end = datetime.strptime(end, "%H:%M").strftime("%H:%M")
        except ValueError:
            return
        self.schedule["start"] = start
        self.schedule["end"] = end
        self._save()
        self.state_changed.emit()

    def set_reminder_enabled(self, key: str, enabled: bool) -> None:
        reminder = self.reminder(key)
        reminder["enabled"] = bool(enabled)
        reminder["next_at"] = time.time() + reminder["interval_minutes"] * 60
        self._save()
        self.state_changed.emit()

    def set_reminder_interval(self, key: str, minutes: int) -> None:
        reminder = self.reminder(key)
        reminder["interval_minutes"] = max(15, min(240, int(minutes)))
        reminder["next_at"] = time.time() + reminder["interval_minutes"] * 60
        self._save()
        self.state_changed.emit()

    def mark_reminder_done(self, key: str) -> None:
        reminder = self.reminder(key)
        reminder["next_at"] = time.time() + reminder["interval_minutes"] * 60
        self._save()
        self.state_changed.emit()

    def snooze_reminder(self, key: str, minutes: int = 10) -> None:
        self.reminder(key)["next_at"] = time.time() + minutes * 60
        self._save()
        self.state_changed.emit()

    def pause_reminders(self, minutes: int = 60) -> None:
        now = time.time()
        self._data["reminders_paused"] = {"started_at": now, "until": now + minutes * 60}
        self._save()
        self.state_changed.emit()

    def resume_reminders(self) -> None:
        paused = self._data.get("reminders_paused", {})
        now = time.time()
        until = float(paused.get("until", 0) or 0)
        if until:
            started_at = float(paused.get("started_at", now) or now)
            elapsed = max(0, min(now, until) - started_at)
            for reminder in self._data["reminders"].values():
                reminder["next_at"] = float(reminder["next_at"]) + elapsed
            self._data["reminders_paused"] = {}
        self._save()
        self.state_changed.emit()

    def add_task(self, text: str) -> None:
        clean = text.strip()
        if not clean:
            return
        self.tasks.append({"id": uuid.uuid4().hex, "text": clean, "done": False})
        self._save()
        self.state_changed.emit()

    def toggle_task(self, task_id: str) -> None:
        for task in self.tasks:
            if task.get("id") == task_id:
                task["done"] = not bool(task.get("done"))
                break
        self._save()
        self.state_changed.emit()

    def delete_task(self, task_id: str) -> None:
        self._today_data["tasks"] = [task for task in self.tasks if task.get("id") != task_id]
        self._save()
        self.state_changed.emit()

    def set_note(self, value: str) -> None:
        if self.note == value:
            return
        self._today_data["note"] = value
        self._save()

    def _tick(self) -> None:
        state_emitted = False
        today = date.today().isoformat()
        if today != self._today:
            self._today = today
            self._ensure_today()
            self._save()
            self.state_changed.emit()
            state_emitted = True

        now = time.time()
        if self.timer_running:
            remaining = self.timer_remaining()
            if remaining <= 0:
                self._complete_timer_phase()
                state_emitted = True
            elif remaining != self._last_remaining:
                self._last_remaining = remaining
                self.state_changed.emit()
                state_emitted = True

        reminders_changed = self._resume_reminders(now)
        if not self.reminders_paused and self.in_reminder_window:
            for key, reminder in self._data["reminders"].items():
                if reminder["enabled"] and now >= float(reminder["next_at"]):
                    reminder["next_at"] = now + reminder["interval_minutes"] * 60
                    title, message = self._reminder_message(key)
                    self.notification_requested.emit(title, message)
                    reminders_changed = True
                    self.state_changed.emit()
                    state_emitted = True
        if reminders_changed:
            self._save()
        if not state_emitted:
            # Keep the countdown labels fresh even while the Pomodoro is idle.
            self.state_changed.emit()

    def _complete_timer_phase(self) -> None:
        timer = self._data["timer"]
        completed_mode = timer["mode"]
        timer["running"] = False
        timer["end_at"] = None
        if completed_mode == "focus":
            timer["completed_focus"] += 1
            if timer["completed_focus"] % timer["long_break_every"] == 0:
                timer["mode"] = "long_break"
            else:
                timer["mode"] = "short_break"
            title, message = t("office_focus_complete_title"), t("office_focus_complete_body")
        else:
            if completed_mode == "long_break":
                timer["completed_focus"] = 0
            timer["mode"] = "focus"
            title, message = t("office_break_complete_title"), t("office_break_complete_body")
        timer["remaining_seconds"] = self._duration_for(timer["mode"])
        self._last_remaining = timer["remaining_seconds"]
        self._save()
        self.notification_requested.emit(title, message)
        self.state_changed.emit()

    def _resume_reminders(self, now: float) -> bool:
        paused = self._data.get("reminders_paused", {})
        until = float(paused.get("until", 0) or 0)
        if not until or now < until:
            return False
        started_at = float(paused.get("started_at", now) or now)
        pause_seconds = max(0, until - started_at)
        for reminder in self._data["reminders"].values():
            reminder["next_at"] = float(reminder["next_at"]) + pause_seconds
        self._data["reminders_paused"] = {}
        return True

    @staticmethod
    def _reminder_message(key: str) -> tuple[str, str]:
        if key == "water":
            return t("office_water_title"), t("office_water_body")
        return t("office_movement_title"), t("office_movement_body")

    def _save(self) -> None:
        # Keep a rolling two-month daily log of tasks and notes.
        daily = self._data.get("daily", {})
        for old_day in sorted(daily)[:-60]:
            daily.pop(old_day, None)
        temporary = self.path.with_suffix(".json.tmp")
        try:
            temporary.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.path)
        except OSError as exc:
            print(f"[Office] Could not save workspace data: {exc}")
