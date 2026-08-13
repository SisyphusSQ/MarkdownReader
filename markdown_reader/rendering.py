"""Convert Markdown into a self-contained minihtml document."""

import json
import unicodedata

from .mathjax import math_formula_key, math_plugin
from .mermaid import mermaid_block_key
from .security import DEFAULT_SECURITY_POLICY
from .vendor.mistune import create_markdown
from .vendor.mistune.plugins.table import table
from .vendor.mistune.plugins.task_lists import task_lists
from .vendor.mistune.renderers.html import HTMLRenderer
from .vendor.mistune.util import escape, escape_url, striptags, unescape

_TABLE_CELL_PADDING_REM = 0.7


def _typographic_width(html):
    """Estimate rendered text width in em for minihtml's monospace stack."""
    width = 0.0
    for character in unescape(striptags(html)):
        if unicodedata.combining(character):
            continue
        if unicodedata.east_asian_width(character) in ("F", "W"):
            width += 1.0
        else:
            width += 0.6
    return width


def _format_rem(value):
    return "{:.3f}".format(value).rstrip("0").rstrip(".")


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
        if token["type"] == "table":
            return self._render_table(token, state)
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
            if item.get("type") == "task_list_item":
                checked = (item.get("attrs") or {}).get("checked", False)
                contents = self._render_task_contents(item, state, checked)
            else:
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

    def _render_task_list(self, token, state):
        items = ['<div class="task-list">\n']
        for item in token.get("children", ()):
            if item.get("type") == "task_list_item":
                checked = (item.get("attrs") or {}).get("checked", False)
                state_class = "checked" if checked else "open"
                contents = self._render_task_contents(item, state, checked)
            else:
                state_class = "regular"
                contents = self._render_regular_task_contents(item, state)
            items.append(
                '<div class="task-list-item task-list-item-{}">{}</div>\n'.format(
                    state_class,
                    contents,
                )
            )
        items.append("</div>\n")
        return "".join(items)

    def _render_task_contents(self, item, state, checked):
        children = item.get("children", ())
        marker = self._task_marker(checked)
        if not children:
            return marker
        label = self.render_token(children[0], state)
        remainder = self.render_tokens(children[1:], state)
        return "{} {}{}".format(
            marker,
            self._task_label(label, checked),
            remainder,
        )

    def _render_regular_task_contents(self, item, state):
        children = item.get("children", ())
        marker = (
            '<strong class="task-marker task-marker-bullet">•</strong>'
        )
        if not children:
            return marker
        label = self.render_token(children[0], state)
        remainder = self.render_tokens(children[1:], state)
        return "{} {}{}".format(marker, self._task_label(label, False), remainder)

    @staticmethod
    def _task_marker(checked):
        if checked:
            return '<strong class="task-marker task-marker-checked">✓</strong>'
        return '<strong class="task-marker task-marker-open">✓</strong>'

    @staticmethod
    def _task_label(text, checked):
        classes = ["task-label"]
        if checked:
            classes.append("task-label-checked")
        return '<div class="{}">{}</div>'.format(" ".join(classes), text)

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
        image_source, reason = self._policy.resolve_image_source(url, self._source_path)
        if reason:
            return self._image_placeholder(alt, reason)

        image = '<img class="local-image" src="{}" alt="{}"'.format(
            escape(escape_url(image_source)),
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
        state_class = "checked" if checked else "open"
        return (
            '<div class="task-list-item task-list-item-{}">{} {}</div>\n'.format(
                state_class,
                self._task_marker(checked),
                self._task_label(text, checked),
            )
        )

    def block_quote(self, text):
        """Use a supported block container instead of the unsupported tag."""
        return '<div class="blockquote">\n' + text + "</div>\n"

    def _render_table(self, token, state):
        """Render a horizontal table using minihtml-compatible divs."""
        head_cells = []
        body_rows = []
        for section in token.get("children", ()):
            if section.get("type") == "table_head":
                head_cells = self._render_table_cells(section.get("children", ()), state)
            elif section.get("type") == "table_body":
                for row in section.get("children", ()):
                    body_rows.append(
                        self._render_table_cells(row.get("children", ()), state)
                    )

        rows = ([head_cells] if head_cells else []) + body_rows
        if not rows:
            return ""

        column_count = max(len(row) for row in rows)
        column_widths = [0.0] * column_count
        for row in rows:
            for index, cell in enumerate(row):
                column_widths[index] = max(column_widths[index], cell["width"])

        parts = ['<div class="markdown-table">\n']
        if head_cells:
            parts.append('<div class="table-head"><div class="table-row">')
            parts.append(self._render_table_row(head_cells, column_widths))
            parts.append("</div></div>\n")
        parts.append('<div class="table-body">\n')
        for row in body_rows:
            parts.append('<div class="table-row">')
            parts.append(self._render_table_row(row, column_widths))
            parts.append("</div>\n")
        parts.append("</div>\n</div>\n")
        return "".join(parts)

    def _render_table_cells(self, cells, state):
        rendered = []
        for cell in cells:
            html = self.render_tokens(cell.get("children", ()), state)
            rendered.append(
                {
                    "html": html,
                    "width": _typographic_width(html),
                    "attrs": cell.get("attrs") or {},
                }
            )
        return rendered

    def _render_table_row(self, cells, column_widths):
        rendered = []
        for index, cell in enumerate(cells):
            attrs = cell["attrs"]
            align = attrs.get("align") or "left"
            missing = column_widths[index] - cell["width"]
            if align == "right":
                left_padding = missing
                right_padding = 0.0
            elif align == "center":
                left_padding = missing / 2.0
                right_padding = missing - left_padding
            else:
                left_padding = 0.0
                right_padding = missing

            styles = []
            if left_padding > 0.0001:
                styles.append(
                    "padding-left:{}rem".format(
                        _format_rem(_TABLE_CELL_PADDING_REM + left_padding)
                    )
                )
            if right_padding > 0.0001:
                styles.append(
                    "padding-right:{}rem".format(
                        _format_rem(_TABLE_CELL_PADDING_REM + right_padding)
                    )
                )

            html = cell["html"]
            classes = ["table-cell"]
            if attrs.get("head"):
                classes.append("table-cell-head")
                html = "<strong>" + html + "</strong>"
            classes.append("table-align-{}".format(align))
            style = ' style="{}"'.format("; ".join(styles)) if styles else ""
            rendered.append(
                '<div class="{}"{}>{}</div>'.format(
                    " ".join(classes), style, html
                )
            )
        return "".join(rendered)

    def block_code(self, code, info=None):
        """Preserve code whitespace using minihtml-supported CSS."""
        language_class = ""
        language = ""
        if info:
            language = info.strip().split(None, 1)[0]
            if language:
                language_class = ' class="language-{}"'.format(escape(language))
        if language.lower() == "mermaid":
            return self._render_mermaid(code)
        return (
            '<div class="code-block"><code{}>{}</code></div>\n'.format(
                language_class,
                escape(code),
            )
        )

    def _render_mermaid(self, code):
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
        return '<div class="mermaid-block">{}</div>\n'.format(rendered)

    def block_math(self, tex, delimiter="dollar"):
        """Render a display formula result with a trusted copy command link."""
        return self._render_math(tex, display=True, delimiter=delimiter)

    def inline_math(self, tex, delimiter="bracket"):
        """Render an inline formula result with explicit baseline alignment."""
        return self._render_math(tex, display=False, delimiter=delimiter)

    def _render_math(self, tex, display, delimiter):
        result = self._special_results.get(math_formula_key(tex, display))
        if result is None:
            rendered = '<em class="math-status">Rendering formula…</em>'
        elif result.error:
            rendered = '<em class="math-error">MathJax: {}</em>'.format(
                escape(result.error)
            )
        else:
            dimensions = ' width="{}" height="{}"'.format(
                result.width,
                result.height,
            )
            style = ""
            image_class = "block-math-image" if display else "inline-math-image"
            if not display and result.baseline_offset:
                style = ' style="position: relative; top: {}px"'.format(
                    result.baseline_offset
                )
            rendered = (
                '<img class="math-image {}" '
                'src="data:image/png;base64,{}" alt="Rendered formula"{}{} />'
            ).format(image_class, result.data, dimensions, style)

        copy_payload = json.dumps(
            {"text": tex},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        copy_href = escape("subl:markdown_reader_copy_tex " + copy_payload)
        copy_link = '<a class="math-copy" href="{}">Copy TeX</a>'.format(copy_href)
        if display:
            return (
                '<div class="math-block"><div class="math-image-container">{}</div>'
                '<div class="math-actions">{}</div></div>\n'
            ).format(rendered, copy_link)
        return "{} {}".format(rendered, copy_link)


_DOCUMENT_PREFIX = """<html>
<head>
<style>
html {
    --markdown-muted: color(var(--foreground) alpha(0.68));
    --markdown-border: color(var(--foreground) alpha(0.18));
    --markdown-surface: color(var(--foreground) alpha(0.06));
    --markdown-surface-strong: color(var(--foreground) alpha(0.10));
}
body {
    margin: 0;
    padding-top: 2rem;
    padding-right: 1.5rem;
    padding-bottom: 3rem;
    padding-left: 1.5rem;
    color: var(--foreground);
    background-color: var(--background);
    font-size: 1rem;
    line-height: 1.6;
}
h1, h2, h3, h4, h5, h6 {
    margin-top: 1.5rem;
    margin-bottom: 0.6rem;
    line-height: 1.25;
}
h1 {
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--markdown-border);
    font-size: 2rem;
    font-weight: bold;
}
h2 {
    padding-bottom: 0.3rem;
    border-bottom: 1px solid var(--markdown-border);
    font-size: 1.6rem;
    font-weight: bold;
}
h3 {
    font-size: 1.35rem;
    font-weight: bold;
}
h4 {
    font-size: 1.2rem;
    font-weight: bold;
}
h5, h6 {
    font-size: 1rem;
    font-weight: bold;
}
p, ul, div.ordered-list, div.task-list, div.blockquote, div.code-block,
div.markdown-table, div.mermaid-block, div.math-block, img.local-image {
    margin-top: 0.75rem;
    margin-bottom: 0.75rem;
}
div.ordered-list-item {
    display: block;
    margin-left: 1rem;
    margin-top: 0.2rem;
    margin-bottom: 0.2rem;
}
div.task-list-item {
    display: block;
    margin-left: 0;
    margin-top: 0.15rem;
    margin-bottom: 0.15rem;
    line-height: 1.45rem;
}
strong.task-marker {
    display: inline-block;
    width: 1rem;
    height: 1rem;
    margin-right: 0.25rem;
    padding: 0;
    border: 1px solid var(--markdown-muted);
    border-radius: 0.25rem;
    font-family: sans-serif;
    font-size: 0.75rem;
    line-height: 1rem;
    font-weight: bold;
    text-align: center;
}
strong.task-marker-open {
    color: transparent;
    background-color: transparent;
}
strong.task-marker-checked {
    color: var(--background);
    border-color: var(--accent);
    background-color: var(--accent);
}
strong.task-marker-bullet {
    color: var(--markdown-muted);
    border-color: transparent;
}
div.task-label {
    display: inline;
}
div.task-label-checked {
    color: var(--markdown-muted);
    text-decoration: line-through;
}
div.task-list div.task-list {
    margin-top: 0.15rem;
    margin-bottom: 0;
    margin-left: 0.7rem;
    padding-left: 1.15rem;
    border-left: 1px solid var(--markdown-border);
}
a {
    color: var(--accent);
    text-decoration: underline;
}
div.blockquote {
    margin-left: 0;
    padding-top: 0.15rem;
    padding-bottom: 0.15rem;
    padding-left: 1rem;
    border-left: 0.15rem solid var(--accent);
    color: var(--markdown-muted);
}
code {
    padding-top: 0.1rem;
    padding-right: 0.3rem;
    padding-bottom: 0.1rem;
    padding-left: 0.3rem;
    border-radius: 0.3rem;
    color: var(--foreground);
    background-color: var(--markdown-surface-strong);
    font-family: monospace;
    font-size: 0.9rem;
}
div.code-block {
    padding: 0.9rem;
    border: 1px solid var(--markdown-border);
    border-radius: 0.45rem;
    background-color: var(--markdown-surface);
}
div.code-block code {
    display: block;
    padding: 0;
    border-radius: 0;
    background-color: transparent;
    white-space: pre-wrap;
}
div.markdown-table {
    border: 1px solid var(--markdown-border);
    border-radius: 0.45rem;
    font-family: monospace;
}
div.table-head {
    display: block;
    background-color: var(--markdown-surface-strong);
}
div.table-body {
    display: block;
}
div.table-row {
    display: block;
    border-top: 1px solid var(--markdown-border);
}
div.table-head div.table-row {
    border-top: 0 solid transparent;
}
div.table-cell {
    display: inline;
    padding-top: 0.45rem;
    padding-right: 0.7rem;
    padding-bottom: 0.45rem;
    padding-left: 0.7rem;
    border-right: 1px solid var(--markdown-border);
    white-space: nowrap;
}
div.markdown-table code {
    padding-right: 0;
    padding-left: 0;
    font-size: 1rem;
}
div.mermaid-block {
    padding: 0.9rem;
    border: 1px solid var(--markdown-border);
    border-radius: 0.45rem;
    background-color: var(--markdown-surface);
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
div.math-block {
    padding: 0.9rem;
    border: 1px solid var(--markdown-border);
    border-radius: 0.45rem;
    background-color: var(--markdown-surface);
}
div.math-image-container {
    text-align: center;
}
div.math-actions {
    margin-top: 0.35rem;
    text-align: center;
}
em.math-status, em.math-error {
    color: var(--accent);
}
em.math-error {
    color: var(--redish);
}
a.math-copy {
    font-size: 0.85rem;
    color: var(--markdown-muted);
}
em.image-placeholder, div.security-error {
    color: var(--redish);
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
    allow_single_dollar_math=False,
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
    markdown = create_markdown(
        renderer=renderer,
        plugins=[table, task_lists, math_plugin(allow_single_dollar_math)],
    )
    return _DOCUMENT_PREFIX + markdown(source) + _DOCUMENT_SUFFIX
