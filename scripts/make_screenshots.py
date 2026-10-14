#!/usr/bin/env python
"""Generate README screenshots, tray shot and demo GIF on a synthetic desktop (no private content).

Run from the repo root:
    uv run --with qrcode python scripts/make_screenshots.py

Outputs to assets/screenshots/*.png and assets/demo.gif. Needs Noto Sans + ffmpeg-free (PIL only).
"""
import os
import sys
import threading
import time
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_SCALE_FACTOR"] = "2"
os.environ["XDG_CURRENT_DESKTOP"] = "niri"
os.environ["NIRI_SOCKET"] = "/nonexistent"

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

S = 2                      # backdrop pixel ratio
W, H = 1280, 760           # logical size
F_REG = "/usr/share/fonts/noto/NotoSans-Regular.ttf"
F_BOLD = "/usr/share/fonts/noto/NotoSans-Bold.ttf"


def font(size, bold=False):
    return ImageFont.truetype(F_BOLD if bold else F_REG, int(size * S))


# ---------------------------------------------------------------- backdrop
def build_backdrop() -> Image.Image:
    img = Image.new("RGB", (W * S, H * S))
    d = ImageDraw.Draw(img)
    for y in range(H * S):
        k = y / (H * S)
        d.line([(0, y), (W * S, y)], fill=(int(20 + 18 * k), int(24 + 14 * k), int(52 + 40 * k)))
    blobs = Image.new("RGB", img.size, (0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    bd.ellipse((-200 * S, 380 * S, 560 * S, 1000 * S), fill=(70, 40, 140))
    bd.ellipse((820 * S, -240 * S, 1500 * S, 360 * S), fill=(20, 90, 150))
    blobs = blobs.filter(ImageFilter.GaussianBlur(120 * S))
    img = ImageChops.add(img, blobs)
    d = ImageDraw.Draw(img, "RGBA")

    # --- top panel
    d.rectangle((0, 0, W * S, 34 * S), fill=(10, 10, 16, 235))
    for i in range(3):
        c = (56, 189, 248, 255) if i == 0 else (120, 120, 140, 255)
        d.rounded_rectangle((14 * S + i * 22 * S, 12 * S, 14 * S + i * 22 * S + 14 * S, 22 * S), 5 * S, fill=c)
    d.text((90 * S, 8 * S), "Th 3, 14 Th10   09:41", font=font(13), fill=(228, 228, 231))
    x = 1280 - 18
    try:
        ic = Image.open(ROOT / "src/click_to_do_linux/assets/icon-64.png").convert("RGBA").resize((20 * S, 20 * S))
        img.paste(ic, ((1280 - 38) * S, 7 * S), ic)
    except Exception:
        pass
    d = ImageDraw.Draw(img, "RGBA")
    x = 1280 - 72
    d.rounded_rectangle((x * S, 12 * S, (x + 22) * S, 22 * S), 3 * S, outline=(228, 228, 231), width=S + 1)   # battery
    d.ellipse(((x - 28) * S, 9 * S, (x - 10) * S, 25 * S), outline=(228, 228, 231), width=S + 1)             # wifi-ish
    d.ellipse(((x - 56) * S, 10 * S, (x - 42) * S, 24 * S), fill=(228, 228, 231))                             # volume-ish

    def window(x0, y0, x1, y1, title, dark=False):
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rounded_rectangle(
            (x0 * S, (y0 + 10) * S, x1 * S, (y1 + 10) * S), 14 * S, fill=(0, 0, 0, 150))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18 * S))
        img.paste(shadow, (0, 0), shadow)
        dd = ImageDraw.Draw(img, "RGBA")
        body = (24, 24, 30) if dark else (250, 250, 252)
        bar = (38, 38, 46) if dark else (233, 235, 241)
        dd.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), 14 * S, fill=body)
        dd.rounded_rectangle((x0 * S, y0 * S, x1 * S, (y0 + 40) * S), 14 * S, fill=bar)
        dd.rectangle((x0 * S, (y0 + 24) * S, x1 * S, (y0 + 40) * S), fill=bar)
        for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            dd.ellipse(((x0 + 16 + i * 20) * S, (y0 + 14) * S, (x0 + 28 + i * 20) * S, (y0 + 26) * S), fill=c)
        dd.text(((x0 + 100) * S, (y0 + 9) * S), title, font=font(14, True),
                fill=(228, 228, 231) if dark else (40, 40, 52))
        return dd

    # --- window 1: notes (light)
    d = window(70, 70, 720, 700, "Ghi chú dự án — Notes")
    ink, sub = (24, 24, 36), (90, 90, 110)
    d.text((110 * S, 128 * S), "Lịch họp tuần này", font=font(28, True), fill=ink)
    lines = [
        "Thứ Hai: Họp nhóm phát triển lúc 9:30 sáng",
        "Thứ Tư: Báo cáo tiến độ cho khách hàng",
        "Meeting notes: ship the Wayland release on Friday",
        "Liên hệ: support@clicktodo.dev",
        "Tài liệu: https://github.com/thanhnndev/click-to-do-linux",
        "Mật khẩu Wi-Fi: Cộng hòa xã hội chủ nghĩa Việt Nam",
        "Khoảng 3.200 người đã tải về trong tháng này",
    ]
    for i, tx in enumerate(lines):
        y = 190 + i * 56
        d.text((134 * S, y * S), tx, font=font(19), fill=ink)

    # --- window 2: moodboard (dark)
    d = window(760, 70, 1220, 700, "Moodboard", dark=True)
    sw = [((124, 58, 237), "#7C3AED"), ((245, 158, 11), "#F59E0B"), ((16, 185, 129), "#10B981")]
    for i, (c, hx) in enumerate(sw):
        x0 = 790 + i * 142
        d.rounded_rectangle((x0 * S, 130 * S, (x0 + 130) * S, 215 * S), 14 * S, fill=c)
        d.text(((x0 + 14) * S, 160 * S), hx, font=font(17, True), fill=(255, 255, 255))
    # illustration (sunset + mountains + mascot subject)
    ix0, iy0, ix1, iy1 = 790, 245, 1190, 520
    ill = Image.new("RGB", ((ix1 - ix0) * S, (iy1 - iy0) * S))
    idr = ImageDraw.Draw(ill)
    for y in range(ill.height):
        k = y / ill.height
        idr.line([(0, y), (ill.width, y)], fill=(int(250 - 90 * k), int(150 - 70 * k), int(120 + 80 * k)))
    idr.ellipse((250 * S, 40 * S, 330 * S, 120 * S), fill=(255, 226, 150))
    idr.polygon([(0, 275 * S), (110 * S, 120 * S), (210 * S, 275 * S)], fill=(60, 50, 110))
    idr.polygon([(140 * S, 275 * S), (270 * S, 150 * S), (400 * S, 275 * S)], fill=(40, 34, 88))
    # mascot
    cx, cy = 150 * S, 190 * S
    idr.ellipse((cx - 62 * S, cy - 40 * S, cx + 62 * S, cy + 84 * S), fill=(56, 189, 248))
    idr.ellipse((cx - 30 * S, cy - 4 * S, cx - 10 * S, cy + 16 * S), fill="white")
    idr.ellipse((cx + 10 * S, cy - 4 * S, cx + 30 * S, cy + 16 * S), fill="white")
    idr.ellipse((cx - 24 * S, cy + 2 * S, cx - 16 * S, cy + 10 * S), fill=(20, 20, 30))
    idr.ellipse((cx + 16 * S, cy + 2 * S, cx + 24 * S, cy + 10 * S), fill=(20, 20, 30))
    idr.arc((cx - 20 * S, cy + 24 * S, cx + 20 * S, cy + 54 * S), 20, 160, fill=(20, 20, 30), width=3 * S)
    mask = Image.new("L", ill.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, ill.width, ill.height), 16 * S, fill=255)
    img.paste(ill, (ix0 * S, iy0 * S), mask)
    d = ImageDraw.Draw(img, "RGBA")
    # QR
    qr_rect = (800, 555, 920, 675)
    try:
        import qrcode
        q = qrcode.make("https://github.com/thanhnndev/click-to-do-linux").convert("RGB").resize((120 * S, 120 * S), Image.NEAREST)
        d.rounded_rectangle(((qr_rect[0] - 6) * S, (qr_rect[1] - 6) * S, (qr_rect[2] + 6) * S, (qr_rect[3] + 6) * S), 8 * S, fill="white")
        img.paste(q, (qr_rect[0] * S, qr_rect[1] * S))
    except Exception as e:  # pragma: no cover
        print("qrcode missing:", e)
    d = ImageDraw.Draw(img, "RGBA")
    d.text((950 * S, 585 * S), "Quét để mở dự án", font=font(18, True), fill=(244, 244, 245))
    d.text((950 * S, 620 * S), "github.com/thanhnndev/click-to-do-linux", font=font(12), fill=(161, 161, 170))
    return img


