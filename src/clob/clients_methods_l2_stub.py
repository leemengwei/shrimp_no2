try:
    import py_clob_client  # noqa: F401
    print("py-clob-client installed. Use create_and_post_order() with API creds.")
except ImportError:
    print("Install py-clob-client to use L2 methods: pip install py-clob-client")
