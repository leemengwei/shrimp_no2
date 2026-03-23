#!/usr/bin/env python3
"""Plot many Kelly growth curves on one chart.

Example:
  python3 src/kelly_multi_curve_plot.py
  python3 src/kelly_multi_curve_plot.py --p-list 0.35,0.45,0.55,0.65 --r-list 0.6,1.0,1.4 --l-list 0.4,0.6
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib.pyplot as plt

from kelly_core import expected_log_growth, solve_kelly


def parse_float_list(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-curve Kelly plot")
    parser.add_argument("--p-list", default="0.35,0.45,0.55,0.65", help="Comma-separated p values")
    parser.add_argument("--r-list", default="0.6,1.0,1.4", help="Comma-separated r values")
    parser.add_argument("--l-list", default="0.4,0.6", help="Comma-separated l values")
    parser.add_argument("--f-max", type=float, default=1.0, help="Max fraction on x-axis (default no leverage: 1.0)")
    parser.add_argument("--points", type=int, default=201, help="Number of f grid points")
    parser.add_argument(
        "--legend-max",
        type=int,
        default=24,
        help="Show legend only if total curves <= this value",
    )
    parser.add_argument(
        "--legend-sample",
        type=int,
        default=12,
        help="If curves exceed legend-max, show this many sampled legend entries",
    )
    parser.add_argument(
        "--y-quantile",
        type=float,
        default=0.0,
        help="If >0, set y-limits by symmetric quantiles, e.g. 0.02 uses [2%,98%]",
    )
    parser.add_argument("--out", default="docs/kelly_multi_curves.png", help="Output image path")
    args = parser.parse_args()

    p_list = parse_float_list(args.p_list)
    r_list = parse_float_list(args.r_list)
    l_list = parse_float_list(args.l_list)

    if args.f_max <= 0:
        raise ValueError("f-max must be > 0")

    f_grid = [args.f_max * i / (args.points - 1) for i in range(args.points)]

    combos = []
    for p in p_list:
        for r in r_list:
            for l in l_list:
                combos.append((p, r, l))

    plt.figure(figsize=(13, 8))
    cmap = plt.get_cmap("tab20")
    all_y = []

    handles = []
    labels = []
    for i, (p, r, l) in enumerate(combos):
        color = cmap(i % 20)
        ys = [expected_log_growth(f, p, r, l) for f in f_grid]
        all_y.extend(ys)
        res = solve_kelly(p, r, l)
        f_star = min(max(res.optimal_fraction, 0.0), args.f_max)
        g_star = expected_log_growth(f_star, p, r, l)

        label = f"p={p:.2f}, r={r:.2f}, l={l:.2f}, f*={f_star:.2f}"
        line, = plt.plot(f_grid, ys, color=color, linewidth=1.4, alpha=0.9, label=label)
        plt.scatter([f_star], [g_star], color=color, s=14)
        handles.append(line)
        labels.append(label)

    plt.axhline(0.0, color="black", linewidth=1.0, alpha=0.4)
    plt.title("Kelly Curves: E[log growth] vs Bet Fraction f (Many p/r/l Scenarios)")
    plt.xlabel("Bet fraction f")
    plt.ylabel("Expected log growth per round")
    plt.xlim(0.0, args.f_max)
    if args.y_quantile > 0.0:
        q = args.y_quantile
        ys_sorted = sorted(all_y)
        n = len(ys_sorted)
        lo = ys_sorted[int(q * (n - 1))]
        hi = ys_sorted[int((1.0 - q) * (n - 1))]
        if lo < hi:
            plt.ylim(lo, hi)
    plt.grid(alpha=0.25)
    if len(combos) <= args.legend_max:
        plt.legend(fontsize=7, ncol=2, loc="best")
    elif args.legend_sample > 0:
        k = min(args.legend_sample, len(handles))
        # Evenly sample curve labels to keep legend informative but compact.
        idxs = [int(round(i * (len(handles) - 1) / (k - 1))) for i in range(k)] if k > 1 else [0]
        sampled_h = [handles[i] for i in idxs]
        sampled_l = [labels[i] for i in idxs]
        plt.legend(
            sampled_h,
            sampled_l,
            fontsize=7,
            ncol=1,
            loc="upper left",
            bbox_to_anchor=(1.01, 1.0),
            borderaxespad=0.0,
            frameon=True,
        )
    plt.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=180)

    print(f"Saved: {out}")
    print(f"Total curves: {len(combos)}")
    if len(combos) > args.legend_max:
        if args.legend_sample > 0:
            print(f"Legend sampled entries: {min(args.legend_sample, len(combos))}")
        else:
            print("Legend hidden due to too many curves.")


if __name__ == "__main__":
    main()
