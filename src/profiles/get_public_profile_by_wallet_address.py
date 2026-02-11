from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

address = require_env("USER_ADDRESS")
params = {"address": address}

data = request_json("GET", BASE_URL, "/public-profile", params=params)
print_json(data)
