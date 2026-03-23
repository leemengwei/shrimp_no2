#!/usr/bin/env python3
"""Kelly bet sizing experiment.

Run examples:
  python3 src/kelly_bet_sizing_experiment.py
  python3 src/kelly_bet_sizing_experiment.py --rounds 1000 --paths 20000 --seed 7
"""

from __future__ import annotations

import argparse
import math
import random

from kelly_core import expected_log_growth, solve_kelly


def simulate_median_log_growth(
    f: float,
    p_win: float,
    win_return: float,
    loss_fraction: float,
    rounds: int,
    paths: int,
    seed: int,
) -> float:
    """Monte Carlo estimate of median per-round log growth across paths."""
    rng = random.Random(seed)
    per_round_logs = []
    for _ in range(paths):
        wealth = 1.0
        for _ in range(rounds):
            if rng.random() < p_win:
                wealth *= 1.0 + f * win_return
            else:
                wealth *= 1.0 - f * loss_fraction
            if wealth <= 0.0:
                wealth = 0.0
                break
        if wealth <= 0.0:
            per_round_logs.append(float("-inf"))
        else:
            per_round_logs.append(math.log(wealth) / rounds)
    per_round_logs.sort()
    return per_round_logs[len(per_round_logs) // 2]


def grid_search_best_f(p_win: float, win_return: float, loss_fraction: float, step: float = 0.001) -> tuple[float, float]:
    """Numerically find f maximizing expected log growth over a grid."""
    upper = (1.0 / loss_fraction) - 1e-12
    best_f = 0.0
    best_g = expected_log_growth(0.0, p_win, win_return, loss_fraction)

    i = 0
    while True:
        f = i * step
        if f > upper:
            break
        g = expected_log_growth(f, p_win, win_return, loss_fraction)
        if g > best_g:
            best_f, best_g = f, g
        i += 1
    return best_f, best_g


def main() -> None:
    parser = argparse.ArgumentParser(description="Kelly sizing theory + simulation")
    parser.add_argument("--p", type=float, default=0.5, help="Win probability p")
    parser.add_argument("--r", type=float, default=1.0, help="Win return multiple r")
    parser.add_argument("--l", type=float, default=0.5, help="Loss fraction l")
    parser.add_argument("--rounds", type=int, default=1000, help="Rounds per path")
    parser.add_argument("--paths", type=int, default=10000, help="Number of simulation paths")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    result = solve_kelly(args.p, args.r, args.l)
    gf = grid_search_best_f(args.p, args.r, args.l, step=0.001)

    print("=== Theoretical (Kelly) ===")
    print(f"p={args.p:.4f}, r={args.r:.4f}, l={args.l:.4f}")
    print(f"f* (closed form)      = {result.optimal_fraction:.6f}")
    print(f"g(f*) expected log    = {result.expected_log_growth:.6f} per round")
    print(f"growth multiplier exp = {math.exp(result.expected_log_growth):.6f} per round")

    print("\n=== Grid Sanity Check ===")
    print(f"best f (grid)         = {gf[0]:.6f}")
    print(f"best g (grid)         = {gf[1]:.6f}")

    print("\n=== Monte Carlo (median path log growth) ===")
    for f in [0.0, result.optimal_fraction / 2, result.optimal_fraction, min(1.0, result.optimal_fraction * 1.5)]:
        med = simulate_median_log_growth(
            f=f,
            p_win=args.p,
            win_return=args.r,
            loss_fraction=args.l,
            rounds=args.rounds,
            paths=args.paths,
            seed=args.seed,
        )
        print(f"f={f:.6f} -> median log growth/round ~ {med:.6f}")


if __name__ == "__main__":
    main()
