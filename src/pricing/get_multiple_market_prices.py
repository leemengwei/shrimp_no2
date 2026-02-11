from common.http_client import print_json, request_json

BASE_URL = "https://clob.polymarket.com"

data = request_json("GET", BASE_URL, "/prices")
print_json(data)
