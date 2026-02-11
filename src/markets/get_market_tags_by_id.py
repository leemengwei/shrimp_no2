from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

market_id = require_env("MARKET_ID")

data = request_json("GET", BASE_URL, f"/markets/{market_id}/tags")
print_json(data)
