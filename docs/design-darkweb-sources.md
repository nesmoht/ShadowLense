# Design: dark web source categories

Status: **design only, not implemented**. Written 2026-08-26.

## Why

Current sources (`ahmia`, `urlhaus`, `malware_bazaar` in `pipeline/config.py`)
are all clearnet — none actually crawl `.onion` addresses despite
`pipeline/tools/tor_client.py` existing and `use_tor: True` being supported.
This is the plan for adding real dark-web coverage, deliberately scoped down
from "crawl the dark web" to specific, bounded source categories.

## Categories considered

| Category | Value | Risk/access | Decision |
|---|---|---|---|
| Ransomware group leak/blog sites (DLS) | High — raw ransom notes, deadlines, proof-of-data; maps directly onto existing schema fields | Low — named, known `.onion` addresses, no account/interaction needed, purely public extortion posts | **Iteration 1** |
| Credential/leak exposure (domain monitoring) | High — matches against `alert_domains` | none, if routed through a clearnet aggregator API instead of raw onion crawling | **Iteration 1**, via clearnet API (not onion crawling) |
| Raw onion paste-site crawling (credential dumps) | High — broader coverage than any aggregator | Medium-high — the line between "read metadata" and "downloaded a sample of stolen data to verify it" blurs in practice; site instability | **Iteration 2**, deferred |
| Cybercrime forums (initial-access-brokers, exploit sales) | Highest — earliest possible warning, before an attack happens | High — most reputable forums gate access behind paid membership/vetting designed to screen out researchers; heavy anti-bot (would need a headless browser over Tor, not just `requests`); creating an account is a different category of participation than reading a static page; forums get seized/relaunched constantly | **Rejected** for this project — this is the domain of commercial TI vendors (Recorded Future, Flashpoint, KELA) with legal review and dedicated ops, not a personal-project scrape target. Revisit only via existing sanitized third-party trackers, never by building login-based scraping. |

## Iteration 1

### Ransomware DLS via Tor

- New `source_type: "ransomware_dls"` entries in `pipeline/config.py`,
  `use_tor: True`, pointed at named ransomware groups' own `.onion` sites.
- **No automatic link-following** — only the specific whitelisted URLs are
  fetched, ever. No open-ended crawling into unknown `.onion` territory.
- **Address sourcing: via ransomware.live's own API/group directory**, not a
  manually maintained list. Ransomware.live already tracks which groups'
  DLS addresses are currently live — riding on their maintenance instead of
  independently discovering and re-verifying `.onion` addresses that churn
  constantly. (API is free for personal use, not for commercial use — fine
  for this project; see [[project_shadowlense]].)
- Requires the Tor proxy (`tor_client.py` already expects `127.0.0.1:9050`)
  actually running on the host — ties into the macOS hosting design
  ([[project_shadowlense]] macOS section): `brew install tor` on the Mac
  Mini alongside the container setup.

### Credential exposure via HIBP (no onion crawling)

- New `source_type: "hibp_domain_search"`, clearnet only, no Tor.
- Uses the Have I Been Pwned domain-search API (~$3.50/mo) to check whether
  watched domains (`alert_domains`) appear in known breaches — same
  intelligence value as scraping credential-paste sites, without touching
  the dark web or storing any actual leaked credential data.
- Alternatives considered: DeHashed, Leak-Lookup (both viable, HIBP is the
  most purpose-built for domain monitoring specifically).

## Iteration 2 (deferred)

Raw onion paste-site crawling for credential dumps. Not scoped in detail
yet — when this is picked up, it needs:
- A concrete metadata-only extraction rule enforced in code (never persist
  actual dumped credentials/PII, only site/post/date/referenced-domain)
- Renewed review of which specific paste sites are in scope, since this
  category carries the highest risk of accidentally landing on sites
  distributing genuinely illegal content
