"""Discover Mermaid blocks and coordinate isolated asynchronous rendering."""

import base64
import hashlib
import re
from dataclasses import dataclass

from .vendor.mistune import create_markdown

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_MERMAID_SOURCE_BYTES = 128 * 1024
MAX_RENDERED_IMAGE_BYTES = 5 * 1024 * 1024
MAX_RENDERED_DIMENSION = 4096
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class MermaidBlock:
    """One fenced Mermaid block and its stable source key."""

    key: str
    source: str


@dataclass(frozen=True)
class MermaidRenderResult:
    """Either an embedded PNG payload or a concise per-block error."""

    data: str = ""
    error: str = ""
    width: int = 0
    height: int = 0

    @classmethod
    def success(cls, data, width=0, height=0):
        return cls(data=data, width=width, height=height)

    @classmethod
    def failure(cls, error):
        return cls(error=error)


@dataclass(frozen=True)
class MermaidRenderOptions:
    """Browser rendering inputs derived from the current preview context."""

    theme: str
    width: int
    scale: int


def mermaid_block_key(source):
    """Return the deterministic identity used to join parser and renderer output."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def extract_mermaid_blocks(source):
    """Return fenced Mermaid blocks, including blocks nested in quotations or lists."""
    if len(source.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        return []

    markdown = create_markdown(renderer=None)
    blocks = []

    def visit(tokens):
        for token in tokens:
            attrs = token.get("attrs") or {}
            info = attrs.get("info") or ""
            language = info.strip().split(None, 1)[0].lower() if info.strip() else ""
            if token.get("type") == "block_code" and language == "mermaid":
                block_source = token.get("raw", "")
                blocks.append(MermaidBlock(mermaid_block_key(block_source), block_source))
            children = token.get("children")
            if children:
                visit(children)

    visit(markdown(source))
    return blocks


def mermaid_theme_for_background(background):
    """Map a Sublime hexadecimal background color to a Mermaid theme."""
    match = re.fullmatch(
        r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?",
        background or "",
    )
    if not match:
        return "default"
    color = match.group(1)
    if len(color) == 3:
        color = "".join(channel * 2 for channel in color)
    red, green, blue = (
        int(color[index : index + 2], 16) for index in (0, 2, 4)
    )
    luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return "dark" if luminance < 128 else "default"


class MermaidController:
    """Render Mermaid blocks off the UI thread and apply only current results."""

    def __init__(
        self,
        preview_manager,
        renderer_provider,
        schedule_async,
        schedule_main,
        region_factory,
        options_provider,
    ):
        self._preview_manager = preview_manager
        self._renderer_provider = renderer_provider
        self._schedule_async = schedule_async
        self._schedule_main = schedule_main
        self._region_factory = region_factory
        self._options_provider = options_provider

    def preview_updated(self, window, source_view, source):
        """Schedule all Mermaid blocks found in one rendered source revision."""
        blocks = extract_mermaid_blocks(source)
        if not blocks:
            return
        options = self._options_provider(source_view)
        self._schedule_async(
            lambda: self._render_revision(window, source_view, source, blocks, options)
        )

    def _render_revision(self, window, source_view, source, blocks, options):
        results = {}
        unique_blocks = {block.key: block for block in blocks}
        try:
            renderer = self._renderer_provider()
        except Exception as error:  # environment failures apply to every block
            message = _concise_error(error)
            results = {
                key: MermaidRenderResult.failure(message) for key in unique_blocks
            }
        else:
            for key, block in unique_blocks.items():
                results[key] = self._render_block(renderer, block, options)

        self._schedule_main(
            lambda: self._apply_if_current(window, source_view, source, results)
        )

    def _render_block(self, renderer, block, options):
        if len(block.source.encode("utf-8")) > MAX_MERMAID_SOURCE_BYTES:
            return MermaidRenderResult.failure(
                "Mermaid source exceeds the 128 KiB rendering limit"
            )

        try:
            response = renderer.request(
                "renderMermaid",
                {
                    "source": block.source,
                    "theme": options.theme,
                    "width": options.width,
                    "scale": options.scale,
                },
            )
            return self._validated_result(response, options.scale)
        except Exception as error:  # a malformed block must not affect its siblings
            return MermaidRenderResult.failure(_concise_error(error))

    @staticmethod
    def _validated_result(response, scale):
        if not isinstance(response, dict) or response.get("mimeType") != "image/png":
            raise ValueError("renderer returned a non-PNG image")

        data = response.get("data")
        try:
            decoded = base64.b64decode(data, validate=True)
        except (TypeError, ValueError) as error:
            raise ValueError("renderer returned invalid PNG data") from error
        if not decoded.startswith(_PNG_SIGNATURE):
            raise ValueError("renderer returned invalid PNG data")
        if len(decoded) > MAX_RENDERED_IMAGE_BYTES:
            raise ValueError("renderer image exceeds the 5 MiB limit")

        width = response.get("width")
        height = response.get("height")
        if not all(
            isinstance(value, int) and 0 < value <= MAX_RENDERED_DIMENSION
            for value in (width, height)
        ):
            raise ValueError("renderer returned invalid image dimensions")
        return MermaidRenderResult.success(
            data,
            width=max(1, round(width / scale)),
            height=max(1, round(height / scale)),
        )

    def _apply_if_current(self, window, source_view, source, results):
        if not self._preview_manager.has_preview(window, source_view):
            return
        current = source_view.substr(self._region_factory(0, source_view.size()))
        if current != source:
            return
        self._preview_manager.apply_special_results(
            window,
            source_view,
            self._region_factory,
            results,
        )


def _concise_error(error):
    message = str(error).strip().splitlines()[0] if str(error).strip() else "rendering failed"
    return message[:240]
