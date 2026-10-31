"""Thread-safe wrapper over the existing Calls ledger (runs/<id>/calls.json)."""
import threading


class LockedCalls:
    def __init__(self, calls):
        self._calls, self._lock = calls, threading.Lock()

    def begin(self, *a, **k):
        with self._lock:
            return self._calls.begin(*a, **k)

    def finish(self, *a, **k):
        with self._lock:
            return self._calls.finish(*a, **k)

    def fail(self, *a, **k):
        with self._lock:
            return self._calls.fail(*a, **k)
