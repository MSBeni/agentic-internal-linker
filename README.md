# Agentic Internal Linker

Agentic Internal Linker is a small, safe-by-default Python package that adds contextual internal links to Markdown. It coordinates four narrowly scoped agents:

1. **Planner** finds eligible prose blocks without changing document structure.
2. **Selector** ranks same-site catalog entries that already have a natural anchor in the text.
3. **Writer** wraps that exact source span in Markdown link syntax. It never rewrites prose.
4. **Validator** independently verifies the URL, catalog membership, uniqueness, and byte-exact edit before any patch is applied.

The core package makes no network calls, sends no content to an AI provider, and has no runtime dependencies. “Agentic” describes the separated planning, selection, writing, and validation responsibilities—not an autonomous model with unrestricted tools.

> **Status:** `0.1.0` alpha. Use review workflows before applying output to production content.

## Why this design?

Internal linking is usually a constrained editing task. The first public release favors predictable behavior:

- Only HTTPS links from the configured site are accepted by default.
- External, credential-bearing, utility-page, homepage, and Markdown-unsafe URLs are rejected.
- Existing links, headings, lists, tables, fenced code, and inline code are not rewritten.
- If validation fails, the original document is returned unchanged.
- No generated anchor text or prose is introduced; an anchor must already exist in the document.
- Serialized reports omit document bodies unless content inclusion is explicitly requested.

## Install

From a checkout:

```bash
python -m pip install -e .
```

For development:

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
```

## Python API

```python
from agentic_internal_linker import link_document

catalog = [
    {
        "url": "https://example.com/guides/internal-linking-strategy",
        "title": "Internal Linking Strategy",
        "description": "Plan contextual links between related pages.",
    },
    {
        "url": "https://example.com/guides/content-audit-checklist",
        "title": "Content Audit Checklist",
        "description": "Find outdated and orphaned pages.",
    },
]

markdown = """# Improve Your Content

An internal linking strategy helps readers discover related pages.

Start with a content audit checklist before changing navigation.
"""

result = link_document(
    markdown,
    catalog,
    base_url="https://example.com",
    max_links=4,
)

if result.report.ok:
    print(result.linked_markdown)
else:
    print(result.report.issues)
```

## CLI

The repository includes a runnable example:

```bash
agentic-internal-linker \
  --catalog examples/catalog.json \
  --input examples/article.md \
  --output /tmp/linked-article.md \
  --report /tmp/link-report.json \
  --base-url https://example.com \
  --max-links 3
```

Catalog JSON may be a list or an object containing a `links` or `processed_links` list. Each entry requires `url` and `title`; `description` is optional.

## Trust boundaries

- Treat the catalog as trusted editorial input, even though every URL is validated.
- This library does not fetch catalog URLs. Confirm that destinations exist in your own crawler or publishing pipeline.
- `base_url` is recommended. When omitted, the linker only infers a policy if every catalog entry has exactly the same host.
- HTTP and subdomains are disabled unless explicitly enabled.
- The package is not an authentication or tenant-isolation layer. A service wrapping it must authorize catalogs and documents before calling the library.

## Current limitations

- Selection is deterministic lexical matching, not semantic embedding search.
- Anchors must already appear in the document.
- Complex Markdown constructs are deliberately skipped instead of being rewritten.
- It does not check live URLs or HTTP redirects.

These restrictions are intentional for the initial public release. Provider and vector-store adapters can be added later without weakening the core writer and validator invariants.

## Security

Please read [SECURITY.md](SECURITY.md) before reporting a vulnerability. Do not include credentials, private documents, or customer data in a public issue.

## License

MIT. See [LICENSE](LICENSE).
