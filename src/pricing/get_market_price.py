import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://clob.polymarket.com"

token_id = require_env("TOKEN_ID")
side = os.getenv("SIDE", "BUY").upper()
params = {"token_id": token_id, "side": side}

data = request_json("GET", BASE_URL, "/price", params=params)
print_json(data)
