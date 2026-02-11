import asyncio

try:
    import websockets
except ImportError:
    raise SystemExit("Install websockets: pip install websockets")

WS_URL = "wss://sports-api.polymarket.com/ws"

async def main():
    async with websockets.connect(WS_URL) as ws:
        for _ in range(10):
            msg = await ws.recv()
            if msg == "ping":
                await ws.send("pong")
                continue
            print(msg)

asyncio.run(main())
