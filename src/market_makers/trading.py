import json
import os

payload = {
    "tokenID": os.getenv("TOKEN_ID", ""),
    "side": os.getenv("SIDE", "BUY"),
    "price": float(os.getenv("PRICE", "0.5")),
    "size": float(os.getenv("SIZE", "1")),
    "orderType": os.getenv("ORDER_TYPE", "GTC"),
}

print(json.dumps(payload, indent=2, ensure_ascii=True))
