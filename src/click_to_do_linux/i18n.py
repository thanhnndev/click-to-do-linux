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
    "open_link": {"vi": "Mở liên kết", "en": "Open Link"},
    "email": {"vi": "Gửi email", "en": "Email"},
    "search": {"vi": "Tìm kiếm", "en": "Search"},
    "summarize": {"vi": "Tóm tắt", "en": "Summarize"},
    "rewrite": {"vi": "Viết lại / Chỉnh câu", "en": "Rewrite / Polish"},
    "cutout": {"vi": "Tách nền", "en": "Cutout"},
    "cutting": {"vi": "Đang tách...", "en": "Cutting..."},
    "blur_bg": {"vi": "Làm mờ nền", "en": "Blur BG"},
    "blurring": {"vi": "Đang làm mờ...", "en": "Blurring..."},
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
    "copy_all": {"vi": "Sao chép toàn bộ chữ", "en": "Copy All Text"},
    # Tray
    "tray_tooltip": {
        "vi": "Click to Do — Chuột trái: chụp màn hình | Chuột phải: menu",
        "en": "Click to Do — Left-click: Capture | Right-click: Menu",
    },
    "tray_capture": {"vi": "Chụp màn hình (Click to Do)", "en": "Capture Screen (Click to Do)"},
    "tray_color": {"vi": "Chọn màu trên màn hình (HEX)", "en": "Pick Screen Color (HEX)"},
    "tray_settings": {"vi": "Cài đặt & mô hình AI cục bộ", "en": "Settings & Local Models"},
    "tray_quit": {"vi": "Thoát dịch vụ nền", "en": "Quit Daemon"},
    # Settings
    "set_title": {"vi": "Click to Do — Cài đặt", "en": "Click to Do — Settings"},
    "set_sub": {
        "vi": "Lớp phủ thông minh trên màn hình, mô hình AI chạy cục bộ và tích hợp thanh hệ thống",
        "en": "Screen intelligence overlay, local models, and desktop bar integration",
    },
    "card_cutout": {"vi": "MÔ HÌNH TÁCH NỀN (ONNX)", "en": "SUBJECT CUTOUT ENGINE (ONNX)"},
    "cutout_fast": {"vi": "u2netp  —  Siêu nhanh (~4,7 MB, <50ms)", "en": "u2netp  —  Ultra-fast (~4.7 MB, <50ms latency)"},
    "cutout_precise": {
        "vi": "isnet-general-use  —  Chính xác cao (~170 MB, viền mịn)",
        "en": "isnet-general-use  —  High precision (~170 MB, fine edges)",
    },
    "card_llm": {"vi": "MÔ HÌNH NGÔN NGỮ CỤC BỘ (OLLAMA)", "en": "LOCAL LANGUAGE MODEL (OLLAMA)"},
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
        "vi": "Sẵn sàng tải/kiểm tra mô hình hoặc cài đặt dịch vụ nền.",
        "en": "Ready to download/verify models or install desktop service.",
    },
    "btn_warmup": {"vi": " Tải && khởi động mô hình", "en": " Download && Warmup Models"},
    "btn_install": {"vi": " Cài đặt ứng dụng && dịch vụ nền", "en": " Install App && Systemd Service"},
    "btn_uninstall": {"vi": " Gỡ cài đặt...", "en": " Uninstall..."},
    "btn_about": {"vi": " Giới thiệu && giấy phép", "en": " About && Licenses"},
    "btn_cancel": {"vi": "Hủy", "en": "Cancel"},
    "btn_save": {"vi": "Lưu thay đổi", "en": "Save Changes"},
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
    # About
    "about_title": {"vi": "Giới thiệu & giấy phép", "en": "About & Licenses"},
    "about_body": {
        "vi": "Click to Do for Linux — phiên bản mã nguồn mở, mô phỏng tính năng Click to Do của Windows 11 cho Wayland.\n"
        "Dự án độc lập, không liên kết với Microsoft.\n\n"
        "Giấy phép: GNU GPL v3.0 trở lên.\n"
        "Tác giả: thanhnndev\n\n"
        "Thành phần bên thứ ba:\n"
        "• RapidOCR / PaddleOCR (Apache-2.0) — phát hiện chữ\n"
        "• Tesseract OCR (Apache-2.0) — nhận dạng tiếng Việt\n"
        "• rembg, U²-Net, IS-Net (MIT / Apache-2.0) — tách nền\n"
        "• Ollama (MIT) + Qwen, Gemma, Sailor2 — mô hình ngôn ngữ cục bộ\n"
        "• PyQt6 (GPL v3), OpenCV, Pillow, NumPy, requests\n\n"
        "Xem LICENSE và CREDITS.md trong kho mã nguồn.",
        "en": "Click to Do for Linux — open-source take on Windows 11 Click to Do for Wayland.\n"
        "Independent project, not affiliated with Microsoft.\n\n"
        "License: GNU GPL v3.0 or later.\n"
        "Author: thanhnndev\n\n"
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
