"""Wayland compositor / shell detection and keybinding integration (Niri, Umbriel, Hyprland, Sway, ...)."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

HOME = Path.home()
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
BLOCK_BEGIN = "# >>> click-to-do keybinds (managed) >>>"
BLOCK_END = "# <<< click-to-do keybinds <<<"

DEFAULT_CAPTURE_KEY = "Mod+Shift+C"
DEFAULT_COLOR_KEY = "Mod+Alt+C"

_MOD_ALIASES = {
    "mod": "mod", "super": "mod", "win": "mod", "meta": "mod", "logo": "mod", "mod4": "mod", "$mod": "mod",
    "ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt", "mod1": "alt", "iso_level3_shift": "altgr",
}


def normalize_key(spec: str) -> frozenset[str]:
    """'Super+Shift+c' / 'Mod+Shift+C' / 'SUPER SHIFT, C' -> frozenset({'mod','shift','c'})."""
    parts = [p for p in re.split(r"[+\s,]+", spec.strip()) if p]
    out = set()
    for p in parts:
        low = p.lower()
        out.add(_MOD_ALIASES.get(low, low))
    return frozenset(out)


@dataclass
class Compositor:
    id: str
    name: str
    config_path: Optional[Path] = None
    can_apply: bool = False
    shells: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name + (f"  +  {', '.join(self.shells)}" if self.shells else "")


def _running(names: tuple[str, ...]) -> set[str]:
    try:
        out = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True, timeout=2).stdout
    except Exception:
        return set()
    procs = {l.strip() for l in out.splitlines()}
    return {n for n in names if n in procs}


_SHELLS = {
    "dms": "Dank Material Shell", "noctalia": "Noctalia", "quickshell": "Quickshell", "waybar": "Waybar",
    "hyprpanel": "HyprPanel", "ags": "AGS", "eww": "Eww", "ironbar": "Ironbar", "yambar": "Yambar",
    "swaybar": "Swaybar", "plasmashell": "KDE Plasma", "gnome-shell": "GNOME Shell", "cosmic-panel": "COSMIC Panel",
}


def detect() -> Compositor:
    """Best-effort detection of the running Wayland compositor and the shell/bar on top of it."""
    env = os.environ
    desktop = (env.get("XDG_CURRENT_DESKTOP", "") + ":" + env.get("XDG_SESSION_DESKTOP", "")).lower()
    running = _running(("umbriel", "niri", "Hyprland", "sway", "river", "labwc", "wayfire", "kwin_wayland",
                        "gnome-shell", "cosmic-comp", "mango", "dwl", "hikari"))
    shells = [label for proc, label in _SHELLS.items() if proc in _running(tuple(_SHELLS))]
    shells = [s for s in shells if s not in ("KDE Plasma", "GNOME Shell", "COSMIC Panel")]

    def has(*ids: str) -> bool:
        return any(i.lower() in desktop for i in ids) or any(i in running for i in ids)

    if "umbriel" in running or "umbriel" in desktop:
        return Compositor("umbriel", "Umbriel", CONFIG_HOME / "umbriel" / "config.toml", True, shells)
    if env.get("NIRI_SOCKET") or "niri" in running or "niri" in desktop:
        return Compositor("niri", "Niri", CONFIG_HOME / "niri" / "config.kdl", True, shells)
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") or "Hyprland" in running or "hyprland" in desktop:
        return Compositor("hyprland", "Hyprland", CONFIG_HOME / "hypr" / "hyprland.conf", True, shells)
    if env.get("SWAYSOCK") or "sway" in running or "sway" in desktop:
        return Compositor("sway", "Sway", CONFIG_HOME / "sway" / "config", True, shells)
    if "river" in running or "river" in desktop:
        return Compositor("river", "River", CONFIG_HOME / "river" / "init", True, shells)
    if "labwc" in running or "labwc" in desktop:
        return Compositor("labwc", "labwc", CONFIG_HOME / "labwc" / "rc.xml", False, shells)
    if "wayfire" in running or "wayfire" in desktop:
        return Compositor("wayfire", "Wayfire", CONFIG_HOME / "wayfire.ini", False, shells)
    if "kwin_wayland" in running or "kde" in desktop or "plasma" in desktop:
        return Compositor("kde", "KDE Plasma (KWin)", None, False, shells)
    if "cosmic" in desktop or "cosmic-comp" in running:
        return Compositor("cosmic", "COSMIC", None, False, shells)
    if "gnome" in desktop or "gnome-shell" in running:
        return Compositor("gnome", "GNOME (Mutter)", None, False, shells)
    for cid, nm in (("mango", "MangoWC"), ("dwl", "dwl"), ("hikari", "hikari")):
        if cid in running:
            return Compositor(cid, nm, None, False, shells)
    return Compositor("generic", env.get("XDG_CURRENT_DESKTOP") or "Wayland", None, False, shells)


# ---------------------------------------------------------------- key syntax per compositor

def _parts(key: str) -> tuple[list[str], str]:
    toks = [t for t in key.strip().split("+") if t]
    return toks[:-1], toks[-1]


def _canon_mods(mods: list[str]) -> list[str]:
    out = []
    for m in mods:
        n = _MOD_ALIASES.get(m.lower(), m.lower())
        out.append({"mod": "Super", "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt"}.get(n, m))
    return out


def snippet(comp_id: str, capture_key: str, color_key: str, bin_cmd: str = "click-to-do") -> str:
    """Config text (without managed-block markers) that binds the two shortcuts."""
    cap_m, cap_k = _parts(capture_key)
    col_m, col_k = _parts(color_key)
    cm, om = _canon_mods(cap_m), _canon_mods(col_m)

    if comp_id == "niri":
        return (
            "binds {\n"
            f'    {capture_key} repeat=false hotkey-overlay-title="Click to Do" {{ spawn "{bin_cmd}" "capture"; }}\n'
            f'    {color_key} repeat=false hotkey-overlay-title="Click to Do: Color Picker" {{ spawn "{bin_cmd}" "color"; }}\n'
            "}\n"
        )
    if comp_id == "umbriel":
        return (
            "[keybinds]\n"
            f'"{capture_key}" = {{ action = "spawn:{bin_cmd} capture", repeat = false }}\n'
            f'"{color_key}" = {{ action = "spawn:{bin_cmd} color", repeat = false }}\n'
        )
    if comp_id == "hyprland":
        h = lambda mods: " ".join(m.upper() for m in mods)
        return (
            f"bind = {h(cm)}, {cap_k.upper()}, exec, {bin_cmd} capture\n"
            f"bind = {h(om)}, {col_k.upper()}, exec, {bin_cmd} color\n"
        )
    if comp_id == "sway":
        s = lambda mods, k: "+".join(["Mod4" if m == "Super" else m for m in mods] + [k.lower() if len(k) == 1 else k])
        return (
            f"bindsym {s(cm, cap_k)} exec {bin_cmd} capture\n"
            f"bindsym {s(om, col_k)} exec {bin_cmd} color\n"
        )
    if comp_id == "river":
        r = lambda mods: "+".join(mods)
        return (
            f'riverctl map normal {r(cm)} {cap_k.upper()} spawn "{bin_cmd} capture"\n'
            f'riverctl map normal {r(om)} {col_k.upper()} spawn "{bin_cmd} color"\n'
        )
    if comp_id == "labwc":
        lw = lambda mods, k: "-".join({"Super": "W", "Ctrl": "C", "Shift": "S", "Alt": "A"}.get(m, m) for m in mods) + "-" + k.lower()
        return (
            "<!-- inside <keyboard> in ~/.config/labwc/rc.xml -->\n"
            f'<keybind key="{lw(cm, cap_k)}"><action name="Execute" command="{bin_cmd} capture" /></keybind>\n'
            f'<keybind key="{lw(om, col_k)}"><action name="Execute" command="{bin_cmd} color" /></keybind>\n'
        )
    if comp_id == "wayfire":
        w = lambda mods, k: " ".join([f"<{m.lower()}>" for m in mods] + [f"KEY_{k.upper()}"])
        return (
            "# ~/.config/wayfire.ini  (enable the 'command' plugin: plugins = ... command)\n"
            "[command]\n"
            f"binding_c2d = {w(cm, cap_k)}\ncommand_c2d = {bin_cmd} capture\n"
            f"binding_c2d_color = {w(om, col_k)}\ncommand_c2d_color = {bin_cmd} color\n"
        )
    if comp_id == "kde":
        return (
            "# KDE Plasma — no config file needed:\n"
            "# System Settings → Keyboard → Shortcuts → Add New → Command or Script…\n"
            f"#   Command : {bin_cmd} capture      Shortcut: {capture_key.replace('Mod', 'Meta')}\n"
            f"#   Command : {bin_cmd} color        Shortcut: {color_key.replace('Mod', 'Meta')}\n"
        )
    if comp_id == "gnome":
        base = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
        gk = lambda mods, k: "".join(f"<{m}>" for m in mods) + k.lower()
        return (
            "# GNOME — run once in a terminal (keeps your existing custom shortcuts):\n"
            "python3 - <<'PY'\n"
            "import ast, subprocess\n"
            "S='org.gnome.settings-daemon.plugins.media-keys'\n"
            "cur=ast.literal_eval(subprocess.check_output(['gsettings','get',S,'custom-keybindings']).decode().replace('@as ',''))\n"
            f"items={{'click-to-do':('Click to Do','{bin_cmd} capture','{gk(cm, cap_k)}'),\n"
            f"       'click-to-do-color':('Click to Do: Color','{bin_cmd} color','{gk(om, col_k)}')}}\n"
            "for k,(n,c,b) in items.items():\n"
            f"    p='{base}/'+k+'/'\n"
            "    if p not in cur: cur.append(p)\n"
            "    for f,v in (('name',n),('command',c),('binding',b)):\n"
            "        subprocess.run(['gsettings','set',S+'.custom-keybinding:'+p,f,v])\n"
            "subprocess.run(['gsettings','set',S,'custom-keybindings',str(cur)])\n"
            "PY\n"
        )
    if comp_id == "cosmic":
        return (
            "# COSMIC — Settings → Keyboard → Custom Shortcuts → Add Shortcut\n"
            f"#   Command: {bin_cmd} capture   Shortcut: {capture_key.replace('Mod', 'Super')}\n"
            f"#   Command: {bin_cmd} color     Shortcut: {color_key.replace('Mod', 'Super')}\n"
        )
    return (
        "# Bind these two commands to keys in your compositor / desktop settings:\n"
        f"#   {bin_cmd} capture    (freeze screen + overlay)\n"
        f"#   {bin_cmd} color      (HEX colour picker)\n"
    )


# ---------------------------------------------------------------- conflict scanning

_KEY_LINE: dict[str, re.Pattern] = {
    "niri": re.compile(r"^\s*([A-Za-z0-9_$]+(?:\+[A-Za-z0-9_$]+)+|[A-Za-z0-9_]+)\s*(?:[a-z\-]+=\S+\s*)*\{"),
    "umbriel": re.compile(r'^\s*(?:\[keybinds\."([^"]+)"\]|"([^"]+)"\s*=)'),
    "hyprland": re.compile(r"^\s*bind[a-z]*\s*=\s*([^,]*),\s*([^,]+),"),
    "sway": re.compile(r"^\s*bindsym\s+(?:--\S+\s+)*(\S+)"),
}


def _config_files(comp: Compositor) -> list[Path]:
    """Config file plus files it includes/sources (one level deep, best effort)."""
    if not comp.config_path or not comp.config_path.exists():
        return []
    files = [comp.config_path]
    base = comp.config_path.parent
    try:
        text = comp.config_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return files
    cands: list[str] = []
    if comp.id == "niri":
        cands = re.findall(r'^\s*include\s+(?:optional=true\s+)?"([^"]+)"', text, re.M)
    elif comp.id == "umbriel":
        for m in re.finditer(r"files\s*=\s*\[([^\]]*)\]", text):
            cands += re.findall(r'"([^"]+)"', m.group(1))
    elif comp.id == "hyprland":
        cands = re.findall(r"^\s*source\s*=\s*(\S+)", text, re.M)
    elif comp.id == "sway":
        cands = re.findall(r"^\s*include\s+(\S+)", text, re.M)
    for c in cands:
        p = Path(os.path.expanduser(c))
        p = p if p.is_absolute() else base / p
        if p.exists() and p not in files:
            files.append(p)
    return files


def find_conflicts(comp: Compositor, key: str) -> list[str]:
    """Lines in the user's own config that already use `key` for something other than click-to-do."""
    pat = _KEY_LINE.get(comp.id)
    if not pat:
        return []
    want = normalize_key(key)
    hits: list[str] = []
    for f in _config_files(comp):
        if f.name == "click-to-do.conf" or f.name.startswith("click-to-do"):
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        inside_managed = False
        for n, line in enumerate(lines, 1):
            if BLOCK_BEGIN in line:
                inside_managed = True
            if BLOCK_END in line:
                inside_managed = False
            if inside_managed or "click-to-do" in line:
                continue
            m = pat.match(line)
            if not m:
                continue
            if comp.id == "hyprland":
                spec = f"{m.group(1)} {m.group(2)}"
            elif comp.id == "umbriel":
                spec = m.group(1) or m.group(2)
            else:
                spec = m.group(1)
            if spec and normalize_key(spec) == want:
                hits.append(f"{f.name}:{n}  {line.strip()[:90]}")
    return hits


