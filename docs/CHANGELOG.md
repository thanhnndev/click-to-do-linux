# Changelog

## v0.5.0 (2026-10)

### Text toolbar sub-menu
- `ui/action_bar.py`: a labelled **More** button (chevron) opens a second row under the text toolbar. It replaces the old "⋯" menu; open/closed state is remembered between selections.
- Sub-toolbar toggles (pill buttons, applied to the Copy button and Ctrl+C): **Remove line breaks** (moved from beside Copy, region selections only), **Remove spaces** (phone numbers, emails, codes) and **Remove accents** (Vietnamese-aware, `đ`/`Đ` included).
- **Summarize** and **Rewrite** moved from the "⋯" menu into the sub-toolbar.
- Image regions that contain text get the same sub-toolbar copy options (without Summarize/Rewrite).
- `ai/entities.py`: new `strip_spaces()` and `strip_accents()`; `ui/icons.py`: `chevron_down`/`chevron_up`; new i18n keys (`more`, `more_options`, `strip_spaces`, `strip_accents`).
- Tests: sub-toolbar transforms and visibility in `tests/test_text_actions.py`.

## 2026-10 (overlay border)

### Wave border (current)
- `ui/aurora.py`: border is now an **undulating wave only** — no square outline, no concentric rings. Inner edge of the glow is a travelling sine wave that bobs in/out like an ocean swell.
- Two stacked wave layers (strong + faint, different counts/phase) so gaps between crests are filled.
- Tunables (AuroraSpec): `glow_depth=18`, `wave_amplitude=4`, `wave_count=5.0`, second layer `amplitude=2.5`, `count=7.0`, `strength=0.35`.
- Colour travels along the wave (Copilot palette).
- Perf: pure vector slices, ~1–2 ms/frame at 1080p.

### Iterations (for context)
1. `7c426b1` — first attempt: conic gradient + rim 6.5px + glow 84px. Read as "3 concentric rings", no wave feel.
2. `f4d0d10` — texture-based wave (arc-length, corner patch, 1.8 ms/frame). Still judged "terrible".
3. `e7f475c` — restored rotating rainbow conic (thicker, deeper glow). User: "Wave đâu? không cần hình vuông".
4. `137515e` — undulating wave on inner side, no square outline.
5. `353251f` — second faint wave layer, reduced max amplitude, uniform heights.
6. `1129aec` — remove square border entirely, wave only, shorter & denser.
7. `c0915e2` — denser & shallower waves, closer crest-trough gap.

### Docs
- `docs/DESIGN_CONTRACT.md` §1.6 rewritten for the wave border (tokens + rules).
- Tests: `tests/test_aurora_border.py` (7 cases).
PY
## Image processing UX (overlay)
- While running remove_bg / blur_bg: keep the capture frame open and draw a
  processing border + "Đang xử lý..." label over the selected region.
- After the task finishes: do not close the frame; instead render the
  processed result in place of the original crop (so the user can review/copy).
  Result is still copied to clipboard (and saved for cutout).
- New i18n key: "processing".

### Image processing UX (revised)
- Processing border now uses the same animated aurora wave as the screen border
  (scoped to the selection rect) instead of a static hue-per-side border.
- Loading overlay now covers the entire captured image (dimming + animated
  spinner + pulsing label), not just the selection.
- When done: frame stays open and the processed result is composited onto the
  background (crop region replaced), so the result is seen in full context.
