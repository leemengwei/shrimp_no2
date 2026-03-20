#!/usr/bin/env python3
"""Local web dashboard for Polymarket user data.

Example:
  python web/app.py --data-dir data/polymarket/user_activities --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from flask import Flask, jsonify, render_template, request

DEFAULT_DATA_DIR = Path("data/polymarket/user_activities")
LEGACY_DATA_DIR = Path("data/polymarket")
DEFAULT_SPORTS_DIR = Path("data/polymarket/sports_history")


def resolve_data_dir(cli_data_dir: Path) -> Path:
    # Auto-migrate default web loading path to the new user_activities folder.
    # If old layout still exists and new one does not, fallback to legacy path.
    if cli_data_dir == DEFAULT_DATA_DIR:
        if DEFAULT_DATA_DIR.exists():
            return DEFAULT_DATA_DIR
        if LEGACY_DATA_DIR.exists():
            return LEGACY_DATA_DIR
    if cli_data_dir.exists():
        return cli_data_dir
    root = Path("data/polymarket")
    if root.exists():
        candidates: List[Path] = []
        for p in root.glob("*"):
            if not p.is_dir():
                continue
            has_user_dirs = any(c.is_dir() and c.name.startswith("0x") for c in p.iterdir())
            if has_user_dirs:
                candidates.append(p)
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            return candidates[0]
    return cli_data_dir


def resolve_sports_dir(cli_sports_dir: Path) -> Path:
    if cli_sports_dir.exists() and (cli_sports_dir / "manifest.json").exists():
        return cli_sports_dir
    if cli_sports_dir == DEFAULT_SPORTS_DIR and DEFAULT_SPORTS_DIR.exists():
        return DEFAULT_SPORTS_DIR

    root = Path("data/polymarket")
    if root.exists():
        candidates: List[Tuple[float, Path]] = []
        for p in root.glob("*"):
            if not p.is_dir():
                continue
            manifest = p / "manifest.json"
            if not manifest.exists():
                continue
            try:
                payload = load_json(manifest)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("markets"), list):
                candidates.append((manifest.stat().st_mtime, p))
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
    return cli_sports_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local web dashboard for Polymarket data")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Data root directory (user activity bundles)",
    )
    parser.add_argument(
        "--sports-dir",
        default=str(DEFAULT_SPORTS_DIR),
        help="Sports history output directory (from collect_sports_history.py)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def list_users(data_dir: Path) -> List[str]:
    if not data_dir.exists():
        return []
    users = [p.name for p in data_dir.iterdir() if p.is_dir() and p.name.startswith("0x")]
    return sorted(users)


def resolve_user_label(data_dir: Path, user: str) -> Optional[str]:
    for endpoint in ("activity", "trades"):
        files = resolve_endpoint_files(data_dir, user, endpoint)
        if not files:
            continue
        rows_iter = read_endpoint_pages(files)
        for row in rows_iter:
            if not isinstance(row, dict):
                continue
            label = row.get("name")
            if label:
                return str(label)
    return None


def load_manifest(data_dir: Path, user: str) -> Dict[str, Any]:
    path = data_dir / user / "manifest.json"
    if path.exists():
        return load_json(path)
    return {}


def load_user_bundle(data_dir: Path, user: str) -> Dict[str, Any]:
    path = data_dir / user / "user_bundle.json"
    if path.exists():
        return load_json(path)
    return {}


def configs_path(data_dir: Path, user: str) -> Path:
    return data_dir / user / "web_configs.json"


def load_web_configs(data_dir: Path, user: str) -> Dict[str, Any]:
    path = configs_path(data_dir, user)
    if path.exists():
        try:
            return load_json(path)
        except json.JSONDecodeError:
            return {}
    return {}


def save_web_configs(data_dir: Path, user: str, payload: Dict[str, Any]) -> None:
    save_json(configs_path(data_dir, user), payload)


def resolve_endpoint_files(data_dir: Path, user: str, endpoint: str) -> List[Path]:
    manifest = load_manifest(data_dir, user)
    endpoints = manifest.get("endpoints", {}) if isinstance(manifest, dict) else {}
    info = endpoints.get(endpoint) if isinstance(endpoints, dict) else None

    if isinstance(info, dict):
        dir_hint = info.get("dir")
        file_hint = info.get("file")
        base_dir: Optional[Path] = None
        if dir_hint:
            candidate = Path(dir_hint)
            if not candidate.is_absolute():
                candidate = Path.cwd() / candidate
            base_dir = candidate if candidate.exists() else None
        if base_dir is None:
            base_dir = data_dir / user / "endpoints"

        if file_hint:
            hinted = base_dir / file_hint
            if hinted.exists():
                return [hinted]
            fallback_file = data_dir / user / "endpoints" / file_hint
            if fallback_file.exists():
                return [fallback_file]
            return [hinted]
        if base_dir.exists() and base_dir.is_dir():
            pattern = info.get("pattern")
            if isinstance(pattern, str) and "%06d" in pattern:
                glob_pattern = pattern.replace("%06d", "*")
                files = sorted(base_dir.glob(glob_pattern))
                if files:
                    return files
                # Some manifests store endpoint dir hints at root `.../endpoints`,
                # while page files are under `.../endpoints/<endpoint>/`.
                nested_dir = base_dir / endpoint
                if nested_dir.exists() and nested_dir.is_dir():
                    nested_files = sorted(nested_dir.glob(glob_pattern))
                    if nested_files:
                        return nested_files
                return files
            return sorted(p for p in base_dir.iterdir() if p.is_file() and p.suffix == ".json")

    # Fallback to conventional layout
    guess_dir = data_dir / user / "endpoints" / endpoint
    if guess_dir.exists() and guess_dir.is_dir():
        return sorted(p for p in guess_dir.iterdir() if p.is_file() and p.suffix == ".json")

    guess_file = data_dir / user / "endpoints" / f"{endpoint}.json"
    if guess_file.exists() and guess_file.is_file():
        return [guess_file]
    return []


def read_endpoint_pages(files: Iterable[Path]) -> Iterable[Any]:
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        try:
            data = load_json(path)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for row in data:
                yield row
        else:
            yield data


def extract_ts(row: Dict[str, Any]) -> Optional[int]:
    for key in ("timestamp", "ts", "time", "createdAt", "created_at", "resolvedAt"):
        val = row.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


def _sort_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _activity_row_tie_breaker(row: Dict[str, Any]) -> Tuple[str, ...]:
    return (
        _sort_text(row.get("transactionHash")),
        _sort_text(row.get("asset")),
        _sort_text(row.get("conditionId")),
        _sort_text(row.get("outcomeIndex")),
        _sort_text(row.get("side")),
        _sort_text(row.get("price")),
        _sort_text(row.get("size")),
    )


def _activity_row_sort_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    ts = extract_ts(row)
    return (ts if ts is not None else -1, *_activity_row_tie_breaker(row))


def parse_ts_param(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def row_matches(row: Dict[str, Any], query: str) -> bool:
    if not query:
        return True
    q = query.lower()
    for v in row.values():
        if isinstance(v, str) and q in v.lower():
            return True
    return False


def filter_rows(
    rows: Iterable[Any],
    query: str,
    from_ts: Optional[int],
    to_ts: Optional[int],
    column_filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    columns: List[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in row.keys():
            if key not in columns:
                columns.append(key)
        if query and not row_matches(row, query):
            continue
        if column_filters:
            matched_all = True
            for key, raw in column_filters.items():
                if raw is None:
                    continue
                q = raw
                if not q:
                    continue
                val = row.get(key)
                if val is None and key not in row:
                    continue
                candidates = [part.strip() for part in str(q).split(",") if part.strip()]
                if not candidates:
                    continue
                matched_any = False
                for token in candidates:
                    if val is None:
                        matched = False
                    elif isinstance(val, (int, float)):
                        matched = token in str(val)
                    elif isinstance(val, str):
                        matched = token.lower() in val.lower()
                    else:
                        matched = token.lower() in json.dumps(val, ensure_ascii=False).lower()
                    if matched:
                        matched_any = True
                        break
                if not matched_any:
                    matched_all = False
                    break
            if not matched_all:
                continue
        if from_ts is not None or to_ts is not None:
            ts = extract_ts(row)
            if ts is not None:
                if from_ts is not None and ts < from_ts:
                    continue
                if to_ts is not None and ts > to_ts:
                    continue
        filtered.append(row)
    return filtered, columns


def paginate(rows: List[Dict[str, Any]], limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
    total = len(rows)
    if limit <= 0:
        return rows, total
    return rows[offset : offset + limit], total


def is_noisy_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("id"):
        return True
    noisy_parts = ("hash", "token", "wallet", "address", "tx", "clob")
    return any(part in lowered for part in noisy_parts)


def compact_columns(endpoint: str, rows: List[Dict[str, Any]]) -> List[str]:
    preferred = [
        "timestamp",
        "createdAt",
        "time",
        "type",
        "action",
        "title",
        "market",
        "slug",
        "outcome",
        "side",
        "price",
        "size",
        "avgCost",
        "value",
        "pnl",
        "pnlPercent",
        "resolvedAt",
    ]
    existing = []
    if rows:
        keys = set().union(*[set(r.keys()) for r in rows])
        for key in preferred:
            if key in keys:
                existing.append(key)
        # Add remaining non-noisy keys at the end
        for key in sorted(keys):
            if key in existing or is_noisy_key(key):
                continue
            existing.append(key)
    return existing


def apply_compact_view(endpoint: str, rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    columns = compact_columns(endpoint, rows)
    if not columns:
        return rows, []
    trimmed = [{k: row.get(k) for k in columns} for row in rows]
    return trimmed, columns


def summarize_rows(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    total = 0
    min_ts: Optional[int] = None
    max_ts: Optional[int] = None
    for row in rows:
        if not isinstance(row, dict):
            continue
        total += 1
        ts = extract_ts(row)
        if ts is None:
            continue
        if min_ts is None or ts < min_ts:
            min_ts = ts
        if max_ts is None or ts > max_ts:
            max_ts = ts
    return {"total": total, "min_ts": min_ts, "max_ts": max_ts}


def load_sports_manifest(sports_dir: Path) -> Dict[str, Any]:
    path = sports_dir / "manifest.json"
    if path.exists():
        return load_json(path)
    return {}


def resolve_sports_market_dir(sports_dir: Path, market: Dict[str, Any]) -> Optional[Path]:
    index = market.get("index")
    if not isinstance(index, int):
        return None
    slug = str(market.get("slug") or "").strip()
    if slug:
        exact = sports_dir / f"{index:05d}_{slug}"
        if exact.exists() and exact.is_dir():
            return exact
    prefix = f"{index:05d}_"
    matches = sorted(
        (p for p in sports_dir.glob(f"{prefix}*") if p.is_dir()),
        key=lambda p: p.name,
    )
    if matches:
        return matches[0]
    return None


def iter_jsonl(path: Path) -> Iterable[Any]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def summarize_tokens(tokens: List[Dict[str, Any]]) -> Dict[str, Any]:
    min_ts = None
    max_ts = None
    points = 0
    unique_points = 0
    for token in tokens:
        if not isinstance(token, dict):
            continue
        points += int(token.get("points") or 0)
        unique_points += int(token.get("unique_points") or 0)
        t_min = token.get("min_ts")
        t_max = token.get("max_ts")
        if isinstance(t_min, int):
            min_ts = t_min if min_ts is None else min(min_ts, t_min)
        if isinstance(t_max, int):
            max_ts = t_max if max_ts is None else max(max_ts, t_max)
    return {
        "min_ts": min_ts,
        "max_ts": max_ts,
        "points": points,
        "unique_points": unique_points,
    }


def list_sports_markets(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    markets = manifest.get("markets") if isinstance(manifest, dict) else None
    if not isinstance(markets, list):
        return []
    out: List[Dict[str, Any]] = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        tokens = market.get("tokens") if isinstance(market.get("tokens"), list) else []
        stats = summarize_tokens(tokens)
        out.append(
            {
                "index": market.get("index"),
                "market_id": market.get("market_id"),
                "condition_id": market.get("condition_id"),
                "slug": market.get("slug"),
                "question": market.get("question"),
                "token_count": len(market.get("token_ids") or []),
                "min_ts": stats["min_ts"],
                "max_ts": stats["max_ts"],
                "points": stats["points"],
                "unique_points": stats["unique_points"],
            }
        )
    out.sort(
        key=lambda m: (
            -(int(m.get("points") or 0)),
            -(int(m.get("unique_points") or 0)),
            int(m.get("index") or 0),
        )
    )
    return out


def resolve_market_entry(manifest: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    markets = manifest.get("markets") if isinstance(manifest, dict) else None
    if not isinstance(markets, list):
        return None
    for market in markets:
        if isinstance(market, dict) and market.get("index") == index:
            return market
    return None


def load_metrics(data_dir: Path, user: str) -> Dict[str, Any]:
    manifest = load_manifest(data_dir, user)
    bundle = load_user_bundle(data_dir, user)
    endpoints = manifest.get("endpoints", {}) if isinstance(manifest, dict) else {}

    def load_single(endpoint_name: str) -> Optional[Any]:
        info = endpoints.get(endpoint_name)
        if isinstance(info, dict):
            files = resolve_endpoint_files(data_dir, user, endpoint_name)
            if files:
                return load_json(files[0])
        fallback = data_dir / user / "endpoints" / f"{endpoint_name}.json"
        if fallback.exists():
            return load_json(fallback)
        return None

    positions_value = load_single("positions_value")
    traded_markets = load_single("traded_markets")

    return {
        "generated_at": manifest.get("generated_at"),
        "fetched_at": bundle.get("fetched_at") or manifest.get("fetched_at"),
        "positions_value": positions_value,
        "traded_markets": traded_markets,
    }


app = Flask(__name__)
DATA_DIR = resolve_data_dir(DEFAULT_DATA_DIR)
SPORTS_DIR = DEFAULT_SPORTS_DIR
DB_PATH = DATA_DIR / "dashboard.db"


def _db_exists() -> bool:
    return DB_PATH.exists() and DB_PATH.is_file()


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS web_configs (
            user TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (user, endpoint)
        )
        """
    )
    return conn


