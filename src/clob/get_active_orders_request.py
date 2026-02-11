import os
from urllib.parse import urlencode

params = {}
order_id = os.getenv("ORDER_ID")
market = os.getenv("MARKET")
asset_id = os.getenv("ASSET_ID")

if order_id:
    params["id"] = order_id
if market:
    params["market"] = market
if asset_id:
    params["asset_id"] = asset_id

print("/data/orders" + ("?" + urlencode(params) if params else ""))
