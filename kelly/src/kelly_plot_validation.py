#!/usr/bin/env python3
"""Plot-based validation for Kelly sizing.

Example:
  python3 src/kelly_plot_validation.py
  python3 src/kelly_plot_validation.py --p 0.5 --r 1.0 --l 0.5 --rounds 500 --paths 3000
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import matplotlib.pyplot as plt

from kelly_core import expected_log_growth, solve_kelly


def mc_mean_log_growth(f: float, p: float, r: float, l: float, rounds: int, paths: int, seed: int) -> float:
    rng = random.Random(seed)
    total = 0.0
    valid = 0
    for _ in range(paths):
        wealth = 1.0
        for _ in range(rounds):
            if rng.random() < p:
                wealth *= 1.0 + f * r
            else:
                wealth *= 1.0 - f * l
            if wealth <= 0.0:
                wealth = 0.0
                break
        if wealth > 0.0:
            total += math.log(wealth) / rounds
            valid += 1
    if valid == 0:
        return float("-inf")
    return total / valid


def main() -> None:
    parser = argparse.ArgumentParser(description="Kelly plot validation")
    parser.add_argument("--p", type=float, default=0.5)
    parser.add_argument("--r", type=float, default=1.0)
    parser.add_argument("--l", type=float, default=0.5)
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--paths", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default="docs/kelly_validation.png")
    args = parser.parse_args()

    res = solve_kelly(args.p, args.r, args.l)
    # Long-only, no leverage: only consider 0 <= f <= 1.
    upper = 1.0

    n = 121
    f_grid = [upper * i / (n - 1) for i in range(n)]
    g_theory = [expected_log_growth(f, args.p, args.r, args.l) for f in f_grid]

    sample_idx = list(range(0, n, 10))
    f_sample = [f_grid[i] for i in sample_idx]
    g_mc = [mc_mean_log_growth(f, args.p, args.r, args.l, args.rounds, args.paths, args.seed + i) for i, f in enumerate(f_sample)]

    best_theory_idx = max(range(n), key=lambda i: g_theory[i])
    f_best_theory = f_grid[best_theory_idx]
    f_closed = min(max(res.optimal_fraction, 0.0), 1.0)
    g_closed = expected_log_growth(f_closed, args.p, args.r, args.l)

    plt.figure(figsize=(9, 5.5))
    plt.plot(f_grid, g_theory, label="Theory: E[log growth]", linewidth=2.0)
    plt.scatter(f_sample, g_mc, s=22, label="Monte Carlo estimate", alpha=0.9)
    plt.axvline(f_closed, linestyle="--", linewidth=1.5, label=f"Closed-form f* (clipped)={f_closed:.3f}")
    plt.scatter([f_best_theory], [g_theory[best_theory_idx]], s=40, label=f"Grid max f={f_best_theory:.3f}")

    plt.title(f"Kelly Validation (p={args.p}, r={args.r}, l={args.l})")
    plt.xlabel("Bet fraction f")
    plt.ylabel("Per-round log growth")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=160)
    print(f"Saved plot: {out}")
    print(f"Closed-form f* (raw): {res.optimal_fraction:.6f}")
    print(f"Closed-form f* in [0,1]: {f_closed:.6f}, g(f): {g_closed:.6f}")
    print(f"Grid best in [0,1]: {f_best_theory:.6f}, g(f): {g_theory[best_theory_idx]:.6f}")


if __name__ == "__main__":
    main()
