"""Discover TeX formulas and coordinate isolated asynchronous rendering."""

import base64
import hashlib
import math
from dataclasses import dataclass

from .render_cache import BoundedMemoryCache, RenderCacheKey
from .renderer_process import RendererProtocolError
from .vendor.mistune import create_markdown

MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
MAX_FORMULA_SOURCE_BYTES = 32 * 1024
MAX_RENDERED_IMAGE_BYTES = 5 * 1024 * 1024
MAX_RENDERED_DIMENSION = 4096
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MATHJAX_RENDERER_VERSION = "4.1.3"

_BLOCK_DOLLAR_PATTERN = (
    r"^ {0,3}\$\$(?:[ \t]*\n(?P<math_dollar_multiline>[\s\S]+?)\n"
    r"|[ \t]*(?P<math_dollar_single>.+?)[ \t]*)\$\$[ \t]*$"
)
_BLOCK_BRACKET_PATTERN = (
    r"^ {0,3}\\\[(?:[ \t]*\n(?P<math_bracket_multiline>[\s\S]+?)\n"
    r"|[ \t]*(?P<math_bracket_single>.+?)[ \t]*)\\\][ \t]*$"
)
_INLINE_BRACKET_PATTERN = r"\\\((?P<inline_math_bracket_text>[^\n]+?)\\\)"
_INLINE_DOLLAR_PATTERN = r"\$(?!\s)(?P<inline_math_dollar_text>.+?)(?!\s)\$"


@dataclass(frozen=True)
class MathFormula:
    """One TeX formula and its stable rendering identity."""

    key: str
    tex: str
    display: bool


@dataclass(frozen=True)
class MathRenderResult:
    """Either an embedded PNG payload or a concise per-formula error."""

    data: str = ""
    error: str = ""
    width: int = 0
    height: int = 0
    baseline_offset: float = 0
    cacheable: bool = True

    @classmethod
    def success(cls, data, width=0, height=0, baseline_offset=0):
        return cls(
            data=data,
            width=width,
            height=height,
            baseline_offset=baseline_offset,
        )

    @classmethod
    def failure(cls, error, cacheable=True):
        return cls(error=error, cacheable=cacheable)


@dataclass(frozen=True)
class MathRenderOptions:
    """Browser rendering inputs derived from the current preview context."""

    theme: str
    width: int
    scale: int
    font_size: int


def math_formula_key(tex, display):
    """Return a deterministic identity separated by inline/display mode."""
    mode = "display" if display else "inline"
    payload = "mathjax\0{}\0{}".format(mode, tex)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return "mathjax:{}".format(digest)


def math_render_cache_key(formula, options):
    """Return the full identity of one rendered MathJax image."""
    return RenderCacheKey(
        renderer="mathjax",
        version=MATHJAX_RENDERER_VERSION,
        source=formula.tex,
        theme=options.theme,
        width=options.width,
        scale=options.scale,
        font_size=options.font_size,
        display=formula.display,
    )


def _parse_block_math(parser, match, state, delimiter):
    if delimiter == "dollar":
        text = match.group("math_dollar_multiline")
        if text is None:
            text = match.group("math_dollar_single")
    else:
        text = match.group("math_bracket_multiline")
        if text is None:
            text = match.group("math_bracket_single")
    state.append_token(
        {"type": "block_math", "raw": text, "attrs": {"delimiter": delimiter}}
    )
    return match.end() + 1


def _parse_inline_bracket_math(parser, match, state):
    if state.in_link or state.in_image:
        state.append_token({"type": "text", "raw": match.group(0)})
        return match.end()
    state.append_token(
        {
            "type": "inline_math",
            "raw": match.group("inline_math_bracket_text"),
            "attrs": {"delimiter": "bracket"},
        }
    )
    return match.end()


def _parse_inline_dollar_math(parser, match, state):
    if state.in_link or state.in_image:
        state.append_token({"type": "text", "raw": match.group(0)})
        return match.end()
    state.append_token(
        {
            "type": "inline_math",
            "raw": match.group("inline_math_dollar_text"),
            "attrs": {"delimiter": "dollar"},
        }
    )
    return match.end()


def math_plugin(allow_single_dollar=False):
    """Return a Mistune plugin with conservative TeX delimiters."""

    def plugin(markdown):
        markdown.block.register(
            "block_math_dollar",
            _BLOCK_DOLLAR_PATTERN,
            lambda parser, match, state: _parse_block_math(
                parser, match, state, "dollar"
            ),
            before="list",
        )
        markdown.block.register(
            "block_math_bracket",
            _BLOCK_BRACKET_PATTERN,
            lambda parser, match, state: _parse_block_math(
                parser, match, state, "bracket"
            ),
            before="list",
        )
        for nested_rules in (
            markdown.block.block_quote_rules,
            markdown.block.list_rules,
        ):
            markdown.block.insert_rule(
                nested_rules,
                "block_math_dollar",
                before="list",
            )
            markdown.block.insert_rule(
                nested_rules,
                "block_math_bracket",
                before="list",
            )

        markdown.inline.register(
            "inline_latex",
            _INLINE_BRACKET_PATTERN,
            _parse_inline_bracket_math,
            before="escape",
        )
        if allow_single_dollar:
            markdown.inline.register(
                "inline_math",
                _INLINE_DOLLAR_PATTERN,
                _parse_inline_dollar_math,
                before="link",
            )

    return plugin


