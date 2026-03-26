#!/usr/bin/env python3
"""Collect independent market history from both CLOB and trades for all markets touched by a user.

Example:
  python3 src/collect_user_market_price_by_clob_and_trades.py \
    --user 0x1ea6aab09d4b9b504fa24f961f0c6709efb72f5d
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
USER_AGENT = "polymarket-research-user-price-history/1.0"
PAGE_LIMIT = 1000
RETRIES = 100
SLEEP_S = 0.02
OUTPUT_ROOT = Path("data/market_price_by_clob_and_trades/by_user")
USER_ACTIVITY_ROOT = Path("data/polymarket/user_activities")
MAX_TRANSIENT_FAILURES = 100
DEFAULT_FIDELITY = 1
DEFAULT_CHUNK_DAYS = 14
MARKET_WORKERS = 8
TRADES_MAX_OFFSET = 3000
FLUSH_EVERY = 200


def log(msg: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    th = threading.current_thread().name
    print(f"[{now}][{th}] {msg}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect independent CLOB history and trades history for markets touched by a user."
    )
    parser.add_argument("--user", required=True, help="Username or wallet address")
    parser.add_argument(
        "--workers",
        type=int,
        default=MARKET_WORKERS,
        help=f"Number of parallel market workers (default: {MARKET_WORKERS})",
    )
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
                payload = json.loads(resp.read().decode("utf-8"))
                if attempt > 0:
                    log(f"[HTTP恢复] url={full_url} 尝试={attempt + 1}/{retries + 1}")
                return payload
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
            sleep_s = min(20.0, 1.6**attempt)
            log(
                f"[HTTP重试] url={full_url} 尝试={attempt + 1}/{retries + 1} "
                f"等待={sleep_s:.2f}s 错误={exc}"
            )
            time.sleep(sleep_s)
    if retries > 0:
        log(f"[HTTP失败] url={full_url} 最后错误={last_err}")
    raise RuntimeError(f"Request failed: {full_url} ({last_err})")


def resolve_user_wallet(user: str) -> str:
    if user.lower().startswith("0x") and len(user) == 42:
        log(f"[钱包] 输入已是钱包地址={user.lower()}")
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
    log(f"[钱包] 用户名解析完成 user={user} wallet={wallet} 候选数={len(counts)}")
    return wallet


def _iter_local_endpoint_rows(user_dir: Path, endpoint: str) -> Iterable[Dict[str, Any]]:
    endpoint_dir = user_dir / "endpoints" / endpoint
    if not endpoint_dir.exists() or not endpoint_dir.is_dir():
        return
    files = sorted(endpoint_dir.glob("*.json"))
    for idx, path in enumerate(files, start=1):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for row in payload:
            if isinstance(row, dict):
                yield row
        if idx % 200 == 0:
            log(f"[本地扫描] 端点={endpoint} 文件进度={idx}/{len(files)}")


def iter_user_markets_from_local(user_wallet: str) -> Iterable[Dict[str, Any]]:
    user_dir = USER_ACTIVITY_ROOT / user_wallet
    if not user_dir.exists() or not user_dir.is_dir():
        raise SystemExit(f"Local user activity dir not found: {user_dir}")

    markets: Dict[str, Dict[str, Any]] = {}
    scheduled: Set[str] = set()
    seen_rows = 0
    for endpoint in ("activity", "trades"):
        endpoint_rows = 0
        for row in _iter_local_endpoint_rows(user_dir, endpoint):
            endpoint_rows += 1
            seen_rows += 1
            cid = str(row.get("conditionId") or "").strip().lower()
            if not cid:
                continue
            info = markets.get(cid)
            ts = parse_ts(row.get("timestamp")) or 0
            if info is None:
                info = {
                    "condition_id": cid,
                    "slug": str(row.get("eventSlug") or row.get("slug") or "").strip().lower(),
                    "title": row.get("title"),
                    "last_user_trade_ts": ts,
                    "last_trade_ts_local": 0,
                }
                markets[cid] = info
            elif ts > int(info.get("last_user_trade_ts") or 0):
                info["last_user_trade_ts"] = ts

            if not info.get("slug"):
                s = str(row.get("eventSlug") or row.get("slug") or "").strip().lower()
                if s:
                    info["slug"] = s
            if not info.get("title") and row.get("title"):
                info["title"] = row.get("title")
            event_type = str(row.get("type") or "").strip().upper()
            if event_type == "TRADE" and ts > int(info.get("last_trade_ts_local") or 0):
                info["last_trade_ts_local"] = ts
            if cid not in scheduled and info.get("slug"):
                scheduled.add(cid)
                yield dict(info)
        log(f"[本地扫描] 端点={endpoint} 行数={endpoint_rows} 唯一市场={len(markets)}")
    log(
        f"[用户] 来源=local_activities 扫描行数={seen_rows} "
        f"唯一市场={len(markets)} 已提交市场={len(scheduled)}"
    )


def _load_existing_market_manifest_index(markets_dir: Path) -> Dict[str, Tuple[Dict[str, Any], Path]]:
    index: Dict[str, Tuple[Dict[str, Any], Path]] = {}
    if not markets_dir.exists() or not markets_dir.is_dir():
        return index
    for market_dir in sorted(p for p in markets_dir.iterdir() if p.is_dir()):
        manifest_path = market_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        cid = str(payload.get("condition_id") or "").strip().lower()
        slug = str(payload.get("slug") or "").strip().lower()
        if cid:
            index[f"cid:{cid}"] = (payload, market_dir)
        if slug:
            index[f"slug:{slug}"] = (payload, market_dir)
    return index


def _existing_market_complete(existing_manifest: Dict[str, Any], market_dir: Path) -> bool:
    tokens = existing_manifest.get("tokens")
    if not isinstance(tokens, list) or not tokens:
        return False
    for token in tokens:
        if not isinstance(token, dict):
            return False
        clob_file = token.get("clob_output_file")
        trade_file = token.get("trades_output_file")
        if not isinstance(clob_file, str) or not isinstance(trade_file, str):
            return False
        clob_path = Path(clob_file)
        trade_path = Path(trade_file)
        if not clob_path.is_absolute():
            clob_path = Path.cwd() / clob_path
        if not trade_path.is_absolute():
            trade_path = Path.cwd() / trade_path
        if not clob_path.exists() or not trade_path.exists():
            # Backward-compatible fallback: old manifests may store stale relative paths.
            fallback_clob = market_dir / Path(clob_file).name
            fallback_trade = market_dir / Path(trade_file).name
            if not fallback_clob.exists() or not fallback_trade.exists():
                return False
    return True


def _fetch_latest_market_trade_ts(condition_id: str) -> Optional[int]:
    log(f"[远端成交时间探测-开始] condition={condition_id[:14]}...")
    try:
        rows = http_get_json(
            f"{DATA_API}/trades",
            params={"market": condition_id, "limit": 50, "offset": 0},
            retries=RETRIES,
        )
    except RuntimeError:
        return None
    if not isinstance(rows, list):
        log(f"[远端成交时间探测-空] condition={condition_id[:14]}... 原因=非列表")
        return None
    latest = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        ts = parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        latest = ts if latest is None else max(latest, ts)
    log(f"[远端成交时间探测-完成] condition={condition_id[:14]}... latest={latest}")
    return latest


def _clob_has_update_since(asset_id: str, known_max_ts: Optional[int], end_ts: int) -> Optional[bool]:
    if known_max_ts is None:
        log(f"[CLOB探测-跳过] asset={asset_id[:14]}... known_max_ts=None")
        return None
    start_ts = int(known_max_ts) + 1
    if start_ts > end_ts:
        return False
    try:
        log(
            f"[CLOB探测-开始] asset={asset_id[:14]}... start={start_ts} end={end_ts}"
        )
        payload = http_get_json(
            f"{CLOB_API}/prices-history",
            params={"market": asset_id, "startTs": start_ts, "endTs": end_ts, "fidelity": 1},
            retries=0,
        )
    except RuntimeError as exc:
        if "HTTP Error 400" in str(exc):
            # Probe a short tail window if full range is rejected.
            short_start = max(start_ts, end_ts - 86400)
            try:
                log(
                    f"[CLOB探测-回退短窗] asset={asset_id[:14]}... start={short_start} end={end_ts}"
                )
                payload = http_get_json(
                    f"{CLOB_API}/prices-history",
                    params={"market": asset_id, "startTs": short_start, "endTs": end_ts, "fidelity": 1},
                    retries=0,
                )
            except RuntimeError:
                return None
        else:
            return None
    history = payload.get("history") if isinstance(payload, dict) else None
    has = bool(history) if isinstance(history, list) else False
    log(f"[CLOB探测-完成] asset={asset_id[:14]}... 有更新={has}")
    return has


def _needs_refresh_from_remote(
    condition_id: str,
    existing_manifest: Dict[str, Any],
    end_ts: int,
) -> Tuple[bool, str]:
    known_trade_max = parse_ts(existing_manifest.get("trade_max_ts"))
    if known_trade_max is None:
        tokens = existing_manifest.get("tokens")
        if isinstance(tokens, list):
            vals: List[int] = []
            for tok in tokens:
                if not isinstance(tok, dict):
                    continue
                v = parse_ts(tok.get("trade_max_ts"))
                if v is not None:
                    vals.append(v)
            if vals:
                known_trade_max = max(vals)
    latest_trade_ts = _fetch_latest_market_trade_ts(condition_id)
    if latest_trade_ts is not None and (known_trade_max is None or latest_trade_ts > known_trade_max):
        return True, "remote_trades_updated"

    tokens = existing_manifest.get("tokens")
    if not isinstance(tokens, list):
        return False, "remote_no_update"
    for tok in tokens:
        if not isinstance(tok, dict):
            continue
        token_id = str(tok.get("token_id") or "").strip()
        if not token_id:
            continue
        known_clob_max = parse_ts(tok.get("clob_max_ts"))
        has_update = _clob_has_update_since(token_id, known_clob_max, end_ts)
        if has_update is None:
            # Conservative: if remote probe failed, rebuild to avoid stale data.
            return True, "remote_probe_failed"
        if has_update:
            return True, "remote_clob_updated"
    return False, "remote_no_update"


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
    log(
        f"[Token列表] market_id={market_row.get('id')} condition={market_row.get('conditionId')} "
        f"token数={len(deduped)}"
    )
    return deduped


def fetch_gamma_market_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    log(f"[Gamma按Slug查询-开始] slug={slug}")
    rows = http_get_json(
        f"{GAMMA_API}/markets",
        params={"slug": slug},
        retries=RETRIES,
    )
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        log(f"[Gamma按Slug查询-命中] slug={slug} market_id={rows[0].get('id')}")
        return rows[0]
    log(f"[Gamma按Slug查询-未命中] slug={slug}")
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


def _stream_prices_history_window(
    asset_id: str,
    start_ts: int,
    end_ts: int,
    fidelity: int,
    on_point,
) -> int:
    """Fetch CLOB prices with recursive range split and stream rows via callback."""
    transient_failures = 0
    while True:
        try:
            payload = http_get_json(
                f"{CLOB_API}/prices-history",
                params={
                    "market": asset_id,
                    "startTs": start_ts,
                    "endTs": end_ts,
                    "fidelity": fidelity,
                },
                retries=0,
            )
            break
        except RuntimeError as exc:
            text = str(exc)
            log(
                f"[CLOB窗口错误] asset={asset_id[:14]}... start={start_ts} end={end_ts} err={exc}"
            )
            if "HTTP Error 400" in text:
                if end_ts - start_ts <= 3600:
                    log(
                        f"[CLOB窗口停止400] asset={asset_id[:14]}... window={end_ts - start_ts}s"
                    )
                    return 0
                mid = start_ts + (end_ts - start_ts) // 2
                log(
                    f"[CLOB窗口二分] asset={asset_id[:14]}... mid={mid} left=({start_ts},{mid}) right=({mid+1},{end_ts})"
                )
                left = _stream_prices_history_window(asset_id, start_ts, mid, fidelity, on_point)
                right = _stream_prices_history_window(asset_id, mid + 1, end_ts, fidelity, on_point)
                return left + right
            transient_failures += 1
            if transient_failures >= MAX_TRANSIENT_FAILURES:
                log(
                    "[CLOB失败] "
                    f"asset={asset_id[:14]} start={start_ts} end={end_ts} err={exc} "
                    "放弃该区间=true"
                )
                return 0
            sleep_s = min(20.0, 1.6**transient_failures)
            log(
                "[CLOB重试] "
                f"asset={asset_id[:14]} start={start_ts} end={end_ts} "
                f"attempt={transient_failures}/{MAX_TRANSIENT_FAILURES} sleep={sleep_s:.2f}s"
            )
            time.sleep(sleep_s)
    history = payload.get("history") if isinstance(payload, dict) else None
    if not isinstance(history, list):
        return 0
    wrote = 0
    for row in history:
        if not isinstance(row, dict):
            continue
        norm = normalize_clob_point(row)
        if norm is None:
            continue
        on_point(norm)
        wrote += 1
    return wrote


def stream_prices_history_range(
    asset_id: str,
    start_ts: int,
    end_ts: int,
    fidelity: int,
    chunk_days: int,
    on_point,
) -> int:
    """Fetch CLOB prices by forward time windows; split only failed windows."""
    if end_ts < start_ts:
        return 0
    step = max(1, chunk_days) * 86400
    cursor = start_ts
    total = 0
    while cursor <= end_ts:
        window_end = min(end_ts, cursor + step - 1)
        log(
            f"[CLOB前向窗口] asset={asset_id[:14]}... cursor={cursor} window_end={window_end} step_days={max(1, chunk_days)}"
        )
        total += _stream_prices_history_window(
            asset_id=asset_id,
            start_ts=cursor,
            end_ts=window_end,
            fidelity=fidelity,
            on_point=on_point,
        )
        cursor = window_end + 1
    return total


def stream_market_trade_points_to_files(
    condition_id: str,
    tracked_token_ids: Set[str],
    token_trade_paths: Dict[str, Path],
    token_existing_trade_max_ts: Dict[str, Optional[int]],
    append_mode: bool,
) -> Dict[str, Any]:
    token_stats: Dict[str, Dict[str, Optional[int]]] = {
        token_id: {
            "trade_points_raw": 0,
            "trade_points_in_window": 0,
            "trade_min_ts": None,
            "trade_max_ts": None,
        }
        for token_id in tracked_token_ids
    }
    fps: Dict[str, Any] = {}
    for token_id, out_path in token_trade_paths.items():
        fps[token_id] = out_path.open("a" if append_mode else "w", encoding="utf-8", buffering=1)

    offset = 0
    transient_failures = 0
    total_rows = 0
    page_count = 0
    capped = False
    log(f"[Trades抓取-开始] condition={condition_id[:14]}...")
    try:
        while True:
            if offset > TRADES_MAX_OFFSET:
                capped = True
                log(
                    f"[Trades停止-偏移上限] condition={condition_id[:14]}... "
                    f"offset={offset} 上限={TRADES_MAX_OFFSET}"
                )
                break
            try:
                rows = http_get_json(
                    f"{DATA_API}/trades",
                    params={
                        "market": condition_id,
                        "limit": PAGE_LIMIT,
                        "offset": offset,
                        "takerOnly": "false",
                    },
                    retries=0,
                )
                transient_failures = 0
            except RuntimeError as exc:
                if "HTTP Error 400" in str(exc) and offset > 0:
                    # Pagination reached API cap / tail boundary.
                    capped = True
                    break
                transient_failures += 1
                if transient_failures >= MAX_TRANSIENT_FAILURES:
                    log(
                        "[Trades失败] "
                        f"condition={condition_id[:14]} offset={offset} err={exc} "
                        "放弃并保留部分结果=true"
                    )
                    break
                sleep_s = min(20.0, 1.6**transient_failures)
                log(
                    "[Trades重试] "
                    f"condition={condition_id[:14]} offset={offset} "
                    f"attempt={transient_failures}/{MAX_TRANSIENT_FAILURES} sleep={sleep_s:.2f}s"
                )
                time.sleep(sleep_s)
                continue
            if not isinstance(rows, list) or not rows:
                log(
                    f"[Trades停止-空页] condition={condition_id[:14]}... offset={offset}"
                )
                break
            page_count += 1
            total_rows += len(rows)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                point = normalize_trade_point(row)
                if point is None:
                    continue
                token_id = str(point["asset"])
                if token_id not in tracked_token_ids:
                    continue
                stats = token_stats[token_id]
                stats["trade_points_raw"] = int(stats["trade_points_raw"] or 0) + 1
                ts_i = int(point["t"])
                known_max = token_existing_trade_max_ts.get(token_id)
                if known_max is not None and ts_i <= int(known_max):
                    continue
                if ts_i > 0:
                    out_row = {
                        "t": ts_i,
                        "t_utc": point.get("t_utc"),
                        "p": point.get("p"),
                        "source": "trade",
                    }
                    fps[token_id].write(json.dumps(out_row, ensure_ascii=False) + "\n")
                    stats["trade_points_in_window"] = int(stats["trade_points_in_window"] or 0) + 1
                    if int(stats["trade_points_in_window"]) % FLUSH_EVERY == 0:
                        fps[token_id].flush()
                    tmin = stats["trade_min_ts"]
                    tmax = stats["trade_max_ts"]
                    stats["trade_min_ts"] = ts_i if tmin is None else min(int(tmin), ts_i)
                    stats["trade_max_ts"] = ts_i if tmax is None else max(int(tmax), ts_i)
            if page_count == 1 or page_count % 5 == 0:
                log(
                    f"[Trades分页] condition={condition_id[:14]}... page={page_count} "
                    f"rows={len(rows)} total_rows={total_rows} tracked_assets={len(tracked_token_ids)}"
                )
            if len(rows) < PAGE_LIMIT:
                log(
                    f"[Trades停止-短页] condition={condition_id[:14]}... rows={len(rows)}"
                )
                break
            offset += PAGE_LIMIT
            time.sleep(SLEEP_S)
        log(
            f"[Trades抓取-完成] condition={condition_id[:14]}... pages={page_count} "
            f"rows_total={total_rows} tracked_assets={len(tracked_token_ids)} capped={str(capped).lower()}"
        )
    finally:
        for fp in fps.values():
            fp.close()
    return {
        "token_stats": token_stats,
        "rows_total": total_rows,
        "page_count": page_count,
        "capped": capped,
    }


def process_single_market(
    idx: int,
    total_markets: int,
    market: Dict[str, Any],
    existing_index: Dict[str, Tuple[Dict[str, Any], Path]],
    markets_dir: Path,
    start_ts: int,
    end_ts: int,
    fidelity: int,
    chunk_days: int,
) -> Tuple[int, Optional[Dict[str, Any]], int]:
    progress = f"{idx}/{total_markets}" if total_markets > 0 else f"{idx}/streaming"
    log(f"[市场开始] idx={progress}")
    slug = str(market.get("slug") or "").strip()
    cid = str(market.get("condition_id") or "")
    cid_key = f"cid:{cid.lower()}" if cid else ""
    slug_key = f"slug:{slug.lower()}" if slug else ""
    existing = existing_index.get(cid_key) or existing_index.get(slug_key)
    existing_manifest: Optional[Dict[str, Any]] = None
    existing_dir: Optional[Path] = None
    append_mode = False
    if existing is not None:
        existing_manifest, existing_dir = existing
        if _existing_market_complete(existing_manifest, existing_dir):
            should_refresh, refresh_reason = _needs_refresh_from_remote(
                cid.lower(),
                existing_manifest,
                end_ts=end_ts,
            )
            if should_refresh:
                log(
                    f"[增量刷新] {progress} "
                    f"slug={slug or existing_manifest.get('slug') or 'unknown'} "
                    f"cid={cid[:12]}... reason={refresh_reason}"
                )
                append_mode = True
            else:
                log(
                    f"[跳过已有] {progress} "
                    f"slug={slug or existing_manifest.get('slug') or 'unknown'} "
                    f"cid={cid[:12]}..."
                )
                return idx, existing_manifest, int(existing_manifest.get("market_points_total") or 0)
    if not slug:
        log(f"[跳过] {progress} cid={cid[:12]}... 缺少slug")
        return idx, None, 0

    gamma_market: Optional[Dict[str, Any]] = None

    # Fast path: resolve by slug first (usually available from local rows), avoid global CID scan.
    if slug:
        gamma_market = fetch_gamma_market_by_slug(slug)
    if gamma_market and cid:
        fetched_cid = str(gamma_market.get("conditionId") or "").strip().lower()
        if fetched_cid != cid.lower():
            log(
                f"[Slug与CID不一致] {progress} slug={slug} local_cid={cid[:12]}... "
                f"gamma_cid={fetched_cid[:12]}..."
            )
            gamma_market = None

    if not gamma_market:
        log(f"[跳过] {progress} slug={slug} 在gamma中不存在")
        return idx, None, 0

    token_ids = parse_token_ids(gamma_market)
    if not token_ids:
        log(f"[跳过] {progress} slug={slug} 没有token ids")
        return idx, None, 0

    market_start_ts = infer_market_start_ts(gamma_market, fallback_ts=start_ts)
    effective_start_ts = max(start_ts, market_start_ts)
    log(
        f"[市场时间范围] idx={progress} slug={slug} "
        f"effective_start={effective_start_ts} end={end_ts} chunks=adaptive_split"
    )

    market_slug = safe_slug(slug)
    market_dir = markets_dir / f"{idx:04d}_{market_slug}"
    market_dir.mkdir(parents=True, exist_ok=True)

    market_points = 0
    token_summaries: List[Dict[str, Any]] = []
    token_trade_paths: Dict[str, Path] = {}
    existing_token_by_id: Dict[str, Dict[str, Any]] = {}
    if isinstance(existing_manifest, dict):
        tokens = existing_manifest.get("tokens")
        if isinstance(tokens, list):
            for tok in tokens:
                if not isinstance(tok, dict):
                    continue
                tid = str(tok.get("token_id") or "").strip()
                if tid:
                    existing_token_by_id[tid] = tok
    token_existing_trade_max_ts: Dict[str, Optional[int]] = {}
    token_existing_clob_max_ts: Dict[str, Optional[int]] = {}
    for token_idx, token_id in enumerate(token_ids, start=1):
        fallback_trade = market_dir / f"token_{token_idx}_{token_id[:14]}_trades.jsonl"
        fallback_clob = market_dir / f"token_{token_idx}_{token_id[:14]}_clob.jsonl"
        tok = existing_token_by_id.get(token_id, {})
        tpath_raw = tok.get("trades_output_file")
        cpath_raw = tok.get("clob_output_file")
        tpath = Path(tpath_raw) if isinstance(tpath_raw, str) else fallback_trade
        cpath = Path(cpath_raw) if isinstance(cpath_raw, str) else fallback_clob
        if not tpath.is_absolute():
            tpath = Path.cwd() / tpath
        if not cpath.is_absolute():
            cpath = Path.cwd() / cpath
        token_trade_paths[token_id] = tpath
        token_existing_trade_max_ts[token_id] = parse_ts(tok.get("trade_max_ts"))
        token_existing_clob_max_ts[token_id] = parse_ts(tok.get("clob_max_ts"))
        # Ensure legacy relative paths still land in current market dir when missing.
        if append_mode and not tpath.exists():
            token_trade_paths[token_id] = fallback_trade
        if append_mode and not cpath.exists():
            cpath = fallback_clob
        tok["_resolved_clob_path"] = str(cpath)
        tok["_resolved_trade_path"] = str(token_trade_paths[token_id])

    trade_fetch = stream_market_trade_points_to_files(
        cid,
        tracked_token_ids=set(token_ids),
        token_trade_paths=token_trade_paths,
        token_existing_trade_max_ts=token_existing_trade_max_ts,
        append_mode=append_mode,
    )
    trade_stats_by_token: Dict[str, Dict[str, Optional[int]]] = trade_fetch["token_stats"]

    for token_idx, token_id in enumerate(token_ids, start=1):
        log(
            f"[市场Token开始] {progress} slug={slug} "
            f"token={token_idx}/{len(token_ids)} chunks=adaptive_split fidelity={fidelity}"
        )
        tok_existing = existing_token_by_id.get(token_id, {})
        resolved_clob = tok_existing.get("_resolved_clob_path")
        clob_out_path = Path(resolved_clob) if isinstance(resolved_clob, str) else (
            market_dir / f"token_{token_idx}_{token_id[:14]}_clob.jsonl"
        )
        trades_out_path = token_trade_paths[token_id]

        seen_clob_ts: Set[int] = set()
        written_clob_ts: Set[int] = set()
        clob_raw_points = 0
        clob_points = 0
        clob_open_mode = "a" if append_mode else "w"
        with clob_out_path.open(clob_open_mode, encoding="utf-8", buffering=1) as clob_fp:
            def _on_clob_point(row: Dict[str, Any]) -> None:
                nonlocal clob_raw_points, clob_points
                ts_i = int(row["t"])
                clob_raw_points += 1
                if ts_i in seen_clob_ts:
                    return
                seen_clob_ts.add(ts_i)
                known_max = token_existing_clob_max_ts.get(token_id)
                if known_max is not None and ts_i <= int(known_max):
                    return
                if ts_i >= effective_start_ts:
                    clob_fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                    clob_points += 1
                    if clob_points % FLUSH_EVERY == 0:
                        clob_fp.flush()
                    written_clob_ts.add(ts_i)

            clob_start = effective_start_ts
            known_clob_max = token_existing_clob_max_ts.get(token_id)
            if known_clob_max is not None:
                clob_start = max(clob_start, int(known_clob_max) + 1)
            stream_prices_history_range(
                token_id,
                clob_start,
                end_ts,
                fidelity,
                chunk_days,
                _on_clob_point,
            )
            log(
                f"[市场Token进度] {progress} slug={slug} "
                f"token={token_idx}/{len(token_ids)} mode=adaptive_split clob_points={clob_points}"
            )

        clob_min_ts = min(written_clob_ts) if written_clob_ts else None
        clob_max_ts = max(written_clob_ts) if written_clob_ts else None
        token_trade_stats = trade_stats_by_token.get(token_id, {})
        trade_points_raw = int(token_trade_stats.get("trade_points_raw") or 0)
        trade_points = int(token_trade_stats.get("trade_points_in_window") or 0)
        trade_min_ts_new = parse_ts(token_trade_stats.get("trade_min_ts"))
        trade_max_ts_new = parse_ts(token_trade_stats.get("trade_max_ts"))
        prev_trade_min = parse_ts(tok_existing.get("trade_min_ts"))
        prev_trade_max = parse_ts(tok_existing.get("trade_max_ts"))
        trade_min_ts = min(v for v in [prev_trade_min, trade_min_ts_new] if v is not None) if (
            prev_trade_min is not None or trade_min_ts_new is not None
        ) else None
        trade_max_ts = max(v for v in [prev_trade_max, trade_max_ts_new] if v is not None) if (
            prev_trade_max is not None or trade_max_ts_new is not None
        ) else None
        prev_clob_min = parse_ts(tok_existing.get("clob_min_ts"))
        prev_clob_max = parse_ts(tok_existing.get("clob_max_ts"))
        clob_min_ts = min(v for v in [prev_clob_min, clob_min_ts] if v is not None) if (
            prev_clob_min is not None or clob_min_ts is not None
        ) else None
        clob_max_ts = max(v for v in [prev_clob_max, clob_max_ts] if v is not None) if (
            prev_clob_max is not None or clob_max_ts is not None
        ) else None
        prev_clob_points = int(tok_existing.get("clob_points") or 0)
        prev_clob_points_raw = int(tok_existing.get("clob_points_raw") or 0)
        prev_trade_points_raw = int(tok_existing.get("trade_points_raw") or 0)
        prev_trade_points_window = int(tok_existing.get("trade_points_in_window") or 0)

        token_summaries.append(
            {
                "token_id": token_id,
                "clob_points_raw": prev_clob_points_raw + clob_raw_points,
                "clob_points": prev_clob_points + clob_points,
                "trade_points_raw": prev_trade_points_raw + trade_points_raw,
                "trade_points_in_window": prev_trade_points_window + trade_points,
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
        market_points += (prev_clob_points + clob_points) + (prev_trade_points_window + trade_points)
        log(
            f"[市场Token汇总] {progress} slug={slug} token={token_idx}/{len(token_ids)} "
            f"clob_points={clob_points} trades_points={trade_points} "
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
        "fidelity": fidelity,
        "chunk_days": chunk_days,
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
    log(
        f"[市场完成] idx={progress} slug={slug} "
        f"tokens={len(token_summaries)} market_points={market_points}"
    )
    return idx, manifest, market_points


def write_top_manifest(
    out_path: Path,
    *,
    user: str,
    wallet: str,
    start_ts: int,
    end_ts: int,
    fidelity: int,
    chunk_days: int,
    collected: List[Tuple[int, Dict[str, Any], int]],
    submitted: int,
    completed: int,
    status: str,
) -> None:
    now_ts = int(time.time())
    ordered = sorted(collected, key=lambda x: x[0])
    summary: List[Dict[str, Any]] = [manifest for _, manifest, _ in ordered]
    total_points = sum(points for _, _, points in ordered)
    payload = {
        "generated_at": now_ts,
        "generated_at_utc": to_utc(now_ts),
        "run_status": status,
        "user": user,
        "resolved_wallet": wallet,
        "submitted_markets": submitted,
        "completed_markets": completed,
        "markets_total": len(summary),
        "price_window_start_ts": start_ts,
        "price_window_end_ts": end_ts,
        "fidelity": fidelity,
        "chunk_days": chunk_days,
        "points_total": total_points,
        "markets": summary,
    }
    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(out_path)


def main() -> None:
    args = parse_args()
    user = args.user.strip()
    if not user:
        raise SystemExit("--user is required")
    workers = int(args.workers)
    if workers <= 0:
        raise SystemExit("--workers must be >= 1")
    start_ts = 0
    end_ts = int(time.time())
    fidelity = DEFAULT_FIDELITY
    chunk_days = DEFAULT_CHUNK_DAYS
    if end_ts < start_ts:
        raise SystemExit("end-ts must be >= start-ts")
    log(
        f"[配置] user={user} start_ts={start_ts} end_ts={end_ts} "
        f"fidelity={fidelity} chunk_days={chunk_days} workers={workers} "
        f"retries={RETRIES} max_transient_failures={MAX_TRANSIENT_FAILURES}"
    )

    wallet = resolve_user_wallet(user)
    log(f"[用户] input={user} resolved_wallet={wallet}")

    user_dir = OUTPUT_ROOT / safe_slug(user)
    markets_dir = user_dir / "markets"
    markets_dir.mkdir(parents=True, exist_ok=True)
    top_manifest_path = user_dir / "manifest.json"
    existing_index = _load_existing_market_manifest_index(markets_dir)

    collected: List[Tuple[int, Dict[str, Any], int]] = []
    submitted = 0
    completed_tasks = 0
    max_in_flight = max(workers, workers * 4)
    write_top_manifest(
        top_manifest_path,
        user=user,
        wallet=wallet,
        start_ts=start_ts,
        end_ts=end_ts,
        fidelity=fidelity,
        chunk_days=chunk_days,
        collected=collected,
        submitted=submitted,
        completed=completed_tasks,
        status="running",
    )
    log(f"[执行器启动] markets=streaming workers={workers}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        market_iter = iter(iter_user_markets_from_local(wallet))
        in_flight: Set[concurrent.futures.Future[Tuple[int, Optional[Dict[str, Any]], int]]] = set()
        feed_exhausted = False

        def _submit_one(market_row: Dict[str, Any]) -> None:
            nonlocal submitted
            submitted += 1
            fut = executor.submit(
                process_single_market,
                submitted,
                0,
                market_row,
                existing_index,
                markets_dir,
                start_ts,
                end_ts,
                fidelity,
                chunk_days,
            )
            in_flight.add(fut)
            if submitted == 1 or submitted % 200 == 0:
                log(
                    f"[执行器提交] submitted={submitted} workers={workers} "
                    f"in_flight={len(in_flight)}/{max_in_flight}"
                )

        while len(in_flight) < max_in_flight and not feed_exhausted:
            try:
                _submit_one(next(market_iter))
            except StopIteration:
                feed_exhausted = True
        if feed_exhausted:
            log(f"[执行器提交完成] submitted={submitted}")

        while in_flight:
            done, in_flight = concurrent.futures.wait(
                in_flight, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for fut in done:
                idx, manifest, market_points = fut.result()
                completed_tasks += 1
                if manifest is not None:
                    collected.append((idx, manifest, market_points))
                log(
                    f"[执行器进度] completed={completed_tasks}/{submitted} "
                    f"last_idx={idx} has_manifest={str(manifest is not None).lower()} "
                    f"market_points={market_points}"
                )
                write_top_manifest(
                    top_manifest_path,
                    user=user,
                    wallet=wallet,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    fidelity=fidelity,
                    chunk_days=chunk_days,
                    collected=collected,
                    submitted=submitted,
                    completed=completed_tasks,
                    status="running",
                )

            while len(in_flight) < max_in_flight and not feed_exhausted:
                try:
                    _submit_one(next(market_iter))
                except StopIteration:
                    feed_exhausted = True
                    log(f"[执行器提交完成] submitted={submitted}")
                    break

    write_top_manifest(
        top_manifest_path,
        user=user,
        wallet=wallet,
        start_ts=start_ts,
        end_ts=end_ts,
        fidelity=fidelity,
        chunk_days=chunk_days,
        collected=collected,
        submitted=submitted,
        completed=completed_tasks,
        status="done",
    )
    total_points = sum(points for _, _, points in collected)
    log(
        f"[完成] user={user} markets={len(collected)} points_total={total_points} "
        f"out={top_manifest_path}"
    )


if __name__ == "__main__":
    main()
