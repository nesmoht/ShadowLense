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
                "reason": {"type": "string"},
            },
            "required": ["record_id", "reason"],
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
    "You are a quality assurance agent for threat intelligence data. "
    "Each Silver record has these fields: id, category, severity, affected_domains "
    "(list of domains), ioc_type, ai_summary, stix_indicator, attack_technique, source_credibility.\n\n"
    "For each record:\n"
    "1. Call get_silver_records to retrieve pending records.\n"
    "2. Call score_record with a confidence between 0.0 and 1.0 and your reasoning.\n"
    "   Approve only records that have: clear category, non-empty ai_summary, "
    "confidence >= 0.7, and at least one affected_domain or IOC.\n"
    "3. Call approve_record for records with confidence >= 0.7.\n"
    "4. Call reject_record for records with confidence < 0.7, giving a clear reason."
)


class QAAgent:
    def __init__(self, config: Config, store: DuckDBStore) -> None:
        self.config = config
        self.store = store
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._scores: dict[str, float] = {}

    def run(self, silver_records: list[dict[str, Any]]) -> list[str]:
        """Score and approve/reject silver records. Returns list of approved Silver record IDs."""
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

        max_iterations = self.config.qa_max_iterations
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
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
                        "content": json.dumps(result),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        if iteration >= max_iterations:
            logger.warning("QAAgent hit max iterations limit (%d).", max_iterations)

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
            return silver_records

        if name == "score_record":
            record_id = inputs["record_id"]
            confidence = float(inputs.get("confidence", 0.0))
            confidence = max(0.0, min(1.0, confidence))
            self._scores[record_id] = confidence
            logger.info(
                "QAAgent scored %s: %.2f — %s",
                record_id, confidence, inputs.get("reasoning", ""),
            )
            return {"record_id": record_id, "confidence": confidence, "scored": True}

        if name == "approve_record":
            record_id = inputs["record_id"]
            confidence = self._scores.get(record_id, 0.0)
            threshold = self.config.qa_confidence_threshold
            if confidence < threshold:
                logger.warning(
                    "QAAgent blocked approval of %s: score %.2f < threshold %.2f",
                    record_id, confidence, threshold,
                )
                return {
                    "record_id": record_id,
                    "approved": False,
                    "error": f"score {confidence:.2f} below threshold {threshold:.2f}",
                }
            self.store.approve_to_gold(record_id, confidence)
            approved_ids.append(record_id)
            logger.info("QAAgent approved %s (confidence %.2f).", record_id, confidence)
            return {"record_id": record_id, "approved": True}

        if name == "reject_record":
            record_id = inputs["record_id"]
            reason = inputs.get("reason", "")
            self.store.reject_silver(record_id, reason)
            logger.info("QAAgent rejected %s: %s", record_id, reason)
            return {"record_id": record_id, "rejected": True, "reason": reason}

        return {"error": f"Unknown tool: {name}"}
