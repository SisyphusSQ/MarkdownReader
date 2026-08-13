"""Debounce source changes before refreshing an open preview."""


class DebouncedRefreshScheduler:
    """Run only the newest scheduled callback for each source key."""

    def __init__(self, schedule, delay_ms=250, delay_provider=None):
        self._schedule = schedule
        self._delay_ms = delay_ms
        self._delay_provider = delay_provider
        self._generation = 0
        self._pending = {}

    def schedule(self, key, callback):
        """Schedule a callback and invalidate any older callback for the key."""
        self._generation += 1
        generation = self._generation
        self._pending[key] = generation

        def run_if_current():
            if self._pending.get(key) != generation:
                return
            del self._pending[key]
            callback()

        delay_ms = (
            self._delay_provider()
            if self._delay_provider is not None
            else self._delay_ms
        )
        self._schedule(run_if_current, delay_ms)

    def cancel(self, key):
        """Invalidate the currently pending callback for a source key."""
        self._pending.pop(key, None)


class LivePreviewController:
    """Route source modifications to an open preview after a debounce."""

    def __init__(self, preview_manager, debouncer, region_factory):
        self._preview_manager = preview_manager
        self._debouncer = debouncer
        self._region_factory = region_factory

    def on_modified(self, source_view):
        """Schedule a refresh only when this source currently has a preview."""
        window = source_view.window()
        if window is None or not self._preview_manager.has_preview(window, source_view):
            return

        key = (window.id(), source_view.id())
        self._debouncer.schedule(key, lambda: self._refresh(source_view))

    def _refresh(self, source_view):
        window = source_view.window()
        if window is None or not self._preview_manager.has_preview(window, source_view):
            return
        self._preview_manager.refresh_preview(window, source_view, self._region_factory)
