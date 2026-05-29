"""DuckDB-backed Parquet store for bronze, silver, and gold layers."""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _ensure_parquet(path: str, schema: pa.Schema) -> None:
    """Create an empty Parquet file with the given schema if it does not exist."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        table = schema.empty_table()
        pq.write_table(table, path)


_BRONZE_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("url", pa.string()),
        pa.field("source_name", pa.string()),
        pa.field("source_type", pa.string()),
        pa.field("content", pa.string()),
        pa.field("fetched_at", pa.string()),
        pa.field("content_hash", pa.string()),
    ]
)

_SILVER_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("bronze_id", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("category", pa.string()),
        pa.field("severity", pa.string()),
        pa.field("affected_domains", pa.string()),  # JSON array
        pa.field("ioc_type", pa.string()),
        pa.field("ai_summary", pa.string()),
        pa.field("stix_indicator", pa.string()),  # JSON object
        pa.field("attack_technique", pa.string()),
        pa.field("source_credibility", pa.float64()),
        pa.field("enriched_at", pa.string()),
    ]
)

_GOLD_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("silver_id", pa.string()),
        pa.field("category", pa.string()),
        pa.field("severity", pa.string()),
        pa.field("affected_domains", pa.string()),  # JSON array
        pa.field("ioc_type", pa.string()),
        pa.field("ai_summary", pa.string()),
        pa.field("stix_indicator", pa.string()),  # JSON object
        pa.field("attack_technique", pa.string()),
        pa.field("confidence", pa.float64()),
        pa.field("embedding_cluster", pa.int64()),
        pa.field("approved_at", pa.string()),
    ]
)

_REJECTED_SCHEMA = pa.schema(
    [
        pa.field("silver_id", pa.string()),
        pa.field("reason", pa.string()),
        pa.field("rejected_at", pa.string()),
    ]
)


class DuckDBStore:
    """Parquet-backed store with a DuckDB query layer."""

    def __init__(self, data_dir: str) -> None:
        self.data_dir = data_dir
        self._bronze_path = os.path.join(data_dir, "bronze", "records.parquet")
        self._silver_path = os.path.join(data_dir, "silver", "records.parquet")
        self._gold_path = os.path.join(data_dir, "gold", "records.parquet")
        self._rejected_path = os.path.join(data_dir, "silver", "rejected.parquet")

        _ensure_parquet(self._bronze_path, _BRONZE_SCHEMA)
        _ensure_parquet(self._silver_path, _SILVER_SCHEMA)
        _ensure_parquet(self._gold_path, _GOLD_SCHEMA)
        _ensure_parquet(self._rejected_path, _REJECTED_SCHEMA)

        self._con = duckdb.connect()

    # ------------------------------------------------------------------
    # Bronze
    # ------------------------------------------------------------------

    def store_bronze(self, record: dict[str, Any]) -> str:
        """Append a bronze record, return its id (sha256 of url+content)."""
        record_id = _sha256(record.get("url", "") + record.get("content", ""))
        row = {
            "id": record_id,
            "url": record.get("url", ""),
            "source_name": record.get("source_name", ""),
            "source_type": record.get("source_type", ""),
            "content": record.get("content", ""),
            "fetched_at": record.get("fetched_at", ""),
            "content_hash": _sha256(record.get("content", "")),
        }
        self._append(_BRONZE_SCHEMA, self._bronze_path, row)
        return record_id

    def get_new_bronze_records(self) -> list[dict[str, Any]]:
        """Return bronze records whose id does not appear in the silver layer."""
        silver_ids = self._con.execute(
            f"SELECT bronze_id FROM read_parquet('{self._silver_path}')"
        ).fetchall()
        silver_set = {r[0] for r in silver_ids}

        rows = self._con.execute(
            f"SELECT * FROM read_parquet('{self._bronze_path}')"
        ).fetchdf()

        result = []
        for _, row in rows.iterrows():
            if row["id"] not in silver_set:
                result.append(row.to_dict())
        return result

    # ------------------------------------------------------------------
    # Silver
    # ------------------------------------------------------------------

    def store_silver(self, record: dict[str, Any]) -> str:
        """Append a silver record, return its id."""
        record_id = _sha256(record.get("bronze_id", "") + record.get("enriched_at", ""))
        stix = record.get("stix_indicator", {})
        row = {
            "id": record_id,
            "bronze_id": record.get("bronze_id", ""),
            "source_url": record.get("source_url", ""),
            "category": record.get("category", ""),
            "severity": record.get("severity", ""),
            "affected_domains": json.dumps(record.get("affected_domains", [])),
            "ioc_type": record.get("ioc_type", ""),
            "ai_summary": record.get("ai_summary", ""),
            # stix_indicator may already be a JSON string (if Claude passed it as-is)
            # or a dict — normalise to string for storage
            "stix_indicator": stix if isinstance(stix, str) else json.dumps(stix),
            "attack_technique": record.get("attack_technique", ""),
            "source_credibility": float(record.get("source_credibility", 0.0)),
            "enriched_at": record.get("enriched_at", ""),
        }
        self._append(_SILVER_SCHEMA, self._silver_path, row)
        return record_id

    def get_new_silver_records(self) -> list[dict[str, Any]]:
        """Return silver records not yet in gold and not rejected."""
        gold_ids = self._con.execute(
            f"SELECT silver_id FROM read_parquet('{self._gold_path}')"
        ).fetchall()
        gold_set = {r[0] for r in gold_ids}

        rejected_ids = self._con.execute(
            f"SELECT silver_id FROM read_parquet('{self._rejected_path}')"
        ).fetchall()
        rejected_set = {r[0] for r in rejected_ids}

        rows = self._con.execute(
            f"SELECT * FROM read_parquet('{self._silver_path}')"
        ).fetchdf()

        result = []
        for _, row in rows.iterrows():
            if row["id"] not in gold_set and row["id"] not in rejected_set:
                d = row.to_dict()
                d["affected_domains"] = json.loads(d.get("affected_domains", "[]"))
                d["stix_indicator"] = json.loads(d.get("stix_indicator", "{}"))
                result.append(d)
        return result

    def reject_silver(self, record_id: str, reason: str) -> None:
        """Mark a silver record as rejected so it is excluded from future QA runs."""
        row = {
            "silver_id": record_id,
            "reason": reason,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
        }
        self._append(_REJECTED_SCHEMA, self._rejected_path, row)

    # ------------------------------------------------------------------
    # Gold
    # ------------------------------------------------------------------

    def approve_to_gold(self, record_id: str, qa_confidence: float) -> None:
        """Copy a silver record to the gold layer using the QA confidence score."""
        rows = self._con.execute(
            f"SELECT * FROM read_parquet('{self._silver_path}') WHERE id = ?",
            [record_id],
        ).fetchdf()

        if rows.empty:
            return

        silver_row = rows.iloc[0].to_dict()
        gold_row = {
            "id": _sha256(record_id + "gold"),
            "silver_id": record_id,
            "category": silver_row.get("category", ""),
            "severity": silver_row.get("severity", ""),
            "affected_domains": silver_row.get("affected_domains", "[]"),
            "ioc_type": silver_row.get("ioc_type", ""),
            "ai_summary": silver_row.get("ai_summary", ""),
            "stix_indicator": silver_row.get("stix_indicator", "{}"),
            "attack_technique": silver_row.get("attack_technique", ""),
            "confidence": float(qa_confidence),
            "embedding_cluster": -1,  # not yet implemented
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
        self._append(_GOLD_SCHEMA, self._gold_path, gold_row)

    def search_domain(self, domain: str) -> list[dict[str, Any]]:
        """Search gold layer records whose affected_domains contains the domain."""
        rows = self._con.execute(
            f"SELECT * FROM read_parquet('{self._gold_path}') "
            "WHERE affected_domains LIKE ?",
            [f"%{domain}%"],
        ).fetchdf()

        result = []
        for _, row in rows.iterrows():
            d = row.to_dict()
            d["affected_domains"] = json.loads(d.get("affected_domains", "[]"))
            d["stix_indicator"] = json.loads(d.get("stix_indicator", "{}"))
            result.append(d)
        return result

    def get_gold_records_by_silver_ids(self, silver_ids: list[str]) -> list[dict[str, Any]]:
        """Return gold records matching the given silver record IDs."""
        if not silver_ids:
            return []
        silver_set = set(silver_ids)
        rows = self._con.execute(
            f"SELECT * FROM read_parquet('{self._gold_path}')"
        ).fetchdf()

        result = []
        for _, row in rows.iterrows():
            if row["silver_id"] in silver_set:
                d = row.to_dict()
                d["affected_domains"] = json.loads(d.get("affected_domains", "[]"))
                d["stix_indicator"] = json.loads(d.get("stix_indicator", "{}"))
                result.append(d)
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append(self, schema: pa.Schema, path: str, row: dict[str, Any]) -> None:
        """Append a single row to a Parquet file."""
        existing = pq.read_table(path)
        new_table = pa.table({col: [row.get(col)] for col in schema.names})
        combined = pa.concat_tables([existing, new_table])
        pq.write_table(combined, path)
