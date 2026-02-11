import os

from common.http_client import print_json, request_json, require_env

BASE_URL = "https://clob.polymarket.com"

token_id = require_env("TOKEN_ID")
params = {"market": token_id}

interval = os.getenv("INTERVAL")
start_ts = os.getenv("START_TS")
end_ts = os.getenv("END_TS")
if interval:
    params["interval"] = interval
else:
    if start_ts:
        params["startTs"] = start_ts
    if end_ts:
        params["endTs"] = end_ts

fidelity = os.getenv("FIDELITY")
if fidelity:
    params["fidelity"] = fidelity

data = request_json("GET", BASE_URL, "/prices-history", params=params)
print_json(data)
