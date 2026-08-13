"""Convert Markdown into a self-contained minihtml document."""

from .vendor.mistune import create_markdown
from .vendor.mistune.renderers.html import HTMLRenderer
from .vendor.mistune.util import escape


class MinihtmlRenderer(HTMLRenderer):
    """Render only the inert Markdown subset supported by the first release slice."""

    def render_token(self, token, state):
        """Render ordered lists with explicit markers minihtml can display."""
        attrs = token.get("attrs") or {}
        if token["type"] == "list" and attrs.get("ordered"):
            return self._render_ordered_list(token, state)
        return super().render_token(token, state)

    def _render_ordered_list(self, token, state):
        attrs = token.get("attrs") or {}
        start = attrs.get("start", 1)
        items = ['<div class="ordered-list">\n']
        for number, item in enumerate(token.get("children", ()), start):
            contents = self.render_tokens(item.get("children", ()), state)
            items.append(
                '<div class="ordered-list-item">'
                '<strong class="ordered-marker">{}.</strong> {}</div>\n'.format(
                    number,
                    contents,
                )
            )
        items.append("</div>\n")
        return "".join(items)

    def link(self, text, url, title=None):
        """Keep link text selectable without activating navigation yet."""
        return text

    def image(self, text, url, title=None):
        """Keep image alt text visible without loading a resource yet."""
        return text

    def block_quote(self, text):
        """Use a supported block container instead of the unsupported tag."""
        return '<div class="blockquote">\n' + text + "</div>\n"

    def block_code(self, code, info=None):
        """Preserve code whitespace using minihtml-supported CSS."""
        language_class = ""
        if info:
            language = info.strip().split(None, 1)[0]
            if language:
                language_class = ' class="language-{}"'.format(escape(language))
        return (
            '<div class="code-block"><code{}>{}</code></div>\n'.format(
                language_class,
                escape(code),
            )
        )


_MARKDOWN = create_markdown(renderer=MinihtmlRenderer(escape=True))

_DOCUMENT_PREFIX = """<html>
<head>
<style>
body {
    margin: 0;
    padding: 1.5rem;
    color: var(--foreground);
    background-color: var(--background);
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.4rem;
    margin-bottom: 0.6rem;
}
p, ul, div.ordered-list, div.blockquote, div.code-block {
    margin-top: 0.6rem;
    margin-bottom: 0.6rem;
}
div.ordered-list-item {
    display: block;
    margin-left: 1rem;
}
div.blockquote {
    margin-left: 0;
    padding-left: 1rem;
    border-left: 0.2rem solid var(--accent);
}
div.code-block {
    padding: 0.8rem;
    border-radius: 0.3rem;
    background-color: color(var(--foreground) alpha(0.08));
}
div.code-block code {
    display: block;
    font-family: monospace;
    white-space: pre-wrap;
}
</style>
</head>
<body id="markdown-reader-preview">
"""

_DOCUMENT_SUFFIX = "</body>\n</html>\n"


def render_markdown(source):
    """Return theme-aware minihtml for a Markdown source string."""
    return _DOCUMENT_PREFIX + _MARKDOWN(source) + _DOCUMENT_SUFFIX
