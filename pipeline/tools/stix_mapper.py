"""STIX 2.1 mapping helpers for ShadowLense threat records."""

import json
from datetime import datetime, timezone

import stix2

_ATTACK_TECHNIQUE_MAP: dict[str, str] = {
    "credential_leak": "T1589",
    "ransomware": "T1486",
    "c2_infrastructure": "T1071",
    "exploit": "T1203",
}
_DEFAULT_TECHNIQUE = "T1190"


def create_stix_indicator(record: dict) -> dict:
    """Create a STIX 2.1 Indicator object from a threat record dict.

    Expects record to have at least: category, ai_summary, affected_domains,
    ioc_type, attack_technique, source_url.
    Returns the indicator as a plain dict (not a JSON string).
    """
    affected = record.get("affected_domains", [])
    domain_pattern = " OR ".join(
        f"[domain-name:value = '{d}']" for d in affected
    ) if affected else "[domain-name:value = 'unknown']"

    indicator = stix2.Indicator(
        name=f"{record.get('category', 'unknown')} indicator",
        description=record.get("ai_summary", ""),
        pattern=domain_pattern,
        pattern_type="stix",
        valid_from=datetime.now(timezone.utc),
        labels=["malicious-activity"],
        external_references=[
            stix2.ExternalReference(
                source_name="source",
                url=record.get("source_url", ""),
            )
        ] if record.get("source_url") else [],
    )
    return json.loads(indicator.serialize(pretty=False, ensure_ascii=False))


def get_attack_technique(category: str) -> str:
    """Map a threat category string to a MITRE ATT&CK technique ID."""
    return _ATTACK_TECHNIQUE_MAP.get(category.lower(), _DEFAULT_TECHNIQUE)
