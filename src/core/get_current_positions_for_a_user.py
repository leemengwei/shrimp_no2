import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://data-api.polymarket.com"

user = require_env("USER_ADDRESS")
params = {
    "user": user,
    "limit": 20,
    "offset": 0,
    "sortBy": "TOKENS",
    "sortDirection": "DESC",
}

market_ids = os.getenv("MARKET_IDS")
if market_ids:
    params["market"] = market_ids

data = request_json("GET", BASE_URL, "/positions", params=params)
print_json(data)
