from datetime import datetime, time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import LLMPurpose, LLMUsage


class LLMUsageService:
    def list_usage(
        self,
        db: Session,
        purpose: str | None = None,
        symbol: str | None = None,
        success: bool | None = None,
    ) -> list[LLMUsage]:
        query = db.query(LLMUsage)
        if purpose:
            try:
                purpose_filter = LLMPurpose(purpose)
            except ValueError:
                return []
            query = query.filter(LLMUsage.purpose == purpose_filter)
        if symbol:
            query = query.filter(LLMUsage.symbol == symbol.upper())
        if success is not None:
            query = query.filter(LLMUsage.success.is_(success))
        return query.order_by(LLMUsage.created_at.desc()).all()

    def get_usage(self, db: Session, usage_id: int) -> LLMUsage | None:
        return db.get(LLMUsage, usage_id)

    def summarize(self, db: Session) -> dict:
        today_start = datetime.combine(datetime.utcnow().date(), time.min)
        month_start = today_start.replace(day=1)

        today_rows = self._aggregate_since(db, today_start)
        month_rows = self._aggregate_since(db, month_start)

        average_latency = db.query(func.avg(LLMUsage.latency_ms)).scalar() or 0
        return {
            "today_calls": today_rows["calls"],
            "today_prompt_tokens": today_rows["prompt_tokens"],
            "today_completion_tokens": today_rows["completion_tokens"],
            "today_total_tokens": today_rows["total_tokens"],
            "today_estimated_cost_usd": today_rows["estimated_cost_usd"],
            "monthly_estimated_cost_usd": month_rows["estimated_cost_usd"],
            "average_latency_ms": float(average_latency),
            "successful_calls": self._count_by_success(db, True),
            "failed_calls": self._count_by_success(db, False),
        }

    def _aggregate_since(self, db: Session, start: datetime) -> dict:
        row = (
            db.query(
                func.count(LLMUsage.id),
                func.coalesce(func.sum(LLMUsage.prompt_tokens), 0),
                func.coalesce(func.sum(LLMUsage.completion_tokens), 0),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0),
                func.coalesce(func.sum(LLMUsage.estimated_cost_usd), 0),
            )
            .filter(LLMUsage.created_at >= start)
            .one()
        )
        return {
            "calls": int(row[0] or 0),
            "prompt_tokens": int(row[1] or 0),
            "completion_tokens": int(row[2] or 0),
            "total_tokens": int(row[3] or 0),
            "estimated_cost_usd": float(row[4] or 0),
        }

    @staticmethod
    def _count_by_success(db: Session, success: bool) -> int:
        return db.query(LLMUsage).filter(LLMUsage.success.is_(success)).count()
