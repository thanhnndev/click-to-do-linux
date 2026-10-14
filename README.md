# Click to Do for Linux

A high-speed, native-feeling port of **Windows 11 Click to Do** built for modern Wayland compositors (**Niri**, **Umbriel**, **Hyprland**, **Sway**, **KDE Plasma**, **GNOME**).

Designed with a **Resident Daemon + Zero-Disk PPM Pipe** architecture to freeze the screen in **< 25ms**, detect text and QR codes in the background, isolate subjects (AI Cutout), redact sensitive areas, and run local Vietnamese/English LLMs via Ollama.

---

## Key Features

- **Instant Screen Freeze (< 25ms):** Streams uncompressed framebuffers directly from `grim` into RAM (`QImage` / `PIL.Image`) with zero temporary disk writes and zero PNG encoding overhead.
- **HiDPI & Multi-Monitor Native:** Automatically maps physical framebuffer pixels to logical Wayland coordinates (1.0x, 1.5x, 2.0x fractional scaling) without offset or blurriness.
- **Zero-Scroll Overlay on Niri:** Uses stationary `(0, 0)` floating window rules so activating the overlay never shifts or scrolls Niri tiling columns.
- **Direct Point-and-Click Text Interaction:**
  - **Single-click** any text line to open the contextual action pill (`Copy`, `Translate`, `Explain`, `Ask AI`, `Search`).
  - **Double-click** any text line to immediately copy and exit in 0.5s.
  - **`Shift + Click`** multiple lines to merge non-contiguous text blocks.
  - **Live Screen Find (`Ctrl + F`):** Highlight matching text anywhere on screen in real time.
- **Image & Subject Intelligence (Drag Selection):**
  - **AI Subject Cutout (`u2netp` / `isnet`):** Removes background into a transparent PNG directly in your Wayland clipboard.
  - **Background Blur:** Isolates the subject and blurs the surrounding backdrop.
  - **Privacy Redact:** Pixelates sensitive regions (keys, emails, personal info) before copying.
  - **Built-in Eyedropper / Color Picker:** Middle-click anywhere (or click `Pick Color`) with a live HEX magnifier loupe.
- **Universal Bar Quick-Action Button:**
  - **System Tray (`StatusNotifierItem`):** Automatically embeds a sleek vector icon in **Dank Material Shell**, **Umbriel**, **Waybar**, **Quickshell**, **Hyprpanel**, or **KDE** (Left-click: Capture, Middle-click: Pick Color, Right-click: Menu).
  - **Custom Bar Module (`click-to-do bar-status`):** JSON output for custom bar widgets.

---

## Recommended Local AI Models (Vietnamese & English)

| Task | Model | Size | Highlights |
| :--- | :--- | :--- | :--- |
| **LLM (Best Speed/Vietnamese)** | `qwen2.5:3b` | ~1.9 GB | Ultra-fast streaming (>90 tok/s), natural Vietnamese translation & summarization. |
| **LLM (Code & Reasoning)** | `gemma3:4b` | ~3.1 GB | Strong multilingual comprehension and code explanation. |
| **LLM (Ultra-Light CPU/iGPU)** | `qwen2.5:1.5b` | ~980 MB | Runs effortlessly on iGPU/CPU with near-zero VRAM footprint. |
| **LLM (High Accuracy)** | `qwen2.5:7b` | ~4.7 GB | Fits comfortably in 8GB VRAM for polished rewrites and complex queries. |
| **Subject Cutout (Fast)** | `u2netp` | 4.7 MB | Instant subject isolation (< 50ms). |
| **Subject Cutout (Detailed)** | `isnet-general-use` | 170 MB | High-precision edge segmentation. |

---

## Installation & App Setup

### 1. Build & Install as a Desktop App
 inside the project directory (managed by `mise` and `uv`):

```bash
uv sync
uv run click-to-do install

```

Running `click-to-do install` automatically:

1. Links the `click-to-do` executable into `~/.local/bin/click-to-do`.
2. Installs the desktop launcher (`~/.local/share/applications/click-to-do.desktop`) and scalable vector icon.
3. Configures and starts the **Systemd User Service** (`click-to-do.service`) so the background daemon and bar icon start automatically across any desktop/compositor.
4. Injects the non-scrolling floating rule into `~/.config/niri/config.kdl` (if Niri is installed).

### 2. Configure Models (GUI)

```bash
click-to-do settings

```

Select your preferred Cutout engine and Ollama model, then click **Download & Warmup Models**.

---

## Compositor & Bar Integration

### 1. Niri (`~/.config/niri/config.kdl`)

Add the shortcut inside your `binds { ... }` block:

```kdl
binds {
    Mod+Q { spawn "click-to-do" "capture"; }
    Print { spawn "click-to-do" "capture"; }
}

```

### 2. Umbriel / Waybar / Custom Bar Quick-Action Button

The background daemon **automatically displays a Quick-Action icon** in any bar supporting `StatusNotifierItem` (System Tray):

* **Left Click:** Trigger Click to Do Overlay
* **Middle Click:** Trigger Screen Color Picker (HEX)
* **Right Click:** Open Quick Menu (`Capture`, `Pick Color`, `Settings`, `Quit`)

If you also want a dedicated custom button module (e.g. in **Waybar** or **Umbriel**), use:

```json
"custom/click-to-do": {
    "exec": "click-to-do bar-status",
    "return-type": "json",
    "interval": "once",
    "on-click": "click-to-do capture",
    "on-click-middle": "click-to-do color",
    "on-click-right": "click-to-do settings"
}

```

---

## CLI Reference

| Command | Description |
| --- | --- |
| `click-to-do capture` | Freeze screen and open interactive overlay (< 25ms via daemon) |
| `click-to-do color` | Open overlay directly in HEX Color Picker loupe mode |
| `click-to-do settings` | Open minimalist Settings & Local Model Manager GUI |
| `click-to-do daemon` | Start background resident daemon and universal bar icon |
| `click-to-do install` | Install desktop app, icon, and systemd user service |
| `click-to-do bar-status` | Print JSON status for custom bar modules |
| `click-to-do stop` | Stop the running background daemon |
