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

    def test_rim_is_bright_and_saturated(self):
        image = self.render(0.0)
        rim = image.pixelColor(200, 0)
        brightest = max(rim.red(), rim.green(), rim.blue())
        self.assertGreater(brightest, 120, 'the rim must read as a bright line')
        self.assertGreater(brightest - min(rim.red(), rim.green(), rim.blue()), 30,
                           'the rim must keep a saturated hue')

    def test_bloom_fades_out_towards_the_content(self):
        image = self.render(0.0)
        depth = [12, 24, 40, 60]
        glow = [max(image.pixelColor(200, y).getRgb()[:3]) for y in depth]
        self.assertGreater(glow[0], glow[-1] + 20, 'the glow must fade with the depth')
        for closer, further in zip(glow, glow[1:]):
            self.assertGreaterEqual(closer, further, 'the glow must decay monotonically')

    def test_bloom_reaches_further_than_the_old_strip(self):
        spec = AuroraSpec()
        image = self.render(0.0, spec=spec)
        edge = max(image.pixelColor(200, 0).getRgb()[:3])
        far = max(image.pixelColor(200, int(spec.bloom_depth * 0.7)).getRgb()[:3])
        self.assertGreater(far, 6, 'the glow has to reach inside the screen')
        self.assertLess(far, edge * 0.4, 'the glow still has to fade out')

    def test_hue_sweeps_with_the_phase(self):
        first = self.render(0.0).pixelColor(200, 0).getRgb()
        later = self.render(0.5).pixelColor(200, 0).getRgb()
        self.assertNotEqual(first, later, 'the rim colour has to animate')

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
