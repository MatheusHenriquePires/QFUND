import json
from pathlib import Path
from typing import Optional

STORAGE = Path("generated/user_profile.json")

class UserService:
    def __init__(self):
        self._data = None
        self._load()

    def _load(self):
        try:
            if STORAGE.exists():
                with open(STORAGE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        except Exception:
            self._data = {}

    def _save(self):
        try:
            STORAGE.parent.mkdir(parents=True, exist_ok=True)
            with open(STORAGE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_profile(self) -> dict:
        return self._data or {}

    def set_profile(self, profile: dict):
        self._data = profile or {}
        self._save()

    def clear(self):
        self._data = {}
        self._save()
