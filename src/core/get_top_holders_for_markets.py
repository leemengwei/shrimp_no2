from common.http_client import print_json, request_json, require_env

BASE_URL = "https://data-api.polymarket.com"

market_ids = require_env("MARKET_IDS")
params = {
    "market": market_ids,
    "limit": 10,
    "minBalance": 1,
}

data = request_json("GET", BASE_URL, "/holders", params=params)
print_json(data)
