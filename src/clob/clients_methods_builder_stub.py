try:
    import py_builder_signing_sdk  # noqa: F401
    print("py-builder-signing-sdk installed. Configure builder creds for attribution.")
except ImportError:
    print("Install py-builder-signing-sdk: pip install py-builder-signing-sdk")
