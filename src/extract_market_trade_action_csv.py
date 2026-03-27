#!/usr/bin/env python3
"""Extract per-market CSV from user activity + market trades/clob history.

This script builds one CSV per market with separated price sources:
- trades price history (`*_trades.jsonl`)
- clob price history (`*_clob.jsonl`)
and user trade actions from activity endpoint.

Example:
  python3 src/extract_market_trade_action_csv.py 0x2005d16a84ceefa912d4e380cd32e7ff827875ea

Example with plots:
  python3 src/extract_market_trade_action_csv.py \
    0x2005d16a84ceefa912d4e380cd32e7ff827875ea \
    --plot
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class MarketToken:
    token_id: str
    trades_file: Path
    clob_file: Optional[Path]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract per-market CSV with separated trades/clob price series and "
            "user buy/sell actions for two token directions."
        )
    )
    parser.add_argument("userid", help="Wallet address")
    parser.add_argument(
        "--activity-dir",
        type=Path,
        default=None,
        help="Default: data/polymarket/user_activities/<userid>/endpoints/activity",
    )
    parser.add_argument(
        "--markets-dir",
        type=Path,
        default=None,
        help="Default: data/market_price_by_clob_and_trades/by_user/<userid>/markets",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Default: data/analysis/market_trade_action_csv/<userid>",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Also generate per-market PNG visualization",
    )
    parser.add_argument(
        "--max-markets",
        type=int,
        default=0,
        help="Optional limit for number of markets to process (0 means all)",
    )
    parser.add_argument("--quiet", action="store_true", help="Disable progress logs")
    return parser.parse_args()


def to_int(v: Any, default: int = 0) -> int:
    if v is None:
        return default
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return default
        try:
            return int(float(s))
        except ValueError:
            return default
    return default


def to_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            return default
    return default


def iter_activity_rows(activity_dir: Path) -> Iterable[Dict[str, Any]]:
    for f in sorted(activity_dir.glob("*.json")):
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for row in payload:
            if isinstance(row, dict):
                yield row


def load_user_actions(activity_dir: Path) -> Dict[Tuple[str, str, int], float]:
    """Return signed shares by (condition_id, token_id, timestamp)."""
    out: Dict[Tuple[str, str, int], float] = defaultdict(float)
    for row in iter_activity_rows(activity_dir):
        if str(row.get("type") or "").strip().upper() != "TRADE":
            continue
        cid = str(row.get("conditionId") or "").strip().lower()
        token_id = str(row.get("asset") or "").strip()
        ts = to_int(row.get("timestamp"))
        size = to_float(row.get("size"))
        side = str(row.get("side") or "").strip().upper()
        if not cid or not token_id or ts <= 0 or size <= 0:
            continue
        signed = size if side == "BUY" else (-size if side == "SELL" else 0.0)
        if signed == 0.0:
            continue
        out[(cid, token_id, ts)] += signed
    return out


def load_market_tokens(manifest_path: Path) -> Tuple[str, str, List[MarketToken]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cid = str(payload.get("condition_id") or "").strip().lower()
    slug = str(payload.get("slug") or "").strip()

    tokens_raw = payload.get("tokens") if isinstance(payload.get("tokens"), list) else []
    tokens: List[MarketToken] = []
    for t in tokens_raw:
        if not isinstance(t, dict):
            continue
        token_id = str(t.get("token_id") or "").strip()
        tf = t.get("trades_output_file")
        if not token_id or not isinstance(tf, str) or not tf.strip():
            continue
        trade_path = Path(tf)
        if not trade_path.is_absolute():
            # Backward-compatible path resolution:
            # 1) path relative to repo cwd (common in older manifests)
            # 2) path relative to manifest directory
            cwd_candidate = Path.cwd() / trade_path
            if cwd_candidate.exists():
                trade_path = cwd_candidate.resolve()
            else:
                trade_path = (manifest_path.parent / trade_path).resolve()
        if trade_path.exists():
            clob_path: Optional[Path] = None
            cf = t.get("clob_output_file")
            if isinstance(cf, str) and cf.strip():
                cp = Path(cf)
                if not cp.is_absolute():
                    cwd_candidate = Path.cwd() / cp
                    if cwd_candidate.exists():
                        cp = cwd_candidate.resolve()
                    else:
                        cp = (manifest_path.parent / cp).resolve()
                if cp.exists():
                    clob_path = cp
            tokens.append(MarketToken(token_id=token_id, trades_file=trade_path, clob_file=clob_path))
    return cid, slug, tokens


def load_prices(path: Path) -> Dict[int, float]:
    """Load timestamp -> price from one source jsonl file."""
    prices: Dict[int, float] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = to_int(obj.get("t"))
            p = to_float(obj.get("p"), default=-1.0)
            if ts <= 0 or p < 0:
                continue
            prices[ts] = p
    return prices


def maybe_plot(csv_rows: List[Dict[str, Any]], title: str, out_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt  # type: ignore
        import matplotlib.dates as mdates  # type: ignore
        import numpy as np  # type: ignore
        from matplotlib.ticker import MaxNLocator, FormatStrFormatter  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise SystemExit(f"--plot requested but matplotlib is unavailable: {exc}")

    if not csv_rows:
        return

    def forward_fill(arr: np.ndarray) -> np.ndarray:
        out = arr.copy()
        last = np.nan
        for i in range(len(out)):
            if np.isnan(out[i]):
                out[i] = last
            else:
                last = out[i]
        return out

    def parse_price(v: Any) -> float:
        if v == "" or v is None:
            return np.nan
        return float(v)

    xs_dt = [datetime.fromtimestamp(int(r["timestamp"]), tz=timezone.utc) for r in csv_rows]
    t1_clob = np.array([parse_price(r["token1_clob_price"]) for r in csv_rows], dtype=float)
    t2_clob = np.array([parse_price(r["token2_clob_price"]) for r in csv_rows], dtype=float)
    t1_trade = np.array([parse_price(r["token1_trades_price"]) for r in csv_rows], dtype=float)
    t2_trade = np.array([parse_price(r["token2_trades_price"]) for r in csv_rows], dtype=float)
    a1 = np.array([float(r["token1_action"]) for r in csv_rows], dtype=float)
    a2 = np.array([float(r["token2_action"]) for r in csv_rows], dtype=float)

    # Build continuous clob display lines from sparse clob updates.
    t1_clob_line = forward_fill(t1_clob)
    t2_clob_line = forward_fill(t2_clob)

    # For action markers, use nearest available displayed price (forward-filled).
    t1_ref = np.where(~np.isnan(t1_clob_line), t1_clob_line, forward_fill(t1_trade))
    t2_ref = np.where(~np.isnan(t2_clob_line), t2_clob_line, forward_fill(t2_trade))

    # Position curves on secondary y-axis.
    pos1 = np.cumsum(a1)
    pos2 = np.cumsum(a2)

    fig, ax = plt.subplots(1, 1, figsize=(16, 8))
    # CLOB as lines.
    ax.plot_date(xs_dt, t1_clob_line, "-", linewidth=1.4, alpha=0.95, color="#1f77b4", label="token1 clob")
    ax.plot_date(xs_dt, t2_clob_line, "-", linewidth=1.4, alpha=0.95, color="#d62728", label="token2 clob")
    # Trades as points.
    ax.plot_date(
        xs_dt,
        t1_trade,
        "o",
        markersize=5.0,
        alpha=0.85,
        markeredgewidth=0.0,
        color="#1f77b4",
        label="token1 trades",
    )
    ax.plot_date(
        xs_dt,
        t2_trade,
        "o",
        markersize=5.0,
        alpha=0.85,
        markeredgewidth=0.0,
        color="#d62728",
        label="token2 trades",
    )

    # Buy/Sell markers like stock chart annotations.
    t1_buy = (a1 > 0) & ~np.isnan(t1_ref)
    t1_sell = (a1 < 0) & ~np.isnan(t1_ref)
    t2_buy = (a2 > 0) & ~np.isnan(t2_ref)
    t2_sell = (a2 < 0) & ~np.isnan(t2_ref)

    xarr = np.array(xs_dt)
    ax.scatter(
        xarr[t1_buy], t1_ref[t1_buy], marker="^", s=88, color="#00a650", edgecolors="black",
        linewidths=0.4, zorder=6, label="token1 buy"
    )
    ax.scatter(
        xarr[t1_sell], t1_ref[t1_sell], marker="v", s=88, color="#00a650", edgecolors="black",
        linewidths=0.4, zorder=6, label="token1 sell"
    )
    ax.scatter(
        xarr[t2_buy], t2_ref[t2_buy], marker="^", s=88, color="#ff8c00", edgecolors="black",
        linewidths=0.4, zorder=6, label="token2 buy"
    )
    ax.scatter(
        xarr[t2_sell], t2_ref[t2_sell], marker="v", s=88, color="#ff8c00", edgecolors="black",
        linewidths=0.4, zorder=6, label="token2 sell"
    )

    ax.set_title(title)
    ax.set_ylabel("price")
    ax.set_xlabel("time (UTC)")
    ax.grid(alpha=0.25)

    # Reduce tick crowding.
    ax.yaxis.set_major_locator(MaxNLocator(nbins=10))
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.3f"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d %H:%M"))
    ax.tick_params(axis="x", labelrotation=30)

    ax_pos = ax.twinx()
    ax_pos.plot_date(xs_dt, pos1, "-", linewidth=1.0, alpha=0.8, color="#17becf", label="token1 position")
    ax_pos.plot_date(xs_dt, pos2, "-", linewidth=1.0, alpha=0.8, color="#9467bd", label="token2 position")
    ax_pos.set_ylabel("position (shares)")
    ax_pos.yaxis.set_major_locator(MaxNLocator(nbins=10))

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax_pos.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="best", ncol=3, fontsize=9)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    user = str(args.userid).strip().lower()
    if not user:
        raise SystemExit("userid is required")

    activity_dir = args.activity_dir or Path("data/polymarket/user_activities") / user / "endpoints" / "activity"
    markets_dir = args.markets_dir or Path("data/market_price_by_clob_and_trades/by_user") / user / "markets"
    output_dir = args.output_dir or Path("data/analysis/market_trade_action_csv") / user

    def log(msg: str) -> None:
        if not args.quiet:
            print(f"[extract_market_trade_action_csv] {msg}", flush=True)

    if not activity_dir.exists():
        raise SystemExit(f"activity dir not found: {activity_dir}")
    if not markets_dir.exists():
        raise SystemExit(f"markets dir not found: {markets_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_dir = output_dir / "plots"

    log("loading activity actions...")
    actions = load_user_actions(activity_dir)
    log(f"loaded action keys={len(actions)}")

    market_dirs = sorted([p for p in markets_dir.iterdir() if p.is_dir()])
    if args.max_markets > 0:
        market_dirs = market_dirs[: args.max_markets]

    written_csv = 0
    written_plot = 0
    skipped = 0

    for idx, mdir in enumerate(market_dirs, start=1):
        manifest_path = mdir / "manifest.json"
        if not manifest_path.exists():
            skipped += 1
            continue

        try:
            condition_id, slug, tokens = load_market_tokens(manifest_path)
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue

        if len(tokens) < 2:
            skipped += 1
            continue

        token1 = tokens[0]
        token2 = tokens[1]
        token1_trades_prices = load_prices(token1.trades_file)
        token2_trades_prices = load_prices(token2.trades_file)
        token1_clob_prices = load_prices(token1.clob_file) if token1.clob_file else {}
        token2_clob_prices = load_prices(token2.clob_file) if token2.clob_file else {}

        ts_set = (
            set(token1_trades_prices.keys())
            | set(token2_trades_prices.keys())
            | set(token1_clob_prices.keys())
            | set(token2_clob_prices.keys())
        )
        action_ts_1 = {
            ts for (cid, tid, ts), _v in actions.items() if cid == condition_id and tid == token1.token_id
        }
        action_ts_2 = {
            ts for (cid, tid, ts), _v in actions.items() if cid == condition_id and tid == token2.token_id
        }
        ts_set |= action_ts_1
        ts_set |= action_ts_2

        if not ts_set:
            skipped += 1
            continue

        rows: List[Dict[str, Any]] = []
        last_t1_trade: Optional[float] = None
        last_t2_trade: Optional[float] = None
        last_t1_clob: Optional[float] = None
        last_t2_clob: Optional[float] = None
        for ts in sorted(ts_set):
            t1_trade = token1_trades_prices.get(ts, "")
            t2_trade = token2_trades_prices.get(ts, "")
            t1_clob = token1_clob_prices.get(ts, "")
            t2_clob = token2_clob_prices.get(ts, "")
            a1 = actions.get((condition_id, token1.token_id, ts), 0.0)
            a2 = actions.get((condition_id, token2.token_id, ts), 0.0)

            changed = False
            if t1_trade != "":
                changed = changed or (last_t1_trade is None or float(t1_trade) != last_t1_trade)
                last_t1_trade = float(t1_trade)
            if t2_trade != "":
                changed = changed or (last_t2_trade is None or float(t2_trade) != last_t2_trade)
                last_t2_trade = float(t2_trade)
            if t1_clob != "":
                changed = changed or (last_t1_clob is None or float(t1_clob) != last_t1_clob)
                last_t1_clob = float(t1_clob)
            if t2_clob != "":
                changed = changed or (last_t2_clob is None or float(t2_clob) != last_t2_clob)
                last_t2_clob = float(t2_clob)

            # Compress dense clob/trades snapshots:
            # keep only price-change points, or points with user actions.
            if not changed and a1 == 0.0 and a2 == 0.0:
                continue

            rows.append(
                {
                    "timestamp": ts,
                    "condition_id": condition_id,
                    "token1_id": token1.token_id,
                    "token2_id": token2.token_id,
                    "token1_trades_price": t1_trade,
                    "token2_trades_price": t2_trade,
                    "token1_clob_price": t1_clob,
                    "token2_clob_price": t2_clob,
                    "token1_action": a1,
                    "token2_action": a2,
                }
            )

        market_name = mdir.name if mdir.name else (slug or condition_id[:16])
        csv_path = output_dir / f"{market_name}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "condition_id",
                    "token1_id",
                    "token2_id",
                    "token1_trades_price",
                    "token2_trades_price",
                    "token1_clob_price",
                    "token2_clob_price",
                    "token1_action",
                    "token2_action",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        written_csv += 1

        if args.plot:
            plot_path = plot_dir / f"{market_name}.png"
            maybe_plot(rows, title=market_name, out_path=plot_path)
            written_plot += 1

        if idx <= 5 or idx % 20 == 0 or idx == len(market_dirs):
            log(
                f"processed {idx}/{len(market_dirs)}: {market_name}, rows={len(rows)}, "
                f"csv={written_csv}, plot={written_plot}"
            )

    summary = {
        "user": user,
        "activity_dir": str(activity_dir),
        "markets_dir": str(markets_dir),
        "output_dir": str(output_dir),
        "markets_total": len(market_dirs),
        "csv_written": written_csv,
        "plot_written": written_plot,
        "markets_skipped": skipped,
    }

    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
