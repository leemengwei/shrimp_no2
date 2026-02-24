import json
import os
import time
import sys
from hashlib import sha256
import hmac
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# CLOB API 基本配置与输出路径
CLOB_API = "https://clob.polymarket.com"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "clob_snapshot.json")

# 从环境变量读取 API 凭证（适合个人在本地设置）
CLOB_API_KEY = os.getenv("CLOB_API_KEY")
CLOB_SECRET = os.getenv("CLOB_SECRET")
CLOB_PASSPHRASE = os.getenv("CLOB_PASSPHRASE")

if not CLOB_API_KEY or not CLOB_SECRET or not CLOB_PASSPHRASE:
    # 未设置凭证则直接退出，避免无凭证请求导致 401
    raise SystemExit("Set CLOB_API_KEY, CLOB_SECRET, CLOB_PASSPHRASE")


def sign_headers(method, path, body):
    # 按 CLOB API 要求签名请求头：timestamp + method + path + body，使用 HMAC-SHA256
    timestamp = str(int(time.time()))
    message = f"{timestamp}{method}{path}{body}".encode("utf-8")
    signature = hmac.new(CLOB_SECRET.encode("utf-8"), message, sha256).hexdigest()
    return {
        "POLY_API_KEY": CLOB_API_KEY,
        "POLY_PASSPHRASE": CLOB_PASSPHRASE,
        "POLY_SIGNATURE": signature,
        "POLY_TIMESTAMP": timestamp,
    }


def get_json(path, params=None):
    # 发起带签名头的 GET 请求并解析 JSON
    params = params or {}
    url = CLOB_API + path
    if params:
        url += "?" + urlencode(params)

    headers = sign_headers("GET", path + ("?" + urlencode(params) if params else ""), "")
    req = Request(url, method="GET", headers=headers)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    # 可通过环境变量 MARKET 或 ASSET_ID 来过滤要获取的订单
    market = os.getenv("MARKET")
    asset_id = os.getenv("ASSET_ID")

    orders_params = {}
    if market:
        orders_params["market"] = market
    if asset_id:
        orders_params["asset_id"] = asset_id

    # 拉取订单与成交数据，并把快照写到本地文件
    orders = get_json("/data/orders", params=orders_params)
    trades = get_json("/data/trades")

    snapshot = {
        "orders": orders,
        "trades": trades,
        "generated_at": int(time.time()),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, indent=2, ensure_ascii=True)

    print(f"Saved {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
