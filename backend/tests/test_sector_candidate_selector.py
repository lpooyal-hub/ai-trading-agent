import unittest
from types import SimpleNamespace

from app.strategy.sector_candidate_selector import SectorCandidateSelector


class SectorCandidateSelectorTest(unittest.TestCase):
    def test_ranks_only_allowed_sector_and_universe(self):
        selector = SectorCandidateSelector(
            active_universe=["NVDA", "AMD"],
            allowed_sector="semiconductor",
            max_candidates=2,
        )
        snapshots = [
            SimpleNamespace(symbol="NVDA", sector="semiconductor", change_percent=1.6, volume=2_000_000),
            SimpleNamespace(symbol="AMD", sector="semiconductor", change_percent=-2.0, volume=1_000_000),
            SimpleNamespace(symbol="TSLA", sector="automotive", change_percent=8.0, volume=9_000_000),
            SimpleNamespace(symbol="INTC", sector="semiconductor", change_percent=3.0, volume=1_000_000),
        ]

        signals = selector.selected_candidate_signals(snapshots)

        self.assertEqual([signal.symbol for signal in signals], ["AMD", "NVDA"])
        self.assertEqual(signals[0].reason, "downside_risk_or_reversal")

    def test_ignores_zero_volume_and_flat_price(self):
        selector = SectorCandidateSelector(
            active_universe=["NVDA", "AMD"],
            allowed_sector="semiconductor",
        )
        snapshots = [
            SimpleNamespace(symbol="NVDA", sector="semiconductor", change_percent=0, volume=2_000_000),
            SimpleNamespace(symbol="AMD", sector="semiconductor", change_percent=2.0, volume=0),
        ]

        self.assertEqual(selector.selected_candidate_signals(snapshots), [])


if __name__ == "__main__":
    unittest.main()
