#!/usr/bin/env bash
# Click to Do for Linux — one-shot installer for Arch, Debian/Ubuntu, Fedora, openSUSE and derivatives.
#
#   ./install.sh                 install deps + app + desktop integration
#   ./install.sh --no-deps       skip system packages (you installed them yourself)
#   ./install.sh --with-ollama   also install Ollama (local LLM runtime)
#   ./install.sh --yes           no confirmation prompts
#   ./install.sh --uninstall     remove the app and desktop integration (add --purge to delete data)
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_VERSION="3.12"          # onnxruntime / rembg wheels target 3.12; uv fetches it if the system one differs
ASSUME_YES=0 DEPS=1 OLLAMA=0 UNINSTALL=0 PURGE=0

for a in "$@"; do
  case "$a" in
    -y|--yes) ASSUME_YES=1 ;;
    --no-deps) DEPS=0 ;;
    --with-ollama) OLLAMA=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done

c_b=$'\033[1m'; c_g=$'\033[32m'; c_y=$'\033[33m'; c_r=$'\033[31m'; c_0=$'\033[0m'
say()  { printf '%s==>%s %s\n' "$c_g$c_b" "$c_0" "$*"; }
warn() { printf '%s!!%s  %s\n' "$c_y$c_b" "$c_0" "$*" >&2; }
die()  { printf '%sxx%s  %s\n' "$c_r$c_b" "$c_0" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
confirm() { [ "$ASSUME_YES" = 1 ] && return 0; read -r -p "$1 [Y/n] " r; [[ -z "$r" || "$r" =~ ^[Yy] ]]; }
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

if [ "$UNINSTALL" = 1 ]; then
  say "Removing desktop integration"
  if have click-to-do; then click-to-do uninstall $([ "$PURGE" = 1 ] && echo --purge) || true; fi
  if have uv; then uv tool uninstall click-to-do-linux 2>/dev/null || true; fi
  say "Uninstalled. (System packages such as grim/tesseract were left alone.)"
  exit 0
fi

# ---- distro detection -------------------------------------------------------
. /etc/os-release 2>/dev/null || true
ID_ALL=" ${ID:-} ${ID_LIKE:-} "
family=unknown
case "$ID_ALL" in
  *" arch "*|*" cachyos "*|*" manjaro "*|*" endeavouros "*) family=arch ;;
  *" debian "*|*" ubuntu "*) family=debian ;;
  *" fedora "*|*" rhel "*|*" centos "*|*" nobara "*) family=fedora ;;
  *" suse "*|*" opensuse "*) family=suse ;;
esac
say "Detected distro: ${PRETTY_NAME:-unknown} (family: $family)"
[ "${XDG_SESSION_TYPE:-}" = "wayland" ] || warn "Not a Wayland session (XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-unset}); the overlay targets Wayland compositors."

# ---- system packages --------------------------------------------------------
install_deps() {
  case "$family" in
    arch)
      local pk=(grim wl-clipboard tesseract tesseract-data-vie tesseract-data-eng libxkbcommon)
      have uv || pk+=(uv)
      [ "$OLLAMA" = 1 ] && pk+=(ollama)
      $SUDO pacman -S --needed --noconfirm "${pk[@]}" ;;
    debian)
      local pk=(grim wl-clipboard tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng libxkbcommon0 libegl1 libgl1 libdbus-1-3 libfontconfig1 curl ca-certificates)
      $SUDO apt-get update -y && $SUDO apt-get install -y "${pk[@]}" ;;
    fedora)
      local pk=(grim wl-clipboard tesseract tesseract-langpack-vie tesseract-langpack-eng libxkbcommon mesa-libEGL dbus-libs curl)
      $SUDO dnf install -y "${pk[@]}" ;;
    suse)
      local pk=(grim wl-clipboard tesseract-ocr tesseract-ocr-traineddata-vietnamese tesseract-ocr-traineddata-english libxkbcommon0 Mesa-libEGL1 curl)
      $SUDO zypper --non-interactive install "${pk[@]}" ;;
    *)
      warn "Unknown distro. Please install manually: grim, wl-clipboard, tesseract (+ Vietnamese data), uv."
      return 0 ;;
  esac
}

if [ "$DEPS" = 1 ]; then
  say "Installing system packages (grim, wl-clipboard, tesseract + Vietnamese data)"
  if confirm "Run the package manager with sudo now?"; then install_deps; else warn "Skipped system packages."; fi
fi

# ---- uv ---------------------------------------------------------------------
if ! have uv; then
  say "Installing uv (Python package manager)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
have uv || die "uv not found after install"

# ---- app --------------------------------------------------------------------
say "Installing Click to Do (Python $PY_VERSION via uv)"
uv tool install --python "$PY_VERSION" --reinstall --force "$SRC_DIR"
export PATH="$HOME/.local/bin:$PATH"
have click-to-do || die "click-to-do not on PATH; add ~/.local/bin to PATH"

say "Setting up desktop launcher, icon and systemd user service"
click-to-do install

if [ "$OLLAMA" = 1 ] && ! have ollama && [ "$family" != arch ]; then
  say "Installing Ollama"; curl -fsSL https://ollama.com/install.sh | sh
fi

cat <<EOF

${c_g}${c_b}Done.${c_0}
  • Open ${c_b}click-to-do settings${c_0} → Shortcuts tab to bind a key for your compositor.
  • Settings → "Download & Warmup Models" fetches OCR/cutout models and your Ollama model.
  • Uninstall any time with: ./install.sh --uninstall   (or Settings → Uninstall)
EOF
