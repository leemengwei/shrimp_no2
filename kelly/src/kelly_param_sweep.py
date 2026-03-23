#!/usr/bin/env python3
"""Parameter sweep for Kelly sizing.

Example:
  python3 src/kelly_param_sweep.py
  python3 src/kelly_param_sweep.py --p-list 0.45,0.5,0.55 --r-list 0.8,1.0,1.2 --l-list 0.4,0.5
"""

from __future__ import annotations

import argparse
import math

from kelly_core import solve_kelly


def parse_float_list(raw: str) -> list[float]:
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Kelly parameter sweep")
    parser.add_argument("--p-list", default="0.5", help="Comma-separated p values")
    parser.add_argument("--r-list", default="1.0", help="Comma-separated r values")
    parser.add_argument("--l-list", default="0.5", help="Comma-separated l values")
    parser.add_argument("--fractional", type=float, default=1.0, help="Apply fractional Kelly multiplier")
    args = parser.parse_args()

    p_list = parse_float_list(args.p_list)
    r_list = parse_float_list(args.r_list)
    l_list = parse_float_list(args.l_list)

    print("p,r,l,f_kelly,f_used,g_per_round,geo_multiplier")
    for p in p_list:
        for r in r_list:
            for l in l_list:
                res = solve_kelly(p, r, l)
                f_used = res.optimal_fraction * args.fractional
                # Keep feasibility under one-step loss.
                f_used = min(f_used, (1.0 / l) - 1e-12)
                g_used = p * math.log(1.0 + f_used * r) + (1.0 - p) * math.log(1.0 - f_used * l)
                print(
                    f"{p:.6f},{r:.6f},{l:.6f},"
                    f"{res.optimal_fraction:.6f},{f_used:.6f},{g_used:.6f},{math.exp(g_used):.6f}"
                )


if __name__ == "__main__":
    main()
