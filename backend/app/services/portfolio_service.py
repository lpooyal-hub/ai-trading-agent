from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import BotPosition, LegacyPosition, MarketSnapshot, OrderSide, OrderStatus, TradeOrder
from app.schemas import LegacyPositionCreate
from app.services.broker_position_normalizer import BrokerPositionNormalizer
from app.services.llm_usage_service import LLMUsageService


class PortfolioService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.position_normalizer = BrokerPositionNormalizer()

    def initialize_legacy_positions(
        self,
        db: Session,
        positions: list[LegacyPositionCreate],
    ) -> tuple[list[LegacyPosition], int]:
        created: list[LegacyPosition] = []
        skipped_count = 0

        for position in positions:
            symbol = position.symbol.upper()
            existing = (
                db.query(LegacyPosition)
                .filter(LegacyPosition.symbol == symbol)
                .first()
            )
            if existing:
                skipped_count += 1
                continue

            legacy_position = LegacyPosition(
                symbol=symbol,
                name=position.name,
                quantity=position.quantity,
                avg_price=position.avg_price,
                source=position.source,
                is_protected=True,
            )
            db.add(legacy_position)
            created.append(legacy_position)

        db.commit()
        for position in created:
            db.refresh(position)

        return created, skipped_count

    def sync_legacy_positions_from_broker_payload(
        self,
        db: Session,
        payload: dict,
    ) -> tuple[list[LegacyPosition], int, str | None]:
        if self.list_bot_positions(db):
            return [], 0, "Broker legacy import is blocked after bot positions exist."

        normalized_positions = self.position_normalizer.normalize_positions(payload)
        create_payload = [
            LegacyPositionCreate(
                symbol=position["symbol"],
                name=position["name"],
                quantity=position["quantity"],
                avg_price=position["avg_price"],
                source=position["source"],
                is_protected=True,
            )
            for position in normalized_positions
        ]
        created, skipped_count = self.initialize_legacy_positions(db, create_payload)
        return created, skipped_count, None

    def list_legacy_positions(self, db: Session) -> list[LegacyPosition]:
        return (
            db.query(LegacyPosition)
            .order_by(LegacyPosition.symbol.asc())
            .all()
        )

    def list_bot_positions(self, db: Session) -> list[BotPosition]:
        return (
            db.query(BotPosition)
            .order_by(BotPosition.symbol.asc())
            .all()
        )

    def sync_bot_positions_from_market_snapshots(self, db: Session) -> tuple[list[BotPosition], int, str]:
        positions = (
            db.query(BotPosition)
            .filter(BotPosition.status == "OPEN")
            .order_by(BotPosition.symbol.asc())
            .all()
        )
        updated: list[BotPosition] = []
        skipped_count = 0

        for position in positions:
            snapshot = self._latest_market_snapshot_for_symbol(
                db,
                position.symbol,
                self.settings.market_snapshot_max_age_minutes,
            )
            if not snapshot:
                skipped_count += 1
                continue

            position.current_price = snapshot.price
            position.unrealized_pnl = (position.current_price - position.avg_buy_price) * position.quantity
            position.unrealized_pnl_percent = (
                position.unrealized_pnl / position.total_invested_amount * 100
                if position.total_invested_amount
                else 0
            )
            updated.append(position)

        db.commit()
        for position in updated:
            db.refresh(position)

        if updated:
            message = "Bot position valuation refreshed from latest market snapshots."
        else:
            message = "No bot positions were refreshed. Add fresh market snapshots first."
        return updated, skipped_count, message

    def get_summary(self, db: Session) -> dict:
        invested_amount = float(
            db.query(func.coalesce(func.sum(BotPosition.total_invested_amount), 0)).scalar()
            or 0
        )
        unrealized_pnl = float(
            db.query(func.coalesce(func.sum(BotPosition.unrealized_pnl), 0)).scalar()
            or 0
        )
        bot_positions = self.list_bot_positions(db)
        legacy_positions = self.list_legacy_positions(db)
        available_budget = max(
            self.settings.bot_capital_limit_krw
            - invested_amount
            - self.settings.min_cash_reserve_krw,
            0,
        )
        pnl_percent = (unrealized_pnl / invested_amount * 100) if invested_amount else 0

        return {
            "bot_capital_limit_krw": self.settings.bot_capital_limit_krw,
            "invested_amount_krw": invested_amount,
            "available_budget_krw": available_budget,
            "min_cash_reserve_krw": self.settings.min_cash_reserve_krw,
            "bot_position_count": len(bot_positions),
            "legacy_position_count": len(legacy_positions),
            "protected_legacy_symbols": [
                position.symbol for position in legacy_positions if position.is_protected
            ],
            "bot_symbols": [position.symbol for position in bot_positions],
            "unrealized_pnl_krw": unrealized_pnl,
            "unrealized_pnl_percent": pnl_percent,
            "dry_run": self.settings.dry_run,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "use_mock_data": self.settings.use_mock_data,
            "active_universe": self.settings.active_universe,
        }

    def get_performance(self, db: Session) -> dict:
        orders = self._list_simulated_orders(db)
        live_submitted_orders = self._list_live_submitted_orders(db)
        realized_trades = self._calculate_realized_trades(orders)
        buy_order_count = 0
        sell_order_count = 0
        gross_bought = 0.0
        gross_sold = 0.0

        for order in orders:
            if order.side == OrderSide.BUY:
                buy_order_count += 1
                gross_bought += order.order_amount
            else:
                sell_order_count += 1
                gross_sold += order.order_amount

        realized_pnl = sum(trade["realized_pnl_krw"] for trade in realized_trades)
        winning_sell_count = len([trade for trade in realized_trades if trade["realized_pnl_krw"] > 0])
        losing_sell_count = len([trade for trade in realized_trades if trade["realized_pnl_krw"] < 0])
        unrealized_pnl = float(
            db.query(func.coalesce(func.sum(BotPosition.unrealized_pnl), 0)).scalar()
            or 0
        )
        total_invested = gross_bought
        total_pnl = realized_pnl + unrealized_pnl
        total_pnl_percent = total_pnl / total_invested * 100 if total_invested else 0
        realized_sell_count = winning_sell_count + losing_sell_count
        win_rate_percent = winning_sell_count / realized_sell_count * 100 if realized_sell_count else 0
        bot_positions = self.list_bot_positions(db)

        return {
            "simulated_order_count": len(orders),
            "live_submitted_order_count": len(live_submitted_orders),
            "live_submitted_order_amount_krw": sum(order.order_amount for order in live_submitted_orders),
            "buy_order_count": buy_order_count,
            "sell_order_count": sell_order_count,
            "gross_bought_krw": gross_bought,
            "gross_sold_krw": gross_sold,
            "realized_pnl_krw": realized_pnl,
            "unrealized_pnl_krw": unrealized_pnl,
            "total_pnl_krw": total_pnl,
            "total_pnl_percent": total_pnl_percent,
            "winning_sell_count": winning_sell_count,
            "losing_sell_count": losing_sell_count,
            "win_rate_percent": win_rate_percent,
            "open_bot_position_count": len([position for position in bot_positions if position.status == "OPEN"]),
            "closed_bot_position_count": len([position for position in bot_positions if position.status == "CLOSED"]),
        }

    def get_cost_recovery(self, db: Session) -> dict:
        performance = self.get_performance(db)
        llm_summary = LLMUsageService().summarize(db)
        monthly_llm_cost_usd = llm_summary["monthly_estimated_cost_usd"]
        monthly_llm_cost_krw = monthly_llm_cost_usd * self.settings.usd_to_krw_display_rate
        total_pnl_krw = performance["total_pnl_krw"]
        realized_pnl_krw = performance["realized_pnl_krw"]
        net_after_llm_cost_krw = total_pnl_krw - monthly_llm_cost_krw
        realized_net_after_llm_cost_krw = realized_pnl_krw - monthly_llm_cost_krw

        return {
            "pnl_scope": "all_time_paper",
            "llm_cost_scope": "month_to_date",
            "paper_total_pnl_krw": total_pnl_krw,
            "paper_realized_pnl_krw": realized_pnl_krw,
            "monthly_llm_cost_usd": monthly_llm_cost_usd,
            "today_llm_cost_usd": llm_summary["today_estimated_cost_usd"],
            "net_after_llm_cost_krw": net_after_llm_cost_krw,
            "realized_net_after_llm_cost_krw": realized_net_after_llm_cost_krw,
            "llm_cost_recovery_ratio": (
                total_pnl_krw / monthly_llm_cost_krw
                if monthly_llm_cost_krw > 0
                else None
            ),
            "realized_llm_cost_recovery_ratio": (
                realized_pnl_krw / monthly_llm_cost_krw
                if monthly_llm_cost_krw > 0
                else None
            ),
            "llm_cost_covered": net_after_llm_cost_krw >= 0 if monthly_llm_cost_krw > 0 else None,
            "realized_llm_cost_covered": realized_net_after_llm_cost_krw >= 0 if monthly_llm_cost_krw > 0 else None,
            "simulated_order_count": performance["simulated_order_count"],
            "today_llm_calls": llm_summary["today_calls"],
        }

    def list_realized_trades(self, db: Session, limit: int = 25) -> list[dict]:
        realized_trades = self._calculate_realized_trades(self._list_simulated_orders(db))
        return list(reversed(realized_trades))[:limit]

    def list_symbol_performance(self, db: Session) -> list[dict]:
        realized_trades = self._calculate_realized_trades(self._list_simulated_orders(db))
        by_symbol: dict[str, dict] = {}
        for trade in realized_trades:
            symbol = trade["symbol"]
            row = by_symbol.setdefault(
                symbol,
                {
                    "symbol": symbol,
                    "realized_trade_count": 0,
                    "winning_trade_count": 0,
                    "realized_pnl_krw": 0.0,
                    "sell_amount_krw": 0.0,
                },
            )
            row["realized_trade_count"] += 1
            row["sell_amount_krw"] += trade["sell_amount_krw"]
            row["realized_pnl_krw"] += trade["realized_pnl_krw"]
            if trade["realized_pnl_krw"] > 0:
                row["winning_trade_count"] += 1

        result = []
        for row in by_symbol.values():
            trade_count = row["realized_trade_count"]
            result.append({
                "symbol": row["symbol"],
                "realized_trade_count": trade_count,
                "realized_pnl_krw": row["realized_pnl_krw"],
                "sell_amount_krw": row["sell_amount_krw"],
                "win_rate_percent": row["winning_trade_count"] / trade_count * 100 if trade_count else 0,
            })
        return sorted(result, key=lambda item: item["realized_pnl_krw"], reverse=True)

    @staticmethod
    def _list_simulated_orders(db: Session) -> list[TradeOrder]:
        return (
            db.query(TradeOrder)
            .filter(TradeOrder.status == OrderStatus.SIMULATED)
            .order_by(TradeOrder.created_at.asc(), TradeOrder.id.asc())
            .all()
        )

    @staticmethod
    def _list_live_submitted_orders(db: Session) -> list[TradeOrder]:
        return (
            db.query(TradeOrder)
            .filter(TradeOrder.status == OrderStatus.LIVE_SUBMITTED)
            .order_by(TradeOrder.created_at.asc(), TradeOrder.id.asc())
            .all()
        )

    @staticmethod
    def _calculate_realized_trades(orders: list[TradeOrder]) -> list[dict]:
        quantity_by_symbol: dict[str, float] = {}
        cost_by_symbol: dict[str, float] = {}
        realized_trades: list[dict] = []

        for order in orders:
            symbol = order.symbol.upper()
            if order.side == OrderSide.BUY:
                quantity_by_symbol[symbol] = quantity_by_symbol.get(symbol, 0) + order.quantity
                cost_by_symbol[symbol] = cost_by_symbol.get(symbol, 0) + order.order_amount
                continue

            held_quantity = quantity_by_symbol.get(symbol, 0)
            held_cost = cost_by_symbol.get(symbol, 0)
            avg_cost = held_cost / held_quantity if held_quantity else 0
            matched_quantity = min(order.quantity, held_quantity)
            cost_basis = avg_cost * matched_quantity
            realized_pnl = order.order_amount - cost_basis
            realized_pnl_percent = realized_pnl / cost_basis * 100 if cost_basis else 0
            if matched_quantity > 0:
                realized_trades.append({
                    "order_id": order.id,
                    "created_at": order.created_at,
                    "symbol": symbol,
                    "quantity": matched_quantity,
                    "sell_amount_krw": order.order_amount,
                    "cost_basis_krw": cost_basis,
                    "realized_pnl_krw": realized_pnl,
                    "realized_pnl_percent": realized_pnl_percent,
                })
            quantity_by_symbol[symbol] = max(held_quantity - matched_quantity, 0)
            cost_by_symbol[symbol] = max(held_cost - cost_basis, 0)

        return realized_trades

    @staticmethod
    def _latest_market_snapshot_for_symbol(
        db: Session,
        symbol: str,
        max_age_minutes: int,
    ) -> MarketSnapshot | None:
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        return (
            db.query(MarketSnapshot)
            .filter(MarketSnapshot.symbol == symbol.upper())
            .filter(MarketSnapshot.created_at >= cutoff)
            .order_by(MarketSnapshot.created_at.desc())
            .first()
        )
