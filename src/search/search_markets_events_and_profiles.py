from common.http_client import print_json, request_json, require_env

BASE_URL = "https://gamma-api.polymarket.com"

query = require_env("QUERY")
params = {"q": query}

data = request_json("GET", BASE_URL, "/public-search", params=params)
print_json(data)
