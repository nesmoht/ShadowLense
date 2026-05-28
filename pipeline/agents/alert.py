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
        """Check watched domains against Gold layer and dispatch alerts."""
        watched_domains = self.config.alert_domains
        if not watched_domains:
            logger.info("AlertAgent: no watched domains configured, skipping.")
            return

        domains_text = ", ".join(watched_domains)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Check the Gold layer for threats involving these monitored domains: "
                    f"{domains_text}\n\n"
                    f"For each domain, call search_gold_for_domain. "
                    f"If matches are found, call send_alert with the recipient "
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

                result = self._dispatch_tool(block.name, block.input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result) if not isinstance(result, str) else result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

    def _dispatch_tool(self, name: str, inputs: dict[str, Any]) -> Any:
        if name == "search_gold_for_domain":
            domain = inputs["domain"]
            return self.store.search_domain(domain)

        if name == "send_alert":
            to_email = inputs["to_email"]
            domain = inputs["domain"]
            threat_summary = inputs.get("threat_summary", "")
            threats = self.store.search_domain(domain)
            success = _send_alert(
                api_key=self.config.sendgrid_api_key,
                from_email=self.config.alert_from_email,
                to_email=to_email,
                domain=domain,
                threats=threats if threats else [{"ai_summary": threat_summary}],
            )
            if success:
                logger.info("AlertAgent: sent alert for domain %s to %s.", domain, to_email)
            else:
                logger.warning("AlertAgent: failed to send alert for domain %s.", domain)
            return {"sent": success, "domain": domain, "to": to_email}

        return f"Unknown tool: {name}"
