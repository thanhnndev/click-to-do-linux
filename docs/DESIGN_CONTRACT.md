# Design Contract — Click to Do for Linux

> Hợp đồng thiết kế cho đợt migrate UI sang **PyQt6 + PyQt6-Fluent-Widgets**.
> Áp dụng cho mọi màn: Workbench, Settings, overlay OCR, AI dialog, tray.
> Nguồn sự thật duy nhất cho màu, cỡ chữ, nhịp, bo góc, trạng thái. Khi code và
> hợp đồng mâu thuẫn → sửa code, không sửa hợp đồng (trừ khi có quyết định mới).
>
> **v2 — "native" nghĩa là: không tự vẽ lại control.** Mọi control tương tác là
> component của `qfluentwidgets`; app chỉ sở hữu layout, typography và accent.

## 0.1 Quy tắc sở hữu (bắt buộc)

| Ai sở hữu | Nội dung | Cơ chế |
| --- | --- | --- |
| `qfluentwidgets` | Mọi control tương tác: button, input, combo, spin, checkbox, tab, scroll, progress, menu, toast | Class của thư viện, dùng nguyên xi |
| `qfluentwidgets` | Theme sáng/tối + màu nhấn | `ui/fluent_theme.py::sync_fluent_theme()` gọi `setTheme` + `setThemeColor` + `setFontFamilies` |
| App | Layout, khoảng cách, card, nền vùng | QSS chỉ gồm `#id` rule, **không** style control |
| App | Typography | `ui/typography.py` — map role → label Fluent + `setTextColor(light, dark)` |
| App | Nội dung copy | `t()` trong `i18n.py` |

**Cấm:** QSS ghi đè control Fluent (`QPushButton{}`, `QLineEdit{}`, `QComboBox{}`…).
Lý do: control Fluent mang stylesheet riêng, stylesheet của widget thắng stylesheet
của tổ tiên → mọi rule QSS ghi đè đều là code chết, và rule `QWidget{background}`
còn làm nền tối loang lổ dưới label Fluent.

**Bẫy Qt đã gặp (không lặp lại):**
- Rule cuối cùng thắng khi cùng specificity → đặt `QLabel{background:transparent}`
  **sau** `QWidget{...}`.
- `QScrollArea` viewport tự fill bằng palette → `scroll.viewport().setAutoFillBackground(False)`.
- `FluentWindow`/`FluentWindow` sub-interface dùng `NavigationInterface` sẵn — không tự vẽ sidebar.
- Icon-only `PushButton` của Fluent đặt icon theo `minimumSizeHint` → cắt icon. Dùng `ToolButton` cho nút chỉ có icon.
- Tab tĩnh: `tabBar.setCloseButtonDisplayMode(TabCloseButtonDisplayMode.NEVER)` + `tabBar.addButton.hide()`.

## 0. Brief (chốt trước khi dựng)

| Mục | Giá trị |
| --- | --- |
| Sản phẩm | Workbench cá nhân: tasks, notes, Pomodoro, wellbeing reminders, screen tools (OCR/QR/cutout/redact/color/AI) |
| Người dùng | Một người dùng Linux (Niri/Umbriel, Wayland), làm việc за столом, dùng cả ngày |
| Phong cách | **Flat dark** (hướng A của skill) cho shell; **glass** cho overlay nổi (đã có trong `theme.py`, giữ nguyên) |
| Màu nhấn | Cyan/sky `#38bdf8` (dark) / `#0369a1` (light) — lấy từ logo (gradient cyan→indigo→purple) |
| Màu AI | Indigo→purple gradient `#6366f1 → #a855f7` — chỉ dùng cho AI sparkles, AI dialog header, AI action button |
| Font UI | Inter, fallback Noto Sans (diacritics VN), system-ui |
| Font mono | Noto Sans Mono, fallback DejaVu Sans Mono (timer, code, HEX) |
| Dark mode | Có, mặc định dark; light qua `Theme.AUTO`/toggle. Lưu `ui_theme` trong config |
| Ngôn ngữ copy | Tiếng Việt mặc định, English qua `i18n.current_lang()`; nhãn UI theo `t()` |
| Framework UI | PyQt6 + **PyQt6-Fluent-Widgets** (`qfluentwidgets`), theme `Theme.DARK/AUTO/LIGHT` |

