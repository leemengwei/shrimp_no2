from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

tag_id = require_env("TAG_ID")

data = request_json("GET", BASE_URL, f"/tags/{tag_id}")
print_json(data)
