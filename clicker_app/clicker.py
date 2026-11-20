"""Core auto-clicker logic.

Handles mouse clicking at a configurable interval, mouse button selection,
random-chance skipping, click counting, and thread-safe start/stop control.
"""

from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass
from typing import Callable

from pynput.mouse import Button, Controller


@dataclass
class ClickerState:
    running: bool = False
    interval: float = 1.0
    button: str = "left"  # left | right | middle
    random_chance: bool = False
    random_chance_percent: float = 50.0
    click_count: int = 0


class Clicker:
    """Background auto-clicker that runs on a dedicated thread."""

    def __init__(self, on_status_change: Callable[[bool], None] | None = None) -> None:
        self._mouse = Controller()
        self._lock = threading.Lock()
        self._state = ClickerState()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._on_status_change = on_status_change

    # ------------------------------------------------------------------ config
    def configure(
        self,
        *,
        interval: float | None = None,
        button: str | None = None,
        random_chance: bool | None = None,
        random_chance_percent: float | None = None,
    ) -> None:
        with self._lock:
            if interval is not None:
                self._state.interval = max(0.01, float(interval))
            if button is not None:
                self._state.button = button
            if random_chance is not None:
                self._state.random_chance = bool(random_chance)
            if random_chance_percent is not None:
                self._state.random_chance_percent = max(
                    0.0, min(100.0, float(random_chance_percent))
                )

    def reset_count(self) -> None:
        with self._lock:
            self._state.click_count = 0

    # ------------------------------------------------------------------ status
    def is_running(self) -> bool:
        with self._lock:
            return self._state.running

    def get_state(self) -> ClickerState:
        with self._lock:
            return ClickerState(**self._state.__dict__)

    # ------------------------------------------------------------------ control
    def start(self) -> bool:
        """Start clicking. Returns True if started, False if already running."""
        with self._lock:
            if self._state.running:
                return False
            self._state.running = True
            self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._notify_status(True)
        return True

    def stop(self) -> bool:
        """Stop clicking. Returns True if stopped, False if not running."""
        with self._lock:
            if not self._state.running:
                return False
            self._state.running = False
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._notify_status(False)
        return True

    def toggle(self) -> bool:
        with self._lock:
            running = self._state.running
        if running:
            return self.stop()
        return self.start()

    # ------------------------------------------------------------------ internals
    def _notify_status(self, running: bool) -> None:
        if self._on_status_change is not None:
            try:
                self._on_status_change(running)
            except Exception:
                pass

    def _should_click(self) -> bool:
        state = self.get_state()
        if not state.random_chance:
            return True
        return random.random() * 100.0 < state.random_chance_percent

    def _run(self) -> None:
        """Main click loop — precise interval timing, no UI blocking."""
        while not self._stop_event.is_set():
            state = self.get_state()
            if not state.running:
                break

            if self._should_click():
                try:
                    button = _button_for(state.button)
                    self._mouse.click(button)
                    with self._lock:
                        self._state.click_count += 1
                except Exception:
                    pass

            # Sleep in small chunks so stop is responsive while keeping
            # interval accuracy.
            interval = max(0.01, state.interval)
            deadline = time.monotonic() + interval
            while not self._stop_event.is_set():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._stop_event.wait(min(remaining, 0.005))


def _button_for(name: str) -> Button:
    mapping = {"left": Button.left, "right": Button.right, "middle": Button.middle}
    return mapping.get(name, Button.left)
