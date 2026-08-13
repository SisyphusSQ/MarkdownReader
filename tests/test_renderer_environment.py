import unittest

from markdown_reader.renderer_environment import RendererEnvironmentDetector


class RendererEnvironmentDetectorTests(unittest.TestCase):
    def test_reports_ready_environment(self):
        detector = RendererEnvironmentDetector(
            which=lambda name: "/tools/node" if name == "node" else None,
            is_executable=lambda path: path in {"/tools/node", "/apps/chrome"},
            chrome_candidates=lambda: ["/apps/chrome"],
            read_node_version=lambda _path: "v22.22.2",
        )

        environment = detector.detect()

        self.assertTrue(environment.ready)
        self.assertEqual("/tools/node", environment.node_path)
        self.assertEqual("22.22.2", environment.node_version)
        self.assertEqual("/apps/chrome", environment.chrome_path)
        self.assertEqual([], environment.problems)

    def test_reports_actionable_missing_tools(self):
        detector = RendererEnvironmentDetector(
            which=lambda name: None,
            is_executable=lambda path: False,
            chrome_candidates=lambda: [],
            read_node_version=lambda _path: "",
        )

        environment = detector.detect()

        self.assertFalse(environment.ready)
        self.assertIn("Node.js executable was not found", environment.problems)
        self.assertIn("Chrome or Chromium executable was not found", environment.problems)

    def test_rejects_node_older_than_the_bundled_renderer_requires(self):
        detector = RendererEnvironmentDetector(
            which=lambda name: "/tools/node" if name == "node" else None,
            is_executable=lambda path: path in {"/tools/node", "/apps/chrome"},
            chrome_candidates=lambda: ["/apps/chrome"],
            read_node_version=lambda _path: "v20.19.0",
        )

        environment = detector.detect()

        self.assertFalse(environment.ready)
        self.assertIn(
            "Node.js 22.12 or newer is required; found 20.19.0",
            environment.problems,
        )

    def test_configured_paths_take_precedence_over_auto_discovery(self):
        detector = RendererEnvironmentDetector(
            configured_node_path="/configured/node",
            configured_chrome_path="/configured/chrome",
            which=lambda _name: "/auto/tool",
            is_executable=lambda path: path in {
                "/configured/node",
                "/configured/chrome",
                "/auto/tool",
            },
            chrome_candidates=lambda: ["/auto/chrome"],
            read_node_version=lambda path: (
                "v22.22.2" if path == "/configured/node" else "v20.0.0"
            ),
        )

        environment = detector.detect()

        self.assertTrue(environment.ready)
        self.assertEqual("/configured/node", environment.node_path)
        self.assertEqual("/configured/chrome", environment.chrome_path)

    def test_invalid_configured_paths_are_not_silently_replaced(self):
        detector = RendererEnvironmentDetector(
            configured_node_path="/missing/node",
            configured_chrome_path="/missing/chrome",
            which=lambda _name: "/auto/tool",
            is_executable=lambda path: path == "/auto/tool",
            chrome_candidates=lambda: ["/auto/tool"],
            read_node_version=lambda _path: "v22.22.2",
        )

        environment = detector.detect()

        self.assertFalse(environment.ready)
        self.assertEqual("", environment.node_path)
        self.assertEqual("", environment.chrome_path)
        self.assertIn(
            "Configured Node.js executable is not executable: /missing/node",
            environment.problems,
        )
        self.assertIn(
            "Configured Chrome executable is not executable: /missing/chrome",
            environment.problems,
        )


if __name__ == "__main__":
    unittest.main()
