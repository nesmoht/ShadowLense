# Design: LLM strategy (extraction paths, local vs Claude API)

Status: **design only, not implemented**. Written 2026-08-26.

## Bronze → Silver: two extraction paths

Today, every source flows through the same path regardless of content
shape: `CrawlerAgent` stores raw content as a string in Bronze
(`pipeline/agents/crawler.py` — one generic `fetch_page` tool, no
per-`source_type` branching), then `EnrichmentAgent` uses a Claude
tool-use loop to extract structured fields from that raw string.

That's the right approach for genuinely unstructured content, but wasteful
and hallucination-prone for sources that already return clean structured
data.

| Path | Sources | Bronze → Silver mechanism |
|---|---|---|
| **Unstructured** | `ahmia` (search-result HTML), `ransomware_dls` (raw ransom-note text via Tor) | LLM extraction (see below) |
| **Structured** | `urlhaus`, `malware_bazaar`, `ransomware_live_api`, `dehashed_search` | Deterministic Python mapper — JSON fields map directly to the Silver schema, no LLM call, no hallucination risk on data that's already ground truth from the source |

## Local LLM for extraction

The unstructured path's extraction step is a candidate to run locally on
the Mac Mini instead of via the Anthropic API.

- **Runtime: Ollama** — Metal-accelerated on Apple Silicon, OpenAI-compatible
  API, supports tool-calling for the model candidates below (relevant since
  `EnrichmentAgent`/`QAAgent` are built around Claude's tool-use pattern, not
  plain prompt-in/text-out). MLX considered as a higher-performance
  alternative, more manual setup — not chosen for iteration 1, simplicity
  wins while everything else is also new.
- **Model candidates**: Qwen2.5 7B/14B (strong structured-output/JSON
  extraction, good instruction-following) or Llama 3.1 8B (solid
  tool-calling support in Ollama). Not pinned yet — pick when actually
  implementing, based on what's available in Ollama's library at the time.
- **Sizing**: the Mac Mini M6 base config now starts at 16GB RAM (not 8GB —
  corrects an earlier estimate in this project's chat history). A 7-8B
  model at Q4 quantization needs ~4-5GB RAM, comfortable alongside Docker +
  macOS on 16GB. A 14B model (~8-9GB at Q4) is safer on the 24GB M5 Pro
  tier if that's the config bought.

## QA stage: local in iteration 1, Claude API in iteration 2

Decision (explicit tradeoff, not a mistake to fix later): **QA scoring
runs locally via Ollama in iteration 1**, even though local models are
weaker at the judgment-heavy call QA makes (is this record real enough to
promote to Gold / trigger an alert). Reasoning: iteration 1's goal is
getting the whole pipeline working end-to-end cheaply while learning the
threat landscape — Claude API cost isn't the blocker, but there's no reason
to pay for API calls before the pipeline is proven. **Iteration 2 moves QA
to the Claude API** once the pipeline is trusted, since QA runs only on
already-filtered Silver records (low volume) and is the decision that
actually gates what reaches Gold/triggers alerts — worth paying for better
judgment once the rest of the system works.

Enrichment (the unstructured extraction step) stays on the local model in
both iterations — it's higher-volume (every crawled raw page, not just
filtered Silver records) and errors there are cheaper to tolerate since QA
is a downstream check regardless of which LLM produced Silver.

## Open items

- Exact model pin (Qwen2.5 vs Llama 3.1, and size) — deferred to
  implementation time
- Whether `EnrichmentAgent`/`QAAgent`'s tool-use loop code needs changes to
  target Ollama's API vs `anthropic.Anthropic`, or whether an
  abstraction/adapter is worth adding given the iteration-2 QA swap is
  already planned
