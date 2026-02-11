import os

base_rate_bps = float(os.getenv("BASE_RATE_BPS", "0")) / 10000.0
price = float(os.getenv("PRICE", "0.5"))
size = float(os.getenv("SIZE", "1"))

fee_quote = base_rate_bps * min(price, 1 - price) * size
fee_base = base_rate_bps * min(price, 1 - price) * (size / price if price else 0)

print({
    "fee_quote": fee_quote,
    "fee_base": fee_base,
})
