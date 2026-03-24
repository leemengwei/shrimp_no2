#!/usr/bin/env python3
"""Collect full trade history for all markets a user has participated in.

Example:
  python3 src/collect_user_markets_full_trades.py --user lee0708
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

DATA_API = "https://data-api.polymarket.com"
USER_AGENT = "polymarket-research-user-markets/1.0"
PAGE_LIMIT = 1000
SLEEP_S = 0.02
RETRIES = 3
OUTPUT_ROOT = Path("data/market_trade_history/by_user")


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect full market trades for every market touched by a user."
    )
    parser.add_argument("--user", required=True, help="Username or wallet address")
    return parser.parse_args()


def to_utc(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def safe_slug(text: Optional[str]) -> str:
    if not text:
        return "unknown"
    out: List[str] = []
    for ch in str(text).lower():
        if ch.isalnum() or ch in {"-", "_"}:
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    s = "".join(out).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s[:120] or "unknown"


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


def iter_user_trades(user: str) -> Iterable[List[Dict[str, Any]]]:
    offset = 0
    transient_failures = 0
    while True:
        try:
            rows = http_get_json(
                f"{DATA_API}/trades",
                params={"user": user, "limit": PAGE_LIMIT, "offset": offset},
                retries=RETRIES,
            )
            transient_failures = 0
        except RuntimeError as exc:
            if "HTTP Error 400" in str(exc):
                log(f"[user-stop] offset={offset} detail={exc}")
                break
            transient_failures += 1
            if transient_failures >= 6:
                raise
            log(
                f"[user-retry] offset={offset} attempt={transient_failures}/5 detail={exc}"
            )
            time.sleep(min(10.0, 1.6**transient_failures))
            continue
        if not isinstance(rows, list) or not rows:
            break
        yield [r for r in rows if isinstance(r, dict)]
        if len(rows) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(SLEEP_S)


def iter_market_trades(condition_id: str) -> Iterable[List[Dict[str, Any]]]:
    offset = 0
    transient_failures = 0
    while True:
        try:
            rows = http_get_json(
                f"{DATA_API}/trades",
                params={"market": condition_id, "limit": PAGE_LIMIT, "offset": offset},
                retries=RETRIES,
            )
            transient_failures = 0
        except RuntimeError as exc:
            if "HTTP Error 400" in str(exc):
                log(f"[market-stop] condition={condition_id} offset={offset} detail={exc}")
                break
            transient_failures += 1
            if transient_failures >= 6:
                raise
            log(
                f"[market-retry] condition={condition_id} offset={offset} "
                f"attempt={transient_failures}/5 detail={exc}"
            )
            time.sleep(min(10.0, 1.6**transient_failures))
            continue
        if not isinstance(rows, list) or not rows:
            break
        yield [r for r in rows if isinstance(r, dict)]
        if len(rows) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(SLEEP_S)


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


def resolve_user_wallet(user: str) -> str:
    if user.lower().startswith("0x") and len(user) == 42:
        return user.lower()
    rows = http_get_json(
        f"{DATA_API}/trades",
        params={"user": user, "limit": 20, "offset": 0},
        retries=RETRIES,
    )
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"Could not resolve user to wallet: {user}")
    counts: Dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        w = str(row.get("proxyWallet") or "").lower()
        if not w.startswith("0x") or len(w) != 42:
            continue
        counts[w] = counts.get(w, 0) + 1
    if not counts:
        raise SystemExit(f"Could not resolve user wallet from trades rows: {user}")
    wallet = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]
    return wallet


def collect_user_markets(user: str) -> Dict[str, Dict[str, Any]]:
    markets: Dict[str, Dict[str, Any]] = {}
    wallet = None
    total_rows = 0
    for page_idx, rows in enumerate(iter_user_trades(user), start=1):
        total_rows += len(rows)
        for row in rows:
            cid = str(row.get("conditionId") or "")
            if not cid:
                continue
            if wallet is None and row.get("proxyWallet"):
                wallet = str(row.get("proxyWallet"))
            info = markets.get(cid)
            if info is None:
                info = {
                    "condition_id": cid,
                    "slug": row.get("slug"),
                    "title": row.get("title"),
                    "last_user_trade_ts": row.get("timestamp"),
                }
                markets[cid] = info
            else:
                ts = row.get("timestamp")
                prev = info.get("last_user_trade_ts")
                if isinstance(ts, (int, float)) and (not isinstance(prev, (int, float)) or ts > prev):
                    info["last_user_trade_ts"] = int(ts)
            if not info.get("slug") and row.get("slug"):
                info["slug"] = row.get("slug")
            if not info.get("title") and row.get("title"):
                info["title"] = row.get("title")
        log(f"[user-page] idx={page_idx} rows={len(rows)} unique_markets={len(markets)}")

    if wallet:
        log(f"[user] resolved_wallet={wallet}")
    log(f"[user] total_user_trade_rows={total_rows} unique_markets={len(markets)}")
    return markets


def main() -> None:
    args = parse_args()
    user = args.user.strip()
    if not user:
        raise SystemExit("--user is required")

    wallet = resolve_user_wallet(user)
    log(f"[user] input={user} resolved_wallet={wallet}")
    markets = collect_user_markets(wallet)
    if not markets:
        raise SystemExit(f"No markets found for user={wallet}")

    user_dir = OUTPUT_ROOT / safe_slug(user)
    markets_dir = user_dir / "markets"
    markets_dir.mkdir(parents=True, exist_ok=True)

    summary_markets: List[Dict[str, Any]] = []
    total_market_rows = 0

    sorted_markets = sorted(
        markets.values(),
        key=lambda x: int(x.get("last_user_trade_ts") or 0),
        reverse=True,
    )

    for idx, m in enumerate(sorted_markets, start=1):
        cid = str(m.get("condition_id") or "")
        slug = safe_slug(m.get("slug") or cid)
        market_dir = markets_dir / f"{idx:04d}_{slug}"
        market_dir.mkdir(parents=True, exist_ok=True)
        ticks_path = market_dir / "trades_ticks.jsonl"
        manifest_path = market_dir / "manifest.json"

        seen: Set[str] = set()
        kept = 0
        min_ts: Optional[int] = None
        max_ts: Optional[int] = None
        pages = 0
        fetched_rows = 0

        with ticks_path.open("w", encoding="utf-8") as fp:
            for page_idx, rows in enumerate(iter_market_trades(cid), start=1):
                pages = page_idx
                fetched_rows += len(rows)
                page_kept = 0
                for row in rows:
                    ts = row.get("timestamp")
                    if not isinstance(ts, (int, float)):
                        continue
                    ts_i = int(ts)
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
                        "slug": row.get("slug") or m.get("slug"),
                        "question": row.get("title") or m.get("title"),
                        "event_slug": row.get("eventSlug"),
                        "outcome": row.get("outcome"),
                        "outcome_index": row.get("outcomeIndex"),
                        "proxy_wallet": row.get("proxyWallet"),
                        "raw": row,
                    }
                    fp.write(json.dumps(out_row, ensure_ascii=False) + "\n")
                    kept += 1
                    page_kept += 1
                    min_ts = ts_i if min_ts is None else min(min_ts, ts_i)
                    max_ts = ts_i if max_ts is None else max(max_ts, ts_i)

                log(
                    f"[market-page] {idx}/{len(sorted_markets)} cid={cid[:10]}... "
                    f"page={page_idx} rows={len(rows)} kept={page_kept}"
                )

        total_market_rows += kept
        market_manifest = {
            "condition_id": cid,
            "slug": m.get("slug"),
            "title": m.get("title"),
            "last_user_trade_ts": m.get("last_user_trade_ts"),
            "last_user_trade_ts_utc": to_utc(int(m.get("last_user_trade_ts")))
            if isinstance(m.get("last_user_trade_ts"), (int, float))
            else None,
            "fetched_rows_total": fetched_rows,
            "kept_trade_rows": kept,
            "pages": pages,
            "min_ts": min_ts,
            "max_ts": max_ts,
            "min_ts_utc": to_utc(min_ts),
            "max_ts_utc": to_utc(max_ts),
            "output_file": str(ticks_path),
        }
        manifest_path.write_text(json.dumps(market_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_markets.append(market_manifest)

    top_manifest = {
        "generated_at": int(time.time()),
        "generated_at_utc": to_utc(int(time.time())),
        "user": user,
        "resolved_wallet": wallet,
        "markets_total": len(summary_markets),
        "kept_trade_rows_total": total_market_rows,
        "markets": summary_markets,
    }
    (user_dir / "manifest.json").write_text(
        json.dumps(top_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"[done] user={user} markets={len(summary_markets)} "
        f"kept_trade_rows_total={total_market_rows} out={user_dir / 'manifest.json'}"
    )


if __name__ == "__main__":
    main()
