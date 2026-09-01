# Notes: commercial considerations (speculative, not a roadmap)

Status: **exploratory discussion only, not a plan**. Written 2026-08-26.
Nothing here is scheduled or agreed as work — this captures a conversation
about what it would take to eventually turn Shadowlense into a paid
service, kept for later reference. Do not treat any of this as scoped or
prioritized.

## What "commercial" would mean here

Not a public searchable tool — a **managed monitoring service**. Customers
never query the system or see raw data; the operator controls what's
monitored per customer (their domains), and sends plain-language alert
emails when something's found, for a small subscription. Structurally
close to the existing `AlertAgent` (matches Gold records against
`alert_domains`, sends email) — the gap is **multi-tenancy**: today there's
one global watchlist, commercially each customer needs their own domain
list and their own alert history (so customer A never learns about
customer B's findings).

## What would actually need to change

- **Source licensing**: checked all six sources against commercial use
  specifically (2026-08-26) — most "free" sources have a hidden commercial
  clause, not just ransomware.live:

  | Source | Commercial status |
  |---|---|
  | `ahmia` | No restriction found — public search engine |
  | `urlhaus` | Free "Community API" is fair-use only; abuse.ch/Spamhaus states commercial/for-profit use may require their paid commercial API |
  | `malware_bazaar` | Same abuse.ch org, same caveat — their own FAQ claims "free for commercial and non-commercial usage" while the API policy page separately flags commercial/for-profit use as possibly requiring a paid subscription; contradictory enough to require direct confirmation with abuse.ch before commercial use, not assumption |
  | `ransomware_dls` (Tor) | No third-party data license issue (crawling the group's own site directly), but legal/liability exposure rises with commercial framing regardless |
  | `ransomware_live_api` | **Confirmed blocked** — free for personal use only |
  | `dehashed_search` | Likely fine — already a paid product built for individuals/teams/enterprises, so commercial use is presumably covered by paying the right tier, unlike ransomware.live's blanket personal-only restriction |

  Using data to generate a paid service is commercial use of the source
  regardless of whether customers ever see the raw data directly — the
  restriction is about how the operator monetizes the data, not who has
  read access. This is the hard blocker to resolve first, not a technical
  problem, and it's nearly every source, not just one.
- **Data handling / liability**: today's "personal use only, domain-level
  only" scope (see `design-darkweb-sources.md`) was chosen specifically to
  avoid PII handling responsibility and GDPR data-controller obligations.
  Serving other companies' monitoring reintroduces both.
- **Reliability bar**: a single Mac Mini with no redundancy is fine for
  personal use; a paid service failing silently (the exact failure mode
  that started this whole redesign — see `design-macos-hosting.md` "Why")
  becomes a customer-facing SLA breach, not a private annoyance.

## Differentiation: simplicity, not deeper dark-web coverage

Discussed and rejected as a differentiator: crawling deeper/broader than
established commercial TI vendors (Recorded Future, Flashpoint, KELA) —
that's an arms race against dedicated legal/ops teams a small operator
can't win, and it's also the highest-risk, highest-cost part of the system
to build. Broader dark-web scraping (cybercrime forums etc., see
`design-darkweb-sources.md`'s rejected category) is more "table stakes to
catch up on later" than an actual edge.

**Chosen angle: simplicity.** No dashboard, no login, no raw data/JSON to
interpret — just a plain-language email when something's found. This
isn't new work: the pipeline's existing `ai_summary` field (LLM-generated
in enrichment) is already the technical foundation. Competitors like
DeHashed/HIBP hand back structured API data; a small operator can
differentiate by handing back something a non-technical business owner
can read and act on immediately.

**The tension this creates**: a simplicity-first product lives or dies on
low noise — false alerts erode trust fast when there's no dashboard to
dig into context. This makes the QA stage's quality a *product* decision,
not just a technical one — directly connects to the local-Ollama-in-
iteration-1 vs. Claude-API-in-iteration-2 QA choice in
`design-llm-strategy.md`.

### Example alert email

Illustrates the "no dashboard, plain language" idea concretely. Fictional
company, fictional ransomware group name — purely illustrative, maps to
real Gold-layer fields (`affected_domains`, `source_name`, `ai_summary`,
`attack_technique`, `confidence`).

```
Emne: Jeres domæne er nævnt på en lækageside — nordiskbeslag.dk

Hej Nordisk Beslag ApS,

I dag kl. 14:32 fandt vi jeres domæne nordiskbeslag.dk nævnt på en side
hvor en ransomware-gruppe offentliggør navne på virksomheder, de hævder
at have kompromitteret.

HVAD DET BETYDER
Gruppen bag siden ("DarkVault") bruger typisk denne slags opslag som pres
for at få virksomheder til at betale løsesum — de truer med at
offentliggøre stjålne data hvis der ikke betales inden en frist. Opslaget
angiver ingen frist endnu, og vi kan ikke se om data faktisk er
offentliggjort.

DET HER ER IKKE NØDVENDIGVIS BEKRÆFTELSE PÅ ET BRUD — det er en offentlig
udmelding fra gruppen selv, som vi endnu ikke har kunnet verificere
uafhængigt.

ANBEFALEDE NÆSTE SKRIDT
1. Undersøg om I har haft usædvanlig aktivitet på jeres netværk for
   nylig (uventede login, ukendte enheder, ændrede filer)
2. Kontakt jeres IT-leverandør eller en sikkerhedsrådgiver for at få
   verificeret om der er tegn på indtrængen
3. Overvej at skifte adgangskoder til kritiske systemer som en
   forholdsregel

Vi holder øje med siden og sender en ny mail hvis der sker udvikling —
fx hvis gruppen offentliggør en frist eller faktiske data.

Ingen handling krævet fra jer for at modtage denne overvågning — I
behøver ikke logge ind noget sted. Har I spørgsmål, så svar bare på
denne mail.

Mvh
[Tjenestens navn]

---
Detaljer til jeres IT-ansvarlige, hvis relevant:
Kilde: Ransomware-gruppens egen lækageside (Tor)
Fundet: 2026-08-26 14:32
Kategori: Ransomware / data-udpresning
Tillid til fundet: 87%
```

Mapping to existing schema: opening line = `affected_domains` +
`source_name`; "hvad det betyder" = `ai_summary` + `attack_technique`
rewritten in plain language; the non-confirmation caveat = `confidence`
made legible instead of a raw number; next steps could be generated by
the same LLM from `category`, given the right prompt.
