from sqlalchemy.orm import Session

from app.agents.decision_agent import DecisionAgent
from app.agents.logger_agent import LoggerAgent
from app.agents.market_agent import MarketAgent
from app.agents.order_agent import OrderAgent
from app.config import Settings, get_settings
from app.models import AgentAction, AgentDecision, DecisionStatus, MarketSnapshot
from app.risk.llm_budget_manager import LLMBudgetManager


class AgentService:
    no_candidate_reason = "No candidate passed rule-based pre-filter."

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_agent = MarketAgent(self.settings)
        self.decision_agent = DecisionAgent(self.settings)
        self.logger_agent = LoggerAgent(self.decision_agent)
        self.order_agent = OrderAgent(self.settings)
        self.llm_budget_manager = LLMBudgetManager(self.settings)

    def run_once(self, db: Session) -> AgentDecision:
        market_result = self.market_agent.run(db)
        snapshots = market_result.snapshots
        candidates = market_result.candidates

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

        candidate_payload = [self._snapshot_to_dict(item) for item in candidates]
        decision_result = self.decision_agent.run(candidate_payload)
        response = decision_result.response
        selected_snapshot = self._find_snapshot(candidates, response["symbol"]) or candidates[0]
        usage = decision_result.usage
        decision = AgentDecision(
            symbol=response["symbol"],
            sector=self.settings.allowed_sector,
            action=AgentAction(response["action"]),
            confidence=response["confidence"],
            current_price=selected_snapshot.price,
            recommended_order_amount=response["recommended_order_amount"],
            thesis=response["thesis"],
            risk_notes=response["risk_notes"],
            llm_model=decision_result.model,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            estimated_llm_cost_usd=decision_result.estimated_cost_usd,
            status=self._status_for_response(response, decision_result.success, decision_result.guard_blocked),
            rejection_reason=self._rejection_reason(
                response,
                decision_result.success,
                decision_result.error_message,
                decision_result.guard_warnings,
            ),
            dry_run=True,
        )
        logged = self.logger_agent.save_decision_with_usage(
            db,
            decision=decision,
            decision_result=decision_result,
            market_source=market_result.market_source,
            candidates=candidates,
            candidate_details=market_result.candidate_details,
            active_universe=self.settings.active_universe,
            llm_mode=self.settings.llm_mode,
            max_candidates_per_run=self.settings.llm_max_candidates_per_run_safe,
            real_llm_ready=self.settings.real_llm_enabled,
            automation_policy=self._automation_policy_snapshot(),
        )
        self.order_agent.run_paper_auto(db, logged.decision)
        return logged.decision

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
            "automation_enabled": self.settings.agent_automation_enabled,
            "automation_mode": self.settings.agent_automation_mode_normalized,
            "paper_auto_enabled": self.settings.paper_auto_enabled,
            "active_universe": self.settings.active_universe,
            "last_decision_id": latest_decision.id if latest_decision else None,
            "last_decision_status": latest_decision.status.value if latest_decision else None,
        }

    def get_automation_policy(self) -> dict:
        blockers = self._paper_auto_blockers()
        return {
            "automation_enabled": self.settings.agent_automation_enabled,
            "automation_mode": self.settings.agent_automation_mode_normalized,
            "paper_auto_enabled": self.settings.paper_auto_enabled,
            "min_confidence": self.settings.agent_auto_execute_min_confidence,
            "max_order_amount_usd": self.settings.agent_auto_execute_max_order_amount_usd,
            "dry_run": self.settings.dry_run,
            "live_trading_enabled": self.settings.live_trading_enabled,
            "blockers": blockers,
            "next_actions": self._automation_next_actions(blockers),
        }

    def get_readiness(self, db: Session) -> dict:
        market_result = self.market_agent.preview(db)
        market_status = market_result.snapshot_status or {}
        candidates = market_result.candidates
        budget = self.llm_budget_manager.check_budget(db)
        budget_ready = bool(budget["approved"])
        market_ready = bool(candidates)
        ready = market_ready and budget_ready
        reason = "Agent can run once." if ready else self._readiness_reason(market_ready, budget_ready, budget)
        automation_ready = ready and self.settings.real_llm_enabled
        automation_reason = (
            "Real LLM agent automation can run in DRY_RUN."
            if automation_ready
            else self._automation_readiness_reason(ready, reason)
        )
        paper_auto_blockers = self._paper_auto_blockers()
        paper_auto_ready = ready and not paper_auto_blockers
        return {
            "ready": ready,
            "reason": reason,
            "automation_ready": automation_ready,
            "automation_reason": automation_reason,
            "paper_auto_ready": paper_auto_ready,
            "paper_auto_reason": "Paper auto execution can run." if paper_auto_ready else " ".join(paper_auto_blockers),
            "llm_mode": self.settings.llm_mode,
            "llm_blockers": self.settings.llm_readiness_blockers,
            "dry_run": self.settings.dry_run,
            "use_mock_data": self.settings.use_mock_data,
            "real_llm_ready": self.settings.real_llm_enabled,
            "market_ready": market_ready,
            "budget_ready": budget_ready,
            "candidate_symbols": [snapshot.symbol for snapshot in candidates],
            "candidate_details": market_result.candidate_details,
            "max_candidates_per_run": self.settings.llm_max_candidates_per_run_safe,
            "fresh_symbol_count": market_status.get("fresh_symbol_count", 0),
            "missing_symbols": market_status.get("missing_symbols", []),
            "llm_budget_reason": str(budget["reason"]),
        }

    @staticmethod
    def _readiness_reason(market_ready: bool, budget_ready: bool, budget: dict) -> str:
        reasons: list[str] = []
        if not market_ready:
            reasons.append("No market candidate passed the rule-based pre-filter.")
        if not budget_ready:
            reasons.append(f"LLM budget blocked: {budget['reason']}")
        return " ".join(reasons)

    def _automation_readiness_reason(self, run_ready: bool, run_reason: str) -> str:
        reasons: list[str] = []
        if not run_ready:
            reasons.append(run_reason)
        reasons.extend(self.settings.llm_readiness_blockers)
        return " ".join(reasons)

    def _paper_auto_blockers(self) -> list[str]:
        blockers: list[str] = []
        if not self.settings.agent_automation_enabled:
            blockers.append("AGENT_AUTOMATION_ENABLED is false.")
        if self.settings.agent_automation_mode_normalized != "paper_auto":
            blockers.append("AGENT_AUTOMATION_MODE is not paper_auto.")
        if not self.settings.dry_run:
            blockers.append("DRY_RUN must stay true for paper auto execution.")
        if self.settings.live_trading_enabled:
            blockers.append("LIVE_TRADING_ENABLED must stay false for paper auto execution.")
        return blockers

    @staticmethod
    def _automation_next_actions(blockers: list[str]) -> list[str]:
        if not blockers:
            return ["Review generated orders and LLM usage after each paper auto run."]
        return [
            "Keep real live orders blocked while validating paper automation.",
            "Set AGENT_AUTOMATION_ENABLED=true and AGENT_AUTOMATION_MODE=paper_auto only after reviewing risk limits.",
        ]

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
            risk_notes=self._skipped_risk_notes(reason),
            input_snapshot_json={
                "snapshot_symbols": [item.symbol for item in snapshots],
                "snapshot_count": len(snapshots),
                "max_candidates_per_run": self.settings.llm_max_candidates_per_run_safe,
                "active_universe": self.settings.active_universe,
                "llm_mode": self.settings.llm_mode,
            },
            agent_response_json={
                "skip_reason": reason,
                "skip_reason_category": self._skip_reason_category(reason),
                "llm_mode": self.settings.llm_mode,
                "real_llm_ready": self.settings.real_llm_enabled,
                "llm_blockers": self.settings.llm_readiness_blockers,
                "automation_policy": self._automation_policy_snapshot(),
            },
            status=DecisionStatus.SKIPPED,
            rejection_reason=reason,
            dry_run=True,
        )
        return self.logger_agent.save_skipped_decision(db, decision).decision

    @staticmethod
    def _snapshot_to_dict(snapshot: MarketSnapshot) -> dict:
        return {
            "symbol": snapshot.symbol,
            "price": snapshot.price,
            "change_percent": snapshot.change_percent,
            "volume": snapshot.volume,
            "sector": snapshot.sector,
        }

    def _skipped_risk_notes(self, reason: str) -> str:
        if self.settings.llm_mode != "real_openai":
            return "No real OpenAI LLM call was made. This is not an autonomous AI trading decision."
        if reason == self.no_candidate_reason:
            return "The LLM was not called because the pre-filter found no candidate."
        return "The LLM was not called because a readiness or budget guard blocked the run."

    def _skip_reason_category(self, reason: str) -> str:
        if reason == self.no_candidate_reason:
            return "NO_CANDIDATE"
        if "budget" in reason.lower() or "cooldown" in reason.lower() or "limit" in reason.lower():
            return "LLM_COST_GUARD"
        if self.settings.llm_mode != "real_openai":
            return "LLM_NOT_READY"
        return "AGENT_GUARD"

    def _automation_policy_snapshot(self) -> dict:
        return {
            "automation_enabled": self.settings.agent_automation_enabled,
            "automation_mode": self.settings.agent_automation_mode_normalized,
            "paper_auto_enabled": self.settings.paper_auto_enabled,
            "min_confidence": self.settings.agent_auto_execute_min_confidence,
            "max_order_amount_usd": self.settings.agent_auto_execute_max_order_amount_usd,
        }

    @staticmethod
    def _rejection_reason(
        response: dict,
        llm_success: bool,
        error_message: str | None,
        guard_warnings: list[str],
    ) -> str | None:
        if not llm_success:
            return f"LLM call failed: {error_message}"
        if guard_warnings:
            return f"LLM response guard blocked execution: {'; '.join(guard_warnings)}"
        if not response.get("should_execute"):
            return "Agent did not request execution."
        return None

    @staticmethod
    def _status_for_response(
        response: dict,
        llm_success: bool = True,
        guard_blocked: bool = False,
    ) -> DecisionStatus:
        if not llm_success or guard_blocked:
            return DecisionStatus.SKIPPED
        if not response.get("should_execute"):
            return DecisionStatus.SKIPPED
        if response.get("action") == AgentAction.HOLD.value:
            return DecisionStatus.SKIPPED
        return DecisionStatus.PENDING
