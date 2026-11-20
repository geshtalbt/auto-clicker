"""Global hotkey listener for starting/stopping the auto-clicker.

Uses pynput to listen for a configurable key even when the window is hidden
or another application is focused. Includes conflict protection: the hotkey
cannot be set to keys that would break normal system behavior (e.g. Esc).
"""

from __future__ import annotations

import threading
from typing import Callable

from pynput.keyboard import Key, KeyCode, Listener


# Keys reserved / disallowed as hotkeys to avoid conflicts.
DISALLOWED_KEYS = {
    Key.esc,
    Key.ctrl_l,
    Key.ctrl_r,
    Key.alt_l,
    Key.alt_r,
    Key.shift_l,
    Key.shift_r,
    Key.cmd_l,
    Key.cmd_r,
}

# Map of user-friendly names to pynput keys for the UI selector.
KEY_NAMES = {
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
}


def normalize_hotkey(value: str) -> str:
    return str(value).strip().lower()


def parse_key(value: str) -> Key | KeyCode | None:
    """Parse a hotkey string like 'f6' or 'a' into a pynput key."""
    value = normalize_hotkey(value)
    if value in KEY_NAMES:
        return KEY_NAMES[value]
    if len(value) == 1 and value.isalnum():
        return KeyCode.from_char(value)
    return None


def key_to_label(key: Key | KeyCode | None) -> str:
    if key is None:
        return "—"
    if isinstance(key, KeyCode):
        return key.char.upper() if key.char else str(key)
    name = key.name if hasattr(key, "name") else str(key)
    return name.upper()


def is_allowed(key: Key | KeyCode | None) -> bool:
    if key is None:
        return False
    return key not in DISALLOWED_KEYS


class HotkeyListener:
    """Listens for the global hotkey and invokes a callback."""

    def __init__(self, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._key: Key | KeyCode | None = parse_key("f6")
        self._listener: Listener | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pressed_keys: set = set()

    def set_hotkey(self, value: str) -> bool:
        key = parse_key(value)
        if key is None or not is_allowed(key):
            return False
        with self._lock:
            self._key = key
        self._restart()
        return True

    def get_hotkey(self) -> str:
        with self._lock:
            key = self._key
        return key_to_label(key).lower()

    def _restart(self) -> None:
        self.stop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._listener = Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.start()
            self._listener.join()
        except Exception:
            self._listener = None

    def _on_press(self, key) -> None:
        with self._lock:
            target = self._key
        if target is None:
            return
        if key == target:
            self._pressed_keys.add(key)
            # Trigger on press (single key).
            if not isinstance(key, KeyCode) or len(self._pressed_keys) == 1:
                self._safe_callback()

    def _on_release(self, key) -> None:
        self._pressed_keys.discard(key)

    def _safe_callback(self) -> None:
        try:
            self._callback()
        except Exception:
            pass

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._pressed_keys.clear()
