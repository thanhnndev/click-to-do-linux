# Changelog

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