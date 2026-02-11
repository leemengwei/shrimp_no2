import os

from common.http_client import download_file, require_env

BASE_URL = "https://data-api.polymarket.com"

user = require_env("USER_ADDRESS")
output_path = os.getenv("OUTPUT", "snapshot.zip")

saved = download_file(
    BASE_URL,
    "/v1/accounting/snapshot",
    params={"user": user},
    output_path=output_path,
)
print(f"Saved {saved}")
