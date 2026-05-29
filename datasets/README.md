# Gold JSONL datasets

| File | Rows | Engine | Description |
|------|------|--------|-------------|
| `arxiv_gold.jsonl` | 10 | manual | Curated ML abstracts ([`build-arxiv-gold`](https://github.com/marfago-labs/ner-gold-generator)) |
| `synthetic_news_100.jsonl` | 100 | procedural | News-article profile |
| `synthetic_blog_100.jsonl` | 100 | procedural | Blog-post profile |
| `synthetic_transcript_100.jsonl` | 100 | procedural | Transcript / dialogue profile |
| `synthetic_scientific_100.jsonl` | 100 | procedural | Scientific-abstract profile (not the same as `arxiv_gold`) |
| `synthetic_mixed_100.jsonl` | 100 | procedural | 40% news / 30% blog / 30% transcript |

Regenerate procedural batches from `ner-gold-generator`:

```bash
cd ../ner-gold-generator
for cfg in news blog transcript scientific mixed; do
  uv run build-gold --source synthetic \
    --synthetic-config "../ner-dataset/generate/${cfg}_100.yaml" \
    --output "../ner-dataset/datasets/synthetic_${cfg}_100.jsonl"
done
```

LLM-quality corpora: use `configs/synthetic_*.yaml` in ner-gold-generator with `engine: llm` and `num_documents: 100` (requires `OPENROUTER_API_KEY`).
