from dataclasses import dataclass, field


@dataclass(frozen=True)
class MarketDataResult:
    success: bool
    status: str
    message: str
    snapshots: list[dict] = field(default_factory=list)


class MarketDataClient:
    """Placeholder for future external market data providers."""

    provider_name = "external_market_data"

    def get_market_snapshots(self, symbols: list[str]) -> MarketDataResult:
        return MarketDataResult(
            success=False,
            status="NOT_CONFIGURED",
            message=(
                "External market data provider is not connected yet. "
                "Use manual snapshots or the mock demo source."
            ),
            snapshots=[],
        )
