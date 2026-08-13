"""Sublime Text command entry points for MarkdownReader."""

import logging
import os
import subprocess
import tempfile
import threading
import webbrowser

import sublime
import sublime_plugin

from .markdown_reader.browser_preview import BrowserPreviewFiles, BrowserPreviewService
from .markdown_reader.diagnostics import format_diagnostics
from .markdown_reader.mathjax import MathJaxController, MathRenderOptions
from .markdown_reader.mermaid import (
    MermaidController,
    MermaidRenderOptions,
    mermaid_theme_for_background,
)
from .markdown_reader.preview import PreviewManager, choose_side_by_side_group
from .markdown_reader.refresh import DebouncedRefreshScheduler, LivePreviewController
from .markdown_reader.render_cache import BoundedMemoryCache
from .markdown_reader.renderer_environment import RendererEnvironmentDetector
from .markdown_reader.renderer_process import RendererProcess
from .markdown_reader.rendering import render_markdown
from .markdown_reader.security import SecurityPolicy
from .markdown_reader.settings import read_settings

LOGGER = logging.getLogger(__name__)
PACKAGE_SETTINGS_FILE = "MarkdownReader.sublime-settings"
PREFERENCES_FILE = "Preferences.sublime-settings"
PACKAGE_SETTINGS_CHANGE_KEY = "markdown_reader.package_settings"
PREFERENCES_CHANGE_KEY = "markdown_reader.preferences"


def _settings_snapshot():
    return read_settings(sublime.load_settings(PACKAGE_SETTINGS_FILE))


def _single_dollar_math_enabled():
    return _settings_snapshot().math_single_dollar


def _render_markdown_with_settings(*args, **kwargs):
    settings = _settings_snapshot()
    kwargs["allow_single_dollar_math"] = settings.math_single_dollar
    kwargs["policy"] = SecurityPolicy(
        allow_remote_images=settings.remote_images == "allow_https"
    )
    return render_markdown(*args, **kwargs)


PREVIEW_MANAGER = PreviewManager(_render_markdown_with_settings)
REFRESH_SCHEDULER = DebouncedRefreshScheduler(
    sublime.set_timeout,
    delay_provider=lambda: _settings_snapshot().refresh_delay_ms,
)
LIVE_PREVIEW_CONTROLLER = LivePreviewController(
    PREVIEW_MANAGER,
    REFRESH_SCHEDULER,
    sublime.Region,
)
RENDERER_PROCESS = None
RENDERER_PROCESS_LOCK = threading.Lock()
RENDER_CACHE = BoundedMemoryCache()
BROWSER_PREVIEW_FILES = BrowserPreviewFiles()


def _load_browser_preview_runtime():
    return sublime.load_resource(
        "Packages/MarkdownReader/renderer/browser-preview.js"
    )


def _open_system_browser(uri):
    return webbrowser.open(uri, new=2)


BROWSER_PREVIEW_SERVICE = BrowserPreviewService(
    runtime_loader=_load_browser_preview_runtime,
    files=BROWSER_PREVIEW_FILES,
    opener=_open_system_browser,
)


