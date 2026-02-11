from common.http_client import print_json, request_json

BASE_URL = "https://bridge.polymarket.com"

data = request_json("GET", BASE_URL, "/supported-assets")
print_json(data)
