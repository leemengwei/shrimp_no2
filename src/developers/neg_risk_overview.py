from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {"active": True, "closed": False, "limit": 50}

events = request_json("GET", BASE_URL, "/events", params=params)
neg_risk = [event for event in events if event.get("negRisk")]

print_json({"neg_risk_events": len(neg_risk), "sample": neg_risk[:3]})
