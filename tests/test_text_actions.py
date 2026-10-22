import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PIL import Image
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QAbstractButton, QApplication, QWidget
from click_to_do_linux.ai.entities import EntityDetector, LinkEntity, merge_text_lines
from click_to_do_linux.ai.ocr import OCREngine, TextBox
from click_to_do_linux.capture.screen import CapturedScreen
from click_to_do_linux.ui.action_bar import ActionBar
from click_to_do_linux.ui.overlay import OverlayWindow
from click_to_do_linux.i18n import t


def box(text, x=30, y=100, w=350, h=20):
    return TextBox(text, 0.99, (x, y, w, h))


def event(x, y, shift=False, pressed=False):
    return SimpleNamespace(
        pos=lambda: QPoint(x, y),
        button=lambda: Qt.MouseButton.LeftButton,
        buttons=lambda: Qt.MouseButton.LeftButton if pressed else Qt.MouseButton.NoButton,
        modifiers=lambda: Qt.KeyboardModifier.ShiftModifier if shift else Qt.KeyboardModifier.NoModifier,
    )


def click_action(bar, label):
    for widget in bar.findChildren(QAbstractButton):
        if widget.isVisibleTo(bar) and widget.text().strip() == label:
            widget.click()
            return
    raise AssertionError(f'Missing button: {label}')


