"""Alert agent — checks Gold layer for watched domains and sends email alerts."""

import json
import logging
from typing import Any

import anthropic

from pipeline.config import Config
from pipeline.tools.duckdb_store import DuckDBStore
from pipeline.tools.email_sender import send_alert as _send_alert

logger = logging.getLogger(__name__)

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_gold_for_domain",
        "description": "Search the Gold layer for threat records mentioning a specific domain.",
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The domain name to search for.",
                },
            },
            "required": ["domain"],
        },
    },
    {
        "name": "send_alert",
        "description": "Send an email alert for a domain with matching threat records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to_email": {"type": "string"},
                "domain": {"type": "string"},
                "threat_summary": {
                    "type": "string",
                    "description": "Human-readable summary of the threats detected.",
                },
            },
            "required": ["to_email", "domain", "threat_summary"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a threat alert agent. Check if any monitored domains appear in the Gold layer "
    "threat intelligence. Send email alerts for matches."
)


class AlertAgent:
    def __init__(self, config: Config, store: DuckDBStore) -> None:
        self.config = config
        self.store = store
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def run(self, gold_record_ids: list[str]) -> None:
        """Check watched domains against newly approved Gold records and dispatch alerts."""
        if not gold_record_ids:
            logger.info("AlertAgent: no new gold records to check.")
            return

        watched_domains = self.config.alert_domains
        if not watched_domains:
            logger.info("AlertAgent: no watched domains configured, skipping.")
            return

        if not self.config.sendgrid_api_key:
            logger.warning("AlertAgent: SENDGRID_API_KEY not set, skipping alerts.")
            return

        # Scope to domains that appear in the newly approved Gold records only
        new_gold_records = self.store.get_gold_records_by_silver_ids(gold_record_ids)
        if not new_gold_records:
            logger.info("AlertAgent: no gold records found for the approved IDs.")
            return

        new_domains: set[str] = set()
        for record in new_gold_records:
            for d in record.get("affected_domains", []):
                new_domains.add(d.lower())

        relevant_domains = [d for d in watched_domains if d.lower() in new_domains]
        if not relevant_domains:
            logger.info("AlertAgent: no watched domains appear in newly approved records.")
            return

        domains_text = ", ".join(relevant_domains)
        logger.info("AlertAgent: checking domains: %s", domains_text)

        messages = [
            {
                "role": "user",
                "content": (
                    f"The following watched domains appear in newly approved threat records: "
                    f"{domains_text}\n\n"
                    f"For each domain, call search_gold_for_domain to get full threat context, "
                    f"then call send_alert with the recipient "
                    f"{self.config.alert_to_email}, the domain, and a threat summary."
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

                logger.debug("AlertAgent calling tool: %s %s", block.name, block.input)
                result = self._dispatch_tool(block.name, block.input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

    def _dispatch_tool(self, name: str, inputs: dict[str, Any]) -> Any:
        if name == "search_gold_for_domain":
            domain = inputs["domain"]
            results = self.store.search_domain(domain)
            logger.info("AlertAgent: search_gold_for_domain(%s) → %d records", domain, len(results))
            return results

        if name == "send_alert":
            to_email = inputs["to_email"]
            domain = inputs["domain"]
            threats = self.store.search_domain(domain)
            if not threats:
                logger.warning("AlertAgent: no threats found for domain %s at send time.", domain)
                return {"sent": False, "domain": domain, "reason": "no_threats_found"}
            success = _send_alert(
                api_key=self.config.sendgrid_api_key,
                from_email=self.config.alert_from_email,
                to_email=to_email,
                domain=domain,
                threats=threats,
            )
            if success:
                logger.info("AlertAgent: sent alert for domain %s to %s.", domain, to_email)
            else:
                logger.warning("AlertAgent: failed to send alert for domain %s.", domain)
            return {"sent": success, "domain": domain, "to": to_email}

        return {"error": f"Unknown tool: {name}"}
