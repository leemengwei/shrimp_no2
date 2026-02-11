import json
import os

payload = {
    "tokenID": os.getenv("TOKEN_ID", ""),
    "price": float(os.getenv("PRICE", "0.5")),
    "size": float(os.getenv("SIZE", "1")),
    "side": os.getenv("SIDE", "BUY"),
}

print(json.dumps(payload, indent=2, ensure_ascii=True))
