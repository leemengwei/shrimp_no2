import json
import os

order_ids = os.getenv("TOKEN_IDS", "").split(",")
orders = []

for token_id in [item.strip() for item in order_ids if item.strip()]:
    order = {
        "salt": "1",
        "maker": "0x0",
        "signer": "0x0",
        "taker": "0x0000000000000000000000000000000000000000",
        "tokenId": token_id,
        "makerAmount": "0",
        "takerAmount": "0",
        "expiration": "0",
        "nonce": "0",
        "feeRateBps": "0",
        "side": "BUY",
        "signatureType": 0,
        "signature": "0x",
    }
    orders.append({"order": order, "orderType": "GTC", "owner": ""})

print(json.dumps(orders, indent=2, ensure_ascii=True))
