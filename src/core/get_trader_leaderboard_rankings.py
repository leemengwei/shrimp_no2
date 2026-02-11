from common.http_client import print_json, request_json

BASE_URL = "https://data-api.polymarket.com"

params = {
    "category": "OVERALL",
    "timePeriod": "DAY",
    "orderBy": "PNL",
    "limit": 10,
    "offset": 0,
}

data = request_json("GET", BASE_URL, "/v1/leaderboard", params=params)
print_json(data)
