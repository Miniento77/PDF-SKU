import io
import unittest
from pathlib import Path
from unittest.mock import patch
from wsgiref.util import setup_testing_defaults

from label_pdf_sku.web import create_app, main


def build_multipart_body(
    fields: dict[str, str],
    files: list[tuple[str, str, str, bytes]],
) -> tuple[bytes, str]:
    boundary = "----label-pdf-sku-test-boundary"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8")
        )
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, filename, content_type, content in files:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(content)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def invoke_app(
    app,
    method: str,
    path: str = "/",
    body: bytes = b"",
    content_type: str = "text/plain",
):
    environ = {}
    setup_testing_defaults(environ)
    environ.update(
        {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": content_type,
            "wsgi.input": io.BytesIO(body),
        }
    )

    metadata = {}

    def start_response(status, headers):
        metadata["status"] = status
        metadata["headers"] = dict(headers)

    response_iter = app(environ, start_response)
    try:
        response_body = b"".join(response_iter)
    finally:
        close = getattr(response_iter, "close", None)
        if close is not None:
            close()

    return metadata["status"], metadata["headers"], response_body


class WebAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()

    def test_get_root_renders_form(self) -> None:
        status, headers, body = invoke_app(self.app, "GET")

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b'type="file"', body)
        self.assertIn(b'name="items"', body)

    @patch("label_pdf_sku.web.append_footer_to_label")
    def test_post_root_returns_generated_pdf(self, append_footer_to_label_mock) -> None:
        def write_output(input_pdf, output_pdf, items):
            self.assertTrue(Path(input_pdf).exists())
            self.assertEqual(
                [item.display_text for item in items],
                ["SF601 x2", "BJ601DRY x1"],
            )
            Path(output_pdf).write_bytes(b"%PDF-1.4\nmock output\n")

        append_footer_to_label_mock.side_effect = write_output
        body, content_type = build_multipart_body(
            fields={"items": "SF601 x2, BJ601DRY x1"},
            files=[
                (
                    "input_pdf",
                    "shipping-label.pdf",
                    "application/pdf",
                    b"%PDF-1.4\nmock input\n",
                )
            ],
        )

        status, headers, response_body = invoke_app(
            self.app,
            "POST",
            body=body,
            content_type=content_type,
        )

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/pdf")
        self.assertEqual(
            headers["Content-Disposition"],
            'attachment; filename="shipping-label-sku.pdf"',
        )
        self.assertEqual(response_body, b"%PDF-1.4\nmock output\n")

    def test_post_root_returns_form_error_for_invalid_items(self) -> None:
        body, content_type = build_multipart_body(
            fields={"items": "SF601"},
            files=[
                (
                    "input_pdf",
                    "shipping-label.pdf",
                    "application/pdf",
                    b"%PDF-1.4\nmock input\n",
                )
            ],
        )

        status, headers, response_body = invoke_app(
            self.app,
            "POST",
            body=body,
            content_type=content_type,
        )

        self.assertEqual(status, "400 Bad Request")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(b"Could not parse", response_body)

    @patch("sys.stdout", new_callable=io.StringIO)
    @patch("label_pdf_sku.web.make_server")
    def test_main_starts_server(self, make_server_mock, stdout: io.StringIO) -> None:
        class DummyServer:
            def __init__(self) -> None:
                self.served = False

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback) -> bool:
                return False

            def serve_forever(self) -> None:
                self.served = True

        dummy_server = DummyServer()
        make_server_mock.return_value = dummy_server

        exit_code = main(["--host", "127.0.0.1", "--port", "8765"])

        self.assertEqual(exit_code, 0)
        self.assertTrue(dummy_server.served)
        make_server_mock.assert_called_once()
        self.assertIn("http://127.0.0.1:8765", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