class LinkTests(unittest.TestCase):
    def test_patterns_punctuation_and_email(self):
        self.assertEqual(EntityDetector.extract_urls(
            'https://example.technology/a?q=1&b=2, www.example.com and '
            'example.org/path. https://example.technology/a?q=1&b=2'
        ), ['https://example.technology/a?q=1&b=2', 'www.example.com', 'example.org/path'])
        self.assertEqual(EntityDetector.extract_urls('(https://example.com/wiki/Foo_(bar)).'),
                         ['https://example.com/wiki/Foo_(bar)'])
        self.assertEqual(EntityDetector.extract_urls('hello@sub.example.com'), [])

    def test_detect_before_selection_across_multiple_boxes(self):
        boxes = [box('https://example.com/a-very-long'),
                 box('path/with-query?token=ab', y=125),
                 box('c123&download=1', y=150),
                 box('Separate paragraph', y=200)]
        links = EntityDetector.detect_links(boxes)
        self.assertEqual(len(links), 1)
        link = links[0]
        self.assertEqual(link.text, 'https://example.com/a-very-longpath/with-query?token=abc123&download=1')
        self.assertEqual(len(link.rects), 3)
        for y in (110, 135, 160):
            self.assertTrue(link.contains_point(40, y))
        self.assertFalse(link.contains_point(40, 210))

    def test_nearby_column_does_not_break_or_extend_link(self):
        boxes = [box('https://example.com/long'), box('Sidebar', x=700, y=110),
                 box('path', y=125), box('Footer', y=250)]
        self.assertEqual(EntityDetector.detect_links(boxes)[0].text, 'https://example.com/longpath')

    def test_wrapped_hostname_and_filename(self):
        for first, second, expected in [
            ('https://exam', 'ple.com/path', 'https://example.com/path'),
            ('www.example.com/files/', 'report.pdf', 'www.example.com/files/report.pdf'),
            ('example.com/path/', 'next', 'example.com/path/next'),
        ]:
            with self.subTest(first=first):
                self.assertEqual(EntityDetector.detect_links([box(first), box(second, y=125)])[0].text, expected)

    def test_hostname_dot_wrap_from_reported_screenshot(self):
        # Actual OCR geometry from the user-provided screenshot, without storing it.
        boxes = [box('https://humanforward.', 21, 580, 537, 56),
                 box('academy/AIBuilderResidency', 18, 640, 690, 61),
                 box('AI Builder Residency là chương trình đào tạo', 21, 769, 967, 55)]
        links = EntityDetector.detect_links(boxes)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].text, 'https://humanforward.academy/AIBuilderResidency')
        self.assertEqual(len(links[0].rects), 2)
        self.assertTrue(links[0].contains_point(40, 660))

    def test_hostname_dot_does_not_join_next_sentence(self):
        links = EntityDetector.detect_links([
            box('https://example.com.'), box('This is another sentence', y=125)])
        self.assertEqual(links[0].text, 'https://example.com')
        self.assertEqual(len(links[0].rects), 1)

    def test_two_urls_on_one_line_have_distinct_hit_areas(self):
        links = EntityDetector.detect_links([box('See https://one.test/a and https://two.test/b', w=430)])
        self.assertEqual([link.text for link in links], ['https://one.test/a', 'https://two.test/b'])
        self.assertFalse(links[0].contains_point(35, 110))  # preceding prose
        self.assertLess(links[0].rect[0] + links[0].rect[2], links[1].rect[0])

    def test_separate_urls_and_prose_are_not_joined(self):
        for first, second in [
            ('https://one.test/path', 'https://two.test/path'),
            ('https://one.test/path.', 'Next'),
            ('https://one.test/path', 'Normal prose here'),
            ('https://one.test', 'Heading'),
        ]:
            with self.subTest(second=second):
                links = EntityDetector.detect_links([box(first), box(second, y=125)])
                self.assertEqual(links[0].text, first.rstrip('.'))

    def test_separate_bare_domain_after_paragraph_gap(self):
        links = EntityDetector.detect_links([box('https://one.test/path'), box('two.test', y=200)])
        self.assertEqual([link.text for link in links], ['https://one.test/path', 'two.test'])

    def test_domain_shaped_filename_is_a_path_continuation(self):
        links = EntityDetector.detect_links([box('https://example.com/rep'), box('ort.unlistedextension', y=125)])
        self.assertEqual([link.text for link in links], ['https://example.com/report.unlistedextension'])

    def test_every_possible_line_break_in_url_components(self):
        urls = [
            'https://humanforward.academy/AIBuilderResidency',
            'https://example.technology:8443/a-report.v2.pdf?download=1&token=ab%2Fcd#section-2',
            'www.example.com/path',
            'http://127.0.0.1:8080/a',
            'http://[::1]:8080/a',
            'https://example.com',
            'https://example.com/tiếng-việt',
            'https://example.com/?redirect=https://target.org/a',
            'HTTPS://EXAMPLE.COM/A',
            'https://www.example.com/a',
            'https://user:pass@example.com/path',
            'http://localhost:8080/a',
        ]
        for url in urls:
            for first in range(1, len(url)):
                with self.subTest(url=url, cut=first):
                    links = EntityDetector.detect_links([box(url[:first]), box(url[first:], y=125)])
                    self.assertEqual([link.text for link in links], [url])
                for second in range(first + 1, len(url)):
                    with self.subTest(url=url, cuts=(first, second)):
                        links = EntityDetector.detect_links([
                            box(url[:first]), box(url[first:second], y=125), box(url[second:], y=150)])
                        self.assertEqual([link.text for link in links], [url])

    def test_adjacent_ocr_boxes_on_same_line(self):
        url = 'https://humanforward.academy/AIBuilderResidency'
        for cut in range(1, len(url)):
            with self.subTest(cut=cut):
                links = EntityDetector.detect_links([
                    box(url[:cut], w=200), box(url[cut:], x=234, w=300)])
                self.assertEqual([link.text for link in links], [url])

    def test_ocr_spaces_around_structural_punctuation(self):
        for text in ['https: //humanforward. academy/AIBuilderResidency',
                     'https://humanforward. academy/AIBuilderResidency']:
            with self.subTest(text=text):
                links = EntityDetector.detect_links([box(text)])
                self.assertEqual([link.text for link in links],
                                 ['https://humanforward.academy/AIBuilderResidency'])

    def test_inline_link_with_hanging_indent(self):
        links = EntityDetector.detect_links([
            box('Visit: https://humanforward.', w=540),
            box('academy/AIBuilderResidency', x=170, y=125)])
        self.assertEqual([link.text for link in links], ['https://humanforward.academy/AIBuilderResidency'])

    def test_incomplete_protocol_or_domain_is_not_a_link(self):
        for text in ['https:', 'https://', 'https://humanforward.', 'www.']:
            with self.subTest(text=text):
                self.assertEqual(EntityDetector.detect_links([box(text)]), [])

    def test_invalid_continuation_does_not_remove_valid_link(self):
        links = EntityDetector.detect_links([box('https://example.com'), box(':badport', y=125)])
        self.assertEqual([link.text for link in links], ['https://example.com'])

    def test_merge_vietnamese_text(self):
        self.assertEqual(merge_text_lines('Xin chào\n  thế giới\r\nHôm nay'), 'Xin chào thế giới Hôm nay')


