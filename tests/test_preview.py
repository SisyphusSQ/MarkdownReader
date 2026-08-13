import unittest

from markdown_reader.mermaid import MermaidRenderResult
from markdown_reader.preview import PreviewManager, choose_side_by_side_group


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
    def __init__(self, owner, name, contents, group):
        self.owner = owner
        self.name = name
        self.contents = contents
        self.group = group
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
    def __init__(self, window_id, active_group=0, num_groups=1):
        self._window_id = window_id
        self._active_group = active_group
        self._num_groups = num_groups
        self.created_sheets = []
        self.focused_sheets = []
        self.layout_updates = []
        self.moved_sheets = []

    def id(self):
        return self._window_id

    def active_group(self):
        return self._active_group

    def num_groups(self):
        return self._num_groups

    def set_layout(self, layout):
        self.layout_updates.append(layout)
        self._num_groups = len(layout["cells"])

    def new_html_sheet(self, name, contents, group=-1):
        target_group = self._active_group if group == -1 else group
        sheet = FakeSheet(self, name, contents, target_group)
        self.created_sheets.append(sheet)
        return sheet

    def get_sheet_index(self, sheet):
        return (sheet.group, self.created_sheets.index(sheet))

    def set_sheet_index(self, sheet, group, index):
        sheet.group = group
        self.moved_sheets.append((sheet, group, index))

    def focus_sheet(self, sheet):
        self.focused_sheets.append(sheet)


class PreviewManagerTests(unittest.TestCase):
    def setUp(self):
        self.rendered_sources = []

        def render(source, source_path=None, special_results=None):
            self.rendered_sources.append((source, source_path, special_results or {}))
            return "<p>{}</p>".format(source)

        self.manager = PreviewManager(render)
        self.window = FakeWindow(11)
        self.view = FakeView(22, "notes.md", "first unsaved revision")

    def test_creates_html_sheet_from_current_unsaved_buffer(self):
        sheet = self.manager.open_preview(self.window, self.view, make_region)

        self.assertEqual(
            [("first unsaved revision", None, {})],
            self.rendered_sources,
        )
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
            [
                ("first unsaved revision", None, {}),
                ("first unsaved revision", None, {}),
            ],
            self.rendered_sources,
        )

    def test_creates_preview_in_requested_group(self):
        window = FakeWindow(11, num_groups=2)

        sheet = self.manager.open_preview(window, self.view, make_region, group=1)

        self.assertEqual(1, sheet.group)

    def test_moves_existing_preview_to_requested_group(self):
        window = FakeWindow(11, num_groups=2)
        sheet = self.manager.open_preview(window, self.view, make_region, group=0)

        updated_sheet = self.manager.open_preview(window, self.view, make_region, group=1)

        self.assertIs(sheet, updated_sheet)
        self.assertEqual(1, sheet.group)
        self.assertEqual([(sheet, 1, -1)], window.moved_sheets)
        self.assertEqual([sheet], window.focused_sheets)

    def test_refreshes_existing_preview_without_moving_or_focusing_it(self):
        window = FakeWindow(11, num_groups=2)
        sheet = self.manager.open_preview(window, self.view, make_region, group=1)
        self.view.text = "automatic refresh"

        refreshed_sheet = self.manager.refresh_preview(window, self.view, make_region)

        self.assertIs(sheet, refreshed_sheet)
        self.assertEqual(1, sheet.group)
        self.assertEqual(["<p>automatic refresh</p>"], sheet.content_updates)
        self.assertEqual([], window.moved_sheets)
        self.assertEqual([], window.focused_sheets)

    def test_does_not_recreate_closed_preview_during_refresh(self):
        sheet = self.manager.open_preview(self.window, self.view, make_region)
        self.manager._special_results[(self.window.id(), self.view.id())] = {
            "old": MermaidRenderResult.success("old-data")
        }
        sheet.owner = None

        refreshed_sheet = self.manager.refresh_preview(self.window, self.view, make_region)

        self.assertIsNone(refreshed_sheet)
        self.assertEqual(1, len(self.window.created_sheets))
        self.assertFalse(self.manager.has_preview(self.window, self.view))
        self.assertEqual({}, self.manager._special_results)

    def test_accepts_equivalent_window_wrapper_for_open_sheet(self):
        sheet = self.manager.open_preview(self.window, self.view, make_region)
        sheet.owner = FakeWindow(self.window.id())
        self.view.text = "wrapper-safe refresh"

        self.assertTrue(self.manager.has_preview(self.window, self.view))
        refreshed_sheet = self.manager.refresh_preview(self.window, self.view, make_region)

        self.assertIs(sheet, refreshed_sheet)
        self.assertEqual(["<p>wrapper-safe refresh</p>"], sheet.content_updates)

    def test_uses_untitled_name_when_source_has_no_name(self):
        view = FakeView(33, "", "draft")

        sheet = self.manager.open_preview(self.window, view, make_region)

        self.assertEqual("Untitled — Preview", sheet.name)

    def test_uses_file_basename_when_view_name_is_empty(self):
        view = FakeView(44, "", "saved", "/project/docs/guide.md")

        sheet = self.manager.open_preview(self.window, view, make_region)

        self.assertEqual("guide.md — Preview", sheet.name)
        self.assertEqual(
            [("saved", "/project/docs/guide.md", {})],
            self.rendered_sources,
        )

    def test_notifies_after_open_and_refresh_but_not_after_result_application(self):
        notifications = []
        self.manager.set_after_render(
            lambda window, view, source: notifications.append((window, view, source))
        )
        sheet = self.manager.open_preview(self.window, self.view, make_region)

        self.view.text = "second unsaved revision"
        self.manager.refresh_preview(self.window, self.view, make_region)
        self.manager.apply_special_results(
            self.window,
            self.view,
            make_region,
            {"diagram": MermaidRenderResult.success("png-data")},
        )

        self.assertEqual(
            [
                (self.window, self.view, "first unsaved revision"),
                (self.window, self.view, "second unsaved revision"),
            ],
            notifications,
        )
        self.assertEqual(
            {"diagram": MermaidRenderResult.success("png-data")},
            self.rendered_sources[-1][2],
        )
        self.assertEqual(2, len(sheet.content_updates))


class SideBySideGroupTests(unittest.TestCase):
    def test_single_group_becomes_two_equal_columns(self):
        window = FakeWindow(11)

        target_group = choose_side_by_side_group(window)

        self.assertEqual(1, target_group)
        self.assertEqual(
            [
                {
                    "cols": [0.0, 0.5, 1.0],
                    "rows": [0.0, 1.0],
                    "cells": [[0, 0, 1, 1], [1, 0, 2, 1]],
                }
            ],
            window.layout_updates,
        )

    def test_existing_layout_is_preserved_and_next_group_is_used(self):
        window = FakeWindow(11, active_group=1, num_groups=3)

        target_group = choose_side_by_side_group(window)

        self.assertEqual(2, target_group)
        self.assertEqual([], window.layout_updates)

    def test_last_existing_group_uses_previous_group(self):
        window = FakeWindow(11, active_group=2, num_groups=3)

        target_group = choose_side_by_side_group(window)

        self.assertEqual(1, target_group)
        self.assertEqual([], window.layout_updates)


if __name__ == "__main__":
    unittest.main()
