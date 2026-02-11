TIERS = {
    "unverified": {"daily_relayer_tx_limit": 100, "api_rate_limits": "standard"},
    "verified": {"daily_relayer_tx_limit": 3000, "api_rate_limits": "standard"},
    "partner": {"daily_relayer_tx_limit": "unlimited", "api_rate_limits": "highest"},
}

print(TIERS)