# ---------------------------------------------------------------- framing
def rounded(img: Image.Image, r: int) -> Image.Image:
    img = img.convert("RGBA")
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, *img.size), r, fill=255)
    img.putalpha(m)
    return img


def framed(img: Image.Image, width=1500, margin=70, radius=22) -> Image.Image:
    """Rounded window with soft shadow on a brand gradient."""
    img = img.convert("RGB")
    h = int(img.height * width / img.width)
    img = rounded(img.resize((width, h), Image.LANCZOS), radius)
    cw, ch = width + margin * 2, h + margin * 2
    bg = Image.new("RGB", (cw, ch))
    px = bg.load()
    c0, c1 = (99, 102, 241), (56, 189, 248)
    for y in range(ch):
        for x in range(0, cw, 1):
            k = (x / cw * 0.6 + y / ch * 0.4)
            px[x, y] = (int(c0[0] + (c1[0] - c0[0]) * k), int(c0[1] + (c1[1] - c0[1]) * k), int(c0[2] + (c1[2] - c0[2]) * k))
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((margin, margin + 18, margin + width, margin + h + 18), radius, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(26))
    bg = bg.convert("RGBA")
    bg.alpha_composite(sh)
    bg.alpha_composite(img, (margin, margin))
    return bg.convert("RGB")


