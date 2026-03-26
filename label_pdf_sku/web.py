from __future__ import annotations

import argparse
import cgi
import html
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence, Tuple
from wsgiref.simple_server import make_server

from .errors import DependencyError, LayoutError, ParseError
from .layout import LayoutConfig, validate_layout_config
from .parsing import parse_items
from .pdf_ops import append_footer_to_label

Response = Tuple[str, list[tuple[str, str]], bytes]
WsgiApp = Callable[[dict, Callable[[str, list[tuple[str, str]]], object]], Iterable[bytes]]


@dataclass(frozen=True)
class _AdvancedField:
    name: str
    config_name: str
    label: str
    input_mode: str
    step: str
    placeholder: str
    min_value: str
    parser: Callable[[str], float | int]
    parser_label: str


_ADVANCED_FIELDS = (
    _AdvancedField(
        name="min_font_size",
        config_name="min_font_size",
        label="最小字号",
        input_mode="decimal",
        step="0.1",
        placeholder=f"{LayoutConfig.min_font_size:g}",
        min_value="0.1",
        parser=float,
        parser_label="数字",
    ),
    _AdvancedField(
        name="max_font_size",
        config_name="max_font_size",
        label="最大字号",
        input_mode="decimal",
        step="0.1",
        placeholder=f"{LayoutConfig.max_font_size:g}",
        min_value="0.1",
        parser=float,
        parser_label="数字",
    ),
    _AdvancedField(
        name="max_lines",
        config_name="max_lines",
        label="最大行数",
        input_mode="numeric",
        step="1",
        placeholder=f"{LayoutConfig.max_lines:g}",
        min_value="1",
        parser=int,
        parser_label="整数",
    ),
    _AdvancedField(
        name="horizontal_padding",
        config_name="horizontal_padding",
        label="左右边距",
        input_mode="decimal",
        step="0.1",
        placeholder=f"{LayoutConfig.horizontal_padding:g}",
        min_value="0",
        parser=float,
        parser_label="数字",
    ),
    _AdvancedField(
        name="vertical_padding",
        config_name="vertical_padding",
        label="上下边距",
        input_mode="decimal",
        step="0.1",
        placeholder=f"{LayoutConfig.vertical_padding:g}",
        min_value="0",
        parser=float,
        parser_label="数字",
    ),
    _AdvancedField(
        name="footer_min_height",
        config_name="min_footer_height",
        label="底部最小高度",
        input_mode="decimal",
        step="0.1",
        placeholder=f"{LayoutConfig.min_footer_height:g}",
        min_value="0.1",
        parser=float,
        parser_label="数字",
    ),
)


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
        description="启动本地面单 SKU 标注工具。"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    app = create_app()
    try:
        with make_server(args.host, args.port, app) as server:
            print(f"面单 SKU 标注工具已启动：http://{args.host}:{args.port}")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\n服务已停止。")
    except OSError as exc:
        parser.exit(1, f"错误：{exc}\n")

    return 0


def _dispatch_request(environ: dict) -> Response:
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    if path != "/":
        return _text_response("404 Not Found", "页面不存在\n")
    if method == "GET":
        return _html_response(
            raw_items="",
            error_message=None,
            raw_layout_values=_default_layout_values(),
            advanced_open=False,
        )
    if method == "POST":
        return _handle_form_submission(environ)

    return _text_response(
        "405 Method Not Allowed",
        "不支持的请求方法\n",
        extra_headers=[("Allow", "GET, POST")],
    )


