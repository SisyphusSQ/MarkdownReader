import unittest

from markdown_reader.renderer_environment import RendererEnvironment
from markdown_reader.settings import read_settings


class DiagnosticsFormattingTests(unittest.TestCase):
    def test_ready_report_includes_effective_settings_and_renderer_versions(self):
        try:
            from markdown_reader.diagnostics import format_diagnostics
        except ImportError as error:
            self.fail("diagnostics formatter is not implemented: {}".format(error))

        settings = read_settings(
            {
                "refresh_delay_ms": 400,
                "remote_images": "allow_https",
                "math_single_dollar": True,
                "node_path": "/tools/node",
                "chrome_path": "/apps/chrome",
            }
        )
        environment = RendererEnvironment(
            node_path="/tools/node",
            node_version="22.22.2",
            chrome_path="/apps/chrome",
            problems=[],
        )
        ping = {
            "protocolVersion": 3,
            "mermaidVersion": "11.16.1",
            "mathJaxVersion": "4.1.3",
            "puppeteerVersion": "25.6.0",
        }

        report = format_diagnostics(settings, environment, ping=ping)

        self.assertIn("Renderer: READY", report)
        self.assertIn("Refresh delay: 400 ms", report)
        self.assertIn("Remote images: HTTPS opt-in enabled", report)
        self.assertIn("Single-dollar math: enabled", report)
        self.assertIn("Node: /tools/node (22.22.2)", report)
        self.assertIn("Chrome: /apps/chrome", report)
        self.assertIn("Protocol: 3", report)
        self.assertIn("Mermaid: 11.16.1", report)
        self.assertIn("MathJax: 4.1.3", report)
        self.assertIn("Puppeteer: 25.6.0", report)
        self.assertIn("Browser preview: bundled offline runtime", report)

    def test_not_ready_report_preserves_environment_problems_and_warnings(self):
        from markdown_reader.diagnostics import format_diagnostics

        settings = read_settings({"refresh_delay_ms": 1, "remote_images": "always"})
        environment = RendererEnvironment(
            node_path="",
            node_version="",
            chrome_path="",
            problems=[
                "Node.js executable was not found",
                "Chrome or Chromium executable was not found",
            ],
        )

        report = format_diagnostics(settings, environment)

        self.assertIn("Renderer: NOT READY", report)
        self.assertIn("Problems:", report)
        self.assertIn("- Node.js executable was not found", report)
        self.assertIn("- Chrome or Chromium executable was not found", report)
        self.assertIn("Settings warnings:", report)
        self.assertIn("refresh_delay_ms", report)
        self.assertIn("remote_images", report)