def _materialize_renderer_resource():
    source = sublime.load_resource("Packages/MarkdownReader/renderer/server.js")
    renderer_directory = os.path.join(sublime.cache_path(), "MarkdownReader", "renderer")
    renderer_path = os.path.join(renderer_directory, "server.js")
    os.makedirs(renderer_directory, exist_ok=True)
    try:
        with open(renderer_path, "r", encoding="utf-8") as existing:
            if existing.read() == source:
                return renderer_path
    except FileNotFoundError:
        pass

    descriptor, temporary_path = tempfile.mkstemp(dir=renderer_directory, suffix=".js")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write(source)
        os.replace(temporary_path, renderer_path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
    return renderer_path


def _create_renderer(environment):
    renderer_path = _materialize_renderer_resource()
    process_environment = os.environ.copy()
    process_environment["MARKDOWN_READER_CHROME_PATH"] = environment.chrome_path

    def start_process():
        return subprocess.Popen(
            [environment.node_path, renderer_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            env=process_environment,
        )

    return RendererProcess(start_process, timeout_seconds=30)


def _get_renderer_process(environment=None):
    global RENDERER_PROCESS
    with RENDERER_PROCESS_LOCK:
        if RENDERER_PROCESS is not None:
            return RENDERER_PROCESS

        environment = environment or _detect_renderer_environment()
        if not environment.ready:
            raise RuntimeError("; ".join(environment.problems))
        RENDERER_PROCESS = _create_renderer(environment)
        return RENDERER_PROCESS


def _detect_renderer_environment():
    settings = _settings_snapshot()
    return RendererEnvironmentDetector(
        configured_node_path=settings.node_path,
        configured_chrome_path=settings.chrome_path,
    ).detect()


def _mermaid_render_options(source_view):
    style = source_view.style_for_scope("text") or {}
    viewport_width, _ = source_view.viewport_extent()
    target_width = max(320, min(1600, int(viewport_width) - 64))
    return MermaidRenderOptions(
        theme=mermaid_theme_for_background(style.get("background", "")),
        width=target_width,
        scale=2,
    )


def _mathjax_render_options(source_view):
    style = source_view.style_for_scope("text") or {}
    viewport_width, _ = source_view.viewport_extent()
    target_width = max(320, min(1600, int(viewport_width) - 64))
    configured_font_size = source_view.settings().get("font_size", 16)
    try:
        font_size = int(round(float(configured_font_size)))
    except (TypeError, ValueError):
        font_size = 16
    return MathRenderOptions(
        theme=mermaid_theme_for_background(style.get("background", "")),
        width=target_width,
        scale=2,
        font_size=max(8, min(64, font_size)),
    )


MERMAID_CONTROLLER = MermaidController(
    preview_manager=PREVIEW_MANAGER,
    renderer_provider=_get_renderer_process,
    schedule_async=sublime.set_timeout_async,
    schedule_main=sublime.set_timeout,
    region_factory=sublime.Region,
    options_provider=_mermaid_render_options,
    cache=RENDER_CACHE,
)
MATHJAX_CONTROLLER = MathJaxController(
    preview_manager=PREVIEW_MANAGER,
    renderer_provider=_get_renderer_process,
    schedule_async=sublime.set_timeout_async,
    schedule_main=sublime.set_timeout,
    region_factory=sublime.Region,
    options_provider=_mathjax_render_options,
    cache=RENDER_CACHE,
)


def _render_special_blocks(window, source_view, source):
    MERMAID_CONTROLLER.preview_updated(window, source_view, source)
    MATHJAX_CONTROLLER.preview_updated(
        window,
        source_view,
        source,
        allow_single_dollar=_single_dollar_math_enabled(),
    )


PREVIEW_MANAGER.set_after_render(_render_special_blocks)


def plugin_loaded():
    package_settings = sublime.load_settings(PACKAGE_SETTINGS_FILE)
    preferences = sublime.load_settings(PREFERENCES_FILE)
    package_settings.clear_on_change(PACKAGE_SETTINGS_CHANGE_KEY)
    preferences.clear_on_change(PREFERENCES_CHANGE_KEY)
    package_settings.add_on_change(
        PACKAGE_SETTINGS_CHANGE_KEY,
        _on_package_settings_changed,
    )
    preferences.add_on_change(
        PREFERENCES_CHANGE_KEY,
        _on_preferences_changed,
    )


def _on_package_settings_changed():
    RENDER_CACHE.clear()
    sublime.set_timeout_async(_close_renderer_process)
    sublime.set_timeout(_refresh_all_previews)


def _on_preferences_changed():
    sublime.set_timeout(_refresh_all_previews)


def _refresh_all_previews():
    PREVIEW_MANAGER.refresh_all(sublime.Region)


def _close_renderer_process():
    global RENDERER_PROCESS
    with RENDERER_PROCESS_LOCK:
        if RENDERER_PROCESS is not None:
            RENDERER_PROCESS.close()
            RENDERER_PROCESS = None


def plugin_unloaded():
    sublime.load_settings(PACKAGE_SETTINGS_FILE).clear_on_change(
        PACKAGE_SETTINGS_CHANGE_KEY
    )
    sublime.load_settings(PREFERENCES_FILE).clear_on_change(
        PREFERENCES_CHANGE_KEY
    )
    BROWSER_PREVIEW_SERVICE.close()
    RENDER_CACHE.clear()
    _close_renderer_process()


def _open_preview(window, side_by_side):
    source_view = window.active_view()
    if source_view is None:
        sublime.status_message("MarkdownReader: No active document to preview")
        return

    try:
        group = choose_side_by_side_group(window) if side_by_side else -1
        PREVIEW_MANAGER.open_preview(window, source_view, sublime.Region, group=group)
    except Exception as error:
        LOGGER.exception("Unable to open Markdown preview")
        sublime.error_message("MarkdownReader could not open the preview: {}".format(error))


class MarkdownReaderOpenPreviewCommand(sublime_plugin.WindowCommand):
    """Open or update a native Markdown preview in the active group."""

    def is_enabled(self):
        return self.window.active_view() is not None

    def run(self):
        _open_preview(self.window, side_by_side=False)


class MarkdownReaderOpenPreviewSideBySideCommand(sublime_plugin.WindowCommand):
    """Open or update a native Markdown preview in an adjacent group."""

    def is_enabled(self):
        return self.window.active_view() is not None

    def run(self):
        _open_preview(self.window, side_by_side=True)


class MarkdownReaderOpenFullPreviewInBrowserCommand(sublime_plugin.WindowCommand):
    """Open an offline full-page preview in the system browser."""

    def is_enabled(self):
        return self.window.active_view() is not None

    def run(self):
        source_view = self.window.active_view()
        if source_view is None:
            sublime.status_message("MarkdownReader: No active document to preview")
            return

        source = source_view.substr(sublime.Region(0, source_view.size()))
        source_path = source_view.file_name()
        title = source_view.name()
        if not title:
            title = os.path.basename(source_path) if source_path else "Untitled"
        style = source_view.style_for_scope("text") or {}
        theme = (
            "dark"
            if mermaid_theme_for_background(style.get("background", "")) == "dark"
            else "light"
        )
        window_id = self.window.id()
        view_id = source_view.id()
        allow_single_dollar_math = _single_dollar_math_enabled()

        def open_browser_preview():
            try:
                BROWSER_PREVIEW_SERVICE.open(
                    window_id=window_id,
                    view_id=view_id,
                    source=source,
                    source_path=source_path,
                    title=title,
                    theme=theme,
                    allow_single_dollar_math=allow_single_dollar_math,
                )
            except Exception as error:
                LOGGER.exception("Unable to open browser Markdown preview")
                message = "MarkdownReader could not open the browser preview: {}".format(
                    error
                )
                sublime.set_timeout(lambda: sublime.error_message(message))
                return
            sublime.set_timeout(
                lambda: sublime.status_message(
                    "MarkdownReader: Full preview opened in the browser"
                )
            )

        sublime.set_timeout_async(open_browser_preview)


class MarkdownReaderCopyTexCommand(sublime_plugin.WindowCommand):
    """Copy TeX supplied only by MarkdownReader's trusted generated markup."""

    def run(self, text=""):
        if not isinstance(text, str) or len(text.encode("utf-8")) > 32 * 1024:
            sublime.error_message("MarkdownReader could not copy this TeX formula")
            return
        sublime.set_clipboard(text)
        sublime.status_message("MarkdownReader: TeX copied")


class MarkdownReaderLivePreviewListener(sublime_plugin.EventListener):
    """Schedule a debounced update after the source buffer changes."""

    def on_modified(self, view):
        LIVE_PREVIEW_CONTROLLER.on_modified(view)


class MarkdownReaderCheckRendererEnvironmentCommand(sublime_plugin.WindowCommand):
    """Check external renderer tools and the reusable NDJSON process."""

    def run(self):
        sublime.set_timeout_async(self._run_diagnostics)

    def _run_diagnostics(self):
        settings = _settings_snapshot()
        environment = _detect_renderer_environment()
        result = None
        renderer_error = ""
        if environment.ready:
            try:
                result = _get_renderer_process(environment).request("ping")
            except Exception as error:
                LOGGER.exception("Renderer diagnostics failed")
                renderer_error = str(error).strip().splitlines()[0][:500]
        message = format_diagnostics(
            settings,
            environment,
            ping=result,
            renderer_error=renderer_error,
        )
        sublime.set_timeout(lambda: sublime.message_dialog(message))
