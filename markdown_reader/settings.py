"""Validate MarkdownReader settings into one immutable runtime snapshot."""

import os
from dataclasses import dataclass

DEFAULT_REFRESH_DELAY_MS = 250
MIN_REFRESH_DELAY_MS = 50
MAX_REFRESH_DELAY_MS = 5000
REMOTE_IMAGE_POLICIES = ("blocked", "allow_https")


@dataclass(frozen=True)
class MarkdownReaderSettings:
    refresh_delay_ms: int
    remote_images: str
    math_single_dollar: bool
    node_path: str
    chrome_path: str
    warnings: tuple


def read_settings(values):
    """Return validated settings, preserving invalid inputs as warnings."""
    warnings = []

    refresh_delay_ms = values.get("refresh_delay_ms", DEFAULT_REFRESH_DELAY_MS)
    if (
        isinstance(refresh_delay_ms, bool)
        or not isinstance(refresh_delay_ms, int)
        or not MIN_REFRESH_DELAY_MS
        <= refresh_delay_ms
        <= MAX_REFRESH_DELAY_MS
    ):
        warnings.append(
            "refresh_delay_ms must be an integer from {} to {}; using {}".format(
                MIN_REFRESH_DELAY_MS,
                MAX_REFRESH_DELAY_MS,
                DEFAULT_REFRESH_DELAY_MS,
            )
        )
        refresh_delay_ms = DEFAULT_REFRESH_DELAY_MS

    remote_images = values.get("remote_images", "blocked")
    if remote_images not in REMOTE_IMAGE_POLICIES:
        warnings.append(
            "remote_images must be blocked or allow_https; using blocked"
        )
        remote_images = "blocked"

    math_single_dollar = values.get("math_single_dollar", False)
    if not isinstance(math_single_dollar, bool):
        warnings.append("math_single_dollar must be true or false; using false")
        math_single_dollar = False

    node_path = _optional_path(values, "node_path", warnings)
    chrome_path = _optional_path(values, "chrome_path", warnings)

    return MarkdownReaderSettings(
        refresh_delay_ms=refresh_delay_ms,
        remote_images=remote_images,
        math_single_dollar=math_single_dollar,
        node_path=node_path,
        chrome_path=chrome_path,
        warnings=tuple(warnings),
    )


def _optional_path(values, name, warnings):
    value = values.get(name, "")
    if not isinstance(value, str):
        warnings.append("{} must be an absolute path string; using auto-detect".format(name))
        return ""
    value = value.strip()
    if value and not os.path.isabs(value):
        warnings.append("{} must be an absolute path; using auto-detect".format(name))
        return ""
    return value
