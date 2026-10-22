"""Lightweight UI localisation (Vietnamese / English). Language follows config.ui_language or the system locale."""

import locale
import os

_STRINGS: dict[str, dict[str, str]] = {
    # Action bar
    "copy": {"vi": "Sao chép", "en": "Copy"},
    "translate": {"vi": "Dịch", "en": "Translate"},
    "explain": {"vi": "Giải thích", "en": "Explain"},
    "ask": {"vi": "Hỏi AI", "en": "Ask"},
    "ask_placeholder": {"vi": "Hỏi AI về đoạn đã chọn...", "en": "Ask AI about selection..."},
    "copy_link": {"vi": "Sao chép liên kết", "en": "Copy Link"},
    "merge_paragraph": {"vi": "Bỏ xuống dòng", "en": "Remove line breaks"},
    "merge_paragraph_hint": {"vi": "Gộp các dòng thành một đoạn khi sao chép chữ", "en": "Join wrapped lines into one paragraph when copying text"},
    "open_link": {"vi": "Mở liên kết", "en": "Open Link"},
    "email": {"vi": "Gửi email", "en": "Email"},
    "search": {"vi": "Tìm kiếm", "en": "Search"},
    "summarize": {"vi": "Tóm tắt", "en": "Summarize"},
    "rewrite": {"vi": "Viết lại / Chỉnh câu", "en": "Rewrite / Polish"},
    "cutout": {"vi": "Tách nền", "en": "Cutout"},
    "cutting": {"vi": "Đang tách...", "en": "Cutting..."},
    "blur_bg": {"vi": "Làm mờ nền", "en": "Blur BG"},
    "blurring": {"vi": "Đang làm mờ...", "en": "Blurring..."},
    "processing": {"vi": "Đang xử lý...", "en": "Processing..."},
    "redact": {"vi": "Che thông tin", "en": "Redact"},
    "copy_text": {"vi": "Sao chép chữ", "en": "Copy Text"},
    "save": {"vi": "Lưu ảnh", "en": "Save"},
    "copy_qr": {"vi": "Sao chép mã QR", "en": "Copy QR"},
    # AI dialog
    "generating": {"vi": "Đang tạo...", "en": "Generating..."},
    "done": {"vi": "Hoàn tất", "en": "Done"},
    "error": {"vi": "Lỗi", "en": "Error"},
    "copied": {"vi": "Đã sao chép", "en": "Copied"},
    "ai_ask_title": {"vi": "Hỏi AI", "en": "AI"},
    # Overlay
    "find_placeholder": {"vi": "Tìm chữ trên màn hình (Ctrl+F)...", "en": "Find text on screen (Ctrl+F)..."},
    "pick_color": {"vi": "Chọn màu", "en": "Pick Color"},
    "copy_image": {"vi": "Sao chép ảnh", "en": "Copy Image"},
    "copy_region_text": {"vi": "Sao chép chữ", "en": "Copy Text"},
    "copy_all": {"vi": "Sao chép chữ", "en": "Copy Text"},
    # Tray
    "tray_tooltip": {
        "vi": "Click to Do — Chuột trái: chụp màn hình | Chuột phải: menu",
        "en": "Click to Do — Left-click: Capture | Right-click: Menu",
    },
    "tray_capture": {"vi": "Chụp màn hình (Click to Do)", "en": "Capture Screen (Click to Do)"},
    "tray_color": {"vi": "Chọn màu trên màn hình (HEX)", "en": "Pick Screen Color (HEX)"},
    "tray_settings": {"vi": "Cài đặt && mô hình AI cục bộ", "en": "Settings && Local Models"},
    "tray_office": {"vi": "Mở Bàn làm việc", "en": "Open Workbench"},
    "tray_quit": {"vi": "Thoát dịch vụ nền", "en": "Quit Daemon"},
    # App shell and appearance
    "shell_workspace": {"vi": "KHÔNG GIAN LÀM VIỆC", "en": "WORKSPACE"},
    "shell_background": {"vi": "● Đang chạy nền", "en": "● Background is running"},
    "shell_background_hint": {"vi": "Đóng cửa sổ vẫn giữ timer, nhắc việc và tray hoạt động. Chọn Thoát Click to Do để dừng ứng dụng.", "en": "Closing the window keeps timers, reminders and the tray running. Choose Quit Click to Do to stop the app."},
    "shell_quit": {"vi": "Thoát Click to Do", "en": "Quit Click to Do"},
    "shell_local_saved": {"vi": "Tự lưu trên máy này", "en": "Saved automatically on this device"},
    "shell_settings_sub": {"vi": "Cấu hình ngày làm việc, giao diện và tích hợp Linux.", "en": "Manage your workday, appearance and Linux integration."},
    "shell_every_day": {"vi": "Mỗi ngày", "en": "Every day"},
    "shell_all_day": {"vi": "Nhắc việc cả ngày", "en": "Reminders throughout the day"},
    "theme_to_light": {"vi": "Giao diện sáng", "en": "Light mode"},
    "theme_to_dark": {"vi": "Giao diện tối", "en": "Dark mode"},
    "theme_heading": {"vi": "Giao diện", "en": "Appearance"},
    "theme_hint": {"vi": "Chọn giao diện sáng hoặc tối. Lựa chọn được lưu và áp dụng ngay cho Bàn làm việc và Cài đặt.", "en": "Choose light or dark mode. Your choice is saved and applied immediately to Workbench and Settings."},
    "theme_light": {"vi": "Sáng", "en": "Light"},
    "theme_dark": {"vi": "Tối", "en": "Dark"},
    "tab_appearance": {"vi": "Giao diện", "en": "Appearance"},
    "tab_workday": {"vi": "Ngày làm việc", "en": "Workday"},
    "workday_autosave": {"vi": "Thay đổi tự lưu. Tạm dừng timer trước khi chỉnh thời lượng phiên.", "en": "Changes save automatically. Pause the timer to change session lengths."},
    "workday_start": {"vi": "Bắt đầu giờ làm", "en": "Workday starts"},
    "workday_end": {"vi": "Kết thúc giờ làm", "en": "Workday ends"},
    # Office workspace
    "office_title": {"vi": "Click to Do — Bàn làm việc", "en": "Click to Do — Workbench"},
    "office_heading": {"vi": "Bàn làm việc", "en": "Workbench"},
    "office_subtitle": {
        "vi": "Tập trung vào việc cần làm, nhớ dành chỗ cho những khoảng nghỉ.",
        "en": "Make room for focused work and the breaks that go with it.",
    },
    "office_capture": {"vi": "Chụp màn hình", "en": "Capture screen"},
    "office_color": {"vi": "Lấy màu", "en": "Pick a color"},
    "office_settings": {"vi": "Cài đặt", "en": "Settings"},
    "office_focus_section": {"vi": "TẬP TRUNG", "en": "FOCUS"},
    "office_focus_desc": {"vi": "Một việc mỗi lần. Nghỉ ngắn giữa các phiên.", "en": "One task at a time. Take a short break between sessions."},
    "office_mode_focus": {"vi": "Tập trung", "en": "Focus"},
    "office_mode_short": {"vi": "Nghỉ ngắn", "en": "Short break"},
    "office_mode_long": {"vi": "Nghỉ dài", "en": "Long break"},
    "office_focus_duration": {"vi": "Tập trung", "en": "Focus"},
    "office_short_duration": {"vi": "Nghỉ ngắn", "en": "Short break"},
    "office_long_duration": {"vi": "Nghỉ dài", "en": "Long break"},
    "office_long_every": {"vi": "Nghỉ dài sau", "en": "Long break every"},
    "office_sessions": {"vi": "phiên", "en": "sessions"},
    "office_cycle": {"vi": "Chu kỳ {done}/{total}", "en": "Cycle {done}/{total}"},
    "office_start": {"vi": "Bắt đầu", "en": "Start"},
    "office_pause": {"vi": "Tạm dừng", "en": "Pause"},
    "office_reset": {"vi": "Đặt lại", "en": "Reset"},
    "office_timer_ready": {"vi": "Sẵn sàng bắt đầu phiên mới", "en": "Ready for a new session"},
    "office_timer_running": {"vi": "Đang chạy · tập trung vào việc trước mắt", "en": "Running · stay with the task at hand"},
    "office_timer_paused": {"vi": "Đã tạm dừng · tiếp tục khi bạn sẵn sàng", "en": "Paused · resume when you are ready"},
    "office_health_section": {"vi": "NHẮC SỨC KHỎE", "en": "WELLBEING REMINDERS"},
    "office_water": {"vi": "Uống nước", "en": "Drink water"},
    "office_water_hint": {"vi": "Một ngụm nước, rồi quay lại nhịp của bạn.", "en": "Take a sip, then return to your own pace."},
    "office_movement": {"vi": "Rời ghế, vận động nhẹ", "en": "Step away and move"},
    "office_movement_hint": {"vi": "Đi lại vài phút, thả lỏng vai và nhìn ra xa.", "en": "Walk for a few minutes, relax your shoulders, and look into the distance."},
    "office_every": {"vi": "Mỗi", "en": "Every"},
    "office_enabled": {"vi": "Bật", "en": "On"},
    "office_minutes": {"vi": "phút", "en": "min"},
    "office_next_in": {"vi": "Còn {time}", "en": "Next in {time}"},
    "office_reminder_off": {"vi": "Đã tắt nhắc", "en": "Reminder is off"},
    "office_mark_done": {"vi": "Đã xong", "en": "Done"},
    "office_snooze": {"vi": "Hoãn 10 phút", "en": "Snooze 10 min"},
    "office_pause_reminders": {"vi": "Tạm dừng nhắc 1 giờ", "en": "Pause reminders for 1 hour"},
    "office_resume_reminders": {"vi": "Bật lại nhắc", "en": "Resume reminders"},
    "office_reminders_paused": {"vi": "Đang tạm dừng · {time}", "en": "Paused · {time}"},
    "office_schedule": {"vi": "Chỉ nhắc trong giờ làm", "en": "Limit to work hours"},
    "office_weekdays": {"vi": "Thứ Hai–Thứ Sáu", "en": "Weekdays only"},
    "office_hours": {"vi": "Khung giờ", "en": "Hours"},
    "office_next_work_window": {"vi": "Sẽ nhắc trong giờ làm", "en": "Reminder waits for work hours"},
    "office_tasks_section": {"vi": "VIỆC HÔM NAY", "en": "TODAY'S TASKS"},
    "office_tasks_count": {"vi": "{done}/{total} hoàn tất", "en": "{done}/{total} done"},
    "office_task_placeholder": {"vi": "Thêm việc cần làm…", "en": "Add a task…"},
    "office_add_task": {"vi": "Thêm việc", "en": "Add task"},
    "office_delete_task": {"vi": "Xóa việc", "en": "Delete task"},
    "office_no_tasks": {"vi": "Danh sách đang trống. Thêm một việc để bắt đầu ngày mới.", "en": "Nothing here yet. Add a task to get your day moving."},
    "office_notes_section": {"vi": "GHI CHÚ NHANH", "en": "QUICK NOTES"},
    "office_notes_hint": {"vi": "Ghi chú cuộc họp hoặc ý tưởng. Tự lưu cục bộ.", "en": "Meeting notes or ideas. Saved on this device."},
    "office_notes_placeholder": {"vi": "Bắt đầu ghi chú…", "en": "Start writing…"},
    "office_focus_complete_title": {"vi": "Hoàn thành phiên tập trung", "en": "Focus session complete"},
    "office_focus_complete_body": {"vi": "Đến lúc rời mắt khỏi màn hình và nghỉ một chút.", "en": "Time to look away from the screen and take a short break."},
    "office_break_complete_title": {"vi": "Hết giờ nghỉ", "en": "Break is over"},
    "office_break_complete_body": {"vi": "Khi sẵn sàng, bạn có thể bắt đầu phiên tập trung tiếp theo.", "en": "When you are ready, start your next focus session."},
    "office_water_title": {"vi": "Một lời nhắc uống nước", "en": "A water break"},
    "office_water_body": {"vi": "Uống một chút nước nếu bạn đang cần nhé.", "en": "Take a sip of water if you need one."},
    "office_movement_title": {"vi": "Đã đến lúc đứng dậy", "en": "Time to move a little"},
    "office_movement_body": {"vi": "Đi lại nhẹ nhàng và thả lỏng cơ thể vài phút nhé.", "en": "Take a gentle walk and loosen up for a few minutes."},
    # Settings
    "set_title": {"vi": "Click to Do — Cài đặt", "en": "Click to Do — Settings"},
    "set_sub": {
        "vi": "Lớp phủ thông minh trên màn hình, mô hình AI chạy cục bộ và tích hợp thanh hệ thống",
        "en": "Screen intelligence overlay, local models, and desktop bar integration",
    },
    "card_cutout": {"vi": "MÔ HÌNH TÁCH NỀN (ONNX)", "en": "SUBJECT CUTOUT ENGINE (ONNX)"},
    "cutout_fast": {"vi": "u2netp  —  Nhỏ & nhanh nhất (~4,7 MB)", "en": "u2netp  —  Smallest & fastest (~4.7 MB)"},
    "cutout_precise": {
        "vi": "isnet-general-use  —  Chính xác cao (~170 MB, viền mịn)",
        "en": "isnet-general-use  —  High precision (~170 MB, fine edges)",
    },
    "card_llm": {"vi": "MÔ HÌNH NGÔN NGỮ CỤC BỘ (OLLAMA / NPU)", "en": "LOCAL LANGUAGE MODEL (OLLAMA / NPU)"},
    "refresh": {"vi": " Làm mới", "en": " Refresh"},
    "installed_tag": {"vi": "đã cài", "en": "Installed"},
    "llm_hint": {
        "vi": "Gợi ý cho tiếng Việt: qwen3:4b (2,5 GB) cân bằng nhất, qwen3:8b / sailor2:8b nếu có ≥ 8 GB VRAM.",
        "en": "Best for Vietnamese: qwen3:4b (2.5 GB) is the balanced pick; qwen3:8b / sailor2:8b with ≥ 8 GB VRAM.",
    },
    "card_prefs": {"vi": "TÙY CHỌN", "en": "PREFERENCES"},
    "pref_target": {"vi": "Ngôn ngữ đích", "en": "Target language"},
    "pref_ui": {"vi": "Ngôn ngữ giao diện", "en": "Interface language"},
    "ui_auto": {"vi": "Tự động (theo hệ thống)", "en": "Auto (system)"},
    "pref_search": {"vi": "Tìm kiếm web", "en": "Web search"},
    "card_cache": {"vi": "BỘ NHỚ MÔ HÌNH & TÍCH HỢP HỆ THỐNG", "en": "MODEL CACHE & DESKTOP INTEGRATION"},
    "status_ready": {
        "vi": "Sẵn sàng tải/kiểm tra mô hình hoặc cài tích hợp desktop.",
        "en": "Ready to download/verify models or install desktop integration.",
    },
    "btn_warmup": {"vi": " Tải && khởi động mô hình", "en": " Download && Warmup Models"},
    "btn_install": {"vi": " Cài ứng dụng && khởi động nền", "en": " Install App && Background Startup"},
    "btn_uninstall": {"vi": " Gỡ cài đặt...", "en": " Uninstall..."},
    "btn_about": {"vi": " Giới thiệu && giấy phép", "en": " About && Licenses"},
    "btn_cancel": {"vi": "Hủy", "en": "Cancel"},
    "btn_apply": {"vi": "Áp dụng", "en": "Apply"},
    "btn_applied": {"vi": "Đã áp dụng", "en": "Applied"},
    "btn_save": {"vi": "Lưu và đóng", "en": "Save and Close"},
    "install_done": {"vi": "Cài đặt hoàn tất", "en": "Installation Complete"},
    "uninstall_title": {"vi": "Gỡ cài đặt Click to Do", "en": "Uninstall Click to Do"},
    "uninstall_confirm": {
        "vi": "Gỡ dịch vụ nền, lối tắt, biểu tượng và quy tắc Niri đã cài?\n\nDữ liệu cá nhân (cấu hình, mô hình đã tải) chỉ bị xóa nếu bạn chọn bên dưới.",
        "en": "Remove the background service, launchers, icons and Niri rule?\n\nUser data (config, downloaded models) is only deleted if you tick the option below.",
    },
    "uninstall_purge": {
        "vi": "Xóa luôn cấu hình và dữ liệu Tesseract đã tải",
        "en": "Also delete config and downloaded Tesseract data",
    },
    "uninstall_done": {"vi": "Đã gỡ cài đặt", "en": "Uninstalled"},
    "status_error": {"vi": "Lỗi: ", "en": "Error: "},
    "warm_ocr": {"vi": "Đang khởi tạo bộ phát hiện chữ (RapidOCR)...", "en": "Initializing text detector (RapidOCR)..."},
    "warm_tess": {"vi": "Đang tải dữ liệu OCR tiếng Việt (Tesseract)...", "en": "Downloading Vietnamese OCR data (Tesseract)..."},
    "warm_cutout": {"vi": "Đang nạp mô hình tách nền ({m})...", "en": "Loading cutout engine ({m})..."},
    "warm_pull": {"vi": "Đang tải mô hình Ollama '{m}'...", "en": "Pulling Ollama model '{m}'..."},
    "warm_ready": {"vi": "Sẵn sàng", "en": "Ready"},
    "warm_done": {"vi": "Đã khởi tạo và lưu đệm toàn bộ mô hình cục bộ.", "en": "All local models initialized and cached."},
    "warm_no_tess": {
        "vi": "Chưa có lệnh 'tesseract' — OCR tiếng Việt sẽ mất dấu. Cài: sudo pacman -S tesseract (hoặc apt install tesseract-ocr).",
        "en": "'tesseract' not found — Vietnamese OCR will lose diacritics. Install: sudo pacman -S tesseract (or apt install tesseract-ocr).",
    },
    # Tabs / diagnostics / shortcuts
    "tab_general": {"vi": "Chung && AI", "en": "General && AI"},
    "tab_shortcuts": {"vi": "Phím tắt", "en": "Shortcuts"},
    "tab_system": {"vi": "Hệ thống", "en": "System"},
    "card_diag": {"vi": "KIỂM TRA MÔI TRƯỜNG", "en": "ENVIRONMENT CHECK"},
    "diag_compositor": {"vi": "Compositor / shell", "en": "Compositor / shell"},
    "diag_unknown": {"vi": "không nhận diện được", "en": "not recognised"},
    "diag_install": {"vi": "cài gói {p}", "en": "install {p}"},
    "diag_tessdata": {"vi": "Dữ liệu OCR tiếng Việt (vie + eng)", "en": "Vietnamese OCR data (vie + eng)"},
    "diag_tessdata_hint": {"vi": "bấm Tải && khởi động mô hình", "en": "click Download && Warmup Models"},
    "diag_ollama_hint": {"vi": "chạy `ollama serve` hoặc cài Ollama", "en": "run `ollama serve` or install Ollama"},
    "llm_backend": {"vi": "Nơi chạy mô hình", "en": "Run models on"},
    "llm_backend_ollama": {"vi": "Ollama (GPU/CPU)", "en": "Ollama (GPU/CPU)"},
    "ocr_det_cpu": {"vi": "Phát hiện chữ (OCR): CPU", "en": "Text detection (OCR): CPU"},
    "ocr_det_npu": {
        "vi": "Phát hiện chữ (OCR): NPU (cần AMD Ryzen AI Software, xem docs/NPU.md)",
        "en": "Text detection (OCR): NPU (needs AMD Ryzen AI Software, see docs/NPU.md)",
    },
    "llm_backend_npu": {"vi": "NPU qua FastFlowLM (tiết kiệm pin)", "en": "NPU via FastFlowLM (battery-friendly)"},
    "llm_keepalive": {"vi": "Giải phóng mô hình sau", "en": "Unload model after"},
    "keep_now": {"vi": "Ngay lập tức", "en": "Immediately"},
    "keep_never": {"vi": "Không bao giờ", "en": "Never"},
    "llm_npu_hint": {
        "vi": "Chạy `flm serve <model>` (cổng 52625). Tên model theo FastFlowLM, ví dụ qwen3:4b.",
        "en": "Run `flm serve <model>` (port 52625). Use FastFlowLM model tags, e.g. qwen3:4b.",
    },
    "diag_npu": {"vi": "NPU", "en": "NPU"},
    "diag_npu_none": {"vi": "không tìm thấy /dev/accel", "en": "no /dev/accel device found"},
    "diag_flm": {"vi": "FastFlowLM (flm)", "en": "FastFlowLM (flm)"},
    "diag_flm_hint": {"vi": "cài gói fastflowlm + xrt-plugin-amdxdna", "en": "install fastflowlm + xrt-plugin-amdxdna"},
    "diag_memlock": {"vi": "memlock không giới hạn", "en": "memlock unlimited"},
    "diag_memlock_hint": {"vi": "đặt `memlock unlimited` trong limits.conf rồi đăng nhập lại", "en": "set `memlock unlimited` in limits.conf and re-login"},
    "diag_service": {"vi": "Khởi động nền Click to Do", "en": "Click to Do background startup"},
    "diag_service_hint": {"vi": "bấm Cài đặt ứng dụng", "en": "click Install App"},
    "card_detect": {"vi": "COMPOSITOR ĐANG DÙNG", "en": "DETECTED COMPOSITOR"},
    "detected_auto": {"vi": "● tự động nhận diện", "en": "● auto-detected"},
    "detected_manual": {"vi": "○ chọn thủ công", "en": "○ manual choice"},
    "config_file": {"vi": "Tệp cấu hình", "en": "Config file"},
    "other": {"vi": "Khác", "en": "Other"},
    "card_keys": {"vi": "PHÍM TẮT (Mod = phím Super/Windows)", "en": "KEYBOARD SHORTCUTS (Mod = Super/Windows key)"},
    "key_capture": {"vi": "Chụp màn hình", "en": "Capture screen"},
    "key_color": {"vi": "Chọn màu", "en": "Color picker"},
    "key_ok": {"vi": "Không phát hiện xung đột với cấu hình hiện tại.", "en": "No conflict with your current config."},
    "key_conflict": {"vi": "{k} đã được dùng:", "en": "{k} is already bound:"},
    "key_existing": {"vi": "Đã có phím tắt Click to Do:", "en": "Click to Do is already bound:"},
    "card_snippet": {"vi": "CẤU HÌNH SẼ ĐƯỢC THÊM / HƯỚNG DẪN", "en": "CONFIG SNIPPET / GUIDE"},
    "keys_apply": {"vi": "Áp dụng vào cấu hình", "en": "Apply to config"},
    "keys_remove": {"vi": "Gỡ phím tắt", "en": "Remove shortcuts"},
    "keys_removed": {"vi": "Đã gỡ phím tắt ({n} mục).", "en": "Shortcuts removed ({n} item(s))."},
    # About
    "about_title": {"vi": "Giới thiệu & giấy phép", "en": "About & Licenses"},
    "about_body": {
        "vi": "Click to Do for Linux — phiên bản mã nguồn mở, mô phỏng tính năng Click to Do của Windows 11 cho Wayland.\n"
        "Có thêm Bàn làm việc cá nhân với Pomodoro, việc trong ngày, ghi chú và nhắc sức khỏe.\n"
        "Dự án độc lập, không liên kết với Microsoft.\n\n"
        "Giấy phép: GNU GPL v3.0 trở lên.\n"
        "Tác giả: thanhnndev — contact@thanhnn.dev\n"
        "Mã nguồn: github.com/thanhnndev/click-to-do-linux\n\n"
        "Thành phần bên thứ ba:\n"
        "• RapidOCR / PaddleOCR (Apache-2.0) — phát hiện chữ\n"
        "• Tesseract OCR (Apache-2.0) — nhận dạng tiếng Việt\n"
        "• rembg, U²-Net, IS-Net (MIT / Apache-2.0) — tách nền\n"
        "• Ollama (MIT) + Qwen, Gemma, Sailor2 — mô hình ngôn ngữ cục bộ\n"
        "• PyQt6 (GPL v3), OpenCV, Pillow, NumPy, requests\n\n"
        "Xem LICENSE và CREDITS.md trong kho mã nguồn.",
        "en": "Click to Do for Linux — a personal workbench with focus timer, daily tasks, notes, and wellbeing reminders, alongside screen tools for Wayland.\n"
        "Independent project, not affiliated with Microsoft.\n\n"
        "License: GNU GPL v3.0 or later.\n"
        "Author: thanhnndev — contact@thanhnn.dev\n"
        "Source: github.com/thanhnndev/click-to-do-linux\n\n"
        "Third-party components:\n"
        "• RapidOCR / PaddleOCR (Apache-2.0) — text detection\n"
        "• Tesseract OCR (Apache-2.0) — Vietnamese recognition\n"
        "• rembg, U²-Net, IS-Net (MIT / Apache-2.0) — cutout\n"
        "• Ollama (MIT) + Qwen, Gemma, Sailor2 — local language models\n"
        "• PyQt6 (GPL v3), OpenCV, Pillow, NumPy, requests\n\n"
        "See LICENSE and CREDITS.md in the repository.",
    },
}


def current_lang() -> str:
    try:
        from .config import load_config

        pref = load_config().ui_language
    except Exception:
        pref = "auto"
    if pref in ("vi", "en"):
        return pref
    loc = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    if not loc:
        try:
            loc = locale.getlocale()[0] or ""
        except Exception:
            loc = ""
    return "vi" if loc.lower().startswith("vi") else "en"


_LANG: str | None = None


def set_lang(lang: str | None = None) -> None:
    global _LANG
    _LANG = lang if lang in ("vi", "en") else None


def t(key: str, **fmt) -> str:
    global _LANG
    if _LANG is None:
        _LANG = current_lang()
    entry = _STRINGS.get(key)
    s = entry.get(_LANG, entry["en"]) if entry else key
    return s.format(**fmt) if fmt else s
