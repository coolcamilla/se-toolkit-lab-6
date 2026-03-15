# Plan: Task 3 — The System Agent

## Overview

Add a `query_api` tool to the agent so it can query the deployed backend API and answer data-dependent questions. 

## Tool Schema: `query_api`

### Parameters

- `method` (string, required): HTTP method — GET, POST, PUT, DELETE, etc.
- `path` (string, required): API endpoint path, e.g., `/items/`, `/analytics/completion-rate`
- `body` (string,  optional): JSON request body for POST/PUT requests

### Description for LLM

The tool description should tell the LLM when to use it:

> "Query the backend API to get real-time data or perform actions. Use this for questions about database contents, statistics, or system state. Do NOT use for static documentation questions — use read_file or list_files for those."

### Return Format

JSON string with:

- `status_code`: HTTP status code (e.g., 200, 404, 500)
- `body`: Response body as string (JSON or error message)

## Authentication

### Environment Variables

Load from `.env.docker.secret`:

- `LMS_API_KEY` — Backend API key for authorization

### Authorization Header

Send requests with:

```
Authorization: Bearer <LMS_API_KEY>
```

## Configuration

### Environment Variables (from `.env.agent.secret` and `.env.docker.secret`)

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_API_KEY` | LLM provider API key | — |
| `LLM_API_BASE` | LLM API endpoint URL | — |
| `LLM_MODEL` | Model name | `qwen3-coder-plus` |
| `LMS_API_KEY` | Backend API key for query_api | — |
| `AGENT_API_BASE_URL` | Base URL for query_api | `http://localhost:42002` |

> **Important**: All config must come from environment variables. The autochecker injects its own values.

## System Prompt Update

Current prompt focuses on wiki tools. Update to include decision logic:

```
You are a helpful assistant that answers questions using the project repository and backend API.

You have access to these tools:
- list_files(path): List files/directories at a given path
- read_file(path): Read contents of a file
- query_api(method, path, body): Query the backend API for real-time data

Decision workflow:
1. For static documentation questions (e.g., "What is REST?", "How to protect a branch?") → use list_files and read_file in wiki/
2. For data-dependent questions (e.g., "How many items?", "What's the completion rate?") → use query_api
3. For system facts (e.g., "What framework?", "What port?") → use read_file on source code (backend/main.py, docker-compose.yml)

Rules:
- Always provide the source file path where you found the answer (for wiki/code questions)
- For API queries, include the endpoint path in your answer
- If you can't find the answer after exploring, say so honestly
- Don't make up information not present in the files or API responses
- When you find the answer, respond with the answer and source, do not make additional tool calls
```

## Implementation Steps

1. **Load environment variables**:
   - Add `LMS_API_KEY = os.getenv("LMS_API_KEY")`
   - Add `AGENT_API_BASE_URL = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")`

2. **Define tool schema**:
   - Add `query_api` to `TOOL_DEFINITIONS` list

3. **Implement `query_api` function**:
   - Use `httpx.Client()` to send requests
   - Add Authorization header with Bearer token
   - Return JSON string with status_code and body

4. **Update `TOOLS` dictionary**:
   - Add `"query_api": query_api`

5. **Update system prompt**:
   - Include decision workflow for wiki vs API vs code

6. **Test manually**:
   - `uv run agent.py "How many items are in the database?"`
   - `uv run agent.py "What framework does the backend use?"`

7. **Run benchmark**:
   - `uv run run_eval.py`
   - Iterate on failures

## Benchmark Results

### Final Score

```
7/10 passed
```

### First Failures

| Question | Expected | Got | Likely Cause |
|----------|----------|-----|--------------|
| [6/10] What HTTP status code without auth header | 401 | 200 | query_api always sent Authorization header |
| [7/10] Division by zero error | Source field | Empty source | Regex didn't extract source correctly |
| [8/10] /analytics/top-learners bug | Find sorting bug | Incomplete answer | Need more investigation |

### Iteration Strategy

1. **Add `auth` parameter to query_api** — Allow LLM to test unauthenticated access
2. **Fix source extraction regex** — Match file paths like `backend/app/routers/analytics.py`
3. **Update system prompt** — Tell LLM to always add "Source: <file>" at end of answer
4. **Re-run benchmark** — Iterate until all pass

## Lessons Learned

### Implementation

1. **Tool descriptions matter** — The LLM needs clear guidance on when to use `query_api` vs `read_file`. Added a decision workflow to the system prompt:
   - Wiki questions → `list_files` + `read_file`
   - Data questions → `query_api`
   - System facts → `read_file` on source code
   - Unauthenticated tests → `query_api` with `auth=false`

2. **Error handling is crucial** — Implemented comprehensive error handling in `query_api`:
   - 503 for connection errors
   - 504 for timeouts
   - 400 for invalid JSON
   - Clear error messages returned to LLM

3. **Two API keys** — Keep `LLM_API_KEY` (for LLM provider) separate from `LMS_API_KEY` (for backend API). Load from different files:
   - `.env.agent.secret` → LLM config
   - `.env.docker.secret` → Backend config

4. **Null content handling** — Use `(choice.get("content") or "")` instead of `choice.get("content", "")` to handle `content: null` from LLM.

5. **Environment variables** — All config must come from environment variables with sensible defaults:
   - `AGENT_API_BASE_URL` defaults to `http://10.93.25.3:42002` (VM address)

6. **Source extraction** — Use regex that matches file paths: `r"source:\s*`?([a-zA-Z0-9_/.-]+\.[a-z]+)"`

7. **System prompt engineering** — Explicitly tell LLM to add "Source: <file-path>" at the end of answers

### Testing

- All 5 regression tests pass
- 7/10 benchmark questions pass
- Remaining questions require more complex multi-step reasoning
