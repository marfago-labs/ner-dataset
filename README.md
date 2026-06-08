# ner-dataset

Gold **NER benchmark datasets** (JSONL with character-offset spans) produced by [ner-gold-generator](https://github.com/marfago-labs/ner-gold-generator) and consumed by [ner-detector](https://github.com/marfago-labs/ner-detector).

**Live statistics:** [marfago-labs.github.io/ner-dataset](https://marfago-labs.github.io/ner-dataset/) (GitHub Pages, auto-deployed from `docs/` on push).

## Layout

```
ner-dataset/
  datasets/           # gold JSONL (see datasets/README.md)
  generate/           # regen YAML configs (100 rows each; engine: llm)
```

**Included:** `arxiv_gold.jsonl` (10 curated papers) plus five **100-row LLM-generated** synthetic corpora (`synthetic_news_100`, `synthetic_blog_100`, `synthetic_transcript_100`, `synthetic_scientific_100`, `synthetic_mixed_100`).

## Reproduce / cite

- **Release:** Git tag [`v1.0.0`](https://github.com/marfago-labs/ner-dataset/releases/tag/v1.0.0) — canonical benchmark snapshot (arxiv + five LLM synthetics).
- **Regenerate:** [ner-gold-generator](https://github.com/marfago-labs/ner-gold-generator) with configs in `generate/` (see [datasets/README.md](datasets/README.md)).
- **Evaluate:** [ner-detector](https://github.com/marfago-labs/ner-detector) `load_dataset("<name>")` or `benchmark/run_benchmark.py`.

## Monorepo defaults

When this folder sits next to the other marfago-labs repos:

```
marfago-labs/
  ner-gold-generator/   # builds gold JSONL
  ner-dataset/          # ← this repo (datasets/)
  ner-detector/         # loads datasets for benchmarks
  text-compressor/      # raw arXiv / YouTube inputs
```

- **ner-gold-generator** writes here by default (`build-arxiv-gold`, `--output` examples).
- **ner-detector** resolves `load_dataset("arxiv_gold")` from `datasets/` here first, then falls back to `NER_DATASET_DIR` or sibling paths.

**Secret scanning:** Gitleaks in CI and pre-commit (`.gitleaks.toml`). No API keys belong in this repo.

Override the directory with `NER_DATASET_DIR` in either project's `.env`.

## Generate gold

From `ner-gold-generator`:

```bash
uv run build-arxiv-gold
# → ../ner-dataset/datasets/arxiv_gold.jsonl

uv run build-gold --source synthetic \
  --synthetic-config configs/synthetic_mixed.yaml \
  --output ../ner-dataset/datasets/synthetic_mixed.jsonl
```

Schema: see [ner-gold-generator docs/gold-schema.md](https://github.com/marfago-labs/ner-gold-generator/blob/master/docs/gold-schema.md).

**Coding agents:** [docs/for-agents.md](docs/for-agents.md) · [llms.txt](llms.txt)

## License

[MIT](LICENSE)
