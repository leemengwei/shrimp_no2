#!/usr/bin/env python3
"""High-throughput real-time sports market price collector for Polymarket.

Example:
  python3 src/stream_sports_prices.py \
    --output data/realtime/sports_ticks.jsonl \
    --snapshot-output data/realtime/sports_latest_snapshot.json \
    --batch-size 350 \
    --max-connections 10
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import signal
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

GAMMA_API = "https://gamma-api.polymarket.com"
DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_USER_AGENT = "polymarket-research-realtime/1.0"


@dataclass
class CollectorStats:
    messages: int = 0
    events: int = 0
    reconnects: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect high-frequency real-time price updates for active Polymarket sports markets."
        )
    )
    parser.add_argument(
        "--output",
        default="data/realtime/sports_ticks.jsonl",
        help="Output JSONL file path for tick-level raw events",
    )
    parser.add_argument(
        "--snapshot-output",
        default="data/realtime/sports_latest_snapshot.json",
        help="Output JSON snapshot path for latest price per asset id",
    )
    parser.add_argument("--batch-size", type=int, default=400, help="Asset ids per websocket connection")
    parser.add_argument("--max-connections", type=int, default=8, help="Max concurrent websocket connections")
    parser.add_argument(
        "--snapshot-interval", type=float, default=5.0, help="Seconds between snapshot file updates"
    )
    parser.add_argument("--log-interval", type=float, default=10.0, help="Seconds between throughput logs")
    parser.add_argument("--flush-interval", type=float, default=1.0, help="Seconds between output flushes")
    parser.add_argument(
        "--flush-lines",
        type=int,
        default=400,
        help="Flush output every N lines (in addition to flush interval)",
    )
    parser.add_argument("--ws-url", default=DEFAULT_WS_URL, help="CLOB websocket endpoint")
    parser.add_argument(
        "--sports-tag",
        default="Sports",
        help="Gamma markets tag/category used to filter sports markets",
    )
    parser.add_argument("--limit-markets", type=int, default=0, help="Limit markets for testing. 0 means no limit")
    parser.add_argument(
        "--disable-ping",
        action="store_true",
        help="Disable websocket ping interval (useful for some proxy setups)",
    )
    return parser.parse_args()


def log(message: str) -> None:
    print(message, flush=True)


def _http_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    req = urllib.request.Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def is_sports_market(market: Dict[str, Any], sports_tag: str) -> bool:
    needle = sports_tag.lower().strip()
    category = str(market.get("category") or "").lower()
    if needle and needle in category:
        return True

    tags = market.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and needle in tag.lower():
                return True
            if isinstance(tag, dict):
                label = str(tag.get("label") or tag.get("name") or "").lower()
                slug = str(tag.get("slug") or "").lower()
                if needle in label or needle in slug:
                    return True
    return False


def _fetch_markets_page(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = _http_json(f"{GAMMA_API}/markets", params)
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def fetch_sports_markets(sports_tag: str, limit_markets: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    offset = 0
    page_limit = 500

    while True:
        payload = _fetch_markets_page(
            {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "tag": sports_tag,
                "limit": page_limit,
                "offset": offset,
            }
        )
        if not payload:
            break
        rows.extend(payload)
        if 0 < limit_markets <= len(rows):
            return rows[:limit_markets]
        if len(payload) < page_limit:
            break
        offset += page_limit

    # Fallback: Some deployments may not support tag filter.
    if rows:
        return rows[:limit_markets] if limit_markets > 0 else rows

    offset = 0
    while True:
        payload = _fetch_markets_page(
            {
                "active": "true",
                "closed": "false",
                "archived": "false",
                "limit": page_limit,
                "offset": offset,
            }
        )
        if not payload:
            break
        for row in payload:
            if is_sports_market(row, sports_tag):
                rows.append(row)
                if 0 < limit_markets <= len(rows):
                    return rows
        if len(payload) < page_limit:
            break
        offset += page_limit
    return rows


def _coerce_token_ids(market: Dict[str, Any]) -> List[str]:
    token_ids: List[str] = []
    raw = market.get("clobTokenIds")
    if isinstance(raw, str) and raw.strip():
        with contextlib.suppress(json.JSONDecodeError):
            decoded = json.loads(raw)
            if isinstance(decoded, list):
                token_ids.extend(str(v) for v in decoded if str(v).strip())

    tokens = market.get("tokens")
    if isinstance(tokens, list):
        for item in tokens:
            if not isinstance(item, dict):
                continue
            token_id = item.get("token_id") or item.get("tokenId") or item.get("id")
            if token_id is not None:
                token_ids.append(str(token_id))
    return token_ids


def extract_asset_ids(markets: Sequence[Dict[str, Any]]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for market in markets:
        for token_id in _coerce_token_ids(market):
            if token_id and token_id not in seen:
                seen.add(token_id)
                out.append(token_id)
    return out


def chunked(items: Sequence[str], size: int) -> Iterable[List[str]]:
    for idx in range(0, len(items), size):
        yield list(items[idx : idx + size])


def make_connection_batches(asset_ids: Sequence[str], batch_size: int, max_connections: int) -> List[List[str]]:
    initial_batches = list(chunked(list(asset_ids), max(1, batch_size)))
    if max_connections <= 0 or len(initial_batches) <= max_connections:
        return initial_batches

    # Merge chunks round-robin into max_connections buckets to avoid dropping any asset ids.
    merged: List[List[str]] = [[] for _ in range(max_connections)]
    for idx, batch in enumerate(initial_batches):
        merged[idx % max_connections].extend(batch)
    return [bucket for bucket in merged if bucket]


def normalize_event(payload: Dict[str, Any], connection_id: int) -> Dict[str, Any]:
    return {
        "recv_ts": time.time(),
        "connection_id": connection_id,
        "event_type": payload.get("event_type") or payload.get("type"),
        "market": payload.get("market") or payload.get("market_id"),
        "asset_id": payload.get("asset_id") or payload.get("asset") or payload.get("token_id"),
        "price": payload.get("price"),
        "best_bid": payload.get("best_bid") or payload.get("bid"),
        "best_ask": payload.get("best_ask") or payload.get("ask"),
        "side": payload.get("side"),
        "size": payload.get("size") or payload.get("amount"),
        "source_ts": payload.get("timestamp") or payload.get("ts"),
        "raw": payload,
    }


def maybe_collect_events(message: Any, connection_id: int) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if isinstance(message, list):
        for item in message:
            if isinstance(item, dict):
                events.append(normalize_event(item, connection_id))
        return events

    if isinstance(message, dict):
        data = message.get("data")
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    events.append(normalize_event(item, connection_id))
            return events
        if any(k in message for k in ("asset_id", "asset", "token_id", "price", "best_bid", "best_ask")):
            events.append(normalize_event(message, connection_id))
    return events


async def stream_batch(
    websocket_url: str,
    connection_id: int,
    asset_ids: List[str],
    queue: asyncio.Queue,
    stop_event: asyncio.Event,
    stats: CollectorStats,
    disable_ping: bool,
) -> None:
    import websockets

    subscribe_payload = {
        "type": "subscribe",
        "channel": "market",
        # Keep both spellings for compatibility with possible server variants.
        "asset_ids": asset_ids,
        "assets_ids": asset_ids,
    }

    backoff = 1.0
    while not stop_event.is_set():
        try:
            ping_interval = None if disable_ping else 20
            async with websockets.connect(
                websocket_url,
                ping_interval=ping_interval,
                max_queue=2048,
                close_timeout=5,
            ) as ws:
                await ws.send(json.dumps(subscribe_payload, ensure_ascii=False))
                backoff = 1.0
                log(f"[ws {connection_id}] subscribed assets={len(asset_ids)} sample={asset_ids[:2]}")

                while not stop_event.is_set():
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    stats.messages += 1
                    with contextlib.suppress(json.JSONDecodeError):
                        parsed = json.loads(raw_msg)
                        events = maybe_collect_events(parsed, connection_id)
                        stats.events += len(events)
                        for event in events:
                            await queue.put(event)
        except asyncio.TimeoutError:
            stats.reconnects += 1
            log(f"[ws {connection_id}] timeout, reconnecting")
        except Exception as exc:  # noqa: BLE001
            stats.reconnects += 1
            log(f"[ws {connection_id}] error={exc}, reconnecting")

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 15)


async def writer_loop(
    queue: asyncio.Queue,
    out_path: Path,
    snapshot_path: Path,
    snapshot_interval: float,
    flush_interval: float,
    flush_lines: int,
    stop_event: asyncio.Event,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    latest_by_asset: Dict[str, Dict[str, Any]] = {}
    buffer: List[str] = []
    last_flush_ts = time.monotonic()
    last_snapshot_ts = time.monotonic()

    with out_path.open("a", encoding="utf-8") as file_obj:
        while True:
            if stop_event.is_set() and queue.empty():
                break

            try:
                item = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                item = None

            if item is not None:
                asset_id = str(item.get("asset_id") or "")
                if asset_id:
                    latest_by_asset[asset_id] = item
                buffer.append(json.dumps(item, ensure_ascii=False))

            now = time.monotonic()
            if buffer and (len(buffer) >= flush_lines or now - last_flush_ts >= flush_interval):
                file_obj.write("\n".join(buffer) + "\n")
                file_obj.flush()
                os.fsync(file_obj.fileno())
                buffer.clear()
                last_flush_ts = now

            if now - last_snapshot_ts >= snapshot_interval:
                snapshot_payload = {
                    "updated_at": time.time(),
                    "asset_count": len(latest_by_asset),
                    "latest": latest_by_asset,
                }
                snapshot_path.write_text(
                    json.dumps(snapshot_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                last_snapshot_ts = now

        if buffer:
            file_obj.write("\n".join(buffer) + "\n")
            file_obj.flush()
            os.fsync(file_obj.fileno())

    if latest_by_asset:
        snapshot_payload = {
            "updated_at": time.time(),
            "asset_count": len(latest_by_asset),
            "latest": latest_by_asset,
        }
        snapshot_path.write_text(json.dumps(snapshot_payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def metrics_loop(stats: CollectorStats, interval_s: float, stop_event: asyncio.Event) -> None:
    last_messages = 0
    last_events = 0
    while not stop_event.is_set():
        await asyncio.sleep(interval_s)
        delta_messages = stats.messages - last_messages
        delta_events = stats.events - last_events
        last_messages = stats.messages
        last_events = stats.events
        log(
            "[metrics] "
            f"messages_total={stats.messages} messages_rate={delta_messages / interval_s:.1f}/s "
            f"events_total={stats.events} events_rate={delta_events / interval_s:.1f}/s "
            f"reconnects={stats.reconnects}"
        )


async def async_main(args: argparse.Namespace) -> None:
    try:
        import websockets  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency `websockets`. Install with: python3 -m pip install websockets"
        ) from exc

    markets = fetch_sports_markets(args.sports_tag, args.limit_markets)
    if not markets:
        raise SystemExit("No active sports markets found. Check --sports-tag or network/proxy setup.")

    asset_ids = extract_asset_ids(markets)
    if not asset_ids:
        raise SystemExit("No asset ids found in sports markets payload.")

    batches = make_connection_batches(asset_ids, args.batch_size, args.max_connections)
    if not batches:
        raise SystemExit("No subscription batches were generated; check --batch-size and asset extraction.")

    covered_assets = {asset_id for batch in batches for asset_id in batch}
    if len(covered_assets) != len(set(asset_ids)):
        raise SystemExit("Batching error: not all asset ids are covered. Refusing to start.")

    log(
        f"[init] markets={len(markets)} unique_assets={len(asset_ids)} "
        f"connections={len(batches)} batch_size={args.batch_size}"
    )

    queue: asyncio.Queue = asyncio.Queue(maxsize=200_000)
    stop_event = asyncio.Event()
    stats = CollectorStats()

    loop = asyncio.get_running_loop()

    def _request_stop() -> None:
        if not stop_event.is_set():
            log("[signal] stop requested, draining queue...")
            stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _request_stop)

    writer_task = asyncio.create_task(
        writer_loop(
            queue=queue,
            out_path=Path(args.output),
            snapshot_path=Path(args.snapshot_output),
            snapshot_interval=max(1.0, args.snapshot_interval),
            flush_interval=max(0.2, args.flush_interval),
            flush_lines=max(1, args.flush_lines),
            stop_event=stop_event,
        )
    )
    metric_task = asyncio.create_task(metrics_loop(stats, max(1.0, args.log_interval), stop_event))

    workers = [
        asyncio.create_task(
            stream_batch(
                websocket_url=args.ws_url,
                connection_id=idx,
                asset_ids=batch,
                queue=queue,
                stop_event=stop_event,
                stats=stats,
                disable_ping=args.disable_ping,
            )
        )
        for idx, batch in enumerate(batches, start=1)
    ]

    try:
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        pass
    finally:
        stop_event.set()
        for worker in workers:
            worker.cancel()
        await writer_task
        metric_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await metric_task


def main() -> None:
    args = parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
