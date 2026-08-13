# MarkdownReader product and rendering design

- Status: approved for project initialization
- Package name: `MarkdownReader`
- Initial PoC target: Sublime Text 4 Build 4200
- Planned minimum build: 4065 or newer, subject to the APIs actually used

## Objective

Build a native Markdown reader and live-preview package for Sublime Text 4.
Normal Markdown is rendered in a Sublime `HtmlSheet`; Mermaid diagrams and
MathJax formulas are rendered locally and embedded as images. Source code is
distributed from one public GitHub repository and future releases use semantic
version tags for Package Control.

The package is intentionally named `MarkdownReader` to distinguish it from
`MarkdownPreview`, whose primary preview path is a web browser.

## User experience

- Provide separate commands for opening the preview in the current group and
  in a side-by-side group. Do not silently change the user's existing layout.
- Read the active, possibly unsaved, editor buffer and refresh after a short
  debounce.
- Keep headings, paragraphs, lists, links, quotations, task lists, code blocks,
  and local images as native minihtml content.
- Keep normal text selectable. Do not rasterize the entire document.
- Use browser preview only for capabilities that require a full browser, such
  as interactive Mermaid diagrams, printing, and export.

## Rendering architecture

The proposed data flow is:

`Markdown buffer -> block parsing -> local rendering -> PNG data -> HtmlSheet`

### Normal Markdown

Normal Markdown is converted to minihtml and assigned to a Sublime
`HtmlSheet`. The preview may be opened as an editor tab or in an adjacent
group. Rendering must not depend on temporary HTML files.

The implementation must verify how `HtmlSheet.set_contents()` affects the
current scroll position. Sublime does not expose a complete public viewport API,
so synchronized source/preview scrolling is not a committed feature.

### Mermaid and MathJax

- Recognize fenced Mermaid code blocks.
- Recognize block and common inline MathJax syntax.
- Treat single-dollar inline formulas as an opt-in setting to avoid
  interpreting currency as TeX.
- Generate SVG in a hidden local browser page, then capture a transparent PNG
  suitable for minihtml.
- Use a high pixel density and render against the current light or dark theme.
- Return image data in memory or as Base64; never write generated images into
  the user's Markdown project.
- Render wide diagrams against the target preview width.
- Preserve the original Mermaid or TeX source so users can inspect or copy it
  when the image itself is not selectable.

### Renderer process

The first implementation may require the user's existing Node.js and Chrome,
with explicit environment checks and actionable error messages. A later phase
may evaluate a self-contained cross-platform renderer.

The renderer should be a single lazy, reusable child process:

- communicate over newline-delimited JSON on stdin/stdout;
- never open a listening port;
- launch Chrome only when the document first requires Mermaid or MathJax;
- load pinned Mermaid and MathJax assets locally rather than from a CDN;
- use `puppeteer-core` or an equivalent client with the user's installed
  Chrome;
- close child processes when the plugin unloads or Sublime exits.

The renderer bundle required at runtime must be included in release tags.
Package Control installations cannot rely on running `npm install` after the
package is installed.

## Incremental updates and caching

Only changed Mermaid or formula blocks should be rendered again. A cache key
must include at least:

- source text;
- renderer type and renderer version;
- color theme;
- target width;
- scale or font size.

The initial cache may be in memory. Persistent caching should be considered only
after invalidation, cleanup, privacy, and storage limits are defined.

## Failure behavior

- A syntax error in one Mermaid or MathJax block affects only that block.
- Replace a failed image with a concise error summary and the original source.
- A missing Node.js or Chrome binary produces an environment diagnostic rather
  than a blank preview.
- Renderer crashes and timeouts are reported without blocking normal Markdown
  rendering.
- Preview refreshes should discard stale responses from earlier buffer
  revisions.

## Security model

Markdown and embedded diagram source are untrusted input.

- Disable raw Markdown HTML by default.
- Reject or sanitize `subl:` links so a document cannot invoke arbitrary
  Sublime commands.
- Default to blocking remote images and other implicit network access.
- Use Mermaid's strict security mode and disable click actions and embedded
  HTML.
- Intercept and reject browser network requests during local rendering.
- Launch Chrome with an isolated temporary profile that does not reuse the
  user's cookies, extensions, or authenticated browser state.
- Apply a source-size limit and timeout to every rendered block.
- Pin renderer assets and never fetch executable scripts from a CDN at preview
  time.

Current native-preview defaults enforce a 2 MiB Markdown source limit and a
20 MiB local-image limit. Local images are restricted to regular PNG, JPG, or
GIF files within the saved Markdown file's directory tree. Renderer-process,
Mermaid, MathJax, browser-network, timeout, and isolated-profile controls are
implemented with their respective rendering slices rather than implied by the
native-only path.

## Static-image boundary

The embedded Mermaid and MathJax output is a high-quality static image:

- Mermaid node clicks, animation, pan, and zoom are not preserved.
- Formula glyphs cannot be selected directly, so copying the original TeX must
  remain available.
- Inline formulas require baseline-alignment validation.
- Browser preview remains the supported path for interactive Mermaid, printing,
  and export.

## PoC acceptance checklist

The first development milestone should validate:

1. A Markdown buffer can open and refresh in an `HtmlSheet`.
2. Refreshing does not unexpectedly reset the user's preview position, or the
   limitation is made explicit.
3. A Mermaid flowchart, an inline formula, and a block formula can be returned
   as in-memory PNG data and embedded in the sheet.
4. Retina clarity, transparent backgrounds, theme changes, formula baselines,
   and wide diagrams remain readable.
5. Only changed special blocks are rendered again and stale responses are
   ignored.
6. A malformed block does not break the rest of the preview.
7. Network blocking, the isolated Chrome profile, input limits, and timeouts are
   effective.
8. Browser preview reliably handles interactive diagrams, printing, and export.

After the PoC passes, decide the first public release's supported platforms,
renderer packaging, dependency diagnostics, and Package Control submission
scope.

## Distribution

- Keep exactly one Sublime package in this repository.
- Keep the package root at the repository root.
- Use semantic version tags such as `0.1.0` only for installable releases.
- Submit the repository to `wbond/package_control_channel` after the package is
  ready for public installation.
- After acceptance, new semantic version tags become the normal upgrade path.
