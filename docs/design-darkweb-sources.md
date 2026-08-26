# Design: dark web source categories

Status: **design only, not implemented**. Written 2026-08-26.

## Purpose (clarified 2026-08-26)

Shadowlense's practical goal is a personal, lightweight "am I / are these
domains in a breach" lookup — a light HIBP, not a public service. Scope:
personal use only (no other users), domain-level lookups only (no
individual email/credential storage), primarily a learning vehicle for
understanding the threat landscape rather than a product. This removes most
of HIBP's actual hard problems (no data-exposure risk to other people, no
abuse/rate-limiting surface, no PII handling responsibility) — the Gold
layer's `affected_domains` field plus a simple `duckdb`/`read_parquet` query
already mostly *is* this tool; no new service needs building. Given that,
the priority is data coverage/breadth, which is what the rest of this
document is about.

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

### Ransomware.live structured API (clearnet, alongside the Tor DLS crawl)

- New `source_type: "ransomware_live_api"`, clearnet only, no Tor.
- Ransomware.live's own API already returns structured victim records
  (company, industry, country, group, date) — it's what sources the
  whitelist addresses for the Tor crawl above, but the victim data itself
  is also directly useful and far cheaper to consume: no Tor proxy, no HTML
  parsing, already structured.
- Complements rather than replaces the raw Tor DLS crawl: this gives
  clean, low-effort victim/domain metadata (good match for the domain-lookup
  goal above); the Tor crawl gives the richer raw content (ransom note text,
  proof-of-data, deadlines) that ransomware.live's API doesn't expose.
- Same licensing note as above: free for personal use, not commercial.

### Credential exposure via DeHashed (no onion crawling)

- New `source_type: "dehashed_search"`, clearnet only, no Tor.
- **HIBP considered and dropped**: its domain-search API requires proving
  ownership/control of a domain before you're allowed to search it. Shadowlense
  isn't scoped to only the user's own domains, so that requirement disqualifies
  HIBP outright — not a pricing issue, a hard capability mismatch.
- DeHashed doesn't require domain ownership verification — general breach
  search by domain/email/username, credit-based pricing (~$0.02/query),
  free tier includes 10 monitor tasks. Exact Monitor-product pricing is
  behind a login wall, not yet confirmed.
- Leak-Lookup considered too: free public tier only returns the site name
  (not enough signal), private tier pricing is quote-only and paid via
  Bitcoin/XMR — deprioritized versus DeHashed's transparent credit model.
- Same intelligence value as scraping credential-paste sites, without
  touching the dark web or storing any actual leaked credential data.

## Iteration 2 (deferred)

Raw onion paste-site crawling for credential dumps. Not scoped in detail
yet — when this is picked up, it needs:
- A concrete metadata-only extraction rule enforced in code (never persist
  actual dumped credentials/PII, only site/post/date/referenced-domain)
- Renewed review of which specific paste sites are in scope, since this
  category carries the highest risk of accidentally landing on sites
  distributing genuinely illegal content
