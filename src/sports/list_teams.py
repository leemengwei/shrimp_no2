import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {
    "limit": int(os.getenv("LIMIT", "10")),
    "offset": int(os.getenv("OFFSET", "0")),
}

league = os.getenv("LEAGUE")
name = os.getenv("NAME")
abbreviation = os.getenv("ABBREVIATION")
if league:
    params["league"] = league
if name:
    params["name"] = name
if abbreviation:
    params["abbreviation"] = abbreviation

data = request_json("GET", BASE_URL, "/teams", params=params)
print_json(data)
