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

    def open_preview(self, window, source_view, region_factory, group=-1):
        """Render the source's current buffer and focus its preview sheet."""
        title, contents = self._render_preview(source_view, region_factory)
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)
        target_group = window.active_group() if group == -1 else group

        if sheet is None or not self._is_sheet_in_window(sheet, window):
            sheet = window.new_html_sheet(title, contents, group=target_group)
            self._sheets[key] = sheet
            return sheet

        sheet.set_name(title)
        sheet.set_contents(contents)
        current_group, _ = window.get_sheet_index(sheet)
        if current_group != target_group:
            window.set_sheet_index(sheet, target_group, -1)
        window.focus_sheet(sheet)
        return sheet

    def has_preview(self, window, source_view):
        """Return whether the source has an open preview in this window."""
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)
        if sheet is None:
            return False
        if not self._is_sheet_in_window(sheet, window):
            self._sheets.pop(key, None)
            return False
        return True

    def refresh_preview(self, window, source_view, region_factory):
        """Update an open preview in place without moving or focusing it."""
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)
        if sheet is None or not self._is_sheet_in_window(sheet, window):
            self._sheets.pop(key, None)
            return None

        title, contents = self._render_preview(source_view, region_factory)
        sheet.set_name(title)
        sheet.set_contents(contents)
        return sheet

    def _render_preview(self, source_view, region_factory):
        source = source_view.substr(region_factory(0, source_view.size()))
        source_name = source_view.name()
        if not source_name:
            file_name = source_view.file_name()
            source_name = os.path.basename(file_name) if file_name else "Untitled"
        return "{} — Preview".format(source_name), self._render(
            source,
            source_path=source_view.file_name(),
        )

    @staticmethod
    def _is_sheet_in_window(sheet, window):
        owner = sheet.window()
        return owner is not None and owner.id() == window.id()