def existing_click_to_do_binds(comp: Compositor) -> list[str]:
    """Lines already spawning click-to-do from the user's own files (outside our managed block)."""
    out = []
    for f in _config_files(comp):
        if f.name.startswith("click-to-do"):
            continue
        try:
            for n, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                s = line.strip()
                if "click-to-do" in s and re.search(r"spawn|exec|bindsym|action", s) and not s.startswith(("#", "//")):
                    out.append(f"{f.name}:{n}  {s[:90]}")
        except OSError:
            pass
    return out


# ---------------------------------------------------------------- apply / remove

def _managed_file(comp: Compositor) -> Optional[Path]:
    if comp.id in ("niri", "umbriel", "hyprland", "sway") and comp.config_path:
        ext = {"niri": "kdl", "umbriel": "toml", "hyprland": "conf", "sway": "conf"}[comp.id]
        return comp.config_path.parent / f"click-to-do.{ext}"
    return None


def _include_line(comp: Compositor, fname: str) -> str:
    return {
        "niri": f'include optional=true "{fname}"',
        "hyprland": f"source = {fname}",
        "sway": f"include {fname}",
    }.get(comp.id, "")


def apply(comp: Compositor, capture_key: str, color_key: str, bin_cmd: str = "click-to-do") -> tuple[bool, str]:
    """Writes click-to-do.<ext> next to the user's config and wires it in with one include line."""
    if not comp.can_apply or not comp.config_path:
        return False, "Auto-apply is not supported for this compositor — copy the snippet instead."
    try:
        cfg = comp.config_path
        cfg.parent.mkdir(parents=True, exist_ok=True)
        own = _managed_file(comp)
        text = snippet(comp.id, capture_key, color_key, bin_cmd)

        if comp.id == "river":
            body = f"{BLOCK_BEGIN}\n{text}{BLOCK_END}\n"
            cur = cfg.read_text(encoding="utf-8") if cfg.exists() else "#!/bin/sh\n"
            cur = _strip_block(cur)
            cfg.write_text(cur.rstrip() + "\n\n" + body, encoding="utf-8")
            cfg.chmod(cfg.stat().st_mode | 0o111)
            return True, f"Wrote shortcuts to {cfg} — run the same lines once or restart River."

        assert own is not None
        own.write_text(f"{'//' if comp.id == 'niri' else '#'} Managed by Click to Do — edit via Settings → Shortcuts\n{text}", encoding="utf-8")

        if comp.id == "umbriel":
            _umbriel_include(cfg, own.name)
        else:
            cur = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
            inc = _include_line(comp, own.name)
            if inc not in cur:
                shutil.copy2(cfg, cfg.with_name(cfg.name + ".click-to-do.bak")) if cfg.exists() else None
                cfg.write_text(cur.rstrip() + f"\n\n{'//' if comp.id == 'niri' else '#'} Click to Do shortcuts\n{inc}\n", encoding="utf-8")
        _reload(comp)
        return True, f"Applied: {own}  (included from {cfg.name}). Config reloaded."
    except Exception as e:
        return False, f"Could not apply shortcuts: {e}"


