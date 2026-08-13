"""Build a self-contained, offline browser preview document."""

import base64
import hashlib
import os
import shutil
import tempfile
import threading
from pathlib import Path

from .mathjax import math_plugin
from .security import DEFAULT_SECURITY_POLICY
from .vendor.mistune import create_markdown
from .vendor.mistune.plugins.task_lists import task_lists
from .vendor.mistune.renderers.html import HTMLRenderer
from .vendor.mistune.util import escape, escape_url, striptags

_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; "
    "base-uri 'none'; "
    "connect-src 'none'; "
    "font-src 'none'; "
    "form-action 'none'; "
    "frame-src 'none'; "
    "img-src data:; "
    "media-src 'none'; "
    "object-src 'none'; "
    "script-src data:; "
    "style-src 'unsafe-inline'"
)
MAX_EMBEDDED_IMAGE_BYTES = 40 * 1024 * 1024
BROWSER_PREVIEW_DIRECTORY_PREFIX = "markdown-reader-browser-"
_DOCUMENT_STYLE = """
:root {
    color-scheme: light;
    --background: #ffffff;
    --foreground: #24292f;
    --muted: #57606a;
    --surface: #f6f8fa;
    --border: #d0d7de;
    --accent: #0969da;
    --danger: #cf222e;
}
html[data-theme="dark"] {
    color-scheme: dark;
    --background: #0d1117;
    --foreground: #e6edf3;
    --muted: #8b949e;
    --surface: #161b22;
    --border: #30363d;
    --accent: #58a6ff;
    --danger: #ff7b72;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    color: var(--foreground);
    background: var(--background);
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.preview-toolbar {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    justify-content: flex-end;
    padding: 0.75rem max(1rem, calc((100vw - 960px) / 2));
    border-bottom: 1px solid var(--border);
    background: color-mix(in srgb, var(--background) 92%, transparent);
    backdrop-filter: blur(10px);
}
button {
    padding: 0.42rem 0.7rem;
    color: var(--foreground);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 0.35rem;
    cursor: pointer;
}
button + button { margin-left: 0.35rem; }
button:hover { border-color: var(--accent); }
.preview-document {
    width: min(960px, calc(100% - 2rem));
    margin: 0 auto;
    padding: 2rem 0 4rem;
}
h1, h2, h3, h4, h5, h6 { line-height: 1.25; margin: 1.4em 0 0.6em; }
a { color: var(--accent); }
blockquote { margin-left: 0; padding-left: 1rem; border-left: 0.25rem solid var(--border); }
pre { overflow: auto; padding: 0.9rem; background: var(--surface); border-radius: 0.4rem; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
img.local-image { display: block; max-width: 100%; height: auto; margin: 1rem auto; }
.image-placeholder { color: var(--muted); }
.interactive-mermaid, .display-math {
    margin: 1rem 0;
    padding: 0.9rem;
    border: 1px solid var(--border);
    border-radius: 0.5rem;
    background: var(--surface);
}
.mermaid-toolbar { display: flex; justify-content: flex-end; margin-bottom: 0.75rem; }
.mermaid-viewport { overflow: auto; padding: 0.5rem; background: var(--background); }
.mermaid-target { width: 100%; transition: transform 120ms ease; }
.mermaid-source { margin-top: 0.75rem; color: var(--muted); }
.math-target mjx-container { margin: 0; color: var(--foreground); }
.display-math .math-target { display: block; overflow-x: auto; text-align: center; }
.render-error, .security-error { color: var(--danger); white-space: pre-wrap; }
@media print {
    .preview-toolbar { display: none; }
    .preview-document { width: 100%; padding: 0; }
    .interactive-mermaid, .display-math { break-inside: avoid; }
}
"""


def cleanup_stale_browser_preview_directories(
    directory=None,
    current_process_id=None,
    is_process_alive=None,
):
    """Remove browser-preview directories not owned by a live plugin host."""
    root = Path(directory) if directory else Path(tempfile.gettempdir())
    current_process_id = current_process_id or os.getpid()
    is_process_alive = is_process_alive or _is_process_alive
    removed = 0
    try:
        candidates = list(root.iterdir())
    except OSError:
        return removed
    for candidate in candidates:
        if not candidate.name.startswith(BROWSER_PREVIEW_DIRECTORY_PREFIX):
            continue
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        suffix = candidate.name[len(BROWSER_PREVIEW_DIRECTORY_PREFIX) :]
        process_text = suffix.split("-", 1)[0]
        process_id = int(process_text) if process_text.isdigit() else None
        if process_id == current_process_id:
            continue
        if process_id is not None and is_process_alive(process_id):
            continue
        shutil.rmtree(str(candidate), ignore_errors=True)
        if not candidate.exists():
            removed += 1
    return removed