**Quy tắc màu nhấn (`D5`):** cyan phải xuất hiện ở (1) nút chính, (2) nav đang chọn,
(3) focus ring, (4) progress bar, (5) link. Nếu một màn không có chỗ nào dùng cyan → màn đó chưa quyết định, phải thêm.

## 1. Token

### 1.1 Màu — Neutral (dark, mặc định)

| Token | Dark | Light | Dùng cho |
| --- | --- | --- | --- |
| `--bg` | `#09090b` | `#f8fafc` | Nền cửa sổ |
| `--surface` | `#121215` | `#ffffff` | Card, panel |
| `--surface-2` | `#18181b` | `#f1f5f9` | Sidebar, input bg, hover |
| `--border` | `#27272a` | `#cbd5e1` | Viền 1px |
| `--border-strong` | `#3f3f46` | `#94a3b8` | Viền input, nút |
| `--fg` | `#fafafa` | `#0f172a` | Chữ chính |
| `--fg-muted` | `#a1a1aa` | `#475569` | Chữ phụ, hint |
| `--fg-subtle` | `#71717a` | `#64748b` | Eyebrow, caption |

### 1.2 Màu — Accent & trạng thái

| Token | Dark | Light | Dùng cho |
| --- | --- | --- | --- |
| `--accent` | `#38bdf8` | `#0369a1` | Nút chính, nav active, focus, progress |
| `--accent-ink` | `#082f49` | `#ffffff` | Chữ trên nút accent |
| `--accent-soft` | `#123044` | `#e0f2fe` | Nền nav active, badge info |
| `--ai` | `#6366f1 → #a855f7` | (giữ) | AI-only: dialog header, sparkle, AI button |
| `--success` | `#4ade80` | `#15803d` | Reminder done, task done |
| `--warning` | `#fbbf24` | `#a16207` | Snooze, pending |
| `--danger` | `#f87171` | `#b91c1c` | Xoá, lỗi, redact |
| `--info` | `#38bdf8` | `#0369a1` | Entity link, URL |

State colors chỉ dùng cho **trạng thái thật** (M4): done/success, warning/snooze, danger/delete. Không dùng làm trang trí.

### 1.3 Typography

| Bậc | Size | Weight | Dùng cho |
| --- | --- | --- | --- |
| `display` | 60px | 600 | Timer Pomodoro |
| `title` | 23px | 650 | Tiêu đề trang (`MainTitle`) |
| `heading` | 16px | 650 | Brand, card title lớn |
| `subheading` | 14px | 650 | Card title |
| `body` | 13px | 400 | Nội dung chính |
| `small` | 12px | 500 | Nút, hint, nav |
| `caption` | 11px | 600 | Section label, eyebrow |
| `mono` | 13px | 400 | Timer, HEX, code |

Font family: `"Inter", "Noto Sans", system-ui, sans-serif`. Mono: `"Noto Sans Mono", "DejaVu Sans Mono", monospace`.
Tiếng Việt phải giữ dấu → dùng Noto Sans (đã có). Không dùng font thiếu glyph.

### 1.4 Nhịp & bo góc & viền

| Token | Giá trị | Ghi chú |
| --- | --- | --- |
| `--space-1` … `--space-6` | 4, 8, 12, 16, 24, 32 px | Chỉ dùng các bậc này (M16) |
| `--radius-sm` | 6px | Nút, input, badge |
| `--radius-md` | 9px | Reminder item, dropdown |
| `--radius-lg` | 12px | Card, dialog |
| `--radius-xl` | 16px | Modal lớn, overlay pill |
| `--border-width` | 1px | Viền mặc định (M13: tách bằng viền, không bằng bóng) |
| `--shadow` | none (flat) | Chỉ lớp nổi (overlay pill, AI dialog, modal) dùng shadow |

**Flat mặc định:** card tách bằng viền 1px + chênh lệch nền, **không bóng**. Shadow chỉ cho overlay nổi (M15).

### 1.5 Thanh cuộn (luôn chép)

Dáng thanh cuộn trong `tokens.css` (từ `* { --scrollbar-thumb` đến hết `.scrollbar-clean`) + component `ScrollbarAutohide` (I18). Thiếu là trình duyệt/Qt vẽ thanh mặc định to và thô.

## 2. Hợp đồng nguyên tố (D1) — bảy thứ, chốt một lần

Áp dụng cho PyQt6: dùng widget qfluent (`PushButton`, `LineEdit`, `CardWidget`, …) và QSS token ở §1. Không đẻ biến thể giữa chừng.

