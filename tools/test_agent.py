#!/usr/bin/env python3
"""Tester Agent — validates code written by the developer agent."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import anthropic

PROJECT_ROOT = Path(__file__).parent.parent

SYSTEM_PROMPT = """You are a senior QA engineer working on ShadowLense — a dark web
threat intelligence monitor built as a multi-agent AI system.

Your job is to validate that code is correct and working:
1. Read the relevant files
2. Check for bugs, missing imports, broken logic, incorrect schemas
3. Run import checks and tests to verify behaviour
4. Give a clear PASS or FAIL verdict with specific findings

Focus on correctness. Report every issue you find, and confirm what is working.
End your response with one of:
  VERDICT: PASS
  VERDICT: FAIL — <reason>
"""

TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file in the project",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to project root"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "default": "."}
            }
        }
    },
    {
        "name": "run_command",
        "description": "Run a command to test or validate code",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 60}
            },
            "required": ["command"]
        }
    }
]


class TesterAgent:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def _execute_tool(self, name: str, inputs: dict) -> dict:
        if name == "read_file":
            path = PROJECT_ROOT / inputs["path"]
            try:
                content = path.read_text()
                if len(content) > 8000:
                    content = content[:8000] + f"\n... [truncated — {len(content)} chars total]"
                return {"content": content, "path": inputs["path"]}
            except Exception as e:
                return {"error": str(e)}

        if name == "list_files":
            directory = PROJECT_ROOT / inputs.get("directory", ".")
            try:
                files = []
                for f in sorted(directory.rglob("*")):
                    if f.is_file() and ".git" not in str(f) and "__pycache__" not in str(f):
                        files.append(str(f.relative_to(PROJECT_ROOT)))
                return {"files": files}
            except Exception as e:
                return {"error": str(e)}

        if name == "run_command":
            try:
                result = subprocess.run(
                    inputs["command"],
                    shell=True,
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=inputs.get("timeout", 60)
                )
                return {
                    "stdout": result.stdout[-3000:],
                    "stderr": result.stderr[-1000:],
                    "returncode": result.returncode
                }
            except subprocess.TimeoutExpired:
                return {"error": "Command timed out", "returncode": -1}
            except Exception as e:
                return {"error": str(e), "returncode": -1}

        return {"error": f"Unknown tool: {name}"}

    def run(self, task: str, max_iterations: int = 15) -> str:
        print(f"\n[Tester Agent] Validating: {task}\n")
        messages = [{"role": "user", "content": task}]
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"[Tester Agent] Iteration {iteration}/{max_iterations}...")

            for attempt in range(4):
                try:
                    response = self.client.messages.create(
                        # model="claude-opus-4-7",  # ~$3-8/run
                        model="claude-sonnet-4-6",  # ~$0.50-1.50/run
                        max_tokens=4096,
                        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
                        tools=TOOLS,
                        messages=messages
                    )
                    break
                except anthropic.RateLimitError:
                    wait = 60 * (attempt + 1)
                    print(f"  [rate limit] waiting {wait}s before retry {attempt + 1}/3...")
                    time.sleep(wait)
            else:
                return "VERDICT: FAIL — rate limit retries exhausted"

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                verdict = next((b.text for b in response.content if hasattr(b, "text")), "No verdict.")
                passed = "VERDICT: PASS" in verdict
                print(f"\n[Tester Agent] {'PASS' if passed else 'FAIL'}:\n{verdict}")
                return verdict

            tool_results = []
            for block in tool_uses:
                print(f"  → {block.name}({', '.join(f'{k}={repr(v)[:40]}' for k, v in block.input.items())})")
                result = self._execute_tool(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result)
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            if len(messages) > 22:
                messages = messages[:1] + messages[-20:]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/test_agent.py '<what to validate>'")
        print("Example: python tools/test_agent.py 'validate all pipeline agents import correctly'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    agent = TesterAgent()
    agent.run(task)
