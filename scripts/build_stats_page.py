#!/usr/bin/env python3
"""Analyze datasets/*.jsonl and write docs/index.html for GitHub Pages."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATASETS_DIR = _REPO_ROOT / "datasets"
_OUT_HTML = _REPO_ROOT / "docs" / "index.html"
_OUT_JSON = _REPO_ROOT / "docs" / "stats.json"


@dataclass
class DatasetStats:
    """Aggregated statistics for one JSONL gold file."""

    file_name: str
    slug: str
    documents: int = 0
    entities: int = 0
    chars_total: int = 0
    text_lengths: list[int] = field(default_factory=list)
    entities_per_doc: list[int] = field(default_factory=list)
    labels: Counter[str] = field(default_factory=Counter)
    sources: Counter[str] = field(default_factory=Counter)
    engines: Counter[str] = field(default_factory=Counter)
    document_types: Counter[str] = field(default_factory=Counter)

    @property
    def avg_text_len(self) -> float:
        return statistics.mean(self.text_lengths) if self.text_lengths else 0.0

    @property
    def avg_entities(self) -> float:
        return statistics.mean(self.entities_per_doc) if self.entities_per_doc else 0.0


def _slug(name: str) -> str:
    return name.removesuffix(".jsonl")


def _load_dataset(path: Path) -> DatasetStats:
    stats = DatasetStats(file_name=path.name, slug=_slug(path.name))
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            stats.documents += 1
            text = row.get("text", "")
            ents = row.get("entities") or []
            stats.chars_total += len(text)
            stats.text_lengths.append(len(text))
            stats.entities_per_doc.append(len(ents))
            stats.entities += len(ents)
            stats.sources[row.get("source", "unknown")] += 1
            for ent in ents:
                stats.labels[ent.get("label", "unknown")] += 1
            meta = row.get("synthetic_meta") or {}
            engine = meta.get("text_engine") or meta.get("engine") or ""
            if engine:
                stats.engines[engine] += 1
            doc_type = meta.get("document_type") or row.get("source", "")
            if doc_type:
                stats.document_types[str(doc_type)] += 1
    return stats


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_float(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}"


def _bar_row(label: str, count: int, total: int, max_pct: float) -> str:
    pct = (100.0 * count / total) if total else 0.0
    width = (pct / max_pct * 100) if max_pct else 0
    return (
        f'<tr><td class="label">{label}</td>'
        f'<td class="num">{_fmt_int(count)}</td>'
        f'<td class="num">{pct:.1f}%</td>'
        f'<td class="bar"><span style="width:{width:.1f}%"></span></td></tr>'
    )


def _render_label_table(labels: Counter[str]) -> str:
    total = sum(labels.values())
    if not total:
        return "<p class=\"muted\">No entities.</p>"
    max_pct = max(100.0 * c / total for c in labels.values())
    rows = [
        _bar_row(label, count, total, max_pct)
        for label, count in labels.most_common()
    ]
    return (
        '<table class="bars"><thead><tr><th>Label</th><th>Count</th>'
        "<th>Share</th><th></th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_dataset_card(ds: DatasetStats) -> str:
    tlen = ds.text_lengths
    epd = ds.entities_per_doc
    engine = ", ".join(f"{k} ({v})" for k, v in ds.engines.most_common()) or "manual"
    doc_types = ", ".join(f"{k} ({v})" for k, v in ds.document_types.most_common()[:6])
    if len(ds.document_types) > 6:
        doc_types += ", …"
    return f"""
    <section class="dataset" id="{ds.slug}">
      <h2>{ds.slug}</h2>
      <p class="file"><code>datasets/{ds.file_name}</code></p>
      <div class="kpis">
        <div class="kpi"><span class="value">{_fmt_int(ds.documents)}</span><span class="name">Documents</span></div>
        <div class="kpi"><span class="value">{_fmt_int(ds.entities)}</span><span class="name">Entities</span></div>
        <div class="kpi"><span class="value">{_fmt_float(ds.avg_entities)}</span><span class="name">Entities / doc (avg)</span></div>
        <div class="kpi"><span class="value">{_fmt_int(min(tlen) if tlen else 0)}–{_fmt_int(max(tlen) if tlen else 0)}</span><span class="name">Chars / doc</span></div>
        <div class="kpi"><span class="value">{_fmt_float(ds.avg_text_len, 0)}</span><span class="name">Avg chars</span></div>
        <div class="kpi"><span class="value">{len(ds.labels)}</span><span class="name">Label types</span></div>
      </div>
      <p class="meta"><strong>Engine:</strong> {engine}</p>
      <p class="meta"><strong>Document types:</strong> {doc_types or "—"}</p>
      <h3>Label distribution</h3>
      {_render_label_table(ds.labels)}
    </section>
    """


def _render_summary_table(all_stats: list[DatasetStats]) -> str:
    rows = []
    total_docs = 0
    total_ents = 0
    for ds in all_stats:
        total_docs += ds.documents
        total_ents += ds.entities
        rows.append(
            f"<tr><td><a href=\"#{ds.slug}\">{ds.slug}</a></td>"
            f"<td class=\"num\">{_fmt_int(ds.documents)}</td>"
            f"<td class=\"num\">{_fmt_int(ds.entities)}</td>"
            f"<td class=\"num\">{_fmt_float(ds.avg_entities)}</td>"
            f"<td class=\"num\">{_fmt_int(min(ds.text_lengths) if ds.text_lengths else 0)}</td>"
            f"<td class=\"num\">{_fmt_int(max(ds.text_lengths) if ds.text_lengths else 0)}</td>"
            f"<td class=\"num\">{_fmt_float(ds.avg_text_len, 0)}</td>"
            f"<td class=\"num\">{len(ds.labels)}</td></tr>"
        )
    rows.append(
        f'<tr class="total"><td><strong>Total</strong></td>'
        f'<td class="num"><strong>{_fmt_int(total_docs)}</strong></td>'
        f'<td class="num"><strong>{_fmt_int(total_ents)}</strong></td>'
        f"<td colspan=\"5\"></td></tr>"
    )
    return (
        '<table class="summary"><thead><tr>'
        "<th>Dataset</th><th>Docs</th><th>Entities</th><th>Ent/doc</th>"
        "<th>Min chars</th><th>Max chars</th><th>Avg chars</th><th>Labels</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _stats_to_json(all_stats: list[DatasetStats]) -> dict:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "datasets": [
            {
                "file": ds.file_name,
                "documents": ds.documents,
                "entities": ds.entities,
                "avg_entities_per_doc": round(ds.avg_entities, 3),
                "text_length": {
                    "min": min(ds.text_lengths) if ds.text_lengths else 0,
                    "max": max(ds.text_lengths) if ds.text_lengths else 0,
                    "avg": round(ds.avg_text_len, 1),
                },
                "labels": dict(ds.labels.most_common()),
                "engines": dict(ds.engines),
                "document_types": dict(ds.document_types),
            }
            for ds in all_stats
        ],
    }


def build_html(all_stats: list[DatasetStats]) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cards = "\n".join(_render_dataset_card(ds) for ds in all_stats)
    nav = "\n".join(
        f'<a href="#{ds.slug}">{ds.slug}</a> ({ds.documents})' for ds in all_stats
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>marfago-labs NER gold datasets — statistics</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a2332;
      --text: #e7ecf3;
      --muted: #8b9cb3;
      --accent: #3d8bfd;
      --border: #2a3544;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 600; margin: 0 0 0.5rem; }}
    .lead {{ color: var(--muted); margin: 0 0 2rem; }}
    .nav {{
      display: flex; flex-wrap: wrap; gap: 0.5rem 1rem;
      margin-bottom: 2rem; font-size: 0.9rem;
    }}
    .nav a {{ color: var(--accent); text-decoration: none; }}
    .nav a:hover {{ text-decoration: underline; }}
    .summary {{ width: 100%; border-collapse: collapse; margin-bottom: 2.5rem; font-size: 0.9rem; }}
    .summary th, .summary td {{ padding: 0.5rem 0.65rem; border-bottom: 1px solid var(--border); text-align: left; }}
    .summary th {{ color: var(--muted); font-weight: 500; }}
    .summary .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .summary tr.total td {{ border-top: 2px solid var(--border); }}
    .dataset {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 1.5rem;
    }}
    .dataset h2 {{ margin: 0 0 0.25rem; font-size: 1.25rem; }}
    .dataset h3 {{ margin: 1.25rem 0 0.5rem; font-size: 1rem; color: var(--muted); }}
    .file code {{ font-size: 0.85rem; color: var(--muted); }}
    .meta {{ font-size: 0.9rem; color: var(--muted); margin: 0.35rem 0; }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
      gap: 0.75rem;
      margin: 1rem 0;
    }}
    .kpi {{
      background: var(--bg);
      border-radius: 8px;
      padding: 0.65rem 0.75rem;
      text-align: center;
    }}
    .kpi .value {{ display: block; font-size: 1.15rem; font-weight: 600; }}
    .kpi .name {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.03em; }}
    table.bars {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
    table.bars th {{ text-align: left; color: var(--muted); font-weight: 500; padding: 0.35rem 0.5rem; }}
    table.bars td {{ padding: 0.35rem 0.5rem; vertical-align: middle; }}
    table.bars .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    table.bars .bar span {{
      display: block; height: 0.55rem; background: var(--accent);
      border-radius: 3px; min-width: 2px;
    }}
    .muted {{ color: var(--muted); }}
    footer {{ margin-top: 2rem; font-size: 0.85rem; color: var(--muted); }}
    footer a {{ color: var(--accent); }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>NER gold datasets</h1>
    <p class="lead">
      Character-offset gold JSONL for <a href="https://github.com/marfago-labs/ner-detector">ner-detector</a>
      benchmarks. Built with
      <a href="https://github.com/marfago-labs/ner-gold-generator">ner-gold-generator</a>.
      Schema: <code>id</code>, <code>text</code>, <code>entities[]</code> with <code>start</code>/<code>end</code>.
    </p>
    <nav class="nav">{nav}</nav>
    <h2 style="font-size:1.1rem;margin-bottom:0.75rem;">Overview</h2>
    {_render_summary_table(all_stats)}
    {cards}
    <footer>
      Generated {generated} by <code>scripts/build_stats_page.py</code>.
      Machine-readable: <a href="stats.json">stats.json</a>.
      Repository: <a href="https://github.com/marfago-labs/ner-dataset">github.com/marfago-labs/ner-dataset</a>.
    </footer>
  </div>
</body>
</html>
"""


def main() -> None:
    paths = sorted(_DATASETS_DIR.glob("*.jsonl"))
    if not paths:
        raise SystemExit(f"No JSONL files in {_DATASETS_DIR}")
    all_stats = [_load_dataset(p) for p in paths]
    _OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    _OUT_HTML.write_text(build_html(all_stats), encoding="utf-8")
    _OUT_JSON.write_text(
        json.dumps(_stats_to_json(all_stats), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {_OUT_HTML}")
    print(f"Wrote {_OUT_JSON}")


if __name__ == "__main__":
    main()
