import base64
import json
import tempfile
import unittest
from pathlib import Path


class BrowserPreviewRenderingTests(unittest.TestCase):
    def test_builds_a_self_contained_offline_document(self):
        try:
            from markdown_reader.browser_preview import render_browser_preview
        except ImportError as error:
            self.fail("browser preview renderer is not implemented: {}".format(error))

        runtime = "globalThis.__previewReady = true;"
        html = render_browser_preview("# Offline", runtime_script=runtime)

        encoded_runtime = base64.b64encode(runtime.encode("utf-8")).decode("ascii")
        self.assertIn("<h1>Offline</h1>", html)
        self.assertIn("default-src 'none'", html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn("img-src data:", html)
        self.assertIn(
            'src="data:text/javascript;base64,{}"'.format(encoded_runtime),
            html,
        )

    def test_keeps_untrusted_html_and_dangerous_links_inert(self):
        from markdown_reader.browser_preview import render_browser_preview

        source = (
            "<script>alert('unsafe')</script>\n\n"
            "[command](subl:run_command) "
            "[website](https://example.com/docs)"
        )
        html = render_browser_preview(source, runtime_script="")

        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;alert", html)
        self.assertNotIn('href="subl:', html)
        self.assertIn('<meta name="referrer" content="no-referrer">', html)
        self.assertIn(
            '<a href="https://example.com/docs" target="_blank" '
            'rel="noopener noreferrer" referrerpolicy="no-referrer">website</a>',
            html,
        )

    def test_embeds_allowed_local_images_without_exposing_file_paths(self):
        from markdown_reader.browser_preview import render_browser_preview

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "assets" / "pixel.png"
            image.parent.mkdir()
            image_bytes = b"\x89PNG\r\n\x1a\npreview"
            image.write_bytes(image_bytes)

            html = render_browser_preview(
                "![pixel](assets/pixel.png)",
                runtime_script="",
                source_path=str(root / "notes.md"),
            )

        encoded = base64.b64encode(image_bytes).decode("ascii")
        self.assertIn('src="data:image/png;base64,{}"'.format(encoded), html)
        self.assertNotIn(str(image), html)
        self.assertNotIn("file://", html)

    def test_bounds_the_total_bytes_embedded_from_local_images(self):
        from markdown_reader.browser_preview import render_browser_preview

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.png").write_bytes(b"1234")
            (root / "two.png").write_bytes(b"5678")
            try:
                html = render_browser_preview(
                    "![one](one.png)\n\n![two](two.png)",
                    runtime_script="",
                    source_path=str(root / "notes.md"),
                    max_embedded_image_bytes=6,
                )
            except TypeError as error:
                self.fail("browser preview image budget is not implemented: {}".format(error))

        self.assertEqual(1, html.count("data:image/png;base64,"))
        self.assertIn("browser preview embedded-image limit", html)

    def test_emits_inert_mermaid_and_math_definitions_for_the_runtime(self):
        from markdown_reader.browser_preview import render_browser_preview

        source = (
            "```mermaid\nflowchart LR\n  A[<unsafe>] --> B\n```\n\n"
            r"Inline \(x+1\)."
            "\n\n$$\ny^2\n$$\n"
        )
        html = render_browser_preview(source, runtime_script="runtime")

        self.assertEqual(1, html.count('class="interactive-mermaid"'))
        self.assertIn('class="mermaid-target"', html)
        self.assertIn('class="mermaid-definition" hidden', html)
        self.assertIn("A[&lt;unsafe&gt;]", html)
        self.assertIn('data-action="zoom-in"', html)
        self.assertIn('data-action="zoom-out"', html)
        self.assertIn('data-action="reset"', html)
        self.assertIn("<summary>Mermaid source</summary>", html)
        self.assertEqual(1, html.count('class="math-expression inline-math"'))
        self.assertEqual(1, html.count('class="math-expression display-math"'))
        self.assertIn('class="math-target"', html)
        self.assertIn('class="math-definition" hidden', html)

    def test_single_dollar_math_remains_opt_in(self):
        from markdown_reader.browser_preview import render_browser_preview

        default_html = render_browser_preview(
            "Price $10$",
            runtime_script="",
        )
        try:
            enabled_html = render_browser_preview(
                "Formula $x+1$",
                runtime_script="",
                allow_single_dollar_math=True,
            )
        except TypeError as error:
            self.fail("single-dollar browser setting is not implemented: {}".format(error))

        self.assertNotIn('class="math-expression', default_html)
        self.assertIn('class="math-expression inline-math"', enabled_html)
        self.assertIn(">x+1</code>", enabled_html)

    def test_rejects_oversized_markdown_before_parsing(self):
        from markdown_reader.browser_preview import render_browser_preview
        from markdown_reader.security import SecurityPolicy

        html = render_browser_preview(
            "# Too long",
            runtime_script="",
            policy=SecurityPolicy(max_source_bytes=4),
        )

        self.assertIn("Markdown source exceeds the 4-byte preview limit", html)
        self.assertNotIn("<h1>Too long</h1>", html)

    def test_exposes_theme_title_and_print_export_controls(self):
        from markdown_reader.browser_preview import render_browser_preview

        try:
            html = render_browser_preview(
                "Document",
                runtime_script="",
                title="Notes <draft>",
                theme="dark",
            )
        except TypeError as error:
            self.fail("browser preview document chrome is not implemented: {}".format(error))

        self.assertIn('<html lang="en" data-theme="dark">', html)
        self.assertIn("<title>Notes &lt;draft&gt; — MarkdownReader Preview</title>", html)
        self.assertIn('class="preview-toolbar"', html)
        self.assertIn('data-action="print"', html)
        self.assertIn("Print / Save as PDF", html)
        self.assertIn("@media print", html)
        self.assertIn(".preview-toolbar { display: none; }", html)


class BrowserPreviewFilesTests(unittest.TestCase):
    def test_prunes_legacy_and_dead_process_directories_only(self):
        try:
            from markdown_reader.browser_preview import (
                cleanup_stale_browser_preview_directories,
            )
        except ImportError as error:
            self.fail("stale browser-preview cleanup is not implemented: {}".format(error))

        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)
            legacy = root / "markdown-reader-browser-legacy"
            dead = root / "markdown-reader-browser-424242-dead"
            live = root / "markdown-reader-browser-123-live"
            current = root / "markdown-reader-browser-999-current"
            unrelated = root / "another-application"
            for directory in (legacy, dead, live, current, unrelated):
                directory.mkdir()
                (directory / "preview.html").write_text("private", encoding="utf-8")

            removed = cleanup_stale_browser_preview_directories(
                directory=root,
                current_process_id=999,
                is_process_alive=lambda process_id: process_id == 123,
            )

            self.assertEqual(2, removed)
            self.assertFalse(legacy.exists())
            self.assertFalse(dead.exists())
            self.assertTrue(live.exists())
            self.assertTrue(current.exists())
            self.assertTrue(unrelated.exists())

    def test_reuses_one_private_artifact_per_view_and_cleans_the_session(self):
        try:
            from markdown_reader.browser_preview import BrowserPreviewFiles
        except ImportError as error:
            self.fail("browser preview file lifecycle is not implemented: {}".format(error))

        with tempfile.TemporaryDirectory() as parent:
            session_directory = Path(parent) / "browser-session"
            files = BrowserPreviewFiles(directory=session_directory)

            first = files.write(window_id=7, view_id=11, html="first")
            second = files.write(window_id=7, view_id=11, html="second")

            self.assertEqual(first, second)
            self.assertEqual("second", second.read_text(encoding="utf-8"))
            self.assertEqual([second], list(session_directory.iterdir()))
            files.cleanup()
            self.assertFalse(session_directory.exists())

    def test_old_expiry_cannot_remove_a_newer_snapshot_for_the_same_view(self):
        from markdown_reader.browser_preview import BrowserPreviewFiles

        scheduled = []
        with tempfile.TemporaryDirectory() as parent:
            session_directory = Path(parent) / "browser-session"
            files = BrowserPreviewFiles(directory=session_directory)
            first = files.write(window_id=7, view_id=11, html="first")
            files.schedule_cleanup(
                first,
                lambda callback, _delay_ms: scheduled.append(callback),
                10_000,
            )
            second = files.write(window_id=7, view_id=11, html="second")

            scheduled[0]()

            self.assertEqual(first, second)
            self.assertTrue(second.is_file())
            self.assertEqual("second", second.read_text(encoding="utf-8"))
            files.cleanup()


