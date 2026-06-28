class SemiconductorAgent:
    """Rule-based semiconductor candidate selector before LLM review."""

    def __init__(self, active_universe: list[str], allowed_sector: str):
        self.active_universe = {symbol.upper() for symbol in active_universe}
        self.allowed_sector = allowed_sector.lower()

    def select_candidates(self, snapshots: list) -> list:
        eligible = [
            item
            for item in snapshots
            if item.symbol.upper() in self.active_universe
            and item.sector.lower() == self.allowed_sector
            and item.volume > 0
            and item.change_percent > 0
        ]
        ranked = sorted(
            eligible,
            key=lambda item: (abs(item.change_percent), item.volume),
            reverse=True,
        )
        return ranked[:3]
