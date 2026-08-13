import unittest

from markdown_reader.renderer_environment import RendererEnvironmentDetector


class RendererEnvironmentDetectorTests(unittest.TestCase):
    def test_reports_ready_environment(self):
        detector = RendererEnvironmentDetector(
            which=lambda name: "/tools/node" if name == "node" else None,
            is_executable=lambda path: path in {"/tools/node", "/apps/chrome"},
            chrome_candidates=lambda: ["/apps/chrome"],
        )

        environment = detector.detect()

        self.assertTrue(environment.ready)
        self.assertEqual("/tools/node", environment.node_path)
        self.assertEqual("/apps/chrome", environment.chrome_path)
        self.assertEqual([], environment.problems)

    def test_reports_actionable_missing_tools(self):
        detector = RendererEnvironmentDetector(
            which=lambda name: None,
            is_executable=lambda path: False,
            chrome_candidates=lambda: [],
        )

        environment = detector.detect()

        self.assertFalse(environment.ready)
        self.assertIn("Node.js executable was not found", environment.problems)
        self.assertIn("Chrome or Chromium executable was not found", environment.problems)


if __name__ == "__main__":
    unittest.main()
