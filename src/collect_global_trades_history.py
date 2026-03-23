#!/usr/bin/env python3
"""Collect full trade history for one Polymarket market via Data API /trades.

Example:
  python3 src/collect_global_trades_history.py --market-slug bitboy-convicted
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

GAMMA_API = "https://gamma-api.polymarket.com"
DATA_API = "https://data-api.polymarket.com"
USER_AGENT = "polymarket-research-trades-rebuild/1.0"
OUTPUT_ROOT = Path("data/market_trade_history/by_market")
PAGE_LIMIT = 1000
SLEEP_S = 0.02
RETRIES = 3


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect full trade history for one market using /trades?market=<conditionId>."
    )
    parser.add_argument(
        "--market-condition-id",
        default="",
        help="Target conditionId (0x...).",
    )
    parser.add_argument(
        "--market-slug",
        default="",
        help="Target market slug. Auto-resolved to conditionId via Gamma.",
    )
    return parser.parse_args()


def to_utc(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


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
            time.sleep(1.7**attempt)
    raise RuntimeError(f"Request failed: {full_url} ({last_err})")


def resolve_target_market(market_condition_id: str, market_slug: str) -> Dict[str, Any]:
    cid = market_condition_id.strip()
    slug = market_slug.strip()

    if bool(cid) == bool(slug):
        raise SystemExit("Provide exactly one of --market-condition-id or --market-slug")

    if cid:
        if cid.isdigit():
            raise SystemExit(
                "--market-condition-id expects conditionId (0x...), not Gamma numeric market id."
            )
        return {
            "market_id": "",
            "condition_id": cid,
            "slug": None,
            "question": None,
        }

    rows = http_get_json(
        f"{GAMMA_API}/markets",
        params={"slug": slug, "limit": 1, "offset": 0},
        retries=RETRIES,
    )
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"Could not resolve slug to market: {slug}")

    row = rows[0]
    resolved_cid = str(row.get("conditionId") or "")
    if not resolved_cid:
        raise SystemExit(f"Resolved market has no conditionId: slug={slug}")

    return {
        "market_id": str(row.get("id") or ""),
        "condition_id": resolved_cid,
        "slug": row.get("slug"),
        "question": row.get("question") or row.get("title"),
    }


def trade_key(row: Dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("transactionHash") or ""),
            str(row.get("asset") or ""),
            str(row.get("timestamp") or ""),
            str(row.get("price") or ""),
            str(row.get("size") or ""),
            str(row.get("side") or ""),
        ]
    )


def iter_market_trades(condition_id: str) -> Iterable[List[Dict[str, Any]]]:
    offset = 0
    while True:
        try:
            rows = http_get_json(
                f"{DATA_API}/trades",
                params={"market": condition_id, "limit": PAGE_LIMIT, "offset": offset},
                retries=RETRIES,
            )
        except RuntimeError as exc:
            if "HTTP Error 400" in str(exc):
                log(f"[stop] page_limit_reached offset={offset} detail={exc}")
                break
            raise
        if not isinstance(rows, list) or not rows:
            break
        yield [r for r in rows if isinstance(r, dict)]
        if len(rows) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(SLEEP_S)


def output_dir_for_target(target: Dict[str, Any]) -> Path:
    slug = str(target.get("slug") or "").strip()
    if slug:
        name = slug
    else:
        cid = str(target.get("condition_id") or "")
        name = f"condition_{cid[:18]}" if cid else "unknown_market"
    return OUTPUT_ROOT / name


def main() -> None:
    args = parse_args()
    target = resolve_target_market(args.market_condition_id, args.market_slug)

    out_dir = output_dir_for_target(target)
    out_dir.mkdir(parents=True, exist_ok=True)
    ticks_path = out_dir / "trades_ticks.jsonl"
    manifest_path = out_dir / "manifest.json"

    log(
        "[target] "
        f"condition_id={target.get('condition_id')} "
        f"market_id={target.get('market_id')} "
        f"slug={target.get('slug')}"
    )

    seen: Set[str] = set()
    total_rows = 0
    kept_rows = 0
    min_ts: Optional[int] = None
    max_ts: Optional[int] = None

    with ticks_path.open("w", encoding="utf-8") as fp:
        for page_idx, rows in enumerate(iter_market_trades(str(target.get("condition_id") or "")), start=1):
            page_kept = 0
            page_min_ts: Optional[int] = None
            page_max_ts: Optional[int] = None

            for row in rows:
                total_rows += 1
                ts = row.get("timestamp")
                if not isinstance(ts, (int, float)):
                    continue
                ts_i = int(ts)
                page_min_ts = ts_i if page_min_ts is None else min(page_min_ts, ts_i)
                page_max_ts = ts_i if page_max_ts is None else max(page_max_ts, ts_i)

                key = trade_key(row)
                if key in seen:
                    continue
                seen.add(key)

                out_row = {
                    "timestamp": ts_i,
                    "timestamp_utc": to_utc(ts_i),
                    "price": row.get("price"),
                    "size": row.get("size"),
                    "side": row.get("side"),
                    "asset": row.get("asset"),
                    "condition_id": row.get("conditionId"),
                    "transaction_hash": row.get("transactionHash"),
                    "market_id": target.get("market_id"),
                    "slug": target.get("slug") or row.get("slug"),
                    "question": target.get("question") or row.get("title"),
                    "event_slug": row.get("eventSlug"),
                    "outcome": row.get("outcome"),
                    "outcome_index": row.get("outcomeIndex"),
                    "proxy_wallet": row.get("proxyWallet"),
                    "raw": row,
                }
                fp.write(json.dumps(out_row, ensure_ascii=False) + "\n")
                kept_rows += 1
                page_kept += 1
                min_ts = ts_i if min_ts is None else min(min_ts, ts_i)
                max_ts = ts_i if max_ts is None else max(max_ts, ts_i)

            log(
                f"[page] idx={page_idx} rows={len(rows)} kept={page_kept} "
                f"total_rows={total_rows} total_kept={kept_rows} "
                f"page_min_ts={page_min_ts} page_max_ts={page_max_ts}"
            )

    now_ts = int(time.time())
    manifest = {
        "generated_at": now_ts,
        "generated_at_utc": to_utc(now_ts),
        "target_market": target,
        "fetched_trade_rows_total": total_rows,
        "kept_trade_rows": kept_rows,
        "kept_min_ts": min_ts,
        "kept_max_ts": max_ts,
        "kept_min_ts_utc": to_utc(min_ts),
        "kept_max_ts_utc": to_utc(max_ts),
        "output_file": str(ticks_path),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[done] manifest={manifest_path} kept_trade_rows={kept_rows}")


if __name__ == "__main__":
    main()
