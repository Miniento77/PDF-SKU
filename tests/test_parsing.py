import unittest

from label_pdf_sku.errors import ParseError
from label_pdf_sku.parsing import parse_items, render_item_text


class ParseItemsTests(unittest.TestCase):
    def test_parse_items_preserves_order_and_original_text(self) -> None:
        items = parse_items("SF601x2，BJ601DRY x1, 第三个SKU-任意字符")

        self.assertEqual(
            [render_item_text(item) for item in items],
            ["SF601x2", "BJ601DRY x1", "第三个SKU-任意字符"],
        )

    def test_parse_items_accepts_any_characters_between_commas(self) -> None:
        items = parse_items("  SF601x1  ,   型号A/蓝色#2  ")

        self.assertEqual([item.display_text for item in items], ["SF601x1", "型号A/蓝色#2"])

    def test_parse_items_rejects_blank_input(self) -> None:
        with self.assertRaises(ParseError):
            parse_items("   ")

    def test_parse_items_rejects_blank_chunk(self) -> None:
        with self.assertRaises(ParseError):
            parse_items("SF601x1，")


if __name__ == "__main__":
    unittest.main()
