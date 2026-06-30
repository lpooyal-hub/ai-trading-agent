from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models import WorkflowRun, WorkflowRunStatus, WorkflowStep, WorkflowStepStatus


class WorkflowService:
    agent_workflow_definition = {
        "workflow_name": "agent.run_once",
        "description": "Agentic trading research workflow with deterministic guards and LLM decision support.",
        "nodes": [
            {
                "id": "runtime_lock",
                "label": "Runtime Lock",
                "agent_type": "system",
                "uses_llm": False,
                "runtime": "Redis",
                "responsibility": "Prevent overlapping agent runs.",
            },
            {
                "id": "market_agent",
                "label": "Market Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "Python",
                "responsibility": "Prepare market snapshots and candidate symbols.",
            },
            {
                "id": "news_agent",
                "label": "News Agent",
                "agent_type": "hybrid_ready",
                "uses_llm": False,
                "runtime": "Python",
                "responsibility": "Build current news/event context for decision input.",
            },
            {
                "id": "risk_agent",
                "label": "Risk Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "Python",
                "responsibility": "Check LLM budget and deterministic execution constraints.",
            },
            {
                "id": "memory_agent",
                "label": "Memory Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "Python",
                "responsibility": "Summarize journaled outcomes, mistakes, and lessons for the next decision.",
            },
            {
                "id": "decision_agent",
                "label": "Decision Agent",
                "agent_type": "llm",
                "uses_llm": True,
                "runtime": "OpenAI or mock LLM",
                "responsibility": "Generate BUY/SELL/HOLD decision and rationale.",
            },
            {
                "id": "execution_risk_agent",
                "label": "Execution Risk Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "Python",
                "responsibility": "Apply deterministic execution guardrails before an order can be attempted.",
            },
            {
                "id": "logger_agent",
                "label": "Logger Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "SQLAlchemy",
                "responsibility": "Persist decision, LLM usage, context, and audit payloads.",
            },
            {
                "id": "order_agent",
                "label": "Order Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "Paper execution adapter",
                "responsibility": "Attempt policy-approved paper execution while live orders stay blocked.",
            },
            {
                "id": "evaluation_agent",
                "label": "Evaluation Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "Python",
                "responsibility": "Evaluate due historical decisions and produce hindsight performance signals.",
            },
            {
                "id": "journal_agent",
                "label": "Journal Agent",
                "agent_type": "python",
                "uses_llm": False,
                "runtime": "SQLAlchemy",
                "responsibility": "Persist a decision/order journal entry for later MemoryAgent feedback.",
            },
        ],
        "edges": [
            {"from": "runtime_lock", "to": "market_agent"},
            {"from": "market_agent", "to": "news_agent"},
            {"from": "news_agent", "to": "risk_agent"},
            {"from": "risk_agent", "to": "memory_agent"},
            {"from": "memory_agent", "to": "decision_agent"},
            {"from": "decision_agent", "to": "execution_risk_agent"},
            {"from": "execution_risk_agent", "to": "logger_agent"},
            {"from": "logger_agent", "to": "order_agent"},
            {"from": "order_agent", "to": "evaluation_agent"},
            {"from": "evaluation_agent", "to": "journal_agent"},
        ],
        "side_loops": [
            {
                "name": "evaluation_memory_loop",
                "description": "Evaluation and Journal entries become MemoryAgent context for future DecisionAgent prompts.",
                "nodes": ["evaluation_agent", "journal_agent", "memory_agent", "decision_agent"],
            }
        ],
    }

    def get_definition(self) -> dict[str, Any]:
        return self.agent_workflow_definition

    def start_run(
        self,
        db: Session,
        *,
        workflow_name: str,
        trigger_source: str,
        input_json: dict[str, Any] | None = None,
    ) -> WorkflowRun:
        run = WorkflowRun(
            workflow_name=workflow_name,
            trigger_source=trigger_source,
            status=WorkflowRunStatus.RUNNING,
            input_json=input_json or {},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def finish_run(
        self,
        db: Session,
        run: WorkflowRun,
        *,
        status: WorkflowRunStatus,
        decision_id: int | None = None,
        output_json: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> WorkflowRun:
        run.status = status
        run.decision_id = decision_id
        run.output_json = output_json or {}
        run.error_message = error_message
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    def record_step(
        self,
        db: Session,
        run: WorkflowRun,
        *,
        step_name: str,
        status: WorkflowStepStatus,
        input_json: dict[str, Any] | None = None,
        output_json: dict[str, Any] | None = None,
        error_message: str | None = None,
        retry_count: int = 0,
    ) -> WorkflowStep:
        step = WorkflowStep(
            run_id=run.id,
            step_name=step_name,
            status=status,
            input_json=input_json or {},
            output_json=output_json or {},
            error_message=error_message,
            retry_count=retry_count,
            finished_at=datetime.utcnow(),
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        return step

    def list_runs(self, db: Session, limit: int = 50) -> list[WorkflowRun]:
        safe_limit = min(max(limit, 1), 200)
        return (
            db.query(WorkflowRun)
            .options(selectinload(WorkflowRun.steps))
            .order_by(WorkflowRun.started_at.desc())
            .limit(safe_limit)
            .all()
        )

    def get_run(self, db: Session, run_id: int) -> WorkflowRun | None:
        return (
            db.query(WorkflowRun)
            .options(selectinload(WorkflowRun.steps))
            .filter(WorkflowRun.id == run_id)
            .first()
        )

    def get_latest_run_for_decision(self, db: Session, decision_id: int) -> WorkflowRun | None:
        return (
            db.query(WorkflowRun)
            .options(selectinload(WorkflowRun.steps))
            .filter(WorkflowRun.decision_id == decision_id)
            .order_by(WorkflowRun.started_at.desc())
            .first()
        )
