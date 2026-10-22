"""Animated aurora border for the screen capture overlay.

The border is a **wave that bobs on the inner side**: the inner edge of the
glow is a travelling sine wave (like water rolling along the screen edge),
so the glow undulates instead of reading as a square outline or a stack of
concentric rings.  The hue also travels with the wave.

How the effect is built
-----------------------
* **One wavy band per edge.**  The outer edge stays on the screen border, the
  inner edge is a sine wave that travels along the edge, so the band
  "breathes" in and out like a swell.  The glow is brightest at the crest
  (where the wave pushes deepest) and fades to nothing at the trough.
* **A travelling hue** along each band, sampled from the Copilot palette, so
  the colour rolls with the wave.
* **No square outline, no concentric rings** - only the undulating wave.

Everything stays vector work: vertical slices + gradients.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QLinearGradient,
    QPen,
    QBrush,
)


COPILOT_PALETTE = ((56, 189, 248), (129, 140, 248), (192, 132, 252), (244, 114, 182))


@dataclass(frozen=True)
class AuroraSpec:
    rim_width: float = 6.0
    glow_depth: float = 50.0
    wave_amplitude: float = 22.0
    wave_count: float = 2.0
    wave_period: float = 5.0
    glow_strength: float = 0.9


def _phase_color(phase: float, offset: float) -> QColor:
    t = (phase + offset) % 1.0
    stops = ((0.00, COPILOT_PALETTE[0]), (0.25, COPILOT_PALETTE[1]),
             (0.50, COPILOT_PALETTE[2]), (0.75, COPILOT_PALETTE[3]),
             (1.00, COPILOT_PALETTE[0]))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t0 <= t <= t1:
            factor = (t - t0) / (t1 - t0) if (t1 - t0) else 0.0
            return QColor(
                int(c0[0] + factor * (c1[0] - c0[0])),
                int(c0[1] + factor * (c1[1] - c0[1])),
                int(c0[2] + factor * (c1[2] - c0[2])),
            )
    return QColor(*COPILOT_PALETTE[0])


def _wave(phase_pos: float) -> float:
    return math.sin(2.0 * math.pi * phase_pos)


def draw_aurora_border(
    painter: QPainter,
    width: int,
    height: int,
    phase: float,
    spec: AuroraSpec = AuroraSpec(),
) -> None:
    if width <= 0 or height <= 0:
        return

    w = float(width)
    h = float(height)
    phase = phase % 1.0
    step = 6.0

    # Top edge.
    for x in range(0, int(w), int(step)):
        u = x / w
        wave = _wave(spec.wave_count * u - phase)
        depth = spec.glow_depth + spec.wave_amplitude * wave
        if depth < 4:
            depth = 4
        crest = 0.5 + 0.5 * wave
        alpha = int(255 * spec.glow_strength * (0.3 + 0.7 * crest))
        c = _phase_color(phase, u * spec.hue_turns if hasattr(spec,'hue_turns') else u)
        grad = QLinearGradient(x, 0, x, depth)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.fillRect(QRectF(x, 0, step, depth), grad)

    # Bottom edge.
    for x in range(0, int(w), int(step)):
        u = x / w
        wave = _wave(spec.wave_count * u - phase)
        depth = spec.glow_depth + spec.wave_amplitude * wave
        if depth < 4:
            depth = 4
        crest = 0.5 + 0.5 * wave
        alpha = int(255 * spec.glow_strength * (0.3 + 0.7 * crest))
        c = _phase_color(phase, 0.5 + u)
        y0 = h - depth
        grad = QLinearGradient(x, h, x, y0)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.fillRect(QRectF(x, y0, step, depth), grad)

    # Left edge.
    for y in range(0, int(h), int(step)):
        u = y / h
        wave = _wave(spec.wave_count * u - phase)
        depth = spec.glow_depth + spec.wave_amplitude * wave
        if depth < 4:
            depth = 4
        crest = 0.5 + 0.5 * wave
        alpha = int(255 * spec.glow_strength * (0.3 + 0.7 * crest))
        c = _phase_color(phase, 0.25 + u)
        grad = QLinearGradient(0, y, depth, y)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.fillRect(QRectF(0, y, depth, step), grad)

    # Right edge.
    for y in range(0, int(h), int(step)):
        u = y / h
        wave = _wave(spec.wave_count * u - phase)
        depth = spec.glow_depth + spec.wave_amplitude * wave
        if depth < 4:
            depth = 4
        crest = 0.5 + 0.5 * wave
        alpha = int(255 * spec.glow_strength * (0.3 + 0.7 * crest))
        c = _phase_color(phase, 0.75 + u)
        x0 = w - depth
        grad = QLinearGradient(w, y, x0, y)
        grad.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), alpha))
        grad.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        painter.fillRect(QRectF(x0, y, depth, step), grad)

    # Rim: a thick line along the outer edge with the travelling hue.
    rim_color = _phase_color(phase, 0.0)
    painter.setPen(QPen(
        QColor(rim_color.red(), rim_color.green(), rim_color.blue(),
               int(255 * spec.glow_strength)), spec.rim_width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(QRectF(spec.rim_width / 2.0, spec.rim_width / 2.0,
                            w - spec.rim_width, h - spec.rim_width))

    painter.setPen(QPen())
    painter.setBrush(QBrush())
