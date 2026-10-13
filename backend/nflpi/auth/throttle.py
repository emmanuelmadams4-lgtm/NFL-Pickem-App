"""One sliding-window limit shared by the public passkey routes."""

import threading
import time
from collections import deque

LIMIT = 30
WINDOW_S = 60.0

# ponytail: per process, resets on restart. Move it to the database if the app ever runs more than one process.
_calls: deque[float] = deque()
_lock = threading.Lock()


def allow() -> bool:
    """Record one call; False when LIMIT calls already happened in the last WINDOW_S seconds."""
    now = time.monotonic()
    with _lock:
        while _calls and now - _calls[0] >= WINDOW_S:
            _calls.popleft()
        if len(_calls) >= LIMIT:
            return False
        _calls.append(now)
        return True


def reset() -> None:
    with _lock:
        _calls.clear()
