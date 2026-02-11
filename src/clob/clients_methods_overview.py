from common.http_client import print_json, request_json

BASE_URL = "https://clob.polymarket.com"

markets = request_json("GET", BASE_URL, "/markets", params={"limit": 1})
print_json(markets)
