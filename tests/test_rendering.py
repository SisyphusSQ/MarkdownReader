import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from markdown_reader.rendering import render_markdown
from markdown_reader.security import SecurityPolicy


class MarkdownRenderingTests(unittest.TestCase):
    def test_wraps_output_as_theme_aware_minihtml_document(self):
        html = render_markdown("Hello")

        self.assertIn('<body id="markdown-reader-preview">', html)
        self.assertIn("var(--foreground)", html)
        self.assertIn("var(--background)", html)
        self.assertIn("<p>Hello</p>", html)

    def test_renders_headings_paragraphs_emphasis_and_quotes(self):
        source = """# Reader

Paragraph with *emphasis* and **strong text**.

> Quoted text
"""

        html = render_markdown(source)

        self.assertIn("<h1>Reader</h1>", html)
        self.assertIn("<em>emphasis</em>", html)
        self.assertIn("<strong>strong text</strong>", html)
        self.assertIn("<p>Quoted text</p>", html)

    def test_renders_unordered_and_ordered_lists(self):
        source = """- first
- second

1. one
2. two
"""

        html = render_markdown(source)

        self.assertIn("<ul>", html)
        self.assertIn("<li>first</li>", html)
        self.assertIn("<li>second</li>", html)
        self.assertIn('<div class="ordered-list">', html)
        self.assertIn('<strong class="ordered-marker">1.</strong> one', html)
        self.assertIn('<strong class="ordered-marker">2.</strong> two', html)

    def test_uses_minihtml_supported_container_for_block_quote(self):
        html = render_markdown("> Quoted text")

        self.assertIn('<div class="blockquote">', html)
        self.assertIn("<p>Quoted text</p>", html)
        self.assertNotIn("<blockquote>", html)

    def test_renders_fenced_code_as_escaped_preformatted_text(self):
        source = """```python
if value < 10:
    print("ok")
```
"""

        html = render_markdown(source)

        self.assertIn('<div class="code-block"><code class="language-python">', html)
        self.assertIn("if value &lt; 10:", html)
        self.assertIn('print(&quot;ok&quot;)', html)
        self.assertIn("white-space: pre-wrap", html)
        self.assertNotIn("<pre>", html)

    def test_activates_http_and_https_links(self):
        html = render_markdown(
            "Read [HTTP](http://example.com/a?b=1&c=2) and "
            '[HTTPS](https://example.com/guide "Guide").'
        )

        self.assertIn('<a href="http://example.com/a?b=1&amp;c=2">HTTP</a>', html)
        self.assertIn(
            '<a href="https://example.com/guide" title="Guide">HTTPS</a>',
            html,
        )

    def test_keeps_non_http_links_inert(self):
        html = render_markdown(
            "Read [local](guide.md), [mail](mailto:reader@example.com), and "
            "[command](subl:save)."
        )

        self.assertIn("Read local, mail, and command.", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("subl:save", html)

    def test_renders_task_lists_with_static_markers(self):
        html = render_markdown(
            "- [ ] draft\n- [x] shipped\n- [X] verified\n- regular item\n\n"
            "1. [ ] ordered task\n2. [x] ordered done\n"
        )

        self.assertIn('<div class="task-list">', html)
        self.assertIn('<strong class="task-marker">☐</strong> draft', html)
        self.assertIn('<strong class="task-marker">☑</strong> shipped', html)
        self.assertIn('<strong class="task-marker">☑</strong> verified', html)
        self.assertIn('<strong class="task-marker">•</strong> regular item', html)
        self.assertIn(
            '<strong class="ordered-marker">1.</strong> '
            '<strong class="task-marker">☐</strong> ordered task',
            html,
        )
        self.assertIn(
            '<strong class="ordered-marker">2.</strong> '
            '<strong class="task-marker">☑</strong> ordered done',
            html,
        )
        self.assertNotIn("<input", html)

    def test_renders_existing_local_image_as_encoded_file_url(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "notes.md"
            image_path = root / "assets" / "diagram one.PNG"
            image_path.parent.mkdir()
            image_path.touch()

            html = render_markdown(
                '![System diagram](assets/diagram%20one.PNG "Overview")',
                source_path=str(source_path),
            )

        self.assertIn('<img class="local-image"', html)
        self.assertIn(image_path.resolve().as_uri(), html)
        self.assertIn('alt="System diagram"', html)
        self.assertIn('title="Overview"', html)

    def test_blocks_remote_missing_and_unsupported_images(self):
        with TemporaryDirectory() as directory:
            source_path = str(Path(directory) / "notes.md")

            html = render_markdown(
                "![remote](https://example.com/image.png)\n\n"
                "![missing](missing.png)\n\n"
                "![vector](diagram.svg)",
                source_path=source_path,
            )

        self.assertNotIn("<img", html)
        self.assertNotIn("https://example.com", html)
        self.assertIn("remote images are blocked", html)
        self.assertIn("local image not found", html)
        self.assertIn("unsupported image format", html)

    def test_relative_image_in_unsaved_buffer_has_placeholder(self):
        html = render_markdown("![draft](diagram.png)")

        self.assertNotIn("<img", html)
        self.assertIn("save the Markdown file to resolve this image", html)

    def test_oversized_source_returns_fixed_diagnostic_without_parsing(self):
        source = "# must not render"

        html = render_markdown(source, policy=SecurityPolicy(max_source_bytes=4))

        self.assertIn('<div class="security-error">', html)
        self.assertIn("Markdown source exceeds the 4-byte preview limit", html)
        self.assertNotIn("<h1>", html)
        self.assertNotIn("must not render", html)

    def test_escapes_raw_html(self):
        html = render_markdown('<script>alert("unsafe")</script>')

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
