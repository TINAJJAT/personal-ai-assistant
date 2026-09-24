"""Resume unfinished runs for the current read-only assistant."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from langchain_core.messages import AIMessage

from backend.api.chat import ChatResponse
from backend.api.threads import Repository


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threads", tags=["Recovery"])

# Review this policy before connecting tools that change external data.
RECOVERY_ALLOWED_TOOLS = {
    "calculator_tool",
    "get_weather",
    "tavily_search",
}


@router.post("/{thread_id}/resume", response_model=ChatResponse)
async def resume_conversation(
    thread_id: UUID,
    request: Request,
    repository: Repository,
):
    agent = request.app.state.agent
    lock = request.app.state.agent_lock
    enabled_tools = set(request.app.state.tool_names)

    if agent is None:
        raise HTTPException(503, "The assistant is unavailable.")

    if not enabled_tools.issubset(RECOVERY_ALLOWED_TOOLS):
        raise HTTPException(
            409,
            "Recovery is not configured for the currently enabled tools.",
        )

    if lock.locked():
        raise HTTPException(
            409,
            "The assistant is still processing a request. Wait and refresh.",
        )

    async with lock:
        config = {
            "configurable": {"thread_id": str(thread_id)},
            "recursion_limit": 10,
        }

        try:
            async with asyncio.timeout(90):
                thread = await repository.get(str(thread_id))

                if thread is None:
                    raise HTTPException(404, "Conversation not found.")

                snapshot = await agent.aget_state(config)

                # Approval pauses require an explicit approval decision,
                # not a generic resume request.
                if any(task.interrupts for task in snapshot.tasks):
                    raise HTTPException(
                        409,
                        "This run is waiting for approval or other input. "
                        "Use the appropriate approval flow.",
                    )

                if not snapshot.next:
                    raise HTTPException(
                        409,
                        "There is no unfinished run. Refresh the conversation.",
                    )

                # None continues saved execution without adding a new message.
                await agent.ainvoke(None, config=config)

                completed = await agent.aget_state(config)

                if completed.next:
                    raise HTTPException(
                        409,
                        "The run is still paused or unfinished.",
                    )

                messages = completed.values.get("messages", [])

                if not messages:
                    raise RuntimeError("No saved messages after recovery.")

                final_message = messages[-1]

                if (
                    not isinstance(final_message, AIMessage)
                    or final_message.tool_calls
                ):
                    raise RuntimeError("Recovery produced no final answer.")

                answer = "\n".join(
                    block["text"]
                    for block in final_message.content_blocks
                    if block["type"] == "text"
                ).strip()

                if not answer:
                    raise RuntimeError("Recovery produced empty text.")

        except HTTPException:
            raise

        except TimeoutError:
            raise HTTPException(
                504,
                "Recovery timed out. Progress may have been saved. "
                "Refresh before trying again.",
            ) from None

        except Exception as exc:
            logger.error("Recovery failed: %s", type(exc).__name__)

            raise HTTPException(
                502,
                "Recovery failed. Resolve the underlying connection, "
                "model, or tool problem before trying again.",
            ) from None

        try:
            await repository.touch(str(thread_id))
        except Exception as exc:
            logger.warning(
                "Timestamp update failed: %s",
                type(exc).__name__,
            )

        return ChatResponse(
            thread_id=thread_id,
            answer=answer,
        )