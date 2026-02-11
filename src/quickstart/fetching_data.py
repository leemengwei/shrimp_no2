from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {"active": True, "closed": False, "limit": 5}

data = request_json("GET", BASE_URL, "/events", params=params)
print_json(data)
