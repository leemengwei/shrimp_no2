import json
import os

order = {
    "salt": os.getenv("SALT", "1"),
    "maker": os.getenv("MAKER", "0x0"),
    "signer": os.getenv("SIGNER", "0x0"),
    "taker": os.getenv("TAKER", "0x0000000000000000000000000000000000000000"),
    "tokenId": os.getenv("TOKEN_ID", "0"),
    "makerAmount": os.getenv("MAKER_AMOUNT", "0"),
    "takerAmount": os.getenv("TAKER_AMOUNT", "0"),
    "expiration": os.getenv("EXPIRATION", "0"),
    "nonce": os.getenv("NONCE", "0"),
    "feeRateBps": os.getenv("FEE_RATE_BPS", "0"),
    "side": os.getenv("SIDE", "BUY"),
    "signatureType": int(os.getenv("SIGNATURE_TYPE", "0")),
    "signature": os.getenv("SIGNATURE", "0x"),
}

payload = {
    "order": order,
    "owner": os.getenv("OWNER", ""),
    "orderType": os.getenv("ORDER_TYPE", "GTC"),
    "postOnly": os.getenv("POST_ONLY", "false").lower() == "true",
}

print(json.dumps(payload, indent=2, ensure_ascii=True))
