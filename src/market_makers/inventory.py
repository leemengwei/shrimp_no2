import os

params = {
    "conditionId": os.getenv("CONDITION_ID", "0x" + "0" * 64),
    "partition": [1, 2],
    "amount": os.getenv("AMOUNT", "0"),
}

print(params)