def _db_missing_response() -> Any:
    return (
        jsonify(
            {
                "error": "database not found",
                "message": (
                    "SQLite database is required. Run: "
                    "python3 src/ingest_user_activity_to_sqlite.py "
                    "--data-dir data/polymarket/user_activities "
                    "--db-path data/polymarket/user_activities/dashboard.db"
                ),
            }
        ),
        503,
    )


def _db_endpoint_base_where(endpoint: str) -> str:
    if endpoint == "activity":
        return "user = ? AND endpoint = ? AND COALESCE(type_upper, '') != 'YIELD'"
    return "user = ? AND endpoint = ?"


def _db_list_users() -> List[str]:
    with _db_connect() as conn:
        rows = conn.execute("SELECT DISTINCT user FROM records ORDER BY user ASC").fetchall()
    return [str(r["user"]) for r in rows]


def _db_resolve_user_label(user: str) -> Optional[str]:
    with _db_connect() as conn:
        row = conn.execute(
            """
            SELECT json_extract(row_json, '$.name') AS name
            FROM records
            WHERE user = ? AND endpoint IN ('activity', 'trades')
              AND json_extract(row_json, '$.name') IS NOT NULL
            ORDER BY COALESCE(ts, -1) DESC, row_hash ASC
            LIMIT 1
            """,
            (user,),
        ).fetchone()
    if not row:
        return None
    val = row["name"]
    return str(val) if val is not None else None


