import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

comment_id = os.getenv("COMMENT_ID", "1")
params = {}
if os.getenv("GET_POSITIONS") is not None:
    params["get_positions"] = os.getenv("GET_POSITIONS", "").lower() == "true"

data = request_json("GET", BASE_URL, f"/comments/{comment_id}", params=params)
print_json(data)
