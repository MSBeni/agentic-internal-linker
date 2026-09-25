"""The planner, selector, writer, and validator agents."""

from __future__ import annotations

import re
from collections import Counter

from .markdown import markdown_links, overlaps_protected, protected_ranges
from .models import CatalogEntry, LinkCandidate, MarkdownBlock, Patch, Plan, ValidationReport
from .policy import URLPolicy, anchor_is_safe, normalize_url

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
STOPWORDS = {
    "about",
    "also",
    "and",
    "are",
    "for",
    "from",
    "have",
    "into",
    "its",
    "that",
    "the",
    "their",
    "this",
    "with",
    "your",
}


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text) if token.lower() not in STOPWORDS]


class PlannerAgent:
    """Select candidate prose blocks without asking a model to rewrite structure."""

    def plan(self, blocks: list[MarkdownBlock], max_links: int) -> Plan:
        eligible = [
            block
            for block in blocks
            if block.eligible and len(_tokens(block.text)) >= 4 and not markdown_links(block.text)
        ]
        if not eligible:
            return Plan(requested_links=0, target_block_indices=())

        first = eligible[0]
        rest = eligible[1:]
        rest.sort(key=lambda block: (-len(set(_tokens(block.text))), block.index))
        ordered = [first, *rest]
        return Plan(
            requested_links=min(max_links, len(eligible)),
            target_block_indices=tuple(block.index for block in ordered),
        )


class SelectorAgent:
    """Rank catalog entries and return only candidates with an exact safe anchor span."""

    def __init__(self, minimum_score: float = 0.35) -> None:
        self.minimum_score = minimum_score

    @staticmethod
    def _entry_terms(entry: CatalogEntry) -> Counter[str]:
        weighted: Counter[str] = Counter()
        weighted.update({term: 4 for term in _tokens(entry.title)})
        weighted.update(
            {term: 2 for term in _tokens(entry.url.replace("-", " ").replace("_", " "))}
        )
        weighted.update({term: 1 for term in _tokens(entry.description)})
        return weighted

    def _best_anchor(self, text: str, entry: CatalogEntry) -> tuple[str, int, int, float] | None:
        protected = protected_ranges(text)
        title_words = WORD_RE.findall(entry.title)
        if 2 <= len(title_words) <= 6:
            exact = re.search(re.escape(entry.title), text, flags=re.IGNORECASE)
            if exact and not overlaps_protected(exact.start(), exact.end(), protected):
                anchor = text[exact.start() : exact.end()]
                if anchor_is_safe(anchor):
                    return anchor, exact.start(), exact.end(), 1.0

        matches = list(WORD_RE.finditer(text))
        terms = self._entry_terms(entry)
        best: tuple[str, int, int, float] | None = None
        for size in range(2, min(6, len(matches)) + 1):
            for start_index in range(0, len(matches) - size + 1):
                window = matches[start_index : start_index + size]
                start, end = window[0].start(), window[-1].end()
                if overlaps_protected(start, end, protected):
                    continue
                anchor = text[start:end]
                if not anchor_is_safe(anchor):
                    continue
                anchor_terms = _tokens(anchor)
                matching = [term for term in anchor_terms if term in terms]
                if len(set(matching)) < 2:
                    continue
                density = len(matching) / max(1, len(anchor_terms))
                weight = sum(terms[term] for term in matching) / (4 * len(anchor_terms))
                score = 0.65 * density + 0.35 * min(1.0, weight)
                candidate = (anchor, start, end, score)
                if (
                    best is None
                    or candidate[3] > best[3]
                    or (candidate[3] == best[3] and len(anchor) < len(best[0]))
                ):
                    best = candidate
        return best

    def select(
        self,
        block: MarkdownBlock,
        catalog: list[CatalogEntry],
        used_urls: set[str],
    ) -> list[LinkCandidate]:
        paragraph_terms = set(_tokens(block.text))
        candidates: list[LinkCandidate] = []
        for entry in catalog:
            normalized_url = normalize_url(entry.url)
            if normalized_url in used_urls:
                continue
            anchor = self._best_anchor(block.text, entry)
            if anchor is None:
                continue
            anchor_text, start, end, anchor_score = anchor
            entry_terms = set(self._entry_terms(entry))
            overlap = len(paragraph_terms & entry_terms) / max(
                1, len(paragraph_terms | entry_terms)
            )
            score = 0.8 * anchor_score + 0.2 * overlap
            if score >= self.minimum_score:
                candidates.append(
                    LinkCandidate(
                        entry=entry,
                        anchor=anchor_text,
                        anchor_start=start,
                        anchor_end=end,
                        score=score,
                        reason="exact in-document anchor with catalog topic overlap",
                    )
                )
        return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.entry.url))


