# Personal AI Assistant

A single-user AI assistant with a modular FastAPI backend and Streamlit chat interface. It combines tool calling, asynchronous execution, PostgreSQL-backed conversations, and streaming responses.

The application runs locally and uses hosted APIs for model inference, web search, and weather information.

## Implemented Features

- **Tool-assisted chat:** Calculator, current weather through OpenWeather, and web search through Tavily.
- **Streaming responses:** Progressive text updates with explicit completion and error events.
- **Persistent conversations:** LangGraph checkpoints stored in PostgreSQL preserve conversation and execution state across restarts.
- **Conversation management:** Create and switch chats in the interface; create, list, retrieve, and rename chats through the API.
- **Async execution:** Asynchronous agent calls, weather requests, and database operations.
- **Connection pooling:** Reusable PostgreSQL connections and an application-owned HTTP client for weather requests.
- **Controlled retries:** Bounded retries for selected temporary model and weather failures.
- **Input validation:** Validated tool arguments, conversation IDs, titles, and chat requests.
- **Recovery endpoint and interface:** An explicit Resume action for unfinished runs using the existing checkpoint, without submitting the user message again.

Recovery is restricted to the current calculator, weather, and search tools. It rejects approval interrupts and unreviewed tool configurations. Endpoint availability has been checked; a controlled failure-and-successful-resume test has not yet been confirmed.

## Technology Stack

| Layer | Technology |
| --- | --- |
| Language | Python 3.11+ |
| Agent framework | LangChain |
| Agent runtime and checkpointing | LangGraph |
| Hosted model integration | OpenRouter via ChatOpenRouter |
| Backend | FastAPI and Uvicorn |
| Frontend | Streamlit |
| Database | PostgreSQL |
| Async database driver | Psycopg 3 and psycopg_pool |
| HTTP client | HTTPX |
| Search | Tavily |
| Weather | OpenWeather |

## How It Works

1. Streamlit sends a message and conversation ID to FastAPI.
2. The backend loads the conversation state through the PostgreSQL checkpointer.
3. The agent calls its model and available tools as needed.
4. The backend streams text to the interface using newline-delimited JSON.
5. Checkpoints preserve execution state; a separate table stores conversation titles and timestamps.
6. On completion, the interface reloads saved conversation history.

The stream uses `token`, `done`, and `error` events. The final `done` event includes the authoritative completed answer. A disconnected stream without that event is not treated as confirmed success.

## Project Structure

```text
personal-ai-assistant/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── agent/
│   │   ├── factory.py
│   │   ├── models.py
│   │   ├── prompts.py
│   │   └── middleware.py
│   ├── api/
│   │   ├── threads.py
│   │   ├── chat.py
│   │   └── recovery.py
│   ├── db/
│   │   ├── connection.py
│   │   ├── checkpoints.py
│   │   └── threads.py
│   └── tools/
│       ├── calculator.py
│       ├── weather.py
│       ├── search.py
│       └── registry.py
├── frontend/
│   ├── app.py
│   └── api_client.py
├── scripts/
│   ├── init_db.py
│   ├── run_backend.py
│   └── check_*.py
├── .env.example
├── .gitignore
└── README.md
```

## Local Setup

These commands use Windows PowerShell. Start in the repository root with Python 3.11+ and PostgreSQL installed.

### 1. Create the environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install python-dotenv langchain langchain-openrouter langchain-tavily httpx fastapi uvicorn streamlit "psycopg[binary,pool]" langgraph-checkpoint-postgres
```

This installs the direct dependencies used by the modular application. The command is not a version-locked environment specification.

### 3. Configure the application

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your settings:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
PRIMARY_MODEL=your_exact_model_identifier
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/personal_ai_v2
TAVILY_API_KEY=your_tavily_key
WEATHER_API_KEY=your_openweather_key
USER_TIMEZONE=Asia/Kolkata
```

Leave optional tool keys empty to disable those tools. The calculator is always enabled. Use the exact model identifier available to your account and check its pricing and limits; a model's open weights do not guarantee free hosted inference.

Keep real credentials in `.env`, not `.env.example`. URL-encode special characters in database credentials when constructing the connection string.

### 4. Initialize the database

Create the `personal_ai_v2` database in PostgreSQL, then run:

```powershell
python -m scripts.init_db
```

This initializes checkpoint and conversation metadata tables inside the existing database.

### 5. Start the backend

```powershell
python -m scripts.run_backend
```

- [Health check](http://127.0.0.1:8000/health)
- [Interactive API documentation](http://127.0.0.1:8000/docs)

### 6. Start the frontend

Open a second terminal in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run frontend/app.py --server.address 127.0.0.1
```

Open [the chat interface](http://127.0.0.1:8501). Keep both terminals running.

## Example Requests

- "Use the calculator to multiply 125 by 48."
- "What is the current weather in Bengaluru, India?"
- "Find the official LangGraph persistence documentation."
- "Which numbers did I ask you to multiply earlier in this conversation?"

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Check API responsiveness |
| POST | `/threads` | Create a conversation |
| GET | `/threads` | List recent conversations |
| GET | `/threads/{thread_id}` | Retrieve conversation metadata |
| PATCH | `/threads/{thread_id}` | Rename a conversation |
| POST | `/threads/{thread_id}/messages` | Send a message |
| GET | `/threads/{thread_id}/messages` | Load saved chat history |
| POST | `/threads/{thread_id}/messages/stream` | Stream a response |
| POST | `/threads/{thread_id}/resume` | Resume an eligible unfinished run |

## Manual Checks

The project includes manual checks for configuration-dependent integrations, tool registration, agent execution, database metadata, and persistence.

```powershell
python -m scripts.check_tools
python -m scripts.check_agent
python -m scripts.check_threads
python -m scripts.check_memory write
python -m scripts.check_memory read
python -m scripts.check_memory ask
```

Model and external-tool checks consume provider quota. The thread check creates a metadata record. The memory write check requires a new test thread; use `--thread-id` with a fresh value when repeating it. Use that same value for the corresponding read and ask commands.

These are manual checks, not a comprehensive automated test suite. No task-accuracy or latency benchmark is claimed.

## Current Operating Boundaries

- Intended for one person on a local machine; no authentication is included.
- One active agent run per backend process, enforced by an async lock.
- Conversation memory is thread-scoped; preferences are not shared automatically across chats.
- The sidebar displays up to 100 recent conversations.
- Displayed message history comes from saved agent state.
- Runs have a timeout and graph-step limit. Provider availability and quota still affect completion.
- Recovery may repeat unfinished model or read-only tool calls and consume additional quota. It does not repair invalid credentials or guarantee exactly-once operations.

## Credentials and Local Data

Exclude `.env`, Google credentials and tokens, virtual environments, logs, and personal local files from version control. Commit only placeholder configuration in `.env.example`.
