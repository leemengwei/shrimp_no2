from common.http_client import print_json, request_json, require_env

BASE_URL = "https://data-api.polymarket.com"

user = require_env("USER_ADDRESS")
params = {
    "user": user,
    "limit": 10,
    "offset": 0,
    "sortBy": "REALIZEDPNL",
    "sortDirection": "DESC",
}

market_ids = os.getenv("MARKET_IDS")
if market_ids:
    params["market"] = market_ids

event_ids = os.getenv("EVENT_IDS")
if event_ids:
    params["eventId"] = event_ids

data = request_json("GET", BASE_URL, "/closed-positions", params=params)
print_json(data)
