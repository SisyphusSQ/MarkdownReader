import unittest

from markdown_reader.refresh import DebouncedRefreshScheduler, LivePreviewController


class FakeScheduler:
    def __init__(self):
        self.calls = []

    def __call__(self, callback, delay_ms):
        self.calls.append((callback, delay_ms))


class DebouncedRefreshSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = FakeScheduler()
        self.debouncer = DebouncedRefreshScheduler(self.scheduler)

    def test_runs_callback_after_default_delay(self):
        refreshed = []

        self.debouncer.schedule((11, 22), lambda: refreshed.append("done"))

        self.assertEqual(1, len(self.scheduler.calls))
        callback, delay_ms = self.scheduler.calls[0]
        self.assertEqual(250, delay_ms)
        callback()
        self.assertEqual(["done"], refreshed)

    def test_only_latest_callback_runs_for_same_source(self):
        refreshed = []

        self.debouncer.schedule((11, 22), lambda: refreshed.append("first"))
        self.debouncer.schedule((11, 22), lambda: refreshed.append("second"))

        first_callback = self.scheduler.calls[0][0]
        second_callback = self.scheduler.calls[1][0]
        first_callback()
        second_callback()

        self.assertEqual(["second"], refreshed)

    def test_old_callback_stays_stale_after_new_debounce_cycle(self):
        refreshed = []

        self.debouncer.schedule((11, 22), lambda: refreshed.append("first"))
        self.debouncer.schedule((11, 22), lambda: refreshed.append("second"))
        first_callback = self.scheduler.calls[0][0]
        second_callback = self.scheduler.calls[1][0]
        second_callback()

        self.debouncer.schedule((11, 22), lambda: refreshed.append("third"))
        third_callback = self.scheduler.calls[2][0]
        first_callback()
        third_callback()

        self.assertEqual(["second", "third"], refreshed)

    def test_cancel_discards_pending_callback(self):
        refreshed = []

        self.debouncer.schedule((11, 22), lambda: refreshed.append("unexpected"))
        self.debouncer.cancel((11, 22))
        self.scheduler.calls[0][0]()

        self.assertEqual([], refreshed)

    def test_reads_the_current_configured_delay_for_each_schedule(self):
        configured_delay = [300]
        debouncer = DebouncedRefreshScheduler(
            self.scheduler,
            delay_provider=lambda: configured_delay[0],
        )

        debouncer.schedule((11, 22), lambda: None)
        configured_delay[0] = 700
        debouncer.schedule((33, 44), lambda: None)

        self.assertEqual([300, 700], [call[1] for call in self.scheduler.calls])


class FakeWindow:
    def id(self):
        return 11


class FakeView:
    def __init__(self, window):
        self.owner = window

    def id(self):
        return 22

    def window(self):
        return self.owner


class FakePreviewManager:
    def __init__(self):
        self.preview_open = True
        self.refreshes = []

    def has_preview(self, window, view):
        return self.preview_open

    def refresh_preview(self, window, view, region_factory):
        self.refreshes.append((window, view, region_factory))


class LivePreviewControllerTests(unittest.TestCase):
    def setUp(self):
        self.window = FakeWindow()
        self.view = FakeView(self.window)
        self.manager = FakePreviewManager()
        self.scheduler = FakeScheduler()
        self.debouncer = DebouncedRefreshScheduler(self.scheduler)
        self.region_factory = object()
        self.controller = LivePreviewController(
            self.manager,
            self.debouncer,
            self.region_factory,
        )

    def test_modified_source_with_preview_is_refreshed_after_debounce(self):
        self.controller.on_modified(self.view)

        self.assertEqual(1, len(self.scheduler.calls))
        self.scheduler.calls[0][0]()

        self.assertEqual(
            [(self.window, self.view, self.region_factory)],
            self.manager.refreshes,
        )

    def test_source_without_preview_is_not_scheduled(self):
        self.manager.preview_open = False

        self.controller.on_modified(self.view)

        self.assertEqual([], self.scheduler.calls)

    def test_detached_source_is_not_refreshed(self):
        self.controller.on_modified(self.view)
        self.view.owner = None

        self.scheduler.calls[0][0]()

        self.assertEqual([], self.manager.refreshes)

    def test_preview_closed_during_debounce_is_not_refreshed(self):
        self.controller.on_modified(self.view)
        self.manager.preview_open = False

        self.scheduler.calls[0][0]()

        self.assertEqual([], self.manager.refreshes)


if __name__ == "__main__":
    unittest.main()
