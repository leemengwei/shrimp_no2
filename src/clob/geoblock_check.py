from common.http_client import print_json, request_json

BASE_URL = "https://polymarket.com"

data = request_json("GET", BASE_URL, "/api/geoblock")
print_json(data)
