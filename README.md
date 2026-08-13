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
- Open or move the preview to an adjacent group through
  **MarkdownReader: Open Preview Side by Side**. A single-group window becomes
  two equal columns; existing multi-group layouts are preserved.
- Preview unsaved edits in a native, theme-aware Sublime `HtmlSheet`.
- Refresh an open preview after a configurable debounce delay (250ms by
  default) without moving the preview or stealing editor focus.
- Reuse the same preview tab when the command is run again.
- Render headings, paragraphs, emphasis, quotations, lists, and fenced code.
- Open absolute HTTP(S) links through Sublime's native minihtml protocol support.
- Render task lists with static checkbox markers.
- Render existing local PNG, JPG, and GIF files relative to a saved Markdown
  file. Remote images are blocked by default and can be enabled explicitly for
  HTTPS only; missing and unsupported images remain explicit placeholders.
- Keep other link protocols inert and escape raw HTML.
- Inspect effective settings, Node.js, Chrome, and local renderer versions
  through **MarkdownReader: Show Diagnostics**.
- Render fenced `mermaid` blocks offline as transparent, theme-aware PNG images
  while preserving the original diagram source below each image.
- Render `\(...\)` inline formulas plus `$$...$$` and `\[...\]` display
  formulas through local MathJax as transparent PNG images. Single-dollar math
  is disabled by default so currency remains ordinary text; each formula has a
  **Copy TeX** action.
- Re-render only changed Mermaid and MathJax sources. Completed results use a
  shared in-memory LRU cache bounded to 128 entries and an estimated 64 MiB;
  cache keys include the renderer/version and every visual render option.
- Open an offline, full-page snapshot through **MarkdownReader: Open Full
  Preview in Browser**. The browser page keeps Mermaid as sanitized SVG with
  zoom controls, renders MathJax as SVG, and provides **Print / Save as PDF**.

## Settings and diagnostics

Open **Preferences: Package Settings → MarkdownReader → Settings** to configure:

- `refresh_delay_ms`: native-preview debounce delay from 50 to 5000ms; the
  default is `250`.
- `remote_images`: `"blocked"` by default, or `"allow_https"` to let the native
  preview contact explicitly referenced HTTPS image hosts. The offline browser
  preview always blocks remote images.
- `math_single_dollar`: opt in to `$...$` inline formulas; the default is
  `false` so currency remains text.
- `node_path` and `chrome_path`: optional absolute executable paths. Empty
  values use auto-detection. A configured path is authoritative, so a missing
  or non-executable target is reported instead of silently falling back.

Valid setting changes and Sublime theme/preference changes refresh every open
native preview without restarting the editor. Invalid values fall back to safe
defaults and appear under **Settings warnings** in **MarkdownReader: Show
Diagnostics**. The same report shows whether the renderer is ready, which tool
paths are active, and the protocol, Mermaid, MathJax, and Puppeteer versions.

## Security defaults

Markdown is treated as untrusted input. Raw HTML is escaped, while `subl:` and
other non-HTTP(S) links are inert. Remote images are blocked by default. The
native preview's `"allow_https"` opt-in permits requests only to explicit HTTPS
URLs without embedded credentials; enabling it discloses the reader's IP
address and request metadata to those image hosts. Local images must be regular
PNG, JPG, or GIF files inside the saved Markdown file's directory tree and no
larger than 20 MiB. Markdown sources larger than 2 MiB show a diagnostic instead
of entering the parser. These limits are measured in bytes.

The full browser preview does not grant the browser access to the Markdown
project. Approved local images are embedded as data URIs, raw HTML remains
escaped, Mermaid uses strict mode with active links removed, and a Content
Security Policy blocks network, file, frame, form, media, and object resources.
All embedded local images share an additional 40 MiB document budget. The
self-contained HTML is written to a private operating-system temporary
directory, never to the Markdown project, and is removed when the plugin
unloads. It is a point-in-time snapshot; run the command again after editing.

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

The special-block renderer requires Node.js 22.12 or newer and Chrome or
Chromium. It is a lazy, reusable Node.js child process using
newline-delimited JSON over stdin/stdout; it never opens a listening port.
Renderer resources bundled with the package are materialized under Sublime's
cache directory when first needed. The pinned Mermaid, MathJax, and
`puppeteer-core` runtime is committed as a single bundle, so end users do not
run `npm install`. Rendered diagram and formula images are cached only in
memory, are cleared when the plugin unloads, and are never written to disk.
The separate browser-preview bundle is also included in the package and runs
inside a modern default browser without a CDN request.

## Releases

There are no releases yet. The first semantic version tag will be created only
after an installable package has passed its planned proof of concept. A future
Package Control submission will reference tag-based releases from this
repository.

## License

[MIT](LICENSE)
