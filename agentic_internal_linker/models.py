"""Small immutable data models used by the linker workflow."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    url: str
    title: str
    description: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> CatalogEntry:
        return cls(
            url=str(value.get("url", "")).strip(),
            title=str(value.get("title", "")).strip(),
            description=str(value.get("description", "")).strip(),
        )


@dataclass(frozen=True, slots=True)
class MarkdownBlock:
    index: int
    start: int
    end: int
    text: str
    kind: str

    @property
    def eligible(self) -> bool:
        return self.kind == "paragraph"


@dataclass(frozen=True, slots=True)
class Plan:
    requested_links: int
    target_block_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LinkCandidate:
    entry: CatalogEntry
    anchor: str
    anchor_start: int
    anchor_end: int
    score: float
    reason: str


@dataclass(frozen=True, slots=True)
class Patch:
    block_index: int
    original_text: str
    new_text: str
    anchor: str
    url: str
    anchor_start: int
    anchor_end: int


@dataclass(frozen=True, slots=True)
class ValidationReport:
    ok: bool
    issues: tuple[str, ...]
    links_added: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LinkResult:
    linked_markdown: str
    plan: Plan
    report: ValidationReport
    patches: tuple[Patch, ...]

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        """Serialize metadata, excluding document content unless explicitly requested."""
        value: dict[str, Any] = {
            "plan": asdict(self.plan),
            "report": self.report.to_dict(),
            "patches": [
                {
                    "block_index": patch.block_index,
                    "anchor": patch.anchor,
                    "url": patch.url,
                }
                for patch in self.patches
            ],
        }
        if include_content:
            value["linked_markdown"] = self.linked_markdown
            value["patches"] = [asdict(patch) for patch in self.patches]
        return value
