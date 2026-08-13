import io
import unittest

from markdown_reader.renderer_process import RendererProcess, RendererProtocolError


class FakeProcess:
    def __init__(self, responses):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO("".join(responses))
        self.returncode = None
        self.terminated = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated += 1
        self.returncode = 0


class RendererProcessTests(unittest.TestCase):
    def test_starts_lazily_and_reuses_process(self):
        process = FakeProcess([
            '{"id":1,"ok":true,"result":{"pong":true}}\n',
            '{"id":2,"ok":true,"result":{"pong":true}}\n',
        ])
        starts = []

        client = RendererProcess(lambda: starts.append(True) or process)

        self.assertEqual([], starts)
        self.assertEqual({"pong": True}, client.request("ping"))
        self.assertEqual({"pong": True}, client.request("ping"))
        self.assertEqual([True], starts)
        self.assertIn('"id":1', process.stdin.getvalue())
        self.assertIn('"id":2', process.stdin.getvalue())

    def test_rejects_oversized_request_before_start(self):
        starts = []
        client = RendererProcess(lambda: starts.append(True), max_message_bytes=32)

        with self.assertRaisesRegex(ValueError, "renderer request exceeds"):
            client.request("ping", {"text": "x" * 100})

        self.assertEqual([], starts)

    def test_protocol_error_terminates_process(self):
        process = FakeProcess(['{"id":99,"ok":true,"result":{}}\n'])
        client = RendererProcess(lambda: process)

        with self.assertRaises(RendererProtocolError):
            client.request("ping")

        self.assertEqual(1, process.terminated)

    def test_renderer_error_is_reported_without_protocol_failure(self):
        process = FakeProcess(['{"id":1,"ok":false,"error":"unsupported request"}\n'])
        client = RendererProcess(lambda: process)

        with self.assertRaisesRegex(RuntimeError, "unsupported request"):
            client.request("unknown")

        self.assertEqual(0, process.terminated)

    def test_oversized_response_terminates_process(self):
        process = FakeProcess(
            ['{"id":1,"ok":true,"result":{"data":"' + "x" * 200 + '"}}\n']
        )
        client = RendererProcess(lambda: process, max_response_bytes=64)

        with self.assertRaisesRegex(RendererProtocolError, "response exceeds"):
            client.request("renderMermaid")

        self.assertEqual(1, process.terminated)

    def test_close_is_idempotent(self):
        process = FakeProcess(['{"id":1,"ok":true,"result":{}}\n'])
        client = RendererProcess(lambda: process)
        client.request("ping")

        client.close()
        client.close()

        self.assertEqual(1, process.terminated)


if __name__ == "__main__":
    unittest.main()
