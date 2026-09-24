"""Streamlit interface for the personal assistant."""

import httpx
import streamlit as st

from frontend.api_client import APIError, AssistantAPI


BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Personal AI Assistant",
    page_icon="🤖",
    layout="centered",
)


def render_app(api: AssistantAPI) -> None:
    st.title("Personal AI Assistant")
    st.caption("Your conversations, tools, and personal workspace.")

    threads = api.list_threads()

    if "thread_id" not in st.session_state:
        st.session_state.thread_id = (
            threads[0]["thread_id"] if threads else None
        )

    with st.sidebar:
        st.header("Conversations")

        with st.form("create_chat", clear_on_submit=True):
            title = st.text_input(
                "Chat title",
                placeholder="New Chat",
                max_chars=120,
            )
            create_clicked = st.form_submit_button("New chat")

        if create_clicked:
            thread = api.create_thread(title.strip() or "New Chat")
            st.session_state.thread_id = thread["thread_id"]
            st.rerun()

        if st.button("Refresh conversations"):
            st.rerun()

        st.divider()

        if not threads:
            st.caption("Create a chat to get started.")

        for thread in threads:
            selected = (
                thread["thread_id"] == st.session_state.thread_id
            )

            if st.button(
                thread["title"],
                key=f"thread_{thread['thread_id']}",
                type="primary" if selected else "secondary",
                use_container_width=True,
            ):
                st.session_state.thread_id = thread["thread_id"]
                st.rerun()

        st.caption("Showing up to 100 recent conversations.")

    thread_id = st.session_state.thread_id

    if thread_id is None:
        st.info("Create your first conversation from the sidebar.")
        return

    history = api.get_history(thread_id)

    for message in history["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    pending = history["has_pending_run"]

    if pending:
        st.warning(
            "This conversation has an active or unfinished request. "
            "If it is still running, wait and refresh. Otherwise, "
            "you can resume the saved request."
        )

        if st.button(
            "Resume unfinished request",
            key=f"resume_{thread_id}",
        ):
            with st.spinner("Resuming your request..."):
                api.resume_thread(thread_id)

            st.rerun()

    prompt = st.chat_input(
        "Ask your assistant...",
        key=f"message_{thread_id}",
        max_chars=10000,
        disabled=pending,
    )

    if prompt and prompt.strip():
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            output = st.empty()
            output.markdown("_Working on your request…_")
            text_parts = []

            try:
                for event in api.stream_message(thread_id, prompt.strip()):
                    if event["type"] == "token":
                        text_parts.append(event["text"])
                        output.markdown("".join(text_parts) + " ▌")

                    elif event["type"] == "done":
                        # Replace provisional text with the saved final answer.
                        output.markdown(event["answer"])

            except APIError:
                if text_parts:
                    output.markdown("".join(text_parts))
                else:
                    output.empty()

                st.warning(
                    "This response is incomplete or its completion "
                    "could not be confirmed."
                )
                raise

        st.rerun()


def main() -> None:
    # Longer than the backend's 90-second agent timeout.
    with httpx.Client(
        base_url=BACKEND_URL,
        timeout=httpx.Timeout(120.0, connect=5.0),
    ) as client:
        try:
            render_app(AssistantAPI(client))
        except APIError as exc:
            st.error(str(exc))
            st.info(
                "Use Refresh conversations to inspect saved progress. "
                "Messages are not resent automatically."
            )


if __name__ == "__main__":
    main()