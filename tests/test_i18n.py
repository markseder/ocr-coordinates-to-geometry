import unittest

from ocr_coordinates_to_geometry.i18n import language_code, translate


class TranslationTests(unittest.TestCase):
    def test_russian_locale(self):
        self.assertEqual("ru", language_code("ru_RU"))
        self.assertEqual("Распознать", translate("recognize", "ru_RU"))

    def test_english_is_default(self):
        self.assertEqual("en", language_code("de_DE"))
        self.assertEqual("Recognize", translate("recognize", "en_US"))

    def test_format_values(self):
        self.assertEqual("Recognized points: 12", translate("recognized_points", "en", count=12))


if __name__ == "__main__":
    unittest.main()
