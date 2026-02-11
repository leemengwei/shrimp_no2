from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

user_address = require_env("USER_ADDRESS")
params = {
    "limit": 10,
    "offset": 0,
    "order": "createdAt",
    "ascending": False,
}

data = request_json(
    "GET",
    BASE_URL,
    f"/comments/user_address/{user_address}",
    params=params,
)
print_json(data)
