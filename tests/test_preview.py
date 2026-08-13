import unittest

from markdown_reader.preview import PreviewManager


def make_region(start, end):
    return (start, end)


class FakeView:
    def __init__(self, view_id, name, text, file_name=None):
        self._view_id = view_id
        self._name = name
        self._file_name = file_name
        self.text = text
        self.requested_regions = []

    def id(self):
        return self._view_id

    def name(self):
        return self._name

    def file_name(self):
        return self._file_name

    def size(self):
        return len(self.text)

    def substr(self, region):
        self.requested_regions.append(region)
        start, end = region
        return self.text[start:end]


class FakeSheet:
    def __init__(self, owner, name, contents):
        self.owner = owner
        self.name = name
        self.contents = contents
        self.content_updates = []
        self.name_updates = []

    def window(self):
        return self.owner

    def set_name(self, name):
        self.name = name
        self.name_updates.append(name)

    def set_contents(self, contents):
        self.contents = contents
        self.content_updates.append(contents)


class FakeWindow:
    def __init__(self, window_id):
        self._window_id = window_id
        self.created_sheets = []
        self.focused_sheets = []

    def id(self):
        return self._window_id

    def new_html_sheet(self, name, contents):
        sheet = FakeSheet(self, name, contents)
        self.created_sheets.append(sheet)
        return sheet

    def focus_sheet(self, sheet):
        self.focused_sheets.append(sheet)


class PreviewManagerTests(unittest.TestCase):
    def setUp(self):
        self.rendered_sources = []

        def render(source):
            self.rendered_sources.append(source)
            return "<p>{}</p>".format(source)

        self.manager = PreviewManager(render)
        self.window = FakeWindow(11)
        self.view = FakeView(22, "notes.md", "first unsaved revision")

    def test_creates_html_sheet_from_current_unsaved_buffer(self):
        sheet = self.manager.open_preview(self.window, self.view, make_region)

        self.assertEqual(["first unsaved revision"], self.rendered_sources)
        self.assertEqual([(0, len(self.view.text))], self.view.requested_regions)
        self.assertEqual("notes.md — Preview", sheet.name)
        self.assertEqual("<p>first unsaved revision</p>", sheet.contents)
        self.assertEqual([sheet], self.window.created_sheets)

    def test_updates_existing_sheet_with_latest_buffer_revision(self):
        sheet = self.manager.open_preview(self.window, self.view, make_region)
        self.view.text = "second unsaved revision"

        updated_sheet = self.manager.open_preview(self.window, self.view, make_region)

        self.assertIs(sheet, updated_sheet)
        self.assertEqual(1, len(self.window.created_sheets))
        self.assertEqual(["<p>second unsaved revision</p>"], sheet.content_updates)
        self.assertEqual([sheet], self.window.focused_sheets)

    def test_recreates_preview_after_sheet_was_closed(self):
        closed_sheet = self.manager.open_preview(self.window, self.view, make_region)
        closed_sheet.owner = None

        replacement = self.manager.open_preview(self.window, self.view, make_region)

        self.assertIsNot(closed_sheet, replacement)
        self.assertEqual(2, len(self.window.created_sheets))
        self.assertEqual(
            ["first unsaved revision", "first unsaved revision"],
            self.rendered_sources,
        )

    def test_uses_untitled_name_when_source_has_no_name(self):
        view = FakeView(33, "", "draft")

        sheet = self.manager.open_preview(self.window, view, make_region)

        self.assertEqual("Untitled — Preview", sheet.name)

    def test_uses_file_basename_when_view_name_is_empty(self):
        view = FakeView(44, "", "saved", "/project/docs/guide.md")

        sheet = self.manager.open_preview(self.window, view, make_region)

        self.assertEqual("guide.md — Preview", sheet.name)


if __name__ == "__main__":
    unittest.main()
