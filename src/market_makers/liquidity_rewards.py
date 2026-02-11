import os

v = float(os.getenv("MAX_SPREAD", "0.03"))
s = float(os.getenv("SPREAD", "0.01"))
b = float(os.getenv("BOOST", "1"))

score = ((v - s) / v) ** 2 * b if v > 0 else 0.0

print({"score": score})
