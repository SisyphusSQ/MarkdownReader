"""Discover the external tools required by the local renderer."""

import os
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class RendererEnvironment:
    node_path: str
    chrome_path: str
    problems: list

    @property
    def ready(self):
        return not self.problems


class RendererEnvironmentDetector:
    """Locate Node.js and Chrome without depending only on the app PATH."""

    def __init__(self, which=shutil.which, is_executable=None, chrome_candidates=None):
        self._which = which
        self._is_executable = is_executable or (
            lambda path: os.path.isfile(path) and os.access(path, os.X_OK)
        )
        self._chrome_candidates = chrome_candidates or self._default_chrome_candidates

    def detect(self):
        node_path = self._which("node") or self._first_executable(
            ["/opt/homebrew/bin/node", "/usr/local/bin/node"]
        )
        chrome_path = self._first_executable(self._chrome_candidates())
        if not chrome_path:
            chrome_path = self._first_executable(
                filter(None, (self._which(name) for name in ("google-chrome", "chromium", "chrome")))
            )

        problems = []
        if not node_path or not self._is_executable(node_path):
            node_path = ""
            problems.append("Node.js executable was not found")
        if not chrome_path:
            problems.append("Chrome or Chromium executable was not found")
        return RendererEnvironment(node_path, chrome_path or "", problems)

    def _first_executable(self, candidates):
        return next((path for path in candidates if path and self._is_executable(path)), "")

    @staticmethod
    def _default_chrome_candidates():
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            root = os.environ.get(variable)
            if root:
                candidates.extend(
                    [
                        os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(root, "Chromium", "Application", "chrome.exe"),
                    ]
                )
        return candidates
