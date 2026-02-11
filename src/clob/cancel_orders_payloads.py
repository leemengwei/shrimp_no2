import json
import os

single = os.getenv("ORDER_ID")
batch = [item.strip() for item in os.getenv("ORDER_IDS", "").split(",") if item.strip()]

payload = {
    "cancel_single": {"orderID": single} if single else None,
    "cancel_batch": batch if batch else None,
}

print(json.dumps(payload, indent=2, ensure_ascii=True))
