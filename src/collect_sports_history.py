#!/usr/bin/env python3
"""Collect precise historical price data for all Polymarket sports markets.

Example:
  python3 src/collect_sports_history.py \
    --output-dir data/polymarket/sports_history \
    --start-ts 1704067200 \
    --end-ts 1735689600 \
    --fidelity 1
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
USER_AGENT = "polymarket-research/1.0"

# Broader keyword set to avoid dropping sports markets whose tags do not contain "sport".
SPORTS_KEYWORDS = {
    "sport",
    "soccer",
    "football",
    "nfl",
    "ncaa",
    "basketball",
    "nba",
    "wnba",
    "baseball",
    "mlb",
    "hockey",
    "nhl",
    "golf",
    "tennis",
    "cricket",
    "mma",
    "ufc",
    "boxing",
    "f1",
    "formula 1",
    "motogp",
    "esports",
    "olympics",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect all sports market token price histories with fine-grained fidelity from "
            "Polymarket public endpoints."
        )
    )
    parser.add_argument(
        "--output-dir",
        default="data/polymarket/sports_history",
        help="Directory for raw + normalized output",
    )
    parser.add_argument("--start-ts", type=int, required=True, help="Inclusive start timestamp")
    parser.add_argument("--end-ts", type=int, default=None, help="Inclusive end timestamp")
    parser.add_argument(
        "--fidelity",
        type=int,
        default=1,
        help="Price history granularity. 1 is usually the smallest public interval.",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        default=7,
        help="Query CLOB in fixed day chunks to avoid oversized responses",
    )
    parser.add_argument("--market-limit", type=int, default=None, help="Optional cap for debugging")
    parser.add_argument("--sleep", type=float, default=0.05, help="Sleep seconds between requests")
    parser.add_argument("--retries", type=int, default=3, help="Retries per failed request")
    parser.add_argument(
        "--only-active",
        action="store_true",
        help="Collect only active/unresolved markets",
    )
    return parser.parse_args()


def http_get_json(url: str, params: Dict[str, Any], retries: int) -> Any:
    query = urllib.parse.urlencode(params, doseq=True)
    full_url = f"{url}?{query}" if query else url
    req = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
    last_err: Optional[BaseException] = None

    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            ConnectionResetError,
            OSError,
            json.JSONDecodeError,
        ) as exc:
            last_err = exc
            if attempt >= retries:
                break
            time.sleep(1.8**attempt)

    raise RuntimeError(f"Request failed after {retries + 1} attempts: {full_url} ({last_err})")


def chunk_ranges(start_ts: int, end_ts: int, chunk_days: int) -> Iterable[Tuple[int, int]]:
    step = max(1, chunk_days) * 86400
    cursor = start_ts
    while cursor <= end_ts:
        chunk_end = min(end_ts, cursor + step - 1)
        yield cursor, chunk_end
        cursor = chunk_end + 1


def normalize_slug(text: str) -> str:
    allowed: List[str] = []
    for ch in text.lower():
        if ch.isalnum() or ch in {"-", "_"}:
            allowed.append(ch)
        elif ch.isspace():
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:120] or "market"


def parse_clob_token_ids(market: Dict[str, Any]) -> List[str]:
    ids: List[str] = []

    raw_ids = market.get("clobTokenIds")
    if isinstance(raw_ids, str) and raw_ids.strip():
        try:
            parsed = json.loads(raw_ids)
            if isinstance(parsed, list):
                ids.extend(str(item) for item in parsed if item is not None)
        except json.JSONDecodeError:
            pass

    tokens = market.get("tokens")
    if isinstance(tokens, list):
        for token in tokens:
            if not isinstance(token, dict):
                continue
            val = token.get("token_id") or token.get("clobTokenId") or token.get("id")
            if val is not None:
                ids.append(str(val))

    deduped: List[str] = []
    seen: Set[str] = set()
    for token_id in ids:
        if token_id and token_id not in seen:
            deduped.append(token_id)
            seen.add(token_id)
    return deduped


def market_text_signals(market: Dict[str, Any]) -> List[str]:
    out: List[str] = []

    for key in ("category", "sportsMarketType", "question", "title", "slug"):
        value = market.get(key)
        if isinstance(value, str):
            out.append(value.lower())

    tags = market.get("tags")
    if isinstance(tags, list):
        for item in tags:
            if isinstance(item, dict):
                for key in ("slug", "label", "name"):
                    val = item.get(key)
                    if isinstance(val, str):
                        out.append(val.lower())
            elif isinstance(item, str):
                out.append(item.lower())

    event = market.get("event")
    if isinstance(event, dict):
        for key in ("category", "slug", "title"):
            val = event.get(key)
            if isinstance(val, str):
                out.append(val.lower())

    return out


def market_is_sports(market: Dict[str, Any]) -> bool:
    signals = " | ".join(market_text_signals(market))
    return any(keyword in signals for keyword in SPORTS_KEYWORDS)


def fetch_market_mode(mode_params: Dict[str, Any], retries: int, sleep_s: float) -> List[Dict[str, Any]]:
    markets: List[Dict[str, Any]] = []
    limit = 100
    offset = 0

    while True:
        params = {"limit": limit, "offset": offset, "order": "id", "ascending": "true"}
        params.update(mode_params)
        page = http_get_json(f"{GAMMA_API}/markets", params=params, retries=retries)
        if not isinstance(page, list) or not page:
            break
        markets.extend(item for item in page if isinstance(item, dict))
        if len(page) < limit:
            break
        offset += limit
        time.sleep(sleep_s)

    return markets


def fetch_all_markets(only_active: bool, retries: int, sleep_s: float) -> List[Dict[str, Any]]:
    # Use multiple modes + dedupe by market id to avoid accidental blind spots.
    modes: List[Dict[str, Any]]
    if only_active:
        modes = [{"active": "true"}]
    else:
        modes = [
            {"active": "true"},
            {"closed": "true"},
            {"archived": "true"},
            {},
        ]

    merged: Dict[str, Dict[str, Any]] = {}
    for mode in modes:
        page_items = fetch_market_mode(mode_params=mode, retries=retries, sleep_s=sleep_s)
        for item in page_items:
            market_id = item.get("id")
            key = str(market_id) if market_id is not None else str(hash(json.dumps(item, sort_keys=True)))
            merged[key] = item

    return sorted(
        merged.values(),
        key=lambda x: str(x.get("id", "")),
    )


def parse_prices_response(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("history") or payload.get("data") or payload.get("prices")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def normalize_unix_ts(ts: int) -> int:
    if ts > 10_000_000_000_000:
        return ts // 1_000_000
    if ts > 10_000_000_000:
        return ts // 1_000
    return ts


def read_point_ts(row: Dict[str, Any]) -> Optional[int]:
    for key in ("t", "timestamp", "ts", "time"):
        val = row.get(key)
        if isinstance(val, (int, float)):
            return normalize_unix_ts(int(val))
        if isinstance(val, str) and val.isdigit():
            return normalize_unix_ts(int(val))
    return None


def read_point_price(row: Dict[str, Any]) -> Optional[float]:
    for key in ("p", "price", "mid", "value"):
        val = row.get(key)
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                continue
    return None


@dataclass
class TokenSummary:
    token_id: str
    points: int = 0
    unique_points: int = 0
    min_ts: Optional[int] = None
    max_ts: Optional[int] = None


class JsonlWriter:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = path.open("w", encoding="utf-8")

    def write(self, row: Dict[str, Any]) -> None:
        self._fp.write(json.dumps(row, ensure_ascii=False) + "\n")

    def close(self) -> None:
        self._fp.close()


def collect_token_history(
    token_id: str,
    start_ts: int,
    end_ts: int,
    fidelity: int,
    chunk_days: int,
    retries: int,
    sleep_s: float,
    raw_writer: JsonlWriter,
    point_writer: JsonlWriter,
) -> TokenSummary:
    summary = TokenSummary(token_id=token_id)
    seen_ts: Set[int] = set()

    for chunk_start, chunk_end in chunk_ranges(start_ts, end_ts, chunk_days=chunk_days):
        params = {
            "market": token_id,
            "startTs": chunk_start,
            "endTs": chunk_end,
            "fidelity": fidelity,
        }
        payload = http_get_json(f"{CLOB_API}/prices-history", params=params, retries=retries)
        raw_writer.write(
            {
                "token_id": token_id,
                "start_ts": chunk_start,
                "end_ts": chunk_end,
                "requested_fidelity": fidelity,
                "fetched_at": int(time.time()),
                "payload": payload,
            }
        )

        for row in parse_prices_response(payload):
            ts = read_point_ts(row)
            price = read_point_price(row)
            point_writer.write({"token_id": token_id, "ts": ts, "price": price, "raw": row})
            summary.points += 1
            if ts is None:
                continue
            if ts not in seen_ts:
                seen_ts.add(ts)
                summary.unique_points += 1
            summary.min_ts = ts if summary.min_ts is None else min(summary.min_ts, ts)
            summary.max_ts = ts if summary.max_ts is None else max(summary.max_ts, ts)

        time.sleep(sleep_s)

    return summary


def to_utc_str(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def main() -> None:
    args = parse_args()
    end_ts = args.end_ts or int(time.time())
    if args.start_ts > end_ts:
        raise SystemExit("--start-ts must be <= --end-ts")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated_at = int(time.time())
    all_markets = fetch_all_markets(
        only_active=args.only_active,
        retries=args.retries,
        sleep_s=args.sleep,
    )
    sports_markets = [m for m in all_markets if market_is_sports(m)]
    if args.market_limit is not None:
        sports_markets = sports_markets[: args.market_limit]

    manifest: Dict[str, Any] = {
        "generated_at": generated_at,
        "generated_at_utc": to_utc_str(generated_at),
        "start_ts": args.start_ts,
        "end_ts": end_ts,
        "start_ts_utc": to_utc_str(args.start_ts),
        "end_ts_utc": to_utc_str(end_ts),
        "fidelity": args.fidelity,
        "chunk_days": args.chunk_days,
        "markets_total": len(all_markets),
        "sports_markets_total": len(sports_markets),
        "markets": [],
    }

    for idx, market in enumerate(sports_markets, start=1):
        market_title = str(market.get("question") or market.get("title") or f"market-{idx}")
        market_slug = str(market.get("slug") or normalize_slug(market_title))
        market_dir = output_dir / f"{idx:05d}_{market_slug}"
        token_ids = parse_clob_token_ids(market)

        market_entry: Dict[str, Any] = {
            "index": idx,
            "market_id": market.get("id"),
            "condition_id": market.get("conditionId"),
            "slug": market_slug,
            "question": market_title,
            "token_ids": token_ids,
            "sports_signals": market_text_signals(market),
            "tokens": [],
        }

        for token_id in token_ids:
            raw_writer = JsonlWriter(market_dir / "raw" / f"{token_id}.jsonl")
            point_writer = JsonlWriter(market_dir / "points" / f"{token_id}.jsonl")
            try:
                summary = collect_token_history(
                    token_id=token_id,
                    start_ts=args.start_ts,
                    end_ts=end_ts,
                    fidelity=args.fidelity,
                    chunk_days=args.chunk_days,
                    retries=args.retries,
                    sleep_s=args.sleep,
                    raw_writer=raw_writer,
                    point_writer=point_writer,
                )
            finally:
                raw_writer.close()
                point_writer.close()

            market_entry["tokens"].append(
                {
                    "token_id": token_id,
                    "points": summary.points,
                    "unique_points": summary.unique_points,
                    "min_ts": summary.min_ts,
                    "max_ts": summary.max_ts,
                    "min_ts_utc": to_utc_str(summary.min_ts),
                    "max_ts_utc": to_utc_str(summary.max_ts),
                }
            )

        manifest["markets"].append(market_entry)

    with (output_dir / "manifest.json").open("w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=False, indent=2)

    print(
        f"Done. sports_markets={manifest['sports_markets_total']} "
        f"output={output_dir / 'manifest.json'}",
        flush=True,
    )


if __name__ == "__main__":
    main()
