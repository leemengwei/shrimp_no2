#!/usr/bin/env python3
"""Ingest user endpoint JSON pages into SQLite for fast dashboard queries.

Example:
  python3 src/ingest_user_activity_to_sqlite.py \
    --data-dir data/polymarket/user_activities \
    --db-path data/polymarket/user_activities/dashboard.db
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


DEFAULT_DATA_DIR = Path("data/polymarket/user_activities")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "dashboard.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Polymarket endpoint JSON pages into SQLite")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Root directory containing per-user endpoint json files",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="SQLite database output path",
    )
    parser.add_argument(
        "--users",
        nargs="*",
        default=None,
        help="Optional list of user addresses to ingest; default ingests all users under data-dir",
    )
    return parser.parse_args()


def list_users(data_dir: Path) -> List[str]:
    if not data_dir.exists():
        return []
    return sorted([p.name for p in data_dir.iterdir() if p.is_dir() and p.name.startswith("0x")])


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_endpoint_files(data_dir: Path, user: str, endpoint: str) -> List[Path]:
    user_dir = data_dir / user
    manifest_path = user_dir / "manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
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
            if candidate.exists():
                base_dir = candidate
        if base_dir is None:
            base_dir = user_dir / "endpoints"

        if file_hint:
            hinted = base_dir / file_hint
            if hinted.exists():
                return [hinted]
            fallback = user_dir / "endpoints" / file_hint
            return [fallback] if fallback.exists() else []

        if base_dir.exists() and base_dir.is_dir():
            pattern = info.get("pattern")
            if isinstance(pattern, str) and "%06d" in pattern:
                glob_pattern = pattern.replace("%06d", "*")
                files = sorted(base_dir.glob(glob_pattern))
                if files:
                    return files
                nested_dir = base_dir / endpoint
                if nested_dir.exists() and nested_dir.is_dir():
                    nested_files = sorted(nested_dir.glob(glob_pattern))
                    if nested_files:
                        return nested_files
            return sorted([p for p in base_dir.iterdir() if p.is_file() and p.suffix == ".json"])

    guess_dir = user_dir / "endpoints" / endpoint
    if guess_dir.exists() and guess_dir.is_dir():
        return sorted([p for p in guess_dir.iterdir() if p.is_file() and p.suffix == ".json"])
    guess_file = user_dir / "endpoints" / f"{endpoint}.json"
    return [guess_file] if guess_file.exists() else []


def iter_rows_from_files(files: Iterable[Path]) -> Iterable[Dict[str, Any]]:
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        try:
            payload = load_json(path)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict):
                    yield row
        elif isinstance(payload, dict):
            yield payload


def extract_ts(row: Dict[str, Any]) -> Optional[int]:
    for key in ("timestamp", "ts", "time", "createdAt", "created_at", "resolvedAt"):
        val = row.get(key)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


def canonical_json(row: Dict[str, Any]) -> str:
    try:
        return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return json.dumps(row, ensure_ascii=False, separators=(",", ":"))


def row_hash(canonical: str) -> str:
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS records (
            user TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            row_hash TEXT NOT NULL,
            ts INTEGER,
            type_upper TEXT,
            row_text TEXT NOT NULL,
            row_json TEXT NOT NULL,
            PRIMARY KEY (user, endpoint, row_hash)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS endpoint_columns (
            user TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            column_name TEXT NOT NULL,
            ord INTEGER NOT NULL,
            PRIMARY KEY (user, endpoint, column_name)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_state (
            user TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            file_path TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            size_bytes INTEGER NOT NULL,
            PRIMARY KEY (user, endpoint, file_path)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_user_endpoint_ts ON records(user, endpoint, ts)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_user_endpoint_type ON records(user, endpoint, type_upper)"
    )


def load_known_columns(conn: sqlite3.Connection, user: str, endpoint: str) -> Tuple[Set[str], int]:
    cur = conn.execute(
        """
        SELECT column_name, ord
        FROM endpoint_columns
        WHERE user = ? AND endpoint = ?
        ORDER BY ord ASC
        """,
        (user, endpoint),
    )
    rows = cur.fetchall()
    if not rows:
        return set(), 0
    known = {r[0] for r in rows}
    next_ord = int(rows[-1][1]) + 1
    return known, next_ord


def file_state(conn: sqlite3.Connection, user: str, endpoint: str, file_path: str) -> Optional[Tuple[int, int]]:
    cur = conn.execute(
        """
        SELECT mtime_ns, size_bytes
        FROM ingest_state
        WHERE user = ? AND endpoint = ? AND file_path = ?
        """,
        (user, endpoint, file_path),
    )
    row = cur.fetchone()
    if not row:
        return None
    return int(row[0]), int(row[1])


def upsert_file_state(
    conn: sqlite3.Connection,
    user: str,
    endpoint: str,
    file_path: str,
    mtime_ns: int,
    size_bytes: int,
) -> None:
    conn.execute(
        """
        INSERT INTO ingest_state(user, endpoint, file_path, mtime_ns, size_bytes)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(user, endpoint, file_path)
        DO UPDATE SET mtime_ns = excluded.mtime_ns, size_bytes = excluded.size_bytes
        """,
        (user, endpoint, file_path, mtime_ns, size_bytes),
    )


def ingest_endpoint(conn: sqlite3.Connection, data_dir: Path, user: str, endpoint: str) -> Tuple[int, int]:
    files = resolve_endpoint_files(data_dir, user, endpoint)
    known_columns, next_ord = load_known_columns(conn, user, endpoint)
    scanned = 0
    inserted = 0
    for path in files:
        if not path.exists() or not path.is_file():
            continue
        st = path.stat()
        key = str(path.resolve())
        prev = file_state(conn, user, endpoint, key)
        if prev and prev == (st.st_mtime_ns, st.st_size):
            continue
        for row in iter_rows_from_files([path]):
            scanned += 1
            canonical = canonical_json(row)
            digest = row_hash(canonical)
            ts = extract_ts(row)
            type_upper = str(row.get("type", "")).upper() if row.get("type") is not None else None
            row_text = canonical.lower()
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO records(
                    user, endpoint, row_hash, ts, type_upper, row_text, row_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user, endpoint, digest, ts, type_upper, row_text, canonical),
            )
            if cur.rowcount and cur.rowcount > 0:
                inserted += 1
            for key_name in row.keys():
                if key_name in known_columns:
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO endpoint_columns(user, endpoint, column_name, ord)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user, endpoint, str(key_name), next_ord),
                )
                known_columns.add(str(key_name))
                next_ord += 1
        upsert_file_state(conn, user, endpoint, key, st.st_mtime_ns, st.st_size)
    return scanned, inserted


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    db_path = Path(args.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    endpoints = [
        "positions",
        "closed_positions",
        "activity",
        "trades",
        "traded_markets",
        "positions_value",
    ]
    users = args.users if args.users else list_users(data_dir)
    if not users:
        print(f"No users found under {data_dir}")
        return

    with sqlite3.connect(db_path) as conn:
        init_db(conn)
        total_scanned = 0
        total_inserted = 0
        for user in users:
            for endpoint in endpoints:
                scanned, inserted = ingest_endpoint(conn, data_dir, user, endpoint)
                conn.commit()
                total_scanned += scanned
                total_inserted += inserted
                print(
                    f"[ingest] user={user} endpoint={endpoint} scanned={scanned} inserted={inserted}",
                    flush=True,
                )
    print(
        f"[done] users={len(users)} total_scanned={total_scanned} total_inserted={total_inserted} db={db_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
