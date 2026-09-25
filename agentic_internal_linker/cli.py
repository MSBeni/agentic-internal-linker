"""Command-line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .linker import AgenticInternalLinker


def _catalog_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("links", "processed_links"):
            if isinstance(value.get(key), list):
                return value[key]
    raise ValueError("catalog JSON must be a list or contain a 'links'/'processed_links' list")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Add safe internal links to Markdown")
    parser.add_argument("--catalog", required=True, type=Path, help="JSON link catalog")
    parser.add_argument("--input", type=Path, help="Markdown input; defaults to stdin")
    parser.add_argument("--output", type=Path, help="Markdown output; defaults to stdout")
    parser.add_argument("--report", type=Path, help="Optional JSON result report")
    parser.add_argument(
        "--base-url", help="Required site origin when the catalog has multiple hosts"
    )
    parser.add_argument("--max-links", type=int, default=4)
    parser.add_argument("--allow-subdomains", action="store_true")
    parser.add_argument("--allow-http", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog_data = json.loads(args.catalog.read_text(encoding="utf-8"))
    markdown = args.input.read_text(encoding="utf-8") if args.input else sys.stdin.read()
    linker = AgenticInternalLinker(
        _catalog_items(catalog_data),
        base_url=args.base_url,
        max_links=args.max_links,
        allow_subdomains=args.allow_subdomains,
        allow_http=args.allow_http,
    )
    result = linker.link(markdown)
    if args.output:
        args.output.write_text(result.linked_markdown, encoding="utf-8")
    else:
        sys.stdout.write(result.linked_markdown)
    if args.report:
        args.report.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    return 0 if result.report.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
