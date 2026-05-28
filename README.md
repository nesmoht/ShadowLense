# ShadowLense

### Dark Web Threat Intelligence Monitor

> *ShadowLense looks through the shadows of the dark web to surface threats targeting your organisation — before attackers act on them.*

---

## Why ShadowLense?

SpyCloud, Recorded Future, DarkOwl, BreachDirectory — they all do dark web monitoring, and with larger teams and bigger budgets.

ShadowLense isn't competing with them. It's a reverse-engineering of how they work — built from scratch, fully open source, for $5/month.

> *"I got curious about how dark web threat intel companies work — so I built one from scratch to find out."*

The LinkedIn post that gets reshared isn't *"I built a competitor to Recorded Future"* — it's *"I reverse-engineered how threat intel works and here's the blueprint."*

| Commercial tools | ShadowLense |
|---|---|
| Black box | Fully open source |
| $50k+/year | $5/month |
| Fixed data model | You control everything |
| No learning value | Every layer is explainable |

**What you actually learn building this:**
- How to ingest adversarial, unstructured data reliably
- How to use an LLM as a transformation step — not a chatbot
- How to deduplicate semantically, not just by hash
- How to model threat intelligence using industry-standard ontologies
- How to serve interactive analytics from a GitHub repo

---

## The Problem

Every day, stolen credentials, ransomware infrastructure details, and zero-day exploits are traded and discussed across dark web forums and paste sites. Most organisations have no visibility into this — they find out they've been compromised when it's already too late.

ShadowLense changes that.

---

## What It Does

Enter your company domain. ShadowLense tells you:

- Has your domain appeared in a credential dump?
- Are your employees' emails being sold?
- Is your infrastructure being discussed in ransomware forums?
- Are CVEs targeting your tech stack being actively exploited?

Subscribe to email alerts and get notified the moment a new mention is detected.

---

## Agent Architecture

ShadowLense is not a traditional pipeline — it is a **multi-agent AI system**. Each agent owns one layer of the pipeline, has a defined set of tools, and operates independently under an orchestrator.

```
Orchestrator Agent
  │
  ├── Crawler Agent
  │     Role:  Fetches raw content from dark web sources via Tor
  │     Tools: fetch_tor_page, store_bronze
  │     Runs:  One instance per source, every 6 hours
  │
  ├── Enrichment Agent
  │     Role:  Extracts threat entities, maps to STIX and MITRE ATT&CK
  │     Tools: extract_entities, map_stix, map_attack_pattern
  │     Runs:  Processes all new Bronze records after each crawl
  │
  ├── QA Agent
  │     Role:  Validates enrichment quality, rejects low-confidence records
  │     Tools: score_confidence, flag_record, reject_record
  │     Runs:  After Enrichment Agent, before Gold layer write
  │
  └── Alert Agent
        Role:  Monitors Gold layer for domain matches, triggers notifications
        Tools: search_domain, send_email
        Runs:  After every Gold layer update
```

Each agent is implemented as a Claude API call with tool use — a narrow job, a specific toolset, and a clear output contract. The Orchestrator coordinates sequencing and handles failures.

**Why agents over a traditional pipeline:**
- Each agent can reason about its input, not just transform it
- The QA Agent catches AI enrichment errors before they reach the dashboard
- Agents can be swapped, upgraded, or prompted differently without touching the pipeline logic
- The architecture scales naturally — add a new agent for a new capability

---

## How It Works

```
Dark Web Sources
(.onion paste sites · breach forums · exploit markets)
              │
              │  Tor Network (anonymised)
              ▼
┌─────────────────────────────┐
│        BRONZE LAYER         │
│   Raw HTML · unstructured   │
│   deduplicated by hash      │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│        SILVER LAYER         │
│   Claude AI enrichment      │
│   Entity extraction:        │
│   · IOC type                │
│   · Affected domains        │
│   · Severity score          │
│   · Threat category         │
│   · Source credibility      │
│   Ontology mapping:         │
│   · STIX objects            │
│   · MITRE ATT&CK techniques │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│         GOLD LAYER          │
│   Vector deduplication      │
│   Semantic threat clustering│
│   Aggregated metrics        │
│   Parquet files + STIX JSON │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│        DASHBOARD            │
│   DuckDB-WASM in browser    │
│   Domain search             │
│   Live threat feed          │
│   Trend charts              │
│   Knowledge graph (D3.js)   │
│   Email alert subscription  │
└─────────────────────────────┘
```

---

## Architecture

ShadowLense runs entirely on GitHub — zero managed infrastructure.

