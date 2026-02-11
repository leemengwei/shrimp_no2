import os

params = {
    "collateralToken": os.getenv("COLLATERAL_TOKEN", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"),
    "parentCollectionId": "0x" + "0" * 64,
    "conditionId": os.getenv("CONDITION_ID", "0x" + "0" * 64),
    "partition": [1, 2],
    "amount": os.getenv("AMOUNT", "0"),
}

print(params)
