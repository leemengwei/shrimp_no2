import os

from common.http_client import print_json, request_json

BASE_URL = "https://clob.polymarket.com"

token_id = os.getenv("TOKEN_ID")
if not token_id:
    raise SystemExit("Set TOKEN_ID to query fee rate.")

data = request_json("GET", BASE_URL, "/fee-rate", params={"token_id": token_id})
print_json(data)
