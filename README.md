# label-pdf-sku

`label-pdf-sku` is a small CLI that preserves a single-page shipping-label PDF as vector content, extends the page downward, and renders manually entered SKU quantities into a footer sized for 4x6 label workflows.

## How it works

- Reads a single-page input PDF with `pypdf`.
- Keeps the original label content intact by merging that page onto a taller output page instead of rasterizing it.
- Measures footer text with `reportlab` so font size and line count adapt to the real rendered width.
- Wraps only at item boundaries, preserving the original item order.

## Install

Create a virtual environment if you want one, then install the two runtime dependencies:

```bash
python3 -m pip install pypdf reportlab
```

## Usage

The CLI lives in `app.py`.

```bash
python3 app.py input-label.pdf output-label.pdf "SF601 x2, BJ601DRY x1, DRSF601 x3"
```

Optional flags:

- `--min-font-size`: lower bound for adaptive sizing. Default `12`.
- `--max-font-size`: upper bound for adaptive sizing. Default `28`.
- `--max-lines`: maximum footer line count. Default `4`.
- `--horizontal-padding`: left/right footer padding in points. Default `18`.
- `--vertical-padding`: top/bottom footer padding in points. Default `12`.
- `--footer-min-height`: minimum footer height in points. Default `60`.

Example with tighter bounds:

```bash
python3 app.py input.pdf output.pdf "SF601 x2, BJ601DRY x1, DRSF601 x3" \
  --max-lines 3 \
  --min-font-size 14 \
  --max-font-size 24
```

## Tests

The test suite uses the standard library `unittest` runner:

```bash
python3 -m unittest discover -s tests -v
```

What runs:

- Parser and layout unit tests run without third-party packages.
- CLI argument plumbing runs without third-party packages.
- PDF integration tests automatically skip unless both `pypdf` and `reportlab` are installed.
