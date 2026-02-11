import os

api_key = os.getenv("POLY_BUILDER_API_KEY")
secret = os.getenv("POLY_BUILDER_SECRET")
passphrase = os.getenv("POLY_BUILDER_PASSPHRASE")

print({
    "api_key_set": bool(api_key),
    "secret_set": bool(secret),
    "passphrase_set": bool(passphrase),
})
