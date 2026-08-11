import time
from datetime import datetime
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.models import (
    AgentAction,
    AgentDecision,
    AgentSession,
    AgentSessionStatus,
    DecisionStatus,
    EvaluationWindow,
    MarketSnapshot,
    WorkflowRun,
    WorkflowRunStatus,
    WorkflowStepStatus,
)
from app.schemas import TradeJournalEntryCreate
from app.services.agent_service import AgentRunLockedError, AgentService
from app.utils.market_hours import is_market_open

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    END = "__end__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False

# Generous per-cycle node budget for LangGraph's recursion_limit. A full cycle
# (runtime_lock is entry-only) walks market->news->risk->memory->decision->
# execution_risk->logger->order->evaluation->journal->cycle_finish->loop_gate->
# next_cycle, ~13 node-steps; 20 leaves headroom for the shorter skip path.
_SESSION_NODE_STEPS_PER_CYCLE = 20


class AgentGraphState(TypedDict, total=False):
    db: Session
    trigger_source: str
    workflow: WorkflowRun
    lock: Any
    session: AgentSession
    cycle_started_at: datetime
    session_stop_reason: str
    market_result: Any
    snapshots: list[MarketSnapshot]
    candidates: list[MarketSnapshot]
    news_result: Any
    news_context: dict[str, Any]
    budget: dict[str, Any]
    memory_context: dict[str, Any]
    decision_result: Any
    decision: AgentDecision
    logged: Any
    execution_risk_result: Any
    order_result: Any
    evaluation_result: Any
    journal_entry: Any
    skip_reason: str
    agentic_path: list[str]


