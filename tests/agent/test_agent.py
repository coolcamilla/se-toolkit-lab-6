"""Regression tests for agent.py subprocess execution."""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_outputs_valid_json_structure():
    """Test that agent.py outputs valid JSON with 'answer' and 'tool_calls' fields.

    This test verifies the output structure when the LLM API is available.
    It may be skipped if the API returns 429 (rate limited).
    """
    project_root = Path(__file__).parent.parent.parent
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

    assert "answer" in data, "Missing 'answer' field in JSON output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in JSON output"
    assert isinstance(data["answer"], str), "'answer' must be a string"
    assert isinstance(data["tool_calls"], list), "'tool_calls' must be a list"
    assert len(data["answer"]) > 0, "'answer' should not be empty"
