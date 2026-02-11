from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {"limit": 1}

events = request_json("GET", BASE_URL, "/events", params=params)
if not events:
    print_json({"events": 0, "markets": 0})
else:
    first = events[0]
    markets = first.get("markets", []) if isinstance(first, dict) else []
    print_json({"event_id": first.get("id"), "markets_count": len(markets)})
