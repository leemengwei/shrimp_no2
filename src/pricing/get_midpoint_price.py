from common.http_client import print_json, request_json, require_env

BASE_URL = "https://clob.polymarket.com"

token_id = require_env("TOKEN_ID")
params = {"token_id": token_id}

data = request_json("GET", BASE_URL, "/midpoint", params=params)
print_json(data)
