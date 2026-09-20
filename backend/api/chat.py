"""API endpoint for sending messages to the personal assistant."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, AIMessageChunk
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from backend.api.threads import Repository

import json
from contextlib import aclosing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["Chat"])


class ChatRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    message: str = Field(min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    thread_id: UUID
    answer: str


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class HistoryResponse(BaseModel):
    thread_id: UUID
    messages: list[HistoryMessage]
    has_pending_run: bool


@router.post("/{thread_id}/messages", response_model=ChatResponse)
async def send_message(
    thread_id: UUID,
    body: ChatRequest,
    request: Request,
    repository: Repository,
):
    agent = request.app.state.agent
    lock = request.app.state.agent_lock

    if agent is None:
        raise HTTPException(503, "The assistant is unavailable.")

    # One active agent run at a time for this personal application.
    if lock.locked():
        raise HTTPException(
            409,
            "The assistant is already processing a message. Wait for it to finish.",
        )

    async with lock:
        thread = await repository.get(str(thread_id))

        if thread is None:
            raise HTTPException(404, "Conversation not found.")

        config = {
            "configurable": {"thread_id": str(thread_id)},
            "recursion_limit": 10,
        }

        try:
            async with asyncio.timeout(90):
                snapshot = await agent.aget_state(config)

                if snapshot.next:
                    raise HTTPException(
                        409,
                        "This conversation has an unfinished run. "
                        "Recovery is required before adding another message.",
                    )

                result = await agent.ainvoke(
                    {
                        "messages": [
                            {"role": "user", "content": body.message}
                        ]
                    },
                    config=config,
                )

                final_message = result["messages"][-1]

                if (
                    not isinstance(final_message, AIMessage)
                    or final_message.tool_calls
                ):
                    raise RuntimeError("Agent did not finish with an answer.")

                answer = "\n".join(
                    block["text"]
                    for block in final_message.content_blocks
                    if block["type"] == "text"
                ).strip()

                if not answer:
                    raise RuntimeError("Agent returned no final text.")

        except HTTPException:
            raise

        except TimeoutError:
            raise HTTPException(
                504,
                "The assistant exceeded the response time limit. "
                "Partial progress may have been saved. "
                "Do not automatically resend the message.",
            ) from None

        except Exception as exc:
            # Log the exception type without exposing keys or request URLs.
            logger.error("Agent run failed: %s", type(exc).__name__)

            raise HTTPException(
                502,
                "The assistant could not complete this request. "
                "Partial progress may have been saved.",
            ) from None

        # A sidebar timestamp failure should not discard a completed answer.
        try:
            await repository.touch(str(thread_id))
        except Exception as exc:
            logger.warning(
                "Conversation timestamp update failed: %s",
                type(exc).__name__,
            )

        return ChatResponse(
            thread_id=thread_id,
            answer=answer,
        )

@router.get(
    "/{thread_id}/messages",
    response_model=HistoryResponse,
)
async def get_messages(
    thread_id: UUID,
    request: Request,
    repository: Repository,
):
    thread = await repository.get(str(thread_id))

    if thread is None:
        raise HTTPException(404, "Conversation not found.")

    agent = request.app.state.agent

    if agent is None:
        raise HTTPException(503, "The assistant is unavailable.")

    config = {
        "configurable": {"thread_id": str(thread_id)}
    }

    try:
        async with asyncio.timeout(15):
            snapshot = await agent.aget_state(config)

    except TimeoutError:
        raise HTTPException(
            504,
            "Loading conversation history timed out.",
        ) from None

    except Exception as exc:
        logger.error(
            "History loading failed: %s",
            type(exc).__name__,
        )
        raise HTTPException(
            503,
            "Conversation history is temporarily unavailable.",
        ) from None

    history = []

    for message in snapshot.values.get("messages", []):
        if isinstance(message, HumanMessage):
            role = "user"

        elif isinstance(message, AIMessage):
            # Exclude intermediate messages requesting tool execution.
            if message.tool_calls:
                continue

            role = "assistant"

        else:
            # Tool results are internal execution details.
            continue

        text = "\n".join(
            block["text"]
            for block in message.content_blocks
            if block["type"] == "text"
        ).strip()

        if text:
            history.append(
                HistoryMessage(role=role, content=text)
            )

    return HistoryResponse(
        thread_id=thread_id,
        messages=history,
        has_pending_run=bool(snapshot.next),
    )

def encode_event(event_type: str, **data) -> str:
    """Encode one newline-delimited JSON event."""
    return json.dumps(
        {"type": event_type, **data},
        ensure_ascii=False,
    ) + "\n"


@router.post("/{thread_id}/messages/stream")
async def stream_message(
    thread_id: UUID,
    body: ChatRequest,
    request: Request,
    repository: Repository,
):
    agent = request.app.state.agent
    lock = request.app.state.agent_lock

    if agent is None:
        raise HTTPException(503, "The assistant is unavailable.")

    thread = await repository.get(str(thread_id))

    if thread is None:
        raise HTTPException(404, "Conversation not found.")

    config = {
        "configurable": {"thread_id": str(thread_id)},
        "recursion_limit": 10,
    }

    async def generate():
        # Check again here because streaming starts after the route returns.
        if lock.locked():
            yield encode_event(
                "error",
                message="The assistant is busy. Wait for the current request.",
            )
            return

        async with lock:
            try:
                async with asyncio.timeout(90):
                    snapshot = await agent.aget_state(config)

                    if snapshot.next:
                        yield encode_event(
                            "error",
                            message=(
                                "This conversation has an unfinished run. "
                                "Recovery is required before another message."
                            ),
                        )
                        return

                    stream = agent.astream(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": body.message,
                                }
                            ]
                        },
                        config=config,
                        stream_mode="messages",
                    )

                    # Close the graph iterator if streaming is interrupted.
                    async with aclosing(stream):
                        async for chunk, metadata in stream:
                            if metadata.get("langgraph_node") != "model":
                                continue

                            if not isinstance(chunk, AIMessageChunk):
                                continue

                            for block in chunk.content_blocks:
                                if block["type"] == "text":
                                    yield encode_event(
                                        "token",
                                        text=block["text"],
                                    )

                    # Check the persisted final state before claiming success.
                    snapshot = await agent.aget_state(config)
                    messages = snapshot.values.get("messages", [])

                    if snapshot.next or not messages:
                        raise RuntimeError("The run did not complete.")

                    final_message = messages[-1]

                    if (
                        not isinstance(final_message, AIMessage)
                        or final_message.tool_calls
                    ):
                        raise RuntimeError("No final assistant answer.")

                    answer = "\n".join(
                        block["text"]
                        for block in final_message.content_blocks
                        if block["type"] == "text"
                    ).strip()

                    if not answer:
                        raise RuntimeError("The final answer was empty.")

            except TimeoutError:
                yield encode_event(
                    "error",
                    message=(
                        "The response timed out. Partial progress may be "
                        "saved. Refresh before sending another message."
                    ),
                )
                return

            except Exception as exc:
                logger.error("Streaming failed: %s", type(exc).__name__)
                yield encode_event(
                    "error",
                    message=(
                        "The response could not be completed. "
                        "Partial progress may be saved."
                    ),
                )
                return

            try:
                await repository.touch(str(thread_id))
            except Exception as exc:
                logger.warning(
                    "Timestamp update failed: %s",
                    type(exc).__name__,
                )

            yield encode_event("done", answer=answer)

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache"},
    )