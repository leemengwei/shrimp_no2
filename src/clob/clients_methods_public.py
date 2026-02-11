import os

from common.http_client import print_json, request_json

BASE_URL = "https://clob.polymarket.com"

token_id = os.getenv("TOKEN_ID")
if not token_id:
    raise SystemExit("Set TOKEN_ID.")

book = request_json("GET", BASE_URL, "/book", params={"token_id": token_id})
price = request_json("GET", BASE_URL, "/price", params={"token_id": token_id, "side": "BUY"})

print_json({"book": book, "price": price})
