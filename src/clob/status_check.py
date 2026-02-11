from common.http_client import request_text

status_page = request_text("GET", "https://status-clob.polymarket.com", "/")
print(status_page[:500])
