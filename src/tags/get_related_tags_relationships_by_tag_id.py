import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

tag_id = require_env("TAG_ID")
params = {}

status = os.getenv("STATUS")
omit_empty = os.getenv("OMIT_EMPTY")
if status:
    params["status"] = status
if omit_empty is not None:
    params["omit_empty"] = omit_empty.lower() == "true"

data = request_json("GET", BASE_URL, f"/tags/{tag_id}/related-tags", params=params)
print_json(data)
