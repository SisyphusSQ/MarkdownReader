"""Reusable NDJSON client for the local Node renderer process."""

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError


class RendererProtocolError(RuntimeError):
    pass


class RendererProcess:
    """Lazily start and serialize requests through one renderer process."""

    def __init__(self, start_process, timeout_seconds=5, max_message_bytes=2 * 1024 * 1024):
        self._start_process = start_process
        self._timeout_seconds = timeout_seconds
        self._max_message_bytes = max_message_bytes
        self._process = None
        self._request_id = 0
        self._lock = threading.Lock()
        self._reader = ThreadPoolExecutor(max_workers=1)
        self._closed = False

    def request(self, method, params=None):
        with self._lock:
            if self._closed:
                raise RuntimeError("renderer process client is closed")
            self._request_id += 1
            request_id = self._request_id
            payload = {"id": request_id, "method": method, "params": params or {}}
            encoded = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
            if len(encoded) > self._max_message_bytes:
                raise ValueError("renderer request exceeds the message-size limit")

            process = self._ensure_process()
            try:
                process.stdin.write(encoded.decode("utf-8"))
                process.stdin.flush()
                line = self._reader.submit(process.stdout.readline).result(
                    timeout=self._timeout_seconds
                )
                response = json.loads(line)
            except TimeoutError as error:
                self._discard_process()
                raise TimeoutError("renderer request timed out") from error
            except (BrokenPipeError, OSError, ValueError, json.JSONDecodeError) as error:
                self._discard_process()
                raise RendererProtocolError("renderer returned an invalid response") from error

            if response.get("id") != request_id or "ok" not in response:
                self._discard_process()
                raise RendererProtocolError("renderer response did not match the request")
            if not response["ok"]:
                raise RuntimeError(response.get("error") or "renderer request failed")
            return response.get("result")

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._discard_process()
            self._reader.shutdown(wait=False)

    def _ensure_process(self):
        if self._process is None or self._process.poll() is not None:
            self._process = self._start_process()
        return self._process

    def _discard_process(self):
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.terminate()
            if hasattr(process, "wait"):
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
