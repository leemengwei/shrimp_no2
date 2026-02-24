import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

# 将项目 src 添加到 sys.path，方便导入本地模块
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from common.http_client import request_json

# 数据/API 地址常量
DATA_API = "https://data-api.polymarket.com"
GAMMA_API = "https://gamma-api.polymarket.com"

# 追加写入的日志文件（JSONL 格式），可通过环境变量 LOG_PATH 覆盖
LOG_PATH = os.path.join(os.path.dirname(__file__), "user_activity.log.jsonl")

# 在此文件中硬编码要跟踪的用户地址（用于个人使用）
# 请替换为目标用户地址，例如 0xabc...

USER_ID = '0x2005d16a84ceefa912d4e380cd32e7ff827875ea'  # RN1
USER_ID = '0xf0729143cbf9ade46743017ec4e1832a3564cee7'  # selector
USER_ID = '0x1ea6aab09d4b9b504fa24f961f0c6709efb72f5d'  # lmw


# 运行时配置默认值（通过 argparse 覆盖）python field_ops/user_activity_tracker.py --interval 10python field_ops/user_activity_tracker.py --interval 10python field_ops/user_activity_tracker.py --interval 10python field_ops/user_activity_tracker.py --interval 10python field_ops/user_activity_tracker.py --interval 10python field_ops/user_activity_tracker.py --interval 10
REQUEST_TIMEOUT = 30.0
RETRY_MAX = 3
RETRY_BASE_SLEEP = 1.0
RETRY_MAX_SLEEP = 30.0
RETRY_JITTER = 0.3

PROFILE_BOOTSTRAP_SLEEP = 5.0

BACKFILL_ON_START = True
BACKFILL_ONLY = False
BACKFILL_PAGE_SIZE = 200
BACKFILL_SLEEP = 0.1
BACKFILL_PROGRESS_EVERY = 5.0
BACKFILL_PROGRESS_ITEMS = 1000
BACKFILL_MAX_OFFSET = 3000
BACKFILL_RESUME_WINDOW = 3600
BACKFILL_START = 0
BACKFILL_END = 0


def log_error(message):
    now = datetime.now().astimezone().isoformat()
    print(f"[{now}] error: {message}", file=sys.stderr)


def log_info(message):
    now = datetime.now().astimezone().isoformat()
    print(f"[{now}] {message}")


def is_retriable_message(message):
    if not message:
        return False
    needles = (
        "HTTP 429",
        "HTTP 5",
        "Network error",
        "timed out",
        "timeout",
        "Temporary failure",
        "Connection reset",
        "Remote end closed",
        "Name or service not known",
    )
    return any(needle in message for needle in needles)


