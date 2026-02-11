import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

slug = os.getenv("SLUG")
tag_id = os.getenv("TAG_ID")

if slug:
    data = request_json("GET", BASE_URL, f"/events/slug/{slug}")
    print_json(data)
elif tag_id:
    params = {"tag_id": int(tag_id), "limit": 5, "closed": False}
    data = request_json("GET", BASE_URL, "/events", params=params)
    print_json(data)
else:
    params = {"closed": False, "limit": 5, "order": "id", "ascending": False}
    data = request_json("GET", BASE_URL, "/events", params=params)
    print_json(data)
