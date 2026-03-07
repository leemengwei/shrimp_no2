#!/usr/bin/env python3
"""Realtime Polymarket market discovery and price monitoring via CLOB.

This script supports two approaches:
1) SDK mode (preferred): use `py-clob-client` if installed.
2) HTTP mode: use public CLOB/Gamma endpoints directly via urllib.

Example:
  python3 src/realtime_clob_market_monitor.py \
    --mode sdk --query election --limit 5 --watch-seconds 30

  python3 src/realtime_clob_market_monitor.py \
    --mode http --query bitcoin --limit 5 --watch-seconds 30
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


@dataclass
class OutcomeToken:
    token_id: str
    outcome: str


@dataclass
class Market:
    market_id: str
    question: str
    slug: str
    outcomes: List[OutcomeToken]


class ClobMonitorError(RuntimeError):
    """Custom error for market monitor failures."""


def http_get_json(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "shrimp-no2-realtime-monitor/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ClobMonitorError(f"Network error while requesting {url}: {exc}") from exc


def _parse_outcomes(raw_market: Dict[str, Any]) -> List[OutcomeToken]:
    token_ids = raw_market.get("clobTokenIds") or raw_market.get("token_ids")
    outcomes = raw_market.get("outcomes")

    parsed_token_ids: List[str] = []
    if isinstance(token_ids, list):
        parsed_token_ids = [str(x) for x in token_ids]
    elif isinstance(token_ids, str):
        try:
            data = json.loads(token_ids)
            if isinstance(data, list):
                parsed_token_ids = [str(x) for x in data]
        except json.JSONDecodeError:
            parsed_token_ids = [token_ids]

    parsed_outcomes: List[str] = []
    if isinstance(outcomes, list):
        parsed_outcomes = [str(x) for x in outcomes]
    elif isinstance(outcomes, str):
        try:
            data = json.loads(outcomes)
            if isinstance(data, list):
                parsed_outcomes = [str(x) for x in data]
        except json.JSONDecodeError:
            parsed_outcomes = [outcomes]

    max_len = max(len(parsed_token_ids), len(parsed_outcomes))
    pairs: List[OutcomeToken] = []
    for index in range(max_len):
        token_id = parsed_token_ids[index] if index < len(parsed_token_ids) else ""
        outcome = parsed_outcomes[index] if index < len(parsed_outcomes) else f"OUTCOME_{index}"
        if token_id:
            pairs.append(OutcomeToken(token_id=token_id, outcome=outcome))
    return pairs


def parse_market(raw_market: Dict[str, Any]) -> Market:
    return Market(
        market_id=str(raw_market.get("id") or raw_market.get("conditionId") or ""),
        question=str(raw_market.get("question") or raw_market.get("name") or ""),
        slug=str(raw_market.get("slug") or ""),
        outcomes=_parse_outcomes(raw_market),
    )


class HttpClobGateway:
    """Direct CLOB + Gamma endpoint access (no SDK dependency)."""

    def discover_markets(self, query: str, limit: int) -> List[Market]:
        params = {"limit": limit, "active": "true", "closed": "false", "archived": "false"}
        if query:
            params["query"] = query
        raw = http_get_json(f"{GAMMA_API}/markets", params)
        if not isinstance(raw, list):
            raise ClobMonitorError("Unexpected response from Gamma market endpoint")
        markets = [parse_market(m) for m in raw]
        return [m for m in markets if m.outcomes][:limit]

    def get_midpoint_price(self, token_id: str) -> Optional[float]:
        payload = http_get_json(f"{CLOB_API}/midpoint", {"token_id": token_id})
        midpoint = payload.get("mid") if isinstance(payload, dict) else None
        if midpoint is None:
            return None
        return float(midpoint)


class SdkClobGateway:
    """CLOB SDK wrapper with a compatible interface for this script."""

    def __init__(self) -> None:
        try:
            from py_clob_client.client import ClobClient  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ClobMonitorError(
                "SDK mode requires py-clob-client. Install with: pip install py-clob-client"
            ) from exc

        self._client = ClobClient(CLOB_API)

    def discover_markets(self, query: str, limit: int) -> List[Market]:
        markets: List[Dict[str, Any]] = []

        if hasattr(self._client, "get_markets"):
            response = self._client.get_markets(next_cursor="MA==")
            if isinstance(response, dict):
                data = response.get("data")
                if isinstance(data, list):
                    markets = data
        if not markets:
            # Keep an HTTP fallback so SDK mode still works for discovery if SDK surface changes.
            markets = http_get_json(
                f"{GAMMA_API}/markets",
                {
                    "limit": limit,
                    "active": "true",
                    "closed": "false",
                    "archived": "false",
                    "query": query,
                },
            )

        parsed = [parse_market(m) for m in markets if isinstance(m, dict)]
        if query:
            query_l = query.lower()
            parsed = [m for m in parsed if query_l in m.question.lower()]
        return [m for m in parsed if m.outcomes][:limit]

    def get_midpoint_price(self, token_id: str) -> Optional[float]:
        if hasattr(self._client, "get_midpoint"):
            payload = self._client.get_midpoint(token_id=token_id)
            if isinstance(payload, dict):
                midpoint = payload.get("mid")
                if midpoint is not None:
                    return float(midpoint)
        # Fallback: direct endpoint for compatibility.
        payload = http_get_json(f"{CLOB_API}/midpoint", {"token_id": token_id})
        midpoint = payload.get("mid") if isinstance(payload, dict) else None
        return float(midpoint) if midpoint is not None else None


def utc_now_text() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def iter_tokens(markets: Iterable[Market]) -> Iterable[tuple[Market, OutcomeToken]]:
    for market in markets:
        for token in market.outcomes:
            yield market, token


def print_discovery(markets: List[Market]) -> None:
    print(f"[{utc_now_text()}] discovered {len(markets)} markets")
    for idx, market in enumerate(markets, start=1):
        outcomes_text = ", ".join(f"{o.outcome}:{o.token_id}" for o in market.outcomes)
        print(f"  {idx}. {market.question}")
        print(f"     slug={market.slug}")
        print(f"     outcomes={outcomes_text}")


def monitor_prices(gateway: Any, markets: List[Market], interval_s: float, watch_seconds: int) -> None:
    previous_prices: Dict[str, Optional[float]] = {}
    start = time.time()

    while True:
        now = time.time()
        if watch_seconds > 0 and now - start >= watch_seconds:
            print(f"[{utc_now_text()}] monitoring window ended")
            return

        print(f"[{utc_now_text()}] price snapshot")
        for market, token in iter_tokens(markets):
            try:
                price = gateway.get_midpoint_price(token.token_id)
            except Exception as exc:  # noqa: BLE001
                print(f"  [warn] token={token.token_id} outcome={token.outcome} err={exc}")
                continue

            old = previous_prices.get(token.token_id)
            delta = None if old is None or price is None else price - old
            previous_prices[token.token_id] = price
            delta_text = "" if delta is None else f" delta={delta:+.4f}"
            print(
                f"  market='{market.question[:70]}' outcome={token.outcome} "
                f"token={token.token_id} mid={price}{delta_text}"
            )
        time.sleep(interval_s)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Realtime market discovery and price query for Polymarket CLOB"
    )
    parser.add_argument("--mode", choices=("sdk", "http"), default="sdk")
    parser.add_argument("--query", default="", help="Market keyword filter")
    parser.add_argument("--limit", type=int, default=5, help="Number of markets to watch")
    parser.add_argument(
        "--interval", type=float, default=3.0, help="Snapshot interval in seconds"
    )
    parser.add_argument(
        "--watch-seconds",
        type=int,
        default=60,
        help="Stop monitoring after N seconds; <=0 means run forever",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        gateway = SdkClobGateway() if args.mode == "sdk" else HttpClobGateway()
        markets = gateway.discover_markets(query=args.query, limit=args.limit)
        if not markets:
            raise SystemExit("No markets discovered. Try another --query value.")
        print_discovery(markets)
        monitor_prices(gateway, markets, interval_s=args.interval, watch_seconds=args.watch_seconds)
    except ClobMonitorError as exc:
        raise SystemExit(f"[error] {exc}") from exc


if __name__ == "__main__":
    main()
