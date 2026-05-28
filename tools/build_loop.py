#!/usr/bin/env python3
"""Build Loop — automated dev/test feedback cycle.

Developer Agent writes code → Tester Agent validates → if FAIL, feedback
goes back to Developer Agent → repeats until PASS or max iterations.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.dev_agent import DeveloperAgent
from tools.test_agent import TesterAgent

MAX_ITERATIONS = 3


def run(task: str) -> bool:
    dev = DeveloperAgent()
    tester = TesterAgent()

    print(f"\n{'='*60}")
    print(f"Build Loop — Task: {task}")
    print(f"{'='*60}\n")

    dev_task = task
    tester_feedback = None

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Iteration {iteration}/{MAX_ITERATIONS} ---\n")

        if tester_feedback:
            dev_task = f"""Original task: {task}

The tester agent reviewed your previous implementation and found issues:

{tester_feedback}

Fix the issues above. Re-read the relevant files first, then apply the fixes."""

        dev_output = dev.run(dev_task)

        test_task = f"""Validate the implementation of this task: {task}

The developer agent just made changes. Check:
1. All relevant files exist and have correct content
2. Imports work correctly — run: python -c "import pipeline"
3. Logic matches the task requirements
4. No obvious bugs or missing edge cases

Run import checks and any relevant commands to verify."""

        test_result = tester.run(test_task)

        if "VERDICT: PASS" in test_result:
            print(f"\n{'='*60}")
            print(f"Build Loop PASSED on iteration {iteration}")
            print(f"{'='*60}\n")
            return True

        tester_feedback = test_result
        print(f"\n[Build Loop] Iteration {iteration} failed — sending feedback to Developer Agent\n")

    print(f"\n{'='*60}")
    print(f"Build Loop FAILED after {MAX_ITERATIONS} iterations")
    print(f"Last tester feedback:\n{tester_feedback}")
    print(f"{'='*60}\n")
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/build_loop.py '<task>'")
        print("Example: python tools/build_loop.py 'add a get_threats_by_severity method to duckdb_store.py'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    success = run(task)
    sys.exit(0 if success else 1)
