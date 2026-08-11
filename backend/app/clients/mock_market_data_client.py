class MockMarketDataClient:
    """Returns fictional market data for public demos."""

    # Sector metadata for the default ALLOWED_SYMBOLS (KRX large caps, config.py).
    # Falls back to "unknown" for any symbol outside this map so custom
    # ALLOWED_SYMBOLS values (or future real snapshots) still work.
    _DEFAULT_SECTORS: dict[str, str] = {
        "005930": "semiconductor",  # Samsung Electronics
        "000660": "semiconductor",  # SK Hynix
        "005380": "automobile",     # Hyundai Motor
        "000270": "automobile",     # Kia
        "373220": "battery",        # LG Energy Solution
        "207940": "bio",            # Samsung Biologics
        "035420": "internet",       # NAVER
        "035720": "internet",       # Kakao
        "005490": "steel",          # POSCO Holdings
        "068270": "bio",            # Celltrion
    }

    def get_demo_snapshots(self, symbols: list[str]) -> list[dict]:
        return [
            {
                "symbol": symbol,
                "price": 50000 + index * 3500,
                "change_percent": round((index - 4) * 0.35, 2),
                "volume": 1_000_000 + index * 125_000,
                "sector": self._DEFAULT_SECTORS.get(symbol.upper(), "unknown"),
                "extra_json": {"source": "fictional_demo_data"},
            }
            for index, symbol in enumerate(symbols)
        ]
