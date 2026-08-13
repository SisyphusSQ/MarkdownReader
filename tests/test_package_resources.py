import json
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class CommandPaletteResourceTests(unittest.TestCase):
    def test_single_dollar_math_is_disabled_in_default_settings(self):
        settings = (PACKAGE_ROOT / "MarkdownReader.sublime-settings").read_text(
            encoding="utf-8"
        )

        self.assertIn('"math_single_dollar": false', settings)

    def test_package_settings_menu_opens_markdown_reader_settings(self):
        menu = json.loads(
            (PACKAGE_ROOT / "Main.sublime-menu").read_text(encoding="utf-8")
        )
        settings_entry = menu[0]["children"][0]["children"][0]["children"][0]

        self.assertEqual("Settings", settings_entry["caption"])
        self.assertEqual("edit_settings", settings_entry["command"])
        self.assertEqual(
            "${packages}/MarkdownReader/MarkdownReader.sublime-settings",
            settings_entry["args"]["base_file"],
        )

    def test_exposes_current_group_and_side_by_side_commands(self):
        resource = PACKAGE_ROOT / "Default.sublime-commands"

        commands = json.loads(resource.read_text(encoding="utf-8"))

        self.assertIn(
            {
                "caption": "MarkdownReader: Open Preview",
                "command": "markdown_reader_open_preview",
            },
            commands,
        )
        self.assertIn(
            {
                "caption": "MarkdownReader: Check Renderer Environment",
                "command": "markdown_reader_check_renderer_environment",
            },
            commands,
        )
        self.assertIn(
            {
                "caption": "MarkdownReader: Open Preview Side by Side",
                "command": "markdown_reader_open_preview_side_by_side",
            },
            commands,
        )


if __name__ == "__main__":
    unittest.main()
