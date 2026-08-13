import unittest


class MarkdownReaderSettingsTests(unittest.TestCase):
    def test_uses_safe_documented_defaults(self):
        try:
            from markdown_reader.settings import read_settings
        except ImportError as error:
            self.fail("settings parser is not implemented: {}".format(error))

        settings = read_settings({})

        self.assertEqual(250, settings.refresh_delay_ms)
        self.assertEqual("blocked", settings.remote_images)
        self.assertFalse(settings.math_single_dollar)
        self.assertEqual("", settings.node_path)
        self.assertEqual("", settings.chrome_path)
        self.assertEqual((), settings.warnings)

    def test_accepts_each_supported_setting(self):
        from markdown_reader.settings import read_settings

        settings = read_settings(
            {
                "refresh_delay_ms": 600,
                "remote_images": "allow_https",
                "math_single_dollar": True,
                "node_path": "/tools/node",
                "chrome_path": "/apps/chrome",
            }
        )

        self.assertEqual(600, settings.refresh_delay_ms)
        self.assertEqual("allow_https", settings.remote_images)
        self.assertTrue(settings.math_single_dollar)
        self.assertEqual("/tools/node", settings.node_path)
        self.assertEqual("/apps/chrome", settings.chrome_path)
        self.assertEqual((), settings.warnings)

    def test_invalid_values_fall_back_and_become_diagnostic_warnings(self):
        from markdown_reader.settings import read_settings

        settings = read_settings(
            {
                "refresh_delay_ms": True,
                "remote_images": "always",
                "math_single_dollar": "yes",
                "node_path": 22,
                "chrome_path": ["chrome"],
            }
        )

        self.assertEqual(250, settings.refresh_delay_ms)
        self.assertEqual("blocked", settings.remote_images)
        self.assertFalse(settings.math_single_dollar)
        self.assertEqual("", settings.node_path)
        self.assertEqual("", settings.chrome_path)
        self.assertEqual(5, len(settings.warnings))
        self.assertTrue(any("refresh_delay_ms" in warning for warning in settings.warnings))
        self.assertTrue(any("remote_images" in warning for warning in settings.warnings))

    def test_relative_tool_paths_fall_back_to_auto_detection(self):
        from markdown_reader.settings import read_settings

        settings = read_settings(
            {
                "node_path": "bin/node",
                "chrome_path": "apps/chrome",
            }
        )

        self.assertEqual("", settings.node_path)
        self.assertEqual("", settings.chrome_path)
        self.assertEqual(2, len(settings.warnings))
        self.assertTrue(all("absolute path" in warning for warning in settings.warnings))


if __name__ == "__main__":
    unittest.main()
