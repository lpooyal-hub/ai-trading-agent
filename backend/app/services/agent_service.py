from sqlalchemy.orm import Session

from app.agents.decision_agent import DecisionAgent
from app.agents.logger_agent import LoggerAgent
from app.agents.market_agent import MarketAgent
from app.agents.news_agent import NewsAgent
from app.agents.order_agent import OrderAgent
from app.config import Settings, get_settings
from app.models import (
    AgentAction,
    AgentDecision,
    DecisionStatus,
    MarketSnapshot,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.risk.llm_budget_manager import LLMBudgetManager
from app.services.redis_runtime_service import RedisRuntimeService
from app.services.workflow_service import WorkflowService


class AgentRunLockedError(RuntimeError):
    pass


class AgentService:
    no_candidate_reason = "No candidate passed rule-based pre-filter."

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_agent = MarketAgent(self.settings)
        self.news_agent = NewsAgent(self.settings)
        self.decision_agent = DecisionAgent(self.settings)
        self.logger_agent = LoggerAgent(self.decision_agent)
        self.order_agent = OrderAgent(self.settings)
        self.llm_budget_manager = LLMBudgetManager(self.settings)
        self.workflow_service = WorkflowService()
        self.redis_runtime = RedisRuntimeService(self.settings)

    def run_once(self, db: Session) -> AgentDecision:
        lock = self.redis_runtime.acquire_agent_run_lock()
        if not lock.acquired:
            raise AgentRunLockedError(lock.reason)

        workflow = None
        try:
            workflow = self.workflow_service.start_run(
                db,
                workflow_name="agent.run_once",
                trigger_source="manual",
                input_json={
                    "active_universe": self.settings.active_universe,
                    "llm_mode": self.settings.llm_mode,
                    "automation_policy": self._automation_policy_snapshot(),
                    "redis_lock": {
                        "enabled": lock.enabled,
                        "key": lock.key,
                        "reason": lock.reason,
                    },
                },
            )
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="runtime_lock",
                status=WorkflowStepStatus.SUCCEEDED if lock.enabled else WorkflowStepStatus.SKIPPED,
                output_json={
                    "provider": "redis",
                    "enabled": lock.enabled,
                    "key": lock.key,
                    "reason": lock.reason,
                },
            )
            market_result = self.market_agent.run(db)
            snapshots = market_result.snapshots
            candidates = market_result.candidates
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="market_agent",
                status=WorkflowStepStatus.SUCCEEDED,
                output_json={
                    "market_source": market_result.market_source,
                    "snapshot_count": len(snapshots),
                    "candidate_count": len(candidates),
                    "candidate_symbols": [item.symbol for item in candidates],
                },
            )

            news_result = self.news_agent.run(snapshots)
            news_context = self._news_context_snapshot(news_result)
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="news_agent",
                status=WorkflowStepStatus.SUCCEEDED,
                input_json={"snapshot_count": len(snapshots)},
                output_json={
                    "source": news_result.source,
                    "item_count": len(news_result.items),
                    "summary": news_result.summary,
                },
            )

            if not candidates:
                decision = self._save_skipped_decision(
                    db,
                    snapshots=snapshots,
                    news_context=news_context,
                    reason=self.no_candidate_reason,
                )
                self._record_skipped_workflow(db, workflow, decision, self.no_candidate_reason)
                return decision

            budget = self.llm_budget_manager.check_budget(db)
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="risk_agent",
                status=WorkflowStepStatus.SUCCEEDED if budget["approved"] else WorkflowStepStatus.SKIPPED,
                output_json={
                    "approved": budget["approved"],
                    "reason": budget["reason"],
                },
            )
            if not budget["approved"]:
                reason = f"LLM budget exceeded: {budget['reason']}"
                decision = self._save_skipped_decision(
                    db,
                    snapshots=snapshots,
                    news_context=news_context,
                    reason=reason,
                )
                self._record_skipped_workflow(db, workflow, decision, reason)
                return decision

            candidate_payload = [self._snapshot_to_dict(item) for item in candidates]
            decision_result = self.decision_agent.run(candidate_payload, news_context=news_context)
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
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="decision_agent",
                status=WorkflowStepStatus.SUCCEEDED if decision_result.success else WorkflowStepStatus.FAILED,
                input_json={"candidate_symbols": [item.symbol for item in candidates]},
                output_json={
                    "symbol": decision.symbol,
                    "action": decision.action.value,
                    "confidence": decision.confidence,
                    "status": decision.status.value,
                    "llm_model": decision.llm_model,
                    "total_tokens": decision.total_tokens,
                },
                error_message=decision_result.error_message,
            )

            logged = self.logger_agent.save_decision_with_usage(
                db,
                decision=decision,
                decision_result=decision_result,
                market_source=market_result.market_source,
                candidates=candidates,
                candidate_details=market_result.candidate_details,
                news_context=news_context,
                active_universe=self.settings.active_universe,
                llm_mode=self.settings.llm_mode,
                max_candidates_per_run=self.settings.llm_max_candidates_per_run_safe,
                real_llm_ready=self.settings.real_llm_enabled,
                automation_policy=self._automation_policy_snapshot(),
            )
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="logger_agent",
                status=WorkflowStepStatus.SUCCEEDED,
                output_json={
                    "decision_id": logged.decision.id,
                    "decision_status": logged.decision.status.value,
                },
            )

            order_result = self.order_agent.run_paper_auto(db, logged.decision)
            self.workflow_service.record_step(
                db,
                workflow,
                step_name="order_agent",
                status=WorkflowStepStatus.SUCCEEDED if order_result.attempted else WorkflowStepStatus.SKIPPED,
                output_json={
                    "attempted": order_result.attempted,
                    "order_id": order_result.order.id if order_result.order else None,
                    "reason": order_result.reason,
                },
            )
            self.workflow_service.finish_run(
                db,
                workflow,
                status=WorkflowRunStatus.SUCCEEDED,
                decision_id=logged.decision.id,
                output_json={
                    "decision_id": logged.decision.id,
                    "decision_status": logged.decision.status.value,
                    "order_attempted": order_result.attempted,
                },
            )
            return logged.decision
        except Exception as exc:
            if workflow is not None:
                self.workflow_service.finish_run(
                    db,
                    workflow,
                    status=WorkflowRunStatus.FAILED,
                    error_message=str(exc),
                )
            raise
        finally:
            self.redis_runtime.release_lock(lock)

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
            "redis_runtime": self.redis_runtime.status(),
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
        news_context: dict,
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
                "news_context": news_context,
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

    def _record_skipped_workflow(
        self,
        db: Session,
        workflow,
        decision: AgentDecision,
        reason: str,
    ) -> None:
        self.workflow_service.record_step(
            db,
            workflow,
            step_name="decision_agent",
            status=WorkflowStepStatus.SKIPPED,
            output_json={
                "decision_id": decision.id,
                "decision_status": decision.status.value,
                "reason": reason,
            },
        )
        self.workflow_service.finish_run(
            db,
            workflow,
            status=WorkflowRunStatus.SKIPPED,
            decision_id=decision.id,
            output_json={
                "decision_id": decision.id,
                "decision_status": decision.status.value,
                "reason": reason,
            },
        )

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
    def _news_context_snapshot(news_result) -> dict:
        return {
            "summary": news_result.summary,
            "items": news_result.items,
            "source": news_result.source,
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