def safe_request_json(method, base_url, path, params=None, body=None, headers=None, fallback=None):
    attempts = max(1, RETRY_MAX)
    for attempt in range(1, attempts + 1):
        try:
            return request_json(
                method,
                base_url,
                path,
                params=params,
                body=body,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except SystemExit as exc:
            message = str(exc)
        except Exception as exc:
            message = str(exc)

        if attempt >= attempts or not is_retriable_message(message):
            log_error(f"request failed: {method} {base_url}{path}: {message}")
            return fallback

        base_sleep = min(RETRY_MAX_SLEEP, RETRY_BASE_SLEEP * (2 ** (attempt - 1)))
        jitter = base_sleep * RETRY_JITTER * random.random()
        time.sleep(base_sleep + jitter)

    return fallback


def normalize_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        data = value.get("data")
        if isinstance(data, list):
            return data
    return []


def fetch_profile_blocking(user):
    while True:
        profile = safe_request_json(
            "GET",
            GAMMA_API,
            "/public-profile",
            params={"address": user},
            fallback=None,
        )
        if isinstance(profile, dict) and profile:
            return profile
        log_error("public-profile unavailable, retrying")
        time.sleep(PROFILE_BOOTSTRAP_SLEEP)


def fetch_activity_snapshot(user):
    activity = safe_request_json(
        "GET",
        DATA_API,
        "/activity",
        params={"user": user, "limit": 50, "offset": 0},
        fallback=[],
    )
    return normalize_list(activity)


def summarize_snapshot(activity):
    # 不使用 state：每轮将当前快照视为可记录项
    return list(activity)


def log_heartbeat_or_new(user, username, new_activity):
    now = datetime.now().astimezone().isoformat()
    if not new_activity:
        print(f"[{now}] user={user} ({username}) heartbeat")
        return
    print(f"[{now}] user={user} ({username}) new")
    if new_activity:
        print(f"  activity: {len(new_activity)}")


def get_username(profile, user):
    if not isinstance(profile, dict):
        return user
    for key in ("username", "name", "displayName", "handle"):
        value = profile.get(key)
        if value:
            return value
    return user


def parse_event_time(item):
    if not isinstance(item, dict):
        return ""
    raw_ts = item.get("timestamp")
    raw_created = item.get("createdAt")

    if isinstance(raw_ts, (int, float)):
        ts = float(raw_ts)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts).astimezone().isoformat()
    if isinstance(raw_ts, str) and raw_ts.isdigit():
        ts = float(raw_ts)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return datetime.fromtimestamp(ts).astimezone().isoformat()

    if isinstance(raw_created, str) and raw_created:
        value = raw_created.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.astimezone().isoformat()
        except ValueError:
            return raw_created
    return ""


def parse_event_timestamp(item):
    if not isinstance(item, dict):
        return None
    raw_ts = item.get("timestamp")
    raw_created = item.get("createdAt")

    if isinstance(raw_ts, (int, float)):
        ts = float(raw_ts)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return ts
    if isinstance(raw_ts, str) and raw_ts.isdigit():
        ts = float(raw_ts)
        if ts > 1_000_000_000_000:
            ts = ts / 1000.0
        return ts

    if isinstance(raw_created, str) and raw_created:
        value = raw_created.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.timestamp()
        except ValueError:
            return None
    return None


def parse_iso_timestamp(value):
    if not value:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed.timestamp()
    except ValueError:
        return None


def first_value(item, keys):
    for key in keys:
        value = item.get(key)
        if value:
            return value
    return ""


def extract_market_title(item):
    if not isinstance(item, dict):
        return ""
    title = first_value(item, ("marketTitle", "title", "question", "marketName", "eventTitle"))
    if title:
        return title
    market = item.get("market")
    if isinstance(market, dict):
        return first_value(market, ("title", "question", "marketTitle", "name"))
    return ""


def item_fingerprint(item, kind):
    if not isinstance(item, dict):
        raw = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return f"{kind}:raw:{raw}"

    for key in ("id", "tradeId", "eventId", "commentId", "txHash", "hash"):
        value = item.get(key)
        if value:
            return f"{kind}:{key}:{value}"

    parts = []
    base = item.get("timestamp") or item.get("createdAt")
    if base:
        parts.append(f"t={base}")
    for key in ("marketId", "conditionId", "question", "outcome", "side", "price", "size", "amount"):
        value = item.get(key)
        if value not in (None, ""):
            parts.append(f"{key}={value}")
    if parts:
        return f"{kind}:" + "|".join(parts)

    raw = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return f"{kind}:raw:{raw}"


def filter_new_items(items, kind, seen_set):
    new_items = []
    for item in items:
        fingerprint = item_fingerprint(item, kind)
        if fingerprint in seen_set:
            continue
        seen_set.add(fingerprint)
        new_items.append(item)
    return new_items