def _db_list_endpoints(user: str) -> List[str]:
    with _db_connect() as conn:
        rows = conn.execute(
            """
            SELECT endpoint
            FROM (
                SELECT endpoint FROM records WHERE user = ?
                UNION
                SELECT endpoint FROM endpoint_columns WHERE user = ?
                UNION
                SELECT endpoint FROM ingest_state WHERE user = ?
            )
            ORDER BY endpoint ASC
            """,
            (user, user, user),
        ).fetchall()
    return [str(r["endpoint"]) for r in rows]


def _db_endpoint_summary(user: str, endpoint: str) -> Dict[str, Any]:
    where_sql = _db_endpoint_base_where(endpoint)
    with _db_connect() as conn:
        row = conn.execute(
            f"""
            SELECT
              COUNT(1) AS total,
              MIN(ts) AS min_ts,
              MAX(ts) AS max_ts
            FROM records
            WHERE {where_sql}
            """,
            (user, endpoint),
        ).fetchone()
    return {
        "total": int(row["total"]) if row and row["total"] is not None else 0,
        "min_ts": int(row["min_ts"]) if row and row["min_ts"] is not None else None,
        "max_ts": int(row["max_ts"]) if row and row["max_ts"] is not None else None,
        "latest_ts": int(row["max_ts"]) if row and row["max_ts"] is not None else None,
    }


