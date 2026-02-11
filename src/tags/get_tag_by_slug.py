from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

slug = require_env("TAG_SLUG")

data = request_json("GET", BASE_URL, f"/tags/slug/{slug}")
print_json(data)
