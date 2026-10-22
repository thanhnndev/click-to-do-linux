"""Animated aurora border for the screen capture overlay.

The border is a **wave that bobs on the inner side**: the inner edge of the
glow is a travelling sine wave (like water rolling along the screen edge),
so the glow undulates instead of reading as a square outline or a stack of
concentric rings.  The hue also travels with the wave.

How the effect is built
-----------------------
* **Two wavy bands per edge, stacked.**  The first (stronger) wave carries
  the main crest; a second, fainter wave with a different count and a
  phase offset fills the gaps so the border never looks empty between
  crests.  Both inner edges travel, so the border keeps "breathing".
* **A travelling hue** along each band, sampled from the Copilot palette.
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
    glow_depth: float = 36.0
    wave_amplitude: float = 12.0
    wave_count: float = 2.0
    wave_period: float = 5.0
    glow_strength: float = 0.9
    second_wave_count: float = 3.0
    second_wave_amplitude: float = 7.0
    second_wave_strength: float = 0.35
    second_wave_phase: float = 0.37


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


def _draw_edge(
    painter: QPainter,
    orientation: str,   # "h" (top/bottom) or "v" (left/right)
    w: float,
    h: float,
    phase: float,
    spec: AuroraSpec,
    wave_count: float,
    wave_amplitude: float,
    strength: float,
    phase_offset: float,
    step: float,
) -> None:
    """Draw one wavy band along one edge."""
    if orientation == "h":
        length = w
        color = _phase_color(phase, phase_offset)
        for x in range(0, int(w), int(step)):
            u = x / w if w else 0.0
            wave = _wave(wave_count * u - phase)
            depth = spec.glow_depth + wave_amplitude * wave
            if depth < 4:
                depth = 4
            crest = 0.5 + 0.5 * wave
            alpha = int(255 * strength * (0.4 + 0.6 * crest))
            grad = QLinearGradient(x, 0, x, depth)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(__import__("PyQt6.QtCore", fromlist=["QRectF"]).QRectF(x, 0, step, depth), grad)
    # (bottom/left/right handled by callers via flipping)


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

    # Helper to draw a horizontal band (top) for a given wave layer.
    def top_band(wave_count, wave_amplitude, strength, phase_off):
        color = _phase_color(phase, phase_off)
        for x in range(0, int(w), int(step)):
            u = x / w
            wave = _wave(wave_count * u - phase)
            depth = spec.glow_depth + wave_amplitude * wave
            if depth < 4:
                depth = 4
            crest = 0.5 + 0.5 * wave
            alpha = int(255 * strength * (0.4 + 0.6 * crest))
            grad = QLinearGradient(x, 0, x, depth)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(QRectF(x, 0, step, depth), grad)

    def bottom_band(wave_count, wave_amplitude, strength, phase_off):
        color = _phase_color(phase, phase_off + 0.5)
        for x in range(0, int(w), int(step)):
            u = x / w
            wave = _wave(wave_count * u - phase)
            depth = spec.glow_depth + wave_amplitude * wave
            if depth < 4:
                depth = 4
            crest = 0.5 + 0.5 * wave
            alpha = int(255 * strength * (0.4 + 0.6 * crest))
            y0 = h - depth
            grad = QLinearGradient(x, h, x, y0)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(QRectF(x, y0, step, depth), grad)

    def left_band(wave_count, wave_amplitude, strength, phase_off):
        color = _phase_color(phase, phase_off + 0.25)
        for y in range(0, int(h), int(step)):
            u = y / h
            wave = _wave(wave_count * u - phase)
            depth = spec.glow_depth + wave_amplitude * wave
            if depth < 4:
                depth = 4
            crest = 0.5 + 0.5 * wave
            alpha = int(255 * strength * (0.4 + 0.6 * crest))
            grad = QLinearGradient(0, y, depth, y)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(QRectF(0, y, depth, step), grad)

    def right_band(wave_count, wave_amplitude, strength, phase_off):
        color = _phase_color(phase, phase_off + 0.75)
        for y in range(0, int(h), int(step)):
            u = y / h
            wave = _wave(wave_count * u - phase)
            depth = spec.glow_depth + wave_amplitude * wave
            if depth < 4:
                depth = 4
            crest = 0.5 + 0.5 * wave
            alpha = int(255 * strength * (0.4 + 0.6 * crest))
            x0 = w - depth
            grad = QLinearGradient(w, y, x0, y)
            grad.setColorAt(0.0, QColor(color.red(), color.green(), color.blue(), alpha))
            grad.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.fillRect(QRectF(x0, y, depth, step), grad)

    # Primary (stronger) wave layer.
    top_band(spec.wave_count, spec.wave_amplitude, spec.glow_strength, 0.0)
    bottom_band(spec.wave_count, spec.wave_amplitude, spec.glow_strength, 0.0)
    left_band(spec.wave_count, spec.wave_amplitude, spec.glow_strength, 0.0)
    right_band(spec.wave_count, spec.wave_amplitude, spec.glow_strength, 0.0)

    # Secondary (fainter) wave layer fills the gaps.
    top_band(spec.second_wave_count, spec.second_wave_amplitude,
             spec.second_wave_strength, spec.second_wave_phase)
    bottom_band(spec.second_wave_count, spec.second_wave_amplitude,
                spec.second_wave_strength, spec.second_wave_phase)
    left_band(spec.second_wave_count, spec.second_wave_amplitude,
              spec.second_wave_strength, spec.second_wave_phase)
    right_band(spec.second_wave_count, spec.second_wave_amplitude,
               spec.second_wave_strength, spec.second_wave_phase)

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
