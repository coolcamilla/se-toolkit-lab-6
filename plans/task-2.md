# Task 2: Agentic Loop Implementation Plan

## Overview

Implement an agentic loop that allows the LLM to use tools (`read_file`, `list_files`) to find answers in the project repository.

## Architecture

### 1. Tool Schema Definition

Tools will be defined as Python functions with metadata for the LLM function-calling schema.

#### Tool Schema Structure

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
                        "description": "Relative path from project root (e.g., 'wiki/rest-api.md')"
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
                        "description": "Relative directory path from project root (e.g., 'wiki/')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]
```

### 2. Tool Implementation

#### `read_file(path: str) -> str`

```
1. Resolve the path relative to project root
2. Security check:
   - Ensure resolved path is within project directory
   - Reject paths containing ".." or absolute paths
3. Read file contents
4. Return contents or error message
```

#### `list_files(path: str) -> str`

```
1. Resolve the path relative to project root
2. Security check:
   - Ensure resolved path is within project directory
   - Reject paths containing ".." or absolute paths
3. List directory entries (files and subdirectories)
4. Return newline-separated list or error message
```

### 3. Path Security

**Threat:** Path traversal attacks (e.g., `../../.env.agent.secret`)

**Mitigation:**

```python
def is_safe_path(project_root: Path, requested_path: str) -> bool:
    """Check if the requested path is within the project directory."""
    # Reject absolute paths
    if os.path.isabs(requested_path):
        return False
    
    # Resolve the full path
    full_path = (project_root / requested_path).resolve()
    
    # Ensure it's within project root
    return str(full_path).startswith(str(project_root.resolve()))
```

### 4. Agentic Loop

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
│     - Output JSON: {"answer": "...", "tool_calls": [...]}    │
└─────────────────────────────────────────────────────────────┘
```

### 5. Loop Termination Conditions

1. **LLM returns content without tool_calls** → Final answer found
2. **10 tool calls reached** → Stop looping, use best available answer
3. **Error in tool execution** → Return error message to LLM, let it decide

### 6. System Prompt

```
You are a helpful assistant that answers questions using the project repository.

You have access to these tools:
- list_files(path): List files/directories at a given path
- read_file(path): Read contents of a file

Workflow:
1. Use list_files to discover files in the wiki/ directory
2. Use read_file to read relevant files and find the answer
3. Include the source reference (file path + section anchor) in your answer

Rules:
- Always provide the source file path where you found the answer
- If you can't find the answer after exploring, say so honestly
- Don't make up information not present in the files
```

### 7. Message Format

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
    # After tool calls:
    # {"role": "assistant", "tool_calls": [...]},
    # {"role": "tool", "tool_call_id": "...", "content": "..."},
]
```

### 8. Output Format

```json
{
  "answer": "Representational State Transfer.",
  "source": "wiki/rest-api.md#what-is-rest",
  "tool_calls": [
    {"name": "list_files", "arguments": {"path": "wiki"}},
    {"name": "read_file", "arguments": {"path": "wiki/rest-api.md"}}
  ]
}
```

## Implementation Steps

1. **Define tool schemas** — Create `TOOL_DEFINITIONS` for LLM API
2. **Implement `read_file`** — With path security checks
3. **Implement `list_files`** — With path security checks
4. **Build agentic loop** — Main loop in `main()`
5. **Update system prompt** — Include tool usage instructions
6. **Update output format** — Include `source` field in JSON
7. **Add tests** — Test tool execution and loop behavior

## Testing Strategy

1. **Unit tests for tools:**
   - `read_file` with valid path → returns content
   - `read_file` with `../` path → returns error
   - `list_files` with valid path → returns listing
   - `list_files` with `../` path → returns error

2. **Integration tests:**
   - Single tool call → correct output
   - Multiple tool calls → loop completes
   - 10 tool calls → loop terminates

3. **E2E tests:**
   - Ask question about wiki content → correct answer with source
