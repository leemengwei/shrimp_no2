from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {"limit": 1}

data = request_json("GET", BASE_URL, "/markets", params=params)
print_json(data)
