from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.models import WorkflowRun, WorkflowRunStatus, WorkflowStep, WorkflowStepStatus


class WorkflowService:
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
