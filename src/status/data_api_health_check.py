from common.http_client import print_json, request_json

BASE_URL = "https://data-api.polymarket.com"

data = request_json("GET", BASE_URL, "/")
print_json(data)
