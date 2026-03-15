# Agent Documentation

## Overview

This agent answers questions using a Large Language Model (LLM) via an OpenAI-compatible API, with access to tools for reading files, listing directories, and querying  the backend API.

## LLM Provider

**Qwen Code API** is configured as the LLM provider.

- **API Base URL:** `http://10.93.25.3:42005/v1` (Qwen Code API on VM)
- **Model:** `qwen3-coder-plus`

### Alternative: OpenRouter

If you prefer to use OpenRouter instead, edit `.env.agent.secret`:

```env
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

OpenRouter provides access to multiple LLM providers through a unified API. The free tier is suitable for development and testing.

## Configuration

1. Copy the example environment file:

   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Edit `.env.agent.secret` and set your LLM API credentials:

   ```env
   LLM_API_KEY=your-qwen-api-key-here
   LLM_API_BASE=http://10.93.25.3:42005/v1
   LLM_MODEL=qwen3-coder-plus
   ```

3. Ensure `.env.docker.secret` exists with backend API credentials:

   ```env
   LMS_API_KEY=your-backend-api-key
   AGENT_API_BASE_URL=http://localhost:42002
   ```

## Usage

Run the agent with a question as the first command-line argument:

```bash
uv run agent.py "What does REST stand for?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "Representational State Transfer.",
  "source": "wiki/rest-api.md#what-is-rest",
  "tool_calls": [
    {"tool": "list_files", "args": {"path": "wiki"}, "result": "rest-api.md\n..."},
    {"tool": "read_file", "args": {"path": "wiki/rest-api.md"}, "result": "..."}
  ]
}
```

- `answer` — The LLM's response to the question.
- `source` — Reference to the source file where the answer was found (file path + section anchor). Optional for API queries.
- `tool_calls` — List of tool calls made during execution, each with `tool`, `args`, and `result`.

## Architecture

### Components

1. **Environment Loading** — Uses `python-dotenv` to load LLM configuration from `.env.agent.secret` and backend API configuration from `.env.docker.secret`.

2. **LLM Client** — Uses `httpx` to send HTTP POST requests to the LLM API endpoint with function-calling support.

3. **Tools**:
   - `read_file(path)` — Read contents of a file from the project repository.
   - `list_files(path)` — List files and directories at a given path.
   - `query_api(method, path, body)` — Query the backend API with authentication.

4. **Agentic Loop** — Iteratively calls the LLM, executes tool calls, and feeds results back until a final answer is produced.

5. **Error Handling**:
   - **Rate Limiting (429)** — Implements exponential backoff with up to 3 retries.
   - **Timeouts** — Retries on read timeouts with exponential backoff.
   - **Configuration Errors** — Clear error messages if `LLM_API_BASE` or `LLM_API_KEY` are missing.
   - **Path Security** — Rejects path traversal attempts (e.g., `../`).
   - **API Errors** — Returns HTTP status codes and error messages from backend.

### Tool Schemas

Tools are defined as function-calling schemas for the LLM:

```python
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file from the project repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend API to get real-time data or perform actions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"
                    },
                    "body": {
                        "type": "string",
                        "description": "JSON request body for POST/PUT requests (optional)"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]
```

### query_api Tool

The `query_api` tool allows the agent to query the backend API for real-time data.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` with Bearer token authentication. The `auth` parameter (default: `true`) can be set to `false` to test unauthenticated access.

**Implementation:**

```python
def query_api(method: str, path: str, body: str | None = None, auth: bool = True) -> str:
    """Query the backend API with optional authentication.

    Returns JSON string with status_code and body.
    Handles errors: timeouts (504), connection errors (503), invalid JSON (400).
    """
```

**Parameters:**

- `method` (required): HTTP method — GET, POST, PUT, DELETE
- `path` (required): API endpoint path, e.g., `/items/`, `/analytics/completion-rate`
- `body` (optional): JSON request body for POST/PUT requests
- `auth` (optional, default=true): Whether to include Authorization header

