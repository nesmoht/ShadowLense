"""Silver layer — enriched, structured threat intelligence records."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SilverRecord:
    id: str
    bronze_id: str
    source_url: str
    category: str
    severity: str
    affected_domains: List[str]
    ioc_type: str
    ai_summary: str
    stix_indicator: dict
    attack_technique: str
    source_credibility: float
    enriched_at: str
