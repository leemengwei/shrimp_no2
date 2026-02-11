from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

series_id = require_env("SERIES_ID")

data = request_json("GET", BASE_URL, f"/series/{series_id}")
print_json(data)
