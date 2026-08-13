"""Thread-safe bounded in-memory cache for special-block render results."""

import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderCacheKey:
    """All inputs that can change a Mermaid or MathJax image."""

    renderer: str
    version: str
    source: str
    theme: str
    width: int
    scale: int
    font_size: int = 0
    display: bool = False


class _PendingComputation:
    def __init__(self, generation):
        self.generation = generation
        self.event = threading.Event()
        self.value = None
        self.error = None


def estimate_render_entry_bytes(key, value):
    """Return a conservative in-process size estimate for one cache entry."""
    size = sys.getsizeof(key) + sys.getsizeof(value)
    size += sum(sys.getsizeof(field) for field in key.__dict__.values())
    value_fields = getattr(value, "__dict__", {})
    size += sum(sys.getsizeof(field) for field in value_fields.values())
    return size


class BoundedMemoryCache:
    """LRU cache bounded by both entry count and estimated memory use."""

    def __init__(
        self,
        max_entries=128,
        max_bytes=64 * 1024 * 1024,
        entry_size=estimate_render_entry_bytes,
    ):
        if max_entries <= 0 or max_bytes <= 0:
            raise ValueError("cache limits must be positive")
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._entry_size = entry_size
        self._entries = OrderedDict()
        self._pending = {}
        self._current_bytes = 0
        self._generation = 0
        self._lock = threading.Lock()

    @property
    def current_bytes(self):
        with self._lock:
            return self._current_bytes

    @property
    def entry_count(self):
        with self._lock:
            return len(self._entries)

    def get(self, key):
        """Return and promote a cached value, or ``None`` on a miss."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            self._entries.move_to_end(key)
            return entry[0]

    def get_or_compute(self, key, compute, should_store=lambda _value: True):
        """Return one cached/computed value and coalesce same-key work."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
                return entry[0], True

            pending = self._pending.get(key)
            if pending is None or pending.generation != self._generation:
                pending = _PendingComputation(self._generation)
                self._pending[key] = pending
                owner = True
            else:
                owner = False

        if not owner:
            pending.event.wait()
            if pending.error is not None:
                raise pending.error
            return pending.value, True

        try:
            value = compute()
            cacheable = bool(should_store(value))
            size = max(0, int(self._entry_size(key, value)))
        except BaseException as error:
            with self._lock:
                pending.error = error
                if self._pending.get(key) is pending:
                    self._pending.pop(key, None)
                pending.event.set()
            raise

        with self._lock:
            pending.value = value
            if (
                pending.generation == self._generation
                and cacheable
                and size <= self._max_bytes
            ):
                self._store_unlocked(key, value, size)
            if self._pending.get(key) is pending:
                self._pending.pop(key, None)
            pending.event.set()
        return value, False

    def clear(self):
        """Drop cached data without allowing older in-flight work to repopulate it."""
        with self._lock:
            self._entries.clear()
            self._current_bytes = 0
            self._generation += 1

    def _store_unlocked(self, key, value, size):
        previous = self._entries.pop(key, None)
        if previous is not None:
            self._current_bytes -= previous[1]
        self._entries[key] = (value, size)
        self._current_bytes += size

        while (
            len(self._entries) > self._max_entries
            or self._current_bytes > self._max_bytes
        ):
            _old_key, (_old_value, old_size) = self._entries.popitem(last=False)
            self._current_bytes -= old_size
