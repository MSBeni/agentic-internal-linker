from __future__ import annotations

import json
from pathlib import Path

from agentic_internal_linker.cli import main


def test_cli_writes_markdown_and_report(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog.json"
    source = tmp_path / "article.md"
    output = tmp_path / "linked.md"
    report = tmp_path / "report.json"
    catalog.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.com/internal-linking",
                    "title": "Internal Linking Guide",
                    "description": "A practical guide.",
                }
            ]
        ),
        encoding="utf-8",
    )
    source.write_text("Read our internal linking guide before publishing.\n", encoding="utf-8")

    exit_code = main(
        [
            "--catalog",
            str(catalog),
            "--input",
            str(source),
            "--output",
            str(output),
            "--report",
            str(report),
            "--base-url",
            "https://example.com",
        ]
    )

    assert exit_code == 0
    assert "[internal linking guide](https://example.com/internal-linking)" in output.read_text()
    assert json.loads(report.read_text())["report"]["links_added"] == 1
