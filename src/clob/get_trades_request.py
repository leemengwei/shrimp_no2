import os
from urllib.parse import urlencode

params = {}
for key in ["id", "taker", "maker", "market", "before", "after"]:
    value = os.getenv(key.upper())
    if value:
        params[key] = value

print("/data/trades" + ("?" + urlencode(params) if params else ""))
