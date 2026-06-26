class MockMarketDataClient:
    """Returns fictional semiconductor market data for public demos."""

    def get_semiconductor_snapshots(self) -> list[dict]:
        symbols = ["NVDA", "AMD", "TSM", "AVGO", "ASML", "QCOM", "MU", "ARM", "INTC", "AMAT"]
        return [
            {
                "symbol": symbol,
                "price": 100 + index * 7,
                "change_percent": round((index - 4) * 0.35, 2),
                "volume": 1_000_000 + index * 125_000,
                "sector": "semiconductor",
                "extra_json": {"source": "fictional_demo_data"},
            }
            for index, symbol in enumerate(symbols)
        ]
