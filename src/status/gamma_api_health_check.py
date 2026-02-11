from common.http_client import request_text

BASE_URL = "https://gamma-api.polymarket.com"

text = request_text("GET", BASE_URL, "/status")
print(text)
