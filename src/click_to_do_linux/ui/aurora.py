"""Animated aurora border for the screen capture overlay.

The border follows the Windows 11 / Copilot signature: a hue sweep that
travels around the perimeter, a crisp neon rim on the screen edge and a soft
bloom that fades out towards the content of the screen.

How the effect is built
-----------------------
The reference implementation of a "moving border" in CSS paints a conic
gradient (``conic-gradient(from var(--angle, ...)``) and animates the start
angle, then keeps only the ring with ``mask-composite: exclude``.  Qt has no
CSS mask, so the ring is drawn with vector strokes:

* a single conical gradient carries the hue for the whole perimeter, so the
  colour sweep stays continuous around the corners (no per edge phase, which
  is what produced the visible seams before);
* the rim is a soft halo stroke, a saturated tube and a hot hairline;
* the inner bloom is painted as four linear gradients, one per edge.  Each
  one carries the whole fade curve in its alpha stops, so the glow decays
  like ``A * exp(-d / lambda)`` without a single extra stroke.  Drawing the
  bloom as a stack of nested strokes was far too slow, it repainted the same
  band thirty times per frame.

Everything is vector work, no offscreen buffer, a frame costs a handful of
gradient fills.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QConicalGradient, QLinearGradient, QPainter, QPen


# Windows 11 Copilot signature palette: sky, indigo, purple, pink.
COPILOT_PALETTE = ("#38bdf8", "#818cf8", "#c084fc", "#f472b6")

# Hue sweep of the border, a narrow white arc rides on top of it.
_GRADIENT_STOPS = (
    (0.00, COPILOT_PALETTE[0]),
    (0.21, COPILOT_PALETTE[1]),
    (0.42, COPILOT_PALETTE[2]),
    (0.63, COPILOT_PALETTE[3]),
    (0.78, COPILOT_PALETTE[0]),
    (0.875, "#d8b4fe"),
    (0.925, "#ffffff"),
    (0.975, COPILOT_PALETTE[0]),
)


@dataclass(frozen=True)
class AuroraSpec:
    """Tunables of the overlay border, in logical pixels."""

    rim_width: float = 6.5
    rim_halo_width: float = 14.0
    core_width: float = 1.6
    core_mix: float = 0.28

    bloom_depth: float = 84.0
    bloom_strength: float = 92.0
    bloom_falloff: float = 30.0
    bloom_stops: int = 8

    rotation_period: float = 7.0
    pulse_cycles: float = 1.5
    pulse_amount: float = 0.13


def _tint(color: QColor, ratio: float) -> QColor:
    """Mix a colour towards white, used for the hot core of the rim."""
    return QColor(
        int(color.red() + (255 - color.red()) * ratio),
        int(color.green() + (255 - color.green()) * ratio),
        int(color.blue() + (255 - color.blue()) * ratio),
    )


def _palette_color_at(position: float) -> QColor:
    """Sample the hue sweep at a position in ``[0, 1)``."""
    position = position % 1.0
    for index in range(len(_GRADIENT_STOPS) - 1):
        start, start_color = _GRADIENT_STOPS[index]
        end, end_color = _GRADIENT_STOPS[index + 1]
        if start <= position <= end:
            factor = (position - start) / (end - start)
            first = QColor(start_color)
            second = QColor(end_color)
            return QColor(
                int(first.red() + factor * (second.red() - first.red())),
                int(first.green() + factor * (second.green() - first.green())),
                int(first.blue() + factor * (second.blue() - first.blue())),
            )
    return QColor(COPILOT_PALETTE[0])


def _conic_brush(center: QPointF, angle: float, mix: float = 0.0) -> QBrush:
    """Build the rotating hue sweep, ``mix`` fades it towards white."""
    gradient = QConicalGradient(center, angle)
    for position, color in _GRADIENT_STOPS:
        gradient.setColorAt(position, _tint(QColor(color), mix))
    return QBrush(gradient)


def _stroke(painter: QPainter, brush: QBrush, width: float, inset: float, box: QRectF) -> None:
    """Stroke the border rectangle, offset ``inset`` pixels from the edge."""
    path = QRectF(
        box.x() + inset,
        box.y() + inset,
        max(0.0, box.width() - 2 * inset),
        max(0.0, box.height() - 2 * inset),
    )
    pen = QPen(brush, width)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(path)


def _bloom_brush(
    spec: AuroraSpec,
    color: QColor,
    start: QPointF,
    end: QPointF,
) -> QLinearGradient:
    """Gradient that fades the glow out towards the content of the screen."""
    gradient = QLinearGradient(start, end)
    for step in range(spec.bloom_stops + 1):
        position = step / spec.bloom_stops
        decay = math.exp(-(position * spec.bloom_depth) / spec.bloom_falloff)
        alpha = spec.bloom_strength * decay
        gradient.setColorAt(position, QColor(color.red(), color.green(), color.blue(), int(alpha)))
    return gradient


def draw_aurora_border(
    painter: QPainter,
    width: int,
    height: int,
    phase: float,
    spec: AuroraSpec = AuroraSpec(),
) -> None:
    """Draw the animated border of the overlay.

    ``phase`` is a free running value in ``[0, 1)``: 0.0 starts the hue
    sweep, 1.0 completes one rotation.
    """
    if width <= 0 or height <= 0:
        return

    box = QRectF(0.0, 0.0, float(width), float(height))
    center = QPointF(box.width() / 2.0, box.height() / 2.0)
    phase = phase % 1.0
    angle = phase * 360.0
    pulse = 1.0 + spec.pulse_amount * math.sin(2.0 * math.pi * phase * spec.pulse_cycles)

    # 1. Inner bloom, four bands that fade out towards the content.
    depth = min(spec.bloom_depth, box.height() / 3.0, box.width() / 3.0)
    # The glow carries the hue of the sweep, sampled at the top edge.
    bloom_color = _palette_color_at(phase - 0.25)
    alpha_scale = pulse
    previous_opacity = painter.opacity()
    painter.setOpacity(alpha_scale)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(_bloom_brush(
        spec, bloom_color, QPointF(0.0, 0.0), QPointF(0.0, depth)
    )))
    painter.drawRect(QRectF(0.0, 0.0, box.width(), depth))
    painter.setBrush(QBrush(_bloom_brush(
        spec, bloom_color, QPointF(0.0, box.height()), QPointF(0.0, box.height() - depth)
    )))
    painter.drawRect(QRectF(0.0, box.height() - depth, box.width(), depth))
    painter.setBrush(QBrush(_bloom_brush(
        spec, bloom_color, QPointF(0.0, 0.0), QPointF(depth, 0.0)
    )))
    painter.drawRect(QRectF(0.0, 0.0, depth, box.height()))
    painter.setBrush(QBrush(_bloom_brush(
        spec, bloom_color, QPointF(box.width(), 0.0), QPointF(box.width() - depth, 0.0)
    )))
    painter.drawRect(QRectF(box.width() - depth, 0.0, depth, box.height()))
    painter.setOpacity(previous_opacity)

    # 2. Soft halo around the rim, it reads as the light bleeding outwards.
    brush = _conic_brush(center, angle)
    painter.setOpacity(0.28 * pulse)
    _stroke(painter, brush, spec.rim_halo_width, spec.rim_halo_width / 2.0, box)

    # 3. The rim itself, a saturated neon tube on the screen edge.
    painter.setOpacity(pulse)
    _stroke(painter, brush, spec.rim_width, spec.rim_width / 2.0, box)

    # 4. Hot hairline on the inner edge of the rim.
    core_brush = _conic_brush(center, angle, spec.core_mix)
    core_inset = spec.rim_width - spec.core_width / 2.0
    painter.setOpacity(0.6 * pulse)
    _stroke(painter, core_brush, spec.core_width, core_inset, box)

    painter.setOpacity(1.0)
