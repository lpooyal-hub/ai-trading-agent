from app.utils.symbols import symbol_sector


class MockMarketDataClient:
    """Returns fictional market data for public demos."""

    def get_demo_snapshots(self, symbols: list[str]) -> list[dict]:
        return [
            {
                "symbol": symbol,
                "price": 50000 + index * 3500,
                "change_percent": round((index - 4) * 0.35, 2),
                "volume": 1_000_000 + index * 125_000,
                "sector": symbol_sector(symbol) or "unknown",
                "extra_json": {"source": "fictional_demo_data"},
            }
            for index, symbol in enumerate(symbols)
        ]
