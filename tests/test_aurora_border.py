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
        self.assertGreater(glow[0], glow[-1] + 10, 'the glow must fade with the depth')
        for closer, further in zip(glow, glow[1:]):
            self.assertGreaterEqual(closer, further, 'the glow must decay monotonically')

    def test_glow_reaches_further_than_the_old_strip(self):
        spec = AuroraSpec()
        image = self.render(0.0, spec=spec)
        edge = self.luminance(image.pixelColor(200, 0))
        far = self.luminance(image.pixelColor(200, int(spec.glow_depth * 0.6)))
        self.assertGreater(far, 4, 'the glow has to reach inside the screen')
        self.assertLess(far, edge, 'the glow still has to fade out')

    def test_wave_makes_the_border_breathe(self):
        image = self.render(0.0)
        row = [self.luminance(image.pixelColor(x, 0)) for x in range(10, 390, 10)]
        self.assertGreater(max(row) - min(row), 25, 'the wave must swell along the border')

    def test_wave_travels_with_the_phase(self):
        first = [self.luminance(self.render(0.0).pixelColor(x, 0)) for x in range(20, 380, 20)]
        later = [self.luminance(self.render(0.25).pixelColor(x, 0)) for x in range(20, 380, 20)]
        self.assertNotEqual(first, later, 'the wave has to travel along the border')

    def test_corners_do_not_double_up(self):
        image = self.render(0.0)
        # The corner patch and the edge band have to meet without a step.
        left = self.luminance(image.pixelColor(0, 150))
        corner = self.luminance(image.pixelColor(4, 150))
        self.assertLess(abs(left - corner), 40, 'the corner must not be a bright block')

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