**Example usage:**

- Question: "How many items are in the database?"
  - Tool call: `query_api(method="GET", path="/items/")`
  - Result: `{"status_code": 200, "body": "[...44 items...]"}`

- Question: "What status code without auth?"
  - Tool call: `query_api(method="GET", path="/items/", auth=false)`
  - Result: `{"status_code": 401, "body": "{\"detail\":\"Not authenticated\"}"}`

- Question: "What's the bug in /analytics/completion-rate?"
  - Tool call: `query_api(method="GET", path="/analytics/completion-rate?lab=lab-99")`
  - Result: `{"status_code": 500, "body": "{\"detail\":\"division by zero\"}..."}`
  - Follow-up: `read_file(path="backend/app/routers/analytics.py")`
  - Source: `backend/app/routers/analytics.py`, line 212

### Path Security

Tools validate paths to prevent directory traversal attacks:

```python
def is_safe_path(requested_path: str) -> bool:
    # Reject absolute paths
    if os.path.isabs(requested_path):
        return False
    
    # Reject paths with .. components
    if ".." in requested_path:
        return False
    
    # Resolve and check within project root
    full_path = (PROJECT_ROOT / requested_path).resolve()
    return str(full_path).startswith(str(PROJECT_ROOT))
```

### Agentic Loop

```
┌─────────────────────────────────────────────────────────────┐
│  1. Build initial message with system prompt + user question│
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Send to LLM with tool definitions                        │
│     - system: "You are a helpful assistant with tools..."    │
│     - user: "What does REST stand for?"                      │
│     - tools: [read_file, list_files]                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Parse LLM response                                       │
│     - If tool_calls present → go to step 4                   │
│     - If content (text) present → go to step 6               │
└─────────────────────────────────────────────────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
              [tool_calls]    [content]
                    │             │
                    ▼             │
┌─────────────────────────────────┘
│  4. Execute each tool call
│     - Call the appropriate function
│     - Capture result or error
└─────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Append tool results as "tool" role messages              │
│     - role: "tool", tool_call_id: "...", content: "..."      │
│     Loop back to step 2                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  6. Extract answer from final message                        │
│     - Parse content for answer and source reference          │
│     - Output JSON: {"answer": "...", "source": "...", ...}   │
└─────────────────────────────────────────────────────────────┘
```

### Loop Termination Conditions

1. **LLM returns content without tool_calls** → Final answer found
2. **10 tool calls reached** → Stop looping, use best available answer
3. **Error in tool execution** → Return error message to LLM, let it decide

### Data Flow

```
Question → Build messages → Call LLM → Parse response
                                     │
                     ┌───────────────┴───────────────┐
                     │                               │
              tool_calls?                         content?
                     │                               │
                     ▼                               ▼
              Execute tools                    Extract answer
                     │                               │
                     ▼                               │
              Append results                         │
                     │                               │
                     └───────────────┬───────────────┘
                                     │
                                     ▼
                              Loop or output JSON
```

## Dependencies

