"""Convert Markdown into a self-contained minihtml document."""

from .mermaid import mermaid_block_key
from .security import DEFAULT_SECURITY_POLICY
from .vendor.mistune import create_markdown
from .vendor.mistune.plugins.task_lists import task_lists
from .vendor.mistune.renderers.html import HTMLRenderer
from .vendor.mistune.util import escape, escape_url, striptags


class MinihtmlRenderer(HTMLRenderer):
    """Render only the inert Markdown subset supported by the first release slice."""

    def __init__(
        self,
        source_path=None,
        policy=DEFAULT_SECURITY_POLICY,
        special_results=None,
    ):
        super().__init__(escape=True)
        self._source_path = source_path
        self._policy = policy
        self._special_results = special_results or {}

    def render_token(self, token, state):
        """Render ordered lists with explicit markers minihtml can display."""
        attrs = token.get("attrs") or {}
        if token["type"] == "list" and attrs.get("ordered"):
            return self._render_ordered_list(token, state)
        if token["type"] == "list" and any(
            child.get("type") == "task_list_item" for child in token.get("children", ())
        ):
            return self._render_task_list(token, state)
        return super().render_token(token, state)

    def _render_ordered_list(self, token, state):
        attrs = token.get("attrs") or {}
        start = attrs.get("start", 1)
        items = ['<div class="ordered-list">\n']
        for number, item in enumerate(token.get("children", ()), start):
            contents = self.render_tokens(item.get("children", ()), state)
            task_marker = ""
            if item.get("type") == "task_list_item":
                marker = "☑" if (item.get("attrs") or {}).get("checked") else "☐"
                task_marker = '<strong class="task-marker">{}</strong> '.format(marker)
            items.append(
                '<div class="ordered-list-item">'
                '<strong class="ordered-marker">{}.</strong> {}{}</div>\n'.format(
                    number,
                    task_marker,
                    contents,
                )
            )
        items.append("</div>\n")
        return "".join(items)

    def _render_task_list(self, token, state):
        items = ['<div class="task-list">\n']
        for item in token.get("children", ()):
            contents = self.render_tokens(item.get("children", ()), state)
            if item.get("type") == "task_list_item":
                marker = "☑" if (item.get("attrs") or {}).get("checked") else "☐"
            else:
                marker = "•"
            items.append(
                '<div class="task-list-item">'
                '<strong class="task-marker">{}</strong> {}</div>\n'.format(
                    marker,
                    contents,
                )
            )
        items.append("</div>\n")
        return "".join(items)

    def link(self, text, url, title=None):
        """Activate only absolute HTTP(S) links supported by HtmlSheet."""
        if not self._policy.allows_link(url):
            return text
        link = '<a href="{}"'.format(escape(escape_url(url)))
        if title:
            link += ' title="{}"'.format(escape(title))
        return link + ">" + text + "</a>"

    def image(self, text, url, title=None):
        """Render supported local images without performing network access."""
        alt = striptags(text) or "untitled"
        image_path, reason = self._policy.resolve_local_image(url, self._source_path)
        if reason:
            return self._image_placeholder(alt, reason)

        image = '<img class="local-image" src="{}" alt="{}"'.format(
            escape(image_path.as_uri()),
            escape(alt),
        )
        if title:
            image += ' title="{}"'.format(escape(title))
        return image + " />"

    def _image_placeholder(self, alt, reason):
        return '<em class="image-placeholder">[Image: {} — {}]</em>'.format(
            escape(alt),
            reason,
        )

    def task_list_item(self, text, checked=False):
        """Render a task token that appears outside a recognized list."""
        marker = "☑" if checked else "☐"
        return (
            '<div class="task-list-item">'
            '<strong class="task-marker">{}</strong> {}</div>\n'.format(marker, text)
        )

    def block_quote(self, text):
        """Use a supported block container instead of the unsupported tag."""
        return '<div class="blockquote">\n' + text + "</div>\n"

    def block_code(self, code, info=None):
        """Preserve code whitespace using minihtml-supported CSS."""
        language_class = ""
        language = ""
        if info:
            language = info.strip().split(None, 1)[0]
            if language:
                language_class = ' class="language-{}"'.format(escape(language))
        if language.lower() == "mermaid":
            return self._render_mermaid(code, language_class)
        return (
            '<div class="code-block"><code{}>{}</code></div>\n'.format(
                language_class,
                escape(code),
            )
        )

    def _render_mermaid(self, code, language_class):
        result = self._special_results.get(mermaid_block_key(code))
        if result is None:
            rendered = '<div class="mermaid-status">Rendering Mermaid diagram…</div>'
        elif result.error:
            rendered = '<div class="mermaid-error">Mermaid: {}</div>'.format(
                escape(result.error)
            )
        else:
            dimensions = ""
            if result.width > 0 and result.height > 0:
                dimensions = ' width="{}" height="{}"'.format(
                    result.width,
                    result.height,
                )
            rendered = (
                '<div class="mermaid-image-container">'
                '<img class="mermaid-image" src="data:image/png;base64,{}" '
                'alt="Rendered Mermaid diagram"{} /></div>'
            ).format(result.data, dimensions)
        source = '<div class="mermaid-source"><code{}>{}</code></div>'.format(
            language_class,
            escape(code),
        )
        return '<div class="mermaid-block">{}{}</div>\n'.format(rendered, source)


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
p, ul, div.ordered-list, div.task-list, div.blockquote, div.code-block,
div.mermaid-block, img.local-image {
    margin-top: 0.6rem;
    margin-bottom: 0.6rem;
}
div.ordered-list-item {
    display: block;
    margin-left: 1rem;
}
div.task-list-item {
    display: block;
    margin-left: 1rem;
}
strong.task-marker {
    color: var(--accent);
}
a {
    color: var(--accent);
    text-decoration: underline;
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
div.mermaid-block {
    padding: 0.8rem;
    border-radius: 0.3rem;
    background-color: color(var(--foreground) alpha(0.04));
}
div.mermaid-image-container {
    text-align: center;
}
div.mermaid-status, div.mermaid-error {
    margin-bottom: 0.6rem;
    color: var(--accent);
}
div.mermaid-error {
    color: var(--redish);
}
div.mermaid-source code {
    display: block;
    font-family: monospace;
    white-space: pre-wrap;
    opacity: 0.72;
}
</style>
</head>
<body id="markdown-reader-preview">
"""

_DOCUMENT_SUFFIX = "</body>\n</html>\n"


def render_markdown(
    source,
    source_path=None,
    policy=DEFAULT_SECURITY_POLICY,
    special_results=None,
):
    """Return theme-aware minihtml for a Markdown source string."""
    rejection_reason = policy.source_rejection_reason(source)
    if rejection_reason:
        diagnostic = '<div class="security-error">{}</div>\n'.format(escape(rejection_reason))
        return _DOCUMENT_PREFIX + diagnostic + _DOCUMENT_SUFFIX

    renderer = MinihtmlRenderer(
        source_path=source_path,
        policy=policy,
        special_results=special_results,
    )
    markdown = create_markdown(renderer=renderer, plugins=[task_lists])
    return _DOCUMENT_PREFIX + markdown(source) + _DOCUMENT_SUFFIX
