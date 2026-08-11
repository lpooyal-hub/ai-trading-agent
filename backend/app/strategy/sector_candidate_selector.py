from dataclasses import dataclass


@dataclass
class CandidateSignal:
    symbol: str
    score: float
    reason: str
    change_percent: float
    volume: float


class CandidateSelector:
    """Rule-based candidate selector before LLM review. Ranks symbols within
    the active universe (the actual safety boundary, enforced separately by
    RiskManager) with no sector filter — the agent picks freely across
    sectors, not a single configured one."""

    def __init__(self, active_universe: list[str], max_candidates: int = 3):
        self.active_universe = {symbol.upper() for symbol in active_universe}
        self.max_candidates = max(max_candidates, 1)

    def select_candidates(self, snapshots: list) -> list:
        ranked_signals = self.rank_candidates(snapshots)
        snapshot_by_symbol = {item.symbol.upper(): item for item in snapshots}
        return [
            snapshot_by_symbol[signal.symbol]
            for signal in ranked_signals[: self.max_candidates]
            if signal.symbol in snapshot_by_symbol
        ]

    def rank_candidates(self, snapshots: list) -> list[CandidateSignal]:
        eligible = [
            item
            for item in snapshots
            if item.symbol.upper() in self.active_universe
            and item.volume > 0
            and item.change_percent != 0
        ]
        signals = [self._signal_for_snapshot(item) for item in eligible]
        return sorted(
            signals,
            key=lambda item: (item.score, abs(item.change_percent), item.volume),
            reverse=True,
        )

    def selected_candidate_signals(self, snapshots: list) -> list[CandidateSignal]:
        return self.rank_candidates(snapshots)[: self.max_candidates]

    @staticmethod
    def _signal_for_snapshot(snapshot) -> CandidateSignal:
        change = float(snapshot.change_percent)
        volume = float(snapshot.volume)
        volume_score = min(volume / 1_000_000_000, 5)
        score = round(abs(change) * 2 + volume_score, 4)
        if change >= 1.5:
            reason = "upside_momentum"
        elif change <= -1.5:
            reason = "downside_risk_or_reversal"
        elif change > 0:
            reason = "mild_positive_momentum"
        else:
            reason = "mild_negative_pressure"
        return CandidateSignal(
            symbol=snapshot.symbol.upper(),
            score=score,
            reason=reason,
            change_percent=change,
            volume=volume,
        )
