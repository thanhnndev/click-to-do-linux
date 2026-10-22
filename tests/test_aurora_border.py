import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt6.QtGui import QColor, QImage, QPainter
from PyQt6.QtWidgets import QApplication
from click_to_do_linux.ui.aurora import AuroraSpec, draw_aurora_border


class AuroraBorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def render(self, phase, width=400, height=300, spec=None):
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0, 255))
        painter = QPainter(image)
        draw_aurora_border(painter, width, height, phase, spec or AuroraSpec())
        painter.end()
        return image

    @staticmethod
    def luminance(color):
        return max(color.red(), color.green(), color.blue())

    @staticmethod
    def hue(color):
        return color.hue()

    def test_rim_is_bright_and_saturated(self):
        image = self.render(0.0)
        rim = image.pixelColor(200, 0)
        self.assertGreater(self.luminance(rim), 60, 'the rim must read as a bright line')
        self.assertGreater(
            self.luminance(rim) - min(rim.red(), rim.green(), rim.blue()), 20,
            'the rim must keep a saturated hue',
        )

    def test_glow_fades_out_towards_the_content(self):
        image = self.render(0.0)
        depth = [12, 24, 40, 60]
        glow = [self.luminance(image.pixelColor(200, y)) for y in depth]
        self.assertGreater(glow[0], glow[-1] + 5, 'the glow must fade with the depth')
        for closer, further in zip(glow, glow[1:]):
            self.assertGreaterEqual(closer, further, 'the glow must decay monotonically')

    def test_glow_reaches_further_than_the_old_strip(self):
        spec = AuroraSpec()
        image = self.render(0.0, spec=spec)
        edge = self.luminance(image.pixelColor(200, 0))
        far = self.luminance(image.pixelColor(200, int(spec.glow_depth * 0.6)))
        self.assertGreater(far, 4, 'the glow has to reach inside the screen')
        self.assertLess(far, edge, 'the glow still has to fade out')

    def test_sweep_travels_with_the_phase(self):
        # The rotating sweep must move the colour at a fixed point.
        first = self.render(0.0).pixelColor(200, 0)
        later = self.render(0.25).pixelColor(200, 0)
        self.assertNotEqual(
            (first.red(), first.green(), first.blue()),
            (later.red(), later.green(), later.blue()),
            'the sweep has to travel along the border',
        )

    def test_sweep_is_not_uniform_around_the_border(self):
        # A real wave is not one flat colour: different points along the
        # border must carry different hues at the same instant.
        image = self.render(0.0)
        hues = {image.pixelColor(x, 0).hue() for x in (50, 200, 350)}
        self.assertGreater(len(hues), 1, 'the border must not be a single flat colour')

    def test_painter_opacity_is_restored(self):
        image = QImage(200, 200, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        draw_aurora_border(painter, 200, 200, 0.25)
        self.assertAlmostEqual(painter.opacity(), 1.0, places=3)
        painter.end()

    def test_empty_surface_is_ignored(self):
        image = QImage(10, 10, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0, 0))
        painter = QPainter(image)
        draw_aurora_border(painter, 0, 0, 0.5)
        painter.end()
        self.assertEqual(image.pixelColor(5, 5).alpha(), 0)


if __name__ == '__main__':
    unittest.main()
