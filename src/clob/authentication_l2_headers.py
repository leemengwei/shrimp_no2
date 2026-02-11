import hmac
import json
import os
import time
from hashlib import sha256

api_key = os.getenv("CLOB_API_KEY")
secret = os.getenv("CLOB_SECRET")
passphrase = os.getenv("CLOB_PASSPHRASE")

if not api_key or not secret or not passphrase:
    raise SystemExit("Set CLOB_API_KEY, CLOB_SECRET, CLOB_PASSPHRASE.")

method = os.getenv("METHOD", "GET")
path = os.getenv("PATH", "/data/orders")
body = os.getenv("BODY", "")

if body:
    try:
        json.loads(body)
    except json.JSONDecodeError as exc:
        raise SystemExit("BODY must be valid JSON when provided.") from exc

timestamp = str(int(time.time()))
message = f"{timestamp}{method}{path}{body}".encode("utf-8")

signature = hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()

headers = {
    "POLY_API_KEY": api_key,
    "POLY_PASSPHRASE": passphrase,
    "POLY_SIGNATURE": signature,
    "POLY_TIMESTAMP": timestamp,
}

print(json.dumps(headers, indent=2, ensure_ascii=True))