class AgentGraphService:
    """LangGraph-backed agent workflow runner.

    The existing agents still own their domain logic. This layer only turns the
    run into explicit graph nodes and passes shared state between them.
    """

    def __init__(self, settings=None):
        self.agent = AgentService(settings)
        self.graph = self._build_graph() if LANGGRAPH_AVAILABLE else None
        self.session_graph = self._build_session_graph() if LANGGRAPH_AVAILABLE else None

    def run_once(self, db: Session, trigger_source: str = "workflow") -> AgentDecision:
        if self.graph is None:
            return self.agent.run_once(db, trigger_source=trigger_source)

        lock = self.agent.redis_runtime.acquire_agent_run_lock()
        if not lock.acquired:
            raise AgentRunLockedError(lock.reason)

        workflow = None
        try:
            workflow = self.agent.workflow_service.start_run(
                db,
                workflow_name="agent.run_once",
                trigger_source=trigger_source,
                input_json={
                    "workflow_engine": "langgraph",
                    "active_universe": self.agent.settings.active_universe,
                    "llm_mode": self.agent.settings.llm_mode,
                    "automation_policy": self.agent._automation_policy_snapshot(),
                    "redis_lock": {
                        "enabled": lock.enabled,
                        "key": lock.key,
                        "reason": lock.reason,
                    },
                },
            )
            state = self.graph.invoke(
                {
                    "db": db,
                    "trigger_source": trigger_source,
                    "workflow": workflow,
                    "lock": lock,
                    "agentic_path": [],
                }
            )
            decision = state.get("decision")
            if decision is None:
                raise RuntimeError("LangGraph workflow completed without a decision.")
            return decision
        except Exception as exc:
            if workflow is not None and workflow.status == WorkflowRunStatus.RUNNING:
                self.agent.workflow_service.finish_run(
                    db,
                    workflow,
                    status=WorkflowRunStatus.FAILED,
                    error_message=str(exc),
                )
            raise
        finally:
            self.agent.redis_runtime.release_lock(lock)

    def run_session(
        self,
        db: Session,
        trigger_source: str = "worker",
        max_cycles: int | None = None,
    ) -> AgentSession:
        """Run a continuous multi-cycle session: repeat decision cycles inside a
        single graph invocation until a stop condition trips (see _loop_gate_node).

        See docs/plans/continuous-session-loop.md. This runs synchronously and
        paces cycles in real time (time.sleep between cycles), so callers must run
        it off the request thread (a background worker), never inside an HTTP
        request handler.
        """
        if self.session_graph is None:
            raise RuntimeError("LangGraph is not available; run_session() requires the langgraph package.")

        settings = self.agent.settings
        session_max_cycles = settings.agent_session_max_cycles_safe
        if max_cycles is not None:
            session_max_cycles = max(1, min(int(max_cycles), session_max_cycles))

        lock = self.agent.redis_runtime.acquire_agent_run_lock()
        if not lock.acquired:
            raise AgentRunLockedError(lock.reason)

        session = AgentSession(
            status=AgentSessionStatus.RUNNING,
            trigger_source=trigger_source,
            max_cycles=session_max_cycles,
            redis_lock_key=lock.key,
            redis_lock_token=lock.token,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        workflow = None
        try:
            workflow = self.agent.workflow_service.start_run(
                db,
                workflow_name="agent.run_once",
                trigger_source=trigger_source,
                input_json={
                    "workflow_engine": "langgraph",
                    "session_id": session.id,
                    "cycle_index": 0,
                    "session_max_cycles": session.max_cycles,
                    "active_universe": settings.active_universe,
                    "llm_mode": settings.llm_mode,
                    "automation_policy": self.agent._automation_policy_snapshot(),
                    "redis_lock": {
                        "enabled": lock.enabled,
                        "key": lock.key,
                        "reason": lock.reason,
                    },
                },
                session_id=session.id,
                cycle_index=0,
            )
            self.session_graph.invoke(
                {
                    "db": db,
                    "trigger_source": trigger_source,
                    "workflow": workflow,
                    "lock": lock,
                    "session": session,
                    "cycle_started_at": datetime.utcnow(),
                    "agentic_path": [],
                },
                {"recursion_limit": session.max_cycles * _SESSION_NODE_STEPS_PER_CYCLE + 10},
            )
            db.refresh(session)
            return session
        except Exception as exc:
            session.status = AgentSessionStatus.FAILED
            session.stop_reason = str(exc)
            session.finished_at = datetime.utcnow()
            db.add(session)
            db.commit()
            if workflow is not None:
                self.agent.workflow_service.fail_running_runs_for_session(db, session.id, str(exc))
            raise
        finally:
            self.agent.redis_runtime.release_lock(lock)

    def _build_graph(self):
        graph = StateGraph(AgentGraphState)
        graph.add_node("runtime_lock", self._runtime_lock_node)
        graph.add_node("market_agent", self._market_agent_node)
        graph.add_node("news_agent", self._news_agent_node)
        graph.add_node("risk_agent", self._risk_agent_node)
        graph.add_node("memory_agent", self._memory_agent_node)
        graph.add_node("decision_agent", self._decision_agent_node)
        graph.add_node("execution_risk_agent", self._execution_risk_agent_node)
        graph.add_node("logger_agent", self._logger_agent_node)
        graph.add_node("order_agent", self._order_agent_node)
        graph.add_node("evaluation_agent", self._evaluation_agent_node)
        graph.add_node("journal_agent", self._journal_agent_node)
        graph.add_node("skipped_decision", self._skipped_decision_node)
        graph.add_node("finish", self._finish_node)

        graph.set_entry_point("runtime_lock")
        graph.add_edge("runtime_lock", "market_agent")
        graph.add_edge("market_agent", "news_agent")
        graph.add_conditional_edges(
            "news_agent",
            self._route_after_news,
            {"continue": "risk_agent", "skip": "skipped_decision"},
        )
        graph.add_conditional_edges(
            "risk_agent",
            self._route_after_risk,
            {"continue": "memory_agent", "skip": "skipped_decision"},
        )
        graph.add_edge("memory_agent", "decision_agent")
        graph.add_edge("decision_agent", "execution_risk_agent")
        graph.add_edge("execution_risk_agent", "logger_agent")
        graph.add_edge("logger_agent", "order_agent")
        graph.add_edge("order_agent", "evaluation_agent")
        graph.add_edge("evaluation_agent", "journal_agent")
        graph.add_edge("journal_agent", "finish")
        graph.add_edge("finish", END)
        graph.add_edge("skipped_decision", END)
        return graph.compile()

    def _build_session_graph(self):
        """Same per-cycle node logic as _build_graph(), wired with a back-edge so
        journal_agent/skipped_decision route through loop_gate instead of ending,
        and loop_gate either starts another cycle (next_cycle -> market_agent) or
        ends the session (session_finish). runtime_lock only runs once, since the
        cyclic back-edge re-enters at market_agent, not at the entry point.
        """
        graph = StateGraph(AgentGraphState)
        graph.add_node("runtime_lock", self._runtime_lock_node)
        graph.add_node("market_agent", self._market_agent_node)
        graph.add_node("news_agent", self._news_agent_node)
        graph.add_node("risk_agent", self._risk_agent_node)
        graph.add_node("memory_agent", self._memory_agent_node)
        graph.add_node("decision_agent", self._decision_agent_node)
        graph.add_node("execution_risk_agent", self._execution_risk_agent_node)
        graph.add_node("logger_agent", self._logger_agent_node)
        graph.add_node("order_agent", self._order_agent_node)
        graph.add_node("evaluation_agent", self._evaluation_agent_node)
        graph.add_node("journal_agent", self._journal_agent_node)
        graph.add_node("skipped_decision", self._skipped_decision_node)
        graph.add_node("cycle_finish", self._finish_node)
        graph.add_node("loop_gate", self._loop_gate_node)
        graph.add_node("next_cycle", self._next_cycle_node)
        graph.add_node("session_finish", self._session_finish_node)

        graph.set_entry_point("runtime_lock")
        graph.add_edge("runtime_lock", "market_agent")
        graph.add_edge("market_agent", "news_agent")
        graph.add_conditional_edges(
            "news_agent",
            self._route_after_news,
            {"continue": "risk_agent", "skip": "skipped_decision"},
        )
        graph.add_conditional_edges(
            "risk_agent",
            self._route_after_risk,
            {"continue": "memory_agent", "skip": "skipped_decision"},
        )
        graph.add_edge("memory_agent", "decision_agent")
        graph.add_edge("decision_agent", "execution_risk_agent")
        graph.add_edge("execution_risk_agent", "logger_agent")
        graph.add_edge("logger_agent", "order_agent")
        graph.add_edge("order_agent", "evaluation_agent")
        graph.add_edge("evaluation_agent", "journal_agent")
        graph.add_edge("journal_agent", "cycle_finish")
        graph.add_edge("cycle_finish", "loop_gate")
        graph.add_edge("skipped_decision", "loop_gate")
        graph.add_conditional_edges(
            "loop_gate",
            self._route_after_loop_gate,
            {"continue": "next_cycle", "stop": "session_finish"},
        )
        graph.add_edge("next_cycle", "market_agent")
        graph.add_edge("session_finish", END)
        return graph.compile()

    def _runtime_lock_node(self, state: AgentGraphState) -> dict[str, Any]:
        lock = state["lock"]
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="runtime_lock",
            status=WorkflowStepStatus.SUCCEEDED if lock.enabled else WorkflowStepStatus.SKIPPED,
            output_json={
                "provider": "redis",
                "enabled": lock.enabled,
                "key": lock.key,
                "reason": lock.reason,
                "workflow_engine": "langgraph",
            },
        )
        return {"agentic_path": self._path(state, "runtime_lock")}

    def _market_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        market_result = self.agent.market_agent.run(state["db"])
        snapshots = market_result.snapshots
        candidates = market_result.candidates
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="market_agent",
            status=WorkflowStepStatus.SUCCEEDED,
            output_json={
                "market_source": market_result.market_source,
                "snapshot_count": len(snapshots),
                "candidate_count": len(candidates),
                "candidate_symbols": [item.symbol for item in candidates],
            },
        )
        return {
            "market_result": market_result,
            "snapshots": snapshots,
            "candidates": candidates,
            "agentic_path": self._path(state, "market_agent"),
        }

    def _news_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        news_result = self.agent.news_agent.run(state["candidates"])
        news_context = self.agent._news_context_snapshot(news_result)
        updates = {
            "news_result": news_result,
            "news_context": news_context,
            "agentic_path": self._path(state, "news_agent"),
        }
        if not state["candidates"]:
            updates["skip_reason"] = self.agent.no_candidate_reason
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="news_agent",
            status=WorkflowStepStatus.SUCCEEDED,
            input_json={"snapshot_count": len(state["snapshots"])},
            output_json={
                "source": news_result.source,
                "item_count": len(news_result.items),
                "summary": news_result.summary,
            },
        )
        return updates

    @staticmethod
    def _route_after_news(state: AgentGraphState) -> str:
        return "continue" if state.get("candidates") else "skip"

    def _risk_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        budget = self.agent.llm_budget_manager.check_budget(state["db"])
        updates = {
            "budget": budget,
            "agentic_path": self._path(state, "risk_agent"),
        }
        if not budget["approved"]:
            updates["skip_reason"] = f"LLM budget exceeded: {budget['reason']}"
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="risk_agent",
            status=WorkflowStepStatus.SUCCEEDED if budget["approved"] else WorkflowStepStatus.SKIPPED,
            output_json={
                "approved": budget["approved"],
                "reason": budget["reason"],
            },
        )
        return updates

    @staticmethod
    def _route_after_risk(state: AgentGraphState) -> str:
        budget = state.get("budget") or {}
        return "continue" if budget.get("approved") else "skip"

    def _memory_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        memory_context = self.agent.memory_agent.get_summary(state["db"], limit=100)
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="memory_agent",
            status=WorkflowStepStatus.SUCCEEDED,
            output_json={
                "lookback_journal_entries": memory_context["lookback_journal_entries"],
                "evaluated_entry_count": memory_context["evaluated_entry_count"],
                "win_rate_percent": memory_context["win_rate_percent"],
                "common_mistake_count": len(memory_context["common_mistakes"]),
                "recent_lesson_count": len(memory_context["recent_lessons"]),
                "data_gap_count": len(memory_context["data_gaps"]),
            },
        )
        return {
            "memory_context": memory_context,
            "agentic_path": self._path(state, "memory_agent"),
        }

    def _decision_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        candidates = state["candidates"]
        candidate_payload = [self.agent._snapshot_to_dict(item) for item in candidates]
        decision_result = self.agent.decision_agent.run(
            candidate_payload,
            news_context=state["news_context"],
            memory_context=state["memory_context"],
        )
        response = decision_result.response
        selected_snapshot = self.agent._find_snapshot(candidates, response["symbol"]) or candidates[0]
        usage = decision_result.usage
        decision = AgentDecision(
            symbol=response["symbol"],
            sector=selected_snapshot.sector,
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
            status=self.agent._status_for_response(
                response,
                decision_result.success,
                decision_result.guard_blocked,
            ),
            rejection_reason=self.agent._rejection_reason(
                response,
                decision_result.success,
                decision_result.error_message,
                decision_result.guard_warnings,
            ),
            dry_run=True,
        )
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
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
                "memory_lookback_journal_entries": state["memory_context"]["lookback_journal_entries"],
            },
            error_message=decision_result.error_message,
        )
        return {
            "decision_result": decision_result,
            "decision": decision,
            "agentic_path": self._path(state, "decision_agent"),
        }

    def _execution_risk_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        decision = state["decision"]
        execution_risk_result = None
        if decision.status == DecisionStatus.PENDING:
            execution_risk_result = self.agent.execution_risk_agent.validate_decision(decision, state["db"])
            if not execution_risk_result.approved:
                decision.status = DecisionStatus.REJECTED
                decision.rejection_reason = execution_risk_result.reason

        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="execution_risk_agent",
            status=(
                WorkflowStepStatus.SUCCEEDED
                if execution_risk_result
                else WorkflowStepStatus.SKIPPED
            ),
            input_json={
                "symbol": decision.symbol,
                "action": decision.action.value,
                "decision_status_before_order": decision.status.value,
            },
            output_json={
                "approved": execution_risk_result.approved if execution_risk_result else False,
                "reason": (
                    execution_risk_result.reason
                    if execution_risk_result
                    else "Decision is not pending execution."
                ),
                "decision_status": decision.status.value,
                "rejection_reason": decision.rejection_reason,
            },
        )
        return {
            "decision": decision,
            "execution_risk_result": execution_risk_result,
            "agentic_path": self._path(state, "execution_risk_agent"),
        }

    def _logger_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        logged = self.agent.logger_agent.save_decision_with_usage(
            state["db"],
            decision=state["decision"],
            decision_result=state["decision_result"],
            market_source=state["market_result"].market_source,
            candidates=state["candidates"],
            candidate_details=state["market_result"].candidate_details,
            news_context=state["news_context"],
            memory_context=state["memory_context"],
            active_universe=self.agent.settings.active_universe,
            llm_mode=self.agent.settings.llm_mode,
            max_candidates_per_run=self.agent.settings.llm_max_candidates_per_run_safe,
            real_llm_ready=self.agent.settings.real_llm_enabled,
            automation_policy=self.agent._automation_policy_snapshot(),
        )
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="logger_agent",
            status=WorkflowStepStatus.SUCCEEDED,
            output_json={
                "decision_id": logged.decision.id,
                "decision_status": logged.decision.status.value,
            },
        )
        return {
            "logged": logged,
            "decision": logged.decision,
            "agentic_path": self._path(state, "logger_agent"),
        }

    def _order_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        order_result = self.agent.order_agent.run_paper_auto(state["db"], state["decision"])
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="order_agent",
            status=WorkflowStepStatus.SUCCEEDED if order_result.attempted else WorkflowStepStatus.SKIPPED,
            output_json={
                "attempted": order_result.attempted,
                "order_id": order_result.order.id if order_result.order else None,
                "reason": order_result.reason,
            },
        )
        return {
            "order_result": order_result,
            "agentic_path": self._path(state, "order_agent"),
        }

    def _evaluation_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        evaluation_result = self.agent.evaluation_agent.run_due_evaluations(
            state["db"],
            EvaluationWindow.ONE_DAY,
        )
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="evaluation_agent",
            status=WorkflowStepStatus.SUCCEEDED if evaluation_result.created_count else WorkflowStepStatus.SKIPPED,
            input_json={"window": EvaluationWindow.ONE_DAY.value},
            output_json={
                "created_count": evaluation_result.created_count,
                "evaluation_ids": [item.id for item in evaluation_result.evaluations],
                "reason": (
                    "Due decisions were evaluated."
                    if evaluation_result.created_count
                    else "No decisions are due for the 1d evaluation window."
                ),
            },
        )
        return {
            "evaluation_result": evaluation_result,
            "agentic_path": self._path(state, "evaluation_agent"),
        }

    def _journal_agent_node(self, state: AgentGraphState) -> dict[str, Any]:
        order = state["order_result"].order
        journal_entry = self.agent.journal_agent.create_entry(
            state["db"],
            TradeJournalEntryCreate(
                decision_id=state["decision"].id,
                order_id=order.id if order else None,
                outcome_label="PENDING_REVIEW",
                agent_self_feedback=(
                    "Agent run completed. Journal entry is waiting for a fresh evaluation window."
                ),
                strategy_tags=[
                    "agent_run",
                    "paper_trading",
                    "pending_evaluation",
                ],
                journal_json={
                    "workflow_run_id": state["workflow"].id,
                    "workflow_engine": "langgraph",
                    "agentic_path": self._path(state, "journal_agent"),
                    "order_attempted": state["order_result"].attempted,
                    "order_reason": state["order_result"].reason,
                    "evaluation_window": EvaluationWindow.ONE_DAY.value,
                },
            ),
        )
        self.agent.workflow_service.record_step(
            state["db"],
            state["workflow"],
            step_name="journal_agent",
            status=WorkflowStepStatus.SUCCEEDED if journal_entry else WorkflowStepStatus.FAILED,
            input_json={"decision_id": state["decision"].id},
            output_json={
                "journal_id": journal_entry.id if journal_entry else None,
                "decision_id": state["decision"].id,
                "order_id": order.id if order else None,
                "outcome_label": journal_entry.outcome_label if journal_entry else None,
            },
            error_message=None if journal_entry else "Journal entry was not created.",
        )
        return {
            "journal_entry": journal_entry,
            "agentic_path": self._path(state, "journal_agent"),
        }

    def _finish_node(self, state: AgentGraphState) -> dict[str, Any]:
        self.agent.workflow_service.finish_run(
            state["db"],
            state["workflow"],
            status=WorkflowRunStatus.SUCCEEDED,
            decision_id=state["decision"].id,
            output_json={
                **self.agent._workflow_success_output(
                    decision=state["decision"],
                    execution_risk_result=state.get("execution_risk_result"),
                    order_result=state["order_result"],
                    evaluation_result=state["evaluation_result"],
                    journal_entry=state.get("journal_entry"),
                ),
                "workflow_engine": "langgraph",
                "agentic_path": self._path(state, "finish"),
            },
        )
        return {"agentic_path": self._path(state, "finish")}

    def _skipped_decision_node(self, state: AgentGraphState) -> dict[str, Any]:
        reason = state.get("skip_reason") or "Workflow guard stopped the run."
        decision = self.agent._save_skipped_decision(
            state["db"],
            snapshots=state.get("snapshots", []),
            news_context=state.get("news_context", {}),
            reason=reason,
        )
        self.agent._record_skipped_workflow(state["db"], state["workflow"], decision, reason)
        return {
            "decision": decision,
            "agentic_path": self._path(state, "skipped_decision"),
        }

    def _loop_gate_node(self, state: AgentGraphState) -> dict[str, Any]:
        db = state["db"]
        session = state["session"]
        settings = self.agent.settings

        # Re-read from DB: an admin may have flipped stop_requested via a separate
        # request/DB session while this cycle was running.
        db.refresh(session)
        session.cycle_count += 1

        stop_reason = self._session_stop_reason(db, session, settings)

        lock = state["lock"]
        if stop_reason is None:
            lock = self.agent.redis_runtime.renew_agent_run_lock(lock, settings.agent_session_lock_ttl_seconds)
            if not lock.acquired:
                stop_reason = lock.reason

        session.stop_reason = stop_reason
        db.add(session)
        db.commit()

        self.agent.workflow_service.record_step(
            db,
            state["workflow"],
            step_name="loop_gate",
            status=WorkflowStepStatus.SUCCEEDED,
            output_json={
                "cycle_count": session.cycle_count,
                "session_max_cycles": session.max_cycles,
                "continue": stop_reason is None,
                "stop_reason": stop_reason,
            },
        )

        return {
            "session": session,
            "lock": lock,
            "session_stop_reason": stop_reason,
            "agentic_path": self._path(state, "loop_gate"),
        }

    def _session_stop_reason(self, db: Session, session: AgentSession, settings) -> str | None:
        """First stop condition that fails, or None to continue. Order matters:
        cheap/deterministic checks first, DB/budget queries last."""
        if session.stop_requested:
            return "Admin requested the session to stop."
        if session.cycle_count >= session.max_cycles:
            return f"Session reached its max cycle count ({session.max_cycles})."
        elapsed_minutes = (datetime.utcnow() - session.started_at).total_seconds() / 60
        if elapsed_minutes >= settings.agent_session_max_minutes_safe:
            return f"Session reached its max duration ({settings.agent_session_max_minutes_safe} minutes)."
        if settings.agent_scheduler_market_hours_only and not is_market_open(settings):
            return "Market is not in regular session."

        budget = self.agent.llm_budget_manager.check_budget(db)
        if not budget["approved"]:
            return f"LLM budget exceeded: {budget['reason']}"

        trade_count = self.agent.execution_risk_agent.risk_manager.count_today_simulated_trades(db)
        if trade_count >= settings.max_daily_trades:
            return f"Daily trade limit reached ({settings.max_daily_trades})."

        return None

    @staticmethod
    def _route_after_loop_gate(state: AgentGraphState) -> str:
        return "stop" if state.get("session_stop_reason") else "continue"

    def _next_cycle_node(self, state: AgentGraphState) -> dict[str, Any]:
        db = state["db"]
        session = state["session"]
        settings = self.agent.settings

        elapsed_seconds = (datetime.utcnow() - state["cycle_started_at"]).total_seconds()
        pace_seconds = max(settings.agent_scheduler_interval_minutes_safe * 60 - elapsed_seconds, 0)
        if pace_seconds:
            time.sleep(pace_seconds)

        workflow = self.agent.workflow_service.start_run(
            db,
            workflow_name="agent.run_once",
            trigger_source=state["trigger_source"],
            input_json={
                "workflow_engine": "langgraph",
                "session_id": session.id,
                "cycle_index": session.cycle_count,
                "session_max_cycles": session.max_cycles,
                "active_universe": settings.active_universe,
                "llm_mode": settings.llm_mode,
            },
            session_id=session.id,
            cycle_index=session.cycle_count,
        )

        return {
            "workflow": workflow,
            "cycle_started_at": datetime.utcnow(),
            "skip_reason": None,
            "agentic_path": [],
        }

    def _session_finish_node(self, state: AgentGraphState) -> dict[str, Any]:
        db = state["db"]
        session = state["session"]
        session.status = (
            AgentSessionStatus.STOPPED if session.stop_requested else AgentSessionStatus.SUCCEEDED
        )
        session.finished_at = datetime.utcnow()
        db.add(session)
        db.commit()
        return {"agentic_path": self._path(state, "session_finish")}

    @staticmethod
    def _path(state: AgentGraphState, node_name: str) -> list[str]:
        return [*state.get("agentic_path", []), node_name]
