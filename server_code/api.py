"""Anvil Server Module gateway for the external opryski-recipes MVP."""

import anvil.server

from uplink_client import MvpClient


def _client():
    return MvpClient()


def _request(method, path, *, payload=None, query=None, clear_on_401=True, read_only=False):
    result = _client().request(method, path, payload=payload, query=query, read_only=read_only)
    if clear_on_401 and result.get("code") == 401:
        anvil.server.session.clear()
    return result


def _require_login():
    if not anvil.server.session.get("mvp_jwt"):
        return {
            "ok": False,
            "code": 401,
            "kind": "session_expired",
            "message": "Zaloguj się, aby kontynuować.",
        }
    return None


def _path_value(value):
    # IDs are UUID strings in the MVP; rejecting slashes also prevents path
    # injection if a client passes an unexpected value.
    if not isinstance(value, str) or not value.strip() or "/" in value:
        return None
    return value.strip()


@anvil.server.callable
def mvp_login(email, password):
    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Podaj email i hasło."}

    result = _request(
        "POST",
        "/auth/login",
        payload={"username": email.strip(), "password": password, "grant_type": "password"},
    )
    if not result.get("ok"):
        return result

    data = result.get("data") or {}
    token = data.get("access_token") or data.get("token") or data.get("jwt")
    if not token:
        return {
            "ok": False,
            "code": 502,
            "kind": "upstream",
            "message": "Odpowiedź logowania nie zawiera tokenu sesji.",
        }

    anvil.server.session.set("mvp_jwt", token)
    me_result = _request("GET", "/auth/me")
    if me_result.get("ok"):
        return {"ok": True, "data": me_result.get("data")}
    # Never leave a token in the Anvil session when the server cannot validate
    # it. Returning a fallback user here would make the client appear logged in
    # while every subsequent protected request is unauthenticated.
    anvil.server.session.clear()
    return {
        "ok": False,
        "code": me_result.get("code", 502),
        "kind": "session_validation",
        "message": "Nie udało się potwierdzić sesji po zalogowaniu.",
        "detail": me_result,
    }


@anvil.server.callable
def mvp_register(email, password, full_name):
    if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password or not isinstance(full_name, str) or not full_name.strip():
        return {"ok": False, "code": 422, "kind": "validation", "message": "Podaj email, hasło i imię i nazwisko."}
    return _request(
        "POST",
        "/auth/register",
        payload={"email": email.strip(), "password": password, "full_name": full_name.strip()},
    )


@anvil.server.callable
def mvp_logout():
    anvil.server.session.clear()
    return {"ok": True, "data": None}


@anvil.server.callable
def mvp_session():
    missing = _require_login()
    if missing:
        return missing
    return _request("GET", "/auth/me")


@anvil.server.callable
def mvp_me():
    return mvp_session()


@anvil.server.callable
def mvp_dashboard():
    missing = _require_login()
    if missing:
        return missing

    me = _request("GET", "/auth/me")
    if not me.get("ok"):
        return me
    kwatery = _request("GET", "/kwatery")
    if not kwatery.get("ok"):
        return kwatery
    tasks = _request("GET", "/spray-tasks")
    if not tasks.get("ok"):
        return tasks

    weather = {"ok": True, "data": None}
    first_parcel = _first_item(kwatery.get("data"))
    coords = _coordinates(first_parcel)
    if coords:
        weather = _request(
            "GET",
            "/weather/current",
            query={"lat": coords[0], "lon": coords[1]},
        )
        if not weather.get("ok"):
            # A weather outage should be visible but should not hide the
            # authenticated task and parcel data.
            weather = {"ok": False, "data": None, "weather_error": weather}

    return {
        "ok": True,
        "data": {
            "me": me.get("data"),
            "kwatery": _unwrap_collection(kwatery.get("data")),
            "tasks": _unwrap_collection(tasks.get("data")),
            "weather": weather.get("data"),
            "weather_error": weather.get("weather_error"),
        },
    }


@anvil.server.callable
def mvp_weather(latitude, longitude):
    missing = _require_login()
    if missing:
        return missing
    if latitude in (None, "") or longitude in (None, ""):
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak współrzędnych gospodarstwa."}
    return _request("GET", "/weather/current", query={"lat": latitude, "lon": longitude})


@anvil.server.callable
def mvp_kwatery():
    missing = _require_login()
    return missing or _request("GET", "/kwatery")


@anvil.server.callable
def mvp_create_kwatera(payload):
    missing = _require_login()
    return missing or _request("POST", "/kwatery", payload=payload)


@anvil.server.callable
def mvp_tasks():
    missing = _require_login()
    return missing or _request("GET", "/spray-tasks")


@anvil.server.callable
def mvp_worker_my_tasks():
    missing = _require_login()
    return missing or _request("GET", "/workers/me/tasks")


@anvil.server.callable
def mvp_create_task(payload):
    missing = _require_login()
    if missing:
        return missing
    snapshot = mvp_server_weather_snapshot(payload)
    if not snapshot.get("ok"):
        return snapshot
    task_payload = dict(payload or {})
    task_payload["weather_snapshot"] = snapshot.get("data")
    return _request("POST", "/spray-tasks", payload=task_payload)


