from sqlalchemy.orm import Session

from app.clients.mock_llm_client import MockLLMClient
from app.config import Settings, get_settings
from app.models import AgentAction, AgentDecision, DecisionStatus, LLMPurpose, MarketSnapshot
from app.risk.llm_budget_manager import LLMBudgetManager
from app.services.llm_usage_service import LLMUsageService
from app.services.market_service import MarketService


class AgentService:
    no_candidate_reason = "No candidate passed rule-based pre-filter."

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_service = MarketService(self.settings)
        self.llm_client = MockLLMClient()
        self.llm_budget_manager = LLMBudgetManager(self.settings)
        self.llm_usage_service = LLMUsageService()

    def run_once(self, db: Session) -> AgentDecision:
        snapshots = self.market_service.refresh_top_universe_snapshots(db)
        candidates = self._select_candidates(snapshots)

        if not candidates:
            return self._save_skipped_decision(
                db,
                snapshots=snapshots,
                reason=self.no_candidate_reason,
            )

        budget = self.llm_budget_manager.check_budget(db)
        if not budget["approved"]:
            return self._save_skipped_decision(
                db,
                snapshots=snapshots,
                reason=f"LLM budget exceeded: {budget['reason']}",
            )

        llm_result = self.llm_client.create_decision([self._snapshot_to_dict(item) for item in candidates])
        response = llm_result.parsed_response
        selected_snapshot = self._find_snapshot(candidates, response["symbol"]) or candidates[0]
        usage = llm_result.usage
        decision = AgentDecision(
            symbol=response["symbol"],
            sector=self.settings.allowed_sector,
            action=AgentAction(response["action"]),
            confidence=response["confidence"],
            current_price=selected_snapshot.price,
            recommended_order_amount=response["recommended_order_amount"],
            thesis=response["thesis"],
            risk_notes=response["risk_notes"],
            input_snapshot_json={
                "candidate_symbols": [item.symbol for item in candidates],
                "active_universe": self.settings.active_universe,
                "source": "mock_market_data",
            },
            agent_response_json=llm_result.raw_response,
            llm_model=self.llm_client.model,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            estimated_llm_cost_usd=0,
            status=self._status_for_response(response),
            rejection_reason=None if response.get("should_execute") else "Mock agent did not request execution.",
            dry_run=True,
        )
        db.add(decision)
        db.flush()
        self.llm_usage_service.record_usage(
            db,
            model=self.llm_client.model,
            purpose=LLMPurpose.DECISION,
            symbol=decision.symbol,
            decision_id=decision.id,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            estimated_cost_usd=0,
            latency_ms=llm_result.latency_ms,
            success=llm_result.success,
            error_message=llm_result.error_message,
            raw_usage_json={
                **usage,
                "source": "mock_llm_client",
                "raw_response": llm_result.raw_response,
            },
            commit=False,
        )
        db.commit()
        db.refresh(decision)
        return decision

    def get_status(self, db: Session) -> dict:
        latest_decision = (
            db.query(AgentDecision)
            .order_by(AgentDecision.created_at.desc())
            .first()
        )
        return {
            "dry_run": self.settings.dry_run,
            "use_mock_data": self.settings.use_mock_data,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "active_universe": self.settings.active_universe,
            "last_decision_id": latest_decision.id if latest_decision else None,
            "last_decision_status": latest_decision.status.value if latest_decision else None,
        }

    def _select_candidates(self, snapshots: list[MarketSnapshot]) -> list[MarketSnapshot]:
        eligible = [
            item
            for item in snapshots
            if item.symbol in self.settings.active_universe
            and item.sector.lower() == self.settings.allowed_sector.lower()
            and item.volume > 0
            and item.change_percent > 0
        ]
        ranked = sorted(
            eligible,
            key=lambda item: (abs(item.change_percent), item.volume),
            reverse=True,
        )
        return ranked[:3]

    @staticmethod
    def _find_snapshot(snapshots: list[MarketSnapshot], symbol: str) -> MarketSnapshot | None:
        for snapshot in snapshots:
            if snapshot.symbol == symbol:
                return snapshot
        return None

    def _save_skipped_decision(
        self,
        db: Session,
        snapshots: list[MarketSnapshot],
        reason: str,
    ) -> AgentDecision:
        decision = AgentDecision(
            symbol="NONE",
            sector=self.settings.allowed_sector,
            action=AgentAction.HOLD,
            confidence=0,
            current_price=0,
            recommended_order_amount=0,
            thesis=reason,
            risk_notes="The LLM was not called because the pre-filter found no candidate.",
            input_snapshot_json={
                "snapshot_symbols": [item.symbol for item in snapshots],
                "active_universe": self.settings.active_universe,
            },
            agent_response_json={},
            status=DecisionStatus.SKIPPED,
            rejection_reason=reason,
            dry_run=True,
        )
        db.add(decision)
        db.commit()
        db.refresh(decision)
        return decision

    @staticmethod
    def _snapshot_to_dict(snapshot: MarketSnapshot) -> dict:
        return {
            "symbol": snapshot.symbol,
            "price": snapshot.price,
            "change_percent": snapshot.change_percent,
            "volume": snapshot.volume,
            "sector": snapshot.sector,
        }

    @staticmethod
    def _status_for_response(response: dict) -> DecisionStatus:
        if not response.get("should_execute"):
            return DecisionStatus.SKIPPED
        if response.get("action") == AgentAction.HOLD.value:
            return DecisionStatus.SKIPPED
        return DecisionStatus.PENDING
