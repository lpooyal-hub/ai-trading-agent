from app.models import OrderStatus


class MockTossClient:
    """Public-safe brokerage mock. It never calls Toss Securities APIs."""

    def get_portfolio(self) -> dict:
        return {
            "legacy_positions": [
                {
                    "symbol": "SPACE_X",
                    "name": "Fictional Protected Legacy Position",
                    "quantity": 1,
                    "avg_price": 100,
                    "is_protected": True,
                }
            ],
            "cash_usd": 250,
        }

    def place_live_order(self, *args, **kwargs) -> dict:
        return {
            "success": False,
            "status": OrderStatus.TODO_LIVE_ORDER_NOT_IMPLEMENTED.value,
            "message": "Mock mode does not place live orders.",
            "live_order_blocked": True,
            "raw_response_saved": False,
        }
