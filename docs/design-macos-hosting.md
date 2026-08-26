# Design: macOS hosting on Mac Mini

Status: **design only, not implemented**. Written 2026-08-26, ahead of the Mac
Mini's arrival (~2026-09-22). The Azure Terraform infra under `infra/terraform/`
is parked, not removed — this design supersedes it as the actual hosting plan.

## Why

The pipeline previously ran on a GitHub Actions cron schedule
(`.github/workflows/pipeline.yml`, deleted 2026-08-25). It failed silently on
every 6-hour run from 26 July onward (missing pandas dependency, then
exhausted Anthropic credit) and nobody noticed for a month. The user is buying
a Mac Mini as a general dev machine and wants to host Shadowlense there,
isolated from the host OS.

## Hosting

- **Isolation**: Docker container. Nothing installed directly on macOS beyond
  the container runtime — no system Python, no host-level dependencies.
- **Container engine**: OrbStack or Docker Desktop (either works; OrbStack is
  lighter/more Mac-native).
- **Scheduling**: `launchd`, not cron — it's the native macOS mechanism and
  survives reboots correctly. A `launchd` job runs a wrapper script on a
  `StartCalendarInterval` matching four times a day (00/06/12/18), the same
  cadence the old GitHub Actions workflow used.
- **Image build**: built locally on the Mac Mini (`docker build`). No
  registry, no CI — same machine builds and runs it, so there's nothing to
  push/pull. Rebuild manually after `git pull` when pipeline code changes.

### File layout

```
~/shadowlense-data/              bind-mounted into the container at /app/data
    bronze/ silver/ gold/ ...

~/shadowlense-run/
    .env                         chmod 600 — ANTHROPIC_API_KEY, SENDGRID_API_KEY,
                                  ALERT_FROM_EMAIL, HEALTHCHECKS_URL
    run.sh                       wrapper: docker run + healthchecks ping
    logs/                        one file per run

~/Library/LaunchAgents/
    dk.nesmoht.shadowlense.plist launchd job definition
```

### `run.sh` (wrapper script)

```bash
#!/bin/bash
set -euo pipefail
source ~/shadowlense-run/.env
LOGFILE=~/shadowlense-run/logs/$(date +%Y%m%d-%H%M%S).log

curl -fsS "$HEALTHCHECKS_URL/start" || true

if docker run --rm \
    --env-file ~/shadowlense-run/.env \
    -v ~/shadowlense-data:/app/data \
    shadowlense-pipeline:latest >> "$LOGFILE" 2>&1
then
  curl -fsS "$HEALTHCHECKS_URL" || true          # success
else
  curl -fsS "$HEALTHCHECKS_URL/fail" || true     # failure
fi
```

### launchd job

- `ProgramArguments`: runs `run.sh` via bash
- `StartCalendarInterval`: array of four dicts (hour: 0/6/12/18) — launchd has
  no cron-string syntax
- `RunAtLoad`: false — don't fire just because the Mac logs in or wakes
- Separate `StandardOutPath`/`StandardErrorPath` from the wrapper's own log,
  to catch failures in the wrapper itself (e.g. Docker not running yet)

### Monitoring

healthchecks.io dead-man's-switch, one check, expected period 6h + grace.
Pinged at start, on success, and on failure (three distinct endpoints) — this
is what the GitHub Actions setup never had, and is the direct fix for "nobody
noticed for a month."

## Storage engine change (pipeline code, not just infra)

Current implementation (`pipeline/tools/duckdb_store.py`) stores each layer
(bronze/silver/gold/rejected) as a single Parquet file. Every single-record
write (`_append()`, lines 264-269) reads the *entire* existing file, appends
one row in memory, and rewrites the whole file. This means:

- Every write gets slower as history accumulates — not just a disk-space
  problem, a growing-cost-per-run problem.
- `content` (full raw crawled page text) is stored in bronze forever,
  uncompressed, never pruned.

### Decision: switch to persistent DuckDB tables

Replace the Parquet-file-based storage with a real persistent DuckDB database
(`duckdb.connect("shadowlense.duckdb")`, actual tables, plain `INSERT`
statements) instead of PyArrow read-concat-write. DuckDB handles incremental
inserts natively — no full-file rewrite per row, and the custom
`_ensure_parquet`/`_append` logic goes away entirely (net code reduction).

**Blast radius**: contained to `duckdb_store.py`. All four agents
(`crawler.py`, `enrichment.py`, `qa.py`, `alert.py`), `orchestrator.py`, and
`validate.py` only call `DuckDBStore`'s public methods (`store_bronze`,
`store_silver`, `approve_to_gold`, `reject_silver`,
`get_new_bronze_records`, `get_new_silver_records`,
`get_gold_records_by_silver_ids`, `search_domain`) — none of them touch
Parquet files directly, so the public interface stays the same and none of
those files need to change.

### Frontend compatibility: keep exporting `gold.parquet`

`frontend/lib/db.ts:34` loads `gold.parquet` directly in the browser via
DuckDB-WASM — no backend, static hosting (GitHub Pages, per the deleted
`pages.yml`, was the original intent though never actually enabled). That's
why Parquet was chosen originally. The frontend is out of scope for this
round of work but its architecture assumption is real and worth preserving.

Fix: after each pipeline run, export just the gold table —
`COPY gold TO 'gold.parquet' (FORMAT PARQUET)`. Only gold (the small,
QA-approved subset), not bronze/silver — so the frontend keeps working
without paying the full-history rewrite cost anywhere.

### Content retention: 30 days

Bronze rows keep `id`, `url`, `source_name`, `fetched_at`, `content_hash`
forever; the `content` field (the large raw-text blob) is cleared for rows
older than 30 days. `content_hash` is currently computed and stored but never
actually queried for dedup — clearing `content` doesn't break anything live
today, and preserves the option to dedup on hash later without keeping full
text around indefinitely.

## Open items / not yet decided

- Exact `launchd` label / plist filename convention
- Whether `run.sh` also handles log rotation, or that's a separate periodic
  job
- Whether the storage-engine rewrite happens before or after the Mac Mini
  physically arrives (it's independent of the hosting move and could land
  earlier against the current dev environment)

## Explicitly not in scope here

- Frontend hosting/deployment (unreviewed, GitHub Pages never enabled)
- Tor integration (`use_tor: False`, no proxy sidecar planned)
- Semantic clustering (`embedding_cluster` still unimplemented)
