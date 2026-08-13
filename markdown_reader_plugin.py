"""Sublime Text command entry points for MarkdownReader."""

import logging

import sublime
import sublime_plugin

from .markdown_reader.preview import PreviewManager, choose_side_by_side_group
from .markdown_reader.rendering import render_markdown

LOGGER = logging.getLogger(__name__)
PREVIEW_MANAGER = PreviewManager(render_markdown)


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
