"""Crawler agent — fetches raw content from configured sources via Claude agentic loop."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

import anthropic

from pipeline.config import Config
from pipeline.tools.duckdb_store import DuckDBStore
from pipeline.tools.tor_client import fetch as tor_fetch

logger = logging.getLogger(__name__)

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "fetch_page",
        "description": "Fetch the content of a URL, optionally routing through Tor.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch."},
                "use_tor": {
                    "type": "boolean",
                    "description": "Whether to route the request through Tor.",
                    "default": False,
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "store_bronze",
        "description": "Store a successfully fetched page in the Bronze layer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "content": {"type": "string"},
                "source_type": {"type": "string"},
                "source_name": {"type": "string"},
            },
            "required": ["url", "content", "source_type", "source_name"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a web crawler agent. For each source provided, fetch the page content "
    "and store it in the Bronze layer. "
    "If fetch_page returns an error or status_code other than 200, skip that source "
    "and move to the next one — do not store failed fetches."
)


class CrawlerAgent:
    def __init__(self, config: Config, store: DuckDBStore) -> None:
        self.config = config
        self.store = store
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def run(self, sources: list[dict[str, Any]]) -> list[str]:
        """Run the crawler agentic loop for each source. Returns list of stored record IDs."""
        stored_ids: list[str] = []

        sources_text = json.dumps(sources, indent=2)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Please crawl the following sources and store each in the Bronze layer:\n"
                    f"{sources_text}\n\n"
                    "For each source, call fetch_page with the url and use_tor flag. "
                    "If the fetch succeeds (status_code 200), call store_bronze with the result. "
                    "Skip any source that returns an error or non-200 status."
                ),
            }
        ]

        try:
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

                    result = self._dispatch_tool(block.name, block.input, sources)
                    if isinstance(result, dict) and result.get("stored"):
                        stored_ids.append(result["record_id"])
                        logger.info("CrawlerAgent stored bronze record %s.", result["record_id"])

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

        except anthropic.APIError as exc:
            logger.error("CrawlerAgent API error: %s", exc)

        logger.info("CrawlerAgent stored %d bronze records.", len(stored_ids))
        return stored_ids

    def _dispatch_tool(
        self, name: str, inputs: dict[str, Any], sources: list[dict[str, Any]]
    ) -> Any:
        if name == "fetch_page":
            url = inputs["url"]
            use_tor = inputs.get("use_tor", False)
            source = next((s for s in sources if s["url"] == url), {})
            use_tor = source.get("use_tor", use_tor)
            result = tor_fetch(
                url,
                use_tor=use_tor,
                proxy_host=self.config.tor_proxy_host,
                proxy_port=self.config.tor_proxy_port,
            )
            if result.get("status_code") != 200:
                logger.warning(
                    "Fetch failed for %s: status %s", url, result.get("status_code")
                )
                return {"error": result.get("content", "fetch failed"), "status_code": result.get("status_code")}
            return result

        if name == "store_bronze":
            url = inputs.get("url", "")
            content = inputs.get("content", "")
            source_type = inputs.get("source_type", "")
            source_name = inputs.get("source_name", "")

            if not url or not content:
                return {"error": "url and content are required"}

            # Fill source_name/type from config if Claude left them blank
            source = next((s for s in sources if s["url"] == url), {})
            record = {
                "url": url,
                "content": content,
                "source_type": source_type or source.get("source_type", ""),
                "source_name": source_name or source.get("source_name", ""),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            record_id = self.store.store_bronze(record)
            return {"stored": True, "record_id": record_id}

        return {"error": f"Unknown tool: {name}"}
