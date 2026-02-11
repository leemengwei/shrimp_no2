from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

data = request_json("GET", BASE_URL, "/sports/market-types")
print_json(data)