| Nguyên tố | Contract |
| --- | --- |
| **Nút** | Bốn dạng (I1) → map sang class Fluent (không QSS variant): `PrimaryPushButton` (accent), `PushButton` (mặc định), `TransparentPushButton` (quiet), `TogglePushButton` (chọn trạng thái). Nút **chỉ có icon** → `TransparentToolButton`. Min tap target 34px. |
| **Badge trạng thái** | Pill bo `--radius-sm`, padding 2px 8px, font caption 11px 600. Nền soft + chữ màu trạng thái (M7): todo=xám, doing=xám+icon dot, snooze=hổ phách, done=xanh lá, danger=đỏ. Cùng một trạng thái = cùng một hình ở mọi view (D2). |
| **Ô nhập** | `LineEdit` / `EditableComboBox` / `SpinBox` / `TimeEdit` của Fluent — cao 34px, bo 5px, viền 1px, focus viền accent của thư viện. Placeholder màu `--fg-muted` (Fluent không style placeholder → set QPalette). |
| **Card** | Padding 16px (md) / 20px (lg), bo `--radius-lg`, viền 1px `--border`, bg `--surface`. Không shadow. Card nổi (KPI, timer) dùng bg `--surface-2` + viền accent-soft. |
| **Dòng danh sách** | Chiều cao 44px, padding 10px 12px, hover bg `--surface-2`, selected bg `--accent-soft` + viền trái accent 2px. Checkbox 20px. |
| **Modal / dialog** | Bề rộng 480px (sm) / 640px (md) / 800px (lg). Nút đặt phải, primary phải; cho bấm ra ngoài đóng trừ khi có ô gõ xác nhận (I20). Backdrop `rgba(0,0,0,0.5)` + blur 8px. |
| **Trạng thái rỗng** | Icon 40px muted, tiêu đề 14px 650, câu phụ 12px muted, nút primary (nếu có action). Căn giữa trong vùng. |

## 3. Bảng ánh xạ trạng thái (D2) — một chỗ duy nhất

```python
STATUS = {
    "todo":   {"label": "Cần làm",   "color": "muted",   "icon": "circle"},
    "doing":  {"label": "Đang làm",  "color": "muted",   "icon": "circle-dot"},
    "snooze": {"label": "Tạm hoãn",  "color": "warning", "icon": "clock"},
    "done":   {"label": "Xong",      "color": "success", "icon": "circle-check"},
    "error":  {"label": "Lỗi",       "color": "danger",  "icon": "circle-x"},
}
```

Dùng y hệt ở Workbench (task list), Settings (reminder), overlay (OCR status). Trạng thái làm tiêu đề cột → icon + tên + số đếm (không pill). Trạng thái làm giá trị ô → pill.

## 4. Layout contract

### 4.1 Vùng (D6) — đặt tên một lần

| Tên | Mô tả | Code |
| --- | --- | --- |
| `Sidebar` | Cột trái 210px, nav + theme toggle + quit | `QFrame#Sidebar` |
| `Topbar` | Tiêu đề trang + subtitle + action buttons (capture, color) | `QFrame#Topbar` |
| `Content` | Vùng cuộn chính, padding 24px | `QScrollArea` |
| `DashboardGrid` | Grid 2 cột (tasks+notes \| pomodoro+reminders) gap 14px | `QGridLayout` |
| `OverlayPill` | Thanh công cụ nổi trên màn hình đóng băng | `QFrame#ActionBar` |
| `AiDialog` | Panel AI nổi, góc phải dưới | `QFrame#AiDialog` |

Code chết (không được hồi sinh): `GLASS_STYLE` inline overrides cho widget đã có qfluent tương đương; `QToolButton`/`QPushButton` thay bằng `qfluentwidgets`; `QWidget{background}` toàn cục; `theme_stylesheet` chỉ dùng cho card/nền/typography.

### 4.2 Bố cục mặc định theo loại màn

- **Workbench**: Sidebar (210) + Topbar + Content (DashboardGrid 2 cột: trái tasks+notes, phải pomodoro+reminders). Xem `references/layouts/app.md`.
- **Settings**: cùng shell, Content là stack card (General/AI, Shortcuts, System) với `SettingCard`.
- **Overlay capture**: fullscreen freeze + `OverlayPill` (top-center) + `SearchBar` (Ctrl+F). Không thay đổi pixel đã capture.
- **AI dialog**: floating panel 420×520, góc phải dưới, draggable.

### 4.3 Responsive (Qt window)

