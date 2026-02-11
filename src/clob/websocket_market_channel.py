import asyncio
import json
import os

try:
    import websockets
except ImportError:
    raise SystemExit("Install websockets: pip install websockets")

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

token_ids = [item.strip() for item in os.getenv("TOKEN_IDS", "").split(",") if item.strip()]
if not token_ids:
    raise SystemExit("Set TOKEN_IDS as a comma-separated list.")

async def main():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"type": "market", "assets_ids": token_ids}))
        while True:
            msg = await ws.recv()
            print(msg)

asyncio.run(main())
