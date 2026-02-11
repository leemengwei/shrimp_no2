import os

balance = float(os.getenv("BALANCE", "0"))
order_size = float(os.getenv("ORDER_SIZE", "0"))
order_filled = float(os.getenv("ORDER_FILLED", "0"))

max_order_size = balance - (order_size - order_filled)

print({"max_order_size": max_order_size})
