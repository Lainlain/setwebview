"""Load the SET homepage in a hidden webview and return the SET row as a map.

No window is shown. The result is only the SET index row.
"""

from __future__ import annotations

import json
import sys
import time

import webview

HOME_URL = "https://www.set.or.th/th/home"
WAIT_SECONDS = 45

# The homepage fills this table after JavaScript runs. Return JSON only when
# the SET row has both a latest price and a trading value.
EXTRACT_TABLE_JS = r"""
(() => {
  const clean = (value) => (value || "").replace(/\s+/g, " ").trim();
  const tables = Array.from(document.querySelectorAll("table"));
  for (const table of tables) {
    if (table.offsetParent === null) continue;
    const headers = Array.from(table.querySelectorAll("thead th")).map((cell) => clean(cell.innerText));
    if (headers.length < 5) continue;
    const headerText = headers.join(" ").toLowerCase();
    const isIndexTable = headerText.includes("ดัชนี") || headerText.includes("index");
    const hasLatest = headerText.includes("ล่าสุด") || headerText.includes("latest");
    const hasValue = headerText.includes("มูลค่า") || headerText.includes("value");
    if (!isIndexTable || !hasLatest || !hasValue) continue;

    const setRow = Array.from(table.querySelectorAll("tbody tr")).map((row) => {
      const cells = Array.from(row.querySelectorAll("td")).map((cell) => clean(cell.innerText));
      if (cells.length < 5 || cells[0] !== "SET" || !cells[1] || !cells[4]) return null;
      return {
        index: cells[0],
        latest: cells[1],
        change: cells[2],
        quantity: cells[3],
        value: cells[4]
      };
    }).find(Boolean);

    if (setRow) return JSON.stringify(setRow);
  }
  return "";
})()
"""


def parse_number(text: str) -> float:
    cleaned = text.replace(",", "").replace(" ", "").strip()
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    return float(cleaned)


def read_set_row(window: webview.Window) -> dict[str, str]:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        try:
            raw = window.evaluate_js(EXTRACT_TABLE_JS)
        except Exception:
            raw = None
        if raw:
            row = json.loads(raw)
            if isinstance(row, dict) and row.get("index") == "SET":
                return row
        time.sleep(0.5)
    raise TimeoutError(f"SET row was not ready within {WAIT_SECONDS} seconds.")


def as_map(row: dict[str, str]) -> dict[str, str | float | int]:
    quantity = parse_number(row["quantity"])
    return {
        "index": row["index"],
        "latest": parse_number(row["latest"]),
        "change": parse_number(row["change"]),
        "quantity": int(quantity) if quantity.is_integer() else quantity,
        "value": parse_number(row["value"]),
    }


def main() -> int:
    window = webview.create_window(
        "SET",
        HOME_URL,
        hidden=True,
        width=1280,
        height=900,
    )
    status = {"code": 0}

    def load_and_read() -> None:
        try:
            row = as_map(read_set_row(window))
            print(json.dumps(row, indent=2))
        except Exception as exc:
            status["code"] = 1
            print(f"Failed to read the SET table: {exc}", file=sys.stderr)
        finally:
            window.destroy()

    webview.start(load_and_read, private_mode=True, gui="edgechromium")
    return status["code"]


if __name__ == "__main__":
    raise SystemExit(main())