@anvil.server.callable
def mvp_task_action(task_id, action, payload=None):
    missing = _require_login()
    if missing:
        return missing
    task_id = _path_value(task_id)
    action = _path_value(action)
    if not task_id or not action:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnego zadania lub akcji."}
    action_paths = {
        "dispatch": "dispatch",
        "worker-confirm": "worker-confirm",
        "owner-authorize": "owner-authorize",
        "execution-started": "execution-started",
        "execution-completed": "execution-completed",
        "cancel": "cancel",
    }
    action_path = action_paths.get(action)
    if not action_path:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Niepoprawna akcja zadania."}
    return _request("POST", f"/spray-tasks/{task_id}/{action_path}", payload=payload or {})


@anvil.server.callable
def mvp_task_audit(task_id):
    missing = _require_login()
    if missing:
        return missing
    task_id = _path_value(task_id)
    if not task_id:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnego zadania."}
    return _request("GET", f"/spray-tasks/{task_id}/audit")


@anvil.server.callable
def mvp_recipes():
    missing = _require_login()
    return missing or _request("GET", "/recipes")


@anvil.server.callable
def mvp_create_recipe(payload):
    missing = _require_login()
    return missing or _request("POST", "/recipes", payload=payload)


@anvil.server.callable
def mvp_recipe_compute(recipe_id, area_ha):
    missing = _require_login()
    if missing:
        return missing
    recipe_id = _path_value(recipe_id)
    if not recipe_id:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnej receptury."}
    return _request("POST", f"/recipes/{recipe_id}/compute", query={"area_ha": area_ha})


@anvil.server.callable
def mvp_recipe_validation(recipe_id):
    missing = _require_login()
    if missing:
        return missing
    recipe_id = _path_value(recipe_id)
    return _request("GET", f"/recipes/{recipe_id}/validation") if recipe_id else {
        "ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnej receptury."
    }


@anvil.server.callable
def mvp_recipe_copy(recipe_id):
    missing = _require_login()
    if missing:
        return missing
    recipe_id = _path_value(recipe_id)
    return _request("POST", f"/recipes/{recipe_id}/copy", payload={}) if recipe_id else {
        "ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnej receptury."
    }


@anvil.server.callable
def mvp_recipe_export(recipe_id, export_format="json"):
    missing = _require_login()
    if missing:
        return missing
    recipe_id = _path_value(recipe_id)
    if not recipe_id:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnej receptury."}
    export_format = str(export_format or "").strip().lower()
    if export_format not in {"json", "text"}:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Format eksportu musi być json albo text."}
    return _request("GET", f"/recipes/{recipe_id}/export", query={"format": export_format})


@anvil.server.callable
def mvp_workers():
    missing = _require_login()
    return missing or _request("GET", "/workers")


@anvil.server.callable
def mvp_create_worker(email, password, full_name):
    missing = _require_login()
    if missing:
        return missing
    if not email or not password or not full_name:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Podaj email, hasło i imię i nazwisko."}
    return _request("POST", "/workers", payload={"email": email, "password": password, "full_name": full_name})


@anvil.server.callable
def mvp_catalog(limit=50, offset=0):
    missing = _require_login()
    if missing:
        return missing
    try:
        bounded_limit = min(max(int(limit), 1), 50)
        bounded_offset = max(int(offset), 0)
    except (TypeError, ValueError):
        return {"ok": False, "code": 422, "kind": "validation", "message": "Stronicowanie katalogu jest niepoprawne."}
    return _request("GET", "/catalog/products", query={"limit": bounded_limit, "offset": bounded_offset})


@anvil.server.callable
def mvp_inventory():
    missing = _require_login()
    if missing:
        return missing
    return _request("GET", "/inventory")


@anvil.server.callable
def mvp_inventory_lots():
    return mvp_inventory()


@anvil.server.callable
def mvp_inventory_movements():
    missing = _require_login()
    return missing or _request("GET", "/inventory/movements")


@anvil.server.callable
def mvp_inventory_reservation(reservation_id):
    missing = _require_login()
    if missing:
        return missing
    reservation_id = _path_value(reservation_id)
    if not reservation_id:
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak poprawnej rezerwacji."}
    return _request("GET", f"/inventory/reservations/{reservation_id}")


@anvil.server.callable
def mvp_inventory_receipt(payload):
    missing = _require_login()
    return missing or _request("POST", "/inventory/lots", payload=payload)


@anvil.server.callable
def mvp_worker_me():
    missing = _require_login()
    return missing or _request("GET", "/workers/me")


@anvil.server.callable
def mvp_server_weather_snapshot(payload=None, longitude=None):
    missing = _require_login()
    if missing:
        return missing
    if longitude is not None and not isinstance(payload, dict):
        payload = {"lat": payload, "lon": longitude}
    if not isinstance(payload, dict):
        return {"ok": False, "code": 422, "kind": "validation", "message": "Brak danych do snapshotu pogody."}
    return _request(
        "POST",
        "/weather/server-snapshot",
        payload=payload,
        read_only=True,
    )




def _first_item(value):
    if isinstance(value, dict):
        for key in ("items", "results", "data"):
            if isinstance(value.get(key), list) and value[key]:
                return value[key][0]
        return None
    return value[0] if isinstance(value, list) and value else None


def _unwrap_collection(value):
    if isinstance(value, dict):
        for key in ("items", "results", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    return value if isinstance(value, list) else []


def _coordinates(parcel):
    if not isinstance(parcel, dict):
        return None
    for lat_key, lon_key in (("latitude", "longitude"), ("lat", "lon")):
        if parcel.get(lat_key) is not None and parcel.get(lon_key) is not None:
            return parcel[lat_key], parcel[lon_key]
    centroid = parcel.get("centroid")
    if isinstance(centroid, dict) and centroid.get("lat") is not None and centroid.get("lon") is not None:
        return centroid["lat"], centroid["lon"]
    return None