class LinkRecognitionTests(unittest.TestCase):
    def setUp(self):
        self.image = Image.new('RGB', (1125, 2076), 'white')
        self.link = LinkEntity('https://humanforward.academy/AlBuilderResidency',
                               ((21, 580, 537, 56), (18, 640, 690, 61)))

    @patch('click_to_do_linux.ai.ocr.tesseract_ready', return_value=True)
    def test_english_url_pass_preserves_dot_and_corrects_ocr_confusable(self, _ready):
        with patch.object(OCREngine, '_tesseract_line', side_effect=[
            'https://humanforward.', 'academy/AIBuilderResidency'
        ]) as read:
            result = OCREngine.refine_links(self.image, [self.link])
        self.assertEqual(result[0].text, 'https://humanforward.academy/AIBuilderResidency')
        self.assertEqual(result[0].rects, self.link.rects)
        self.assertTrue(all(call.kwargs == {'url_mode': True} for call in read.call_args_list))

    @patch('click_to_do_linux.ai.ocr.tesseract_ready', return_value=True)
    def test_disagreeing_second_pass_keeps_original(self, _ready):
        with patch.object(OCREngine, '_tesseract_line', side_effect=[
            'https://other.', 'academy/different'
        ]):
            self.assertEqual(OCREngine.refine_links(self.image, [self.link]), [self.link])

    @patch('click_to_do_linux.ai.ocr.tesseract_ready', return_value=True)
    def test_failed_second_pass_keeps_original(self, _ready):
        with patch.object(OCREngine, '_tesseract_line', side_effect=OSError('unavailable')):
            self.assertEqual(OCREngine.refine_links(self.image, [self.link]), [self.link])

    @patch('click_to_do_linux.ai.ocr.tesseract_ready', return_value=False)
    def test_without_tesseract_keeps_detected_links(self, _ready):
        self.assertEqual(OCREngine.refine_links(self.image, [self.link]), [self.link])


class ActionBarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.bar = ActionBar()
        self.actions = []
        self.bar.action_triggered.connect(lambda action, payload: self.actions.append((action, payload)))

    def tearDown(self):
        self.bar.close()
        self.bar.deleteLater()

    def test_text_region_copy_checkbox(self):
        self.bar.show_for_text('First\nsecond', region=True)
        click_action(self.bar, t('copy'))
        self.assertEqual(self.actions[-1], ('copy_text', 'First\nsecond'))
        self.bar.merge_lines.setChecked(True)
        click_action(self.bar, t('copy'))
        self.assertEqual(self.actions[-1], ('copy_text', 'First second'))

    def test_image_region_copy_has_no_link_actions(self):
        text = 'https://example.com/a\nSome text'
        self.bar.show_for_image(None, text)
        self.assertFalse(self.bar.merge_lines.isHidden())
        self.bar.merge_lines.setChecked(True)
        click_action(self.bar, t('copy_region_text'))
        self.assertEqual(self.actions[-1], ('copy_text', 'https://example.com/a Some text'))
        with self.assertRaises(AssertionError):
            click_action(self.bar, t('copy_link'))

    def test_link_actions_are_independent_of_merge_setting(self):
        self.bar.merge_lines.setChecked(True)
        self.bar.show_for_link('https://example.com/a')
        self.assertTrue(self.bar.merge_lines.isHidden())
        click_action(self.bar, t('copy_link'))
        self.assertEqual(self.actions[-1], ('copy_text', 'https://example.com/a'))
        click_action(self.bar, t('open_link'))
        self.assertEqual(self.actions[-1], ('open_url', 'https://example.com/a'))
        self.assertEqual(self.bar.row_layout.count(), 2)

    def test_switching_visible_toolbar_measures_buttons_before_positioning(self):
        parent = QWidget()
        parent.resize(1100, 700)
        self.bar.setParent(parent)
        parent.show()
        self.bar.show_for_link('https://example.com/a')
        for show in (
            lambda: self.bar.show_for_image(None, 'First\nsecond'),
            lambda: self.bar.show_for_text('First\nsecond', region=True),
            lambda: self.bar.show_for_link('https://example.com/b'),
            lambda: self.bar.show_for_image(None, 'Another region'),
        ):
            show()
            self.bar.reposition((100, 200, 100, 40), 1100, 700)
            # No processEvents: this must be correct in the mouse-release handler.
            for i in range(self.bar.row_layout.count()):
                widget = self.bar.row_layout.itemAt(i).widget()
                self.assertFalse(widget.isHidden())
                self.assertTrue(self.bar.rect().contains(widget.geometry()), widget.geometry())
            self.assertGreaterEqual(self.bar.width(), self.bar.sizeHint().width())
            self.assertLessEqual(self.bar.x() + self.bar.width(), parent.width())
        self.bar.setParent(None)
        parent.close()

    def test_plain_box_has_no_merge_checkbox(self):
        self.bar.show_for_text('A line')
        self.assertTrue(self.bar.merge_lines.isHidden())


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        pixmap = QPixmap(1000, 700)
        pixmap.fill(Qt.GlobalColor.white)
        capture = CapturedScreen(Image.new('RGB', (1000, 700), 'white'), pixmap,
                                 1000, 700, 1000, 700, 1.0)
        with patch.object(OverlayWindow, '_start_ocr'):
            self.overlay = OverlayWindow(capture)
        self.boxes = [box('https://example.com/long'), box('path?x=1', y=125),
                      box('Đây là dòng một', y=250), box('và dòng hai', y=275)]
        self.overlay._on_ocr_finished(self.boxes, [])
        self.overlay.show()

    def tearDown(self):
        self.overlay.close()
        self.overlay.deleteLater()

    def drag(self, shift=False):
        self.overlay.mousePressEvent(event(20, 240, shift))
        self.overlay.mouseMoveEvent(event(400, 305, shift, pressed=True))
        self.overlay.mouseReleaseEvent(event(400, 305, shift))

    def test_cached_analysis_keeps_refined_link(self):
        from click_to_do_linux.ai.screen_cache import ScreenAnalysisCache
        link = LinkEntity('https://example.com/AIBuilder', ((30, 100, 350, 20),))
        boxes, qr, links = ScreenAnalysisCache.clone_result((self.boxes, [], [link]))
        self.overlay._on_ocr_finished(boxes, qr, links)
        self.assertEqual(self.overlay.link_entities[0].text, link.text)
        self.overlay.mouseReleaseEvent(event(40, 110))
        with patch('click_to_do_linux.ui.overlay.ClipboardManager.copy_text') as copy:
            self.overlay._handle_copy_shortcut()
            copy.assert_called_once_with(link.text)

    def test_links_exist_before_user_selects_anything(self):
        self.assertFalse(self.overlay.selected_boxes)
        self.assertIsNone(self.overlay.selected_rect)
        self.assertEqual([l.text for l in self.overlay.link_entities], ['https://example.com/longpath?x=1'])

    def test_click_continuation_selects_link_and_ctrl_c_copies_whole_link(self):
        self.overlay.mouseReleaseEvent(event(45, 135))
        self.assertEqual(self.overlay.selected_link.text, 'https://example.com/longpath?x=1')
        self.assertFalse(self.overlay.selected_boxes)
        self.assertTrue(self.overlay.action_bar.merge_lines.isHidden())
        with patch('click_to_do_linux.ui.overlay.ClipboardManager.copy_text') as copy:
            self.overlay._handle_copy_shortcut()
            copy.assert_called_once_with('https://example.com/longpath?x=1')

    def test_double_click_continuation_copies_link(self):
        with patch('click_to_do_linux.ui.overlay.ClipboardManager.copy_text') as copy:
            self.overlay.mouseDoubleClickEvent(event(45, 135))
            copy.assert_called_once_with('https://example.com/longpath?x=1')

    def test_drag_after_link_clears_link_and_merges_only_region_text(self):
        self.overlay.mouseReleaseEvent(event(45, 135))
        self.drag()
        self.assertIsNone(self.overlay.selected_link)
        self.assertFalse(self.overlay.action_bar.merge_lines.isHidden())
        self.overlay.action_bar.merge_lines.setChecked(True)
        with patch('click_to_do_linux.ui.overlay.ClipboardManager.copy_text') as copy:
            click_action(self.overlay.action_bar, t('copy_region_text'))
            copy.assert_called_once_with('Đây là dòng một và dòng hai')

    def test_shift_drag_ctrl_c_respects_checkbox(self):
        self.drag(shift=True)
        self.overlay.action_bar.merge_lines.setChecked(True)
        with patch('click_to_do_linux.ui.overlay.ClipboardManager.copy_text') as copy:
            self.overlay._handle_copy_shortcut()
            copy.assert_called_once_with('Đây là dòng một và dòng hai')

    def test_shift_click_link_still_allows_raw_text_selection(self):
        self.overlay.mouseReleaseEvent(event(45, 135, shift=True))
        self.assertIsNone(self.overlay.selected_link)
        self.assertEqual(self.overlay.selected_boxes, [self.boxes[1]])


if __name__ == '__main__':
    unittest.main()
