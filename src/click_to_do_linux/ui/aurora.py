"""Animated aurora border for the screen capture overlay.

The border is a wave of light that rolls around the edge of the screen, the
way a swell rolls along a shore: crests brighten as they travel, troughs sink
back into the dimmed screenshot.

How the effect is built
-----------------------
The reference implementations of a "moving border" in CSS paint a conic
gradient and animate its start angle, and the liquid effects build their
waves from two shapes that rotate at slightly different speeds so the pattern
never repeats.  Both ideas are mapped onto Qt here:

* **The wave travels along the arc length of the border, not along the
  angle.**  A conic gradient is an angular function, so a wave defined in
  the angle would crawl slowly down the long edges and race across the
  short ones.  Every column of the texture therefore carries the wave of its
  own arc length position, which keeps the swell at a constant speed all the
  way round.
* **A sine wave with a modulated amplitude**, so the crests are not all
  identical but every crest still reaches the top of the wave.
* **The texture holds the wave and the fade at once.**  The wave is painted
  as a gradient along the border, the fade towards the content is multiplied
  in with ``CompositionMode_DestinationIn``.  No pixel loop in Python, and
  the two effects multiply instead of adding up into visible rings.
* **The corners are their own patch.**  Two edge bands that overlap in a
  corner would double the glow there and leave a bright square, so the edges
  stop short of the corners and a small patch takes over, fading with the
  distance to the nearest edge.
* Only two bands are drawn, the rim and the glow, both of them follow the
  wave, so the border never reads as a stack of concentric rings.

Everything is vector work, no offscreen buffer: a frame costs a handful of
small textures and a few fills.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QTransform,
)


# Windows 11 Copilot signature palette: sky, indigo, purple, pink.
COPILOT_PALETTE = ("#38bdf8", "#818cf8", "#c084fc", "#f472b6")

# Corner masks only depend on their size, they are built once.
_CORNER_MASKS: dict[tuple[int, int], QImage] = {}


@dataclass(frozen=True)
class AuroraSpec:
    """Tunables of the overlay border, in logical pixels."""

    rim_width: float = 8.0
    rim_strength: float = 1.0
    rim_falloff: float = 8.0

    glow_depth: float = 82.0
    glow_strength: float = 0.6
    glow_falloff: float = 22.0

    wave_count: float = 2.5
    wave_modulation: float = 0.18
    wave_amplitude: float = 1.0
    wave_period: float = 9.0
    hue_turns: float = 1.0
    crest_tint: float = 0.35
    trough_alpha: float = 0.14
    rim_exponent: float = 1.0
    glow_exponent: float = 1.4


@dataclass(frozen=True)
class _Edge:
    """One side of the screen and how it maps onto a texture."""

    name: str
    start: float
    length: float
    along: str          # "x" or "y", the axis that follows the border
    along_flip: bool
    depth_flip: bool


def _tint(color: QColor, ratio: float) -> QColor:
    """Mix a colour towards white, used for the glint on a crest."""
    ratio = max(0.0, min(1.0, ratio))
    return QColor(
        int(color.red() + (255 - color.red()) * ratio),
        int(color.green() + (255 - color.green()) * ratio),
        int(color.blue() + (255 - color.blue()) * ratio),
    )


def _palette_color(position: float) -> QColor:
    """Sample the hue wheel of the signature palette."""
    position = position % 1.0
    count = len(COPILOT_PALETTE)
    scaled = position * count
    index = int(scaled) % count
    factor = scaled - int(scaled)
    first = QColor(COPILOT_PALETTE[index])
    second = QColor(COPILOT_PALETTE[(index + 1) % count])
    return QColor(
        int(first.red() + factor * (second.red() - first.red())),
        int(first.green() + factor * (second.green() - first.green())),
        int(first.blue() + factor * (second.blue() - first.blue())),
    )


def _crest(position: float, spec: AuroraSpec) -> float:
    """Height of the wave at a position along the border, in ``[0, 1]``.

    A sine wave whose amplitude is modulated by a slower wave, so the crests
    differ in size but each of them still reaches the top.
    """
    primary = math.sin(2.0 * math.pi * spec.wave_count * position)
    modulation = 1.0 - spec.wave_modulation + spec.wave_modulation * math.sin(
        2.0 * math.pi * (spec.wave_count - 1.0) * position + 1.3
    )
    height = 0.5 + 0.5 * primary * modulation
    return max(0.0, min(1.0, height)) * spec.wave_amplitude


def _edges(width: float, height: float) -> list[_Edge]:
    """The four sides, walked clockwise from the top left corner."""
    return [
        _Edge("top", 0.0, width, "x", False, False),
        _Edge("right", width, height, "y", False, True),
        _Edge("bottom", width + height, width, "x", True, True),
        _Edge("left", 2.0 * width + height, height, "y", True, False),
    ]


def _edge_rect(edge: _Edge, width: float, height: float, depth: float, inset: float) -> QRectF:
    """Where the band of an edge sits on the screen, corners excluded."""
    if edge.name == "top":
        return QRectF(inset, 0.0, width - 2 * inset, depth)
    if edge.name == "right":
        return QRectF(width - depth, inset, depth, height - 2 * inset)
    if edge.name == "bottom":
        return QRectF(inset, height - depth, width - 2 * inset, depth)
    return QRectF(0.0, inset, depth, height - 2 * inset)


def _corner_rects(width: float, height: float, depth: float) -> list[QRectF]:
    """The four corner patches, clockwise from the top left corner."""
    return [
        QRectF(0.0, 0.0, depth, depth),
        QRectF(width - depth, 0.0, depth, depth),
        QRectF(width - depth, height - depth, depth, depth),
        QRectF(0.0, height - depth, depth, depth),
    ]


def _wave_gradient(
    edge: _Edge,
    tex_width: int,
    tex_height: int,
    perimeter: float,
    phase: float,
    spec: AuroraSpec,
    exponent: float,
    offset: float,
    span: float,
) -> QLinearGradient:
    """Gradient that carries the wave along the border of one edge."""
    if edge.along == "x":
        gradient = QLinearGradient(QPointF(0.0, 0.0), QPointF(tex_width, 0.0))
    else:
        gradient = QLinearGradient(QPointF(0.0, 0.0), QPointF(0.0, tex_height))

    samples = max(4, int(span / 110))
    for index in range(samples + 1):
        ratio = index / samples
        distance = edge.start + offset + ((1.0 - ratio) if edge.along_flip else ratio) * span
        travel = (distance / perimeter - phase) % 1.0
        crest = _crest(travel, spec)
        intensity = crest**exponent
        alpha = int(255 * (spec.trough_alpha + (1.0 - spec.trough_alpha) * intensity))
        color = _palette_color(travel * spec.hue_turns)
        color = _tint(color, spec.crest_tint * crest)
        gradient.setColorAt(ratio, QColor(color.red(), color.green(), color.blue(), alpha))
    return gradient


def _falloff_value(ratio: float, depth: float, falloff: float, curve: str) -> float:
    """How much of a band is still visible at a depth, in ``[0, 1]``.

    ``exp`` fades out towards the content, ``plateau`` keeps the band even
    and drops it at the very end, which is what a neon tube needs.
    """
    if curve == "plateau":
        edge = 0.55
        t = min(1.0, max(0.0, (ratio - edge) / (1.0 - edge)))
        return 1.0 - t * t * (3.0 - 2.0 * t)
    floor = math.exp(-depth / falloff)
    return (math.exp(-(ratio * depth) / falloff) - floor) / (1.0 - floor)


def _falloff_gradient(
    edge: _Edge,
    tex_width: int,
    tex_height: int,
    depth: float,
    strength: float,
    falloff: float,
    curve: str,
) -> QLinearGradient:
    """Gradient that fades the band out towards the content.

    The gradient starts at the outer edge of the screen, so the distance
    always grows with the position on the gradient, whichever side the band
    sits on.
    """
    if edge.along == "y":
        start = QPointF(tex_width if edge.depth_flip else 0.0, 0.0)
        end = QPointF(0.0 if edge.depth_flip else tex_width, 0.0)
    else:
        start = QPointF(0.0, tex_height if edge.depth_flip else 0.0)
        end = QPointF(0.0, 0.0 if edge.depth_flip else tex_height)

    gradient = QLinearGradient(start, end)
    stops = 8
    for index in range(stops + 1):
        ratio = index / stops
        alpha = int(255 * strength * _falloff_value(ratio, depth, falloff, curve))
        gradient.setColorAt(ratio, QColor(0, 0, 0, alpha))
    return gradient


def _band_texture(
    edge: _Edge,
    tex_width: int,
    tex_height: int,
    perimeter: float,
    phase: float,
    spec: AuroraSpec,
    depth: float,
    strength: float,
    falloff: float,
    curve: str,
    exponent: float,
    offset: float,
    span: float,
) -> QImage:
    """Texture of one band: the wave along the border, the fade inwards."""
    image = QImage(tex_width, tex_height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.fillRect(image.rect(), _wave_gradient(
        edge, tex_width, tex_height, perimeter, phase, spec, exponent, offset, span
    ))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.fillRect(image.rect(), _falloff_gradient(
        edge, tex_width, tex_height, depth, strength, falloff, curve
    ))
    painter.end()
    return image


def _band_brush(texture: QImage, rect: QRectF) -> QBrush:
    """Brush that stretches a texture over the band of an edge."""
    brush = QBrush(texture)
    brush.setTransform(QTransform(
        rect.width() / texture.width(),
        0.0,
        0.0,
        rect.height() / texture.height(),
        rect.x(),
        rect.y(),
    ))
    return brush


def _corner_mask(size: int, depth: float, falloff: float, curve: str) -> QImage:
    """Alpha of a corner patch, fading with the distance to the nearest edge.

    The distance to the border of a rectangle is the smaller of the two edge
    distances.  Taking the plain maximum of both fades leaves a crease along
    the diagonal, so the maximum is smoothed out a little.  The mask only
    depends on its size, it is built once and then reused.
    """
    key = (size, int(depth), int(falloff), curve)
    cached = _CORNER_MASKS.get(key)
    if cached is not None:
        return cached

    mask = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    mask.fill(QColor(0, 0, 0, 0))
    smooth = 60.0
    for y in range(size):
        exp_y = _falloff_value(y / size, depth, falloff, curve)
        for x in range(size):
            exp_x = _falloff_value(x / size, depth, falloff, curve)
            # Smooth maximum of the two fades.
            alpha = math.log(math.exp(smooth * exp_x) + math.exp(smooth * exp_y)) / smooth
            mask.setPixelColor(x, y, QColor(0, 0, 0, min(255, max(0, int(255 * alpha)))))
    _CORNER_MASKS[key] = mask
    return mask


def _draw_band(
    painter: QPainter,
    edge: _Edge,
    rect: QRectF,
    perimeter: float,
    phase: float,
    spec: AuroraSpec,
    depth: float,
    strength: float,
    falloff: float,
    curve: str,
    exponent: float,
    offset: float,
    span: float,
) -> None:
    """Fill the band of one edge with the wave and the fade."""
    if edge.along == "x":
        tex_width = max(16, min(512, int(span / 3.0)))
        tex_height = max(4, min(40, int(depth / 2.0)))
    else:
        tex_width = max(4, min(40, int(depth / 2.0)))
        tex_height = max(16, min(512, int(span / 3.0)))
    texture = _band_texture(
        edge, tex_width, tex_height, perimeter, phase, spec,
        depth, strength, falloff, curve, exponent, offset, span,
    )
    painter.fillRect(rect, _band_brush(texture, rect))


def _draw_corner(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    alpha: float,
    mask: QImage,
) -> None:
    """Fill a corner patch with the wave colour and the corner mask."""
    patch = QImage(mask.width(), mask.height(), QImage.Format.Format_ARGB32_Premultiplied)
    patch.fill(color)
    patch_painter = QPainter(patch)
    patch_painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    patch_painter.drawImage(0, 0, mask)
    patch_painter.end()

    brush = QBrush(patch)
    brush.setTransform(QTransform(
        rect.width() / patch.width(),
        0.0,
        0.0,
        rect.height() / patch.height(),
        rect.x(),
        rect.y(),
    ))
    previous = painter.opacity()
    painter.setOpacity(previous * alpha)
    painter.fillRect(rect, brush)
    painter.setOpacity(previous)


def draw_aurora_border(
    painter: QPainter,
    width: int,
    height: int,
    phase: float,
    spec: AuroraSpec = AuroraSpec(),
) -> None:
    """Draw the animated border of the overlay.

    ``phase`` is a free running value in ``[0, 1)``: it moves the wave one
    full lap around the border.
    """
    if width <= 0 or height <= 0:
        return

    w, h = float(width), float(height)
    perimeter = 2.0 * (w + h)
    phase = phase % 1.0
    edges = _edges(w, h)
    glow_depth = min(spec.glow_depth, h / 3.0, w / 3.0)
    rim_depth = min(spec.rim_width, glow_depth)

    # The bands stop short of the corners, the patches take over there.
    for depth, strength, falloff, curve, exponent in (
        (glow_depth, spec.glow_strength, spec.glow_falloff, "exp", spec.glow_exponent),
        (rim_depth, spec.rim_strength, spec.rim_falloff, "plateau", spec.rim_exponent),
    ):
        inset = depth
        for edge in edges:
            span = edge.length - 2 * inset
            if span <= 0:
                continue
            _draw_band(
                painter, edge, _edge_rect(edge, w, h, depth, inset),
                perimeter, phase, spec, depth, strength, falloff, curve, exponent,
                inset, span,
            )

        mask = _corner_mask(max(4, int(depth)), depth, falloff, curve)
        for index, rect in enumerate(_corner_rects(w, h, depth)):
            distance = (
                0.0,
                w,
                w + h,
                2.0 * w + h,
            )[index]
            travel = (distance / perimeter - phase) % 1.0
            crest = _crest(travel, spec)
            intensity = crest**exponent
            alpha = spec.trough_alpha + (1.0 - spec.trough_alpha) * intensity
            color = _tint(
                _palette_color(travel * spec.hue_turns),
                spec.crest_tint * crest,
            )
            _draw_corner(painter, rect, color, alpha, mask)
