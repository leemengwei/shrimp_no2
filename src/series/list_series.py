import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {
    "limit": int(os.getenv("LIMIT", "5")),
    "offset": int(os.getenv("OFFSET", "0")),
}

recurrence = os.getenv("RECURRENCE")
closed = os.getenv("CLOSED")
if recurrence:
    params["recurrence"] = recurrence
if closed is not None:
    params["closed"] = closed.lower() == "true"

data = request_json("GET", BASE_URL, "/series", params=params)
print_json(data)
