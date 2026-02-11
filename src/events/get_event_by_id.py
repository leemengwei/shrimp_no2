from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

event_id = require_env("EVENT_ID")
params = {}

data = request_json("GET", BASE_URL, f"/events/{event_id}", params=params)
print_json(data)
