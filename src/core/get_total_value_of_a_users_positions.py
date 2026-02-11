from common.http_client import print_json, request_json, require_env

BASE_URL = "https://data-api.polymarket.com"

user = require_env("USER_ADDRESS")
params = {"user": user}

market_ids = os.getenv("MARKET_IDS")
if market_ids:
    params["market"] = market_ids

data = request_json("GET", BASE_URL, "/value", params=params)
print_json(data)
