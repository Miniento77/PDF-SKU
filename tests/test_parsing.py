import unittest

from label_pdf_sku.errors import ParseError
from label_pdf_sku.parsing import parse_items, render_item_text


class ParseItemsTests(unittest.TestCase):
    def test_parse_items_preserves_order_and_quantities(self) -> None:
        items = parse_items("SF601 x2, BJ601DRY x1, DRSF601 x3")

        self.assertEqual([item.sku for item in items], ["SF601", "BJ601DRY", "DRSF601"])
        self.assertEqual([item.quantity for item in items], [2, 1, 3])
        self.assertEqual(
            [render_item_text(item) for item in items],
            ["SF601 x2", "BJ601DRY x1", "DRSF601 x3"],
        )

    def test_parse_items_accepts_case_insensitive_x_and_whitespace(self) -> None:
        items = parse_items("  SF601   X2 ,   BJ601DRY x1  ")

        self.assertEqual([item.display_text for item in items], ["SF601 x2", "BJ601DRY x1"])

    def test_parse_items_rejects_blank_input(self) -> None:
        with self.assertRaises(ParseError):
            parse_items("   ")

    def test_parse_items_rejects_missing_quantity(self) -> None:
        with self.assertRaises(ParseError):
            parse_items("SF601, BJ601DRY x1")

    def test_parse_items_rejects_zero_quantity(self) -> None:
        with self.assertRaises(ParseError):
            parse_items("SF601 x0")


if __name__ == "__main__":
    unittest.main()

