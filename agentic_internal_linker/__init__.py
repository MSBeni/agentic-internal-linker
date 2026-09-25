"""Public API for agentic-internal-linker."""

from .agents import PlannerAgent, SelectorAgent, ValidatorAgent, WriterAgent
from .linker import AgenticInternalLinker, link_document
from .models import CatalogEntry, LinkResult, ValidationReport
from .policy import URLPolicy

__all__ = [
    "AgenticInternalLinker",
    "CatalogEntry",
    "LinkResult",
    "PlannerAgent",
    "SelectorAgent",
    "URLPolicy",
    "ValidationReport",
    "ValidatorAgent",
    "WriterAgent",
    "link_document",
]

__version__ = "0.1.0"
