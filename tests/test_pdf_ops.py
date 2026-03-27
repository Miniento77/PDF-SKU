import tempfile
import unittest
from pathlib import Path

from label_pdf_sku.errors import DependencyError
from label_pdf_sku.layout import LayoutConfig
from label_pdf_sku.models import SkuQuantity
from label_pdf_sku.pdf_ops import (
    _prepare_source_page,
    append_footer_to_label,
    pdf_dependencies_available,
)


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
    def test_end_to_end_pdf_normalizes_non_target_input_to_4x6_without_rasterizing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "input.pdf"
            output = Path(tmp_dir) / "output.pdf"
            self._create_source_pdf(
                source,
                width=240,
                height=420,
                title="ORIGINAL LABEL 240x420",
            )

            layout = append_footer_to_label(
                input_pdf=source,
                output_pdf=output,
                items=[
                    SkuQuantity("SF601", 2),
                    SkuQuantity("BJ601DRY", 1),
                    SkuQuantity("DRSF601-CUSTOM"),
                ],
            )

            from pypdf import PdfReader

            reader = PdfReader(str(output))
            page = reader.pages[0]
            extracted_text = page.extract_text()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            self.assertEqual(len(reader.pages), 1)
            self.assertAlmostEqual(page_width / page_height, 4.0 / 6.0, places=3)
            self.assertIn("ORIGINAL LABEL 240x420", extracted_text)
            self.assertIn("SF601 x2", extracted_text)
            self.assertIn("BJ601DRY x1", extracted_text)
            self.assertIn("DRSF601-CUSTOM", extracted_text)
            self.assertEqual(layout.font_name, "Helvetica")
            self.assertGreater(layout.footer_height, 0)

    @unittest.skipUnless(
        pdf_dependencies_available(),
        "Requires pypdf and reportlab for landscape crop validation.",
    )
    def test_prepare_source_page_crops_landscape_half_content_and_rotates_clockwise(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "landscape-half.pdf"
            self._create_landscape_half_source_pdf(source)

            from pypdf import PdfReader

            plan = _prepare_source_page(PdfReader(str(source)).pages[0])

            self.assertTrue(plan.rotate_clockwise)
            self.assertAlmostEqual(plan.crop_region.width, 216.0, delta=0.5)
            self.assertAlmostEqual(plan.crop_region.height, 288.0, delta=0.5)
            self.assertAlmostEqual(plan.placed_width, 288.0, delta=0.5)
            self.assertAlmostEqual(plan.placed_height, 216.0, delta=0.5)

    @unittest.skipUnless(
        pdf_dependencies_available(),
        "Requires pypdf and reportlab for rotated-content crop validation.",
    )
    def test_prepare_source_page_trims_rotated_landscape_content_inside_portrait_page(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "portrait-embedded-landscape.pdf"
            self._create_portrait_embedded_landscape_source_pdf(source)

            from pypdf import PdfReader

            plan = _prepare_source_page(PdfReader(str(source)).pages[0])

            self.assertTrue(plan.rotate_clockwise)
            self.assertLess(plan.crop_region.top, 790.8661)
            self.assertGreater(plan.crop_region.bottom, 400.0)
            self.assertGreater(plan.crop_region.width, plan.crop_region.height)
            self.assertGreater(plan.placed_height, plan.placed_width)

    @unittest.skipUnless(
        pdf_dependencies_available(),
        "Requires pypdf and reportlab for end-to-end landscape validation.",
    )
    def test_end_to_end_pdf_crops_landscape_half_content_then_keeps_footer_working(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "landscape-half.pdf"
            output = Path(tmp_dir) / "output.pdf"
            self._create_landscape_half_source_pdf(source, title="LEFT HALF LABEL")

            layout = append_footer_to_label(
                input_pdf=source,
                output_pdf=output,
                items=[
                    SkuQuantity("HALF-LANDSCAPE", 1),
                    SkuQuantity("ROTATED", 2),
                ],
            )

            from pypdf import PdfReader

            reader = PdfReader(str(output))
            page = reader.pages[0]
            extracted_text = page.extract_text()
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            self.assertAlmostEqual(page_width / page_height, 4.0 / 6.0, places=3)
            self.assertIn("LEFT HALF LABEL", extracted_text)
            self.assertIn("HALF-LANDSCAPE x1", extracted_text)
            self.assertIn("ROTATED x2", extracted_text)
            self.assertGreater(layout.footer_height, 0)

    @unittest.skipUnless(
        pdf_dependencies_available(),
        "Requires pypdf and reportlab for CJK footer validation.",
    )
    def test_end_to_end_pdf_uses_cjk_capable_font_for_chinese_sku(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source = Path(tmp_dir) / "input.pdf"
            output = Path(tmp_dir) / "output.pdf"
            self._create_source_pdf(source)

            layout = append_footer_to_label(
                input_pdf=source,
                output_pdf=output,
                items=[SkuQuantity("测试", 2)],
            )

            from pypdf import PdfReader

            reader = PdfReader(str(output))
            page = reader.pages[0]
            extracted_text = page.extract_text()

            self.assertIn("ORIGINAL LABEL", extracted_text)
            self.assertIn("测试 x2", extracted_text)
            self.assertNotEqual(layout.font_name, "Helvetica")
            self.assertGreater(layout.footer_height, 0)

    def _create_source_pdf(
        self,
        path: Path,
        width: float = 288,
        height: float = 432,
        title: str = "ORIGINAL LABEL",
    ) -> None:
        from reportlab.pdfgen.canvas import Canvas

        canvas = Canvas(str(path), pagesize=(width, height))
        canvas.setFont("Helvetica", 16)
        canvas.drawString(32, height - 50, title)
        canvas.rect(20, 20, width - 40, height - 80)
        canvas.showPage()
        canvas.save()

    def _create_landscape_half_source_pdf(
        self,
        path: Path,
        title: str = "LANDSCAPE HALF LABEL",
    ) -> None:
        from reportlab.pdfgen.canvas import Canvas

        canvas = Canvas(str(path), pagesize=(432, 288))
        canvas.setFont("Helvetica", 16)
        canvas.drawString(24, 248, title)
        canvas.rect(18, 18, 180, 240)
        canvas.line(18, 140, 198, 140)
        canvas.showPage()
        canvas.save()

    def _create_portrait_embedded_landscape_source_pdf(self, path: Path) -> None:
        from reportlab.pdfgen.canvas import Canvas

        canvas = Canvas(str(path), pagesize=(595.2756, 790.8661))
        canvas.saveState()
        canvas.transform(0, 1, -1, 0, 513.6378, 457.5118)
        canvas.setFont("Helvetica", 16)
        canvas.drawString(24, 392, "EMBEDDED LANDSCAPE")
        canvas.rect(18, 18, 252, 396)
        canvas.line(18, 210, 270, 210)
        canvas.restoreState()
        canvas.showPage()
        canvas.save()


if __name__ == "__main__":
    unittest.main()
