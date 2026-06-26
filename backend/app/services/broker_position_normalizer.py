from typing import Any


class BrokerPositionNormalizer:
    symbol_keys = ("symbol", "ticker", "stock_code", "stockCode", "code", "pdno")
    name_keys = ("name", "stock_name", "stockName", "product_name", "productName", "prdt_name")
    quantity_keys = ("quantity", "qty", "hold_qty", "holdQty", "hldg_qty", "balance_quantity")
    avg_price_keys = ("avg_price", "average_price", "avgBuyPrice", "pchs_avg_pric", "purchase_avg_price")
    current_price_keys = ("current_price", "currentPrice", "price", "prpr", "market_price")

    def normalize_positions(self, payload: Any) -> list[dict]:
        rows = self._find_position_rows(payload)
        positions: list[dict] = []
        for row in rows:
            position = self._normalize_row(row)
            if position and position["quantity"] > 0:
                positions.append(position)
        return positions

    def _find_position_rows(self, payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        candidate_keys = (
            "positions",
            "holdings",
            "stocks",
            "items",
            "balances",
            "data",
            "result",
            "output",
            "output1",
            "output2",
            "body",
            "content",
        )
        for key in candidate_keys:
            value = payload.get(key)
            rows = self._find_position_rows(value)
            if rows:
                return rows
        return []

    def _normalize_row(self, row: dict) -> dict | None:
        symbol = self._first_text(row, self.symbol_keys)
        if not symbol:
            return None

        quantity = self._first_float(row, self.quantity_keys)
        avg_price = self._first_float(row, self.avg_price_keys)
        current_price = self._first_float(row, self.current_price_keys)
        name = self._first_text(row, self.name_keys) or symbol

        return {
            "symbol": symbol.upper(),
            "name": name,
            "quantity": quantity,
            "avg_price": avg_price,
            "current_price": current_price,
            "source": "toss_read_only",
        }

    @staticmethod
    def _first_text(row: dict, keys: tuple[str, ...]) -> str | None:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    @staticmethod
    def _first_float(row: dict, keys: tuple[str, ...]) -> float:
        for key in keys:
            value = row.get(key)
            if value is None or value == "":
                continue
            try:
                return float(str(value).replace(",", ""))
            except ValueError:
                continue
        return 0
