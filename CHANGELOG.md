# Changelog

All notable changes to MarkdownReader will be documented in this file.

The project uses semantic versioning for installable releases.

## Unreleased

### Added

- Pipe-delimited Markdown tables, rendered as selectable minihtml divs in native
  previews and semantic HTML tables in browser previews.

### Changed

- Refined native preview typography, spacing, headings, quotations, inline code,
  code blocks, tables, Mermaid, and MathJax with a GitHub-inspired visual hierarchy
  that continues to follow the active Sublime color scheme.
- Restyled task lists with compact theme-aware checkboxes, muted completed labels,
  strike-through states, and nested-task guide lines in native and browser previews.
- Removed the duplicate visible Mermaid source below rendered diagrams while
  retaining the hidden definition required by the browser runtime.

## 0.1.0 - 2026-08-13

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
- Central untrusted-input policy with source, protocol, local-path, and image-size limits.
- Lazy reusable NDJSON renderer process with Node/Chrome diagnostics and lifecycle cleanup.
- Offline static Mermaid rendering with pinned local assets, transparent PNG output,
  per-block errors, theme/viewport sizing, network blocking, and isolated Chrome profiles.
- Offline static MathJax rendering for inline and display formulas with transparent,
  theme-aware PNG output, baseline alignment, per-formula errors, Copy TeX, and an
  opt-in single-dollar delimiter setting.
- Incremental Mermaid and MathJax rendering backed by a shared, bounded in-memory
  LRU cache with full renderer-option keys, same-key work coalescing, stale-revision
  rejection, and unload cleanup.
- Offline full-page browser preview with interactive Mermaid zoom, MathJax SVG,
  print/PDF export, embedded local images, strict CSP, and session-scoped cleanup.
- Annotated settings for refresh timing, native-preview remote-image policy,
  single-dollar math, and explicit Node.js/Chrome executable paths, with live
  refresh of open previews after settings or theme changes.
- A consolidated diagnostics command that reports effective settings, actionable
  environment problems, renderer readiness, and bundled component versions.
- Deterministic runtime-only `.sublime-package` and `SHA256SUMS` generation,
  including the Python 3.8 host selector required by installed packages.
- Vendored Mistune 3.3.0 runtime subset with Python 3.8 compatibility adjustments.
- Unit tests, a manual preview fixture, a project-local uv workflow, and CI checks.

### Fixed

- Resolve renderer theme from `View.style()` so Mermaid, MathJax, and the full
  browser preview remain readable after switching between light and dark themes.
