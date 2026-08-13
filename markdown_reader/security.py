"""Security policy for rendering untrusted Markdown resources."""

from pathlib import Path
from urllib.parse import unquote, urlsplit

_LOCAL_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png"}


class SecurityPolicy:
    """Centralize protocol and resource limits for untrusted Markdown."""

    def __init__(
        self,
        max_source_bytes=2 * 1024 * 1024,
        max_local_image_bytes=20 * 1024 * 1024,
        allow_remote_images=False,
    ):
        self.max_source_bytes = max_source_bytes
        self.max_local_image_bytes = max_local_image_bytes
        self.allow_remote_images = allow_remote_images

    def source_rejection_reason(self, source):
        """Return a diagnostic when a Markdown source exceeds its byte limit."""
        if len(source.encode("utf-8")) > self.max_source_bytes:
            return "Markdown source exceeds the {}-byte preview limit".format(
                self.max_source_bytes
            )
        return None

    def allows_link(self, target):
        """Allow only absolute HTTP(S) navigation with a hostname."""
        if any(character.isspace() for character in target) or "\\" in target:
            return False
        try:
            parsed = urlsplit(target)
        except ValueError:
            return False
        return (
            parsed.scheme.lower() in ("http", "https")
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )

    def resolve_local_image(self, target, source_path):
        """Return a supported local image path or a safe placeholder reason."""
        try:
            parsed = urlsplit(target)
        except ValueError:
            return None, "remote images are blocked"
        if parsed.scheme or parsed.netloc:
            return None, "remote images are blocked"

        try:
            image_path = Path(unquote(parsed.path)).expanduser()
            if not source_path:
                return None, "save the Markdown file to resolve this image"
            source_directory = Path(source_path).parent.resolve()
            if not image_path.is_absolute():
                image_path = source_directory / image_path
            image_path = image_path.resolve()
        except (OSError, RuntimeError, ValueError):
            return None, "local image path is invalid"

        try:
            image_path.relative_to(source_directory)
        except ValueError:
            return None, "local image is outside the Markdown directory"

        if image_path.suffix.lower() not in _LOCAL_IMAGE_EXTENSIONS:
            return None, "unsupported image format"

        try:
            stat_result = image_path.stat()
        except FileNotFoundError:
            return None, "local image not found"
        except OSError:
            return None, "local image is not accessible"

        if not image_path.is_file():
            return None, "local image is not a regular file"
        if stat_result.st_size > self.max_local_image_bytes:
            return None, "local image exceeds the {}-byte preview limit".format(
                self.max_local_image_bytes
            )
        return image_path, None

    def resolve_image_source(self, target, source_path):
        """Return a safe local file URI or explicitly allowed HTTPS image URL."""
        try:
            parsed = urlsplit(target)
            _ = parsed.port
        except ValueError:
            return None, "remote images are blocked"
        if parsed.scheme or parsed.netloc:
            if (
                self.allow_remote_images
                and parsed.scheme.lower() == "https"
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and not any(character.isspace() for character in target)
                and "\\" not in target
            ):
                return target, None
            return None, "remote images are blocked"

        image_path, reason = self.resolve_local_image(target, source_path)
        if reason:
            return None, reason
        return image_path.as_uri(), None


DEFAULT_SECURITY_POLICY = SecurityPolicy()
