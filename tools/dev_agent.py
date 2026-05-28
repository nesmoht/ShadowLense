#!/usr/bin/env python3
"""Developer Agent — give it a task, it reads the codebase and writes the code."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import anthropic

PROJECT_ROOT = Path(__file__).parent.parent

SYSTEM_PROMPT = """You are a senior software developer working on ShadowLense — a dark web
threat intelligence monitor built as a multi-agent AI system.

Your job is to implement features autonomously:
1. Read relevant existing files to understand the codebase first
2. Write clean, working code
3. Run import checks or tests to verify your work
4. Report exactly what you built when done

Project layout:
  pipeline/agents/   — Crawler, Enrichment, QA, Alert agents (Claude API agentic loops)
  pipeline/tools/    — DuckDB store, Tor client, STIX mapper, email sender
  pipeline/layers/   — Bronze / Silver / Gold dataclass schemas
  pipeline/config.py — Config from env vars
  frontend/          — Next.js dashboard (DuckDB-WASM)
  data/              — Parquet files (bronze/, silver/, gold/)
  tools/             — This dev agent + test agent
"""

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file in the project",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to project root"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file in the project",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to project root"},
                "content": {"type": "string", "description": "Full file content to write"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory relative to project root", "default": "."}
            }
        }
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the project root (for installs, tests, import checks)",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 60}
            },
            "required": ["command"]
        }
    }
]


class DeveloperAgent:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set — add it to your .env file")
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

        if name == "write_file":
            path = PROJECT_ROOT / inputs["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(inputs["content"])
            print(f"  ✎ wrote {inputs['path']}")
            return {"status": "written", "path": inputs["path"]}

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

    def run(self, task: str, max_iterations: int = 25) -> str:
        print(f"\n[Developer Agent] Task: {task}\n")
        messages = [{"role": "user", "content": task}]
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"[Developer Agent] Iteration {iteration}/{max_iterations}...")

            for attempt in range(4):
                try:
                    response = self.client.messages.create(
                        # model="claude-opus-4-7",  # ~$3-8/run
                        model="claude-sonnet-4-6",  # ~$0.50-1.50/run
                        max_tokens=8192,
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
                print("[Developer Agent] Rate limit retries exhausted — stopping.")
                return "STOPPED: rate limit retries exhausted"

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                summary = next((b.text for b in response.content if hasattr(b, "text")), "Done.")
                print(f"\n[Developer Agent] Done:\n{summary}")
                return summary

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

            # Keep only the first message (original task) + last 10 exchanges
            if len(messages) > 22:
                messages = messages[:1] + messages[-20:]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/dev_agent.py '<task description>'")
        print("Example: python tools/dev_agent.py 'add a search_by_severity method to duckdb_store.py'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    agent = DeveloperAgent()
    agent.run(task)
