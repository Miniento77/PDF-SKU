from __future__ import annotations

import threading
import webbrowser
from dataclasses import dataclass
from tkinter import StringVar, Tk, ttk
from tkinter import messagebox
from typing import Callable
from wsgiref.simple_server import make_server

from .web import create_app

BrowserOpener = Callable[[str], bool]

APP_TITLE = "面单 SKU 标注工具"
APP_DESCRIPTION = (
    "应用已在本机启动。生成后的 PDF 会由浏览器直接下载，"
    "你可以一直保留这个窗口，处理完成后再点退出。"
)


def build_local_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/"


@dataclass
class DesktopServer:
    host: str = "127.0.0.1"
    port: int = 0

    def __post_init__(self) -> None:
        self._server = make_server(self.host, self.port, create_app())
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="label-pdf-sku-server",
            daemon=True,
        )
        self._started = False

    @property
    def url(self) -> str:
        return build_local_url(self.host, self._server.server_port)

    def start(self) -> None:
        if self._started:
            return
        self._thread.start()
        self._started = True

    def stop(self) -> None:
        if self._started:
            self._server.shutdown()
            if self._thread.is_alive():
                self._thread.join(timeout=3.0)
        self._server.server_close()
        self._started = False


def launch_desktop_app(browser_opener: BrowserOpener | None = None) -> int:
    opener = browser_opener or _open_browser
    server = DesktopServer()

    try:
        server.start()
    except OSError as exc:
        _show_error_dialog(f"无法启动本地服务：{exc}")
        return 1

    root = Tk()
    root.title(APP_TITLE)
    root.geometry("560x220")
    root.resizable(False, False)
    root.configure(padx=22, pady=18)

    ttk.Label(root, text=APP_TITLE, font=("Helvetica", 20, "bold")).pack(anchor="w")
    ttk.Label(
        root,
        text=APP_DESCRIPTION,
        wraplength=510,
        justify="left",
    ).pack(anchor="w", pady=(10, 12))

    ttk.Label(root, text="浏览器地址").pack(anchor="w")
    url_var = StringVar(value=server.url)
    ttk.Entry(root, textvariable=url_var, width=68).pack(anchor="w", fill="x", pady=(4, 10))

    status_var = StringVar(value="已准备就绪，浏览器会自动打开。")
    ttk.Label(root, textvariable=status_var, wraplength=510, justify="left").pack(
        anchor="w",
        pady=(0, 14),
    )

    button_row = ttk.Frame(root)
    button_row.pack(anchor="w")

    def open_in_browser() -> None:
        if opener(server.url):
            status_var.set("浏览器已打开。如果没有自动切换，请手动复制上面的地址。")
        else:
            status_var.set("没有找到可用浏览器，请复制上面的地址手动打开。")

    def copy_url() -> None:
        root.clipboard_clear()
        root.clipboard_append(server.url)
        status_var.set("地址已经复制到剪贴板。")

    def shutdown() -> None:
        status_var.set("正在关闭本地服务…")
        root.update_idletasks()
        server.stop()
        root.destroy()

    ttk.Button(button_row, text="打开网页", command=open_in_browser).pack(
        side="left", padx=(0, 8)
    )
    ttk.Button(button_row, text="复制地址", command=copy_url).pack(
        side="left", padx=(0, 8)
    )
    ttk.Button(button_row, text="退出", command=shutdown).pack(side="left")

    root.protocol("WM_DELETE_WINDOW", shutdown)
    root.after(350, open_in_browser)
    root.mainloop()
    return 0


def _open_browser(url: str) -> bool:
    return bool(webbrowser.open(url, new=2))


def _show_error_dialog(message: str) -> None:
    root = Tk()
    root.withdraw()
    messagebox.showerror(APP_TITLE, message)
    root.destroy()
