# Poor Richard's Engineering Almanack

A RAG application that answers software-engineering questions in Benjamin Franklin's voice,
grounded exclusively in genuine sayings from *Poor Richard's Almanack*.

**Live:** https://almanack.kamradtfamily.net

---

## Architecture

```
Browser
  │  POST /ask  { question }
  ▼
FastAPI (Python 3.12)
  │
  ├─► Ollama nomic-embed-text ──► embed question (768-dim vector)
  │
  ├─► PostgreSQL + pgvector ──► HNSW cosine search ──► top-5 sayings
  │         (almanack schema)         (similarity ≥ 0.35)
  │
  ├─► Anthropic Claude (or Ollama Llama) ──► answer in Franklin's voice
  │         (prompt: quote only retrieved sayings, verbatim)
  │
  └─► Quote Verification ──► regex-extract all "quoted strings"
              │                    from answer
              │               check each is a substring of a retrieved saying
              │               if fail → regenerate once (stricter prompt)
              │               if still fail → return top sayings plainly
              ▼
        { answer, sayings: [{text, year, source, similarity}] }
```

---

## Why quote verification exists

Franklin's sayings are specific, memorable, and historically attributed. The LLM
is prompted to quote them verbatim, but LLMs can hallucinate — producing a plausible-
sounding "Franklin quote" that he never wrote.

After generation, the app regex-extracts every double-quoted string from the answer
and checks that each is a **verbatim substring** of one of the five retrieved records.
If any quoted string fails this test, the call is attempted once more with a stricter
prompt. If it fails again, the answer is discarded and the raw top sayings are returned
instead.

This is the core anti-hallucination guardrail. It cannot prevent *all* misattribution
(an LLM could paraphrase without quoting), but it ensures that anything presented as
a direct quote is genuine. It is also the most interesting piece for interviews: it
shows that output validation, not just input framing, is necessary for faithful RAG.

---

## How retrieval works

1. The corpus (Franklin's *Way to Wealth*, Gutenberg #43855) is parsed at ingestion
   time into ~60 individual sayings.
2. Each saying is lightly spelling-modernised (thee→you, hath→has, etc.) and stored
   as the `modern` field. The original text is stored in `text`, untouched.
3. **Embeddings are computed on `modern`** — modern language matches better against
   modern questions in the embedding space.
4. At query time the question is embedded and compared against all stored vectors using
   **cosine similarity** via PostgreSQL's `pgvector` HNSW index.
5. Results below a minimum similarity threshold (default 0.35) are discarded, and the
   LLM is told in character to admit it has no applicable proverb.

---

## Stack

| Layer | Technology |
|-------|-----------|
| API   | Python 3.12, FastAPI, uvicorn |
| DB    | PostgreSQL 16 + pgvector (HNSW cosine index) |
| Embeddings | Ollama `nomic-embed-text` (768-dim, in-cluster) |
| Generation | Anthropic Claude (configurable; `LLM_PROVIDER=ollama` switches to Llama) |
| Rate limiting | slowapi (5 req/min per IP) + in-memory daily spend cap |
| Frontend | Vanilla HTML/CSS/JS, colonial almanac aesthetic |
| Deploy | K3s via ArgoCD + Cloudflare Tunnel |

---

## Corpus

From Project Gutenberg:

| File | Gutenberg # | URL |
|------|-------------|-----|
| `corpus/raw/way-to-wealth-43855.txt` | 43855 | https://www.gutenberg.org/ebooks/43855 |

See [SOURCES.md](SOURCES.md) for full attribution.

Run the ingestion report:
```bash
python -m corpus.parse corpus/raw/way-to-wealth-43855.txt 2>&1 | tail -1
```

---

## One-time bootstrap

After first deploy:

```bash
# 1. Create DB and user in the cluster PostgreSQL
kubectl exec -n postgresql deploy/postgresql -- psql -U postgres -c "
  CREATE DATABASE almanack;
  CREATE USER almanack_user WITH PASSWORD 'your-password';
  GRANT ALL PRIVILEGES ON DATABASE almanack TO almanack_user;
"
kubectl exec -n postgresql deploy/postgresql -- psql -U postgres -d almanack -c "
  GRANT ALL ON SCHEMA public TO almanack_user;
"

# 2. Create the Kubernetes secret
kubectl create secret generic almanack-secret -n almanack \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-... \
  --from-literal=DB_URL=postgresql://almanack_user:your-password@postgresql.postgresql.svc.cluster.local:5432/almanack

# 3. Run corpus ingestion (once the pod is running)
kubectl exec -n almanack deploy/almanack -- python -m corpus.ingest
```

---

## Local development

```bash
# Start Postgres + pgvector locally (or port-forward)
export DB_URL="postgresql://almanack_user:pass@localhost:5432/almanack"
export OLLAMA_URL="http://localhost:11434"   # kubectl port-forward -n llm svc/ollama 11434:11434
export ANTHROPIC_API_KEY="sk-ant-..."

pip install -e ".[dev]"
python -m corpus.ingest          # populate DB once
uvicorn app.main:app --reload    # http://localhost:8000
```

Run tests (no DB or LLM required — all unit tests are pure Python):
```bash
pytest -v
```

---

## Deployment

Follows the standard platform pipeline:

```
git push → GitHub Actions (python-image.yml) → ghcr.io/rkamradt/almanack:sha-<7hex>
         → rkamradt-helm-charts/almanack/version-values.yaml
         → ArgoCD auto-sync
         → K3s namespace: almanack
         → Cloudflare Tunnel: almanack.kamradtfamily.net
```
