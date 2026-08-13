"""Sublime Text command entry points for MarkdownReader."""

import logging
import os
import subprocess
import tempfile

import sublime
import sublime_plugin

from .markdown_reader.preview import PreviewManager, choose_side_by_side_group
from .markdown_reader.refresh import DebouncedRefreshScheduler, LivePreviewController
from .markdown_reader.renderer_environment import RendererEnvironmentDetector
from .markdown_reader.renderer_process import RendererProcess
from .markdown_reader.rendering import render_markdown

LOGGER = logging.getLogger(__name__)
PREVIEW_MANAGER = PreviewManager(render_markdown)
REFRESH_SCHEDULER = DebouncedRefreshScheduler(sublime.set_timeout)
LIVE_PREVIEW_CONTROLLER = LivePreviewController(
    PREVIEW_MANAGER,
    REFRESH_SCHEDULER,
    sublime.Region,
)
RENDERER_PROCESS = None


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

    return RendererProcess(start_process)


def plugin_unloaded():
    global RENDERER_PROCESS
    if RENDERER_PROCESS is not None:
        RENDERER_PROCESS.close()
        RENDERER_PROCESS = None


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


class MarkdownReaderLivePreviewListener(sublime_plugin.EventListener):
    """Schedule a debounced update after the source buffer changes."""

    def on_modified(self, view):
        LIVE_PREVIEW_CONTROLLER.on_modified(view)


class MarkdownReaderCheckRendererEnvironmentCommand(sublime_plugin.WindowCommand):
    """Check external renderer tools and the reusable NDJSON process."""

    def run(self):
        sublime.set_timeout_async(self._run_diagnostics)

    def _run_diagnostics(self):
        global RENDERER_PROCESS
        environment = RendererEnvironmentDetector().detect()
        if not environment.ready:
            message = "MarkdownReader renderer is not ready:\n\n- " + "\n- ".join(
                environment.problems
            )
            sublime.set_timeout(lambda: sublime.error_message(message))
            return

        try:
            if RENDERER_PROCESS is None:
                RENDERER_PROCESS = _create_renderer(environment)
            result = RENDERER_PROCESS.request("ping")
        except Exception as error:
            LOGGER.exception("Renderer diagnostics failed")
            error_message = "MarkdownReader renderer diagnostics failed: {}".format(error)
            sublime.set_timeout(
                lambda message=error_message: sublime.error_message(message)
            )
            return

        message = (
            "MarkdownReader renderer is ready.\n\n"
            "Node: {}\nChrome: {}\nProtocol: {}"
        ).format(result["nodeVersion"], environment.chrome_path, result["protocolVersion"])
        sublime.set_timeout(lambda: sublime.message_dialog(message))
