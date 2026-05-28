"""QA agent — scores Silver layer records and promotes approved ones to Gold."""

import json
import logging
from typing import Any

import anthropic

from pipeline.config import Config
from pipeline.tools.duckdb_store import DuckDBStore

logger = logging.getLogger(__name__)

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_silver_records",
        "description": "Retrieve all Silver layer records that are pending QA review.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "score_record",
        "description": "Assign a confidence score and reasoning to a Silver layer record.",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string"},
                "confidence": {
                    "type": "number",
                    "description": "Confidence score between 0.0 and 1.0.",
                },
                "reasoning": {"type": "string"},
            },
            "required": ["record_id", "confidence", "reasoning"],
        },
    },
    {
        "name": "approve_record",
        "description": "Approve a Silver record and promote it to the Gold layer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string"},
            },
            "required": ["record_id"],
        },
    },
    {
        "name": "reject_record",
        "description": "Reject a Silver record with a reason.",
        "input_schema": {
            "type": "object",
            "properties": {
                "record_id": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["record_id", "reason"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a quality assurance agent for threat intelligence data. Evaluate each Silver "
    "layer record for accuracy, completeness, and confidence. "
    "Approve records with confidence >= 0.7. Reject the rest."
)


class QAAgent:
    def __init__(self, config: Config, store: DuckDBStore) -> None:
        self.config = config
        self.store = store
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._scores: dict[str, float] = {}

    def run(self, silver_records: list[dict[str, Any]]) -> list[str]:
        """Score and approve/reject silver records. Returns list of approved Gold record IDs."""
        approved_ids: list[str] = []

        if not silver_records:
            logger.info("QAAgent: no silver records to review.")
            return approved_ids

        messages = [
            {
                "role": "user",
                "content": (
                    "Please review all pending Silver layer records. "
                    "Start by calling get_silver_records, then score each one, "
                    "and approve or reject based on confidence >= 0.7."
                ),
            }
        ]

        while True:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=4096,
                system=_SYSTEM_PROMPT,
                tools=_TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                logger.warning("Unexpected stop_reason: %s", response.stop_reason)
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                result = self._dispatch_tool(
                    block.name, block.input, silver_records, approved_ids
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        logger.info("QAAgent approved %d records to Gold.", len(approved_ids))
        return approved_ids

    def _dispatch_tool(
        self,
        name: str,
        inputs: dict[str, Any],
        silver_records: list[dict[str, Any]],
        approved_ids: list[str],
    ) -> Any:
        if name == "get_silver_records":
            return self.store.get_new_silver_records()

        if name == "score_record":
            record_id = inputs["record_id"]
            confidence = float(inputs.get("confidence", 0.0))
            self._scores[record_id] = confidence
            return {"record_id": record_id, "confidence": confidence, "scored": True}

        if name == "approve_record":
            record_id = inputs["record_id"]
            self.store.approve_to_gold(record_id)
            approved_ids.append(record_id)
            return {"record_id": record_id, "approved": True}

        if name == "reject_record":
            record_id = inputs["record_id"]
            reason = inputs.get("reason", "")
            logger.info("QAAgent rejected record %s: %s", record_id, reason)
            return {"record_id": record_id, "rejected": True, "reason": reason}

        return f"Unknown tool: {name}"
