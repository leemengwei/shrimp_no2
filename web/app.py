#!/usr/bin/env python3
"""Local web dashboard for Polymarket user data.

Example:
  python web/app.py --data-dir data/polymarket --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local web dashboard for Polymarket data")
    parser.add_argument("--data-dir", default="data/polymarket", help="Data root directory")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
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
            base_dir = candidate if candidate.exists() else None
        if base_dir is None:
            base_dir = data_dir / user / "endpoints"

        if file_hint:
            return [base_dir / file_hint]
        if base_dir.exists() and base_dir.is_dir():
            pattern = info.get("pattern")
            if isinstance(pattern, str) and "%06d" in pattern:
                glob_pattern = pattern.replace("%06d", "*")
                return sorted(base_dir.glob(glob_pattern))
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
DATA_DIR = Path("data/polymarket")


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/users")
def api_users() -> Any:
    users = list_users(DATA_DIR)
    detailed = []
    for user in users:
        detailed.append({"id": user, "label": resolve_user_label(DATA_DIR, user)})
    return jsonify({"users": detailed})


@app.route("/api/user/<user>/manifest")
def api_manifest(user: str) -> Any:
    manifest = load_manifest(DATA_DIR, user)
    return jsonify(manifest)


@app.route("/api/user/<user>/endpoints")
def api_endpoints(user: str) -> Any:
    manifest = load_manifest(DATA_DIR, user)
    endpoints = []
    if isinstance(manifest, dict) and isinstance(manifest.get("endpoints"), dict):
        endpoints = sorted(manifest["endpoints"].keys())
    else:
        base = DATA_DIR / user / "endpoints"
        if base.exists():
            endpoints = sorted(p.name for p in base.iterdir() if p.is_dir())
    return jsonify({"endpoints": endpoints})


@app.route("/api/user/<user>/summary")
def api_summary(user: str) -> Any:
    manifest = load_manifest(DATA_DIR, user)
    bundle = load_user_bundle(DATA_DIR, user)
    summary = {
        "user": user,
        "generated_at": manifest.get("generated_at"),
        "fetched_at": bundle.get("fetched_at") or manifest.get("fetched_at"),
        "endpoints": manifest.get("endpoints", {}),
    }
    return jsonify(summary)


@app.route("/api/user/<user>/metrics")
def api_metrics(user: str) -> Any:
    return jsonify(load_metrics(DATA_DIR, user))


@app.route("/api/user/<user>/endpoint_summary")
def api_endpoint_summary(user: str) -> Any:
    endpoint = request.args.get("endpoint", "activity")
    manifest = load_manifest(DATA_DIR, user)
    endpoints = manifest.get("endpoints", {}) if isinstance(manifest, dict) else {}
    info = endpoints.get(endpoint) if isinstance(endpoints, dict) else None
    if isinstance(info, dict):
        return jsonify(info)

    files = resolve_endpoint_files(DATA_DIR, user, endpoint)
    rows_iter = read_endpoint_pages(files)
    summary = summarize_rows(rows_iter)
    summary["endpoint"] = endpoint
    return jsonify(summary)


@app.route("/api/user/<user>/configs", methods=["GET", "POST"])
def api_user_configs(user: str) -> Any:
    if request.method == "GET":
        endpoint = request.args.get("endpoint", "")
        configs = load_web_configs(DATA_DIR, user)
        if endpoint:
            payload = configs.get(endpoint, {"active": "默认", "configs": {}})
            return jsonify(payload)
        return jsonify(configs)

    data = request.get_json(silent=True) or {}
    endpoint = data.get("endpoint")
    action = data.get("action", "save")
    config = data.get("config")
    active = data.get("active", "默认")
    if not endpoint or not isinstance(config, dict):
        if action != "delete":
            return jsonify({"error": "invalid payload"}), 400

    configs = load_web_configs(DATA_DIR, user)
    entry = configs.get(endpoint, {"active": "默认", "configs": {}})
    entry_configs = entry.get("configs", {})

    if action == "delete":
        name = data.get("name")
        if name and name in entry_configs:
            del entry_configs[name]
        entry["configs"] = entry_configs
        entry["active"] = data.get("active", "默认")
        configs[endpoint] = entry
        save_web_configs(DATA_DIR, user, configs)
        return jsonify({"ok": True, "active": entry["active"]})

    entry["active"] = active
    name = config.get("name") or active or "默认"
    entry_configs[name] = config
    entry["configs"] = entry_configs
    configs[endpoint] = entry
    save_web_configs(DATA_DIR, user, configs)
    return jsonify({"ok": True, "active": active, "name": name})


@app.route("/api/user/<user>/records")
def api_records(user: str) -> Any:
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

    files = resolve_endpoint_files(DATA_DIR, user, endpoint)
    if not files:
        return jsonify({"rows": [], "total": 0, "endpoint": endpoint})

    rows_iter = read_endpoint_pages(files)
    if endpoint == "activity":
        def _filter_yield(rows: Iterable[Any]) -> Iterable[Any]:
            for row in rows:
                if isinstance(row, dict) and str(row.get("type", "")).upper() == "YIELD":
                    continue
                yield row
        rows_iter = _filter_yield(rows_iter)
    column_filters = None
    if filters_raw:
        try:
            candidate = json.loads(filters_raw)
            if isinstance(candidate, dict):
                column_filters = {str(k): str(v) for k, v in candidate.items() if v}
        except json.JSONDecodeError:
            column_filters = None

    filtered, all_columns = filter_rows(rows_iter, query, from_ts_i, to_ts_i, column_filters)

    if sort_order in ("asc", "desc"):
        filtered.sort(
            key=lambda row: extract_ts(row) if extract_ts(row) is not None else -1,
            reverse=sort_order == "desc",
        )
    page, total = paginate(filtered, limit, offset)
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


if __name__ == "__main__":
    args = parse_args()
    DATA_DIR = Path(args.data_dir)
    app.run(host=args.host, port=args.port, debug=args.debug)
