# Contributing

Thank you for helping improve Agentic Internal Linker.

1. Create a focused feature branch.
2. Add tests for behavior and failure cases.
3. Run `pytest`, `ruff check .`, and `python -m build`.
4. Avoid adding network calls or provider SDKs to the dependency-free core.
5. Never commit secrets, customer content, production URLs, or private catalogs.

Changes to URL policy, Markdown parsing, patch application, or validation should include adversarial tests. New provider integrations should be optional adapters with explicit data-disclosure documentation.
