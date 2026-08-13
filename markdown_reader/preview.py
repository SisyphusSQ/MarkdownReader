"""Manage native preview sheets independently of the Sublime import boundary."""

import os


class PreviewManager:
    """Create or update one preview sheet per source view in a window."""

    def __init__(self, render):
        self._render = render
        self._sheets = {}

    def open_preview(self, window, source_view, region_factory):
        """Render the source's current buffer and focus its preview sheet."""
        source = source_view.substr(region_factory(0, source_view.size()))
        contents = self._render(source)
        source_name = source_view.name()
        if not source_name:
            file_name = source_view.file_name()
            source_name = os.path.basename(file_name) if file_name else "Untitled"
        title = "{} — Preview".format(source_name)
        key = (window.id(), source_view.id())
        sheet = self._sheets.get(key)

        if sheet is None or sheet.window() is None:
            sheet = window.new_html_sheet(title, contents)
            self._sheets[key] = sheet
            return sheet

        sheet.set_name(title)
        sheet.set_contents(contents)
        window.focus_sheet(sheet)
        return sheet
