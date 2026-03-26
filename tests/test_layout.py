import unittest

from label_pdf_sku.errors import LayoutError
from label_pdf_sku.layout import LayoutConfig, choose_footer_layout
from label_pdf_sku.models import SkuQuantity


def fake_measure(text: str, font_name: str, font_size: float) -> float:
    del font_name
    return len(text) * font_size


class ChooseFooterLayoutTests(unittest.TestCase):
    def test_prefers_multiple_columns_with_alignment_when_it_supports_max_font_size(self) -> None:
        layout = choose_footer_layout(
            items=[SkuQuantity("SF601x2"), SkuQuantity("BJ601DRY x1")],
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
        self.assertEqual([cell.text for cell in layout.lines[0].cells], ["SF601x2", "BJ601DRY x1"])
        self.assertEqual(len(layout.column_widths), 2)

    def test_wraps_to_multiple_rows_with_no_more_than_four_items_per_line(self) -> None:
        layout = choose_footer_layout(
            items=[
                SkuQuantity("A001"),
                SkuQuantity("B002"),
                SkuQuantity("C003"),
                SkuQuantity("D004"),
                SkuQuantity("E005"),
                SkuQuantity("F006"),
            ],
            page_width=120,
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

        self.assertEqual(len(layout.lines), 2)
        self.assertEqual(
            [len(line.cells) for line in layout.lines],
            [4, 2],
        )
        self.assertEqual(
            [[cell.column_index for cell in line.cells] for line in layout.lines],
            [[0, 1, 2, 3], [0, 1]],
        )
        self.assertEqual(len(layout.column_widths), 4)

    def test_raises_when_text_cannot_fit_bounds(self) -> None:
        with self.assertRaises(LayoutError):
            choose_footer_layout(
                items=[SkuQuantity("EXTREMELY-LONG-SKU-CODE")],
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
