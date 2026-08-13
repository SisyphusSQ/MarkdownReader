import unittest

from markdown_reader.rendering import render_markdown


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

    def test_keeps_links_inert_until_link_support_is_enabled(self):
        html = render_markdown("Read [the guide](https://example.com).")

        self.assertIn("Read the guide.", html)
        self.assertNotIn("<a ", html)
        self.assertNotIn("https://example.com", html)

    def test_escapes_raw_html(self):
        html = render_markdown('<script>alert("unsafe")</script>')

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
