import unittest

from label_pdf_sku.errors import LayoutError
from label_pdf_sku.layout import LayoutConfig, choose_footer_layout
from label_pdf_sku.models import SkuQuantity


def fake_measure(text: str, font_name: str, font_size: float) -> float:
    del font_name
    return len(text) * font_size


class ChooseFooterLayoutTests(unittest.TestCase):
    def test_prefers_single_line_when_it_supports_max_font_size(self) -> None:
        layout = choose_footer_layout(
            items=[SkuQuantity("SF601", 2), SkuQuantity("BJ601DRY", 1)],
            page_width=160,
            config=LayoutConfig(
                min_font_size=1,
                max_font_size=5,
                max_lines=3,
                horizontal_padding=10,
                vertical_padding=5,
                min_footer_height=20,
            ),
            measure_text=fake_measure,
        )

        self.assertEqual(len(layout.lines), 1)
        self.assertEqual(layout.font_size, 5.0)
        self.assertEqual(layout.lines[0].text, "SF601 x2, BJ601DRY x1")

    def test_splits_into_multiple_lines_when_needed_for_legibility(self) -> None:
        layout = choose_footer_layout(
            items=[
                SkuQuantity("SF601", 2),
                SkuQuantity("BJ601DRY", 1),
                SkuQuantity("DRSF601", 3),
            ],
            page_width=40,
            config=LayoutConfig(
                min_font_size=1,
                max_font_size=5,
                max_lines=3,
                horizontal_padding=2,
                vertical_padding=4,
                min_footer_height=18,
            ),
            measure_text=fake_measure,
        )

        self.assertGreaterEqual(layout.font_size, 2.0)
        self.assertEqual(len(layout.lines), 3)
        self.assertEqual(
            [line.text for line in layout.lines],
            ["SF601 x2", "BJ601DRY x1", "DRSF601 x3"],
        )

    def test_raises_when_text_cannot_fit_bounds(self) -> None:
        with self.assertRaises(LayoutError):
            choose_footer_layout(
                items=[SkuQuantity("EXTREMELY-LONG-SKU-CODE", 9)],
                page_width=18,
                config=LayoutConfig(
                    min_font_size=2,
                    max_font_size=3,
                    max_lines=1,
                    horizontal_padding=4,
                    vertical_padding=4,
                    min_footer_height=12,
                ),
                measure_text=fake_measure,
            )


if __name__ == "__main__":
    unittest.main()