def _db_load_latest_json(user: str, endpoint: str) -> Optional[Any]:
    with _db_connect() as conn:
        row = conn.execute(
            """
            SELECT row_json
            FROM records
            WHERE user = ? AND endpoint = ?
            ORDER BY COALESCE(ts, -1) DESC, rowid DESC
            LIMIT 1
            """,
            (user, endpoint),
        ).fetchone()
    if not row:
        return None
    try:
        return json.loads(row["row_json"])
    except (TypeError, json.JSONDecodeError):
        return None


def _build_db_filters(
    endpoint: str,
    query: str,
    from_ts_i: Optional[int],
    to_ts_i: Optional[int],
    column_filters: Optional[Dict[str, Any]],
) -> Tuple[List[str], List[Any]]:
    where = ["user = ?", "endpoint = ?"]
    params: List[Any] = []
    if endpoint == "activity":
        where.append("COALESCE(type_upper, '') != 'YIELD'")
    if query:
        where.append("row_text LIKE ?")
        params.append(f"%{query.lower()}%")
    if from_ts_i is not None:
        where.append("(ts IS NULL OR ts >= ?)")
        params.append(from_ts_i)
    if to_ts_i is not None:
        where.append("(ts IS NULL OR ts <= ?)")
        params.append(to_ts_i)
    if column_filters:
        for key, raw in column_filters.items():
            if not raw:
                continue
            tokens = [part.strip().lower() for part in str(raw).split(",") if part.strip()]
            if not tokens:
                continue
            key_clause = []
            json_path = f"$.{key}"
            for token in tokens:
                key_clause.append("LOWER(COALESCE(CAST(json_extract(row_json, ?) AS TEXT), '')) LIKE ?")
                params.extend([json_path, f"%{token}%"])
            where.append(f"({' OR '.join(key_clause)})")
    return where, params


