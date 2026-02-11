import asyncio
import json
import os

try:
    import websockets
except ImportError:
    raise SystemExit("Install websockets: pip install websockets")

WS_URL = "wss://ws-live-data.polymarket.com"

async def main():
    async with websockets.connect(WS_URL) as ws:
        subscribe = {
            "action": "subscribe",
            "subscriptions": [
                {"topic": "crypto_prices", "type": "update"},
            ],
        }
        await ws.send(json.dumps(subscribe))
        for _ in range(5):
            print(await ws.recv())

asyncio.run(main())
