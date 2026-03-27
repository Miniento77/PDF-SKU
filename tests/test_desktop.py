import unittest
from unittest.mock import patch

from label_pdf_sku.desktop import DesktopServer, build_local_url


class DesktopTests(unittest.TestCase):
    def test_build_local_url(self) -> None:
        self.assertEqual(build_local_url("127.0.0.1", 8765), "http://127.0.0.1:8765/")

    @patch("label_pdf_sku.desktop.make_server")
    def test_desktop_server_start_and_stop(self, make_server_mock) -> None:
        class DummyServer:
            server_port = 8765

            def __init__(self) -> None:
                self.served = False
                self.shutdown_called = False
                self.closed = False

            def serve_forever(self) -> None:
                self.served = True

            def shutdown(self) -> None:
                self.shutdown_called = True

            def server_close(self) -> None:
                self.closed = True

        dummy_server = DummyServer()
        make_server_mock.return_value = dummy_server

        server = DesktopServer()
        self.assertEqual(server.url, "http://127.0.0.1:8765/")

        server.start()
        server._thread.join(timeout=1.0)
        self.assertTrue(dummy_server.served)

        server.stop()
        self.assertTrue(dummy_server.shutdown_called)
        self.assertTrue(dummy_server.closed)
        self.assertFalse(server._started)


if __name__ == "__main__":
    unittest.main()