class BrowserPreviewServiceTests(unittest.TestCase):
    def test_writes_the_real_document_and_opens_its_file_uri(self):
        try:
            from markdown_reader.browser_preview import (
                BrowserPreviewFiles,
                BrowserPreviewService,
            )
        except ImportError as error:
            self.fail("browser preview service is not implemented: {}".format(error))

        opened = []
        with tempfile.TemporaryDirectory() as parent:
            files = BrowserPreviewFiles(directory=Path(parent) / "session")
            service = BrowserPreviewService(
                runtime_loader=lambda: "globalThis.runtimeLoaded = true;",
                files=files,
                opener=lambda uri: opened.append(uri) or True,
            )

            artifact = service.open(
                window_id=3,
                view_id=5,
                source="# Browser",
                source_path=None,
                title="Browser notes",
                theme="light",
                allow_single_dollar_math=False,
            )

            self.assertTrue(artifact.is_file())
            self.assertEqual([artifact.as_uri()], opened)
            document = artifact.read_text(encoding="utf-8")
            self.assertIn("<h1>Browser</h1>", document)
            self.assertIn("Browser notes — MarkdownReader Preview", document)
            files.cleanup()

    def test_reports_when_the_system_browser_cannot_be_opened(self):
        from markdown_reader.browser_preview import (
            BrowserPreviewFiles,
            BrowserPreviewService,
        )

        with tempfile.TemporaryDirectory() as parent:
            files = BrowserPreviewFiles(directory=Path(parent) / "session")
            service = BrowserPreviewService(
                runtime_loader=lambda: "runtime",
                files=files,
                opener=lambda _uri: False,
            )

            with self.assertRaisesRegex(RuntimeError, "default browser could not be opened"):
                service.open(
                    window_id=3,
                    view_id=5,
                    source="Browser",
                    source_path=None,
                    title="Browser notes",
                    theme="light",
                    allow_single_dollar_math=False,
                )
            self.assertFalse((Path(parent) / "session").exists())

    def test_open_schedules_ephemeral_artifact_removal(self):
        from markdown_reader.browser_preview import (
            BrowserPreviewFiles,
            BrowserPreviewService,
        )

        scheduled = []
        with tempfile.TemporaryDirectory() as parent:
            session_directory = Path(parent) / "session"
            service = BrowserPreviewService(
                runtime_loader=lambda: "runtime",
                files=BrowserPreviewFiles(directory=session_directory),
                opener=lambda _uri: True,
                schedule_cleanup=lambda callback, delay_ms: scheduled.append(
                    (callback, delay_ms)
                ),
                cleanup_delay_ms=10_000,
            )

            artifact = service.open(
                window_id=3,
                view_id=5,
                source="Browser",
                source_path=None,
                title="Browser notes",
                theme="light",
                allow_single_dollar_math=False,
            )

            self.assertTrue(artifact.is_file())
            self.assertEqual(1, len(scheduled))
            self.assertEqual(10_000, scheduled[0][1])
            scheduled[0][0]()
            self.assertFalse(artifact.exists())
            self.assertFalse(session_directory.exists())

    def test_close_cleans_artifacts_and_prevents_post_unload_recreation(self):
        from markdown_reader.browser_preview import (
            BrowserPreviewFiles,
            BrowserPreviewService,
        )

        with tempfile.TemporaryDirectory() as parent:
            session_directory = Path(parent) / "session"
            service = BrowserPreviewService(
                runtime_loader=lambda: "runtime",
                files=BrowserPreviewFiles(directory=session_directory),
                opener=lambda _uri: True,
            )
            arguments = {
                "window_id": 3,
                "view_id": 5,
                "source": "Browser",
                "source_path": None,
                "title": "Browser notes",
                "theme": "light",
                "allow_single_dollar_math": False,
            }
            service.open(**arguments)

            try:
                service.close()
            except AttributeError as error:
                self.fail("browser preview service lifecycle is not implemented: {}".format(error))

            self.assertFalse(session_directory.exists())
            with self.assertRaisesRegex(RuntimeError, "browser preview service is closed"):
                service.open(**arguments)
            self.assertFalse(session_directory.exists())


class BrowserPreviewCommandTests(unittest.TestCase):
    def test_command_palette_exposes_the_full_browser_preview(self):
        commands_path = Path(__file__).resolve().parents[1] / "Default.sublime-commands"
        commands = json.loads(commands_path.read_text(encoding="utf-8"))

        matching = [
            command
            for command in commands
            if command.get("command") == "markdown_reader_open_full_preview_in_browser"
        ]

        self.assertEqual(
            [
                {
                    "caption": "MarkdownReader: Open Full Preview in Browser",
                    "command": "markdown_reader_open_full_preview_in_browser",
                }
            ],
            matching,
        )


if __name__ == "__main__":
    unittest.main()