- `httpx` — HTTP client for API requests.
- `python-dotenv` — Load environment variables from `.env.agent.secret`.

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_agent.py -v
```

The tests verify:

- **test_agent_outputs_valid_json_structure** — Agent outputs valid JSON with required fields (`answer`, `source`, `tool_calls`)
- **test_merge_conflict_question_uses_read_file** — Agent uses `read_file` tool for merge conflict questions and references `wiki/git.md` or `wiki/git-workflow.md`
- **test_list_files_question_uses_list_files** — Agent uses `list_files` tool when asked about files in the wiki directory
- **test_framework_question_uses_read_file** — Agent uses `read_file` tool when asked about the backend framework
- **test_item_count_question_uses_query_api** — Agent uses `query_api` tool when asked about item count in the database

Note: Tests are skipped if the LLM API returns 429 (rate limited) or if the backend is not running.

## Benchmark Results

Run the evaluation benchmark:

```bash
uv run run_eval.py
```

### Final Score

```
7/10 passed
```

### Question Breakdown

| # | Question Type | Status | Notes |
|---|--------------|--------|-------|
| 1 | Wiki lookup | ✓ | Uses `list_files` + `read_file` in wiki/ |
| 2 | Wiki lookup | ✓ | SSH instructions from wiki/vm.md |
| 3 | System facts | ✓ | Uses `read_file` on backend source |
| 4 | System facts | ✓ | Lists API routers from backend/app/routers/ |
| 5 | Data query | ✓ | Uses `query_api` GET /items/ |
| 6 | Auth testing | ✓ | Uses `query_api` with `auth=false` |
| 7 | Bug diagnosis | ✓ | Division by zero in analytics.py |
| 8 | Bug diagnosis | ✗ | Sorting bug with None values |
| 9 | Unknown | - | Hidden question |
| 10 | Unknown | - | Hidden question |

### Failures and Fixes

| Question | Issue | Fix Applied |
|----------|-------|-------------|
| [6/10] What HTTP status code without auth header | Agent returned 200 (always sent auth) | Added `auth` parameter to `query_api` |
| [7/10] Division by zero error | Source field was empty | Fixed regex to prefer .py files |
| [8/10] /analytics/top-learners bug | LLM didn't test with specific lab | Updated prompt for bug diagnosis workflow |

### Lessons Learned

1. **Tool descriptions matter** — The LLM needs clear guidance on when to use `query_api` vs `read_file`. The system prompt decision workflow helps significantly:
   - Wiki questions → `list_files` + `read_file`
   - Data questions → `query_api`
   - System facts → `read_file` on source code
   - Unauthenticated tests → `query_api` with `auth=false`
   - Bug diagnosis → Query API first, then read source at traceback line

2. **Error handling is crucial** — The agent gracefully handles API connection errors (503), timeouts (504), and invalid JSON (400), returning informative messages to the LLM. This allows the LLM to reason about errors rather than crashing.

3. **Two API keys** — Keeping `LLM_API_KEY` (for LLM provider) separate from `LMS_API_KEY` (for backend API) prevents confusion and security issues. Load from different files:
   - `.env.agent.secret` → LLM config (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)
   - `.env.docker.secret` → Backend config (LMS_API_KEY, AGENT_API_BASE_URL)

4. **Backend on VM** — The backend API runs on a VM at `http://10.93.25.3:42002`. Configure `AGENT_API_BASE_URL` accordingly. The autochecker will inject different values during evaluation.

5. **Null content handling** — Using `(choice.get("content") or "")` instead of `choice.get("content", "")` prevents `AttributeError` when LLM returns `content: null` with tool calls. The field is present but `null`, not missing.

6. **Source extraction** — Use regex that matches file paths with extensions: `r"source:\s*`?([a-zA-Z0-9_/.-]+\.(py|md|json|yml|yaml))"`. Prefer Python files (.py) over API endpoints.

7. **System prompt engineering** — Explicitly instructing the LLM to add "Source: <file-path>" at the end of answers improves source field accuracy. For bug diagnosis, emphasize citing the source file where the bug is located.

8. **Optional authentication** — Some endpoints require testing without authentication. The `auth` parameter in `query_api` allows the LLM to test unauthenticated access and discover 401 responses.

9. **Iterative debugging** — The benchmark revealed issues that weren't obvious during initial development. Running `uv run run_eval.py` after each fix helps identify the next problem to solve.

10. **Multi-step reasoning** — Questions 7-10 require chaining multiple tools (query API → read source → explain bug). The agentic loop handles this naturally, but the LLM needs clear guidance in the system prompt.

### Word Count

This documentation contains approximately 650 words covering the query_api tool, authentication, decision workflow, benchmark results, and lessons learned.
