# Compositor integration and shortcuts

**Settings > Shortcuts** detects the compositor (and the shell/bar on top of
it), shows a ready-to-use snippet, checks the existing config for key
conflicts, and can write the shortcuts for you.
Defaults: `Mod+Shift+C` = capture, `Mod+Alt+C` = color picker (editable; `Mod` = Super).

| Compositor | Auto-detect | One-click apply | How it is applied |
| :--- | :---: | :---: | :--- |
| Niri | yes | yes | writes `~/.config/niri/click-to-do.kdl` + one `include optional=true` line, then `niri msg action load-config-file` |
| Umbriel | yes | yes | writes `~/.config/umbriel/click-to-do.toml` and adds it to `[include.optional]` |
| Hyprland | yes | yes | writes `~/.config/hypr/click-to-do.conf` + `source = ...`, then `hyprctl reload` |
| Sway | yes | yes | writes `~/.config/sway/click-to-do.conf` + `include ...`, then `swaymsg reload` |
| River | yes | yes | appends a managed block to `~/.config/river/init` |
| labwc / Wayfire | yes | guide | copy the generated XML / ini snippet |
| KDE Plasma / GNOME / COSMIC | yes | guide | step-by-step instructions (GNOME: one-shot `gsettings` script) |

Your own config files are never edited beyond a single include line (a
`.click-to-do.bak` backup is made first). **Remove shortcuts** or
`click-to-do uninstall` undoes it cleanly.

Note: `Mod+Q` is "close window" on most Niri/Umbriel setups, so do not use it.
The Settings tab warns about any key that is already taken.

## Manual setup

```kdl
// Niri
binds {
    Mod+Shift+C repeat=false { spawn "click-to-do" "capture"; }
    Mod+Alt+C   repeat=false { spawn "click-to-do" "color"; }
}
```

```toml
# Umbriel (keybinds.toml)
[keybinds]
"Mod+Shift+C" = { action = "spawn:click-to-do capture", repeat = false }
```

```ini
# Hyprland
bind = SUPER SHIFT, C, exec, click-to-do capture
```

```
# Sway
bindsym Mod4+Shift+c exec click-to-do capture
```

## Bar button (Umbriel, Noctalia, DMS, Waybar, custom bars)

The daemon shows a quick-action icon in any bar that supports
`StatusNotifierItem` (system tray): left click = capture, middle click = color
picker, right click = menu (Capture, Pick Color, Settings, Quit).

For a dedicated module (for example in Waybar):

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
