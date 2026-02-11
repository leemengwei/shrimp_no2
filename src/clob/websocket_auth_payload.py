import json
import os

payload = {
    "auth": {
        "apiKey": os.getenv("CLOB_API_KEY", ""),
        "secret": os.getenv("CLOB_SECRET", ""),
        "passphrase": os.getenv("CLOB_PASSPHRASE", ""),
    }
}

print(json.dumps(payload, indent=2, ensure_ascii=True))
