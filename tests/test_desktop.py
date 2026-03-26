import unittest
from urllib.request import urlopen

from label_pdf_sku.desktop import DesktopServer, build_local_url


class DesktopTests(unittest.TestCase):
    def test_build_local_url(self) -> None:
        self.assertEqual(build_local_url("127.0.0.1", 8765), "http://127.0.0.1:8765/")

    def test_desktop_server_serves_home_page(self) -> None:
        server = DesktopServer()
        server.start()
        try:
            with urlopen(server.url) as response:
                body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("面单 SKU 标注工具", body)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
