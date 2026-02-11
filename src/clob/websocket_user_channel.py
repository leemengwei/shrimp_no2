import asyncio
import json
import os

try:
    import websockets
except ImportError:
    raise SystemExit("Install websockets: pip install websockets")

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"

api_key = os.getenv("CLOB_API_KEY")
secret = os.getenv("CLOB_SECRET")
passphrase = os.getenv("CLOB_PASSPHRASE")

if not api_key or not secret or not passphrase:
    raise SystemExit("Set CLOB_API_KEY, CLOB_SECRET, CLOB_PASSPHRASE.")

markets = [item.strip() for item in os.getenv("MARKETS", "").split(",") if item.strip()]

async def main():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "user",
                    "auth": {
                        "apiKey": api_key,
                        "secret": secret,
                        "passphrase": passphrase,
                    },
                    "markets": markets,
                }
            )
        )
        while True:
            msg = await ws.recv()
            print(msg)

asyncio.run(main())