| Breakpoint | Hành vi |
| --- | --- |
| ≥ 1100px | Sidebar + 2 cột grid |
| 820–1099px | Sidebar thu 180px + 2 cột grid (gap 10) |
| < 820px | Sidebar ẩn (hamburger) + 1 cột stack |
| Overlay | Luôn fullscreen theo display captured; pill auto-wrap nếu > width |

Kiểm tại 375px logical (R): không cuộn ngang.

## 5. Inventory component — dùng cái đã có (S9)

| Đang có | Vị trí | Quyết định |
| --- | --- | --- |
| `OfficeWindow` | `ui/workspace.py` | Giữ, migrate widget sang qfluent |
| `theme_stylesheet`, `accent`, `primary_ink` | `ui/palette.py` | Giữ token, map sang Fluent theme |
| `GLASS_STYLE` | `ui/theme.py` | Giữ cho overlay, không đụng |
| `get_icon` | `ui/icons.py` | Giữ, icon Fluent `FluentIcon` khi có tương đương |
| i18n `t()` | `i18n.py` | Giữ, tất cả nhãn qua `t()` |
| `ProductivityService` | `productivity.py` | Giữ nguyên, không đụng logic |
| `apply_input_palette` | `ui/palette.py` | Giữ: chỉ set placeholder color (Fluent không style placeholder) |
| `sync_fluent_theme`, `apply_app_font` | `ui/fluent_theme.py` | **Mới** — đẩy theme + accent + font của app vào `qfluentwidgets` |
| `label(role)` | `ui/typography.py` | **Mới** — map vai trò chữ → label Fluent + màu light/dark |

Đã dựng theo qfluent: `FluentWindow` + `NavigationInterface` (sidebar), `TabWidget`, `ScrollArea`, `InfoBar` (toast đổi theme), `AcrylicWidget` (overlay), `RoundMenu`, `PillPushButton` (pill action bar).

## 6. Copy & i18n

- Tất cả nhãn UI qua `t(key)` trong `i18n.py`. Không hardcode tiếng Việt trong widget.
- Ngôn ngữ trả lời người dùng: theo ngôn ngữ đề (Vietnamese). Copy UI theo `T24`/`T28`: nếu dự án đang Vietnamese, giữ Vietnamese; thêm English key song song.
- Dữ liệu giả trong mockup: tên VN có dấu, số thực tế (Pomodoro 25/5, reminder 09:00–18:00).

## 7. Dark / Light

- Mặc định dark. Light qua toggle.
- `sync_fluent_theme(theme)` gọi `setTheme(Theme.DARK/LIGHT)` + `setThemeColor(accent)` + `setFontFamilies` → **mọi** control Fluent đổi màu theo app, kể cả control đã tạo trước đó.
- Overlay glass giữ `GLASS_STYLE` (đã có light overrides) nhưng không style lại control bên trong.
- Icon check SVG regenerate theo theme (đã có trong `theme_stylesheet`).
- Accent ink đảo: dark `#082f49` (chữ trên accent), light `#ffffff`.

## 8. Checklist trước khi báo xong (rút gọn)

- [ ] Câu 1 skill đã trả lời: migrate UI (không wireframe mới, giữ brand cyan + flat dark).
- [ ] Audit stack: PyQt6 + qfluent, không Tailwind → theo quy ước Qt/QSS.
- [ ] Bố cục mặc định Workbench/Settings/Overlay theo §4, báo một dòng.
- [ ] Không tự thêm section ngoài đề (S1).
- [ ] Cyan xuất hiện ≥5 chỗ (D5).
- [ ] Trạng thái dùng §3 y hệt mọi view (D2).
- [ ] Kiểm tại 375px logical: không cuộn ngang.
- [ ] Dark + light đều render đúng.
- [ ] Dữ liệu giả có dấu VN, phủ ca biên (S8).

## 9. Quyết định còn mở (hỏi một dòng khi cần)

- ✅ `AcrylicLabel` — đã thử, trên Linux render ra ô xanh mờ xấu → bỏ, dùng `PixmapLabel` sắc nét.
- ✅ Overlay glass → `AcrylicWidget` (`ActionBar`, `AIDialog`).
- ✅ `InfoBar` toast khi đổi theme.

---

*Contract này là bản v1. Khi thêm luật mới: tối đa 5 luật/đợt, ghi rõ thay thế luật nào, kèm điều kiện áp dụng, đánh dấu ⚑ nếu chưa test.*