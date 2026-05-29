# ner-dataset

Gold **NER benchmark datasets** (JSONL with character-offset spans) produced by [ner-gold-generator](https://github.com/marfago-labs/ner-gold-generator) and consumed by [ner-detector](https://github.com/marfago-labs/ner-detector).

## Layout

```
ner-dataset/
  datasets/
    arxiv_gold.jsonl       # built-in arXiv benchmark (manual spans)
    synthetic_mixed.jsonl  # example synthetic batch output
    …
```

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
- **ner-detector** resolves `load_dataset("arxiv_gold")` from `datasets/` here first, then falls back to `ner-detector/benchmark/datasets/` for shipped copies.

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

## License

[MIT](LICENSE)
