from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import BotPosition, LegacyPosition
from app.schemas import LegacyPositionCreate


class PortfolioService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

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
            self.settings.bot_capital_limit_usd
            - invested_amount
            - self.settings.min_cash_reserve_usd,
            0,
        )
        pnl_percent = (unrealized_pnl / invested_amount * 100) if invested_amount else 0

        return {
            "bot_capital_limit_usd": self.settings.bot_capital_limit_usd,
            "invested_amount_usd": invested_amount,
            "available_budget_usd": available_budget,
            "min_cash_reserve_usd": self.settings.min_cash_reserve_usd,
            "bot_position_count": len(bot_positions),
            "legacy_position_count": len(legacy_positions),
            "protected_legacy_symbols": [
                position.symbol for position in legacy_positions if position.is_protected
            ],
            "bot_symbols": [position.symbol for position in bot_positions],
            "unrealized_pnl_usd": unrealized_pnl,
            "unrealized_pnl_percent": pnl_percent,
            "dry_run": self.settings.dry_run,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "use_mock_data": self.settings.use_mock_data,
            "active_universe": self.settings.active_universe,
        }
