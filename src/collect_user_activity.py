#!/usr/bin/env python3
"""Collect Polymarket user activity via official public data endpoints.

Example:
  python src/collect_user_activity.py --users \
    0x2005d16a84ceefa912d4e380cd32e7ff827875ea \
    0xf0729143cbf9ade46743017ec4e1832a3564cee7 \
    0x1ea6aab09d4b9b504fa24f961f0c6709efb72f5d
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

DATA_API = "https://data-api.polymarket.com"
DEFAULT_OUTPUT_DIR = "data/polymarket/user_activities"

ENDPOINT_MAX_LIMITS = {
    "positions": 500,
    "closed_positions": 50,
    "activity": 500,
    "trades": 500,
}


def log(message: str) -> None:
    print(message, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Polymarket user activity using official public endpoints."
    )
    parser.add_argument("--users", nargs="+", required=True, help="User wallet addresses")
    parser.add_argument(
        "--sleep", type=float, default=0.1, help="Sleep seconds between requests"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress printing",
    )
    parser.add_argument(
        "--recent",
        nargs="?",
        type=int,
        const=24,
        default=None,
        metavar="HOURS",
        help="Fetch only recent data for all endpoints; optionally set hours (e.g. --recent 48)",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Output root directory for per-user activity bundles",
    )
    return parser.parse_args()


def validate_users(users: List[str]) -> List[str]:
    invalid = [u for u in users if not ADDRESS_RE.match(u)]
    if invalid:
        raise SystemExit(f"Invalid user address(es): {invalid}")
    return users


def http_get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retries: Optional[int] = None,
    retry_backoff: float = 1.5,
) -> Any:
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "polymarket-research/1.0"})
    last_err: Optional[Exception] = None
    attempt = 0
    while True:
        try:
            if attempt > 0:
                log(f"[retry] attempt={attempt} url={url}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ConnectionResetError,
            OSError,
        ) as exc:
            last_err = exc
            log(f"[error] attempt={attempt} url={url} err={exc}")
            if retries is not None and attempt >= retries:
                break
            sleep_s = retry_backoff ** attempt
            log(f"[backoff] sleep={sleep_s:.2f}s url={url}")
            time.sleep(sleep_s)
            attempt += 1
    raise RuntimeError(
        f"Request failed after {attempt + 1} attempts: {url} ({last_err})"
    )


def safe_get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retries: Optional[int] = None,
    retry_backoff: float = 1.5,
) -> Any:
    try:
        return http_get_json(url, params, retries=retries, retry_backoff=retry_backoff)
    except urllib.error.HTTPError as exc:
        log(f"[http_error] url={exc.geturl()} status={exc.code}")
        return {"_error": f"HTTP {exc.code}", "_url": exc.geturl()}
    except Exception as exc:  # noqa: BLE001
        log(f"[exception] url={url} err={exc}")
        return {"_error": str(exc), "_url": url}


def infer_latest_time(rows: List[Any]) -> Optional[str]:
    for key in ("timestamp", "createdAt", "created_at", "event_time"):
        for row in reversed(rows):
            if isinstance(row, dict) and row.get(key):
                return str(row.get(key))
    return None


def extract_min_max_ts(rows: List[Any]) -> Tuple[Optional[int], Optional[int]]:
    min_ts: Optional[int] = None
    max_ts: Optional[int] = None
    for row in rows:
        ts = row_timestamp(row)
        if ts is not None:
            min_ts = ts if min_ts is None else min(min_ts, ts)
            max_ts = ts if max_ts is None else max(max_ts, ts)
    return min_ts, max_ts


def normalize_unix_ts(raw_ts: int) -> int:
    # Normalize milliseconds/microseconds to seconds.
    if raw_ts > 10_000_000_000_000:
        return raw_ts // 1_000_000
    if raw_ts > 10_000_000_000:
        return raw_ts // 1_000
    return raw_ts


def parse_time_value(value: Any) -> Optional[int]:
    if isinstance(value, (int, float)):
        return normalize_unix_ts(int(value))
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.isdigit():
            return normalize_unix_ts(int(s))
        try:
            iso = s.replace("Z", "+00:00")
            return int(datetime.fromisoformat(iso).timestamp())
        except ValueError:
            return None
    return None


def row_timestamp(row: Any) -> Optional[int]:
    if not isinstance(row, dict):
        return None
    for key in ("timestamp", "createdAt", "created_at", "event_time", "resolvedAt"):
        ts = parse_time_value(row.get(key))
        if ts is not None:
            return ts
    return None


def filter_rows_by_ts_window(
    rows: Any,
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> Any:
    if not isinstance(rows, list):
        return rows
    if start_ts is None and end_ts is None:
        return rows
    filtered: List[Any] = []
    for row in rows:
        ts = row_timestamp(row)
        if ts is None:
            # Some endpoints may not expose a timestamp field on every row.
            # Keep such rows; otherwise recent mode may drop all data unexpectedly.
            filtered.append(row)
            continue
        if start_ts is not None and ts < start_ts:
            continue
        if end_ts is not None and ts > end_ts:
            continue
        filtered.append(row)
    return filtered


def write_page_json(out_dir: str, endpoint: str, page_index: int, rows: Any) -> str:
    os.makedirs(out_dir, exist_ok=True)
    filename = f"{endpoint}_page_{page_index:06d}.json"
    path = os.path.join(out_dir, filename)
    write_json(path, rows)
    return path


def stable_rows_fingerprint(rows: Any) -> Optional[str]:
    if not isinstance(rows, list):
        return None
    try:
        payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def next_page_index(out_dir: str, prefix: str) -> int:
    if not out_dir or not os.path.exists(out_dir):
        return 0
    max_index = -1
    for name in os.listdir(out_dir):
        if not name.startswith(f"{prefix}_page_") or not name.endswith(".json"):
            continue
        parts = name.split("_page_")
        if len(parts) != 2:
            continue
        num_part = parts[1].split(".json")[0]
        if num_part.isdigit():
            max_index = max(max_index, int(num_part))
    return max_index + 1


def paginated_fetch_stream(
    base_url: str,
    params: Dict[str, Any],
    limit: Optional[int],
    sleep_s: float,
    retries: Optional[int],
    retry_backoff: float,
    progress_label: str,
    progress: bool,
    out_dir: str,
    resume: bool,
    window_start_ts: Optional[int] = None,
    window_end_ts: Optional[int] = None,
) -> Dict[str, Any]:
    total_rows = 0
    start_page = next_page_index(out_dir, progress_label) if resume else 0
    page = start_page
    fetched_pages = 0
    latest_time: Optional[str] = None
    min_ts: Optional[int] = None
    max_ts: Optional[int] = None
    prev_fingerprint: Optional[str] = None
    while True:
        offset = page * (limit or 0)
        page_params = dict(params)
        if limit is not None:
            page_params.update({"limit": limit, "offset": offset})
        rows = safe_get_json(
            base_url,
            page_params,
            retries=retries,
            retry_backoff=retry_backoff,
        )
        if isinstance(rows, dict) and rows.get("_error"):
            if progress:
                log(
                    f"[{progress_label}] error_response page={page} url={rows.get('_url')} "
                    "will_retry"
                )
            time.sleep(retry_backoff)
            continue
        if not rows:
            break
        if isinstance(rows, list):
            raw_min_ts, raw_max_ts = extract_min_max_ts(rows)
            raw_count = len(rows)
            rows = filter_rows_by_ts_window(rows, window_start_ts, window_end_ts)
            kept_count = len(rows)
            if progress and (window_start_ts is not None or window_end_ts is not None):
                log(
                    f"[{progress_label}] filter page={page} offset={offset} "
                    f"raw={raw_count} kept={kept_count} "
                    f"raw_min_ts={raw_min_ts} raw_max_ts={raw_max_ts}"
                )
            if (
                window_start_ts is not None
                and raw_min_ts is None
                and raw_max_ts is None
                and page == start_page
            ):
                if progress:
                    log(
                        f"[{progress_label}] no_timestamp_fields_detected "
                        "recent_mode_fallback=first_page_only"
                    )
            fingerprint = stable_rows_fingerprint(rows)
            if fingerprint and fingerprint == prev_fingerprint:
                if progress:
                    log(
                        f"[{progress_label}] duplicate_page_detected page={page} "
                        f"offset={offset} skipping"
                    )
                page += 1
                time.sleep(sleep_s)
                continue
            if not rows:
                # Recent mode guard: if this page is fully older than window, stop scanning.
                if (
                    window_start_ts is not None
                    and raw_max_ts is not None
                    and raw_max_ts < window_start_ts
                ):
                    if progress:
                        log(
                            f"[{progress_label}] stop page={page} reason=window_exhausted "
                            f"raw_max_ts={raw_max_ts} window_start_ts={window_start_ts}"
                        )
                    break
                page += 1
                time.sleep(sleep_s)
                continue
            latest = infer_latest_time(rows)
            if latest:
                latest_time = latest
            page_min_ts, page_max_ts = extract_min_max_ts(rows)
            if page_min_ts is not None:
                min_ts = page_min_ts if min_ts is None else min(min_ts, page_min_ts)
            if page_max_ts is not None:
                max_ts = page_max_ts if max_ts is None else max(max_ts, page_max_ts)
            total_rows += len(rows)
            write_page_json(out_dir, progress_label, page, rows)
            fetched_pages += 1
            prev_fingerprint = fingerprint
            if progress:
                meta = f"latest_time={latest_time}" if latest_time else "latest_time=NA"
                log(
                    f"[{progress_label}] page={page + 1} offset={offset} "
                    f"count={len(rows)} total={total_rows} {meta}"
                )
            if limit is not None and len(rows) < limit:
                break
            if (
                window_start_ts is not None
                and raw_min_ts is None
                and raw_max_ts is None
            ):
                # This endpoint does not expose per-row timestamps. In recent mode,
                # keep only the first page as a best-effort latest snapshot.
                break
        else:
            write_page_json(out_dir, progress_label, page, rows)
            if progress:
                log(f"[{progress_label}] non-list response, total={total_rows}")
            break
        time.sleep(sleep_s)
        page += 1
    return {
        "total": total_rows,
        "latest_time": latest_time,
        "min_ts": min_ts,
        "max_ts": max_ts,
        "dir": out_dir,
        "page_count": fetched_pages,
        "start_page": start_page,
        "pattern": f"{progress_label}_page_%06d.json",
    }


def time_window_fetch_stream(
    base_url: str,
    params: Dict[str, Any],
    limit: Optional[int],
    sleep_s: float,
    start_ts: int = 0,
    end_ts: Optional[int] = None,
    retries: Optional[int] = None,
    retry_backoff: float = 1.5,
    progress_label: str = "time_window",
    progress: bool = False,
    out_dir: Optional[str] = None,
    resume: bool = True,
) -> Dict[str, Any]:
    total_rows = 0
    latest_ts: Optional[int] = None
    min_ts: Optional[int] = None
    max_ts: Optional[int] = None
    current_start = start_ts
    final_end = end_ts if end_ts is not None else int(time.time())
    request_index = 0
    if out_dir and resume:
        page_index_offset = next_page_index(out_dir, progress_label)
    else:
        page_index_offset = 0
    effective_limit = min(limit, 500) if limit is not None else 500
    if progress:
        log(
            f"[{progress_label}] start_ts={current_start} end_ts={final_end} "
            f"limit={effective_limit}"
        )
    while current_start <= final_end:
        page_params = dict(params)
        page_params.update(
            {
                "limit": effective_limit,
                "start": current_start,
                "end": final_end,
                "sortBy": "TIMESTAMP",
                "sortDirection": "ASC",
            }
        )
        rows = safe_get_json(
            base_url,
            page_params,
            retries=retries,
            retry_backoff=retry_backoff,
        )
        if isinstance(rows, dict) and rows.get("_error"):
            if progress:
                log(
                    f"[{progress_label}] error_response url={rows.get('_url')} will_retry"
                )
            time.sleep(retry_backoff)
            continue
        if not rows:
            if progress and request_index == 0:
                log(f"[{progress_label}] no rows in window")
            break
        if not isinstance(rows, list):
            if out_dir:
                write_page_json(
                    out_dir, progress_label, page_index_offset + request_index, rows
                )
            break
        total_rows += len(rows)
        page_min_ts, page_max_ts = extract_min_max_ts(rows)
        if page_min_ts is not None:
            min_ts = page_min_ts if min_ts is None else min(min_ts, page_min_ts)
        if page_max_ts is not None:
            max_ts = page_max_ts if max_ts is None else max(max_ts, page_max_ts)
        if out_dir:
            write_page_json(
                out_dir, progress_label, page_index_offset + request_index, rows
            )
        last_ts = None
        for row in reversed(rows):
            if isinstance(row, dict) and isinstance(row.get("timestamp"), (int, float)):
                last_ts = int(row["timestamp"])
                break
        if last_ts is None:
            break
        if last_ts < current_start:
            break
        current_start = last_ts + 1
        request_index += 1
        latest_ts = last_ts
        if progress:
            log(
                f"[{progress_label}] page={request_index} rows={total_rows} "
                f"next_start={current_start}"
            )
        time.sleep(sleep_s)
    return {
        "total": total_rows,
        "latest_ts": latest_ts,
        "min_ts": min_ts,
        "max_ts": max_ts,
        "start_ts": start_ts,
        "end_ts": final_end,
        "dir": out_dir,
        "page_count": request_index,
        "pattern": f"{progress_label}_page_%06d.json",
    }


def write_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def read_json(path: str) -> Optional[Any]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def safe_unlink(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)

def clear_dir(path: str) -> None:
    if not os.path.isdir(path):
        return
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            os.unlink(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(path)


def collect_user_bundle(
    user: str,
    user_dir: str,
    sleep_s: float,
    progress: bool,
    recent_hours: Optional[int],
) -> Dict[str, Any]:
    resume_state_path = os.path.join(user_dir, "resume_state.json")
    resume = os.path.exists(resume_state_path)
    if progress:
        mode = "resume" if resume else "full_history"
        log(f"[{user}] mode={mode}")

    bundle: Dict[str, Any] = {"user": user, "fetched_at": int(time.time())}
    if not resume:
        clear_dir(os.path.join(user_dir, "endpoints"))
        safe_unlink(resume_state_path)
        safe_unlink(os.path.join(user_dir, "user_bundle.json"))
        safe_unlink(os.path.join(user_dir, "manifest.json"))
    positions_limit = ENDPOINT_MAX_LIMITS["positions"]
    closed_limit = ENDPOINT_MAX_LIMITS["closed_positions"]
    activity_limit = ENDPOINT_MAX_LIMITS["activity"]
    endpoints_dir = os.path.join(user_dir, "endpoints")
    recent_enabled = recent_hours is not None and recent_hours > 0
    recent_end_ts = int(time.time()) if recent_enabled else None
    recent_start_ts = (
        recent_end_ts - int(recent_hours) * 3600
        if recent_end_ts is not None and recent_hours is not None
        else None
    )
    recent_window_params: Dict[str, Any] = {}
    if recent_start_ts is not None and recent_end_ts is not None:
        recent_window_params = {"start": recent_start_ts, "end": recent_end_ts}
        if progress:
            log(
                f"[{user}] recent_window hours={recent_hours} "
                f"start_ts={recent_start_ts} end_ts={recent_end_ts}"
            )

    positions_stats = paginated_fetch_stream(
        f"{DATA_API}/positions",
        {"user": user, **recent_window_params},
        positions_limit,
        sleep_s,
        None,
        1.5,
        "positions",
        progress,
        os.path.join(endpoints_dir, "positions"),
        resume,
        window_start_ts=recent_start_ts,
        window_end_ts=recent_end_ts,
    )
    if progress:
        log(
            f"[positions] done total={positions_stats['total']} "
            f"pages={positions_stats['page_count']} start_page={positions_stats['start_page']}"
        )
    closed_stats = paginated_fetch_stream(
        f"{DATA_API}/closed-positions",
        {"user": user, **recent_window_params},
        closed_limit,
        sleep_s,
        None,
        1.5,
        "closed_positions",
        progress,
        os.path.join(endpoints_dir, "closed_positions"),
        resume,
        window_start_ts=recent_start_ts,
        window_end_ts=recent_end_ts,
    )
    if progress:
        log(
            f"[closed_positions] done total={closed_stats['total']} "
            f"pages={closed_stats['page_count']} start_page={closed_stats['start_page']}"
        )
    resume_state_path = os.path.join(user_dir, "resume_state.json")
    resume_state = read_json(resume_state_path) if resume else None
    resume_activity_ts = (
        int(resume_state.get("activity_last_ts", 0))
        if isinstance(resume_state, dict)
        else 0
    )
    resume_trade_ts = (
        int(resume_state.get("trade_last_ts", 0)) if isinstance(resume_state, dict) else 0
    )

    if recent_enabled and recent_start_ts is not None:
        activity_start_ts = recent_start_ts
    elif resume_activity_ts > 0:
        activity_start_ts = resume_activity_ts
    else:
        activity_start_ts = 0
    if progress:
        log(
            f"[activity] resume_ts={resume_activity_ts} "
            f"resume={resume}"
        )
    activity_stats = time_window_fetch_stream(
        f"{DATA_API}/activity",
        {"user": user, **recent_window_params},
        activity_limit,
        sleep_s,
        start_ts=activity_start_ts,
        end_ts=recent_end_ts,
        retries=None,
        retry_backoff=1.5,
        progress_label="activity",
        progress=progress,
        out_dir=os.path.join(endpoints_dir, "activity"),
        resume=resume,
    )
    if progress:
        log(
            f"[activity] done total={activity_stats['total']} "
            f"pages={activity_stats['page_count']} start_ts={activity_stats['start_ts']} "
            f"end_ts={activity_stats['end_ts']} min_ts={activity_stats['min_ts']} "
            f"max_ts={activity_stats['max_ts']}"
        )
    if recent_enabled and recent_start_ts is not None:
        trade_start_ts = recent_start_ts
    elif resume_trade_ts > 0:
        trade_start_ts = resume_trade_ts
    else:
        trade_start_ts = 0
    if progress:
        log(
            f"[trades] resume_ts={resume_trade_ts} "
            f"resume={resume}"
        )
    trades_stats = time_window_fetch_stream(
        f"{DATA_API}/activity",
        {"user": user, "type": "TRADE", **recent_window_params},
        activity_limit,
        sleep_s,
        start_ts=trade_start_ts,
        end_ts=recent_end_ts,
        retries=None,
        retry_backoff=1.5,
        progress_label="trades",
        progress=progress,
        out_dir=os.path.join(endpoints_dir, "trades"),
        resume=resume,
    )
    if progress:
        log(
            f"[trades] done total={trades_stats['total']} "
            f"pages={trades_stats['page_count']} start_ts={trades_stats['start_ts']} "
            f"end_ts={trades_stats['end_ts']} min_ts={trades_stats['min_ts']} "
            f"max_ts={trades_stats['max_ts']}"
        )
    bundle["trades_from_activity"] = True

    traded_markets = safe_get_json(
        f"{DATA_API}/traded",
        {"user": user, **recent_window_params},
        retries=None,
        retry_backoff=1.5,
    )
    positions_value = safe_get_json(
        f"{DATA_API}/value",
        {"user": user, **recent_window_params},
        retries=None,
        retry_backoff=1.5,
    )
    write_json(os.path.join(endpoints_dir, "traded_markets.json"), traded_markets)
    write_json(os.path.join(endpoints_dir, "positions_value.json"), positions_value)
    if progress:
        log("[traded_markets] done")
        log("[positions_value] done")

    bundle["endpoints"] = {
        "positions": positions_stats,
        "closed_positions": closed_stats,
        "activity": activity_stats,
        "trades": trades_stats,
        "traded_markets": {
            "dir": endpoints_dir,
            "file": "traded_markets.json",
        },
        "positions_value": {
            "dir": endpoints_dir,
            "file": "positions_value.json",
        },
    }
    if recent_start_ts is not None and recent_end_ts is not None:
        bundle["recent_window"] = {
            "enabled": True,
            "hours": recent_hours,
            "start_ts": recent_start_ts,
            "end_ts": recent_end_ts,
        }
    return bundle


def write_bundle(out_dir: str, bundle: Dict[str, Any]) -> str:
    out_path = os.path.join(out_dir, "user_bundle.json")
    write_json(out_path, bundle)
    return out_path


def main() -> None:
    args = parse_args()
    users = validate_users(args.users)
    out_dir = args.out_dir

    for user in users:
        user_dir = os.path.join(out_dir, user)
        bundle = collect_user_bundle(
            user=user,
            user_dir=user_dir,
            sleep_s=args.sleep,
            progress=not args.no_progress,
            recent_hours=args.recent,
        )

        out_path = write_bundle(user_dir, bundle)
        activity_last_ts = bundle.get("endpoints", {}).get("activity", {}).get("latest_ts")
        trade_last_ts = bundle.get("endpoints", {}).get("trades", {}).get("latest_ts")
        if activity_last_ts or trade_last_ts:
            resume_state = {
                "activity_last_ts": activity_last_ts,
                "trade_last_ts": trade_last_ts,
                "updated_at": int(time.time()),
            }
            resume_state_path = os.path.join(user_dir, "resume_state.json")
            write_json(resume_state_path, resume_state)
        manifest = {
            "user": user,
            "generated_at": int(time.time()),
            "bundle": out_path,
            "endpoints": bundle.get("endpoints", {}),
        }
        manifest_path = os.path.join(user_dir, "manifest.json")
        write_json(manifest_path, manifest)
        log(f"Wrote {out_path}")
        log(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
