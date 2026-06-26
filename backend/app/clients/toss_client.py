class TossClient:
    def place_live_order(self, *args, **kwargs):
        # Public builds must stay DRY_RUN-only. Implement live trading only in a
        # private branch or private repository after explicit safety review.
        raise NotImplementedError("Real Toss Securities order execution is not implemented in V1.")
