import uuid
import streamlit as st
from langchain_core.messages import AIMessageChunk
from langgraph.types import Command

def stream_response(agent_input, run_config):
    for chunk, metadata in agent.stream(
        agent_input,
        config=run_config,
        stream_mode="messages",
    ):
        if metadata.get("langgraph_node") != "model":
            continue

        if not isinstance(chunk, AIMessageChunk):
            continue

        for block in chunk.content_blocks:
            if block["type"] == "text":
                yield block["text"]

from agent import agent
from database import (
    create_thread,
    get_threads,
    update_thread_title,
    update_thread_timestamp,
)
# =================================================
# Page configuration
# =================================================
st.set_page_config(
    page_title = "Personal AI Assistant",
    page_icon = "🤖",
)

# =================================================
# UI
# =================================================
st.title("Personal AI Assistant")
st.caption("Powered by LangChain + OpenRouter")

# =================================================
# Session state
# =================================================
if "thread_id" not in st.session_state:

    threads = get_threads()

    if threads:

        # open most recent thread
        st.session_state.thread_id = threads[0][0]

    else:

        # create first thread
        new_thread_id = str(uuid.uuid4())

        create_thread(
            new_thread_id,
            "New Chat"
        )

        st.session_state.thread_id = new_thread_id

# =================================================
# Sidebar
# =================================================

with st.sidebar:

    st.title("💬 Chats")

    # ---------------------------------------------
    # New Chat
    # ---------------------------------------------

    if st.button(
        "➕ New Chat",
        use_container_width=True
    ):
        
        new_thread_id = str(uuid.uuid4())

        create_thread(
            new_thread_id,
            "New Chat"
        )

        st.session_state.thread_id = new_thread_id

        st.rerun()

    st.divider()


    # ---------------------------------------------
    # Existing Chats
    # ---------------------------------------------

    threads = get_threads()

    for thread in threads:

        thread_id = thread[0]
        title = thread[1]

        if st.button(
            title,
            key=f"thread_{thread_id}",
            use_container_width=True
        ):

            st.session_state.thread_id = thread_id

            st.rerun()

# =================================================
# Current Thread configuration
# =================================================
config = {
    "configurable": {
        "thread_id": st.session_state.thread_id
    }
}

# =================================================
# Get conversation from PostgreSQL
# =================================================
try:

    state = agent.get_state(config)

    messages = state.values.get(
        "messages",
        []
    )

except Exception:
    messages = []

# =================================================
# Display conversation
# =================================================
for message in messages:

    # Human message
    if message.type == "human":

        with st.chat_message("user"):
            st.markdown(message.content)

    # AI message
    elif message.type == "ai":

        with st.chat_message("assistant"):
            st.markdown(message.content)


# =================================================
# Chat input
# =================================================
# =================================================
# Human approval before sending email
# =================================================
try:
    snapshot = agent.get_state(config)

    pending_interrupts = [
        interrupt
        for task in snapshot.tasks
        for interrupt in task.interrupts
    ]

except Exception as e:
    st.error(f"Could not load approval state: {e}")
    st.stop()


if pending_interrupts:
    st.info("Review the email before sending.")

    with st.form(
        key=f"email_approval_{st.session_state.thread_id}"
    ):
        resume_decisions = {}

        for interrupt in pending_interrupts:
            decisions = []

            for index, action in enumerate(
                interrupt.value["action_requests"]
            ):
                st.write(f"**Proposed action:** {action['name']}")

                # Exact recipients, subject, body, and other arguments
                st.json(action["arguments"], expanded=True)

                choice = st.radio(
                    "Send this email?",
                    options=["Reject", "Send"],
                    key=f"approval_{interrupt.id}_{index}",
                    horizontal=True,
                )

                if choice == "Send":
                    decisions.append({"type": "approve"})
                else:
                    decisions.append({
                        "type": "reject",
                        "message": (
                            "The user rejected this email. "
                            "Do not send it or retry unless asked."
                        ),
                    })

            resume_decisions[interrupt.id] = {
                "decisions": decisions
            }

        submitted = st.form_submit_button("Apply decision")

    if submitted:
        with st.chat_message("assistant"):
            try:
                with st.spinner("Applying your decision..."):
                    st.write_stream(
                        stream_response(
                            Command(resume=resume_decisions),
                            config,
                        )
                    )

            except Exception as e:
                st.error(f"Error: {e}")
                st.stop()

        update_thread_timestamp(st.session_state.thread_id)
        st.rerun()

    # Wait for approval before accepting another message
    st.stop()

if prompt := st.chat_input("Ask me anything..."): 

    # ---------------------------------------------
    # Display user message
    # ---------------------------------------------
    with st.chat_message("user"):
        st.markdown(prompt)

    # Ask Agent 
    # with st.chat_message("assistant"): 

    #     with st.spinner("Thinking..."): 

    #         try: 

    #             result = agent.invoke(
    #                 { 
    #                     "messages": [
    #                         {
    #                             "role": "user",
    #                             "content": prompt
    #                         }
    #                     ]
    #                 },
    #                 config = {
    #                     "configurable": {
    #                         "thread_id": st.session_state.thread_id
    #                     }
    #                 }
    #             ) 

    #             answer = result["messages"][-1].content 

    #         except Exception as e: 

    #             answer = f"Error: {e}" 

    #     st.markdown(answer) 

    # Ask Agent with streaming
    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                answer = st.write_stream(
                    stream_response(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt,
                                }
                            ]
                        },
                        config,
                    )
                )

        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    # =================================================
    # Update thread metadata
    # =================================================

    threads = get_threads()

    current_thread = next(
        (
            thread
            for thread in threads
            if thread[0] == st.session_state.thread_id
        ),
        None
    )

    if current_thread:

        current_title = current_thread[1]

        # Automatically name new conversation
        if current_title == "New Chat":

            new_title = prompt[:30]

            update_thread_title(
                st.session_state.thread_id,
                new_title
            )

        # Update last-used timestamp
        update_thread_timestamp(
            st.session_state.thread_id
        )

    st.rerun()
