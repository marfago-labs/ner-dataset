# Gold JSONL datasets

| File | Rows | Engine | Description |
|------|------|--------|-------------|
| `arxiv_gold.jsonl` | 10 | manual | Curated ML abstracts ([`build-arxiv-gold`](https://github.com/marfago-labs/ner-gold-generator)) |
| `synthetic_news_100.jsonl` | 100 | llm | News-article profile (`synthetic_meta.llm_model`: `openai/gpt-oss-120b:free`) |
| `synthetic_blog_100.jsonl` | 100 | llm | Blog-post profile (same LLM engine) |
| `synthetic_transcript_100.jsonl` | 100 | llm | Transcript / dialogue profile (same LLM engine) |
| `synthetic_scientific_100.jsonl` | 100 | llm | Scientific-abstract profile (not the same as `arxiv_gold`) |
| `synthetic_mixed_100.jsonl` | 100 | llm | 40% news / 30% blog / 30% transcript |

Synthetic rows use **entity-first** planning from [ner-gold-generator](https://github.com/marfago-labs/ner-gold-generator) with `engine: llm` in the regen configs under `generate/`. Each row records `synthetic_meta.text_engine` and `synthetic_meta.llm_model` for reproducibility.

Refresh the published stats page after changing JSONL files:

```bash
python scripts/build_stats_page.py
# → docs/index.html and docs/stats.json (includes lexical diversity + gold integrity)
```

Regenerate synthetic batches from `ner-gold-generator` (configs in this repo's `generate/` folder):

```bash
cd ../ner-gold-generator
for cfg in news blog transcript scientific mixed; do
  uv run build-gold --source synthetic \
    --synthetic-config "../ner-dataset/generate/${cfg}_100.yaml" \
    --output "../ner-dataset/datasets/synthetic_${cfg}_100.jsonl"
done
```

Requires `uv sync --extra llm` and `OPENROUTER_API_KEY` in `.env` when configs use `engine: llm`. For offline procedural gold, use `configs/synthetic_smoke.yaml` or set `engine: procedural` in a custom config.
