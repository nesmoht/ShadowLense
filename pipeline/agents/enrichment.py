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
        "description": (
            "Record the threat entities you have extracted from the Bronze content. "
            "You must supply all fields based on your analysis of the raw content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_url": {"type": "string", "description": "Origin URL of the content."},
                "category": {
                    "type": "string",
                    "description": "Threat category: credential_leak, ransomware, c2_infrastructure, exploit, or other.",
                },
                "severity": {
                    "type": "string",
                    "description": "Risk level: critical, high, medium, or low.",
                },
                "affected_domains": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Domain names explicitly mentioned in the content.",
                },
                "ioc_type": {
                    "type": "string",
                    "description": "Indicator type: domain, ip, hash, email, url, or other.",
                },
                "ai_summary": {
                    "type": "string",
                    "description": "1-2 sentence description of the threat.",
                },
                "source_credibility": {
                    "type": "number",
                    "description": "Source trust score 0.0 to 1.0 based on reputation and content quality.",
                },
            },
            "required": [
                "source_url", "category", "severity", "affected_domains",
                "ioc_type", "ai_summary", "source_credibility",
            ],
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
                    "description": (
                        "Assembled Silver record. Must include: bronze_id, source_url, "
                        "category, severity, affected_domains, ioc_type, ai_summary, "
                        "stix_indicator, attack_technique, source_credibility, enriched_at."
                    ),
                },
            },
            "required": ["record"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a threat intelligence enrichment agent. For each Bronze record provided:\n"
    "1. Read the content carefully and extract threat entities.\n"
    "2. Call extract_entities with the source_url and ALL fields you extracted:\n"
    "   - category: one of credential_leak, ransomware, c2_infrastructure, exploit, other\n"
    "   - severity: one of critical, high, medium, low\n"
    "   - affected_domains: list of domain names mentioned in the content\n"
    "   - ioc_type: one of domain, ip, hash, email, url, other\n"
    "   - ai_summary: 1-2 sentence description of the threat\n"
    "   - source_credibility: 0.0 to 1.0 based on source reputation and content quality\n"
    "3. Call map_stix with the entities dict returned by extract_entities.\n"
    "4. Call map_attack_pattern with the category.\n"
    "5. Assemble a complete silver record merging all outputs and call store_silver.\n"
    "   The silver record must include: bronze_id, source_url, category, severity, "
    "affected_domains, ioc_type, ai_summary, stix_indicator (from map_stix), "
    "attack_technique (from map_attack_pattern), source_credibility, enriched_at."
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
            [
                {
                    "id": r.get("id"),
                    "url": r.get("url"),
                    "source_name": r.get("source_name"),
                    "content": r.get("content", "")[:4000],
                }
                for r in bronze_records
            ],
            indent=2,
        )

        messages = [
            {
                "role": "user",
                "content": (
                    "Enrich the following Bronze layer records. For each record:\n"
                    "1. Call extract_entities with your extracted fields and the source URL.\n"
                    "2. Call map_stix with the extracted entities.\n"
                    "3. Call map_attack_pattern with the detected category.\n"
                    "4. Assemble and call store_silver with the complete silver record "
                    "(merge bronze_id and enriched_at from extract_entities, "
                    "stix_indicator from map_stix, attack_technique from map_attack_pattern).\n\n"
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
                logger.debug("Tool %s → %s", block.name, result)

                if isinstance(result, dict) and result.get("stored"):
                    stored_ids.append(result["record_id"])
                    logger.info("EnrichmentAgent stored silver record %s.", result["record_id"])

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
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
            source_url = inputs.get("source_url", "")
            bronze_record = next(
                (r for r in bronze_records if r.get("url") == source_url), {}
            )
            if not bronze_record:
                logger.warning("extract_entities: no bronze record found for URL %s", source_url)

            credibility = float(inputs.get("source_credibility", 0.5))
            credibility = max(0.0, min(1.0, credibility))

            return {
                "bronze_id": bronze_record.get("id", ""),
                "source_url": source_url,
                "category": inputs.get("category", "other"),
                "severity": inputs.get("severity", "medium"),
                "affected_domains": inputs.get("affected_domains", []),
                "ioc_type": inputs.get("ioc_type", "other"),
                "ai_summary": inputs.get("ai_summary", ""),
                "source_credibility": credibility,
                "enriched_at": datetime.now(timezone.utc).isoformat(),
            }

        if name == "map_stix":
            entities = inputs.get("entities", {})
            try:
                stix = create_stix_indicator(entities)
                return {"stix_indicator": stix}
            except Exception as exc:
                logger.warning("map_stix failed: %s", exc)
                return {"stix_indicator": {}, "error": str(exc)}

        if name == "map_attack_pattern":
            category = inputs.get("category", "")
            return {"attack_technique": get_attack_technique(category)}

        if name == "store_silver":
            record = inputs.get("record", {})
            missing = [
                f for f in ("bronze_id", "source_url", "category", "severity",
                            "ioc_type", "ai_summary", "enriched_at")
                if not record.get(f)
            ]
            if missing:
                logger.warning("store_silver: record missing fields %s", missing)
                return {"error": f"missing required fields: {missing}"}
            record_id = self.store.store_silver(record)
            return {"stored": True, "record_id": record_id}

        return {"error": f"Unknown tool: {name}"}