class WriterAgent:
    """Insert Markdown syntax around an existing span; never rewrite prose."""

    def write(self, block: MarkdownBlock, candidate: LinkCandidate) -> Patch:
        start, end = candidate.anchor_start, candidate.anchor_end
        if block.text[start:end] != candidate.anchor:
            raise ValueError("candidate anchor no longer matches its source span")
        new_text = (
            block.text[:start] + f"[{candidate.anchor}]({candidate.entry.url})" + block.text[end:]
        )
        return Patch(
            block_index=block.index,
            original_text=block.text,
            new_text=new_text,
            anchor=candidate.anchor,
            url=candidate.entry.url,
            anchor_start=start,
            anchor_end=end,
        )


class ValidatorAgent:
    """Fail closed unless every patch is the exact expected Markdown insertion."""

    def validate(
        self,
        blocks: list[MarkdownBlock],
        patches: list[Patch],
        catalog: list[CatalogEntry],
        policy: URLPolicy,
        max_links: int,
    ) -> ValidationReport:
        issues: list[str] = []
        by_index = {block.index: block for block in blocks}
        catalog_urls = {normalize_url(entry.url) for entry in catalog}
        seen_blocks: set[int] = set()
        seen_urls: set[str] = set()

        if len(patches) > max_links:
            issues.append(f"Patch count {len(patches)} exceeds maximum {max_links}")

        for patch in patches:
            block = by_index.get(patch.block_index)
            if block is None or not block.eligible:
                issues.append(f"Patch targets missing or ineligible block {patch.block_index}")
                continue
            if patch.block_index in seen_blocks:
                issues.append(f"Multiple patches target block {patch.block_index}")
            seen_blocks.add(patch.block_index)
            if patch.original_text != block.text:
                issues.append(f"Patch source mismatch in block {patch.block_index}")
                continue

            expected = (
                block.text[: patch.anchor_start]
                + f"[{patch.anchor}]({patch.url})"
                + block.text[patch.anchor_end :]
            )
            if (
                patch.new_text != expected
                or block.text[patch.anchor_start : patch.anchor_end] != patch.anchor
            ):
                issues.append(
                    f"Patch modifies text outside its anchor in block {patch.block_index}"
                )

            ok, reason = policy.validate_url(patch.url)
            if not ok:
                issues.append(f"Unsafe URL in block {patch.block_index}: {reason}")
                continue
            normalized = normalize_url(patch.url)
            if normalized not in catalog_urls:
                issues.append(f"URL is not in the catalog for block {patch.block_index}")
            if normalized in seen_urls:
                issues.append(f"Duplicate URL in block {patch.block_index}")
            seen_urls.add(normalized)
            if not anchor_is_safe(patch.anchor):
                issues.append(f"Unsafe anchor in block {patch.block_index}")

            original_links = [(anchor, url) for anchor, url, _, _ in markdown_links(block.text)]
            new_links = [(anchor, url) for anchor, url, _, _ in markdown_links(patch.new_text)]
            if len(new_links) != len(original_links) + 1:
                issues.append(f"Patch must add exactly one link in block {patch.block_index}")
            if any(link not in new_links for link in original_links):
                issues.append(f"Patch removes an existing link in block {patch.block_index}")

        return ValidationReport(
            ok=not issues, issues=tuple(issues), links_added=len(patches) if not issues else 0
        )
