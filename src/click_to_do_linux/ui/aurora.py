"""Animated aurora border for the screen capture overlay.

The border is the signature Windows 11 / Copilot "moving border": a conic
gradient (an iridescent rainbow) that **rotates** around the screen, sweeping
colour along the perimeter like a wave, with a soft inward glow on every edge
and a pulsing inner highlight.  That rotating sweep is the "wave" feel the
user asked for - it is NOT a stack of concentric rings and NOT a brightness
pulse along the rim.

How the effect is built
-----------------------
* **One conic gradient for the whole perimeter** (rotated by the phase).  A
  single gradient means zero seams at the corners, which is exactly why the
  previous "per-edge bands" versions read as stacked rings.
* **Four inward glow strips**, one per edge, each fading out towards the
  content.  Every strip carries the colour the conic gradient has at that
  edge, phase-shifted, so the glow travels with the sweep.
* **One inner highlight line**, white, pulsing, slightly inset - the "lip".
* **Pulse** modulates the alpha of the glow strips and the highlight.

Everything stays vector work: one conic gradient stroke + four linear
gradients + one hairline.  No offscreen buffer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QLinearGradient,
    QPainter,
    QPen,
)


# Windows 11 Copilot signature palette: sky, indigo, purple, pink.
COPILOT_PALETTE = ("#38bdf8", "#818cf8", "#c084fc", "#f472b6")


@dataclass(frozen=True)
class AuroraSpec:
    """Tunables of the overlay border, in logical pixels."""

    rim_width: float = 8.0
    rim_strength: float = 1.0

    glow_depth: float = 72.0
    glow_strength: float = 0.55

    wave_period: float = 7.0
    pulse_amplitude: float = 0.18

    hue_turns: float = 1.0


def _phase_color(phase: float, offset: float) -> QColor:
    """Colour sampled from the Copilot palette at a point along the sweep."""
    t = (phase + offset) % 1.0
    stops = (
        (0.00, (56, 189, 248)),
        (0.25, (129, 140, 248)),
        (0.50, (192, 132, 252)),
        (0.75, (244, 114, 182)),
        (1.00, (56, 189, 248)),
    )
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
    return QColor(56, 189, 248)


def draw_aurora_border(
    painter: QPainter,
    width: int,
    height: int,
    phase: float,
    spec: AuroraSpec = AuroraSpec(),
) -> None:
    """Draw the animated border of the overlay.

    ``phase`` is a free running value in ``[0, 1)``: it rotates the sweep
    one full lap around the border per ``spec.wave_period`` seconds.
    """
    if width <= 0 or height <= 0:
        return

    w = float(width)
    h = float(height)
    phase = phase % 1.0

    pulse = 1.0 - spec.pulse_amplitude + spec.pulse_amplitude * (
        0.5 + 0.5 * math.sin(phase * 2.0 * math.pi)
    )

    center = QPointF(w / 2.0, h / 2.0)
    angle = (phase * 360.0) % 360.0

    # 1. Conic gradient: the rotating rainbow "wave" around the perimeter.
    conical = QConicalGradient(center, angle)
    conical.setColorAt(0.00, QColor("#38bdf8"))
    conical.setColorAt(0.25, QColor("#818cf8"))
    conical.setColorAt(0.50, QColor("#c084fc"))
    conical.setColorAt(0.75, QColor("#f472b6"))
    conical.setColorAt(1.00, QColor("#38bdf8"))

    painter.setPen(QPen(QBrush(conical), spec.rim_width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    half = spec.rim_width / 2.0
    painter.drawRect(QRectF(half, half, w - spec.rim_width, h - spec.rim_width))

    # 2. Soft inward glow strips, one per edge, phase-shifted so the glow
    #    travels with the sweep instead of being a static wash.
    depth = min(spec.glow_depth, h / 3.0, w / 3.0)
    edge_alpha = int(255 * spec.glow_strength * pulse)

    # Top edge: colour from the bottom of the sweep
    c_top = _phase_color(phase, 0.75)
    g_top = QLinearGradient(0, 0, 0, depth)
    g_top.setColorAt(0.0, QColor(c_top.red(), c_top.green(), c_top.blue(), edge_alpha))
    g_top.setColorAt(1.0, QColor(c_top.red(), c_top.green(), c_top.blue(), 0))
    painter.fillRect(QRectF(0, 0, w, depth), g_top)

    # Bottom edge
    c_bottom = _phase_color(phase, 0.25)
    g_bottom = QLinearGradient(0, h, 0, h - depth)
    g_bottom.setColorAt(0.0, QColor(c_bottom.red(), c_bottom.green(), c_bottom.blue(), edge_alpha))
    g_bottom.setColorAt(1.0, QColor(c_bottom.red(), c_bottom.green(), c_bottom.blue(), 0))
    painter.fillRect(QRectF(0, h - depth, w, depth), g_bottom)

    # Left edge
    c_left = _phase_color(phase, 0.50)
    g_left = QLinearGradient(0, 0, depth, 0)
    g_left.setColorAt(0.0, QColor(c_left.red(), c_left.green(), c_left.blue(), edge_alpha))
    g_left.setColorAt(1.0, QColor(c_left.red(), c_left.green(), c_left.blue(), 0))
    painter.fillRect(QRectF(0, 0, depth, h), g_left)

    # Right edge
    c_right = _phase_color(phase, 0.00)
    g_right = QLinearGradient(w, 0, w - depth, 0)
    g_right.setColorAt(0.0, QColor(c_right.red(), c_right.green(), c_right.blue(), edge_alpha))
    g_right.setColorAt(1.0, QColor(c_right.red(), c_right.green(), c_right.blue(), 0))
    painter.fillRect(QRectF(w - depth, 0, depth, h), g_right)

    # 3. Delicate inner highlight line, pulsing.
    highlight_alpha = int(42 * pulse)
    painter.setPen(QPen(QColor(255, 255, 255, highlight_alpha), 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = spec.rim_width + 1.5
    painter.drawRect(QRectF(inset, inset, w - 2 * inset, h - 2 * inset))

    painter.setPen(QPen())
    painter.setBrush(QBrush())
