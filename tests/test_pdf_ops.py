import tempfile
import unittest
from pathlib import Path

from label_pdf_sku.errors import DependencyError
from label_pdf_sku.layout import LayoutConfig
from label_pdf_sku.models import SkuQuantity
from label_pdf_sku.pdf_ops import append_footer_to_label, pdf_dependencies_available


class PdfOpsTests(unittest.TestCase):
    @unittest.skipIf(
        pdf_dependencies_available(),
        "Dependency-missing behavior only applies when PDF packages are absent.",
    )
    def test_missing_dependencies_raise_helpful_error(self) -> None:
        with self.assertRaises(DependencyError) as caught:
            append_footer_to_label(
                input_pdf="missing-input.pdf",
                output_pdf="out.pdf",
                items=[SkuQuantity("SF601", 2)],
                config=LayoutConfig(min_font_size=12, max_font_size=20),
            )

        self.assertIn("pip install pypdf reportlab", str(caught.exception))

    @unittest.skipUnless(
        pdf_dependencies_available(),
        "Requires pypdf and reportlab for end-to-end PDF validation.",
    )
    def test_end_to_end_pdf_appends_footer_without_adding_pages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "input.pdf"
            output = Path(tmp_dir) / "output.pdf"
            self._create_source_pdf(source)

            layout = append_footer_to_label(
                input_pdf=source,
                output_pdf=output,
                items=[
                    SkuQuantity("SF601", 2),
                    SkuQuantity("BJ601DRY", 1),
                    SkuQuantity("DRSF601", 3),
                ],
            )

            from pypdf import PdfReader

            reader = PdfReader(str(output))
            page = reader.pages[0]
            extracted_text = page.extract_text()

            self.assertEqual(len(reader.pages), 1)
            self.assertGreater(float(page.mediabox.height), 432.0)
            self.assertIn("ORIGINAL LABEL", extracted_text)
            self.assertIn("SF601 x2", extracted_text)
            self.assertGreater(layout.footer_height, 0)

    def _create_source_pdf(self, path: Path) -> None:
        from reportlab.pdfgen.canvas import Canvas

        width, height = 288, 432
        canvas = Canvas(str(path), pagesize=(width, height))
        canvas.setFont("Helvetica", 16)
        canvas.drawString(32, height - 50, "ORIGINAL LABEL")
        canvas.rect(20, 20, width - 40, height - 80)
        canvas.showPage()
        canvas.save()


if __name__ == "__main__":
    unittest.main()
