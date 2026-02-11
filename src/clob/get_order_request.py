import os

order_id = os.getenv("ORDER_ID")
if not order_id:
    raise SystemExit("Set ORDER_ID.")

print(f"/data/order/{order_id}")
