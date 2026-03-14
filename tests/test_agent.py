"""Regression tests for agent.py subprocess execution."""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json_structure():
    """Test that agent.py outputs valid JSON with 'answer', 'source', and 'tool_calls' fields.

    This test verifies the output structure when the LLM API is available.
    It may be skipped if the API returns 429 (rate limited).
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [sys.executable, str(agent_path), "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Skip if rate limited - this is expected with free API tiers
    if result.returncode != 0 and "rate limited" in result.stderr.lower():
        import pytest

        pytest.skip("LLM API rate limited. Test will pass when API is available.")

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Check required fields
    assert "answer" in data, "Missing 'answer' field in JSON output"
    assert "source" in data, "Missing 'source' field in JSON output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in JSON output"

    # Check field types
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert isinstance(data["source"], str), "'source' must be a string"
    assert isinstance(data["tool_calls"], list), "'tool_calls' must be a list"

    # Check answer is not empty
    assert len(data["answer"]) > 0, "'answer' should not be empty"


def test_merge_conflict_question_uses_read_file():
    """Test that agent uses read_file tool when asked about resolving merge conflicts.

    Expected behavior:
    - Agent should call read_file to find information in wiki/git-workflow.md
    - Source field should reference wiki/git-workflow.md
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [sys.executable, str(agent_path), "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Skip if rate limited
    if result.returncode != 0 and "rate limited" in result.stderr.lower():
        import pytest

        pytest.skip("LLM API rate limited. Test will pass when API is available.")

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Check that tool_calls contains read_file
    tool_names = [call.get("tool") for call in data["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Check that source references wiki/git.md or wiki/git-workflow.md
    source = data.get("source", "").lower()
    assert (
        "wiki/git.md" in source
        or "wiki/git-workflow.md" in source
        or "git-workflow" in source
        or "git.md" in source
    ), (
        f"Expected source to reference wiki/git.md or wiki/git-workflow.md, got: {data.get('source')}"
    )


def test_list_files_question_uses_list_files():
    """Test that agent uses list_files tool when asked about files in wiki directory.

    Expected behavior:
    - Agent should call list_files to discover files in wiki/
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [sys.executable, str(agent_path), "What files are in the wiki?"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Skip if rate limited
    if result.returncode != 0 and "rate limited" in result.stderr.lower():
        import pytest

        pytest.skip("LLM API rate limited. Test will pass when API is available.")

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Check that tool_calls contains list_files
    tool_names = [call.get("tool") for call in data["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files to be called"


def test_framework_question_uses_read_file():
    """Test that agent uses read_file tool when asked about the backend framework.

    Expected behavior:
    - Agent should call read_file to find information in backend source code
    - Tool calls should include read_file
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [
            sys.executable,
            str(agent_path),
            "What Python web framework does the backend use?",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Skip if rate limited
    if result.returncode != 0 and "rate limited" in result.stderr.lower():
        import pytest

        pytest.skip("LLM API rate limited. Test will pass when API is available.")

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Check that tool_calls contains read_file
    tool_names = [call.get("tool") for call in data["tool_calls"]]
    assert "read_file" in tool_names, (
        "Expected read_file to be called for framework question"
    )


def test_item_count_question_uses_query_api():
    """Test that agent uses query_api tool when asked about item count in database.

    Expected behavior:
    - Agent should call query_api to get real-time data from the backend
    - Tool calls should include query_api with GET method
    """
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [
            sys.executable,
            str(agent_path),
            "How many items are in the database?",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    # Skip if rate limited
    if result.returncode != 0 and "rate limited" in result.stderr.lower():
        import pytest

        pytest.skip("LLM API rate limited. Test will pass when API is available.")

    # Skip if backend is not running (connection error)
    if result.returncode != 0 and (
        "cannot connect to backend" in result.stderr.lower()
        or "connect error" in result.stderr.lower()
    ):
        pytest.skip("Backend API not running. Test will pass when backend is up.")

    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    output = result.stdout.strip()
    assert output, "Agent produced no output"

    data = json.loads(output)

    # Check that tool_calls contains query_api
    tool_names = [call.get("tool") for call in data["tool_calls"]]
    assert "query_api" in tool_names, (
        "Expected query_api to be called for item count question"
    )

    # Check that query_api was called with GET method and /items/ path
    for call in data["tool_calls"]:
        if call.get("tool") == "query_api":
            args = call.get("args", {})
            assert args.get("method") == "GET", "Expected GET method for query_api"
            assert "/items" in args.get("path", ""), (
                "Expected /items path for query_api"
            )

    # Check that answer contains a number (item count)
    import re

    answer = data.get("answer", "")
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, "Expected answer to contain item count number"