# ---------------------------------------------------------------- Qt part
from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
from PyQt6.QtGui import QAction, QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMenu, QToolButton

app = QApplication(sys.argv)


def pump(sec=0.2):
    t0 = time.time()
    while time.time() - t0 < sec:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.02)


def grab(widget) -> Image.Image:
    pump(0.15)
    qi = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = qi.constBits()
    ptr.setsize(qi.sizeInBytes())
    return Image.frombuffer("RGBA", (qi.width(), qi.height()), bytes(ptr), "raw", "RGBA", qi.bytesPerLine(), 1).convert("RGB")


backdrop = build_backdrop()
backdrop.save("/tmp/ctd_backdrop.png")

from click_to_do_linux import i18n
from click_to_do_linux.ai.segmentation import SegmentationEngine
from click_to_do_linux.capture.screen import CapturedScreen
from click_to_do_linux.ui.ai_dialog import AIDialog
from click_to_do_linux.ui.icons import get_icon
from click_to_do_linux.ui.overlay import OverlayWindow

i18n.set_lang("vi")
qimg = QImage("/tmp/ctd_backdrop.png").convertToFormat(QImage.Format.Format_RGB32)
pm = QPixmap.fromImage(qimg)
pm.setDevicePixelRatio(S)
cap = CapturedScreen(image=backdrop, pixmap=pm, physical_w=W * S, physical_h=H * S,
                     logical_w=W, logical_h=H, scale_factor=float(S), qt_screen=None, output_name="demo")

ov = OverlayWindow(cap)
ov.show()
t0 = time.time()
while not ov.ocr_boxes and time.time() - t0 < 180:
    pump(0.2)
pump(0.5)
print("OCR:", [b.text for b in ov.ocr_boxes], "QR:", len(ov.qr_entities))


def box(sub):
    for b in ov.ocr_boxes:
        if sub.lower() in b.text.lower():
            return b
    raise SystemExit(f"box not found: {sub}")


def select(boxes):
    ov.selected_boxes = list(boxes)
    xs = [b.rect[0] for b in boxes]; ys = [b.rect[1] for b in boxes]
    xe = [b.rect[0] + b.rect[2] for b in boxes]; ye = [b.rect[1] + b.rect[3] for b in boxes]
    r = (min(xs), min(ys), max(xe) - min(xs), max(ye) - min(ys))
    ov.selected_rect = QRect(*r)
    ov._show_actions_for_text("\n".join(b.text for b in boxes), r)
    return r


