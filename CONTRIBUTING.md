# Contributing

Thank you for helping improve Agentic Internal Linker.

1. Fork the repository and create a focused feature branch.
2. Add tests for behavior and failure cases.
3. Run `pytest`, `ruff check .`, and `python -m build`.
4. Open a pull request against `main`; direct pushes to `main` are blocked.
5. Avoid adding network calls or provider SDKs to the dependency-free core.
6. Never commit secrets, customer content, production URLs, or private catalogs.

Changes to URL policy, Markdown parsing, patch application, or validation should include adversarial tests. New provider integrations should be optional adapters with explicit data-disclosure documentation.
