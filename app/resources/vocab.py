"""In-memory loader helpers for bundled H3 vocabularies and reference data."""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

_RESOURCES_DIR = Path(__file__).resolve().parent
_CACHE: dict[str, Any] = {}

def load_resource(filename: str) -> Any:
    """Load JSON resource from app/resources/ with simple in-memory caching."""
    if filename not in _CACHE:
        file_path = _RESOURCES_DIR / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Resource {filename} not found in {_RESOURCES_DIR}")
        with open(file_path, "r", encoding="utf-8") as f:
            _CACHE[filename] = json.load(f)
    return _CACHE[filename]

def get_camera_moves() -> dict[str, Any]:
    return load_resource("camera_moves.json")

def get_mood_words() -> dict[str, list[str]]:
    return load_resource("mood_words.json")

def get_sound_lexicon() -> list[str]:
    return load_resource("sound_lexicon.json")

def get_scripts() -> dict[str, dict[str, Any]]:
    return load_resource("scripts.json")

def get_styles() -> dict[str, Any]:
    return load_resource("styles.json")

def get_voices() -> dict[str, dict[str, Any]]:
    return load_resource("voices.json")

def get_deliveries() -> dict[str, dict[str, Any]]:
    return load_resource("deliveries.json")

def get_shot_budgets() -> list[dict[str, Any]]:
    return load_resource("shot_budgets.json")

def get_task_types() -> list[str]:
    return load_resource("task_types.json")

def get_retention_markers() -> dict[str, list[str]]:
    return load_resource("retention_markers.json")

def get_accents() -> list[str]:
    return load_resource("accents.json")

# Standard house sentence
HOUSE_SENTENCE = "The audio contains only the spoken dialogue, with no background music, no ambience, and no sound effects."