def reset():
    ov.selected_boxes = []; ov.selected_rect = None; ov.hovered_box = None
    ov.action_bar.hide(); ov.color_picker_active = False; ov.search_query = ""
    ov.top_bar.show()


def crop_logical(img, rects, pad=70, min_w=760, min_h=430):
    x0 = min(r[0] for r in rects) - pad; y0 = min(r[1] for r in rects) - pad
    x1 = max(r[0] + r[2] for r in rects) + pad; y1 = max(r[1] + r[3] for r in rects) + pad
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = max(x1 - x0, min_w), max(y1 - y0, min_h)
    h = max(h, w * 9 / 16); w = max(w, h * 16 / 9)
    x0 = max(0, min(W - w, cx - w / 2)); y0 = max(60, min(H - h, cy - h / 2))
    return img.crop((int(x0 * S), int(y0 * S), int((x0 + w) * S), int((y0 + h) * S)))


def abar_rect():
    g = ov.action_bar.geometry()
    return (g.x(), g.y(), g.width(), g.height())


def save(name, img):
    framed(img).save(OUT / name, optimize=True)
    print("saved", name)


# ---- stills
reset(); save("01-overlay-ocr.png", grab(ov))
b = box("Họp nhóm"); r = select([b]); full = grab(ov); save("02-text-actions.png", crop_logical(full, [r, abar_rect()]))
b = box("https://github.com/thanhnndev/click-to-do-linux"); r = select([b]); save("03-url-actions.png", crop_logical(grab(ov), [r, abar_rect()]))
reset(); r = select([box("Thứ Hai"), box("Thứ Tư")]); save("04-multi-select.png", crop_logical(grab(ov), [r, abar_rect()]))
reset(); rr = (790, 245, 400, 275)
ov.selected_rect = QRect(*rr)
crop = SegmentationEngine.crop_logical_region(cap.image, rr, cap.scale_factor)
ov.action_bar.show_for_image(crop, text_inside="")
ov.action_bar.reposition(rr, W, H)
save("05-image-actions.png", crop_logical(grab(ov), [rr, abar_rect()], pad=40))
reset()
q = ov.qr_entities[0]; ov.action_bar.show_for_qr(q.text, q.is_url); ov.action_bar.reposition(q.rect, W, H)
save("06-qr.png", crop_logical(grab(ov), [q.rect, abar_rect()], pad=60))
reset(); ov.search_input.setText("họp"); ov._toggle_search_bar(); save("07-search.png", grab(ov))
ov.search_input.setText(""); ov.search_query = ""
reset(); ov.color_picker_active = True; ov.cursor_pos = QPoint(856, 196); save("08-color-picker.png", crop_logical(grab(ov), [(740, 120, 260, 100)], pad=120))
reset()

ev = threading.Event()
TRANSLATION = "Monday: Development team meeting at 9:30 AM"


def gen():
    ev.wait(120)
    yield ""


