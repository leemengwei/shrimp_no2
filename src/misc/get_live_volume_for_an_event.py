from common.http_client import print_json, request_json, require_env

BASE_URL = "https://data-api.polymarket.com"

event_id = require_env("EVENT_ID")
params = {"id": event_id}

data = request_json("GET", BASE_URL, "/live-volume", params=params)
print_json(data)
