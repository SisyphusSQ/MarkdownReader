# MarkdownReader

[简体中文](README.zh-CN.md)

MarkdownReader is a native Markdown reader and live-preview package for
Sublime Text 4. It is designed to keep normal Markdown content inside a Sublime
`HtmlSheet`, while rendering Mermaid diagrams and MathJax formulas locally as
embedded images.

> Project status: active 0.1.0 development. The first native-preview slice is
> usable from a source checkout; no release has been published yet.

## Available now

- Open the active Markdown buffer through **MarkdownReader: Open Preview**.
- Preview unsaved edits in a native, theme-aware Sublime `HtmlSheet`.
- Reuse the same preview tab when the command is run again.
- Render headings, paragraphs, emphasis, quotations, lists, and fenced code.
- Keep links inert and escape raw HTML until the dedicated security and link
  handling slices are complete.

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

The repository root is also the Sublime package root.

## Install from source

On macOS, clone this repository and link it into Sublime's Packages directory:

```bash
ln -s /absolute/path/to/MarkdownReader \
  "$HOME/Library/Application Support/Sublime Text/Packages/MarkdownReader"
```

Use **Preferences: Browse Packages** if your Sublime installation uses a
different Packages directory. Reload the plugin or restart Sublime, open a
Markdown file, and run **MarkdownReader: Open Preview** from the Command
Palette.

## Development

The plugin runtime has no installation-time Python dependency: the required
Mistune subset is vendored in the package. Development uses Python 3.8 to match
Sublime's plugin host and a project-local uv environment:

```bash
uv venv --python 3.8 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/python -m unittest discover -s tests -v
```

## Releases

There are no releases yet. The first semantic version tag will be created only
after an installable package has passed its planned proof of concept. A future
Package Control submission will reference tag-based releases from this
repository.

## License

[MIT](LICENSE)
