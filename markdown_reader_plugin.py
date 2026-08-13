"""Sublime Text command entry points for MarkdownReader."""

import logging

import sublime
import sublime_plugin

from .markdown_reader.preview import PreviewManager
from .markdown_reader.rendering import render_markdown

LOGGER = logging.getLogger(__name__)
PREVIEW_MANAGER = PreviewManager(render_markdown)


class MarkdownReaderOpenPreviewCommand(sublime_plugin.WindowCommand):
    """Open or update a native Markdown preview for the active view."""

    def is_enabled(self):
        return self.window.active_view() is not None

    def run(self):
        source_view = self.window.active_view()
        if source_view is None:
            sublime.status_message("MarkdownReader: No active document to preview")
            return

        try:
            PREVIEW_MANAGER.open_preview(self.window, source_view, sublime.Region)
        except Exception as error:
            LOGGER.exception("Unable to open Markdown preview")
            sublime.error_message("MarkdownReader could not open the preview: {}".format(error))
