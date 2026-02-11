import os

from common.http_client import print_json, request_json

BASE_URL = "https://data-api.polymarket.com"

params = {
    "limit": 50,
    "offset": 0,
    "takerOnly": True,
}

user = os.getenv("USER_ADDRESS")
market_ids = os.getenv("MARKET_IDS")
if user:
    params["user"] = user
if market_ids:
    params["market"] = market_ids

data = request_json("GET", BASE_URL, "/trades", params=params)
print_json(data)
