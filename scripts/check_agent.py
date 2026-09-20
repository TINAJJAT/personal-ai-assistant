"""Check the complete async model-tool-answer workflow."""

import asyncio

import httpx
from langchain_core.messages import AIMessage, ToolMessage

from backend.config import load_settings
from backend.agent.factory import build_agent
from backend.tools.registry import build_tools


async def main() -> None:
    settings = load_settings()

    async with httpx.AsyncClient() as client:
        tools = build_tools(settings, client)
        agent = build_agent(settings, tools)

        print("Running the agent...")

        result = await asyncio.wait_for(
            agent.ainvoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Use calculator_tool to multiply 125 by 48. "
                                "Then give me the result in one sentence."
                            ),
                        }
                    ]
                },
                config={"recursion_limit": 10},
            ),
            timeout=90,
        )

        messages = result["messages"]

        calculator_results = [
            message
            for message in messages
            if isinstance(message, ToolMessage)
            and message.name == "calculator_tool"
        ]

        if not calculator_results:
            raise RuntimeError("The agent did not execute the calculator.")

        for message in calculator_results:
            if message.status == "error":
                raise RuntimeError("The calculator returned a tool error.")

            if float(message.content) != 6000:
                raise RuntimeError("The calculation result was incorrect.")

            print("Calculator result:", message.content)

        final_message = messages[-1]

        if (
            not isinstance(final_message, AIMessage)
            or final_message.tool_calls
            or not final_message.content
        ):
            raise RuntimeError("The agent did not finish with an answer.")

        print("Assistant:", final_message.content)
        print("\nAgent workflow check passed.")


if __name__ == "__main__":
    asyncio.run(main())