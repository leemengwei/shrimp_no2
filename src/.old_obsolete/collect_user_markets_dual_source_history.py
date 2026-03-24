#!/usr/bin/env python3
"""Compatibility wrapper.

Use `collect_user_market_price_by_clob_and_trades.py` instead.
"""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    print(
        "[compat] collect_user_markets_dual_source_history.py is deprecated; "
        "use collect_user_market_price_by_clob_and_trades.py",
        flush=True,
    )
    target = Path(__file__).with_name("collect_user_market_price_by_clob_and_trades.py")
    runpy.run_path(str(target), run_name="__main__")
