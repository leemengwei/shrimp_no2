import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {
    "limit": int(os.getenv("LIMIT", "5")),
    "offset": int(os.getenv("OFFSET", "0")),
}

active = os.getenv("ACTIVE")
closed = os.getenv("CLOSED")
tag_id = os.getenv("TAG_ID")
if active is not None:
    params["active"] = active.lower() == "true"
if closed is not None:
    params["closed"] = closed.lower() == "true"
if tag_id:
    params["tag_id"] = int(tag_id)

data = request_json("GET", BASE_URL, "/events", params=params)
print_json(data)
