import json
import os
from urllib.parse import urlencode

order_id = os.getenv("ORDER_ID", "")
order_ids = [item.strip() for item in os.getenv("ORDER_IDS", "").split(",") if item.strip()]

get_path = "/order-scoring"
if order_id:
    get_path += "?" + urlencode({"order_id": order_id})

post_body = {"orderIds": order_ids}

print(json.dumps({"get": get_path, "post": post_body}, indent=2, ensure_ascii=True))
