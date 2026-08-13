import hashlib
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPOSITORY_ROOT / "scripts" / "build_release_package.py"


class ReleasePackageTests(unittest.TestCase):
    def test_default_asset_name_matches_the_runtime_resource_namespace(self):
        with TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(BUILD_SCRIPT)],
                cwd=directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=result.stderr)
            self.assertTrue(
                (Path(directory) / "dist" / "MarkdownReader.sublime-package").is_file()
            )

    def test_builds_a_deterministic_runtime_only_sublime_package(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.sublime-package"
            second = root / "second.sublime-package"
            checksums = root / "SHA256SUMS"

            self._build(first, checksum_output=checksums)
            self._build(second)

            self.assertEqual(self._sha256(first), self._sha256(second))
            self.assertEqual(
                "{}  {}\n".format(self._sha256(first), first.name),
                checksums.read_text(encoding="utf-8"),
            )
            with zipfile.ZipFile(str(first)) as archive:
                names = set(archive.namelist())
                self.assertTrue(
                    all(
                        info.date_time == (1980, 1, 1, 0, 0, 0)
                        for info in archive.infolist()
                    )
                )

            self.assertTrue(
                {
                    ".python-version",
                    "markdown_reader_plugin.py",
                    "Default.sublime-commands",
                    "Main.sublime-menu",
                    "MarkdownReader.sublime-settings",
                    "markdown_reader/rendering.py",
                    "markdown_reader/vendor/mistune/__init__.py",
                    "markdown_reader/vendor/mistune/LICENSE",
                    "renderer/server.js",
                    "renderer/browser-preview.js",
                    "README.md",
                    "README.zh-CN.md",
                    "CHANGELOG.md",
                    "LICENSE",
                }.issubset(names)
            )
            for forbidden in (
                ".git/",
                ".github/",
                ".venv/",
                "docs/",
                "scripts/",
                "tests/",
                "renderer/src/",
                "renderer/scripts/",
                "renderer/node_modules/",
            ):
                self.assertFalse(any(name.startswith(forbidden) for name in names))
            self.assertNotIn("renderer/package.json", names)
            self.assertNotIn("renderer/package-lock.json", names)
            self.assertNotIn("requirements-dev.txt", names)
            self.assertNotIn("pyproject.toml", names)

    @staticmethod
    def _sha256(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _build(self, destination, checksum_output=None):
        command = [sys.executable, str(BUILD_SCRIPT), "--output", str(destination)]
        if checksum_output is not None:
            command.extend(["--checksum-output", str(checksum_output)])
        result = subprocess.run(
            command,
            cwd=str(REPOSITORY_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, msg=result.stderr)
        self.assertTrue(destination.is_file())
        self.assertIn("SHA256", result.stdout)


if __name__ == "__main__":
    unittest.main()
