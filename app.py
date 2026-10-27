"""Serve the current SET row on GET /set.

Each request reads the live homepage feed again. Quantity is thousands of
shares. Value is million baht.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME_URL = "https://www.set.or.th/th/home"
FEED_URL = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))


class SetClient:
    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())

    def open_session(self) -> None:
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
        self._read(HOME_URL, "text/html,application/xhtml+xml")

    def fetch_set_row(self) -> dict:
        try:
            body = self._read(FEED_URL, "application/json, text/plain, */*")
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403):
                raise
            self.open_session()
            body = self._read(FEED_URL, "application/json, text/plain, */*")
        data = json.loads(body)
        rows = data.get("indexIndustrySectors") or []
        row = next((item for item in rows if item.get("symbol") == "SET"), None)
        if not row or row.get("last") is None or row.get("value") is None:
            raise LookupError("SET row was not in the index feed.")
        return row

    def _read(self, url: str, accept: str) -> bytes:
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": accept,
                "Referer": HOME_URL,
                "Origin": "https://www.set.or.th",
            },
        )
        with self.opener.open(request, timeout=20) as response:
            return response.read()


def as_map(row: dict) -> dict[str, str | float | int]:
    quantity = round(float(row["volume"]) / 1000)
    return {
        "index": "SET",
        "latest": float(row["last"]),
        "change": float(row["change"]),
        "quantity": int(quantity) if float(quantity).is_integer() else quantity,
        "value": round(float(row["value"]) / 1_000_000, 2),
    }


CLIENT = SetClient()
CLIENT_LOCK = threading.Lock()


class SetHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path != "/set":
            self._send(404, {"error": "Not found"})
            return
        try:
            with CLIENT_LOCK:
                row = CLIENT.fetch_set_row()
        except Exception as exc:
            self._send(502, {"error": str(exc)})
            return
        self._send(200, as_map(row))

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} {fmt % args}", file=sys.stderr, flush=True)


def main() -> int:
    CLIENT.open_session()
    server = ThreadingHTTPServer((HOST, PORT), SetHandler)
    print(f"GET http://{HOST}:{PORT}/set", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