def _is_process_alive(process_id):
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class BrowserPreviewFiles:
    """Own private, session-scoped browser preview artifacts."""

    def __init__(self, directory=None, temporary_root=None, process_id=None):
        self._configured_directory = Path(directory) if directory else None
        self._temporary_root = (
            Path(temporary_root) if temporary_root else Path(tempfile.gettempdir())
        )
        self._process_id = process_id or os.getpid()
        self._directory = None
        self._lock = threading.Lock()
        self._generations = {}

    def write(self, window_id, view_id, html):
        """Atomically replace the one preview artifact owned by a source view."""
        identity = "{}:{}".format(window_id, view_id).encode("utf-8")
        name = "preview-{}.html".format(hashlib.sha256(identity).hexdigest()[:24])
        with self._lock:
            directory = self._ensure_directory_unlocked()
            destination = directory / name
            generation = self._generations.get(destination, 0) + 1
            descriptor, temporary_path = tempfile.mkstemp(
                dir=str(directory),
                prefix=".preview-",
                suffix=".tmp",
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
                    temporary.write(html)
                os.replace(temporary_path, str(destination))
            finally:
                if os.path.exists(temporary_path):
                    os.unlink(temporary_path)
            self._generations[destination] = generation
            return destination

    def schedule_cleanup(self, path, scheduler, delay_ms):
        """Remove this exact artifact generation after the browser has loaded it."""
        path = Path(path)
        with self._lock:
            generation = self._generations.get(path)
        scheduler(lambda: self.remove(path, generation), delay_ms)

    def remove(self, path, generation=None):
        """Remove an owned artifact unless a newer generation replaced it."""
        path = Path(path)
        with self._lock:
            directory = self._directory
            if directory is None or path.parent != directory:
                return False
            if generation is not None and self._generations.get(path) != generation:
                return False
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                return False
            self._generations.pop(path, None)
            try:
                directory.rmdir()
            except OSError:
                pass
            else:
                self._directory = None
            return True

    def cleanup(self):
        """Remove every preview artifact created by this plugin session."""
        with self._lock:
            directory = self._directory
            self._directory = None
            self._generations.clear()
            if directory is not None:
                shutil.rmtree(str(directory), ignore_errors=True)

    def _ensure_directory_unlocked(self):
        if self._directory is not None:
            return self._directory
        if self._configured_directory is None:
            self._temporary_root.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory = Path(
                tempfile.mkdtemp(
                    prefix="{}{}-".format(
                        BROWSER_PREVIEW_DIRECTORY_PREFIX,
                        self._process_id,
                    ),
                    dir=str(self._temporary_root),
                )
            )
        else:
            directory = self._configured_directory
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass
        self._directory = directory
        return directory


class BrowserPreviewService:
    """Build one browser document and hand its URI to the system browser."""

    def __init__(
        self,
        runtime_loader,
        files,
        opener,
        schedule_cleanup=None,
        cleanup_delay_ms=10_000,
    ):
        self._runtime_loader = runtime_loader
        self._files = files
        self._opener = opener
        self._schedule_cleanup = schedule_cleanup
        self._cleanup_delay_ms = cleanup_delay_ms
        self._lock = threading.Lock()
        self._closed = False

    def open(
        self,
        window_id,
        view_id,
        source,
        source_path,
        title,
        theme,
        allow_single_dollar_math,
    ):
        """Materialize and open the current source revision as offline HTML."""
        with self._lock:
            if self._closed:
                raise RuntimeError("browser preview service is closed")
            html = render_browser_preview(
                source,
                runtime_script=self._runtime_loader(),
                source_path=source_path,
                allow_single_dollar_math=allow_single_dollar_math,
                title=title,
                theme=theme,
            )
            artifact = self._files.write(window_id, view_id, html)
            if not self._opener(artifact.as_uri()):
                self._files.remove(artifact)
                raise RuntimeError("default browser could not be opened")
            if self._schedule_cleanup is not None:
                self._files.schedule_cleanup(
                    artifact,
                    self._schedule_cleanup,
                    self._cleanup_delay_ms,
                )
            return artifact

    def close(self):
        """Prevent new work and remove all artifacts after active work finishes."""
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._files.cleanup()


class BrowserHtmlRenderer(HTMLRenderer):
    """Render the browser preview without granting Markdown active content."""

    def __init__(
        self,
        source_path=None,
        policy=DEFAULT_SECURITY_POLICY,
        max_embedded_image_bytes=MAX_EMBEDDED_IMAGE_BYTES,
    ):
        super().__init__(escape=True)
        self._source_path = source_path
        self._policy = policy
        self._max_embedded_image_bytes = max_embedded_image_bytes
        self._embedded_image_bytes = 0

    def link(self, text, url, title=None):
        """Keep only explicit HTTP(S) navigation as a user-triggered action."""
        if not self._policy.allows_link(url):
            return text
        link = (
            '<a href="{}" target="_blank" rel="noopener noreferrer" '
            'referrerpolicy="no-referrer"'
        ).format(escape(escape_url(url)))
        if title:
            link += ' title="{}"'.format(escape(title))
        return link + ">" + text + "</a>"

    def image(self, text, url, title=None):
        """Embed a policy-approved local image without exposing its path."""
        alt = striptags(text) or "untitled"
        image_path, reason = self._policy.resolve_local_image(url, self._source_path)
        if reason:
            return self._image_placeholder(alt, reason)
        try:
            expected_size = image_path.stat().st_size
            if (
                self._embedded_image_bytes + expected_size
                > self._max_embedded_image_bytes
            ):
                return self._image_placeholder(
                    alt,
                    "browser preview embedded-image limit reached",
                )
            image_bytes = image_path.read_bytes()
        except OSError:
            return self._image_placeholder(alt, "local image is not accessible")
        if (
            self._embedded_image_bytes + len(image_bytes)
            > self._max_embedded_image_bytes
        ):
            return self._image_placeholder(
                alt,
                "browser preview embedded-image limit reached",
            )
        self._embedded_image_bytes += len(image_bytes)

        subtype = image_path.suffix.lower().lstrip(".")
        if subtype == "jpg":
            subtype = "jpeg"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        image = '<img class="local-image" src="data:image/{};base64,{}" alt="{}"'.format(
            subtype,
            encoded,
            escape(alt),
        )
        if title:
            image += ' title="{}"'.format(escape(title))
        return image + " />"

    def block_code(self, code, info=None):
        """Expose Mermaid source only through inert text nodes."""
        language = info.strip().split(None, 1)[0] if info else ""
        if language.lower() != "mermaid":
            return super().block_code(code, info)
        safe_source = escape(code)
        return (
            '<section class="interactive-mermaid">'
            '<div class="mermaid-toolbar" aria-label="Diagram controls">'
            '<button type="button" data-action="zoom-out">Zoom out</button>'
            '<button type="button" data-action="reset">Reset</button>'
            '<button type="button" data-action="zoom-in">Zoom in</button>'
            "</div>"
            '<div class="mermaid-viewport"><div class="mermaid-target" '
            'aria-label="Interactive Mermaid diagram"></div></div>'
            '<pre class="mermaid-definition" hidden>{}</pre>'
            '<details class="mermaid-source"><summary>Mermaid source</summary>'
            '<pre><code>{}</code></pre></details>'
            "</section>\n"
        ).format(safe_source, safe_source)

    def block_math(self, tex, delimiter="dollar"):
        """Emit an inert display-formula definition for the local runtime."""
        del delimiter
        return self._render_math_definition(tex, display=True)

    def inline_math(self, tex, delimiter="bracket"):
        """Emit an inert inline-formula definition for the local runtime."""
        del delimiter
        return self._render_math_definition(tex, display=False)

    @staticmethod
    def _render_math_definition(tex, display):
        mode = "display-math" if display else "inline-math"
        tag = "div" if display else "span"
        return (
            '<{tag} class="math-expression {mode}">'
            '<span class="math-target" aria-label="Rendered formula"></span>'
            '<code class="math-definition" hidden>{tex}</code>'
            "</{tag}>"
        ).format(tag=tag, mode=mode, tex=escape(tex))

    @staticmethod
    def _image_placeholder(alt, reason):
        return '<em class="image-placeholder">[Image: {} — {}]</em>'.format(
            escape(alt),
            reason,
        )


def render_browser_preview(
    source,
    runtime_script,
    source_path=None,
    policy=DEFAULT_SECURITY_POLICY,
    max_embedded_image_bytes=MAX_EMBEDDED_IMAGE_BYTES,
    allow_single_dollar_math=False,
    title="Untitled",
    theme="light",
):
    """Return a complete HTML document with no external resource dependency."""
    renderer = BrowserHtmlRenderer(
        source_path=source_path,
        policy=policy,
        max_embedded_image_bytes=max_embedded_image_bytes,
    )
    rejection_reason = policy.source_rejection_reason(source)
    if rejection_reason:
        body = '<div class="security-error">{}</div>'.format(
            escape(rejection_reason)
        )
    else:
        markdown = create_markdown(
            renderer=renderer,
            plugins=[task_lists, math_plugin(allow_single_dollar_math)],
        )
        body = markdown(source)
    runtime_data = base64.b64encode(runtime_script.encode("utf-8")).decode("ascii")
    safe_theme = "dark" if theme == "dark" else "light"
    safe_title = escape(title or "Untitled")
    return (
        "<!doctype html>\n"
        '<html lang="en" data-theme="{}"><head><meta charset="utf-8">\n'
        '<meta http-equiv="Content-Security-Policy" content="{}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="referrer" content="no-referrer">\n'
        "<title>{} — MarkdownReader Preview</title>\n"
        "<style>{}</style>\n"
        "</head><body>\n"
        '<div class="preview-toolbar">'
        '<button type="button" data-action="print">Print / Save as PDF</button>'
        "</div>\n"
        '<main class="preview-document">{}</main>\n'
        '<script src="data:text/javascript;base64,{}"></script>\n'
        "</body></html>\n"
    ).format(
        safe_theme,
        _CONTENT_SECURITY_POLICY,
        safe_title,
        _DOCUMENT_STYLE,
        body,
        runtime_data,
    )
