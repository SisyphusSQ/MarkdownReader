import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from markdown_reader.security import SecurityPolicy


class SecurityPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = SecurityPolicy()

    def test_default_resource_limits_are_explicit(self):
        self.assertEqual(2 * 1024 * 1024, self.policy.max_source_bytes)
        self.assertEqual(20 * 1024 * 1024, self.policy.max_local_image_bytes)

    def test_source_size_is_measured_as_utf8_bytes(self):
        policy = SecurityPolicy(max_source_bytes=5)

        self.assertIsNone(policy.source_rejection_reason("12345"))
        self.assertEqual(
            "Markdown source exceeds the 5-byte preview limit",
            policy.source_rejection_reason("你好"),
        )

    def test_allows_only_absolute_http_links_with_hostname(self):
        self.assertTrue(self.policy.allows_link("https://example.com/guide"))
        self.assertTrue(self.policy.allows_link("HTTP://example.com"))

        for target in (
            "guide.md",
            "//example.com/guide",
            "mailto:reader@example.com",
            "file:///tmp/guide.md",
            "data:text/html,unsafe",
            "subl:save",
            "https:///missing-host",
            "https://user:secret@example.com/private",
            "https://example.com\\@evil.example/path",
            "https://example.com/path with space",
            "https://example.com/path\nnext",
            "https://[invalid",
        ):
            with self.subTest(target=target):
                self.assertFalse(self.policy.allows_link(target))

    def test_resolves_supported_relative_image(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "assets" / "diagram.png"
            image.parent.mkdir()
            image.touch()

            resolved, reason = self.policy.resolve_local_image(
                "assets/diagram.png",
                str(root / "notes.md"),
            )

        self.assertEqual(image.resolve(), resolved)
        self.assertIsNone(reason)

    def test_blocks_every_non_local_image_target(self):
        for target in (
            "https://example.com/image.png",
            "//example.com/image.png",
            "file:///tmp/image.png",
            "data:image/png;base64,AAAA",
            "subl:save",
            "https://[invalid",
        ):
            with self.subTest(target=target):
                resolved, reason = self.policy.resolve_local_image(target, "/tmp/notes.md")
                self.assertIsNone(resolved)
                self.assertEqual("remote images are blocked", reason)

    def test_blocks_paths_outside_markdown_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            outside = root / "outside.png"
            outside.touch()

            for target in ("../outside.png", str(outside)):
                with self.subTest(target=target):
                    resolved, reason = self.policy.resolve_local_image(
                        target,
                        str(docs / "notes.md"),
                    )
                    self.assertIsNone(resolved)
                    self.assertEqual("local image is outside the Markdown directory", reason)

    def test_blocks_symlink_that_escapes_markdown_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            outside = root / "outside.png"
            outside.touch()
            link = docs / "linked.png"
            link.symlink_to(outside)

            resolved, reason = self.policy.resolve_local_image(
                "linked.png",
                str(docs / "notes.md"),
            )

        self.assertIsNone(resolved)
        self.assertEqual("local image is outside the Markdown directory", reason)

    def test_rejects_image_larger_than_limit(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "large.png"
            image.touch()
            os.truncate(str(image), 9)
            policy = SecurityPolicy(max_local_image_bytes=8)

            resolved, reason = policy.resolve_local_image("large.png", str(root / "notes.md"))

        self.assertIsNone(resolved)
        self.assertEqual("local image exceeds the 8-byte preview limit", reason)

    def test_invalid_local_path_becomes_placeholder_reason(self):
        resolved, reason = self.policy.resolve_local_image("bad%00name.png", "/tmp/notes.md")

        self.assertIsNone(resolved)
        self.assertEqual("local image path is invalid", reason)


if __name__ == "__main__":
    unittest.main()
