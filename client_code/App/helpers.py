"""Display-only helpers for the Anvil frontend."""

from datetime import datetime
from typing import Any


STATUS_TEXT = {
    "green": ("✓ Bezpiecznie", "op-status-safe"),
    "yellow": ("! Uwaga", "op-status-warning"),
    "red": ("× Zablokowane", "op-status-danger"),
}


def value(data: Any, *keys: str, default: Any = "—") -> Any:
    if not isinstance(data, dict):
        return default
    for key in keys:
        candidate = data.get(key)
        if candidate not in (None, ""):
            return candidate
    return default


def status_copy(status):
    return STATUS_TEXT.get(status, ("i Informacyjnie", "op-status-neutral"))


def format_number(number, suffix=""):
    if number in (None, ""):
        return "—"
    try:
        rendered = f"{float(number):g}"
    except (TypeError, ValueError):
        rendered = str(number)
    return f"{rendered}{suffix}"


def format_datetime(value_to_format):
    if value_to_format in (None, ""):
        return "—"
    if isinstance(value_to_format, datetime):
        return value_to_format.strftime("%d.%m.%Y, %H:%M")
    text = str(value_to_format).replace("T", ", ")
    if text.endswith("Z"):
        text = text[:-1]
    return text[:22]


def result_message(result, fallback="Nie udało się wykonać operacji."):
    if not isinstance(result, dict):
        return fallback
    return result.get("message") or fallback


def result_data(result, default=None):
    if isinstance(result, dict) and result.get("ok"):
        return result.get("data", default)
    return default


def normalise_task(task):
    task = task if isinstance(task, dict) else {}
    parcels = task.get("kwatery") or task.get("parcels") or []
    if not isinstance(parcels, list):
        parcels = [parcels]
    first_parcel = parcels[0] if parcels and isinstance(parcels[0], dict) else {}
    recipe = task.get("recipe") if isinstance(task.get("recipe"), dict) else {}
    worker = task.get("worker") if isinstance(task.get("worker"), dict) else {}
    weather = task.get("weather_snapshot") or task.get("weather") or {}
    suitability = weather.get("suitability", {}) if isinstance(weather, dict) else {}
    return {
        "id": value(task, "id", "task_id", default=""),
        "name": value(task, "name", default="Zabieg ochronny"),
        "parcel": value(first_parcel, "name", "label", "nr_dzialki_ewidencyjnej", default=value(task, "parcel_number", "nr_dzialki_ewidencyjnej")),
        "reason": value(task, "przyczyna", "reason", default="—"),
        "recipe_name": value(recipe, "name", default=value(task, "recipe_name", default="Receptura")),
        "recipe_id": value(recipe, "id", "recipe_id", default=value(task, "recipe_id", default="")),
        "worker_name": value(worker, "full_name", "name", default=value(task, "executor_name", default="—")),
        "scheduled_at": format_datetime(value(task, "scheduled_at", "scheduled_time", "planned_at")),
        "status": value(task, "status", "state", default="created"),
        "weather_status": suitability.get("status") if isinstance(suitability, dict) else value(weather, "status", default="unknown"),
        "karencja_until": value(first_parcel, "karencja_until", default=value(task, "karencja_until")),
    }


def normalise_recipe(recipe):
    recipe = recipe if isinstance(recipe, dict) else {}
    return {
        "id": value(recipe, "id", "recipe_id", default=""),
        "name": value(recipe, "name", default="Receptura bez nazwy"),
        "target": value(recipe, "target", default="—"),
        "water_l_per_ha": value(recipe, "water_l_per_ha", default="—"),
        "products_count": len(recipe.get("products", [])) if isinstance(recipe.get("products"), list) else value(recipe, "products_count", default="—"),
    }
