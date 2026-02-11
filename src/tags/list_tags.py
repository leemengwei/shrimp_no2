import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {
    "limit": int(os.getenv("LIMIT", "20")),
    "offset": int(os.getenv("OFFSET", "0")),
}

include_template = os.getenv("INCLUDE_TEMPLATE")
is_carousel = os.getenv("IS_CAROUSEL")
if include_template is not None:
    params["include_template"] = include_template.lower() == "true"
if is_carousel is not None:
    params["is_carousel"] = is_carousel.lower() == "true"

data = request_json("GET", BASE_URL, "/tags", params=params)
print_json(data)
