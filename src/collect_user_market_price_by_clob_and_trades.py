#!/usr/bin/env python3
"""Collect independent market history from both CLOB and trades for all markets touched by a user.

Example:
  python3 src/collect_user_market_price_by_clob_and_trades.py \
    --user 0x1ea6aab09d4b9b504fa24f961f0c6709efb72f5d \
    --start-ts 0 \
    --fidelity 1 \
    --chunk-days 7
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
from typing import Any, Dict, List, Optional, Set

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
USER_AGENT = "polymarket-research-user-price-history/1.0"
PAGE_LIMIT = 1000
RETRIES = 3
SLEEP_S = 0.02
OUTPUT_ROOT = Path("data/market_price_by_clob_and_trades/by_user")


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect independent CLOB history and trades history for markets touched by a user."
    )
    parser.add_argument("--user", required=True, help="Username or wallet address")
    parser.add_argument(
        "--start-ts",
        type=int,
        default=0,
        help="Inclusive unix start ts for history window. Default 0 (from earliest possible).",
    )
    parser.add_argument(
        "--end-ts",
        type=int,
        default=0,
        help="Inclusive unix end ts. Default 0 means now.",
    )
    parser.add_argument("--fidelity", type=int, default=1, help="CLOB prices-history fidelity.")
    parser.add_argument("--chunk-days", type=int, default=7, help="Split TS window into day chunks.")
    parser.add_argument("--market-limit", type=int, default=0, help="Debug: only process first N markets.")
    return parser.parse_args()


def to_utc(ts: Optional[int]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def parse_ts(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            return int(s)
        try:
            return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
        except ValueError:
            return None
    return None


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
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]


def collect_user_markets(user_wallet: str) -> List[Dict[str, Any]]:
    offset = 0
    markets: Dict[str, Dict[str, Any]] = {}
    while True:
        rows = http_get_json(
            f"{DATA_API}/trades",
            params={"user": user_wallet, "limit": PAGE_LIMIT, "offset": offset},
            retries=RETRIES,
        )
        if not isinstance(rows, list) or not rows:
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("conditionId") or "")
            if not cid:
                continue
            info = markets.get(cid)
            ts = row.get("timestamp")
            ts_i = int(ts) if isinstance(ts, (int, float)) else 0
            if info is None:
                info = {
                    "condition_id": cid,
                    "slug": row.get("slug"),
                    "title": row.get("title"),
                    "last_user_trade_ts": ts_i,
                }
                markets[cid] = info
            elif ts_i > int(info.get("last_user_trade_ts") or 0):
                info["last_user_trade_ts"] = ts_i
            if not info.get("slug") and row.get("slug"):
                info["slug"] = row.get("slug")
            if not info.get("title") and row.get("title"):
                info["title"] = row.get("title")
        log(f"[user-page] offset={offset} rows={len(rows)} unique_markets={len(markets)}")
        if len(rows) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(SLEEP_S)
    out = sorted(markets.values(), key=lambda x: int(x.get("last_user_trade_ts") or 0), reverse=True)
    log(f"[user] unique_markets={len(out)}")
    return out


def parse_token_ids(market_row: Dict[str, Any]) -> List[str]:
    ids: List[str] = []
    raw = market_row.get("clobTokenIds")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    sid = str(item).strip()
                    if sid:
                        ids.append(sid)
        except json.JSONDecodeError:
            pass
    tokens = market_row.get("tokens")
    if isinstance(tokens, list):
        for token in tokens:
            if not isinstance(token, dict):
                continue
            sid = str(token.get("token_id") or token.get("tokenId") or token.get("id") or "").strip()
            if sid:
                ids.append(sid)
    deduped: List[str] = []
    seen: Set[str] = set()
    for sid in ids:
        if sid not in seen:
            deduped.append(sid)
            seen.add(sid)
    return deduped


def fetch_gamma_market_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    rows = http_get_json(
        f"{GAMMA_API}/markets",
        params={"slug": slug, "limit": 1, "offset": 0},
        retries=RETRIES,
    )
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows[0]
    return None


def infer_market_start_ts(market_row: Dict[str, Any], fallback_ts: int) -> int:
    candidates = [
        parse_ts(market_row.get("createdAt")),
        parse_ts(market_row.get("startDate")),
        parse_ts(market_row.get("startTime")),
        parse_ts(market_row.get("updatedAt")),
    ]
    values = [v for v in candidates if v is not None]
    if values:
        return min(values)
    return fallback_ts


def chunk_ranges(start_ts: int, end_ts: int, chunk_days: int) -> List[List[int]]:
    out: List[List[int]] = []
    step = max(1, chunk_days) * 86400
    cursor = start_ts
    while cursor <= end_ts:
        chunk_end = min(end_ts, cursor + step - 1)
        out.append([cursor, chunk_end])
        cursor = chunk_end + 1
    return out


def normalize_clob_point(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    t = item.get("t")
    p = item.get("p")
    if not isinstance(t, (int, float)):
        return None
    ts_i = int(t)
    return {"t": ts_i, "t_utc": to_utc(ts_i), "p": p, "source": "clob"}


def normalize_trade_point(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ts = item.get("timestamp")
    price = item.get("price")
    asset = item.get("asset")
    if not isinstance(ts, (int, float)):
        return None
    if asset is None:
        return None
    ts_i = int(ts)
    return {"t": ts_i, "t_utc": to_utc(ts_i), "p": price, "asset": str(asset), "source": "trade"}


def fetch_prices_history_chunk(asset_id: str, start_ts: int, end_ts: int, fidelity: int) -> List[Dict[str, Any]]:
    try:
        payload = http_get_json(
            f"{CLOB_API}/prices-history",
            params={
                "market": asset_id,
                "startTs": start_ts,
                "endTs": end_ts,
                "fidelity": fidelity,
            },
            retries=RETRIES,
        )
    except RuntimeError as exc:
        if "HTTP Error 400" in str(exc):
            if end_ts - start_ts <= 3600:
                return []
            mid = start_ts + (end_ts - start_ts) // 2
            left = fetch_prices_history_chunk(asset_id, start_ts, mid, fidelity)
            right = fetch_prices_history_chunk(asset_id, mid + 1, end_ts, fidelity)
            return left + right
        raise
    history = payload.get("history") if isinstance(payload, dict) else None
    if not isinstance(history, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in history:
        if not isinstance(row, dict):
            continue
        norm = normalize_clob_point(row)
        if norm is not None:
            out.append(norm)
    return out


def fetch_market_trade_points(condition_id: str) -> Dict[str, Any]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    offset = 0
    transient_failures = 0
    total_rows = 0
    page_count = 0
    capped = False
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
                if offset > 0:
                    capped = True
                break
            transient_failures += 1
            if transient_failures >= 6:
                raise
            time.sleep(min(10.0, 1.6**transient_failures))
            continue
        if not isinstance(rows, list) or not rows:
            break
        page_count += 1
        total_rows += len(rows)
        for row in rows:
            if not isinstance(row, dict):
                continue
            point = normalize_trade_point(row)
            if point is None:
                continue
            grouped.setdefault(str(point["asset"]), []).append(point)
        if len(rows) < PAGE_LIMIT:
            break
        offset += PAGE_LIMIT
        time.sleep(SLEEP_S)
    return {
        "assets": grouped,
        "rows_total": total_rows,
        "page_count": page_count,
        "capped": capped,
    }


def main() -> None:
    args = parse_args()
    user = args.user.strip()
    if not user:
        raise SystemExit("--user is required")
    start_ts = max(0, int(args.start_ts))
    end_ts = int(time.time()) if int(args.end_ts) <= 0 else int(args.end_ts)
    if end_ts < start_ts:
        raise SystemExit("end-ts must be >= start-ts")

    wallet = resolve_user_wallet(user)
    log(f"[user] input={user} resolved_wallet={wallet}")
    markets = collect_user_markets(wallet)
    if args.market_limit > 0:
        markets = markets[: args.market_limit]
        log(f"[debug] applying market_limit={args.market_limit}")

    user_dir = OUTPUT_ROOT / safe_slug(user)
    markets_dir = user_dir / "markets"
    markets_dir.mkdir(parents=True, exist_ok=True)

    summary: List[Dict[str, Any]] = []
    total_points = 0

    for idx, market in enumerate(markets, start=1):
        slug = str(market.get("slug") or "").strip()
        cid = str(market.get("condition_id") or "")
        if not slug:
            log(f"[skip] {idx}/{len(markets)} cid={cid[:12]}... no slug")
            continue

        gamma_market = fetch_gamma_market_by_slug(slug)
        if not gamma_market:
            log(f"[skip] {idx}/{len(markets)} slug={slug} not found in gamma")
            continue

        token_ids = parse_token_ids(gamma_market)
        if not token_ids:
            log(f"[skip] {idx}/{len(markets)} slug={slug} has no token ids")
            continue

        trade_fetch = fetch_market_trade_points(cid)
        trade_points_by_asset = trade_fetch["assets"]
        market_start_ts = infer_market_start_ts(gamma_market, fallback_ts=start_ts)
        effective_start_ts = max(start_ts, market_start_ts)
        market_ranges = chunk_ranges(effective_start_ts, end_ts, args.chunk_days)

        market_slug = safe_slug(slug)
        market_dir = markets_dir / f"{idx:04d}_{market_slug}"
        market_dir.mkdir(parents=True, exist_ok=True)

        market_points = 0
        token_summaries: List[Dict[str, Any]] = []

        for token_idx, token_id in enumerate(token_ids, start=1):
            clob_out_path = market_dir / f"token_{token_idx}_{token_id[:14]}_clob.jsonl"
            trades_out_path = market_dir / f"token_{token_idx}_{token_id[:14]}_trades.jsonl"

            seen_clob_ts: Set[int] = set()
            clob_points: List[Dict[str, Any]] = []
            clob_raw_points = 0

            for start_i, end_i in market_ranges:
                chunk_rows = fetch_prices_history_chunk(token_id, start_i, end_i, args.fidelity)
                for row in chunk_rows:
                    ts_i = int(row["t"])
                    clob_raw_points += 1
                    if ts_i in seen_clob_ts:
                        continue
                    seen_clob_ts.add(ts_i)
                    clob_points.append(row)
                time.sleep(SLEEP_S)

            clob_points.sort(key=lambda x: int(x["t"]))
            with clob_out_path.open("w", encoding="utf-8") as clob_fp:
                for row in clob_points:
                    clob_fp.write(json.dumps(row, ensure_ascii=False) + "\n")

            trade_points_raw = trade_points_by_asset.get(token_id, [])
            trade_points = [
                row for row in trade_points_raw if effective_start_ts <= int(row["t"]) <= end_ts
            ]
            trade_points = sorted(trade_points, key=lambda x: int(x["t"]))
            with trades_out_path.open("w", encoding="utf-8") as trades_fp:
                for row in trade_points:
                    out_row = {
                        "t": int(row["t"]),
                        "t_utc": row.get("t_utc"),
                        "p": row.get("p"),
                        "source": "trade",
                    }
                    trades_fp.write(json.dumps(out_row, ensure_ascii=False) + "\n")

            clob_min_ts = min((int(row["t"]) for row in clob_points), default=None)
            clob_max_ts = max((int(row["t"]) for row in clob_points), default=None)
            trade_min_ts = min((int(row["t"]) for row in trade_points), default=None)
            trade_max_ts = max((int(row["t"]) for row in trade_points), default=None)

            token_summaries.append(
                {
                    "token_id": token_id,
                    "clob_points_raw": clob_raw_points,
                    "clob_points": len(clob_points),
                    "trade_points_raw": len(trade_points_raw),
                    "trade_points_in_window": len(trade_points),
                    "trade_capped": bool(trade_fetch.get("capped")),
                    "clob_min_ts": clob_min_ts,
                    "clob_max_ts": clob_max_ts,
                    "clob_min_ts_utc": to_utc(clob_min_ts),
                    "clob_max_ts_utc": to_utc(clob_max_ts),
                    "trade_min_ts": trade_min_ts,
                    "trade_max_ts": trade_max_ts,
                    "trade_min_ts_utc": to_utc(trade_min_ts),
                    "trade_max_ts_utc": to_utc(trade_max_ts),
                    "clob_output_file": str(clob_out_path),
                    "trades_output_file": str(trades_out_path),
                }
            )
            market_points += len(clob_points) + len(trade_points)
            log(
                f"[market-token] {idx}/{len(markets)} slug={slug} token={token_idx}/{len(token_ids)} "
                f"clob_points={len(clob_points)} trades_points={len(trade_points)} "
                f"trade_capped={str(bool(trade_fetch.get('capped'))).lower()}"
            )

        manifest = {
            "condition_id": cid,
            "slug": slug,
            "title": market.get("title"),
            "last_user_trade_ts": market.get("last_user_trade_ts"),
            "last_user_trade_ts_utc": to_utc(int(market.get("last_user_trade_ts") or 0))
            if market.get("last_user_trade_ts")
            else None,
            "price_window_start_ts": start_ts,
            "market_effective_start_ts": effective_start_ts,
            "market_effective_start_ts_utc": to_utc(effective_start_ts),
            "price_window_end_ts": end_ts,
            "fidelity": args.fidelity,
            "chunk_days": args.chunk_days,
            "trade_rows_total": trade_fetch.get("rows_total"),
            "trade_page_count": trade_fetch.get("page_count"),
            "trade_capped": bool(trade_fetch.get("capped")),
            "tokens": token_summaries,
            "market_points_total": market_points,
        }
        (market_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        summary.append(manifest)
        total_points += market_points

    top_manifest = {
        "generated_at": int(time.time()),
        "generated_at_utc": to_utc(int(time.time())),
        "user": user,
        "resolved_wallet": wallet,
        "markets_total": len(summary),
        "price_window_start_ts": start_ts,
        "price_window_end_ts": end_ts,
        "fidelity": args.fidelity,
        "chunk_days": args.chunk_days,
        "points_total": total_points,
        "markets": summary,
    }
    (user_dir / "manifest.json").write_text(
        json.dumps(top_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log(
        f"[done] user={user} markets={len(summary)} points_total={total_points} "
        f"out={user_dir / 'manifest.json'}"
    )


if __name__ == "__main__":
    main()
