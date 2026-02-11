import os

from common.http_client import print_json, request_json

BASE_URL = "https://data-api.polymarket.com"

params = {}
market_ids = os.getenv("MARKET_IDS")
if market_ids:
    params["market"] = market_ids

data = request_json("GET", BASE_URL, "/oi", params=params)
print_json(data)
