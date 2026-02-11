from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

slug = require_env("EVENT_SLUG")
params = {}

data = request_json("GET", BASE_URL, f"/events/slug/{slug}", params=params)
print_json(data)