def extract_math_formulas(source, allow_single_dollar=False):
    """Return TeX formulas outside code spans and fenced code blocks."""
    if len(source.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        return []

    markdown = create_markdown(
        renderer=None,
        plugins=[math_plugin(allow_single_dollar=allow_single_dollar)],
    )
    formulas = []

    def visit(tokens):
        for token in tokens:
            token_type = token.get("type")
            if token_type in ("inline_math", "block_math"):
                tex = token.get("raw", "")
                display = token_type == "block_math"
                formulas.append(
                    MathFormula(math_formula_key(tex, display), tex, display)
                )
            children = token.get("children")
            if children:
                visit(children)

    visit(markdown(source))
    return formulas


class MathJaxController:
    """Render formulas off the UI thread and apply only current results."""

    def __init__(
        self,
        preview_manager,
        renderer_provider,
        schedule_async,
        schedule_main,
        region_factory,
        options_provider,
        allow_single_dollar=False,
        cache=None,
    ):
        self._preview_manager = preview_manager
        self._renderer_provider = renderer_provider
        self._schedule_async = schedule_async
        self._schedule_main = schedule_main
        self._region_factory = region_factory
        self._options_provider = options_provider
        self._allow_single_dollar = allow_single_dollar
        self._cache = cache if cache is not None else BoundedMemoryCache()

    def preview_updated(
        self,
        window,
        source_view,
        source,
        allow_single_dollar=None,
    ):
        """Schedule all formulas found in one rendered source revision."""
        if allow_single_dollar is None:
            allow_single_dollar = self._allow_single_dollar
        formulas = extract_math_formulas(source, allow_single_dollar)
        self._preview_manager.retain_special_results(
            window,
            source_view,
            "mathjax",
            {formula.key for formula in formulas},
        )
        if not formulas:
            return
        options = self._options_provider(source_view)
        self._schedule_async(
            lambda: self._render_revision(
                window,
                source_view,
                source,
                formulas,
                options,
            )
        )

    def _render_revision(self, window, source_view, source, formulas, options):
        unique_formulas = {formula.key: formula for formula in formulas}
        results = {}
        missing = {}
        for key, formula in unique_formulas.items():
            cache_key = math_render_cache_key(formula, options)
            cached = self._cache.get(cache_key)
            if cached is None:
                missing[key] = (formula, cache_key)
            else:
                results[key] = cached

        if missing:
            try:
                renderer = self._renderer_provider()
            except Exception as error:
                message = _concise_error(error)
                results.update(
                    {key: MathRenderResult.failure(message) for key in missing}
                )
            else:
                for key, (formula, cache_key) in missing.items():
                    result, _reused = self._cache.get_or_compute(
                        cache_key,
                        lambda formula=formula: self._render_formula(
                            renderer,
                            formula,
                            options,
                        ),
                        should_store=lambda candidate: candidate.cacheable,
                    )
                    results[key] = result

        self._schedule_main(
            lambda: self._apply_if_current(window, source_view, source, results)
        )

    def _render_formula(self, renderer, formula, options):
        if len(formula.tex.encode("utf-8")) > MAX_FORMULA_SOURCE_BYTES:
            return MathRenderResult.failure(
                "Math formula exceeds the 32 KiB rendering limit"
            )

        try:
            response = renderer.request(
                "renderMathJax",
                {
                    "source": formula.tex,
                    "display": formula.display,
                    "theme": options.theme,
                    "width": options.width,
                    "scale": options.scale,
                    "fontSize": options.font_size,
                },
            )
            return self._validated_result(response, options.scale)
        except (TimeoutError, RendererProtocolError) as error:
            return MathRenderResult.failure(
                _concise_error(error),
                cacheable=False,
            )
        except Exception as error:
            return MathRenderResult.failure(_concise_error(error))

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

        baseline_offset = response.get("baselineOffset", 0)
        if (
            isinstance(baseline_offset, bool)
            or not isinstance(baseline_offset, (int, float))
            or not math.isfinite(baseline_offset)
            or baseline_offset < 0
            or baseline_offset > height / scale
        ):
            raise ValueError("renderer returned an invalid formula baseline")
        return MathRenderResult.success(
            data,
            width=max(1, round(width / scale)),
            height=max(1, round(height / scale)),
            baseline_offset=round(float(baseline_offset), 2),
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
