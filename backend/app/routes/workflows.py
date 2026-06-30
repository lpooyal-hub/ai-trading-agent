from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import WorkflowDefinitionRead, WorkflowRunRead
from app.services.workflow_service import WorkflowService


router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/definition", response_model=WorkflowDefinitionRead)
def get_workflow_definition() -> WorkflowDefinitionRead:
    return WorkflowService().get_definition()


@router.get("", response_model=list[WorkflowRunRead])
def list_workflow_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[WorkflowRunRead]:
    return WorkflowService().list_runs(db, limit=limit)


@router.get("/{run_id}", response_model=WorkflowRunRead)
def get_workflow_run(
    run_id: int,
    db: Session = Depends(get_db),
) -> WorkflowRunRead:
    run = WorkflowService().get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run was not found.")
    return run
