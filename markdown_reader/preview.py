"""Manage native preview sheets independently of the Sublime import boundary."""

import os

_TWO_COLUMN_LAYOUT = {
    "cols": [0.0, 0.5, 1.0],
    "rows": [0.0, 1.0],
    "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
}


def choose_side_by_side_group(window):
    """Return an adjacent preview group, creating two columns when needed."""
    active_group = window.active_group()
    group_count = window.num_groups()
    if group_count == 1:
        window.set_layout(_TWO_COLUMN_LAYOUT)
        return 1
    if active_group < group_count - 1:
        return active_group + 1
    return active_group - 1


class PreviewManager:
    """Create or update one preview sheet per source view in a window."""

    def __init__(self, render):
        self._render = render
        self._sheets = {}
        self._sources = {}
        self._special_results = {}
        self._after_render = None

    def set_after_render(self, callback):
        """Register a callback used to schedule special-block rendering."""
        self._after_render = callback

    def open_preview(self, window, source_view, region_factory, group=-1):
        """Render the source's current buffer and focus its preview sheet."""
        source, title, contents = self._render_preview(
            window,
            source_view,
            region_factory,
        )
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)
        target_group = window.active_group() if group == -1 else group

        if sheet is None or not self._is_sheet_in_window(sheet, window):
            sheet = window.new_html_sheet(title, contents, group=target_group)
            self._sheets[key] = sheet
        else:
            sheet.set_name(title)
            sheet.set_contents(contents)
            current_group, _ = window.get_sheet_index(sheet)
            if current_group != target_group:
                window.set_sheet_index(sheet, target_group, -1)
            window.focus_sheet(sheet)
        self._sources[key] = (window, source_view)
        self._notify_after_render(window, source_view, source)
        return sheet

    def has_preview(self, window, source_view):
        """Return whether the source has an open preview in this window."""
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)
        if sheet is None:
            return False
        if not self._is_sheet_in_window(sheet, window):
            self._drop_association(key)
            return False
        return True

    def refresh_preview(self, window, source_view, region_factory):
        """Update an open preview in place without moving or focusing it."""
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)
        if sheet is None or not self._is_sheet_in_window(sheet, window):
            self._drop_association(key)
            return None

        source, title, contents = self._render_preview(
            window,
            source_view,
            region_factory,
        )
        sheet.set_name(title)
        sheet.set_contents(contents)
        self._notify_after_render(window, source_view, source)
        return sheet

    def refresh_all(self, region_factory):
        """Refresh every still-open preview after a settings or theme change."""
        refreshed = 0
        for window, source_view in list(self._sources.values()):
            if self.refresh_preview(window, source_view, region_factory) is not None:
                refreshed += 1
        return refreshed

    def apply_special_results(self, window, source_view, region_factory, results):
        """Apply completed special blocks without scheduling another render pass."""
        key = (window.id(), source_view.id())
        if not self.has_preview(window, source_view):
            return None
        self._special_results.setdefault(key, {}).update(results)
        return self._refresh_without_notification(
            window,
            source_view,
            region_factory,
        )

    def retain_special_results(
        self,
        window,
        source_view,
        renderer,
        active_keys,
    ):
        """Prune historical results for one renderer while preserving others."""
        key = (window.id(), source_view.id())
        results = self._special_results.get(key)
        if not results:
            return
        prefix = "{}:".format(renderer)
        stale_keys = [
            result_key
            for result_key in results
            if result_key.startswith(prefix) and result_key not in active_keys
        ]
        for result_key in stale_keys:
            results.pop(result_key, None)
        if not results:
            self._special_results.pop(key, None)

    def _refresh_without_notification(self, window, source_view, region_factory):
        key = (window.id(), source_view.id())
        sheet = self._sheets[key]
        _, title, contents = self._render_preview(window, source_view, region_factory)
        sheet.set_name(title)
        sheet.set_contents(contents)
        return sheet

    def _render_preview(self, window, source_view, region_factory):
        source = source_view.substr(region_factory(0, source_view.size()))
        source_name = source_view.name()
        if not source_name:
            file_name = source_view.file_name()
            source_name = os.path.basename(file_name) if file_name else "Untitled"
        key = (window.id(), source_view.id())
        return (
            source,
            "{} — Preview".format(source_name),
            self._render(
                source,
                source_path=source_view.file_name(),
                special_results=self._special_results.get(key),
            ),
        )

    def _notify_after_render(self, window, source_view, source):
        if self._after_render is not None:
            self._after_render(window, source_view, source)

    def _drop_association(self, key):
        self._sheets.pop(key, None)
        self._sources.pop(key, None)
        self._special_results.pop(key, None)

    @staticmethod
    def _is_sheet_in_window(sheet, window):
        owner = sheet.window()
        return owner is not None and owner.id() == window.id()
