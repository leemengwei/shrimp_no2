import hmac
import json
import os
import time
from hashlib import sha256

api_key = os.getenv("POLY_BUILDER_API_KEY")
secret = os.getenv("POLY_BUILDER_SECRET")
passphrase = os.getenv("POLY_BUILDER_PASSPHRASE")

if not api_key or not secret or not passphrase:
    raise SystemExit("Set POLY_BUILDER_API_KEY, POLY_BUILDER_SECRET, POLY_BUILDER_PASSPHRASE.")

method = os.getenv("METHOD", "POST")
path = os.getenv("PATH", "/order")
body = os.getenv("BODY", "{}")

try:
    json.loads(body)
except json.JSONDecodeError as exc:
    raise SystemExit("BODY must be valid JSON.") from exc

timestamp = str(int(time.time()))
message = f"{timestamp}{method}{path}{body}".encode("utf-8")

signature = hmac.new(secret.encode("utf-8"), message, sha256).hexdigest()

headers = {
    "POLY_BUILDER_SIGNATURE": signature,
    "POLY_BUILDER_TIMESTAMP": timestamp,
    "POLY_BUILDER_API_KEY": api_key,
    "POLY_BUILDER_PASSPHRASE": passphrase,
}

print(json.dumps(headers, indent=2, ensure_ascii=True))
