# Agent Documentation

## Overview

This agent answers questions using a Large Language Model (LLM) via an OpenAI-compatible API.

## LLM Provider

**OpenRouter** is configured as the LLM provider.

- **API Base URL:** `https://openrouter.ai/api/v1`
- **Model:** `meta-llama/llama-3.3-70b-instruct:free`

OpenRouter provides access to multiple LLM providers through a unified API. The free tier is suitable for development and testing.

### Alternative: Local Qwen API

If you have a local Qwen API running (e.g., on a VM), you can switch to it by editing `.env.agent.secret`:

```env
LLM_API_BASE=http://<your-vm-ip>:<qwen-api-port>/v1
LLM_MODEL=qwen3-coder-plus
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.agent.example .env.agent.secret
   ```

2. Edit `.env.agent.secret` and set your API credentials:
   ```env
   LLM_API_KEY=your-api-key-here
   LLM_API_BASE=https://openrouter.ai/api/v1
   LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
   ```

## Usage

Run the agent with a question as the first command-line argument:

```bash
uv run agent.py "What does REST stand for?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

- `answer` — The LLM's response to the question.
- `tool_calls` — Currently empty (no tools implemented yet).

## Architecture

### Components

1. **Environment Loading** — Uses `python-dotenv` to load LLM configuration from `.env.agent.secret`.

2. **LLM Client** — Uses `httpx` to send HTTP POST requests to the LLM API endpoint.

3. **Error Handling**:
   - **Rate Limiting (429)** — Implements exponential backoff with up to 3 retries.
   - **Timeouts** — Retries on read timeouts with exponential backoff.
   - **Configuration Errors** — Clear error messages if `LLM_API_BASE` or `LLM_API_KEY` are missing.

### Data Flow

```
Command-line argument → ask_llm() → HTTP POST to LLM API → Parse response → JSON output
```

## Dependencies

- `httpx` — HTTP client for API requests.
- `python-dotenv` — Load environment variables from `.env.agent.secret`.

## Future Extensions

- **Tools** — Add tool definitions and execution logic (e.g., `read_file`, `query_api`).
- **System Prompt** — Expand the system prompt with domain knowledge and tool instructions.
- **Streaming** — Support streaming responses for long answers.
