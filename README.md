# Click to Do (Linux) 🚀

> **Port tính năng "Click to Do" từ Windows 11 Copilot+ PC sang Linux**, tận dụng khả năng tăng tốc phần cứng từ **AI NPU** (AMD XDNA 2 / Intel VPU), **GPU** (NVIDIA RTX / AMD ROCm), và **CPU đa nhân AVX-512**.

---

## 🌟 Giới thiệu

Trên Windows 11 24H2 Copilot+ PC, **Click to Do** là tính năng tương tác màn hình thông minh:
Khi bạn bấm phím tắt, màn hình lập tức đóng băng lại với giao diện overlay hiện đại. AI sẽ phân tích toàn bộ màn hình để:
- **Tự động nhận diện chữ (OCR)**: Cho phép chọn từ, đoạn văn, copy văn bản, tìm kiếm Google, hoặc gọi trợ lý AI để Tóm tắt / Giải thích / Dịch thuật.
- **Tách nền thông minh (Subject Cutout)**: Tự động tách chủ thể (người, đồ vật, icon, sản phẩm) ra khỏi nền thành ảnh PNG trong suốt lưu vào clipboard.
- **Làm mờ nền (Background Blur)**: Giữ chủ thể rõ nét và làm mờ phông nền xung quanh.
- **Quét mã QR & Liên kết**: Tự động nhận diện mã QR trên màn hình để click mở web hoặc copy link ngay lập tức.
- **Trợ lý AI cục bộ (Local LLM via Ollama)**: Tóm tắt, giải thích code, dịch thuật trực tiếp không phụ thuộc cloud.

Dự án **Click to Do Linux** tái hiện hoàn hảo trải nghiệm này trên Linux (hỗ trợ đầy đủ Wayland như **Niri**, **Hyprland**, **Sway**, **KDE Plasma**, **GNOME**).

---

## ⚡ Kiến trúc tăng tốc phần cứng AI (NPU & GPU)

Hệ thống được thiết kế theo kiến trúc module đa tầng với **ONNX Runtime**:
1. **NPU Backend**:
   - Hỗ trợ **AMD XDNA 2 NPU** (Ryzen AI 9 HX 370 / Strix Point 50 TOPS qua driver kernel `amdxdna` và node `/dev/accel/accel0`).
   - Hỗ trợ **Intel NPU** (Core Ultra qua `intel_vpu` và OpenVINO).
2. **GPU Backend**:
   - NVIDIA GPU (RTX 5060, 4060, v.v.) qua CUDA / TensorRT.
3. **CPU Zen 5 AVX-512**:
   - Fallback siêu tốc với tập lệnh đa luồng AVX-512.

---

## 🛠️ Cài đặt & Quản lý môi trường (với `mise` và `uv`)

Dự án tích hợp sẵn file `.mise.toml` để quản lý runtime:

```bash
# 1. Kiểm tra môi trường với mise
mise install

# 2. Cài đặt các thư viện cần thiết với uv
uv sync
```

---

## 🖥️ Hướng dẫn sử dụng

### 1. Kiểm tra phần cứng AI NPU & GPU
Chạy lệnh chẩn đoán phần cứng:
```bash
uv run click-to-do status
```
*Kết quả sẽ hiển thị chi tiết NPU (`/dev/accel/accel0`), driver `amdxdna`, GPU, và Engine đang kích hoạt.*

### 2. Kích hoạt Click to Do (Overlay Mode)
```bash
uv run click-to-do capture
```
Hoặc:
```bash
uv run click-to-do
```

### 3. Thao tác trên giao diện
- **Bấm vào chữ**: Tự động chọn dòng chữ đó và hiện menu:
  - 📋 **Sao chép** (Copy text)
  - 🌐 **Mở liên kết** (Nếu có URL)
  - 🔍 **Tìm kiếm Google / DuckDuckGo**
  - 🤖 **Trợ lý AI**: Tóm tắt, Giải thích, Dịch sang Tiếng Việt, Viết lại câu.
