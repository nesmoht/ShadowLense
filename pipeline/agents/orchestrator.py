"""Orchestrator — coordinates the full ShadowLense pipeline sequentially."""

import logging

from pipeline.config import Config
from pipeline.tools.duckdb_store import DuckDBStore
from pipeline.agents.crawler import CrawlerAgent
from pipeline.agents.enrichment import EnrichmentAgent
from pipeline.agents.qa import QAAgent
from pipeline.agents.alert import AlertAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Runs CrawlerAgent → EnrichmentAgent → QAAgent → AlertAgent in sequence."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.store = DuckDBStore(config.data_dir)

    def run(self) -> None:
        logger.info("=== ShadowLense pipeline starting ===")

        # 1. Crawl
        crawler = CrawlerAgent(self.config, self.store)
        bronze_ids = crawler.run(self.config.sources)
        logger.info("Crawl complete — %d bronze records stored.", len(bronze_ids))

        # 2. Enrich
        bronze_records = self.store.get_new_bronze_records()
        logger.info("Enriching %d new bronze records.", len(bronze_records))
        enricher = EnrichmentAgent(self.config, self.store)
        silver_ids = enricher.run(bronze_records)
        logger.info("Enrichment complete — %d silver records stored.", len(silver_ids))

        # 3. QA
        silver_records = self.store.get_new_silver_records()
        logger.info("QA reviewing %d new silver records.", len(silver_records))
        qa = QAAgent(self.config, self.store)
        gold_ids = qa.run(silver_records)
        logger.info("QA complete — %d records approved to Gold.", len(gold_ids))

        # 4. Alert
        logger.info("Running alert checks against %d gold records.", len(gold_ids))
        alerter = AlertAgent(self.config, self.store)
        alerter.run(gold_ids)
        logger.info("=== ShadowLense pipeline complete ===")
