#!/usr/bin/env python3
"""Core Kelly sizing functions for asymmetric binary outcomes.

Model per round (bet fraction f of current wealth):
  win  with probability p: W' = W * (1 + f * r)
  lose with probability q: W' = W * (1 - f * l)

where:
  p in [0, 1], q = 1-p
  r > 0  (net return multiple on stake when win)
  l > 0  (loss fraction on stake when lose)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class KellyResult:
    optimal_fraction: float
    expected_log_growth: float


def expected_log_growth(f: float, p: float, r: float, l: float) -> float:
    """Expected one-step log growth g(f)."""
    win_factor = 1.0 + f * r
    lose_factor = 1.0 - f * l
    if win_factor <= 0.0 or lose_factor <= 0.0:
        return float("-inf")
    return p * math.log(win_factor) + (1.0 - p) * math.log(lose_factor)


def kelly_fraction(
    p: float,
    r: float,
    l: float,
    *,
    long_only: bool = True,
    max_fraction: float | None = None,
) -> float:
    """Closed-form Kelly fraction for asymmetric binary outcomes.

    Unconstrained optimum:
      f* = (p*r - (1-p)*l) / (r*l)

    Constraints:
    - Feasibility from no-ruin in one loss: f < 1/l
    - Optional long-only: f >= 0
    - Optional max_fraction cap
    """
    if not (0.0 <= p <= 1.0):
        raise ValueError("p must be in [0, 1]")
    if r <= 0.0:
        raise ValueError("r must be > 0")
    if l <= 0.0:
        raise ValueError("l must be > 0")

    f_star = (p * r - (1.0 - p) * l) / (r * l)

    upper = (1.0 / l) - 1e-12
    if max_fraction is not None:
        upper = min(upper, max_fraction)

    if long_only:
        return max(0.0, min(f_star, upper))
    return min(f_star, upper)


def solve_kelly(
    p: float,
    r: float,
    l: float,
    *,
    long_only: bool = True,
    max_fraction: float | None = None,
) -> KellyResult:
    f = kelly_fraction(p, r, l, long_only=long_only, max_fraction=max_fraction)
    g = expected_log_growth(f, p, r, l)
    return KellyResult(optimal_fraction=f, expected_log_growth=g)
