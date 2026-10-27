"""Watch the SET index and print the SET row whenever it changes.

Linux servers have no Edge webview and usually no GTK or Qt. This reads the
same feed the homepage table uses, after opening the homepage once so the
site accepts the request. Quantity is thousands of shares. Value is million baht.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

HOME_URL = "https://www.set.or.th/th/home"
FEED_URL = "https://www.set.or.th/api/set/index/info/list?type=INDEX"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
WAIT_SECONDS = 45
POLL_SECONDS = 1


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


def watch() -> int:
    client = SetClient()
    previous: dict | None = None
    announced = False
    deadline = time.monotonic() + WAIT_SECONDS

    print(
        "Watching SET. A new map is printed only when the row changes. Press Ctrl+C to stop.",
        file=sys.stderr,
        flush=True,
    )

    try:
        client.open_session()
        while True:
            try:
                row = client.fetch_set_row()
            except Exception as exc:
                if previous is None and time.monotonic() > deadline:
                    print(f"SET row was not ready: {exc}", file=sys.stderr, flush=True)
                    return 1
                time.sleep(POLL_SECONDS)
                continue

            if not announced:
                status = row.get("marketStatus") or "unknown"
                print(f"Market status: {status}", file=sys.stderr, flush=True)
                announced = True
            current = as_map(row)
            if current != previous:
                print(json.dumps(current, indent=2), flush=True)
                previous = current
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        return 0


def main() -> int:
    return watch()


if __name__ == "__main__":
    raise SystemExit(main())
