# ShadowLense — Agent Guide

A complete reference for every agent in the project, what it does, and how it fits in.

---

## Two Types of Agents

ShadowLense uses agents for two completely different purposes:

| Type | Where | Who runs it | Purpose |
|---|---|---|---|
| **Pipeline agents** | `pipeline/agents/` | GitHub Actions (automated, every 6h) | Collect, process and deliver threat intelligence |
| **Developer agents** | `tools/` | GitHub Actions (on demand, via Build Loop) | Build and validate the codebase autonomously |

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

## Developer Agents

Triggered on demand via GitHub Actions. The Developer and Tester agents never run
standalone — they always run together through the Build Loop, which manages the
feedback cycle between them automatically.

---

### Build Loop
**File:** `tools/build_loop.py`
**Type:** Coordinator — not a true agent (no Claude API call)
**Triggered by:** `.github/workflows/dev_loop.yml`

Orchestrates the automated dev/test feedback cycle. You provide a task via the
GitHub Actions UI — the Build Loop handles everything else without any manual steps.

```
You type a task in GitHub Actions UI
          ↓
    Build Loop starts (up to 3 iterations)
          ↓
  Developer Agent writes or fixes code
          ↓
  Tester Agent validates
          ↓
    PASS? → commit changes and done
    FAIL? → tester feedback sent back to Developer Agent
          ↓
  Developer Agent reads feedback and fixes
          ↓
  Tester Agent validates again
          ↓
  (repeats until PASS or 3 iterations)
```

**How to trigger:**
1. Go to GitHub repo → **Actions** tab
2. Select **ShadowLense Dev Loop**
3. Click **Run workflow**
4. Enter your task (e.g. `add search_by_severity to duckdb_store.py`)
5. Click **Run** — the loop runs, commits any changes back to the repo

---

### Developer Agent
**File:** `tools/dev_agent.py`
**Type:** True agent — Claude agentic loop with tools

Reads the codebase and implements features autonomously. Called by the Build Loop —
receives either the original task or the original task plus tester feedback when fixing.

**Tools:**
- `read_file(path)` — reads an existing file
- `write_file(path, content)` — creates or overwrites a file
- `list_files(directory)` — explores the project structure
- `run_command(command)` — runs shell commands for installs and checks

---

### Tester Agent
**File:** `tools/test_agent.py`
**Type:** True agent — Claude agentic loop with tools

Validates code written by the Developer Agent. Called by the Build Loop after every
Developer Agent run. If validation fails, its full output is sent back to the Developer
Agent as feedback for the next iteration.

**Tools:**
- `read_file(path)` — reads files to review
- `list_files(directory)` — explores the project
- `run_command(command)` — runs import checks and tests

**Output:** always ends with `VERDICT: PASS` or `VERDICT: FAIL — <reason>`

---

## What Makes Something a True Agent?

A true agent has three things:
1. A **system prompt** defining its role and behaviour
2. A set of **tools** it can call (real Python functions)
3. An **agentic loop** — Claude decides which tools to call, executes them, and loops until the task is done

The Orchestrator has none of these — it is a plain Python coordinator.
The other six are true agents.

---

## Agent Count

| Agent | True agent | How it runs |
|---|---|---|
| Orchestrator | No — coordinator | GitHub Actions cron (every 6h) |
| Crawler | Yes | Via Orchestrator |
| Enrichment | Yes | Via Orchestrator |
| QA | Yes | Via Orchestrator |
| Alert | Yes | Via Orchestrator |
| Build Loop | No — coordinator | GitHub Actions on demand |
| Developer | Yes | Via Build Loop |
| Tester | Yes | Via Build Loop, feeds back to Developer |
