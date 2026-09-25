from __future__ import annotations

import pytest

from agentic_internal_linker import AgenticInternalLinker, CatalogEntry, link_document
from agentic_internal_linker.markdown import apply_patches, parse_markdown
from agentic_internal_linker.models import Patch
from agentic_internal_linker.policy import URLPolicy

CATALOG = [
    {
        "url": "https://example.com/guides/internal-linking-strategy",
        "title": "Internal Linking Strategy",
        "description": "Plan contextual links between related pages.",
    },
    {
        "url": "https://example.com/guides/content-audit-checklist",
        "title": "Content Audit Checklist",
        "description": "Find outdated and orphaned pages before improving navigation.",
    },
    {
        "url": "https://example.com/guides/topic-cluster-guide",
        "title": "Topic Cluster Guide",
        "description": "Organize related articles around a central subject.",
    },
]

ARTICLE = """# Build a Better Content Library

An internal linking strategy helps readers discover related pages without interrupting the article.

Start with a content audit checklist to identify outdated pages and missing connections.

```python
# Internal Linking Strategy must stay untouched inside code.
print("content audit checklist")
```

- Keep navigation labels clear.
- Do not rewrite list formatting.

Use a topic cluster guide to organize supporting articles around each core subject.
"""


def test_links_realistic_markdown_without_reformatting() -> None:
    result = link_document(ARTICLE, CATALOG, base_url="https://example.com", max_links=3)

    assert result.report.ok
    assert result.report.links_added == 3
    assert (
        "[internal linking strategy](https://example.com/guides/internal-linking-strategy)"
        in result.linked_markdown
    )
    assert (
        "[content audit checklist](https://example.com/guides/content-audit-checklist)"
        in result.linked_markdown
    )
    assert (
        "[topic cluster guide](https://example.com/guides/topic-cluster-guide)"
        in result.linked_markdown
    )
    assert "# Internal Linking Strategy must stay untouched inside code." in result.linked_markdown
    assert (
        "- Keep navigation labels clear.\n- Do not rewrite list formatting."
        in result.linked_markdown
    )
    assert result.linked_markdown.endswith("core subject.\n")


def test_no_match_is_a_byte_for_byte_noop() -> None:
    markdown = (
        "# Heading\n\nUnrelated prose with no matching anchor.\n\n```text\n\nkeep blanks\n\n```\n"
    )
    result = link_document(markdown, CATALOG, base_url="https://example.com")

    assert result.report.ok
    assert result.report.links_added == 0
    assert result.linked_markdown == markdown


def test_existing_links_and_inline_code_are_preserved() -> None:
    markdown = (
        "An [internal linking strategy](https://example.com/existing) already exists.\n\n"
        "Keep `content audit checklist` as code, but this topic cluster guide is linkable.\n"
    )
    result = link_document(markdown, CATALOG, base_url="https://example.com")

    assert result.report.ok
    assert "[internal linking strategy](https://example.com/existing)" in result.linked_markdown
    assert "`content audit checklist`" in result.linked_markdown
    assert (
        "[topic cluster guide](https://example.com/guides/topic-cluster-guide)"
        in result.linked_markdown
    )


def test_frontmatter_html_and_list_continuations_are_skipped() -> None:
    markdown = """---
title: Internal Linking Strategy
---

<aside>Content audit checklist</aside>

- A topic cluster guide
  can organize internal linking strategy pages.

A content audit checklist helps editors find gaps.
"""
    result = link_document(markdown, CATALOG, base_url="https://example.com")

    assert "title: Internal Linking Strategy" in result.linked_markdown
    assert "<aside>Content audit checklist</aside>" in result.linked_markdown
    assert (
        "- A topic cluster guide\n  can organize internal linking strategy pages."
        in result.linked_markdown
    )
    assert (
        "A [content audit checklist](https://example.com/guides/content-audit-checklist)"
        in result.linked_markdown
    )


def test_reference_links_and_images_are_protected() -> None:
    markdown = (
        "Keep [internal linking strategy][guide] and "
        "![content audit checklist](image.png), then use a topic cluster guide.\n"
    )
    result = link_document(markdown, CATALOG, base_url="https://example.com")

    assert "[internal linking strategy][guide]" in result.linked_markdown
    assert "![content audit checklist](image.png)" in result.linked_markdown
    assert (
        "[topic cluster guide](https://example.com/guides/topic-cluster-guide)"
        in result.linked_markdown
    )


def test_rejects_invalid_base_url() -> None:
    with pytest.raises(ValueError, match=r"HTTP\(S\) origin"):
        AgenticInternalLinker(CATALOG, base_url="ftp://example.com")


def test_rejects_external_catalog_url() -> None:
    with pytest.raises(ValueError, match="outside the configured site"):
        AgenticInternalLinker(
            [{"url": "https://attacker.example/guide", "title": "Safe Looking Guide"}],
            base_url="https://example.com",
        )


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://user:password@example.com/private",
        "https://example.com/read more",
        "https://example.com/(malformed)",
        "https://example.com/privacy",
        "https://example.com/",
    ],
)
def test_rejects_unsafe_urls(url: str) -> None:
    policy = URLPolicy.from_base_url("https://example.com")
    ok, _ = policy.validate_url(url)
    assert not ok


def test_duplicate_catalog_urls_are_deduplicated() -> None:
    linker = AgenticInternalLinker(
        [CATALOG[0], {**CATALOG[0], "url": CATALOG[0]["url"] + "/"}],
        base_url="https://example.com",
    )
    assert len(linker.catalog) == 1


def test_validator_rejects_text_rewrite() -> None:
    linker = AgenticInternalLinker(CATALOG, base_url="https://example.com")
    markdown = "An internal linking strategy improves discovery.\n"
    blocks = parse_markdown(markdown)
    patch = Patch(
        block_index=0,
        original_text=blocks[0].text,
        new_text="Completely replaced [internal linking strategy](https://example.com/guides/internal-linking-strategy).\n",
        anchor="internal linking strategy",
        url="https://example.com/guides/internal-linking-strategy",
        anchor_start=3,
        anchor_end=28,
    )

    report = linker.validator.validate(blocks, [patch], linker.catalog, linker.policy, 4)
    assert not report.ok
    assert any("outside its anchor" in issue for issue in report.issues)


def test_patch_application_detects_stale_source() -> None:
    markdown = "Original paragraph.\n"
    blocks = parse_markdown(markdown)
    patch = Patch(
        block_index=0,
        original_text="Different source.\n",
        new_text="Different [source](https://example.com/source).\n",
        anchor="Different source",
        url="https://example.com/source",
        anchor_start=0,
        anchor_end=16,
    )
    with pytest.raises(ValueError, match="Source changed"):
        apply_patches(markdown, blocks, [patch])


def test_catalog_dataclass_is_supported() -> None:
    result = link_document(
        "Use the internal linking strategy before publishing.\n",
        [CatalogEntry(**CATALOG[0])],
        base_url="https://example.com",
        max_links=1,
    )
    assert result.report.links_added == 1
