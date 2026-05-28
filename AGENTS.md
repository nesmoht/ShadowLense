# ShadowLense — Agent Guide

A complete reference for every agent in the project, what it does, and how it fits in.

---

## Pipeline Agents

Run automatically every 6 hours via GitHub Actions. Together they form the threat intelligence pipeline.

```
GitHub Actions (cron)
        │
        ▼
   main.py
        │
        ▼
  Orchestrator  ←  coordinates the sequence (not a true agent — no LLM call)
  │
  ├── 1. Crawler Agent
  ├── 2. Enrichment Agent
  ├── 3. QA Agent
  └── 4. Alert Agent
```

---

### Orchestrator
**File:** `pipeline/agents/orchestrator.py`
**Type:** Pipeline coordinator — not a true agent (no Claude API call)

Runs the four pipeline agents in sequence. Logs record counts at each stage.
If any agent fails, the run stops and GitHub Actions reports the error.

```
crawler.run()     →  bronze_count
enrichment.run()  →  silver_count
qa.run()          →  gold_count
alert.run()
```

---

### Crawler Agent
**File:** `pipeline/agents/crawler.py`
**Type:** True agent — Claude agentic loop with tools

Fetches raw content from configured dark web sources. Uses Tor for .onion sources,
direct HTTP for clearnet sources. Stores raw HTML and API responses in the Bronze layer.

**Tools:**
- `fetch_page(url, use_tor)` — fetches a URL via Tor or direct HTTP
- `store_bronze(url, content, source_name, source_type)` — stores raw content in Bronze Parquet

**Input:** list of sources from `config.py`
**Output:** raw records in `data/bronze/bronze.parquet`

---

### Enrichment Agent
**File:** `pipeline/agents/enrichment.py`
**Type:** True agent — Claude agentic loop with tools

Reads new Bronze records and extracts structured threat intelligence using Claude.
Maps extracted entities to STIX 2.1 objects and MITRE ATT&CK techniques.

**Tools:**
- `extract_entities(record_id, text)` — signals Claude to analyse the text
- `store_silver(record_id, category, severity, affected_domains, attack_pattern, ...)` — stores enriched record

**Input:** unprocessed records from Bronze layer
**Output:** enriched records in `data/silver/silver.parquet`

**STIX mapping:** each record is typed as `indicator`, `malware`, `threat-actor`, or `attack-pattern`
**ATT&CK mapping:** category → technique ID (e.g. `credential_leak` → `T1589`)

---

### QA Agent
**File:** `pipeline/agents/qa.py`
**Type:** True agent — Claude agentic loop with tools

Reviews Silver records and decides which ones are credible enough for the Gold layer.
Acts as a quality gate — rejects vague, low-confidence, or noisy records.

**Tools:**
- `approve_record(record_id, reason)` — promotes record to Gold layer
- `reject_record(record_id, reason)` — marks record as rejected

**Approval criteria:** confidence ≥ 0.7, clear category, at least one affected domain or IOC

**Input:** pending records from Silver layer
**Output:** approved records in `data/gold/gold.parquet`

---

### Alert Agent
**File:** `pipeline/agents/alert.py`
**Type:** True agent — Claude agentic loop with tools

Checks the Gold layer for threats matching monitored domains. Sends email alerts
to subscribers when new matches are found.

**Tools:**
- `search_domain(domain)` — queries Gold layer for domain matches
- `send_alert(to_email, domain, threat_summary)` — sends email via SendGrid

**Input:** subscriber list + Gold layer records
**Output:** email alerts to subscribers

---

## Cost Controls

All pipeline agents use:

- **Model:** `claude-sonnet-4-6` — ~5× cheaper than Opus with comparable quality for structured extraction. Swap by editing `pipeline/config.py`.
- **Prompt caching:** system prompt passed with `cache_control: ephemeral` — charged at 10% of normal input price after the first call in a session.

---

## What Makes Something a True Agent?

A true agent has three things:
1. A **system prompt** defining its role and behaviour
2. A set of **tools** it can call (real Python functions)
3. An **agentic loop** — Claude decides which tools to call, executes them, and loops until the task is done

The Orchestrator has none of these — it is a plain Python coordinator.
The other four are true agents.

---

## Agent Count

| Agent | True agent | How it runs |
|---|---|---|
| Orchestrator | No — coordinator | GitHub Actions cron (every 6h) |
| Crawler | Yes | Via Orchestrator |
| Enrichment | Yes | Via Orchestrator |
| QA | Yes | Via Orchestrator |
| Alert | Yes | Via Orchestrator |
