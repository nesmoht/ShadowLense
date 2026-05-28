"""Gold layer — QA-approved, high-confidence threat intelligence records."""

from dataclasses import dataclass
from typing import List


@dataclass
class GoldRecord:
    id: str
    silver_id: str
    category: str
    severity: str
    affected_domains: List[str]
    ioc_type: str
    ai_summary: str
    stix_indicator: dict
    attack_technique: str
    confidence: float
    embedding_cluster: int
    approved_at: str
