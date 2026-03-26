# label-pdf-sku

`label-pdf-sku` is a small local web app for a single shipping-label PDF at a time. It preserves the original PDF as vector content, extends the page downward, and renders manually entered SKU quantities into an adaptive footer sized for 4x6 label workflows.

## How it works

- Reads a single-page input PDF with `pypdf`.
- Keeps the original label content intact by merging that page onto a taller output page instead of rasterizing it.
- Measures footer text with `reportlab` so font size and line count adapt to the real rendered width.
- Wraps only at item boundaries, preserving the original item order.
- Exposes the existing PDF pipeline through a tiny local WSGI app with one upload form and one download response.

## Run locally

Use the project-local virtual environment if it exists:

```bash
cd /Users/jrclawbot/.openclaw/workspace/projects/label-pdf-sku
.venv/bin/python app.py
```

Then open `http://127.0.0.1:8000` in a browser.

Optional server flags:

```bash
.venv/bin/python app.py --host 127.0.0.1 --port 8000
```

## Browser usage

1. Upload one PDF label file.
2. Enter comma-separated SKU quantities such as `SF601 x2, BJ601DRY x1, DRSF601 x3`.
3. Submit the form.
4. Download the generated PDF.

## CLI

The original CLI is still available:

```bash
.venv/bin/python -m label_pdf_sku.cli input.pdf output.pdf "SF601 x2, BJ601DRY x1"
```

## Tests

Run the full test suite with the project-local environment:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

PDF integration tests run automatically when both `pypdf` and `reportlab` are installed.
