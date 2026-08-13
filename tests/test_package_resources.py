import json
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class CommandPaletteResourceTests(unittest.TestCase):
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
