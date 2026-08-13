import unittest

from markdown_reader.mermaid import (
    MermaidController,
    MermaidRenderOptions,
    extract_mermaid_blocks,
    mermaid_block_key,
    mermaid_theme_for_background,
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


class MermaidExtractionTests(unittest.TestCase):
    def test_extracts_nested_mermaid_fences_and_ignores_other_code(self):
        source = (
            "```python\nprint('no')\n```\n\n"
            "> ```mermaid title\n> flowchart LR\n> A --> B\n> ```\n"
        )

        blocks = extract_mermaid_blocks(source)

        self.assertEqual(1, len(blocks))
        self.assertEqual("flowchart LR\nA --> B\n", blocks[0].source)
        self.assertEqual(mermaid_block_key(blocks[0].source), blocks[0].key)

    def test_maps_editor_background_to_a_supported_mermaid_theme(self):
        self.assertEqual("dark", mermaid_theme_for_background("#202124"))
        self.assertEqual("default", mermaid_theme_for_background("#FAFAFA"))
        self.assertEqual("dark", mermaid_theme_for_background("#123"))
        self.assertEqual("default", mermaid_theme_for_background("not-a-color"))


class MermaidControllerTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        self.source = (
            "```mermaid\nflowchart LR\nA --> B\n```\n\n"
            "```mermaid\nbroken\n```\n"
        )
        self.view = FakeView(self.source)
        self.manager = FakePreviewManager()
        self.async_calls = []
        self.main_calls = []

    def make_controller(self, renderer):
        return MermaidController(
            preview_manager=self.manager,
            renderer_provider=lambda: renderer,
            schedule_async=self.async_calls.append,
            schedule_main=self.main_calls.append,
            region_factory=make_region,
            options_provider=lambda _view: MermaidRenderOptions(
                theme="dark",
                width=900,
                scale=2,
            ),
        )

    def run_scheduled(self):
        self.assertEqual(1, len(self.async_calls))
        self.async_calls.pop(0)()
        self.assertEqual(1, len(self.main_calls))
        self.main_calls.pop(0)()

    def test_renders_each_block_and_isolates_a_syntax_error(self):
        renderer = FakeRenderer(
            [
                {
                    "mimeType": "image/png",
                    "data": "iVBORw0KGgoAAAANSUhEUg==",
                    "width": 320,
                    "height": 120,
                },
                RuntimeError("Parse error on line 1\nsource details"),
            ]
        )
        controller = self.make_controller(renderer)

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        self.assertEqual(2, len(renderer.requests))
        self.assertEqual("renderMermaid", renderer.requests[0][0])
        self.assertEqual("dark", renderer.requests[0][1]["theme"])
        self.assertEqual(900, renderer.requests[0][1]["width"])
        self.assertEqual(2, renderer.requests[0][1]["scale"])
        results = self.manager.applied[0][3]
        valid_result = results[mermaid_block_key("flowchart LR\nA --> B\n")]
        self.assertTrue(valid_result.data)
        self.assertEqual((160, 60), (valid_result.width, valid_result.height))
        self.assertEqual(
            "Parse error on line 1",
            results[mermaid_block_key("broken\n")].error,
        )

    def test_discards_results_when_buffer_changed_during_render(self):
        renderer = FakeRenderer(
            [
                {
                    "mimeType": "image/png",
                    "data": "iVBORw0KGgoAAAANSUhEUg==",
                    "width": 320,
                    "height": 120,
                },
                {
                    "mimeType": "image/png",
                    "data": "iVBORw0KGgoAAAANSUhEUg==",
                    "width": 320,
                    "height": 120,
                },
            ]
        )
        controller = self.make_controller(renderer)

        controller.preview_updated(self.window, self.view, self.source)
        self.async_calls.pop(0)()
        self.view.text += "newer edit"
        self.main_calls.pop(0)()

        self.assertEqual([], self.manager.applied)

    def test_rejects_non_png_renderer_output(self):
        renderer = FakeRenderer(
            [
                {"mimeType": "image/svg+xml", "data": "PHN2Zz4=", "width": 1, "height": 1},
                {"mimeType": "image/svg+xml", "data": "PHN2Zz4=", "width": 1, "height": 1},
            ]
        )
        controller = self.make_controller(renderer)

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        results = self.manager.applied[0][3]
        self.assertTrue(all(result.error == "renderer returned a non-PNG image" for result in results.values()))

    def test_environment_failure_becomes_a_result_for_each_block(self):
        controller = MermaidController(
            preview_manager=self.manager,
            renderer_provider=lambda: (_ for _ in ()).throw(
                RuntimeError("Node.js 22.12 or newer is required")
            ),
            schedule_async=self.async_calls.append,
            schedule_main=self.main_calls.append,
            region_factory=make_region,
            options_provider=lambda _view: MermaidRenderOptions("default", 900, 2),
        )

        controller.preview_updated(self.window, self.view, self.source)
        self.run_scheduled()

        results = self.manager.applied[0][3]
        self.assertEqual(2, len(results))
        self.assertTrue(
            all(
                result.error == "Node.js 22.12 or newer is required"
                for result in results.values()
            )
        )

    def test_document_without_mermaid_does_not_start_renderer(self):
        renderer_requests = []
        controller = MermaidController(
            preview_manager=self.manager,
            renderer_provider=lambda: renderer_requests.append("started"),
            schedule_async=self.async_calls.append,
            schedule_main=self.main_calls.append,
            region_factory=make_region,
            options_provider=lambda _view: MermaidRenderOptions("default", 900, 2),
        )

        controller.preview_updated(self.window, self.view, "# Plain Markdown")

        self.assertEqual([], self.async_calls)
        self.assertEqual([], renderer_requests)


if __name__ == "__main__":
    unittest.main()