def _handle_form_submission(environ: dict) -> Response:
    form = cgi.FieldStorage(
        fp=environ["wsgi.input"],
        environ=environ,
        keep_blank_values=True,
    )
    raw_items = form.getfirst("items", "")
    raw_layout_values = _extract_layout_values(form)
    advanced_open = _advanced_settings_requested(raw_layout_values)
    upload = _extract_upload(form)

    if upload is None or not getattr(upload, "filename", ""):
        return _html_response(
            raw_items=raw_items,
            error_message="请选择一个 PDF 面单文件上传。",
            status="400 Bad Request",
            raw_layout_values=raw_layout_values,
            advanced_open=advanced_open,
        )

    uploaded_bytes = upload.file.read() if getattr(upload, "file", None) else b""
    if not uploaded_bytes:
        return _html_response(
            raw_items=raw_items,
            error_message="上传的 PDF 不能为空。",
            status="400 Bad Request",
            raw_layout_values=raw_layout_values,
            advanced_open=advanced_open,
        )

    try:
        items = parse_items(raw_items)
        layout_config = _build_layout_config(raw_layout_values)
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
                config=layout_config,
            )
            output_bytes = output_path.read_bytes()
    except (DependencyError, LayoutError, OSError, ParseError, ValueError) as exc:
        return _html_response(
            raw_items=raw_items,
            error_message=str(exc),
            status="400 Bad Request",
            raw_layout_values=raw_layout_values,
            advanced_open=advanced_open,
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
    raw_layout_values: dict[str, str] | None = None,
    advanced_open: bool = False,
) -> Response:
    escaped_items = html.escape(raw_items, quote=False)
    raw_layout_values = raw_layout_values or _default_layout_values()
    error_block = ""
    if error_message:
        error_block = (
            f'<p class="error" role="alert">{html.escape(error_message)}</p>'
        )
    advanced_fields = _render_advanced_fields(raw_layout_values)
    details_open = " open" if advanced_open else ""

    body = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>面单 SKU 标注工具</title>
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
    input[type="number"],
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
    details {{
      margin-top: 1rem;
      border-top: 1px solid #e5e7eb;
      padding-top: 1rem;
    }}
    summary {{
      cursor: pointer;
      font-weight: 600;
    }}
    fieldset {{
      margin: 0;
      padding: 0;
      border: 0;
    }}
    .advanced-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
      gap: 0.75rem 1rem;
      margin-top: 0.75rem;
    }}
    .advanced-field label {{
      margin-top: 0;
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
    <h1>面单 SKU 标注工具</h1>
    <p>上传一张快递面单 PDF，输入用中文或英文逗号分隔的 SKU 文本，即可下载底部已追加 SKU 区域的新 PDF。</p>
    {error_block}
    <form method="post" enctype="multipart/form-data">
      <label for="input_pdf">面单 PDF</label>
      <input id="input_pdf" name="input_pdf" type="file" accept="application/pdf,.pdf" required>

      <label for="items">SKU 与数量</label>
      <textarea id="items" name="items" placeholder="SF601x1，BJ601DRY x1，任意字符都可以" required>{escaped_items}</textarea>
      <p class="hint">示例：<code>SF601x1，BJ601DRY x1，第三个SKU-任意字符</code></p>

      <details class="advanced-settings"{details_open}>
        <summary>高级设置</summary>
        <fieldset>
          <p class="hint">系统会自动按列对齐排版，每行最多放 4 个完整 SKU。留空则使用默认自动布局。</p>
          <div class="advanced-grid">
            {advanced_fields}
          </div>
        </fieldset>
      </details>

      <button type="submit">生成 PDF</button>
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


def _default_layout_values() -> dict[str, str]:
    return {field.name: "" for field in _ADVANCED_FIELDS}


def _extract_layout_values(form: cgi.FieldStorage) -> dict[str, str]:
    return {
        field.name: form.getfirst(field.name, "").strip()
        for field in _ADVANCED_FIELDS
    }


def _advanced_settings_requested(raw_layout_values: dict[str, str]) -> bool:
    return any(raw_layout_values.values())


def _build_layout_config(raw_layout_values: dict[str, str]) -> LayoutConfig:
    parsed_values = {}
    for field in _ADVANCED_FIELDS:
        raw_value = raw_layout_values.get(field.name, "")
        if not raw_value:
            continue
        try:
            parsed_values[field.config_name] = field.parser(raw_value)
        except ValueError as exc:
            raise ValueError(f"{field.label}必须填写为{field.parser_label}。") from exc

    config = LayoutConfig(**parsed_values)
    validate_layout_config(config)
    return config


def _render_advanced_fields(raw_layout_values: dict[str, str]) -> str:
    rendered_fields = []
    for field in _ADVANCED_FIELDS:
        escaped_value = html.escape(raw_layout_values.get(field.name, ""), quote=True)
        rendered_fields.append(
            (
                f'<div class="advanced-field">'
                f'<label for="{field.name}">{field.label}</label>'
                f'<input id="{field.name}" name="{field.name}" type="number" '
                f'inputmode="{field.input_mode}" step="{field.step}" '
                f'min="{field.min_value}" placeholder="{field.placeholder}" '
                f'value="{escaped_value}">'
                f"</div>"
            )
        )
    return "".join(rendered_fields)


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
