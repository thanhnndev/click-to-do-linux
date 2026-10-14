import os, sys, time
os.environ["QT_QPA_PLATFORM"]="offscreen"
os.environ["XDG_CURRENT_DESKTOP"]="niri"
os.environ["NIRI_SOCKET"]="/nonexistent"
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
OUT=Path("/home/thanhnndev/develop/projects/click-to-do-linux/assets/screenshots")
W,H=1280,760
F="/usr/share/fonts/TTF/DejaVuSans.ttf"
if not os.path.exists(F):
    import subprocess
    F=subprocess.check_output(["fc-match","-f","%{file}","DejaVu Sans"]).decode()
def font(s,b=False):
    return ImageFont.truetype(F.replace("Sans.ttf","Sans-Bold.ttf") if b else F, s)
img=Image.new("RGB",(W,H),(24,26,38))
d=ImageDraw.Draw(img)
for y in range(H): d.line([(0,y),(W,y)],fill=(24+y//20,26+y//25,48+y//12))
d.rounded_rectangle((120,70,800,690),14,fill=(250,250,252))
d.rectangle((120,70,800,112),fill=(232,234,240)); d.text((140,82),"Ghi chú dự án — Click to Do",font=font(15,True),fill=(30,30,40))
lines=[("Lịch họp tuần này",24,True),
("Thứ Hai: Họp nhóm phát triển lúc 9:30 sáng",18,False),
("Thứ Tư: Báo cáo tiến độ cho khách hàng",18,False),
("Meeting notes: ship the Wayland release on Friday",18,False),
("Liên hệ: support@clicktodo.dev",18,False),
("Tài liệu: https://github.com/thanhnndev/click-to-do-linux",18,False),
("Mật khẩu Wi-Fi: Cộng hòa xã hội chủ nghĩa Việt Nam",18,False),
("Khoảng 3.200 người đã tải về trong tháng này",18,False)]
y=140
for txt,s,b in lines:
    d.text((150,y),txt,font=font(s,b),fill=(20,20,30)); y+=52
# colored swatch + QR-like
d.rounded_rectangle((850,110,1150,230),16,fill=(124,58,237))
d.rounded_rectangle((850,260,1150,380),16,fill=(245,158,11))
d.text((880,150),"#7C3AED",font=font(22,True),fill="white")
d.ellipse((900,430,1100,630),fill=(56,189,248)); d.rectangle((940,470,1060,590),fill=(14,116,144))
try:
    import qrcode
    q=qrcode.make("https://github.com/thanhnndev/click-to-do-linux").convert("RGB").resize((150,150)); img.paste(q,(1000,520))
except Exception as e: print("no qrcode",e)
img.save("/tmp/demo_backdrop.png")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtCore import QPoint, QRect, QTimer, Qt
app=QApplication(sys.argv)
from click_to_do_linux.capture.screen import CapturedScreen
def pump(sec):
    t=time.time()
    while time.time()-t<sec:
        app.processEvents()
        from PyQt6.QtCore import QCoreApplication, QEvent
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.02)
qimg=QImage("/tmp/demo_backdrop.png").convertToFormat(QImage.Format.Format_RGB32)
cap=CapturedScreen(image=img,pixmap=QPixmap.fromImage(qimg),physical_w=W,physical_h=H,logical_w=W,logical_h=H,scale_factor=1.0,qt_screen=None,output_name="demo")
from click_to_do_linux.ui.overlay import OverlayWindow
from click_to_do_linux.ai.ocr import OCREngine
from click_to_do_linux.ai.entities import EntityDetector
from click_to_do_linux.ai.segmentation import SegmentationEngine
ov=OverlayWindow(cap); ov.show()
t0=time.time()
while not ov.ocr_boxes and time.time()-t0<120: pump(0.2)
pump(0.5)
print("boxes",[b.text for b in ov.ocr_boxes],"qr",len(ov.qr_entities))
def snap(name): pump(0.3); ov.grab().save(str(OUT/name)); print("saved",name)
snap("01-overlay-ocr.png")
def box(sub):
    for b in ov.ocr_boxes:
        if sub.lower() in b.text.lower(): return b
    return ov.ocr_boxes[0]
# text select
b=box("Họp nhóm") ; ov.selected_boxes=[b]; ov.selected_rect=QRect(*b.rect); ov._show_actions_for_text(b.text,b.rect); snap("02-text-actions.png")
# url
b=box("https"); ov.selected_boxes=[b]; ov.selected_rect=QRect(*b.rect); ov._show_actions_for_text(b.text,b.rect); snap("03-url-actions.png")
# multi
ov.selected_boxes=[box("Thứ Hai"),box("Thứ Tư")]; r=ov.selected_boxes
u=(min(x.rect[0] for x in r),min(x.rect[1] for x in r),max(x.rect[0]+x.rect[2] for x in r)-min(x.rect[0] for x in r),max(x.rect[1]+x.rect[3] for x in r)-min(x.rect[1] for x in r))
ov.selected_rect=QRect(*u); ov._show_actions_for_text("\n".join(x.text for x in r),u); snap("04-multi-select.png")
# image region
ov.selected_boxes=[]; rr=(860,400,200,200); ov.selected_rect=QRect(*rr)
crop=SegmentationEngine.crop_logical_region(cap.image,rr,1.0); ov.action_bar.show_for_image(crop,text_inside=""); ov.action_bar.reposition(rr,W,H); snap("05-image-actions.png")
# qr
if ov.qr_entities:
    q=ov.qr_entities[0]; ov.selected_rect=None; ov.action_bar.show_for_qr(q.text,q.is_url); ov.action_bar.reposition(q.rect,W,H); snap("06-qr.png")
# search
ov.selected_rect=None; ov.action_bar.hide(); ov.search_input.setText("họp"); ov._toggle_search_bar(); snap("07-search.png")
ov.search_input.setText("")
# color picker
ov.search_query=""; ov.color_picker_active=True; ov.cursor_pos=QPoint(980,170); snap("08-color-picker.png")
ov.color_picker_active=False
# AI dialog
from click_to_do_linux.ui.ai_dialog import AIDialog
def gen():
    yield "Lịch họp tuần này gồm hai mốc chính:\n\n• Thứ Hai 9:30 — họp nhóm phát triển\n• Thứ Tư — báo cáo tiến độ cho khách hàng\n\nCuối tuần cần phát hành bản Wayland vào thứ Sáu."
dlg=AIDialog("Tóm tắt",gen,ov); dlg.move(260,200); dlg.show(); pump(1.5); snap("09-ai-dialog.png")
dlg.hide(); ov.close()

from click_to_do_linux.ui.setup_window import SetupWindow
from click_to_do_linux import i18n
for lang in ("vi","en"):
    i18n.set_lang(lang)
    w=SetupWindow(); w.show(); pump(0.5)
    for i in range(w.tabs.count()):
        w.tabs.setCurrentIndex(i); pump(0.4)
        w.grab().save(str(OUT/f"settings-{lang}-{i+1}.png")); print("settings",lang,i)
    w.close()
