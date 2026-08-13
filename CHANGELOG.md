# Changelog

All notable changes to MarkdownReader will be documented in this file.

The project intends to use semantic versioning once it has an installable release.

## Unreleased

### Added

- Initial public project structure.
- English and Simplified Chinese project overviews.
- Initial design for the native Markdown preview and local Mermaid/MathJax renderer.
- Native `HtmlSheet` preview command for the active, possibly unsaved Markdown buffer.
- Theme-aware minihtml rendering for core Markdown text, lists, quotations, and code blocks.
- Preview-tab reuse, source-derived titles, and command-palette integration.
- Explicit side-by-side preview with equal-column creation and existing-layout preservation.
- Debounced live refresh that preserves the preview group and source-editor focus.
- HTTP(S) links, static task-list markers, and resolved local PNG/JPG/GIF images.
- Vendored Mistune 3.3.0 runtime subset with Python 3.8 compatibility adjustments.
- Unit tests, a manual preview fixture, a project-local uv workflow, and CI checks.
