"""Enrichment agent — extracts structured threat entities from raw Bronze records."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import anthropic

from pipeline.config import Config
from pipeline.tools.duckdb_store import DuckDBStore
from pipeline.tools.stix_mapper import create_stix_indicator, get_attack_technique

logger = logging.getLogger(__name__)

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "extract_entities",
        "description": "Extract structured threat entities from raw dark web content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Raw content to analyse."},
                "source_url": {"type": "string", "description": "Origin URL of the content."},
            },
            "required": ["text", "source_url"],
        },
    },
    {
        "name": "map_stix",
        "description": "Generate a STIX 2.1 Indicator for a set of extracted entities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "object",
                    "description": "Extracted entity dict produced by extract_entities.",
                },
            },
            "required": ["entities"],
        },
    },
    {
        "name": "map_attack_pattern",
        "description": "Map a threat category to a MITRE ATT&CK technique ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Threat category string (e.g. credential_leak).",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "store_silver",
        "description": "Store an enriched record in the Silver layer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "record": {
                    "type": "object",
                    "description": "Silver record dict to persist.",
                },
            },
            "required": ["record"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a threat intelligence enrichment agent. Extract structured threat entities "
    "from raw dark web content. Identify IOC types, affected domains, severity, and "
    "threat category."
)


class EnrichmentAgent:
    def __init__(self, config: Config, store: DuckDBStore) -> None:
        self.config = config
        self.store = store
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def run(self, bronze_records: list[dict[str, Any]]) -> list[str]:
        """Enrich bronze records and store in Silver layer. Returns list of silver record IDs."""
        stored_ids: list[str] = []

        if not bronze_records:
            logger.info("EnrichmentAgent: no bronze records to process.")
            return stored_ids

        records_text = json.dumps(
            [{"id": r.get("id"), "url": r.get("url"), "content": r.get("content", "")[:2000]}
             for r in bronze_records],
            indent=2,
        )

        messages = [
            {
                "role": "user",
                "content": (
                    "Enrich the following Bronze layer records. For each record:\n"
                    "1. Call extract_entities with the content and source URL.\n"
                    "2. Call map_stix with the extracted entities.\n"
                    "3. Call map_attack_pattern with the detected category.\n"
                    "4. Call store_silver with the assembled silver record.\n\n"
                    f"Records:\n{records_text}"
                ),
            }
        ]

        while True:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=8192,
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

                result = self._dispatch_tool(block.name, block.input, bronze_records)
                if isinstance(result, str) and result.startswith("STORED:"):
                    stored_ids.append(result[len("STORED:"):])

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        logger.info("EnrichmentAgent stored %d silver records.", len(stored_ids))
        return stored_ids

    def _dispatch_tool(
        self,
        name: str,
        inputs: dict[str, Any],
        bronze_records: list[dict[str, Any]],
    ) -> Any:
        if name == "extract_entities":
            text = inputs.get("text", "")
            source_url = inputs.get("source_url", "")
            bronze_record = next(
                (r for r in bronze_records if r.get("url") == source_url), {}
            )
            return {
                "bronze_id": bronze_record.get("id", ""),
                "source_url": source_url,
                "category": "unknown",
                "severity": "medium",
                "affected_domains": [],
                "ioc_type": "domain",
                "ai_summary": text[:500],
                "source_credibility": 0.5,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            }

        if name == "map_stix":
            entities = inputs.get("entities", {})
            try:
                stix = create_stix_indicator(entities)
                return {"stix_indicator": stix}
            except Exception as exc:
                return {"stix_indicator": {}, "error": str(exc)}

        if name == "map_attack_pattern":
            category = inputs.get("category", "")
            return {"attack_technique": get_attack_technique(category)}

        if name == "store_silver":
            record = inputs.get("record", {})
            record_id = self.store.store_silver(record)
            return f"STORED:{record_id}"

        return f"Unknown tool: {name}"
