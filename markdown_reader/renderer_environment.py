"""Discover the external tools required by the local renderer."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class RendererEnvironment:
    node_path: str
    node_version: str
    chrome_path: str
    problems: list

    @property
    def ready(self):
        return not self.problems


class RendererEnvironmentDetector:
    """Locate Node.js and Chrome without depending only on the app PATH."""

    def __init__(
        self,
        which=shutil.which,
        is_executable=None,
        chrome_candidates=None,
        read_node_version=None,
    ):
        self._which = which
        self._is_executable = is_executable or (
            lambda path: os.path.isfile(path) and os.access(path, os.X_OK)
        )
        self._chrome_candidates = chrome_candidates or self._default_chrome_candidates
        self._read_node_version = read_node_version or self._default_node_version

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
        node_version = ""
        if not node_path or not self._is_executable(node_path):
            node_path = ""
            problems.append("Node.js executable was not found")
        else:
            node_version = self._normalized_node_version(
                self._read_node_version(node_path)
            )
            if not node_version:
                problems.append("Node.js version could not be determined")
            elif self._version_tuple(node_version) < (22, 12, 0):
                problems.append(
                    "Node.js 22.12 or newer is required; found {}".format(
                        node_version
                    )
                )
        if not chrome_path:
            problems.append("Chrome or Chromium executable was not found")
        return RendererEnvironment(node_path, node_version, chrome_path or "", problems)

    def _first_executable(self, candidates):
        return next((path for path in candidates if path and self._is_executable(path)), "")

    @staticmethod
    def _default_node_version(node_path):
        try:
            completed = subprocess.run(
                [node_path, "--version"],
                capture_output=True,
                check=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return completed.stdout

    @staticmethod
    def _normalized_node_version(value):
        match = re.fullmatch(r"\s*v?(\d+\.\d+\.\d+)\s*", value or "")
        return match.group(1) if match else ""

    @staticmethod
    def _version_tuple(value):
        return tuple(int(part) for part in value.split("."))

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
