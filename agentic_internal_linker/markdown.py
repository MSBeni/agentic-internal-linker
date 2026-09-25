"""Conservative Markdown parsing and exact-span patch application."""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import MarkdownBlock, Patch

FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^[ \t]{0,3}#{1,6}(?:[ \t]+|$)")
STRUCTURAL_RE = re.compile(r"^[ \t]*(?:>|[-+*][ \t]+|\d+[.)][ \t]+)")
TABLE_RE = re.compile(r"^[ \t]*\|.*\|[ \t]*$")
HTML_RE = re.compile(r"^[ \t]{0,3}<(?:!|/?[A-Za-z])")
THEMATIC_BREAK_RE = re.compile(r"^[ \t]{0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)]\(([^\s)]+)\)")
REFERENCE_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]+]\[[^\]\n]*]")
IMAGE_RE = re.compile(r"!\[[^\]\n]*]\([^\n)]*\)")
INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")


def _line_kind(line: str) -> str:
    if HEADING_RE.match(line):
        return "heading"
    if STRUCTURAL_RE.match(line):
        return "structure"
    if TABLE_RE.match(line) or HTML_RE.match(line) or THEMATIC_BREAK_RE.match(line.rstrip("\r\n")):
        return "structure"
    return "paragraph"


def parse_markdown(markdown: str) -> list[MarkdownBlock]:
    """Return source spans without normalizing or rewriting the input."""
    lines = markdown.splitlines(keepends=True)
    blocks: list[MarkdownBlock] = []
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)

    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue

        start_i = i
        if i == 0 and lines[i].rstrip("\r\n") == "---":
            i += 1
            while i < len(lines):
                closing_front_matter = lines[i].rstrip("\r\n") in {"---", "..."}
                i += 1
                if closing_front_matter:
                    break
            kind = "frontmatter"
            start = offsets[start_i]
            end = offsets[i] if i < len(offsets) else len(markdown)
            blocks.append(
                MarkdownBlock(
                    index=len(blocks),
                    start=start,
                    end=end,
                    text=markdown[start:end],
                    kind=kind,
                )
            )
            continue

        fence_match = FENCE_RE.match(lines[i])
        if fence_match:
            marker = fence_match.group(1)[0]
            minimum = len(fence_match.group(1))
            i += 1
            while i < len(lines):
                closing = re.match(
                    rf"^[ \t]{{0,3}}{re.escape(marker)}{{{minimum},}}[ \t]*$",
                    lines[i].rstrip("\r\n"),
                )
                i += 1
                if closing:
                    break
            kind = "code"
        else:
            kind = _line_kind(lines[i])
            i += 1
            if kind == "paragraph":
                while i < len(lines) and lines[i].strip():
                    if FENCE_RE.match(lines[i]) or _line_kind(lines[i]) != "paragraph":
                        break
                    i += 1
            elif kind == "structure":
                while i < len(lines) and lines[i].strip() and not FENCE_RE.match(lines[i]):
                    i += 1

        start = offsets[start_i]
        end = offsets[i] if i < len(offsets) else len(markdown)
        blocks.append(
            MarkdownBlock(
                index=len(blocks), start=start, end=end, text=markdown[start:end], kind=kind
            )
        )

    return blocks


def markdown_links(text: str) -> list[tuple[str, str, int, int]]:
    return [(m.group(1), m.group(2), m.start(), m.end()) for m in LINK_RE.finditer(text)]


def protected_ranges(text: str) -> list[tuple[int, int]]:
    ranges = [(start, end) for _, _, start, end in markdown_links(text)]
    ranges.extend((match.start(), match.end()) for match in REFERENCE_LINK_RE.finditer(text))
    ranges.extend((match.start(), match.end()) for match in IMAGE_RE.finditer(text))
    ranges.extend((match.start(), match.end()) for match in INLINE_CODE_RE.finditer(text))
    return sorted(ranges)


def overlaps_protected(start: int, end: int, ranges: Iterable[tuple[int, int]]) -> bool:
    return any(
        start < protected_end and end > protected_start for protected_start, protected_end in ranges
    )


def apply_patches(markdown: str, blocks: list[MarkdownBlock], patches: Iterable[Patch]) -> str:
    """Apply validated block replacements from the end of the document backward."""
    by_index = {block.index: block for block in blocks}
    result = markdown
    for patch in sorted(patches, key=lambda item: by_index[item.block_index].start, reverse=True):
        block = by_index[patch.block_index]
        if result[block.start : block.end] != patch.original_text:
            raise ValueError(f"Source changed before patching block {patch.block_index}")
        result = result[: block.start] + patch.new_text + result[block.end :]
    return result