def _load_records_from_db(
    user: str,
    endpoint: str,
    query: str,
    from_ts_i: Optional[int],
    to_ts_i: Optional[int],
    sort_order: str,
    limit: int,
    offset: int,
    column_filters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    with _db_connect() as conn:
        where, params = _build_db_filters(endpoint, query, from_ts_i, to_ts_i, column_filters)
        base_where_sql = " AND ".join(where)
        base_params = [user, endpoint, *params]

        total_row = conn.execute(
            f"SELECT COUNT(1) AS total FROM records WHERE {base_where_sql}",
            base_params,
        ).fetchone()
        total = int(total_row["total"]) if total_row else 0

        if sort_order == "asc":
            order_sql = "ORDER BY COALESCE(ts, -1) ASC, row_hash ASC"
        else:
            order_sql = "ORDER BY COALESCE(ts, -1) DESC, row_hash ASC"
        sql = (
            f"SELECT row_json FROM records WHERE {base_where_sql} "
            f"{order_sql} LIMIT ? OFFSET ?"
        )
        rows_db = conn.execute(sql, [*base_params, limit, offset]).fetchall()

        rows: List[Dict[str, Any]] = []
        for r in rows_db:
            try:
                decoded = json.loads(r["row_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(decoded, dict):
                rows.append(decoded)

        col_rows = conn.execute(
            """
            SELECT column_name
            FROM endpoint_columns
            WHERE user = ? AND endpoint = ?
            ORDER BY ord ASC
            """,
            (user, endpoint),
        ).fetchall()
        all_columns = [str(r["column_name"]) for r in col_rows]
        return {"rows": rows, "total": total, "all_columns": all_columns}


def _db_get_configs(user: str, endpoint: str) -> Dict[str, Any]:
    with _db_connect() as conn:
        row = conn.execute(
            "SELECT payload_json FROM web_configs WHERE user = ? AND endpoint = ?",
            (user, endpoint),
        ).fetchone()
    if not row:
        return {"active": "默认", "configs": {}}
    try:
        payload = json.loads(row["payload_json"])
    except (TypeError, json.JSONDecodeError):
        return {"active": "默认", "configs": {}}
    if not isinstance(payload, dict):
        return {"active": "默认", "configs": {}}
    return {
        "active": payload.get("active") or "默认",
        "configs": payload.get("configs") if isinstance(payload.get("configs"), dict) else {},
    }


def _db_save_configs(user: str, endpoint: str, payload: Dict[str, Any]) -> None:
    normalized = {
        "active": payload.get("active") or "默认",
        "configs": payload.get("configs") if isinstance(payload.get("configs"), dict) else {},
    }
    with _db_connect() as conn:
        conn.execute(
            """
            INSERT INTO web_configs(user, endpoint, payload_json, updated_at)
            VALUES (?, ?, ?, strftime('%s', 'now'))
            ON CONFLICT(user, endpoint) DO UPDATE SET
                payload_json = excluded.payload_json,
                updated_at = excluded.updated_at
            """,
            (user, endpoint, json.dumps(normalized, ensure_ascii=False)),
        )
        conn.commit()


def _stable_row_sort_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
    return _activity_row_sort_key(row)


def _stable_row_sort_key_desc(row: Dict[str, Any]) -> Tuple[Any, ...]:
    ts = extract_ts(row)
    ts_key = -(ts if ts is not None else -1)
    return (ts_key, *_activity_row_tie_breaker(row))


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/sports")
def sports_index() -> str:
    return render_template("sports.html")


@app.route("/api/users")
def api_users() -> Any:
    if not _db_exists():
        return _db_missing_response()
    users = _db_list_users()
    detailed = []
    for user in users:
        detailed.append({"id": user, "label": _db_resolve_user_label(user)})
    return jsonify({"users": detailed})


@app.route("/api/user/<user>/manifest")
def api_manifest(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    endpoints = _db_list_endpoints(user)
    endpoint_info = {ep: _db_endpoint_summary(user, ep) for ep in endpoints}
    return jsonify(
        {
            "user": user,
            "generated_at": None,
            "bundle": None,
            "endpoints": endpoint_info,
        }
    )


@app.route("/api/user/<user>/endpoints")
def api_endpoints(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    endpoints = _db_list_endpoints(user)
    return jsonify({"endpoints": endpoints})


@app.route("/api/user/<user>/summary")
def api_summary(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    endpoints = _db_list_endpoints(user)
    endpoint_info = {ep: _db_endpoint_summary(user, ep) for ep in endpoints}
    summary = {
        "user": user,
        "generated_at": None,
        "fetched_at": None,
        "endpoints": endpoint_info,
    }
    return jsonify(summary)


@app.route("/api/user/<user>/metrics")
def api_metrics(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    return jsonify(
        {
            "generated_at": None,
            "fetched_at": None,
            "positions_value": _db_load_latest_json(user, "positions_value"),
            "traded_markets": _db_load_latest_json(user, "traded_markets"),
        }
    )


@app.route("/api/user/<user>/endpoint_summary")
def api_endpoint_summary(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    endpoint = request.args.get("endpoint", "activity")
    summary = _db_endpoint_summary(user, endpoint)
    summary["endpoint"] = endpoint
    return jsonify(summary)


@app.route("/api/user/<user>/configs", methods=["GET", "POST"])
def api_user_configs(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    if request.method == "GET":
        endpoint = request.args.get("endpoint", "")
        if endpoint:
            return jsonify(_db_get_configs(user, endpoint))
        endpoints = _db_list_endpoints(user)
        payload = {}
        for ep in endpoints:
            payload[ep] = _db_get_configs(user, ep)
        return jsonify(payload)

    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    action = data.get("action", "save")
    config = data.get("config")
    active = data.get("active", "默认")
    if not endpoint or not isinstance(config, dict):
        if action != "delete":
            return jsonify({"error": "invalid payload"}), 400

    entry = _db_get_configs(user, endpoint)
    entry_configs = entry.get("configs", {})

    if action == "delete":
        name = data.get("name")
        if name and name in entry_configs:
            del entry_configs[name]
        entry["configs"] = entry_configs
        entry["active"] = data.get("active", "默认")
        _db_save_configs(user, endpoint, entry)
        return jsonify({"ok": True, "active": entry["active"]})

    entry["active"] = active
    name = config.get("name") or active or "默认"
    entry_configs[name] = config
    entry["configs"] = entry_configs
    _db_save_configs(user, endpoint, entry)
    return jsonify({"ok": True, "active": active, "name": name})


@app.route("/api/user/<user>/records")
def api_records(user: str) -> Any:
    if not _db_exists():
        return _db_missing_response()
    endpoint = request.args.get("endpoint", "activity")
    query = request.args.get("query", "").strip()
    from_ts = request.args.get("from_ts")
    to_ts = request.args.get("to_ts")
    view = request.args.get("view", "compact")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    sort_order = request.args.get("sort", "desc")
    filters_raw = request.args.get("filters", "")

    from_ts_i = int(from_ts) if from_ts and from_ts.isdigit() else None
    to_ts_i = int(to_ts) if to_ts and to_ts.isdigit() else None
    limit = min(limit, 2000)

    column_filters = None
    if filters_raw:
        try:
            candidate = json.loads(filters_raw)
            if isinstance(candidate, dict):
                column_filters = {str(k): str(v) for k, v in candidate.items() if v}
        except json.JSONDecodeError:
            column_filters = None

    db_payload = _load_records_from_db(
        user=user,
        endpoint=endpoint,
        query=query,
        from_ts_i=from_ts_i,
        to_ts_i=to_ts_i,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
        column_filters=column_filters,
    )
    page = db_payload["rows"]
    total = db_payload["total"]
    all_columns = db_payload["all_columns"]

    columns: List[str] = []
    if view == "compact":
        page, columns = apply_compact_view(endpoint, page)

    return jsonify({
        "rows": page,
        "total": total,
        "endpoint": endpoint,
        "limit": limit,
        "offset": offset,
        "columns": columns,
        "all_columns": all_columns,
    })


@app.route("/api/sports/summary")
def api_sports_summary() -> Any:
    manifest = load_sports_manifest(SPORTS_DIR)
    markets = list_sports_markets(manifest)
    summary = {
        "generated_at": manifest.get("generated_at"),
        "start_ts": manifest.get("start_ts"),
        "end_ts": manifest.get("end_ts"),
        "start_ts_utc": manifest.get("start_ts_utc"),
        "end_ts_utc": manifest.get("end_ts_utc"),
        "fidelity": manifest.get("fidelity"),
        "chunk_days": manifest.get("chunk_days"),
        "markets_total": manifest.get("markets_total"),
        "sports_markets_total": manifest.get("sports_markets_total"),
        "available_markets": len(markets),
    }
    return jsonify(summary)


@app.route("/api/sports/markets")
def api_sports_markets() -> Any:
    manifest = load_sports_manifest(SPORTS_DIR)
    query = request.args.get("query", "").strip().lower()
    markets = list_sports_markets(manifest)
    if query:
        filtered = []
        for market in markets:
            text = f"{market.get('question') or ''} {market.get('slug') or ''}".lower()
            if query in text:
                filtered.append(market)
        markets = filtered
    return jsonify({"markets": markets})


@app.route("/api/sports/market/<int:index>")
def api_sports_market(index: int) -> Any:
    manifest = load_sports_manifest(SPORTS_DIR)
    market = resolve_market_entry(manifest, index)
    if not market:
        return jsonify({"error": "market not found"}), 404
    tokens = market.get("tokens") if isinstance(market.get("tokens"), list) else []
    stats = summarize_tokens(tokens)
    payload = dict(market)
    payload["summary"] = stats
    return jsonify(payload)


@app.route("/api/sports/points")
def api_sports_points() -> Any:
    market_index_raw = request.args.get("market_index", "")
    token_id = request.args.get("token_id", "")
    sort_order = request.args.get("sort", "asc")
    limit = int(request.args.get("limit", 1000))
    offset = int(request.args.get("offset", 0))
    from_ts = parse_ts_param(request.args.get("from_ts"))
    to_ts = parse_ts_param(request.args.get("to_ts"))
    include_raw = request.args.get("raw", "0") == "1"

    if not market_index_raw.isdigit():
        return jsonify({"error": "market_index required"}), 400
    if not token_id:
        return jsonify({"error": "token_id required"}), 400
    market_index = int(market_index_raw)

    manifest = load_sports_manifest(SPORTS_DIR)
    market = resolve_market_entry(manifest, market_index)
    if not market:
        return jsonify({"error": "market not found"}), 404

    market_dir = resolve_sports_market_dir(SPORTS_DIR, market)
    if market_dir is None:
        return jsonify({"error": "market dir not found"}), 404
    points_path = market_dir / "points" / f"{token_id}.jsonl"
    if not points_path.exists():
        return jsonify({"error": "points file not found"}), 404

    rows: List[Dict[str, Any]] = []
    min_ts = None
    max_ts = None
    for row in iter_jsonl(points_path):
        if not isinstance(row, dict):
            continue
        ts = row.get("ts")
        if not isinstance(ts, int):
            continue
        if from_ts is not None and ts < from_ts:
            continue
        if to_ts is not None and ts > to_ts:
            continue
        min_ts = ts if min_ts is None else min(min_ts, ts)
        max_ts = ts if max_ts is None else max(max_ts, ts)
        payload = {
            "ts": ts,
            "price": row.get("price"),
        }
        if include_raw:
            payload["raw"] = row.get("raw")
        rows.append(payload)

    total = len(rows)
    if sort_order == "desc":
        rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
    else:
        rows.sort(key=lambda r: r.get("ts", 0))

    if limit <= 0:
        page = rows
    else:
        page = rows[offset : offset + min(limit, 5000)]

    return jsonify({
        "market_index": market_index,
        "token_id": token_id,
        "rows": page,
        "total": total,
        "min_ts": min_ts,
        "max_ts": max_ts,
        "limit": limit,
        "offset": offset,
        "file": str(points_path),
    })


if __name__ == "__main__":
    args = parse_args()
    DATA_DIR = resolve_data_dir(Path(args.data_dir))
    SPORTS_DIR = resolve_sports_dir(Path(args.sports_dir))
    app.run(host=args.host, port=args.port, debug=args.debug)
