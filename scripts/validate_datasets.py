#!/usr/bin/env python3
"""Validate committed gold JSONL under datasets/."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATASETS_DIR = _REPO_ROOT / "datasets"


def main() -> int:
    try:
        from ner_detector.eval.gold_validate import validate_arxiv_gold, validate_gold_examples
        from ner_detector.eval.loaders import load_gold_jsonl
    except ImportError:
        print(
            "ner-detector is required. Install with: uv sync --extra dev (from ner-dataset root)",
            file=sys.stderr,
        )
        return 1

    paths = sorted(_DATASETS_DIR.glob("*.jsonl"))
    if not paths:
        print(f"No JSONL files in {_DATASETS_DIR}", file=sys.stderr)
        return 1

    for path in paths:
        examples = load_gold_jsonl(path)
        if path.stem == "arxiv_gold":
            report = validate_arxiv_gold(examples)
        else:
            report = validate_gold_examples(examples, dataset_name=path.stem)
        report.raise_if_invalid()
        print(
            f"OK {path.name}: {report.n_examples} examples, {report.n_entities} entities",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
