#!/usr/bin/env python3
"""
Lab assistant agent — answers questions using an LLM.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {"answer": "...", "tool_calls": []}
"""

import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

# Load LLM configuration from .env.agent.secret
load_dotenv(".env.agent.secret")

LLM_API_BASE = os.getenv("LLM_API_BASE")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL")


def ask_llm(question: str) -> str:
    """Send a question to the LLM and return the answer."""
    if not LLM_API_BASE or not LLM_API_KEY:
        raise RuntimeError(
            "LLM not configured. Check .env.agent.secret and ensure "
            "LLM_API_BASE and LLM_API_KEY are set."
        )

    url = f"{LLM_API_BASE.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL or "qwen3-coder-plus",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": question},
        ],
        "temperature": 0.7,
    }

    max_retries = 3
    retry_delay = 2.0  # seconds

    with httpx.Client() as client:
        for attempt in range(max_retries):
            try:
                response = client.post(url, headers=headers, json=payload, timeout=30.0)

                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        print(
                            f"Rate limited, retrying in {retry_delay}s...",
                            file=sys.stderr,
                        )
                        time.sleep(retry_delay)
                        retry_delay *= 2  # exponential backoff
                        continue
                    else:
                        raise RuntimeError("Max retries exceeded due to rate limiting")

                response.raise_for_status()
                data = response.json()
                break
            except httpx.ReadTimeout as e:
                if attempt < max_retries - 1:
                    print(
                        f"Request timed out, retrying in {retry_delay}s...",
                        file=sys.stderr,
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise RuntimeError("Request timed out after max retries") from e

    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected LLM response: {data}") from e

    return answer


def main():
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    try:
        answer = ask_llm(question)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = {
        "answer": answer,
        "tool_calls": [],
    }

    # Output single JSON line to stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
