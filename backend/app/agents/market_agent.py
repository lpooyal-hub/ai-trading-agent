from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import MarketSnapshot
from app.services.market_service import MarketService
from app.strategy.sector_candidate_selector import SectorCandidateSelector


@dataclass
class MarketAgentResult:
    snapshots: list[MarketSnapshot]
    candidates: list[MarketSnapshot]
    candidate_details: list[dict[str, Any]]
    market_source: str
    snapshot_status: dict[str, Any] | None = None


class MarketAgent:
    """Prepare market inputs and deterministic candidates for the LLM decision agent."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_service = MarketService(self.settings)
        self.selector = SectorCandidateSelector(
            active_universe=self.settings.active_universe,
            allowed_sector=self.settings.allowed_sector,
            max_candidates=self.settings.llm_max_candidates_per_run_safe,
        )

    def run(self, db: Session) -> MarketAgentResult:
        snapshots = self.market_service.refresh_active_universe_snapshots(db)
        return self._result(
            snapshots=snapshots,
            market_source="mock_market_data" if self.settings.use_mock_data else "stored_market_snapshots",
        )

    def preview(self, db: Session) -> MarketAgentResult:
        market_status = self.market_service.get_snapshot_status(db)
        snapshots = self._readiness_snapshots(db)
        return self._result(
            snapshots=snapshots,
            market_source="mock_market_data_preview" if self.settings.use_mock_data else "stored_market_snapshots",
            snapshot_status=market_status,
        )

    def _result(
        self,
        *,
        snapshots: list[MarketSnapshot],
        market_source: str,
        snapshot_status: dict[str, Any] | None = None,
    ) -> MarketAgentResult:
        candidate_signals = self.selector.selected_candidate_signals(snapshots)
        snapshot_by_symbol = {item.symbol.upper(): item for item in snapshots}
        candidates = [
            snapshot_by_symbol[signal.symbol]
            for signal in candidate_signals
            if signal.symbol in snapshot_by_symbol
        ]
        return MarketAgentResult(
            snapshots=snapshots,
            candidates=candidates,
            candidate_details=[
                {
                    "symbol": signal.symbol,
                    "score": signal.score,
                    "reason": signal.reason,
                    "change_percent": signal.change_percent,
                    "volume": signal.volume,
                }
                for signal in candidate_signals
            ],
            market_source=market_source,
            snapshot_status=snapshot_status,
        )

    def _readiness_snapshots(self, db: Session) -> list[MarketSnapshot]:
        snapshots = self.market_service.get_latest_universe_snapshots(db)
        if snapshots or not self.settings.use_mock_data:
            return snapshots

        allowed_symbols = set(self.settings.active_universe)
        preview_snapshots: list[MarketSnapshot] = []
        for item in self.market_service.mock_client.get_demo_snapshots(
            symbols=self.settings.active_universe,
            sector=self.settings.allowed_sector,
        ):
            symbol = item["symbol"].upper()
            if symbol not in allowed_symbols:
                continue
            preview_snapshots.append(
                MarketSnapshot(
                    symbol=symbol,
                    price=item["price"],
                    change_percent=item["change_percent"],
                    volume=item["volume"],
                    sector=item["sector"],
                    extra_json=item.get("extra_json", {}),
                )
            )
        return preview_snapshots
