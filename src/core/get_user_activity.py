import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://data-api.polymarket.com"

user = require_env("USER_ADDRESS")
params = {
    "user": user,
    "limit": 50,
    "offset": 0,
    "sortBy": "TIMESTAMP",
    "sortDirection": "DESC",
}

activity_types = os.getenv("ACTIVITY_TYPES")
if activity_types:
    params["type"] = activity_types

start = os.getenv("START_TS")
end = os.getenv("END_TS")
if start:
    params["start"] = start
if end:
    params["end"] = end

data = request_json("GET", BASE_URL, "/activity", params=params)
print_json(data)
