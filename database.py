import os

import psycopg
from psycopg.rows import dict_row

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in .env")


# =================================================
# Normal PostgreSQL connection
# Used for our custom chat_threads table
# =================================================
def get_connection():
    return psycopg.connect(DATABASE_URL)


# =================================================
# Create custom table
# =================================================
def create_tables():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_threads (
                    thread_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                )
            """)

        conn.commit()


# =================================================
# Create thread
# =================================================
def create_thread(thread_id, title="New Chat"):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                INSERT INTO chat_threads (thread_id, title)
                VALUES (%s, %s)
                """,
                (thread_id, title)
            )

        conn.commit()


# =================================================
# Get threads
# =================================================
def get_threads():

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute("""
                SELECT thread_id, title, created_at, updated_at
                FROM chat_threads
                ORDER BY updated_at DESC
            """)

            return cur.fetchall()


# =================================================
# Update thread title
# =================================================
def update_thread_title(thread_id, title):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE chat_threads
                SET title = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = %s
                """,
                (title, thread_id)
            )

        conn.commit()


# =================================================
# Update thread timestamp
# =================================================
def update_thread_timestamp(thread_id):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE chat_threads
                SET updated_at = CURRENT_TIMESTAMP
                WHERE thread_id = %s
                """,
                (thread_id,)
            )

        conn.commit()


# =================================================
# Create our custom tables
# =================================================
create_tables()


# =================================================
# LangGraph PostgreSQL checkpointer
# =================================================

checkpoint_connection = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(
    checkpoint_connection
)

checkpointer.setup()