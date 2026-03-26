from __future__ import annotations

import argparse
import cgi
import html
import re
import tempfile
from pathlib import Path
from typing import Callable, Iterable, Sequence, Tuple
from wsgiref.simple_server import make_server

from .errors import DependencyError, LayoutError, ParseError
from .parsing import parse_items
from .pdf_ops import append_footer_to_label

Response = Tuple[str, list[tuple[str, str]], bytes]
WsgiApp = Callable[[dict, Callable[[str, list[tuple[str, str]]], object]], Iterable[bytes]]


def create_app() -> WsgiApp:
    def app(
        environ: dict,
        start_response: Callable[[str, list[tuple[str, str]]], object],
    ) -> Iterable[bytes]:
        status, headers, body = _dispatch_request(environ)
        start_response(status, headers)
        return [body]

    return app


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the local label-pdf-sku web app."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    app = create_app()
    try:
        with make_server(args.host, args.port, app) as server:
            print(f"Serving label-pdf-sku at http://{args.host}:{args.port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down.")
    except OSError as exc:
        parser.exit(1, f"Error: {exc}\n")

    return 0


def _dispatch_request(environ: dict) -> Response:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    if path != "/":
        return _text_response("404 Not Found", "Not Found\n")
    if method == "GET":
        return _html_response(raw_items="", error_message=None)
    if method == "POST":
        return _handle_form_submission(environ)

    return _text_response(
        "405 Method Not Allowed",
        "Method Not Allowed\n",
        extra_headers=[("Allow", "GET, POST")],
    )


def _handle_form_submission(environ: dict) -> Response:
    form = cgi.FieldStorage(
        fp=environ["wsgi.input"],
        environ=environ,
        keep_blank_values=True,
    )
    raw_items = form.getfirst("items", "")
    upload = _extract_upload(form)

    if upload is None or not getattr(upload, "filename", ""):
        return _html_response(
            raw_items=raw_items,
            error_message="Choose a single PDF file to upload.",
            status="400 Bad Request",
        )

    uploaded_bytes = upload.file.read() if getattr(upload, "file", None) else b""
    if not uploaded_bytes:
        return _html_response(
            raw_items=raw_items,
            error_message="Uploaded PDF cannot be empty.",
            status="400 Bad Request",
        )

    try:
        items = parse_items(raw_items)
        download_name = _build_download_name(upload.filename)
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "input.pdf"
            output_path = temp_path / download_name
            input_path.write_bytes(uploaded_bytes)
            append_footer_to_label(
                input_pdf=input_path,
                output_pdf=output_path,
                items=items,
            )
            output_bytes = output_path.read_bytes()
    except (DependencyError, LayoutError, OSError, ParseError, ValueError) as exc:
        return _html_response(
            raw_items=raw_items,
            error_message=str(exc),
            status="400 Bad Request",
        )

    return (
        "200 OK",
        [
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", f'attachment; filename="{download_name}"'),
            ("Content-Length", str(len(output_bytes))),
            ("Cache-Control", "no-store"),
        ],
        output_bytes,
    )


def _extract_upload(form: cgi.FieldStorage):
    if "input_pdf" not in form:
        return None

    upload = form["input_pdf"]
    if isinstance(upload, list):
        return upload[0] if upload else None
    return upload


def _build_download_name(filename: str) -> str:
    normalized = filename.replace("\\", "/").split("/")[-1]
    stem = Path(normalized).stem or "label"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-") or "label"
    return f"{safe_stem}-sku.pdf"


def _html_response(
    raw_items: str,
    error_message: str | None,
    status: str = "200 OK",
) -> Response:
    escaped_items = html.escape(raw_items, quote=False)
    error_block = ""
    if error_message:
        error_block = (
            f'<p class="error" role="alert">{html.escape(error_message)}</p>'
        )

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>label-pdf-sku</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body {{
      margin: 0;
      background: #f3f4f6;
      color: #111827;
    }}
    main {{
      max-width: 44rem;
      margin: 0 auto;
      padding: 2.5rem 1rem 3rem;
    }}
    form {{
      background: #ffffff;
      border: 1px solid #d1d5db;
      border-radius: 14px;
      padding: 1.25rem;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
    }}
    h1 {{
      margin-top: 0;
      margin-bottom: 0.75rem;
      font-size: 2rem;
    }}
    p {{
      line-height: 1.5;
    }}
    label {{
      display: block;
      margin-top: 1rem;
      margin-bottom: 0.5rem;
      font-weight: 600;
    }}
    input[type="file"],
    textarea {{
      width: 100%;
      box-sizing: border-box;
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 0.75rem;
      background: #ffffff;
      color: inherit;
      font: inherit;
    }}
    textarea {{
      min-height: 8rem;
      resize: vertical;
    }}
    button {{
      margin-top: 1rem;
      border: 0;
      border-radius: 999px;
      padding: 0.85rem 1.2rem;
      background: #111827;
      color: #ffffff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .error {{
      margin-bottom: 1rem;
      border: 1px solid #fecaca;
      border-radius: 10px;
      padding: 0.75rem 0.9rem;
      background: #fef2f2;
      color: #991b1b;
    }}
    .hint {{
      color: #4b5563;
      font-size: 0.95rem;
    }}
    code {{
      font-family: "SFMono-Regular", SFMono-Regular, ui-monospace, monospace;
    }}
  </style>
</head>
<body>
  <main>
    <h1>label-pdf-sku</h1>
    <p>Upload one shipping-label PDF, enter comma-separated <code>SKU xQTY</code> values, and download the updated PDF with the footer appended.</p>
    {error_block}
    <form method="post" enctype="multipart/form-data">
      <label for="input_pdf">Label PDF</label>
      <input id="input_pdf" name="input_pdf" type="file" accept="application/pdf,.pdf" required>

      <label for="items">SKU + quantity text</label>
      <textarea id="items" name="items" placeholder="SF601 x2, BJ601DRY x1" required>{escaped_items}</textarea>
      <p class="hint">Example: <code>SF601 x2, BJ601DRY x1, DRSF601 x3</code></p>

      <button type="submit">Generate PDF</button>
    </form>
  </main>
</body>
</html>
"""
    return (
        status,
        [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body.encode("utf-8")))),
            ("Cache-Control", "no-store"),
        ],
        body.encode("utf-8"),
    )


def _text_response(
    status: str,
    body: str,
    extra_headers: list[tuple[str, str]] | None = None,
) -> Response:
    encoded_body = body.encode("utf-8")
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(encoded_body))),
        ("Cache-Control", "no-store"),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return status, headers, encoded_body
