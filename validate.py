"""Single-source validation run — verifies each pipeline stage produces real output.

Usage:
    python3 validate.py

Uses only the URLhaus source (clearnet, no Tor, returns JSON quickly).
Writes to ./data_validate/ so it never touches production data.
Prints a summary at each stage so you can verify quality before a full run.
"""

import json
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("validate")

# Override data dir so validation never touches production data
os.environ.setdefault("DATA_DIR", "./data_validate")

from pipeline.config import Config
from pipeline.tools.duckdb_store import DuckDBStore
from pipeline.agents.crawler import CrawlerAgent
from pipeline.agents.enrichment import EnrichmentAgent
from pipeline.agents.qa import QAAgent
from pipeline.agents.alert import AlertAgent


def _sep(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main() -> None:
    config = Config()
    # Single source for validation — URLhaus is clearnet JSON, fast and reliable
    validation_sources = [
        s for s in config.sources if s["source_name"] == "urlhaus"
    ]
    if not validation_sources:
        logger.error("urlhaus source not found in config.sources")
        return

    store = DuckDBStore(os.environ["DATA_DIR"])

    # ── Stage 1: Crawl ────────────────────────────────────────────────
    _sep("STAGE 1 — Crawl (1 source)")
    crawler = CrawlerAgent(config, store)
    bronze_ids = crawler.run(validation_sources)
    print(f"\nStored {len(bronze_ids)} bronze record(s).")

    if not bronze_ids:
        print("FAIL: crawler produced no records — check API key and network.")
        return

    bronze_records = store.get_new_bronze_records()
    for r in bronze_records:
        print(f"\n  id          : {r['id'][:16]}…")
        print(f"  url         : {r['url']}")
        print(f"  source_name : {r['source_name']}")
        print(f"  content_len : {len(r.get('content', ''))} chars")
        print(f"  fetched_at  : {r['fetched_at']}")

    # ── Stage 2: Enrich ───────────────────────────────────────────────
    _sep("STAGE 2 — Enrich")
    enricher = EnrichmentAgent(config, store)
    silver_ids = enricher.run(bronze_records)
    print(f"\nStored {len(silver_ids)} silver record(s).")

    if not silver_ids:
        print("FAIL: enrichment produced no records.")
        return

    silver_records = store.get_new_silver_records()
    for r in silver_records:
        domains = r.get("affected_domains", [])
        stix = r.get("stix_indicator", {})
        print(f"\n  id                : {r['id'][:16]}…")
        print(f"  category          : {r['category']}")
        print(f"  severity          : {r['severity']}")
        print(f"  ioc_type          : {r['ioc_type']}")
        print(f"  affected_domains  : {domains}")
        print(f"  source_credibility: {r.get('source_credibility')}")
        print(f"  attack_technique  : {r.get('attack_technique')}")
        print(f"  ai_summary        : {r.get('ai_summary', '')[:120]}")
        print(f"  stix populated    : {'yes' if stix else 'NO — empty'}")

        # Quality checks
        issues = []
        if r["category"] in ("unknown", "other", ""):
            issues.append("category is generic/empty")
        if not domains:
            issues.append("no affected_domains extracted")
        if not r.get("ai_summary"):
            issues.append("ai_summary is empty")
        if not stix:
            issues.append("stix_indicator is empty")
        if issues:
            print(f"  QUALITY WARNINGS  : {', '.join(issues)}")
        else:
            print(f"  QUALITY           : OK")

    # ── Stage 3: QA ───────────────────────────────────────────────────
    _sep("STAGE 3 — QA")
    qa = QAAgent(config, store)
    approved_ids = qa.run(silver_records)
    print(f"\nApproved {len(approved_ids)} record(s) to Gold.")

    if not approved_ids:
        print("No records approved — check QA reasoning in logs above.")
        return

    gold_records = store.get_gold_records_by_silver_ids(approved_ids)
    for r in gold_records:
        print(f"\n  gold id    : {r['id'][:16]}…")
        print(f"  category   : {r['category']}")
        print(f"  severity   : {r['severity']}")
        print(f"  confidence : {r['confidence']}")
        print(f"  domains    : {r.get('affected_domains', [])}")
        print(f"  approved_at: {r['approved_at']}")

    # ── Stage 4: Alert (dry-run if no SendGrid key) ───────────────────
    _sep("STAGE 4 — Alert")
    if not config.sendgrid_api_key:
        print("\nSendGrid key not set — skipping live alert send.")
        print(f"Watched domains : {config.alert_domains or '(none configured)'}")
        print("Set ALERT_DOMAINS and SENDGRID_API_KEY to test email delivery.")
    else:
        alerter = AlertAgent(config, store)
        alerter.run(approved_ids)

    _sep("VALIDATION COMPLETE")
    print(f"\n  Bronze records : {len(bronze_ids)}")
    print(f"  Silver records : {len(silver_ids)}")
    print(f"  Gold records   : {len(approved_ids)}")
    print(f"\nData written to: {os.environ['DATA_DIR']}")
    print("Production data in ./data/ is untouched.\n")


if __name__ == "__main__":
    main()
