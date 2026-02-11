try:
    import py_clob_client  # noqa: F401
    print("py-clob-client installed. Use create_or_derive_api_key() with your private key.")
except ImportError:
    print("Install py-clob-client to use L1 methods: pip install py-clob-client")
