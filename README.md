# MarkdownReader

[简体中文](README.zh-CN.md)

MarkdownReader is a planned native Markdown reader and live-preview package for
Sublime Text 4. It is designed to keep normal Markdown content inside a Sublime
`HtmlSheet`, while rendering Mermaid diagrams and MathJax formulas locally as
embedded images.

> Project status: repository initialized; the package is not installable yet
> and no release has been published.

## Goals

- Open a Markdown reading view in a normal Sublime tab or a side-by-side group.
- Preview the current editor buffer without generating temporary HTML files.
- Keep normal text selectable and links usable inside the native `HtmlSheet`.
- Render Mermaid and MathJax blocks offline with a local headless browser.
- Isolate rendering failures and prevent untrusted documents from making
  implicit network requests.
- Preserve browser preview as an advanced path for interactive diagrams,
  printing, and export.

## Compatibility target

- Minimum planned Sublime Text build: 4065 or newer, subject to the APIs used
  by the implementation.
- Initial proof-of-concept target: Sublime Text 4 Build 4200.
- Sublime plugin API environment: Python 3.8.

## Design

The initial design, constraints, security model, and proof-of-concept checklist
are documented in
[docs/design/details/markdown-reader/sublime-markdown-reader.md](docs/design/details/markdown-reader/sublime-markdown-reader.md).

The repository root is also the Sublime package root. Runtime package files and
the renderer will be added only when their first vertical slice can be loaded
and verified; this bootstrap commit intentionally does not expose broken
commands or placeholder functionality.

## Releases

There are no releases yet. The first semantic version tag will be created only
after an installable package has passed its planned proof of concept. A future
Package Control submission will reference tag-based releases from this
repository.

## License

[MIT](LICENSE)
