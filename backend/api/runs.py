from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.agent.runs import RunManager, RunStatus

router = APIRouter(prefix="/runs", tags=["Runs"])


class RunResponse(BaseModel):
    run_id: UUID
    thread_id: UUID
    status: RunStatus


def get_run_manager(request: Request) -> RunManager:
    manager = getattr(request.app.state, "runs", None)

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail="Run manager is unavailable.",
        )

    return manager


Manager = Annotated[RunManager, Depends(get_run_manager)]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: UUID, manager: Manager) -> RunResponse:
    run = manager.get(str(run_id))

    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")

    return RunResponse(**run.public_status())


@router.post("/{run_id}/stop", response_model=RunResponse)
async def stop_run(run_id: UUID, manager: Manager) -> RunResponse:
    try:
        run = manager.stop(str(run_id))
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail="Run not found.",
        ) from None

    return RunResponse(**run.public_status())