import unittest
from types import SimpleNamespace

from app.strategy.sector_candidate_selector import CandidateSelector


class SectorCandidateSelectorTest(unittest.TestCase):
    def test_ranks_only_active_universe(self):
        selector = CandidateSelector(
            active_universe=["005930", "035420"],
            max_candidates=2,
        )
        snapshots = [
            SimpleNamespace(symbol="005930", sector="semiconductor", change_percent=1.6, volume=2_000_000),
            SimpleNamespace(symbol="035420", sector="internet", change_percent=-2.0, volume=1_000_000),
            SimpleNamespace(symbol="005380", sector="automobile", change_percent=8.0, volume=9_000_000),
            SimpleNamespace(symbol="000660", sector="semiconductor", change_percent=3.0, volume=1_000_000),
        ]

        signals = selector.selected_candidate_signals(snapshots)

        self.assertEqual([signal.symbol for signal in signals], ["035420", "005930"])
        self.assertEqual(signals[0].reason, "downside_risk_or_reversal")

    def test_allows_multiple_sectors_within_active_universe(self):
        selector = CandidateSelector(
            active_universe=["005930", "005380", "207940"],
            max_candidates=3,
        )
        snapshots = [
            SimpleNamespace(symbol="005930", sector="semiconductor", change_percent=1.0, volume=2_000_000),
            SimpleNamespace(symbol="005380", sector="automobile", change_percent=2.0, volume=1_000_000),
            SimpleNamespace(symbol="207940", sector="bio", change_percent=-1.0, volume=500_000),
        ]

        signals = selector.selected_candidate_signals(snapshots)

        self.assertEqual({signal.symbol for signal in signals}, {"005930", "005380", "207940"})

    def test_ignores_zero_volume_and_flat_price(self):
        selector = CandidateSelector(
            active_universe=["005930", "035420"],
        )
        snapshots = [
            SimpleNamespace(symbol="005930", sector="semiconductor", change_percent=0, volume=2_000_000),
            SimpleNamespace(symbol="035420", sector="internet", change_percent=2.0, volume=0),
        ]

        self.assertEqual(selector.selected_candidate_signals(snapshots), [])


if __name__ == "__main__":
    unittest.main()
