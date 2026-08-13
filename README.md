# MarkdownReader

[简体中文](README.zh-CN.md)

MarkdownReader is a native Markdown reader and live-preview package for
Sublime Text 4. It is designed to keep normal Markdown content inside a Sublime
`HtmlSheet`, while rendering Mermaid diagrams and MathJax formulas locally as
embedded images.

> Latest release: [0.1.0](https://github.com/SisyphusSQ/MarkdownReader/releases/tag/0.1.0).
> Package Control submission is intentionally deferred until after the first
> GitHub release has received real-world validation.

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
directory, never to the Markdown project, and expires shortly after it is handed
to the browser. Plugin unload and the next startup also prune owned stale
artifacts. It is a point-in-time snapshot; run the command again after editing.

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

- Verified release environment: Sublime Text 4 Build 4200 on macOS.
- Builds 4065 and newer are the API compatibility target, but 0.1.0 has not
  received the same end-to-end coverage on every older build or operating system.
- Sublime plugin API environment: Python 3.8.
- Mermaid and MathJax rendering requires Node.js 22.12 or newer plus Chrome or
  Chromium. Core Markdown preview remains available when those tools are absent,
  with special blocks showing isolated errors.

## Design

The initial design, constraints, security model, and proof-of-concept checklist
are documented in
[docs/design/details/markdown-reader/sublime-markdown-reader.md](docs/design/details/markdown-reader/sublime-markdown-reader.md).

The repository root is also the Sublime package root.

## Install 0.1.0

Download `MarkdownReader.sublime-package` and `SHA256SUMS` from the
[0.1.0 release](https://github.com/SisyphusSQ/MarkdownReader/releases/tag/0.1.0).
Keep the package filename exactly `MarkdownReader.sublime-package`, because that
name is also the Sublime resource namespace used by the bundled renderer.

Optionally verify the download from the directory containing both files:

```bash
shasum -a 256 -c SHA256SUMS
```

Quit Sublime Text, copy the package into its `Installed Packages` directory,
then restart Sublime. On a standard macOS installation:

```bash
cp MarkdownReader.sublime-package \
  "$HOME/Library/Application Support/Sublime Text/Installed Packages/MarkdownReader.sublime-package"
```

Do not install the release package and a source checkout under the same package
name at the same time.

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

Build the deterministic release package and checksum file with:

```bash
.venv/bin/python scripts/build_release_package.py \
  --checksum-output dist/SHA256SUMS
```

The package contains only runtime Python files, settings/menu resources,
documentation needed by an installed user, the vendored Mistune subset, and the
two committed renderer bundles. It excludes tests, source modules for the
JavaScript build, `node_modules`, and development dependencies.

## Troubleshooting

Run **MarkdownReader: Show Diagnostics** first. A healthy report shows
`Renderer: READY`, the active Node.js and Chrome paths, protocol version 3, and
the pinned Mermaid, MathJax, and Puppeteer versions.

- If Node.js or Chrome is not found, set the absolute executable path through
  `node_path` or `chrome_path`. GUI applications may not inherit the same `PATH`
  as an interactive shell.
- A configured tool path is authoritative. If it is missing or not executable,
  diagnostics reports that path instead of silently selecting a different tool.
- Renderer resources are extracted automatically into Sublime's cache on first
  use. Do not run `npm install` inside the installed package.
- One malformed Mermaid block or MathJax formula becomes a local error panel;
  it does not prevent the rest of the document from rendering.
- The browser command creates a point-in-time page. Run it again after editing,
  and use the native preview when continuous refresh is required.

## Known limitations

- The 0.1.0 release is fully exercised on macOS with Sublime Text Build 4200;
  other supported-looking platforms and older builds still need broader field
  validation.
- Native previews render Mermaid and MathJax as static PNG images. Interactive
  Mermaid zoom and browser printing/PDF export are available only in the full
  browser preview.
- Local images are limited to PNG, JPG, and GIF inside the saved Markdown
  document's directory tree. Unsaved documents cannot resolve relative images.
- HTTPS remote images are an explicit native-preview opt-in and remain disabled
  in the full browser preview.
- The browser preview is a snapshot and is not kept in sync with later edits.
- Package Control installation is not part of this release; install the GitHub
  release asset or a source checkout.

## Releases

Release notes are available in
[docs/release-notes/0.1.0.md](https://github.com/SisyphusSQ/MarkdownReader/blob/0.1.0/docs/release-notes/0.1.0.md).
A future Package Control submission will reference tag-based releases from this
repository.

## License

[MIT](LICENSE)
