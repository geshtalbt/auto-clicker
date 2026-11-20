"""Application settings persistence."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any


APP_NAME = "Auto Clicker"
SETTINGS_FILE = os.path.join(
    os.path.expanduser("~"), ".autoclicker_settings.json"
)


@dataclass
class Settings:
    interval: float = 1.0
    button: str = "left"  # left | right | middle
    hotkey: str = "f6"
    random_chance: bool = False
    random_chance_percent: float = 50.0
    click_count: int = 0
    minimize_to_tray: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


def load_settings() -> Settings:
    if not os.path.exists(SETTINGS_FILE):
        return Settings()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Settings.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError):
        return Settings()


def save_settings(settings: Settings) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)
    except OSError:
        pass
