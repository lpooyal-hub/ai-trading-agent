from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import BotPosition, MarketSnapshot
from app.services.market_service import MarketService
from app.strategy.intraday_signal_selector import IntradaySignalSelector
from app.strategy.sector_candidate_selector import CandidateSelector


@dataclass
class MarketAgentResult:
    snapshots: list[MarketSnapshot]
    candidates: list[MarketSnapshot]
    candidate_details: list[dict[str, Any]]
    market_source: str
    snapshot_status: dict[str, Any] | None = None
    signal_diagnostics: list[dict[str, str]] | None = None


class MarketAgent:
    """Prepare market inputs and deterministic candidates for the LLM decision agent."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_service = MarketService(self.settings)
        self.selector = CandidateSelector(
            active_universe=self.settings.active_universe,
            max_candidates=self.settings.llm_max_candidates_per_run_safe,
        )
        self.shortlist_selector = CandidateSelector(
            active_universe=self.settings.active_universe,
            max_candidates=self.settings.intraday_shortlist_size_safe,
        )
        self.intraday_selector = IntradaySignalSelector(
            max_candidates=self.settings.llm_max_candidates_per_run_safe,
        )

    def run(self, db: Session) -> MarketAgentResult:
        held_symbols = [
            row[0]
            for row in (
                db.query(BotPosition.symbol)
                .filter(BotPosition.status == "OPEN")
                .distinct()
                .all()
            )
        ]
        snapshots = self.market_service.refresh_active_universe_snapshots(
            db,
            extra_symbols=held_symbols,
        )
        if self.settings.intraday_signals_enabled and not self.settings.use_mock_data:
            return self._intraday_result(db, snapshots)
        return self._result(
            snapshots=snapshots,
            market_source="mock_market_data" if self.settings.use_mock_data else "stored_market_snapshots",
        )

    def preview(self, db: Session) -> MarketAgentResult:
        market_status = self.market_service.get_snapshot_status(db)
        snapshots = self._readiness_snapshots(db)
        if self.settings.intraday_signals_enabled and not self.settings.use_mock_data:
            return self._stored_intraday_result(snapshots, market_status)
        return self._result(
            snapshots=snapshots,
            market_source="mock_market_data_preview" if self.settings.use_mock_data else "stored_market_snapshots",
            snapshot_status=market_status,
        )

    def _intraday_result(self, db: Session, snapshots: list[MarketSnapshot]) -> MarketAgentResult:
        shortlist_symbols = self._intraday_shortlist_symbols(snapshots)
        contexts = self.market_service.market_data_client.get_intraday_context(shortlist_symbols)
        snapshot_by_symbol = {item.symbol.upper(): item for item in snapshots}
        for symbol, context in contexts.items():
            snapshot = snapshot_by_symbol.get(symbol)
            if snapshot:
                context["price"] = snapshot.price
                context["price_timestamp"] = (snapshot.extra_json or {}).get("price_timestamp")

        selection = self.intraday_selector.select_with_diagnostics(contexts, shortlist_symbols)
        signals = selection.signals
        candidates: list[MarketSnapshot] = []
        candidate_details: list[dict[str, Any]] = []
        for signal in signals:
            symbol = str(signal.symbol).upper()
            snapshot = snapshot_by_symbol.get(symbol)
            if snapshot is None or not signal.event_triggered:
                continue
            signal_payload = self._intraday_signal_to_dict(signal)
            snapshot.extra_json = {**(snapshot.extra_json or {}), "intraday_signal": signal_payload}
            db.add(snapshot)
            candidates.append(snapshot)
            candidate_details.append(
                {
                    "symbol": signal.symbol,
                    "score": signal.score,
                    "reason": signal.reason,
                    "change_percent": snapshot.change_percent,
                    "volume": snapshot.volume,
                    **signal_payload,
                }
            )
        if candidates:
            db.commit()
        return MarketAgentResult(
            snapshots=snapshots,
            candidates=candidates,
            candidate_details=candidate_details,
            market_source="toss_realtime_intraday",
            signal_diagnostics=[
                {
                    "symbol": item.symbol,
                    "outcome": item.outcome,
                    "detail": item.detail,
                }
                for item in selection.diagnostics
            ],
        )

    def _intraday_shortlist_symbols(self, snapshots: list[MarketSnapshot]) -> list[str]:
        ranked = self.shortlist_selector.selected_candidate_signals(snapshots)
        symbols = [signal.symbol for signal in ranked]
        if len(symbols) >= self.settings.intraday_shortlist_size_safe:
            return symbols

        selected = set(symbols)
        fallback = sorted(
            (
                snapshot
                for snapshot in snapshots
                if snapshot.symbol.upper() in self.shortlist_selector.active_universe
                and snapshot.symbol.upper() not in selected
                and snapshot.volume > 0
            ),
            key=lambda item: (abs(float(item.change_percent)), float(item.volume)),
            reverse=True,
        )
        symbols.extend(
            snapshot.symbol.upper()
            for snapshot in fallback[: self.settings.intraday_shortlist_size_safe - len(symbols)]
        )
        return symbols

    def _stored_intraday_result(
        self,
        snapshots: list[MarketSnapshot],
        snapshot_status: dict[str, Any],
    ) -> MarketAgentResult:
        # An intraday event is only meaningful for a few minutes. The general
        # freshness window (market_snapshot_max_age_minutes, default 30m) is
        # too loose for that -- a symbol whose price fetch keeps failing could
        # otherwise keep showing a stale "event_triggered" signal from the
        # last successful cycle long after it stopped being current. Bound it
        # to a small multiple of the price-poll cadence instead, never looser
        # than the general freshness window.
        intraday_max_age_minutes = min(
            self.settings.agent_scheduler_interval_minutes_safe * 3,
            self.settings.market_snapshot_max_age_minutes,
        )
        intraday_cutoff = datetime.utcnow() - timedelta(minutes=intraday_max_age_minutes)

        candidates: list[MarketSnapshot] = []
        candidate_details: list[dict[str, Any]] = []
        for snapshot in snapshots:
            if snapshot.created_at < intraday_cutoff:
                continue
            signal = (snapshot.extra_json or {}).get("intraday_signal")
            if not isinstance(signal, dict) or not signal.get("event_triggered"):
                continue
            candidates.append(snapshot)
            candidate_details.append(
                {
                    "symbol": snapshot.symbol,
                    "score": float(signal.get("score") or 0),
                    "reason": str(signal.get("reason") or "intraday_event"),
                    "change_percent": snapshot.change_percent,
                    "volume": snapshot.volume,
                    **signal,
                }
            )
        # Rank by signal strength before truncating -- iteration order above
        # follows active_universe order, not score, so without this the
        # displayed candidates would be whichever symbols happen to sort
        # first rather than the strongest triggered signals.
        ranked = sorted(
            zip(candidates, candidate_details),
            key=lambda pair: pair[1]["score"],
            reverse=True,
        )
        max_candidates = self.settings.llm_max_candidates_per_run_safe
        candidates = [pair[0] for pair in ranked[:max_candidates]]
        candidate_details = [pair[1] for pair in ranked[:max_candidates]]
        return MarketAgentResult(
            snapshots=snapshots,
            candidates=candidates,
            candidate_details=candidate_details,
            market_source="stored_intraday_signals",
            snapshot_status=snapshot_status,
        )

    @staticmethod
    def _intraday_signal_to_dict(signal) -> dict[str, Any]:
        return {
            "score": signal.score,
            "reason": signal.reason,
            "return_5m_percent": signal.return_5m_percent,
            "return_15m_percent": signal.return_15m_percent,
            "volume_ratio": signal.volume_ratio,
            "vwap_deviation_percent": signal.vwap_deviation_percent,
            "spread_percent": signal.spread_percent,
            "event_triggered": signal.event_triggered,
        }

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
