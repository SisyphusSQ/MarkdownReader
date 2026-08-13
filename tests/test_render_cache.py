import json
import threading
import unittest
from pathlib import Path

from markdown_reader.mathjax import (
    MATHJAX_RENDERER_VERSION,
    MathFormula,
    MathRenderOptions,
    math_formula_key,
    math_render_cache_key,
)
from markdown_reader.mermaid import (
    MERMAID_RENDERER_VERSION,
    MermaidBlock,
    MermaidRenderOptions,
    mermaid_block_key,
    mermaid_render_cache_key,
)
from markdown_reader.render_cache import BoundedMemoryCache, RenderCacheKey

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class BoundedMemoryCacheTests(unittest.TestCase):
    def make_cache(self, max_entries=2, max_bytes=10):
        return BoundedMemoryCache(
            max_entries=max_entries,
            max_bytes=max_bytes,
            entry_size=lambda _key, value: value[1],
        )

    def test_evicts_least_recently_used_entry_at_entry_limit(self):
        cache = self.make_cache()

        cache.get_or_compute("a", lambda: ("A", 1))
        cache.get_or_compute("b", lambda: ("B", 1))
        self.assertEqual(("A", 1), cache.get("a"))
        cache.get_or_compute("c", lambda: ("C", 1))

        self.assertIsNone(cache.get("b"))
        self.assertEqual(("A", 1), cache.get("a"))
        self.assertEqual(("C", 1), cache.get("c"))

    def test_evicts_entries_until_estimated_byte_limit_is_met(self):
        cache = self.make_cache(max_entries=10, max_bytes=5)

        cache.get_or_compute("a", lambda: ("A", 3))
        cache.get_or_compute("b", lambda: ("B", 3))

        self.assertIsNone(cache.get("a"))
        self.assertEqual(("B", 3), cache.get("b"))
        self.assertLessEqual(cache.current_bytes, 5)
        self.assertEqual(1, cache.entry_count)

    def test_does_not_store_an_entry_larger_than_the_byte_limit(self):
        cache = self.make_cache(max_entries=10, max_bytes=5)

        value, reused = cache.get_or_compute("large", lambda: ("large", 6))

        self.assertEqual(("large", 6), value)
        self.assertFalse(reused)
        self.assertIsNone(cache.get("large"))

    def test_can_share_but_not_store_a_non_cacheable_result(self):
        cache = self.make_cache()

        value, reused = cache.get_or_compute(
            "transient",
            lambda: ("timeout", 1),
            should_store=lambda _value: False,
        )

        self.assertEqual(("timeout", 1), value)
        self.assertFalse(reused)
        self.assertIsNone(cache.get("transient"))

    def test_coalesces_concurrent_computation_for_the_same_key(self):
        cache = self.make_cache()
        started = threading.Event()
        release = threading.Event()
        calls = []
        results = []

        def compute():
            calls.append("compute")
            started.set()
            release.wait(timeout=2)
            return ("shared", 1)

        first = threading.Thread(
            target=lambda: results.append(cache.get_or_compute("same", compute))
        )
        second = threading.Thread(
            target=lambda: results.append(cache.get_or_compute("same", compute))
        )

        first.start()
        self.assertTrue(started.wait(timeout=2))
        second.start()
        release.set()
        first.join(timeout=2)
        second.join(timeout=2)

        self.assertEqual(["compute"], calls)
        self.assertEqual(2, len(results))
        self.assertEqual({False, True}, {reused for _value, reused in results})

    def test_clear_removes_entries_and_prevents_in_flight_repopulation(self):
        cache = self.make_cache()
        started = threading.Event()
        release = threading.Event()

        def compute():
            started.set()
            release.wait(timeout=2)
            return ("late", 1)

        worker = threading.Thread(target=lambda: cache.get_or_compute("late", compute))
        worker.start()
        self.assertTrue(started.wait(timeout=2))

        cache.clear()
        release.set()
        worker.join(timeout=2)

        self.assertIsNone(cache.get("late"))
        self.assertEqual(0, cache.current_bytes)

    def test_new_generation_does_not_wait_for_pre_clear_computation(self):
        cache = self.make_cache()
        started = threading.Event()
        release = threading.Event()

        def old_compute():
            started.set()
            release.wait(timeout=2)
            return ("old", 1)

        old_worker = threading.Thread(
            target=lambda: cache.get_or_compute("same", old_compute)
        )
        old_worker.start()
        self.assertTrue(started.wait(timeout=2))

        cache.clear()
        value, reused = cache.get_or_compute("same", lambda: ("new", 1))
        release.set()
        old_worker.join(timeout=2)

        self.assertEqual(("new", 1), value)
        self.assertFalse(reused)
        self.assertEqual(("new", 1), cache.get("same"))


class RenderCacheKeyTests(unittest.TestCase):
    def test_key_includes_renderer_version_and_all_render_inputs(self):
        key = RenderCacheKey(
            renderer="mathjax",
            version="4.1.3",
            source="x+1",
            theme="dark",
            width=900,
            scale=2,
            font_size=16,
            display=False,
        )

        self.assertEqual("mathjax", key.renderer)
        self.assertEqual("4.1.3", key.version)
        self.assertNotEqual(key, RenderCacheKey(**{**key.__dict__, "font_size": 17}))
        self.assertNotEqual(key, RenderCacheKey(**{**key.__dict__, "theme": "default"}))

    def test_mermaid_key_changes_with_each_render_option(self):
        block = MermaidBlock(mermaid_block_key("graph LR"), "graph LR")
        base = MermaidRenderOptions(theme="dark", width=900, scale=2)
        key = mermaid_render_cache_key(block, base)

        self.assertEqual("mermaid", key.renderer)
        self.assertEqual(MERMAID_RENDERER_VERSION, key.version)
        self.assertNotEqual(
            key,
            mermaid_render_cache_key(
                block,
                MermaidRenderOptions(theme="default", width=900, scale=2),
            ),
        )
        self.assertNotEqual(
            key,
            mermaid_render_cache_key(
                block,
                MermaidRenderOptions(theme="dark", width=901, scale=2),
            ),
        )
        self.assertNotEqual(
            key,
            mermaid_render_cache_key(
                block,
                MermaidRenderOptions(theme="dark", width=900, scale=3),
            ),
        )

    def test_mathjax_key_changes_with_mode_and_font_size(self):
        formula = MathFormula(math_formula_key("x+1", False), "x+1", False)
        base = MathRenderOptions(theme="dark", width=900, scale=2, font_size=16)
        key = math_render_cache_key(formula, base)

        self.assertEqual("mathjax", key.renderer)
        self.assertEqual(MATHJAX_RENDERER_VERSION, key.version)
        self.assertNotEqual(
            key,
            math_render_cache_key(
                MathFormula(math_formula_key("x+1", True), "x+1", True),
                base,
            ),
        )
        self.assertNotEqual(
            key,
            math_render_cache_key(
                formula,
                MathRenderOptions(theme="dark", width=900, scale=2, font_size=17),
            ),
        )

    def test_renderer_versions_match_pinned_runtime_packages(self):
        package = json.loads(
            (PACKAGE_ROOT / "renderer" / "package.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            package["dependencies"]["mermaid"],
            MERMAID_RENDERER_VERSION,
        )
        self.assertEqual(
            package["dependencies"]["@mathjax/src"],
            MATHJAX_RENDERER_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