def build_activity_log_entry(user, username, item):
    entry = {
        "eventTimeLocal": parse_event_time(item),
    }

    market_title = extract_market_title(item)
    if market_title:
        entry["market"] = market_title

    side = item.get("side")
    if side:
        entry["side"] = side

    outcome = item.get("outcome") or item.get("outcomeName")
    if outcome:
        entry["outcome"] = outcome

    price = item.get("price") or item.get("avgPrice")
    if price not in (None, ""):
        entry["price"] = price

    size = item.get("size") or item.get("shares") or item.get("quantity")
    if size not in (None, ""):
        entry["size"] = size

    amount = item.get("amount") or item.get("value") or item.get("notional")
    if amount not in (None, ""):
        entry["amount"] = amount

    action = item.get("action") or item.get("type") or item.get("eventType")
    if action:
        entry["action"] = action

    comment = item.get("comment") or item.get("text") or item.get("body")
    if comment:
        entry["comment"] = comment

    entry["type"] = "activity"
    return entry


def entry_fingerprint(entry):
    return json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_existing_entry_fingerprints(log_path):
    fingerprints = set()
    if not os.path.exists(log_path):
        return fingerprints
    try:
        with open(log_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(entry, dict):
                    fingerprints.add(entry_fingerprint(entry))
    except OSError as exc:
        log_error(f"failed to read log file {log_path}: {exc}")
    return fingerprints


def load_latest_logged_timestamp(log_path):
    latest_ts = None
    if not os.path.exists(log_path):
        return None
    try:
        with open(log_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(entry, dict):
                    continue
                event_time = entry.get("eventTimeLocal")
                ts = parse_iso_timestamp(event_time)
                if ts is None:
                    continue
                if latest_ts is None or ts > latest_ts:
                    latest_ts = ts
    except OSError as exc:
        log_error(f"failed to read log file {log_path}: {exc}")
    return latest_ts


def user_log_path(base_path, username):
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in username)
    root, ext = os.path.splitext(base_path)
    if not ext:
        ext = ".jsonl"
    return f"{root}.{safe_name}{ext}"


def backfill_activity_stream(user, username, log_path, seen, written_entries, start_ts, end_ts):
    offset = 0
    total = 0
    last_log_ts = 0.0
    last_log_count = 0
    limit = min(BACKFILL_PAGE_SIZE, 500)
    if end_ts <= 0:
        end_ts = int(time.time())

    while True:
        if offset >= BACKFILL_MAX_OFFSET:
            log_info(f"backfill activity: reached max offset {BACKFILL_MAX_OFFSET}")
            break
        batch = safe_request_json(
            "GET",
            DATA_API,
            "/activity",
            params={
                "user": user,
                "limit": limit,
                "offset": offset,
                "start": int(start_ts),
                "end": int(end_ts),
                "sortBy": "TIMESTAMP",
                "sortDirection": "ASC",
            },
            fallback=None,
        )
        if batch is None:
            log_info("backfill activity: request failed, retrying")
            time.sleep(max(BACKFILL_SLEEP, 1.0))
            continue
        batch = normalize_list(batch)
        if not batch:
            break

        total += len(batch)
        last_ts = batch[-1].get("timestamp")
        if isinstance(last_ts, (int, float)):
            last_ts = int(last_ts)
        else:
            last_ts = None

        now_ts = time.time()
        if (total - last_log_count) >= BACKFILL_PROGRESS_ITEMS or (now_ts - last_log_ts) >= BACKFILL_PROGRESS_EVERY:
            log_info(f"backfill activity: fetched {total}")
            last_log_ts = now_ts
            last_log_count = total

        new_activity = filter_new_items(batch, "activity", seen["activity"])
        if new_activity:
            append_log_entries(user, username, log_path, new_activity, written_entries)

        if len(batch) < limit:
            break
        if last_ts is None:
            log_error("backfill activity: missing timestamp, stopping")
            break
        if last_ts == int(start_ts):
            offset += len(batch)
        else:
            start_ts = last_ts
            offset = 0
        if BACKFILL_SLEEP > 0:
            time.sleep(BACKFILL_SLEEP)


def append_log_entries(user, username, log_path, new_activity, written_entries):
    # 以 JSONL 方式追加每条新增事件，便于后续增量解析
    entries = []
    index = 0
    for item in new_activity:
        entry = build_activity_log_entry(user, username, item)
        timestamp = parse_event_timestamp(item)
        if timestamp is None:
            timestamp = parse_iso_timestamp(entry.get("eventTimeLocal"))
        entries.append((timestamp, index, entry))
        index += 1

    if not entries:
        return

    entries.sort(key=lambda item: (item[0] is None, item[0] or 0, item[1]))

    with open(log_path, "a", encoding="utf-8") as handle:
        for _, _, entry in entries:
            if entry.get("action") == "YIELD":
                continue
            fingerprint = entry_fingerprint(entry)
            if fingerprint in written_entries:
                continue
            handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
            written_entries.add(fingerprint)


def main():
    global PROFILE_BOOTSTRAP_SLEEP
    global BACKFILL_ON_START
    global BACKFILL_ONLY
    global BACKFILL_START
    global BACKFILL_END

    parser = argparse.ArgumentParser(description="Track user activity with resilient polling.")
    parser.add_argument("--user-id", default=USER_ID, help="Target user address to track.")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds.")
    parser.add_argument("--log-path", default=LOG_PATH, help="Base JSONL log path.")

    parser.add_argument("--no-backfill", action="store_true", help="Disable backfill on start.")
    parser.add_argument("--backfill-only", action="store_true", help="Exit after backfill completes.")
    parser.add_argument("--backfill-start", type=int, default=BACKFILL_START, help="Backfill start timestamp (unix seconds).")
    parser.add_argument("--backfill-end", type=int, default=BACKFILL_END, help="Backfill end timestamp (unix seconds, 0 = now).")

    args = parser.parse_args()

    BACKFILL_ON_START = not args.no_backfill
    BACKFILL_ONLY = args.backfill_only
    BACKFILL_START = args.backfill_start
    BACKFILL_END = args.backfill_end

    # 确保 USER_ID 已设置为目标地址
    if args.user_id == "0x0000000000000000000000000000000000000000":
        raise SystemExit("Set USER_ID in field_ops/user_activity_tracker.py")

    # 轮询间隔（秒），可通过环境变量 INTERVAL 覆盖
    interval = args.interval
    log_path = args.log_path
    seen = {"activity": set()}
    written_entries = set()
    loaded_log = False
    last_username = args.user_id
    backfill_done = False
    profile = fetch_profile_blocking(args.user_id)
    last_username = get_username(profile, args.user_id)
    # 进入主循环：拉取快照 -> 输出心跳 -> 追加记录 -> sleep
    while True:
        try:
            snapshot = fetch_activity_snapshot(args.user_id)
            new_activity = summarize_snapshot(snapshot)
            new_activity = filter_new_items(new_activity, "activity", seen["activity"])
            username = last_username
            log_heartbeat_or_new(args.user_id, username, new_activity)
            per_user_log_path = user_log_path(log_path, username)
            if not loaded_log:
                written_entries = load_existing_entry_fingerprints(per_user_log_path)
                loaded_log = True

            if BACKFILL_ON_START and not backfill_done:
                resume_start = BACKFILL_START
                if resume_start <= 0:
                    latest_ts = load_latest_logged_timestamp(per_user_log_path)
                    if latest_ts is not None:
                        resume_start = max(0, int(latest_ts) - BACKFILL_RESUME_WINDOW)
                backfill_activity_stream(
                    args.user_id,
                    username,
                    per_user_log_path,
                    seen,
                    written_entries,
                    resume_start,
                    BACKFILL_END,
                )
                backfill_done = True
                if BACKFILL_ONLY:
                    return

            append_log_entries(args.user_id, username, per_user_log_path, new_activity, written_entries)
        except Exception as exc:
            log_error(f"loop error: {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