def _umbriel_include(cfg: Path, fname: str) -> None:
    cur = cfg.read_text(encoding="utf-8")
    if f'"{fname}"' in cur:
        return
    shutil.copy2(cfg, cfg.with_name(cfg.name + ".click-to-do.bak"))
    m = re.search(r"(\[include\.optional\]\s*\nfiles\s*=\s*\[)([^\]]*)(\])", cur)
    if m:
        inner = m.group(2).strip()
        inner = (inner + ", " if inner else "") + f'"{fname}"'
        cur = cur[: m.start()] + m.group(1) + inner + m.group(3) + cur[m.end():]
    else:
        cur = cur.rstrip() + f'\n\n[include.optional]\nfiles = ["{fname}"]\n'
    cfg.write_text(cur, encoding="utf-8")


def _strip_block(text: str) -> str:
    return re.sub(rf"\n?{re.escape(BLOCK_BEGIN)}[\s\S]*?{re.escape(BLOCK_END)}\n?", "\n", text)


def _reload(comp: Compositor) -> None:
    cmds = {
        "niri": ["niri", "msg", "action", "load-config-file"],
        "hyprland": ["hyprctl", "reload"],
        "sway": ["swaymsg", "reload"],
    }
    if comp.id in cmds and shutil.which(cmds[comp.id][0]):
        subprocess.run(cmds[comp.id], check=False, capture_output=True)


def remove(comp: Optional[Compositor] = None) -> list[str]:
    """Undo apply(): delete managed files and the include lines. Returns what was touched."""
    touched: list[str] = []
    for c in ([comp] if comp else [detect()]):
        own = _managed_file(c)
        cfg = c.config_path
        if own and own.exists():
            own.unlink()
            touched.append(str(own))
        if cfg and cfg.exists():
            cur = cfg.read_text(encoding="utf-8")
            new = cur
            if c.id == "umbriel":
                new = re.sub(r',?\s*"click-to-do\.toml"\s*,?', lambda m: "," if m.group(0).count(",") == 2 else "", new)
            elif c.id in ("niri", "hyprland", "sway"):
                inc = _include_line(c, f"click-to-do.{own.suffix[1:]}" if own else "")
                new = re.sub(rf"\n?(?:#|//) Click to Do shortcuts\n{re.escape(inc)}\n?", "\n", new)
                new = new.replace(inc + "\n", "")
            elif c.id == "river":
                new = _strip_block(new)
            if new != cur:
                cfg.write_text(new.rstrip() + "\n", encoding="utf-8")
                touched.append(f"{cfg} (shortcuts)")
                _reload(c)
    return touched
