#!/usr/bin/env python3
"""Simple JSONL viewer server for trails_run logs."""
from __future__ import annotations

import json
import os
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR
STATIC_DIR = BASE_DIR / "viewer"
DEFAULT_LIMIT = 5000


def normalize_side(value: str | None) -> str:
    return str(value or "").upper()


def signed_multiplier(side: str | None) -> int:
    if normalize_side(side) == "SELL":
        return -1
    if normalize_side(side) == "BUY":
        return 1
    return 1


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def list_jsonl_files() -> list[str]:
    files = [p.name for p in DATA_DIR.glob("*.jsonl") if p.is_file()]
    files.sort()
    return files


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def record_matches(
    record: dict[str, Any],
    query: str | None,
    action: str | None,
    side: str | None,
    outcome: str | None,
    record_type: str | None,
    market: str | None,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> bool:
    if action and str(record.get("action")) != action:
        return False
    if side and str(record.get("side")) != side:
        return False
    if outcome and str(record.get("outcome")) != outcome:
        return False
    if record_type and str(record.get("type")) != record_type:
        return False
    if market and str(record.get("market")) != market:
        return False

    if start_dt or end_dt:
        dt = parse_dt(str(record.get("eventTimeLocal") or ""))
        if dt is None:
            return False
        if start_dt and dt < start_dt:
            return False
        if end_dt and dt > end_dt:
            return False

    if query:
        haystack = " ".join(
            str(record.get(key, ""))
            for key in ("market", "outcome", "action", "type", "side")
        ).lower()
        if query.lower() not in haystack:
            return False

    return True


def read_records(file_name: str | None, filters: dict[str, Any]) -> dict[str, Any]:
    limit = int(filters.get("limit") or DEFAULT_LIMIT)
    fast = bool(filters.get("fast"))
    query = filters.get("q")
    action = filters.get("action")
    side = filters.get("side")
    outcome = filters.get("outcome")
    record_type = filters.get("type")
    market = filters.get("market")
    start_dt = parse_dt(filters.get("start"))
    end_dt = parse_dt(filters.get("end"))

    records: list[dict[str, Any]] = []
    total_scanned = 0
    total_matched = 0
    truncated = False

    summary_counts = {
        "action": {},
        "side": {},
        "outcome": {},
    }
    net_by_outcome: dict[str, float] = {}
    total_size_signed = 0.0
    total_notional_signed = 0.0
    price_sum = 0.0
    price_count = 0

    if not file_name:
        files = list_jsonl_files()
        file_name = files[0] if files else None

    if file_name:
        path = DATA_DIR / file_name
        if path.is_file():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    total_scanned += 1
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(record, dict):
                        continue
                    if record_matches(
                        record,
                        query,
                        action,
                        side,
                        outcome,
                        record_type,
                        market,
                        start_dt,
                        end_dt,
                    ):
                        total_matched += 1
                        multiplier = signed_multiplier(record.get("side"))
                        size = safe_float(record.get("size"))
                        price = safe_float(record.get("price"))
                        total_size_signed += size * multiplier
                        total_notional_signed += size * price * multiplier
                        if price:
                            price_sum += price
                            price_count += 1

                        action_key = str(record.get("action") or "-")
                        side_key = str(record.get("side") or "-")
                        outcome_key = str(record.get("outcome") or "-")
                        summary_counts["action"][action_key] = (
                            summary_counts["action"].get(action_key, 0) + 1
                        )
                        summary_counts["side"][side_key] = (
                            summary_counts["side"].get(side_key, 0) + 1
                        )
                        summary_counts["outcome"][outcome_key] = (
                            summary_counts["outcome"].get(outcome_key, 0) + 1
                        )
                        net_by_outcome[outcome_key] = (
                            net_by_outcome.get(outcome_key, 0.0) + size * multiplier
                        )

                        if len(records) < limit:
                            records.append(record)
                        if fast and len(records) >= limit:
                            truncated = True
                            break

        if truncated:
            return {
                "records": records,
                "totalMatched": total_matched,
                "totalScanned": total_scanned,
                "limit": limit,
                "truncated": True,
                "summary": {
                    "counts": summary_counts,
                    "netByOutcome": net_by_outcome,
                    "totalSizeSigned": total_size_signed,
                    "totalNotionalSigned": total_notional_signed,
                    "avgPrice": (price_sum / price_count) if price_count else 0.0,
                },
            }

    return {
        "records": records,
        "totalMatched": total_matched,
        "totalScanned": total_scanned,
        "limit": limit,
        "truncated": False,
        "summary": {
            "counts": summary_counts,
            "netByOutcome": net_by_outcome,
            "totalSizeSigned": total_size_signed,
            "totalNotionalSigned": total_notional_signed,
            "avgPrice": (price_sum / price_count) if price_count else 0.0,
        },
    }


class ViewerHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        parsed = urlparse(self.path)
        if parsed.path == "/api/files":
            payload = {"files": list_jsonl_files()}
            self._send_json(payload)
            return

        if parsed.path == "/api/records":
            params = parse_qs(parsed.query)
            filters = {
                "q": params.get("q", [None])[0] or None,
                "action": params.get("action", [None])[0] or None,
                "side": params.get("side", [None])[0] or None,
                "outcome": params.get("outcome", [None])[0] or None,
                "type": params.get("type", [None])[0] or None,
                "market": params.get("market", [None])[0] or None,
                "start": params.get("start", [None])[0] or None,
                "end": params.get("end", [None])[0] or None,
                "limit": params.get("limit", [None])[0] or None,
                "fast": params.get("fast", [None])[0] == "1",
            }
            file_name = params.get("file", [None])[0]
            payload = read_records(file_name, filters)
            self._send_json(payload)
            return

        if parsed.path == "/":
            self.path = "/viewer/index.html"
        return super().do_GET()

    def translate_path(self, path: str) -> str:
        parsed = urlparse(path)
        safe_path = parsed.path.lstrip("/")
        full_path = (BASE_DIR / safe_path).resolve()
        if str(full_path).startswith(str(STATIC_DIR)):
            return str(full_path)
        if parsed.path.startswith("/viewer/"):
            return str(full_path)
        return str(STATIC_DIR / "index.html")

    def _send_json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), ViewerHandler)
    print(f"JSONL viewer running at http://localhost:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
