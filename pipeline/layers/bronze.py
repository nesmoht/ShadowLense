"""Bronze layer — raw, unprocessed records fetched from sources."""

from dataclasses import dataclass


@dataclass
class BronzeRecord:
    id: str
    url: str
    source_name: str
    source_type: str
    content: str
    fetched_at: str
    content_hash: str
