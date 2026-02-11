import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://clob.polymarket.com"

token_id = require_env("TOKEN_ID")
params = {"market": token_id, "interval": os.getenv("INTERVAL", "1d")}

data = request_json("GET", BASE_URL, "/prices-history", params=params)
print_json(data)
