import io
import unittest
from pathlib import Path
from unittest.mock import patch

from label_pdf_sku.cli import main
from label_pdf_sku.layout import FooterLayout, FooterLine


class CliTests(unittest.TestCase):
    @patch("label_pdf_sku.cli.append_footer_to_label")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_main_parses_items_and_passes_config(
        self,
        stdout: io.StringIO,
        append_footer_to_label_mock,
    ) -> None:
        append_footer_to_label_mock.return_value = FooterLayout(
            font_name="Helvetica-Bold",
            font_size=18.0,
            lines=[FooterLine(text="SF601 x2, BJ601DRY x1", width=180.0)],
            footer_height=72.0,
            line_spacing=1.15,
            horizontal_padding=18.0,
            vertical_padding=12.0,
        )

        exit_code = main(
            [
                "input.pdf",
                "output.pdf",
                "SF601 x2, BJ601DRY x1",
                "--min-font-size",
                "10",
                "--max-font-size",
                "24",
                "--max-lines",
                "3",
                "--horizontal-padding",
                "20",
                "--vertical-padding",
                "8",
                "--footer-min-height",
                "54",
            ]
        )

        self.assertEqual(exit_code, 0)
        append_footer_to_label_mock.assert_called_once()
        call = append_footer_to_label_mock.call_args
        self.assertEqual(call.kwargs["input_pdf"], Path("input.pdf"))
        self.assertEqual(call.kwargs["output_pdf"], Path("output.pdf"))
        self.assertEqual(
            [item.display_text for item in call.kwargs["items"]],
            ["SF601 x2", "BJ601DRY x1"],
        )
        self.assertEqual(call.kwargs["config"].min_font_size, 10.0)
        self.assertEqual(call.kwargs["config"].max_font_size, 24.0)
        self.assertEqual(call.kwargs["config"].max_lines, 3)
        self.assertIn("output.pdf", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