| Component | Technology | Purpose |
|---|---|---|
| Orchestrator Agent | Claude API + Python | Coordinates all agents, handles sequencing and failures |
| Crawler Agent | Claude API + Stem | Fetches raw content from .onion sources via Tor |
| Enrichment Agent | Claude API + STIX2 | Extracts entities, maps to STIX 2.1 and MITRE ATT&CK |
| QA Agent | Claude API | Validates enrichment quality, rejects low-confidence records |
| Alert Agent | Claude API + SendGrid | Monitors for domain matches, sends email notifications |
| Scheduling | GitHub Actions (cron) | Triggers Orchestrator every 6 hours |
| Data Lake | DuckDB + Parquet | Medallion architecture (Bronze/Silver/Gold) |
| Deduplication | Vector embeddings | Semantic clustering of similar threats |
| Storage | GitHub repo | Versioned Parquet files — git is the data history |
| Frontend | Next.js (static export) | Interactive dashboard, domain search, knowledge graph |
| Query Engine | DuckDB-WASM | SQL queries run in the visitor's browser |
| Hosting | GitHub Pages | Zero-cost, always-on |

---

## Ontology — STIX 2.1 + MITRE ATT&CK

ShadowLense models every extracted threat using [STIX 2.1](https://oasis-open.github.io/cti-documentation/stix/intro) — the same standard used by Microsoft Sentinel, Splunk, and CrowdStrike. This makes ShadowLense output directly importable into enterprise SIEM tools.

**STIX object graph:**

```
ThreatActor ──uses──► Malware ──targets──► Identity (your domain)
     │                   │
     └──part-of──► Campaign  └──indicates──► Indicator (IOC)
                                                  │
                                         AttackPattern (MITRE ATT&CK)
```

**MITRE ATT&CK mapping:** Claude maps each extracted threat to a ATT&CK technique during the Silver layer enrichment step. For example:

| Detected Threat | ATT&CK Technique |
|---|---|
| Ransomware encryption discussion | T1486 — Data Encrypted for Impact |
| Credential dump | T1589 — Gather Victim Identity Information |
| C2 infrastructure IOC | T1071 — Application Layer Protocol |
| Exploit kit mention | T1203 — Exploitation for Client Execution |

**Output formats:** Parquet (analytics) + STIX 2.1 JSON bundles (SIEM integration)

---

## Data Model

Every threat record in the Gold layer contains:

```json
{
  "id": "sha256-fingerprint",
  "detected_at": "2026-05-28T14:32:00Z",
  "source": "onion-paste-site-x",
  "source_credibility": 0.82,
  "category": "credential_leak",
  "severity": "critical",
  "affected_domains": ["contoso.com"],
  "affected_emails": 1240,
  "ioc_type": "email:password",
  "stix_type": "indicator",
  "attack_pattern": "T1589",
  "raw_excerpt": "...",
  "ai_summary": "Large credential dump containing corporate emails...",
  "embedding_cluster": 14,
  "confidence": 0.91
}
```

---

## Dashboard Features

- **Domain search** — look up any domain instantly
- **Threat feed** — live, filterable table of detected threats
- **Severity breakdown** — Critical / High / Medium / Low
- **Category distribution** — Credentials · Ransomware · CVEs · General
- **Timeline chart** — threat volume over time
- **Knowledge graph** — D3.js visualisation of threat actor → campaign → IOC → domain relationships
- **MITRE ATT&CK heatmap** — which techniques are most active in current threat landscape
- **Source map** — which dark web sources are most active
- **Email alerts** — subscribe to notifications for your domain

---

## Pipeline Schedule

```
Every 6 hours:
  1. Crawl configured dark web sources via Tor
  2. Hash-deduplicate raw content (Bronze)
  3. Run Claude AI enrichment on new records (Silver)
  4. Generate vector embeddings, cluster threats (Gold)
  5. Write updated Parquet files
  6. Commit to repo — triggers dashboard rebuild
  7. Deploy to GitHub Pages
```

---

## Tech Stack

- **Python** — crawler, pipeline, AI enrichment
- **Stem** — Tor network interface
- **Claude API** — AI entity extraction and classification
- **DuckDB** — local SQL engine for Parquet processing
- **Parquet** — columnar storage, git-versioned
- **Next.js** — static frontend
- **DuckDB-WASM** — in-browser SQL queries
- **Tailwind CSS + shadcn/ui** — UI components
- **STIX2** — threat intelligence ontology (Python library)
- **MITRE ATT&CK** — adversary technique taxonomy
- **D3.js** — knowledge graph visualisation
- **Recharts** — data visualisation
- **GitHub Actions** — pipeline orchestration
- **GitHub Pages** — hosting

---

## Cost

| Item | Cost |
|---|---|
| GitHub (public repo + Actions + Pages) | Free |
| Claude API (~50 enrichment calls/day) | ~$5/month |
| SendGrid (email alerts, free tier) | Free |
| **Total** | **~$5/month** |

---

## Ethical & Legal Scope

ShadowLense aggregates **publicly accessible** data from dark web sources — the same data that commercial threat intelligence platforms sell. It does not:
- Access private or authenticated content
- Store or redistribute full credential dumps
- Target or identify individual users

This is OSINT — open source intelligence gathering for defensive security purposes.

---

*Built for the Data Engineering community — proving that production-grade pipelines don't require enterprise infrastructure.*
