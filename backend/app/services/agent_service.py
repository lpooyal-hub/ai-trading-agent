from sqlalchemy.orm import Session

from app.clients.llm_client import LLMClient
from app.clients.mock_llm_client import MockLLMClient
from app.config import Settings, get_settings
from app.models import AgentAction, AgentDecision, DecisionStatus, LLMPurpose, MarketSnapshot
from app.risk.llm_budget_manager import LLMBudgetManager
from app.services.llm_cost_service import LLMCostService
from app.services.llm_usage_service import LLMUsageService
from app.services.market_service import MarketService
from app.services.trading_service import TradingService
from app.strategy.semiconductor_agent import SemiconductorAgent


class AgentService:
    no_candidate_reason = "No candidate passed rule-based pre-filter."

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.market_service = MarketService(self.settings)
        self.llm_client = MockLLMClient() if self.settings.use_mock_data else LLMClient(self.settings)
        self.llm_budget_manager = LLMBudgetManager(self.settings)
        self.llm_cost_service = LLMCostService(self.settings)
        self.llm_usage_service = LLMUsageService()
        self.strategy = SemiconductorAgent(
            active_universe=self.settings.active_universe,
            allowed_sector=self.settings.allowed_sector,
            max_candidates=self.settings.llm_max_candidates_per_run_safe,
        )

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
        estimated_cost = self.llm_cost_service.estimate_cost_usd(
            usage["prompt_tokens"],
            usage["completion_tokens"],
        )
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
                "candidate_details": self._candidate_details(snapshots),
                "candidate_count": len(candidates),
                "max_candidates_per_run": self.settings.llm_max_candidates_per_run_safe,
                "active_universe": self.settings.active_universe,
                "market_source": "mock_market_data" if self.settings.use_mock_data else "stored_market_snapshots",
                "llm_mode": self.settings.llm_mode,
            },
            agent_response_json={
                **llm_result.raw_response,
                "llm_mode": self.settings.llm_mode,
                "real_llm_ready": self.settings.real_llm_enabled,
                "automation_policy": self._automation_policy_snapshot(),
            },
            llm_model=self.llm_client.model,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            estimated_llm_cost_usd=estimated_cost,
            status=self._status_for_response(response, llm_result.success),
            rejection_reason=self._rejection_reason(response, llm_result),
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
            estimated_cost_usd=estimated_cost,
            latency_ms=llm_result.latency_ms,
            success=llm_result.success,
            error_message=llm_result.error_message,
            raw_usage_json={
                **usage,
                "source": self.llm_client.__class__.__name__,
                "pricing_configured": self.llm_cost_service.pricing_configured(),
                "raw_response": llm_result.raw_response,
            },
            commit=False,
        )
        db.commit()
        db.refresh(decision)
        self._execute_paper_auto_if_allowed(db, decision)
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
        market_status = self.market_service.get_snapshot_status(db)
        snapshots = self._readiness_snapshots(db)
        candidates = self._select_candidates(snapshots)
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
            "candidate_details": self._candidate_details(snapshots),
            "max_candidates_per_run": self.settings.llm_max_candidates_per_run_safe,
            "fresh_symbol_count": market_status["fresh_symbol_count"],
            "missing_symbols": market_status["missing_symbols"],
            "llm_budget_reason": str(budget["reason"]),
        }

    def _select_candidates(self, snapshots: list[MarketSnapshot]) -> list[MarketSnapshot]:
        return self.strategy.select_candidates(snapshots)

    def _candidate_details(self, snapshots: list[MarketSnapshot]) -> list[dict]:
        return [
            {
                "symbol": signal.symbol,
                "score": signal.score,
                "reason": signal.reason,
                "change_percent": signal.change_percent,
                "volume": signal.volume,
            }
            for signal in self.strategy.selected_candidate_signals(snapshots)
        ]

    def _readiness_snapshots(self, db: Session) -> list[MarketSnapshot]:
        snapshots = self.market_service.get_latest_universe_snapshots(db)
        if snapshots or not self.settings.use_mock_data:
            return snapshots

        allowed_symbols = set(self.settings.active_universe)
        preview_snapshots: list[MarketSnapshot] = []
        for item in self.market_service.mock_client.get_semiconductor_snapshots():
            symbol = item["symbol"].upper()
            if symbol not in allowed_symbols:
                continue
            preview_snapshots.append(
                MarketSnapshot(
                    symbol=symbol,
                    price=item["price"],
                    change_percent=item["change_percent"],
                    volume=item["volume"],
                    sector=item["sector"],
                    extra_json=item.get("extra_json", {}),
                )
            )
        return preview_snapshots

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

    def _execute_paper_auto_if_allowed(self, db: Session, decision: AgentDecision) -> None:
        if not self._paper_auto_decision_allowed(decision):
            return
        TradingService(self.settings).execute_approved_decision(db, decision)

    def _paper_auto_decision_allowed(self, decision: AgentDecision) -> bool:
        return bool(
            self.settings.paper_auto_enabled
            and decision.status == DecisionStatus.PENDING
            and decision.confidence >= self.settings.agent_auto_execute_min_confidence
            and decision.recommended_order_amount <= self.settings.agent_auto_execute_max_order_amount_usd
        )

    def _automation_policy_snapshot(self) -> dict:
        return {
            "automation_enabled": self.settings.agent_automation_enabled,
            "automation_mode": self.settings.agent_automation_mode_normalized,
            "paper_auto_enabled": self.settings.paper_auto_enabled,
            "min_confidence": self.settings.agent_auto_execute_min_confidence,
            "max_order_amount_usd": self.settings.agent_auto_execute_max_order_amount_usd,
        }

    @staticmethod
    def _rejection_reason(response: dict, llm_result) -> str | None:
        if not llm_result.success:
            return f"LLM call failed: {llm_result.error_message}"
        if not response.get("should_execute"):
            return "Agent did not request execution."
        return None

    @staticmethod
    def _status_for_response(response: dict, llm_success: bool = True) -> DecisionStatus:
        if not llm_success:
            return DecisionStatus.SKIPPED
        if not response.get("should_execute"):
            return DecisionStatus.SKIPPED
        if response.get("action") == AgentAction.HOLD.value:
            return DecisionStatus.SKIPPED
        return DecisionStatus.PENDING
