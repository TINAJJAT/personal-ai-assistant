"""API endpoints for personal conversation metadata."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from backend.db.threads import ThreadRepository


router = APIRouter(prefix="/threads", tags=["Conversations"])


class CreateThreadRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str = Field(default="New Chat", min_length=1, max_length=120)


class RenameThreadRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str = Field(min_length=1, max_length=120)


class ThreadResponse(BaseModel):
    thread_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


async def get_repository(request: Request) -> ThreadRepository:
    """Reuse the repository initialized during application startup."""
    repository = getattr(request.app.state, "threads", None)

    if repository is None:
        raise HTTPException(
            status_code=503,
            detail="Conversation storage is unavailable.",
        )

    return repository


Repository = Annotated[ThreadRepository, Depends(get_repository)]


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(
    body: CreateThreadRequest,
    repository: Repository,
):
    return await repository.create(title=body.title)


@router.get("", response_model=list[ThreadResponse])
async def list_threads(
    repository: Repository,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await repository.list_recent(limit=limit)


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: UUID,
    repository: Repository,
):
    thread = await repository.get(str(thread_id))

    if thread is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return thread


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def rename_thread(
    thread_id: UUID,
    body: RenameThreadRequest,
    repository: Repository,
):
    updated = await repository.rename(
        thread_id=str(thread_id),
        title=body.title,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    thread = await repository.get(str(thread_id))

    if thread is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    return thread