import time

from common.http_client import request_json

BASE_URL = "https://gamma-api.polymarket.com"

for _ in range(3):
    try:
        data = request_json("GET", BASE_URL, "/events", params={"limit": 1})
        print(data)
        break
    except SystemExit:
        time.sleep(1)
