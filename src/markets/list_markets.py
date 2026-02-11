import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {
    "limit": int(os.getenv("LIMIT", "5")),
    "offset": int(os.getenv("OFFSET", "0")),
}

tag_id = os.getenv("TAG_ID")
closed = os.getenv("CLOSED")
include_tag = os.getenv("INCLUDE_TAG")
if tag_id:
    params["tag_id"] = int(tag_id)
if closed is not None:
    params["closed"] = closed.lower() == "true"
if include_tag is not None:
    params["include_tag"] = include_tag.lower() == "true"

data = request_json("GET", BASE_URL, "/markets", params=params)
print_json(data)
