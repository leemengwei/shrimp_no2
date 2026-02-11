import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://clob.polymarket.com"

token_ids = require_env("TOKEN_IDS").split(",")
body = [{"token_id": token_id.strip()} for token_id in token_ids if token_id.strip()]

if not body:
    raise SystemExit("Provide TOKEN_IDS as a comma-separated list.")

data = request_json("POST", BASE_URL, "/books", body=body)
print_json(data)
