import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from label_pdf_sku.cli import main
from label_pdf_sku.layout import FooterCell, FooterLayout, FooterLine
from label_pdf_sku.pdf_ops import pdf_dependencies_available


class CliTests(unittest.TestCase):
    @patch("label_pdf_sku.cli.append_footer_to_label")
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_main_parses_items_and_passes_config(
        self,
        stdout: io.StringIO,
        append_footer_to_label_mock,
    ) -> None:
        append_footer_to_label_mock.return_value = FooterLayout(
            font_name="Helvetica",
            font_size=18.0,
            lines=[
                FooterLine(
                    text="SF601x2 | BJ601DRY x1",
                    width=180.0,
                    cells=(
                        FooterCell(text="SF601x2", width=72.0, column_index=0),
                        FooterCell(text="BJ601DRY x1", width=108.0, column_index=1),
                    ),
                )
            ],
            footer_height=72.0,
            line_spacing=1.15,
            horizontal_padding=18.0,
            vertical_padding=12.0,
            column_widths=(72.0, 108.0),
            column_gap=12.0,
        )

        exit_code = main(
            [
                "input.pdf",
                "output.pdf",
                "SF601x2，BJ601DRY x1",
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
            ["SF601x2", "BJ601DRY x1"],
        )
        self.assertEqual(call.kwargs["config"].min_font_size, 10.0)
        self.assertEqual(call.kwargs["config"].max_font_size, 24.0)
        self.assertEqual(call.kwargs["config"].max_lines, 3)
        self.assertIn("output.pdf", stdout.getvalue())

    @unittest.skipUnless(
        pdf_dependencies_available(),
        "Requires pypdf and reportlab for CLI module execution validation.",
    )
    def test_python_m_label_pdf_sku_cli_creates_output_pdf(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        with tempfile.TemporaryDirectory() as tmp_dir:
            input_pdf = Path(tmp_dir) / "input.pdf"
            output_pdf = Path(tmp_dir) / "output.pdf"
            self._create_source_pdf(input_pdf)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "label_pdf_sku.cli",
                    str(input_pdf),
                    str(output_pdf),
                    "answer",
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(output_pdf.exists())
            self.assertIn(str(output_pdf), completed.stdout)

    def _create_source_pdf(self, path: Path) -> None:
        from reportlab.pdfgen.canvas import Canvas

        canvas = Canvas(str(path), pagesize=(288, 432))
        canvas.setFont("Helvetica", 16)
        canvas.drawString(32, 382, "ORIGINAL LABEL")
        canvas.rect(20, 20, 248, 332)
        canvas.showPage()
        canvas.save()


if __name__ == "__main__":
    unittest.main()
