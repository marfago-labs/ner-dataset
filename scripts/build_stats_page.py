#!/usr/bin/env python3
"""Analyze datasets/*.jsonl and write docs/index.html for GitHub Pages."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATASETS_DIR = _REPO_ROOT / "datasets"
_OUT_HTML = _REPO_ROOT / "docs" / "index.html"
_OUT_JSON = _REPO_ROOT / "docs" / "stats.json"

_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def tokenize_words(text: str) -> list[str]:
    """Lowercase word tokens (matches ner-gold-generator lexical_diversity)."""
    return [t.lower() for t in _WORD_RE.findall(text)]


def distinct_n(tokens: list[str], n: int) -> float:
    """Unique n-grams / total n-grams (0.0 when undefined)."""
    if n < 1 or len(tokens) < n:
        return 0.0
    if n == 1:
        return len(set(tokens)) / len(tokens)
    grams = [tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
    return len(set(grams)) / len(grams)


@dataclass(frozen=True, slots=True)
class LexicalQuality:
    """Distinct-1/2 lexical diversity (report-only, same as build-gold stderr stats)."""

    per_doc_distinct_1: tuple[float, ...]
    per_doc_distinct_2: tuple[float, ...]
    corpus_distinct_1: float
    corpus_distinct_2: float
    corpus_token_count: int

    @property
    def distinct_1_mean(self) -> float:
        if not self.per_doc_distinct_1:
            return 0.0
        return sum(self.per_doc_distinct_1) / len(self.per_doc_distinct_1)

    @property
    def distinct_2_mean(self) -> float:
        if not self.per_doc_distinct_2:
            return 0.0
        return sum(self.per_doc_distinct_2) / len(self.per_doc_distinct_2)


@dataclass(frozen=True, slots=True)
class GoldIntegrity:
    """Span anchoring checks on committed gold rows."""

    entities_checked: int
    span_match_ok: int
    unique_span_ok: int
    planned_surfaces: int
    used_exactly_once: int

    @property
    def span_match_rate(self) -> float:
        if not self.entities_checked:
            return 1.0
        return self.span_match_ok / self.entities_checked

    @property
    def unique_span_rate(self) -> float:
        if not self.entities_checked:
            return 1.0
        return self.unique_span_ok / self.entities_checked

    @property
    def exactly_once_rate(self) -> float | None:
        if not self.planned_surfaces:
            return None
        return self.used_exactly_once / self.planned_surfaces


def compute_lexical_quality(rows: list[dict[str, Any]]) -> LexicalQuality | None:
    per_doc_d1: list[float] = []
    per_doc_d2: list[float] = []
    corpus_tokens: list[str] = []
    for row in rows:
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        tokens = tokenize_words(text)
        if not tokens:
            continue
        per_doc_d1.append(distinct_n(tokens, 1))
        per_doc_d2.append(distinct_n(tokens, 2))
        corpus_tokens.extend(tokens)
    if not per_doc_d1:
        return None
    return LexicalQuality(
        per_doc_distinct_1=tuple(per_doc_d1),
        per_doc_distinct_2=tuple(per_doc_d2),
        corpus_distinct_1=distinct_n(corpus_tokens, 1),
        corpus_distinct_2=distinct_n(corpus_tokens, 2),
        corpus_token_count=len(corpus_tokens),
    )


def _surface_count(text: str, surface: str) -> int:
    if not surface:
        return 0
    count = 0
    start = 0
    while True:
        idx = text.find(surface, start)
        if idx < 0:
            return count
        count += 1
        start = idx + 1


def compute_gold_integrity(rows: list[dict[str, Any]]) -> GoldIntegrity:
    span_match_ok = 0
    unique_span_ok = 0
    entities_checked = 0
    planned_surfaces = 0
    used_exactly_once = 0
    for row in rows:
        text = row.get("text", "")
        if not isinstance(text, str):
            continue
        meta = row.get("synthetic_meta") or {}
        usage = meta.get("entity_usage") if isinstance(meta, dict) else None
        if isinstance(usage, dict):
            planned_surfaces += int(usage.get("planned") or 0)
            used_exactly_once += int(usage.get("used_exactly_once") or 0)
        for ent in row.get("entities") or []:
            if not isinstance(ent, dict):
                continue
            entities_checked += 1
            surface = ent.get("text", "")
            start = ent.get("start")
            end = ent.get("end")
            if isinstance(start, int) and isinstance(end, int) and text[start:end] == surface:
                span_match_ok += 1
            if _surface_count(text, str(surface)) == 1:
                unique_span_ok += 1
    return GoldIntegrity(
        entities_checked=entities_checked,
        span_match_ok=span_match_ok,
        unique_span_ok=unique_span_ok,
        planned_surfaces=planned_surfaces,
        used_exactly_once=used_exactly_once,
    )


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
    lexical: LexicalQuality | None = None
    integrity: GoldIntegrity | None = None

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
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            rows.append(row)
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
    stats.lexical = compute_lexical_quality(rows)
    stats.integrity = compute_gold_integrity(rows)
    return stats


def _fmt_int(n: int) -> str:
    return f"{n:,}"


def _fmt_float(x: float, digits: int = 1) -> str:
    return f"{x:,.{digits}f}"


def _fmt_pct(rate: float) -> str:
    return f"{100.0 * rate:.1f}%"


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
        return '<p class="muted">No entities.</p>'
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


def _render_quality_block(ds: DatasetStats) -> str:
    parts: list[str] = ['<h3>NLP quality metrics</h3>', '<table class="quality">']
    parts.append(
        "<thead><tr><th>Metric</th><th>Value</th><th>Notes</th></tr></thead><tbody>"
    )
    if ds.lexical:
        lx = ds.lexical
        d1 = lx.per_doc_distinct_1
        d2 = lx.per_doc_distinct_2
        parts.append(
            f"<tr><td>Distinct-1 (per doc, mean)</td>"
            f'<td class="num">{lx.distinct_1_mean:.3f}</td>'
            f"<td>min {min(d1):.3f}, max {max(d1):.3f}</td></tr>"
        )
        parts.append(
            f"<tr><td>Distinct-2 (per doc, mean)</td>"
            f'<td class="num">{lx.distinct_2_mean:.3f}</td>'
            f"<td>min {min(d2):.3f}, max {max(d2):.3f}</td></tr>"
        )
        parts.append(
            f"<tr><td>Distinct-1 (corpus)</td>"
            f'<td class="num">{lx.corpus_distinct_1:.3f}</td>'
            f"<td>{_fmt_int(lx.corpus_token_count)} tokens</td></tr>"
        )
        parts.append(
            f"<tr><td>Distinct-2 (corpus)</td>"
            f'<td class="num">{lx.corpus_distinct_2:.3f}</td>'
            f"<td>unique bigrams / all bigrams</td></tr>"
        )
    if ds.integrity:
        gi = ds.integrity
        parts.append(
            f"<tr><td>Span match rate</td>"
            f'<td class="num">{_fmt_pct(gi.span_match_rate)}</td>'
            f"<td>text[start:end] == entity.text</td></tr>"
        )
        parts.append(
            f"<tr><td>Unique surface rate</td>"
            f'<td class="num">{_fmt_pct(gi.unique_span_rate)}</td>'
            f"<td>each gold surface appears once in text</td></tr>"
        )
        once = gi.exactly_once_rate
        if once is not None:
            parts.append(
                f"<tr><td>Planned surface exactly-once</td>"
                f'<td class="num">{_fmt_pct(once)}</td>'
                f"<td>{gi.used_exactly_once}/{gi.planned_surfaces} from synthetic_meta</td></tr>"
            )
        else:
            parts.append(
                "<tr><td>Planned surface exactly-once</td>"
                '<td class="num">—</td>'
                "<td>manual / non-synthetic rows</td></tr>"
            )
    parts.append("</tbody></table>")
    parts.append(
        '<p class="muted quality-note">Lexical diversity matches '
        "<code>ner-gold-generator</code> build statistics (report-only, not a gate). "
        "Higher distinct-1/2 usually means less repetitive wording.</p>"
    )
    return "\n".join(parts)


def _render_dataset_card(ds: DatasetStats) -> str:
    tlen = ds.text_lengths
    engine = ", ".join(f"{k} ({v})" for k, v in ds.engines.most_common()) or "manual"
    doc_types = ", ".join(f"{k} ({v})" for k, v in ds.document_types.most_common()[:6])
    if len(ds.document_types) > 6:
        doc_types += ", …"
    d1_mean = ds.lexical.distinct_1_mean if ds.lexical else 0.0
    d2_mean = ds.lexical.distinct_2_mean if ds.lexical else 0.0
    return f"""
    <section class="dataset" id="{ds.slug}">
      <h2>{ds.slug}</h2>
      <p class="file"><code>datasets/{ds.file_name}</code></p>
      <div class="kpis">
        <div class="kpi"><span class="value">{_fmt_int(ds.documents)}</span><span class="name">Documents</span></div>
        <div class="kpi"><span class="value">{_fmt_int(ds.entities)}</span><span class="name">Entities</span></div>
        <div class="kpi"><span class="value">{_fmt_float(ds.avg_entities)}</span><span class="name">Entities / doc</span></div>
        <div class="kpi"><span class="value">{d1_mean:.3f}</span><span class="name">Distinct-1 (mean)</span></div>
        <div class="kpi"><span class="value">{d2_mean:.3f}</span><span class="name">Distinct-2 (mean)</span></div>
        <div class="kpi"><span class="value">{_fmt_pct(ds.integrity.span_match_rate if ds.integrity else 1.0)}</span><span class="name">Span match</span></div>
      </div>
      <p class="meta"><strong>Engine:</strong> {engine}</p>
      <p class="meta"><strong>Document types:</strong> {doc_types or "—"}</p>
      {_render_quality_block(ds)}
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
        d1 = ds.lexical.distinct_1_mean if ds.lexical else 0.0
        d2 = ds.lexical.distinct_2_mean if ds.lexical else 0.0
        rows.append(
            f"<tr><td><a href=\"#{ds.slug}\">{ds.slug}</a></td>"
            f"<td class=\"num\">{_fmt_int(ds.documents)}</td>"
            f"<td class=\"num\">{_fmt_int(ds.entities)}</td>"
            f"<td class=\"num\">{_fmt_float(ds.avg_entities)}</td>"
            f"<td class=\"num\">{d1:.3f}</td>"
            f"<td class=\"num\">{d2:.3f}</td>"
            f"<td class=\"num\">{_fmt_pct(ds.integrity.span_match_rate if ds.integrity else 1.0)}</td>"
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
        "<th>Distinct-1</th><th>Distinct-2</th><th>Span match</th><th>Labels</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _quality_to_json(ds: DatasetStats) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if ds.lexical:
        lx = ds.lexical
        out["lexical_diversity"] = {
            "distinct_1_per_doc": {
                "mean": round(lx.distinct_1_mean, 4),
                "min": round(min(lx.per_doc_distinct_1), 4),
                "max": round(max(lx.per_doc_distinct_1), 4),
            },
            "distinct_2_per_doc": {
                "mean": round(lx.distinct_2_mean, 4),
                "min": round(min(lx.per_doc_distinct_2), 4),
                "max": round(max(lx.per_doc_distinct_2), 4),
            },
            "corpus": {
                "distinct_1": round(lx.corpus_distinct_1, 4),
                "distinct_2": round(lx.corpus_distinct_2, 4),
                "token_count": lx.corpus_token_count,
            },
        }
    if ds.integrity:
        gi = ds.integrity
        out["gold_integrity"] = {
            "entities_checked": gi.entities_checked,
            "span_match_rate": round(gi.span_match_rate, 6),
            "unique_span_rate": round(gi.unique_span_rate, 6),
            "planned_surfaces_exactly_once_rate": (
                None if gi.exactly_once_rate is None else round(gi.exactly_once_rate, 6)
            ),
            "planned_surfaces": gi.planned_surfaces,
            "used_exactly_once": gi.used_exactly_once,
        }
    return out


def _stats_to_json(all_stats: list[DatasetStats]) -> dict:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "metrics_note": (
            "Lexical diversity (distinct-1/2) matches ner-gold-generator build-gold "
            "stderr statistics. Gold integrity checks span anchoring on committed JSONL."
        ),
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
                "quality": _quality_to_json(ds),
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
    .summary, table.quality {{ width: 100%; border-collapse: collapse; margin-bottom: 2.5rem; font-size: 0.9rem; }}
    .summary th, .summary td, table.quality th, table.quality td {{
      padding: 0.5rem 0.65rem; border-bottom: 1px solid var(--border); text-align: left;
    }}
    .summary th, table.quality th {{ color: var(--muted); font-weight: 500; }}
    .summary .num, table.quality .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .summary tr.total td {{ border-top: 2px solid var(--border); }}
    table.quality {{ margin-bottom: 0.75rem; font-size: 0.88rem; }}
    .quality-note {{ font-size: 0.82rem; margin: 0 0 1rem; }}
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
      grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
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
      Includes <strong>lexical diversity</strong> (distinct-1/2) and <strong>gold integrity</strong>
      (span match, unique surfaces) — same family of metrics as <code>build-gold</code> stderr stats.
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
