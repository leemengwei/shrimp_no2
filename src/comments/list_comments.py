import os

from common.http_client import print_json, request_json

BASE_URL = "https://gamma-api.polymarket.com"

params = {
    "limit": 5,
    "offset": 0,
}

parent_entity_type = os.getenv("PARENT_ENTITY_TYPE")
parent_entity_id = os.getenv("PARENT_ENTITY_ID")
if parent_entity_type:
    params["parent_entity_type"] = parent_entity_type
if parent_entity_id:
    params["parent_entity_id"] = parent_entity_id
if os.getenv("GET_POSITIONS") is not None:
    params["get_positions"] = os.getenv("GET_POSITIONS", "").lower() == "true"
if os.getenv("HOLDERS_ONLY") is not None:
    params["holders_only"] = os.getenv("HOLDERS_ONLY", "").lower() == "true"

data = request_json("GET", BASE_URL, "/comments", params=params)
print_json(data)
