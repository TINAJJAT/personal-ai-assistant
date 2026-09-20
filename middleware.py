import os
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

load_dotenv()

from langchain.agents.middleware import (
    ToolErrorMiddleware, # handles tool error
    ToolRetryMiddleware, # hanldes tool retry
    ModelRetryMiddleware, # handles model retry
    #default_retry_on, # for retry in model retry
    ModelFallbackMiddleware, # automatically fallback to alternative models when primary model fails.
    SummarizationMiddleware, # summarizes the older conversation and retains the recent ones.
    ToolCallRequest
)

# ==========================================================
# Error handling - ToolErrorMiddleware
# ==========================================================
def on_error(exc: Exception, request:ToolCallRequest) -> str | None:
    """
    Handle errors that occur during tool execution"""
    return (
        f"The tool `{request.tool_call['name']}` failed with "
        f"{type(exc).__name__}. Check the inputs and try again."
    )

tool_error = ToolErrorMiddleware(
    on_error=on_error
)

# =========================================================
# Tool Retry - ToolRetryMiddleware
# =========================================================
tool_retry = ToolRetryMiddleware(
    max_retries=2, # number of times should retry after the initial attempt failed
    backoff_factor=2, # controls how the delay grows between retries. delay = initial_delay × backoff_factor^retry_number
    initial_delay=1, # number of seconds to wait before the first retry
    max_delay=10, # prevents the delay from growing indefinitely
    jitter=True, # adds a small random variation to the retry delay
    on_failure="error",
    tools = ["get_weather", "tavily_search"] # controls which tools should retry
)

# ========================================================
# Model Retry - ModelRetryMiddleware
# ========================================================
model_retry = ModelRetryMiddleware(
    max_retries=2,
    #retry_on=default_retry_on,
    backoff_factor=2,
    initial_delay=1,
    max_delay=10,
    jitter=True
)

# ========================================================
# Model fallback - ModelFallbackMiddleware
# ========================================================
model1 = ChatOpenRouter(
    model = "nvidia/nemotron-3-ultra-550b-a55b:free", 
    temperature=0, 
    api_key=os.environ.get("OPENROUTER_API_KEY")
    )

model2 = ChatOpenRouter(
    model = "openai/gpt-6-astra:batch", 
    temperature=0, 
    api_key=os.environ.get("OPENROUTER_API_KEY")
    )

model_fallback = ModelFallbackMiddleware(
    model1, model2
)

# ========================================================
# Summarization - SummarizationMiddleware
# ========================================================
model = ChatOpenRouter(
    model = "openai/gpt-oss-20b", 
    temperature=0, 
    api_key=os.environ.get("OPENROUTER_API_KEY")
    )

summary_prompt = """
Summarize the conversation.
Preserve:
- User's important preferences
- Important facts
- Previous decisions
- Important tool results
- Unresolved tasks
"""

summarization_middleware = SummarizationMiddleware(
    model=model, # LLM to summarize the older messages
    trigger=("messages", 20), # ("tokens", 4000) or ("fraction", 0.8) start summarization when the conversation reaches 20 messages
    keep=("messages", 10), # Keep the last 10 messages
    summary_prompt=summary_prompt
)

# ========================================================
# Email Approval
# =======================================================
from langchain.agents.middleware import HumanInTheLoopMiddleware

email_approval = HumanInTheLoopMiddleware(
    interrupt_on={
        "send_gmail_message": {
            "allowed_decisions": ["approve", "reject"]
        }
    },
    description_prefix = "Review this email before sending"
)

# =========================================================
# Middleware list
# =========================================================
middleware = [
    tool_error,
    tool_retry,
    model_retry,
    model_fallback,
    summarization_middleware,
    email_approval
    ]