- **Kéo chuột (Drag & Drop)**: Chọn một vùng hình chữ nhật bất kỳ:
  - 📋 **Sao chép ảnh** vào Clipboard
  - ✂️ **Tách nền (AI Cutout)**: Tách chủ thể thành PNG trong suốt
  - 🌫️ **Làm mờ nền**: Blur phông nền xung quanh
  - 🔍 **Tìm ảnh với Google Lens**
  - 💾 **Lưu file ảnh**
- **Bấm vào mã QR**: Mở trực tiếp link trong trình duyệt hoặc copy nội dung mã.
- **Thoát**: Bấm phím `Esc` hoặc nhấp chuột phải bất kỳ đâu để đóng overlay.

---

## ⌨️ Cài đặt phím tắt (Hotkey Integration)

Xem hướng dẫn cấu hình phím tắt cho Desktop của bạn:
```bash
uv run click-to-do setup
```

### Cấu hình cho **Niri** (`~/.config/niri/config.kdl`):
Thêm vào block `binds { ... }`:
```kdl
binds {
    Mod+Q { spawn "click-to-do" "capture"; }
    Print { spawn "click-to-do" "capture"; }
}
```

### Cấu hình cho **Hyprland** (`~/.config/hypr/hyprland.conf`):
```ini
bind = SUPER, Q, exec, click-to-do capture
bind = , Print, exec, click-to-do capture
```

### Cấu hình cho **KDE Plasma / GNOME**:
Vào **Settings -> Keyboard -> Shortcuts -> Custom Shortcuts**:
- Tên: `Click to Do`
- Lệnh: `click-to-do capture` (hoặc đường dẫn tới binary trong virtualenv: `/path/to/click-to-do-linux/.venv/bin/click-to-do capture`)
- Phím tắt: `Super + Q` hoặc `PrintScreen`

---

## ⚙️ Tùy biến cấu hình (`~/.config/click-to-do/config.json`)

File cấu hình tự động được sinh tại `~/.config/click-to-do/config.json`:
```json
{
  "ai_provider": "auto",
  "ocr_engine": "rapidocr",
  "bg_removal_model": "isnet-general-use",
  "ollama_enabled": true,
  "ollama_host": "http://localhost:11434",
  "ollama_model": "qwen2.5:latest",
  "target_language": "vi",
  "search_engine": "google",
  "visual_search": "google_lens",
  "theme": "dark_glass",
  "save_directory": "/home/user/Pictures/ClickToDo"
}
```

---

## 📦 Cấu trúc mã nguồn

```
click-to-do-linux/
├── src/click_to_do_linux/
│   ├── ai/
│   │   ├── ocr.py            # Nhận diện chữ & layout (RapidOCR ONNX)
│   │   ├── segmentation.py   # Tách nền & làm mờ chủ thể (ONNX Rembg)
│   │   ├── entities.py       # Quét QR code, URL, Email, Hex color
│   │   └── llm.py            # Kết nối Ollama cục bộ (Tóm tắt, Dịch, Giải thích)
│   ├── capture/
│   │   └── screen.py         # Chụp màn hình Wayland siêu tốc (grim / /dev/shm)
│   ├── ui/
│   │   ├── overlay.py        # Toàn màn hình đóng băng & canvas tương tác
│   │   ├── action_bar.py     # Thanh công cụ nổi dạng viên thuốc (Pill Bar)
│   │   ├── ai_dialog.py      # Cửa sổ hiển thị kết quả AI trực tiếp dạng stream
│   │   └── theme.py          # Giao diện Glassmorphism / Fluent UI
│   ├── utils/
│   │   └── clipboard.py      # Tương tác clipboard Wayland (wl-copy)
│   ├── config.py             # Quản lý cấu hình
│   ├── hardware.py           # Tự động nhận diện AMD XDNA NPU, GPU, CPU
│   └── main.py               # CLI entrypoint
├── .mise.toml                # Cấu hình mise (Python 3.12, uv)
└── pyproject.toml            # Khai báo dependencies & CLI scripts
```