reset(); r = select([box("Họp nhóm")])
dlg = AIDialog(i18n.t("translate"), gen, ov)
dlg.move((W - dlg.width()) // 2, 300); dlg.show()
dlg._on_chunk(TRANSLATION)
dlg._on_finished()
save("09-ai-dialog.png", crop_logical(grab(ov), [(dlg.x(), dlg.y(), dlg.width(), dlg.height()), r], pad=60))
ev.set(); dlg.hide(); reset()

# ---- tray
menu = QMenu()
menu.setStyleSheet("""
    QMenu { background-color: #141418; border: 1px solid #27272a; border-radius: 8px; padding: 4px; color: #e4e4e7; font-size: 12px; }
    QMenu::item { padding: 6px 18px 6px 10px; border-radius: 5px; }
    QMenu::item:selected { background-color: #27272a; color: #ffffff; }
""")
a1 = QAction(get_icon("sparkles", "#38bdf8", 14), i18n.t("tray_capture"), menu); menu.addAction(a1)
menu.addAction(QAction(get_icon("pipette", "#e4e4e7", 14), i18n.t("tray_color"), menu))
menu.addSeparator()
menu.addAction(QAction(get_icon("settings", "#e4e4e7", 14), i18n.t("tray_settings"), menu))
menu.addAction(QAction(get_icon("power", "#f87171", 14), i18n.t("tray_quit"), menu))
menu.setActiveAction(a1)
menu.show(); pump(0.3)
mimg = grab(menu)
tray = backdrop.crop((int(700 * S), 0, W * S, int(300 * S))).copy()
td = ImageDraw.Draw(tray, "RGBA")
tx = (W - 38 + 10 - 700) * S
td.ellipse((tx - 18 * S, 17 * S - 18 * S, tx + 18 * S, 17 * S + 18 * S), outline=(56, 189, 248, 255), width=2 * S)
mx = min(tray.width - mimg.width - 10 * S, tx - mimg.width // 2)
tray.paste(mimg, (mx, 40 * S))
save("10-tray.png", tray)
menu.hide()

# ---- settings
from click_to_do_linux.ui.setup_window import SetupWindow
for lang in ("vi", "en"):
    import click_to_do_linux.ui.setup_window as sw
    _real_load = sw.load_config
    sw.load_config = lambda lang=lang: (lambda c: (setattr(c, "ui_language", lang), c)[1])(_real_load())
    w = SetupWindow(); w.show(); pump(0.5)
    sw.load_config = _real_load
    home = str(Path.home())
    from PyQt6.QtWidgets import QLabel
    for lb in w.findChildren(QLabel):
        if home in lb.text():
            lb.setText(lb.text().replace(home, "~"))
    for i in range(w.tabs.count()):
        w.tabs.setCurrentIndex(i); pump(0.4)
        framed(grab(w), width=900, margin=50, radius=18).save(OUT / f"settings-{lang}-{i + 1}.png", optimize=True)
    w.close()
i18n.set_lang("vi")

# ---------------------------------------------------------------- GIF
frames: list[tuple[Image.Image, int]] = []
GW = 1000
cap_font = ImageFont.truetype(F_BOLD, 30)
key_font = ImageFont.truetype(F_BOLD, 26)


def cursor(img, x, y):
    d = ImageDraw.Draw(img)
    p = [(x, y), (x, y + 30), (x + 8, y + 23), (x + 14, y + 36), (x + 20, y + 33), (x + 14, y + 21), (x + 25, y + 21)]
    d.polygon(p, fill="white", outline="black")


def add(img, caption, ms=200, cur=None, keys=None):
    im = img.copy()
    d = ImageDraw.Draw(im, "RGBA")
    if cur:
        cursor(im, cur[0] * S, cur[1] * S)
    if keys:
        x = 40 * S
        for k in keys:
            tw = d.textlength(k, font=key_font)
            d.rounded_rectangle((x, (H - 70) * S - 8, x + tw + 36, (H - 70) * S + 44), 12, fill=(255, 255, 255, 235), outline=(160, 160, 170), width=2)
            d.text((x + 18, (H - 70) * S), k, font=key_font, fill=(20, 20, 30))
            x += tw + 52
    if caption:
        tw = d.textlength(caption, font=cap_font)
        x0 = (im.width - tw) / 2 - 28
        y0 = im.height - 92 * S // 1 + 0
        y0 = im.height - 84
        d.rounded_rectangle((x0, y0, x0 + tw + 56, y0 + 62), 31, fill=(12, 12, 18, 225))
        d.text((x0 + 28, y0 + 11), caption, font=cap_font, fill=(244, 244, 245))
    frames.append((im.resize((GW, int(im.height * GW / im.width)), Image.LANCZOS), ms))


def lerp(a, b, k):
    return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)


def move(frm, to, caption, steps=4, ms=70, setup=None):
    for i in range(1, steps + 1):
        p = lerp(frm, to, i / steps)
        ov.cursor_pos = QPoint(int(p[0]), int(p[1]))
        if setup:
            setup(p)
        add(grab(ov), caption, ms, cur=p)


# scene 0: desktop + hotkey
desk = backdrop.copy()
add(desk, "1 · Nhấn phím tắt để chụp màn hình", 1100, keys=["Mod", "Shift", "C"])
# scene 1: overlay
reset()
saved_boxes, saved_qr = ov.ocr_boxes, ov.qr_entities
ov.ocr_boxes, ov.qr_entities = [], []
add(grab(ov), "2 · Màn hình đóng băng, OCR chạy nền", 600)
ov.ocr_boxes, ov.qr_entities = saved_boxes, saved_qr
add(grab(ov), "2 · Mọi dòng chữ đều chọn được (giữ dấu tiếng Việt)", 1300)

# scene 2: hover + click text
target = box("Họp nhóm")
tc = (target.rect[0] + 120, target.rect[1] + target.rect[3] // 2)
def hover(p):
    ov.hovered_box = OCR_find(p)
from click_to_do_linux.ai.ocr import OCREngine as OCR_
def OCR_find(p):
    return OCR_.find_box_at(ov.ocr_boxes, p[0], p[1])
move((900, 180), tc, "3 · Trỏ vào chữ để chọn", steps=4, setup=hover)
r = select([target])
add(grab(ov), "3 · Bấm để mở thanh thao tác", 1100, cur=tc)

# scene 3: translate
tb = None
for btn in ov.action_bar.findChildren(QToolButton):
    if btn.text().strip().lower().startswith(i18n.t("translate").lower()):
        tb = btn
if tb is not None:
    c = tb.mapTo(ov, tb.rect().center())
    move(tc, (c.x(), c.y()), "4 · Dịch bằng AI chạy cục bộ (Ollama)", steps=4)
    add(grab(ov), "4 · Dịch bằng AI chạy cục bộ (Ollama)", 400, cur=(c.x(), c.y()))
ev2 = threading.Event()
def gen2():
    ev2.wait(120)
    yield ""
dlg = AIDialog(i18n.t("translate"), gen2, ov)
dlg.move((W - dlg.width()) // 2, 300); dlg.show()
for i in range(1, 5):
    dlg._on_chunk(" ".join(TRANSLATION.split(" ")[(i - 1) * 2:i * 2]) + " ")
    add(grab(ov), "4 · Kết quả hiện theo thời gian thực", 260)
add(grab(ov), "4 · Kết quả hiện theo thời gian thực", 1400)
ev2.set(); dlg.hide(); dlg.deleteLater(); reset(); pump(0.2)

# scene 4: drag-select image
p0, p1 = (800, 255), (1180, 515)
for i in range(1, 6):
    p = lerp(p0, p1, i / 5)
    ov.selected_rect = QRect(QPoint(*p0), QPoint(int(p[0]), int(p[1]))).normalized()
    add(grab(ov), "5 · Kéo chọn vùng ảnh bất kỳ", 110, cur=p)
rr = (p0[0], p0[1], p1[0] - p0[0], p1[1] - p0[1])
crop = SegmentationEngine.crop_logical_region(cap.image, rr, cap.scale_factor)
ov.action_bar.show_for_image(crop, text_inside="")
ov.action_bar.reposition(rr, W, H)
add(grab(ov), "5 · Cutout · Làm mờ nền · Che thông tin · Lưu", 1800, cur=p1)
reset()

# scene 5: QR
q = ov.qr_entities[0]
ov.action_bar.show_for_qr(q.text, q.is_url); ov.action_bar.reposition(q.rect, W, H)
add(grab(ov), "6 · Tự nhận diện mã QR và liên kết", 1500, cur=(q.rect[0] + 40, q.rect[1] + 40))
reset()

# scene 6: color picker
ov.color_picker_active = True
for i, pt in enumerate([(1000, 190), (856, 196)]):
    ov.cursor_pos = QPoint(*pt)
    add(grab(ov), "7 · Lấy mã màu HEX bằng ống hút", 500 if i == 0 else 900, cur=pt)
ov.color_picker_active = False
reset()

# scene 7: find
ov.search_input.setText("họp"); ov._toggle_search_bar()
add(grab(ov), "8 · Ctrl+F tìm chữ ngay trên màn hình", 1500)
ov.search_input.setText(""); ov.search_query = ""
reset()
add(grab(ov), "Click to Do for Linux · github.com/thanhnndev/click-to-do-linux", 1500)

pal = [f.convert("P", palette=Image.ADAPTIVE, colors=256, dither=Image.NONE) for f, _ in frames]
pal[0].save(ROOT / "assets" / "demo.gif", save_all=True, append_images=pal[1:],
            duration=[ms for _, ms in frames], loop=0, optimize=True, disposal=2)
print("gif frames:", len(frames), "size KB:", (ROOT / "assets/demo.gif").stat().st_size // 1024)
ov.close()
