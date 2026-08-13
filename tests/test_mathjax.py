import unittest

from markdown_reader.mathjax import (
    MathJaxController,
    MathRenderOptions,
    extract_math_formulas,
    math_formula_key,
)


def make_region(start, end):
    return (start, end)


class FakeWindow:
    def id(self):
        return 11


class FakeView:
    def __init__(self, text):
        self.text = text

    def id(self):
        return 22

    def size(self):
        return len(self.text)

    def substr(self, region):
        return self.text[region[0] : region[1]]


class FakePreviewManager:
    def __init__(self):
        self.preview_open = True
        self.applied = []

    def has_preview(self, window, view):
        return self.preview_open

    def apply_special_results(self, window, view, region_factory, results):
        self.applied.append((window, view, region_factory, results))


class FakeRenderer:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def request(self, method, params=None):
        self.requests.append((method, params))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class MathExtractionTests(unittest.TestCase):
    def test_extracts_inline_and_block_formulas_but_not_code_or_money(self):
        source = r"""Price is $12.50 and inline is \(x^2 + y^2\).

`\(not_math\)`

[\(linked_not_math\)](https://example.com)

$$
\int_0^1 x\,dx
$$

> \[
> e^{i\pi} + 1 = 0
> \]
"""

        formulas = extract_math_formulas(source)

        self.assertEqual(3, len(formulas))
        self.assertEqual("x^2 + y^2", formulas[0].tex)
        self.assertFalse(formulas[0].display)
        self.assertEqual(r"\int_0^1 x\,dx", formulas[1].tex)
        self.assertTrue(formulas[1].display)
        self.assertEqual(r"e^{i\pi} + 1 = 0", formulas[2].tex)
        self.assertTrue(formulas[2].display)

    def test_single_dollar_math_is_opt_in(self):
        self.assertEqual([], extract_math_formulas("Total $x+y$ today"))

        formulas = extract_math_formulas("Total $x+y$ today", allow_single_dollar=True)

        self.assertEqual(1, len(formulas))
        self.assertEqual("x+y", formulas[0].tex)
        self.assertFalse(formulas[0].display)

    def test_formula_key_separates_inline_and_display_modes(self):
        self.assertNotEqual(
            math_formula_key("x", display=False),
            math_formula_key("x", display=True),
        )

    def test_extracts_formula_nested_in_a_list(self):
        formulas = extract_math_formulas("- item\n\n  $$\n  x+1\n  $$\n")

        self.assertEqual(1, len(formulas))
        self.assertEqual("x+1", formulas[0].tex)
        self.assertTrue(formulas[0].display)


class MathJaxControllerTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        self.source = r"Inline \(x+1\) and \(broken\)."
        self.view = FakeView(self.source)
        self.manager = FakePreviewManager()
        self.async_calls = []
        self.main_calls = []

    def make_controller(self, renderer):
        return MathJaxController(
            preview_manager=self.manager,
            renderer_provider=lambda: renderer,
            schedule_async=self.async_calls.append,
            schedule_main=self.main_calls.append,
            region_factory=make_region,
            options_provider=lambda _view: MathRenderOptions(
                theme="dark",
                width=900,
                scale=2,
                font_size=16,
            ),
        )

    def run_scheduled(self):
        self.assertEqual(1, len(self.async_calls))
        self.async_calls.pop(0)()
        self.assertEqual(1, len(self.main_calls))
        self.main_calls.pop(0)()

    def test_renders_each_formula_and_isolates_an_error(self):
        renderer = FakeRenderer(
            [
                {
                    "mimeType": "image/png",
                    "data": "iVBORw0KGgoAAAANSUhEUg==",
                    "width": 80,
                    "height": 40,
                    "baselineOffset": 3.5,
                },
                RuntimeError("Undefined control sequence\nprivate detail"),
            ]
        )
        controller = self.make_controller(renderer)

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        self.assertEqual(2, len(renderer.requests))
        self.assertEqual("renderMathJax", renderer.requests[0][0])
        self.assertEqual("x+1", renderer.requests[0][1]["source"])
        self.assertFalse(renderer.requests[0][1]["display"])
        self.assertEqual("dark", renderer.requests[0][1]["theme"])
        self.assertEqual(16, renderer.requests[0][1]["fontSize"])
        results = self.manager.applied[0][3]
        valid = results[math_formula_key("x+1", display=False)]
        self.assertEqual((40, 20), (valid.width, valid.height))
        self.assertEqual(3.5, valid.baseline_offset)
        self.assertEqual(
            "Undefined control sequence",
            results[math_formula_key("broken", display=False)].error,
        )

    def test_controller_can_override_single_dollar_mode_per_revision(self):
        response = {
            "mimeType": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUg==",
            "width": 80,
            "height": 40,
            "baselineOffset": 0,
        }
        source = "Total $x+y$ today"
        self.view.text = source
        renderer = FakeRenderer([response])
        controller = self.make_controller(renderer)

        controller.preview_updated(
            self.window,
            self.view,
            source,
            allow_single_dollar=True,
        )
        self.run_scheduled()

        self.assertEqual("x+y", renderer.requests[0][1]["source"])

    def test_discards_results_when_buffer_changes_during_render(self):
        response = {
            "mimeType": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUg==",
            "width": 80,
            "height": 40,
            "baselineOffset": 0,
        }
        controller = self.make_controller(FakeRenderer([response, response]))

        controller.preview_updated(self.window, self.view, self.source)
        self.async_calls.pop(0)()
        self.view.text += "newer"
        self.main_calls.pop(0)()

        self.assertEqual([], self.manager.applied)

    def test_repeated_formula_is_rendered_once(self):
        response = {
            "mimeType": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUg==",
            "width": 80,
            "height": 40,
            "baselineOffset": 0,
        }
        self.source = r"\(same\) and \(same\)"
        self.view.text = self.source
        renderer = FakeRenderer([response])
        controller = self.make_controller(renderer)

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        self.assertEqual(1, len(renderer.requests))

    def test_invalid_baseline_becomes_an_isolated_error(self):
        response = {
            "mimeType": "image/png",
            "data": "iVBORw0KGgoAAAANSUhEUg==",
            "width": 80,
            "height": 40,
            "baselineOffset": 99,
        }
        controller = self.make_controller(FakeRenderer([response, response]))

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        results = self.manager.applied[0][3]
        self.assertTrue(
            all(
                result.error == "renderer returned an invalid formula baseline"
                for result in results.values()
            )
        )

    def test_environment_failure_becomes_a_result_for_each_formula(self):
        controller = MathJaxController(
            preview_manager=self.manager,
            renderer_provider=lambda: (_ for _ in ()).throw(
                RuntimeError("Chrome was not found")
            ),
            schedule_async=self.async_calls.append,
            schedule_main=self.main_calls.append,
            region_factory=make_region,
            options_provider=lambda _view: MathRenderOptions("default", 900, 2, 16),
        )

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        results = self.manager.applied[0][3]
        self.assertEqual(2, len(results))
        self.assertTrue(
            all(result.error == "Chrome was not found" for result in results.values())
        )

    def test_document_without_math_does_not_start_renderer(self):
        renderer_requests = []
        controller = MathJaxController(
            preview_manager=self.manager,
            renderer_provider=lambda: renderer_requests.append("started"),
            schedule_async=self.async_calls.append,
            schedule_main=self.main_calls.append,
            region_factory=make_region,
            options_provider=lambda _view: MathRenderOptions("default", 900, 2, 16),
        )

        controller.preview_updated(self.window, self.view, "Price is $12.50")

        self.assertEqual([], self.async_calls)
        self.assertEqual([], renderer_requests)


if __name__ == "__main__":
    unittest.main()
