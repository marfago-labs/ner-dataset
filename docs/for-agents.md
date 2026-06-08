# Guide for coding agents

**Artifact repo** — committed gold JSONL and published statistics. No generation code lives here; use [ner-gold-generator](https://github.com/marfago-labs/ner-gold-generator) to rebuild files.

**Credentials:** none for reading datasets or running `build_stats_page.py`. Regenerating LLM gold in gold-generator requires `OPENROUTER_API_KEY` — see [gold-generator configuration](https://github.com/marfago-labs/ner-gold-generator/blob/master/docs/configuration.md).

## Contents

| Path | Purpose |
|------|---------|
| `datasets/*.jsonl` | Benchmark gold (see [datasets/README.md](../datasets/README.md)) |
| `docs/stats.json` | Machine-readable integrity + lexical stats |
| `docs/index.html` | GitHub Pages dashboard |
| `generate/*.yaml` | Regen configs (passed to gold-generator) |

## Integrity metrics

After edits, regenerate stats:

```bash
python scripts/build_stats_page.py
```

`docs/stats.json` includes `gold_integrity.span_match_rate` (should be 1.0 on committed gold).

## Regenerate gold

```bash
cd ../ner-gold-generator
uv run build-gold --source synthetic \
  --synthetic-config ../ner-dataset/generate/news_100.yaml \
  --output ../ner-dataset/datasets/synthetic_news_100.jsonl
```

Schema: [gold-schema.md](https://github.com/marfago-labs/ner-gold-generator/blob/master/docs/gold-schema.md).

## Evaluate (downstream)

```bash
cd ../ner-detector
uv run python scripts/agent_smoke.py
```

## Sibling docs

- [ner-gold-generator for-agents.md](https://github.com/marfago-labs/ner-gold-generator/blob/master/docs/for-agents.md)
- [ner-detector for-agents.md](https://github.com/marfago-labs/ner-detector/blob/master/docs/for-agents.md)
- Repo root [llms.txt](../llms.txt)
