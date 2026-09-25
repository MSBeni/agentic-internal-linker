"""Public orchestration API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .agents import PlannerAgent, SelectorAgent, ValidatorAgent, WriterAgent
from .markdown import apply_patches, parse_markdown
from .models import CatalogEntry, LinkResult
from .policy import URLPolicy, normalize_url, validate_catalog


class AgenticInternalLinker:
    """Coordinate four narrowly scoped agents to add safe Markdown links."""

    def __init__(
        self,
        catalog: Iterable[CatalogEntry | Mapping[str, Any]],
        *,
        base_url: str | None = None,
        max_links: int = 4,
        allow_subdomains: bool = False,
        allow_http: bool = False,
    ) -> None:
        if not 1 <= max_links <= 20:
            raise ValueError("max_links must be between 1 and 20")
        entries = [
            value if isinstance(value, CatalogEntry) else CatalogEntry.from_mapping(value)
            for value in catalog
        ]
        policy = (
            URLPolicy.from_base_url(
                base_url,
                allow_subdomains=allow_subdomains,
                allow_http=allow_http,
            )
            if base_url
            else URLPolicy.from_catalog(entries)
        )
        self.policy = policy
        self.catalog = validate_catalog(entries, policy)
        self.max_links = max_links
        self.planner = PlannerAgent()
        self.selector = SelectorAgent()
        self.writer = WriterAgent()
        self.validator = ValidatorAgent()

    def link(self, markdown: str) -> LinkResult:
        if not isinstance(markdown, str):
            raise TypeError("markdown must be a string")
        if len(markdown) > 500_000:
            raise ValueError("markdown cannot exceed 500,000 characters")

        blocks = parse_markdown(markdown)
        plan = self.planner.plan(blocks, self.max_links)
        by_index = {block.index: block for block in blocks}
        patches = []
        used_urls: set[str] = set()

        for block_index in plan.target_block_indices:
            if len(patches) >= plan.requested_links:
                break
            block = by_index[block_index]
            candidates = self.selector.select(block, self.catalog, used_urls)
            if not candidates:
                continue
            candidate = candidates[0]
            patches.append(self.writer.write(block, candidate))
            used_urls.add(normalize_url(candidate.entry.url))

        report = self.validator.validate(
            blocks,
            patches,
            self.catalog,
            self.policy,
            self.max_links,
        )
        linked = apply_patches(markdown, blocks, patches) if report.ok else markdown
        return LinkResult(
            linked_markdown=linked,
            plan=plan,
            report=report,
            patches=tuple(patches) if report.ok else (),
        )


def link_document(
    markdown: str,
    catalog: Iterable[CatalogEntry | Mapping[str, Any]],
    *,
    base_url: str | None = None,
    max_links: int = 4,
) -> LinkResult:
    """Convenience wrapper for one-shot use."""
    return AgenticInternalLinker(
        catalog,
        base_url=base_url,
        max_links=max_links,
    ).link(markdown)
