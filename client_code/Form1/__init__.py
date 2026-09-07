import json

import anvil.server
from anvil import handle

from ..App.helpers import format_number, result_data, result_message, status_copy, value
from ..App.state import AppState, call
from ._anvil_designer import Form1Template

class Form1(Form1Template):
  OWNER_VIEWS = {
    "panel": ("PANEL", "Dzisiaj w gospodarstwie", "owner_panel_view"),
    "maps": ("GOSPODARSTWO", "Mapy kwater", "owner_maps_view"),
    "sprays": ("OPERACJE", "Opryski", "owner_sprays_view"),
    "recipes": ("OPERACJE", "Receptury", "owner_recipes_view"),
    "recipe_tools": ("OPERACJE", "Narzędzia receptury", "owner_recipe_tools_view"),
    "workers": ("GOSPODARSTWO", "Pracownicy", "owner_workers_view"),
    "catalog": ("GOSPODARSTWO", "Katalog środków", "owner_catalog_view"),
    "inventory": ("GOSPODARSTWO", "Magazyn", "owner_inventory_view"),
    "weather": ("GOSPODARSTWO", "Pogoda", "owner_weather_view"),
    "reports": ("SYSTEM", "Raporty", "owner_reports_view"),
    "settings": ("SYSTEM", "Ustawienia", "owner_settings_view"),
  }

  def __init__(self, **properties):
    super().__init__(**properties)
    self.state = AppState()
    self._started = False
    self._catalog_offset = 0
    self._worker_view = "today"
    self._refreshing_after_conflict = False
    self._set_visible("application_view", False)
    self._set_visible("login_view", True)
    self._set_visible("owner_panel_view", True)

  @handle("", "show")
  def form_show(self, **event_args):
    if not self._started:
      self._started = True
      self._boot()

  def _boot(self):
    result = self._server_call("mvp_session")
    if result.get("ok"):
      self.state.apply_session(result)
      self._show_authenticated()
      self._refresh_for_role()
    else:
      self._show_login(result_message(result, "Zaloguj się, aby otworzyć panel."))

  def _server_call(self, name, *args):
    try:
      return call(name, *args)
    except anvil.server.AppOfflineError:
      return {"ok": False, "code": 503, "kind": "offline", "message": "Aplikacja Anvil jest offline."}

  def _set_visible(self, name, visible):
    component = getattr(self, name)
    component.classes["is-hidden"] = not visible

  def _set_text(self, name, text):
    getattr(self, name).text = "—" if text is None else str(text)

  def _set_enabled(self, name, enabled):
    # M3's generated dependency class exposes this property dynamically; using
    # setattr keeps the app compatible with both the dependency and classic
    # Anvil Button implementations.
    setattr(getattr(self, name), "enabled", bool(enabled))

  def _set_message(self, name, text):
    self._set_text(name, text or "")

  def _set_status(self, name, status):
    label, role = status_copy(status)
    component = getattr(self, name)
    component.text = label
    component.role = role

  def _show_login(self, message=""):
    self._set_visible("application_view", False)
    self._set_visible("login_view", True)
    self._set_message("login_message", message)

  def _show_authenticated(self):
    self._set_visible("login_view", False)
    self._set_visible("application_view", True)
    user = self.state.user or {}
    role = str(user.get("role", "owner")).lower()
    is_worker = role == "worker"
    self._set_visible("owner_shell", not is_worker)
    self._set_visible("worker_shell", is_worker)
    self._set_visible("worker_bottom_nav", is_worker)
    self._set_text("owner_name", value(user, "full_name", "name", "email", default="Właściciel"))
    self._set_text("owner_role", "Pracownik" if is_worker else "Właściciel gospodarstwa")
    self._set_text("worker_name", value(user, "full_name", "name", "email", default="Pracownik"))
    self._set_text("worker_farm_name", value(user, "farm_name", "farm", default="Moje gospodarstwo"))
    self._set_text("farm_name", value(user, "farm_name", "farm", default="Moje gospodarstwo"))
    self.state.role = "worker" if is_worker else "owner"
    if is_worker:
      self._show_worker_view("today")
    else:
      self._show_owner_view("panel")

  def _refresh_for_role(self):
    if self.state.role == "worker":
      self._refresh_worker_tasks()
    else:
      self._refresh_dashboard()

  def _handle_result(self, result, *, target="workspace_message", fallback="Operacja nie powiodła się."):
    if result.get("ok"):
      self._set_message(target, "")
      return True
    if result.get("code") == 401 or result.get("kind") == "session_expired":
      self.state.clear()
      self._show_login(result_message(result, "Sesja wygasła. Zaloguj się ponownie."))
      return False
    self._set_message(target, result_message(result, fallback))
    if result.get("code") == 409 and not self._refreshing_after_conflict:
      self._refreshing_after_conflict = True
      try:
        if self.state.role == "worker":
          self._refresh_worker_tasks()
        else:
          self._refresh_tasks()
      finally:
        self._refreshing_after_conflict = False
    return False

  @handle("login_button", "click")
  def login_button_click(self, **event_args):
    self._set_enabled("login_button", False)
    try:
      result = self._server_call("mvp_login", self.login_email.text, self.login_password.text)
      if result.get("ok"):
        self.state.apply_session(result)
        self._show_authenticated()
        self._refresh_for_role()
      else:
        self._set_message("login_message", result_message(result, "Nie udało się zalogować."))
    finally:
      self._set_enabled("login_button", True)

  @handle("register_button", "click")
  def register_button_click(self, **event_args):
    result = self._server_call("mvp_register", self.login_email.text, self.login_password.text, self.register_full_name_input.text)
    if result.get("ok"):
      self._set_message("login_message", "Konto właściciela utworzone. Możesz się teraz zalogować.")
    else:
      self._set_message("login_message", result_message(result, "Nie udało się utworzyć konta."))

  def _show_owner_view(self, view_name):
    for name in (entry[2] for entry in self.OWNER_VIEWS.values() if entry[2].endswith("_view")):
      self._set_visible(name, False)
    eyebrow, title, target = self.OWNER_VIEWS.get(view_name, self.OWNER_VIEWS["panel"])
    self._set_visible(target, True)
    self._set_text("workspace_eyebrow", eyebrow)
    self._set_text("workspace_title", title)
    if view_name == "panel":
      self._refresh_dashboard()
    elif view_name == "maps":
      self._refresh_kwatery()
    elif view_name == "sprays":
      self._refresh_tasks()
    elif view_name == "recipes":
      self._refresh_recipes()
    elif view_name == "workers":
      self._refresh_workers()
    elif view_name == "catalog":
      self._refresh_catalog()
    elif view_name == "inventory":
      self._refresh_inventory()
    elif view_name == "weather":
      self._refresh_weather()

  def _show_worker_view(self, view_name):
    for name in ("worker_today_view", "worker_task_view", "worker_map_view"):
      self._set_visible(name, False)
    self._worker_view = view_name
    self._set_visible({"today": "worker_today_view", "task": "worker_task_view", "map": "worker_map_view"}.get(view_name, "worker_today_view"), True)
    if view_name == "task":
      self._render_worker_task()

  @handle("nav_panel_button", "click")
  def nav_panel_button_click(self, **event_args): self._show_owner_view("panel")

  @handle("nav_maps_button", "click")
  def nav_maps_button_click(self, **event_args): self._show_owner_view("maps")

  @handle("nav_sprays_button", "click")
  def nav_sprays_button_click(self, **event_args): self._show_owner_view("sprays")

  @handle("nav_recipes_button", "click")
  def nav_recipes_button_click(self, **event_args): self._show_owner_view("recipes")

  @handle("nav_recipe_tools_button", "click")
  def nav_recipe_tools_button_click(self, **event_args): self._show_owner_view("recipe_tools")

  @handle("nav_workers_button", "click")
  def nav_workers_button_click(self, **event_args): self._show_owner_view("workers")

  @handle("nav_catalog_button", "click")
  def nav_catalog_button_click(self, **event_args): self._show_owner_view("catalog")

  @handle("nav_inventory_button", "click")
  def nav_inventory_button_click(self, **event_args): self._show_owner_view("inventory")

  @handle("nav_weather_button", "click")
  def nav_weather_button_click(self, **event_args): self._show_owner_view("weather")

  @handle("nav_reports_button", "click")
  def nav_reports_button_click(self, **event_args): self._show_owner_view("reports")

  @handle("nav_settings_button", "click")
  def nav_settings_button_click(self, **event_args): self._show_owner_view("settings")

  @handle("worker_today_button", "click")
  def worker_today_button_click(self, **event_args): self._show_worker_view("today")

  @handle("worker_task_button", "click")
  def worker_task_button_click(self, **event_args): self._show_worker_view("task")

  @handle("worker_map_button", "click")
  def worker_map_button_click(self, **event_args): self._show_worker_view("map")

  @handle("refresh_dashboard_button", "click")
  def refresh_dashboard_button_click(self, **event_args): self._refresh_dashboard()

  @handle("refresh_tasks_button", "click")
  def refresh_tasks_button_click(self, **event_args): self._refresh_tasks()

  @handle("worker_refresh_button", "click")
  def worker_refresh_button_click(self, **event_args): self._refresh_worker_tasks()

  @handle("refresh_kwatery_button", "click")
  def refresh_kwatery_button_click(self, **event_args): self._refresh_kwatery()

  @handle("create_kwatera_button", "click")
  def create_kwatera_button_click(self, **event_args):
    try:
      geometry = json.loads(self.kwatera_geojson_input.text or "")
      latitude = float(self.kwatera_lat_input.text)
      longitude = float(self.kwatera_lon_input.text)
      area_ha = float(self.kwatera_area_input.text)
    except (TypeError, ValueError):
      self._set_message("workspace_message", "GeoJSON, powierzchnia i współrzędne muszą być poprawne.")
      return
    if not self.kwatera_name_input.text or not self.kwatera_parcel_input.text:
      self._set_message("workspace_message", "Podaj nazwę kwatery i numer działki.")
      return
    result = self._server_call("mvp_create_kwatera", {"name": self.kwatera_name_input.text, "nr_dzialki_ewidencyjnej": self.kwatera_parcel_input.text, "polygon_geojson": geometry, "latitude": latitude, "longitude": longitude, "area_ha": area_ha})
    if self._handle_result(result):
      self._set_message("workspace_message", "Kwatera zapisana.")
      self._refresh_kwatery()

  @handle("refresh_recipes_button", "click")
  def refresh_recipes_button_click(self, **event_args): self._refresh_recipes()

  @handle("refresh_weather_button", "click")
  def refresh_weather_button_click(self, **event_args): self._refresh_weather()

  def _refresh_dashboard(self):
    result = self._server_call("mvp_dashboard")
    if not self._handle_result(result):
      return
    self.state.apply_dashboard(result)
    self._render_dashboard()

  def _refresh_tasks(self):
    result = self._server_call("mvp_tasks")
    if self._handle_result(result):
      self.state.apply_tasks(result)
      self._render_task_panels()

  def _refresh_worker_tasks(self):
    result = self._server_call("mvp_worker_my_tasks")
    if self._handle_result(result):
      self.state.apply_tasks(result)
      self._render_task_panels()
      self._render_worker_task()

  def _render_task_panels(self):
    tasks = self.state.tasks
    self.task_panel.items = tasks
    self.all_tasks_panel.items = tasks
    self.worker_task_panel.items = tasks
    self.task_empty_label.visible = not tasks
    self.all_tasks_empty_label.visible = not tasks
    self.worker_task_empty_label.visible = not tasks
    self._render_active_task()

  def _render_dashboard(self):
    self._render_task_panels()
    self.kwatera_count.text = str(len(self.state.kwatery))
    self._render_weather(self.state.weather)

  def _render_active_task(self):
    task = self.state.active_task
    self.active_task_count.text = str(len([item for item in self.state.tasks if item.get("status") not in {"execution_completed", "cancelled"}]))
    if not task:
      self._set_status("active_task_status", "unknown")
      self.active_task_details.text = "Brak aktywnego zadania do wyświetlenia."
      self._set_enabled("authorize_button", False)
      self._set_enabled("dispatch_button", False)
      self._set_enabled("owner_cancel_button", False)
      return
    self._set_status("active_task_status", task.get("weather_status"))
    self.active_task_details.text = " · ".join((
      str(value(task, "name", default="Zabieg ochronny")),
      f"Kwatera: {value(task, 'parcel')}",
      f"Receptura: {value(task, 'recipe_name')}",
      f"Pracownik: {value(task, 'worker_name')}",
      f"Termin: {value(task, 'scheduled_at')}",
      f"Stan: {value(task, 'status')}"))
    # The MVP owns suitability. The UI only keeps authorization unavailable
    # unless the server has explicitly returned a green/safe status; yellow
    # and red are never presented as authorizable.
    weather_safe = str(task.get("weather_status", "")).lower() in {"green", "safe", "suitable", "ok"}
    self._set_enabled("authorize_button", task.get("status") == "worker_confirmed" and weather_safe)
    self._set_enabled("dispatch_button", task.get("status") in {"created"})
    self._set_enabled("owner_cancel_button", task.get("status") not in {"execution_completed", "cancelled"})

  def _render_weather(self, weather):
    weather = weather if isinstance(weather, dict) else {}
    current = weather.get("current") or weather.get("current_weather") or weather
    suitability = weather.get("suitability") or {}
    status = suitability.get("status") if isinstance(suitability, dict) else weather.get("status")
    status_label, status_role = status_copy(status)
    self.weather_status_label.text = status_label
    self.weather_status_label.role = status_role
    self.weather_status_summary.text = status_label
    self.weather_chip_text.text = f"Pogoda: {status_label}"
    for role in ("op-status-safe", "op-status-warning", "op-status-danger", "op-status-neutral"):
      self.weather_chip.classes[role] = False
    self.weather_chip.classes[status_role] = True
    temperature = format_number(value(current, "temperature", "temperature_2m", default=""), "°C")
    wind = format_number(value(current, "wind_speed", "windspeed", "wind_speed_10m", default=""), " km/h")
    rain = format_number(value(current, "rain", "precipitation", "precipitation_probability", default=""), " mm")
    humidity = format_number(value(current, "relative_humidity", "relative_humidity_2m", "humidity", default=""), "%")
    self._set_text("weather_temperature", temperature)
    self._set_text("weather_wind", wind)
    self._set_text("weather_rain", rain)
    self._set_text("weather_page_temperature", temperature)
    self._set_text("weather_page_wind", wind)
    self._set_text("weather_page_rain", rain)
    self._set_text("weather_humidity", humidity)
    self._set_text("weather_delta_method", weather.get("delta_t_method", "magnus_approx"))
    self._set_text("weather_status_detail", "Snapshot z MVP" if weather else "Brak snapshotu pogody")
    self._set_message("weather_page_message", "" if weather else "Pogoda będzie dostępna po skonfigurowaniu współrzędnych kwatery.")

  def _refresh_kwatery(self):
    result = self._server_call("mvp_kwatery")
    if not self._handle_result(result): return
    data = result_data(result, [])
    if isinstance(data, dict): data = data.get("items", data.get("results", []))
    self.state.kwatery = data or []
    self.kwatera_panel.items = self.state.kwatery
    self.kwatera_empty_label.visible = not self.state.kwatery

  def _refresh_recipes(self):
    result = self._server_call("mvp_recipes")
    if not self._handle_result(result): return
    self.recipe_panel.items = self.state.apply_recipes(result)
    self.recipe_empty_label.visible = not self.state.recipes

  def _refresh_workers(self):
    result = self._server_call("mvp_workers")
    if not self._handle_result(result): return
    data = result_data(result, [])
    if isinstance(data, dict): data = data.get("items", data.get("results", []))
    self.worker_panel.items = data or []
    self.worker_empty_label.visible = not data

  def _refresh_catalog(self):
    result = self._server_call("mvp_catalog", 50, self._catalog_offset)
    if not self._handle_result(result): return
    self.catalog_panel.items = self.state.apply_catalog(result, self._catalog_offset)
    self.catalog_empty_label.visible = not self.state.catalog
    page = self._catalog_offset // 50 + 1
    pages = max(1, (self.state.catalog_total + 49) // 50)
    self.catalog_page_label.text = f"Strona {page} z {pages} · {self.state.catalog_total} produktów"
    self._set_enabled("catalog_previous_button", self._catalog_offset > 0)
    self._set_enabled("catalog_next_button", self._catalog_offset + 50 < self.state.catalog_total)

  def _refresh_inventory(self):
    result = self._server_call("mvp_inventory")
    if self._handle_result(result, target="inventory_message"):
      self._set_text("inventory_balances_result", json.dumps(result_data(result, {}), ensure_ascii=False, indent=2))
    lots = self._server_call("mvp_inventory_lots")
    if self._handle_result(lots, target="inventory_message"):
      self._set_text("inventory_lots_result", json.dumps(result_data(lots, {}), ensure_ascii=False, indent=2))
    movements = self._server_call("mvp_inventory_movements")
    if self._handle_result(movements, target="inventory_message"):
      self._set_text("inventory_movements_result", json.dumps(result_data(movements, {}), ensure_ascii=False, indent=2))

  @handle("catalog_previous_button", "click")
  def catalog_previous_button_click(self, **event_args):
    self._catalog_offset = max(0, self._catalog_offset - 50)
    self._refresh_catalog()

  @handle("catalog_next_button", "click")
  def catalog_next_button_click(self, **event_args):
    if self._catalog_offset + 50 < self.state.catalog_total:
      self._catalog_offset += 50
      self._refresh_catalog()

  def _refresh_weather(self):
    coordinates = self._first_coordinates()
    if not coordinates:
      self._set_message("weather_page_message", "Brak współrzędnych kwatery.")
      return
    result = self._server_call("mvp_weather", coordinates[0], coordinates[1])
    if self._handle_result(result, target="weather_page_message"):
      self.state.weather = result_data(result)
      self._render_weather(self.state.weather)

  def _first_coordinates(self):
    for parcel in self.state.kwatery:
      if not isinstance(parcel, dict): continue
      for lat_key, lon_key in (("latitude", "longitude"), ("lat", "lon")):
        if parcel.get(lat_key) is not None and parcel.get(lon_key) is not None:
          return parcel[lat_key], parcel[lon_key]
      centroid = parcel.get("centroid")
      if isinstance(centroid, dict) and centroid.get("lat") is not None and centroid.get("lon") is not None:
        return centroid["lat"], centroid["lon"]
    return None

  @handle("authorize_button", "click")
  def authorize_button_click(self, **event_args): self._owner_task_action("owner-authorize")

  @handle("dispatch_button", "click")
  def dispatch_button_click(self, **event_args): self._owner_task_action("dispatch")

  @handle("owner_cancel_button", "click")
  def owner_cancel_button_click(self, **event_args): self._owner_task_action("cancel", {"reason_code": "owner_cancelled", "partial_mix_disposed": False})

  def _owner_task_action(self, action, payload=None):
    task_id = (self.state.active_task or {}).get("id")
    if not task_id:
      self._set_message("workspace_message", "Brak aktywnego zadania.")
      return
    if action == "owner-authorize":
      weather_status = str((self.state.active_task or {}).get("weather_status", "")).lower()
      if weather_status not in {"green", "safe", "suitable", "ok"}:
        self._set_message("workspace_message", "Autoryzacja jest zablokowana: MVP nie zwróciło zielonych warunków.")
        return
    result = self._server_call("mvp_task_action", task_id, action, payload or {})
    if self._handle_result(result):
      self._refresh_dashboard()

  @handle("create_task_button", "click")
  def create_task_button_click(self, **event_args):
    try:
      kwatera_ids = json.loads(str(self.task_kwatera_ids_input.text or "[]"))
      actual_dose = json.loads(str(self.task_actual_dose_input.text or "{}"))
    except (TypeError, ValueError):
      self._set_message("workspace_message", "ID kwater i dawki muszą być poprawnym JSON-em.")
      return
    required = (self.task_reason_input.text, self.task_worker_id_input.text, self.task_executor_name_input.text, self.task_recipe_id_input.text, self.task_bbch_input.text)
    if not all(required) or not isinstance(kwatera_ids, list):
      self._set_message("workspace_message", "Uzupełnij wszystkie pola zgodności i listę kwater.")
      return
    coordinates = self._coordinates_for_kwatery(kwatera_ids)
    if not coordinates:
      self._set_message("workspace_message", "Wybierz kwaterę z poprawnymi współrzędnymi WGS84.")
      return
    snapshot = self._server_call("mvp_server_weather_snapshot", coordinates[0], coordinates[1])
    if not self._handle_result(snapshot):
      return
    payload = {
      "przyczyna": self.task_reason_input.text,
      "application_type": self.task_application_input.text or "polowe",
      "worker_id": self.task_worker_id_input.text,
      "executor_name": self.task_executor_name_input.text,
      "recipe_id": self.task_recipe_id_input.text,
      "bbch_at_spray": self.task_bbch_input.text,
      "actual_dose_per_product": actual_dose,
      "kwatera_ids": kwatera_ids,
      "scheduled_at": self.task_scheduled_input.text or None,
      "weather_snapshot": result_data(snapshot, {}),
      "t_source": "server",
    }
    result = self._server_call("mvp_create_task", payload)
    if self._handle_result(result):
      self._set_message("workspace_message", "Zadanie utworzone. Wyślij je teraz do pracownika.")
      self._refresh_tasks()

  def _coordinates_for_kwatery(self, kwatera_ids):
    selected = set(str(item) for item in kwatera_ids)
    for parcel in self.state.kwatery:
      if not isinstance(parcel, dict):
        continue
      parcel_id = value(parcel, "id", "kwatera_id", default="")
      if str(parcel_id) not in selected:
        continue
      for lat_key, lon_key in (("latitude", "longitude"), ("lat", "lon")):
        if parcel.get(lat_key) is not None and parcel.get(lon_key) is not None:
          return parcel[lat_key], parcel[lon_key]
      centroid = parcel.get("centroid")
      if isinstance(centroid, dict) and centroid.get("lat") is not None and centroid.get("lon") is not None:
        return centroid["lat"], centroid["lon"]
    return None

  def _render_worker_task(self):
    task = self.state.active_task
    if not task:
      self._set_status("worker_task_status_label", "unknown")
      self.worker_recipe_result.text = "Brak przypisanego zadania."
      return
    self._set_status("worker_task_status_label", task.get("weather_status"))
    self._set_text("worker_task_name", task.get("name"))
    self._set_text("worker_task_parcel", task.get("parcel"))
    self._set_text("worker_task_reason", task.get("reason"))
    self._set_text("worker_task_schedule", task.get("scheduled_at"))
    self._set_text("worker_action_message", f"Stan serwera: {task.get('status')}")
    self._set_enabled("worker_confirm_button", task.get("status") == "dispatched")
    self._set_enabled("worker_start_button", task.get("status") == "owner_approved")
    self._set_enabled("worker_complete_button", task.get("status") == "execution_started")
    self._set_enabled("worker_cancel_button", task.get("status") not in {"execution_completed", "cancelled"})
    parcel = value(task, "parcel", default="—")
    self.worker_map_message.text = f"Wybrana kwatera: {parcel}. Link mapy pozostaje referencją tylko do odczytu."

  @handle("worker_compute_button", "click")
  def worker_compute_button_click(self, **event_args):
    task = self.state.active_task or {}
    recipe_id = task.get("recipe_id")
    if not recipe_id:
      self.worker_recipe_result.text = "Brak identyfikatora receptury w zadaniu."
      return
    try:
      area_ha = float(self.worker_area_input.text)
    except (TypeError, ValueError):
      self.worker_recipe_result.text = "Podaj poprawną powierzchnię w hektarach."
      return
    result = self._server_call("mvp_recipe_compute", recipe_id, area_ha)
    if self._handle_result(result, target="worker_action_message"):
      computed = result_data(result, {}) or {}
      self.worker_recipe_result.text = json.dumps(computed, ensure_ascii=False, indent=2)
      self._set_text(
        "worker_ppe_result",
        "Dane produktu/PPE są pokazane w wyniku serwera powyżej. Prewencja i REI: Planowane.",
      )

  @handle("worker_confirm_button", "click")
  def worker_confirm_button_click(self, **event_args): self._worker_task_action("worker-confirm")

  @handle("worker_start_button", "click")
  def worker_start_button_click(self, **event_args): self._worker_task_action("execution-started")

  @handle("worker_complete_button", "click")
  def worker_complete_button_click(self, **event_args): self._worker_task_action("execution-completed")

  @handle("worker_cancel_button", "click")
  def worker_cancel_button_click(self, **event_args): self._worker_task_action("cancel", {"reason_code": "worker_cancelled", "partial_mix_disposed": False})

  def _worker_task_action(self, action, payload=None):
    task_id = (self.state.active_task or {}).get("id")
    if not task_id:
      self._set_message("worker_action_message", "Brak przypisanego zadania.")
      return
    result = self._server_call("mvp_task_action", task_id, action, payload or {})
    if self._handle_result(result, target="worker_action_message"):
      self._refresh_worker_tasks()

  @handle("create_worker_button", "click")
  def create_worker_button_click(self, **event_args):
    result = self._server_call("mvp_create_worker", self.worker_email_input.text, self.worker_password_input.text, self.worker_full_name_input.text)
    if self._handle_result(result):
      self._set_message("workspace_message", "Pracownik utworzony.")
      self._refresh_workers()

  @handle("create_recipe_button", "click")
  def create_recipe_button_click(self, **event_args):
    try:
      products = json.loads(self.recipe_products_input.text or "[]")
      water = float(self.recipe_water_input.text)
    except (TypeError, ValueError):
      self._set_message("workspace_message", "Produkty muszą być poprawnym JSON-em, a woda liczbą.")
      return
    if not isinstance(products, list) or not products or not self.recipe_name_input.text or not self.recipe_target_input.text:
      self._set_message("workspace_message", "Podaj nazwę, cel i co najmniej jeden produkt.")
      return
    result = self._server_call("mvp_create_recipe", {"name": self.recipe_name_input.text, "target": self.recipe_target_input.text, "products": products, "water_l_per_ha": water})
    if self._handle_result(result):
      self._set_message("workspace_message", "Szkic receptury zapisany.")
      self._refresh_recipes()

  def _recipe_action_result(self, result):
    if self._handle_result(result, target="recipe_action_message"):
      self._set_text("recipe_action_result", json.dumps(result_data(result, {}), ensure_ascii=False, indent=2))

  def _recipe_action_id(self):
    recipe_id = str(self.recipe_id_action_input.text or "").strip()
    if not recipe_id:
      self._set_message("recipe_action_message", "Podaj identyfikator receptury.")
      return None
    return recipe_id

  @handle("validate_recipe_button", "click")
  def validate_recipe_button_click(self, **event_args):
    recipe_id = self._recipe_action_id()
    if recipe_id:
      self._recipe_action_result(self._server_call("mvp_recipe_validation", recipe_id))

  @handle("copy_recipe_button", "click")
  def copy_recipe_button_click(self, **event_args):
    recipe_id = self._recipe_action_id()
    if recipe_id:
      self._recipe_action_result(self._server_call("mvp_recipe_copy", recipe_id))

  @handle("export_recipe_button", "click")
  def export_recipe_button_click(self, **event_args):
    recipe_id = self._recipe_action_id()
    if recipe_id:
      export_format = str(self.recipe_export_format_input.text or "json").strip().lower() or "json"
      self._recipe_action_result(self._server_call("mvp_recipe_export", recipe_id, export_format))

  @handle("refresh_inventory_button", "click")
  def refresh_inventory_button_click(self, **event_args): self._refresh_inventory()

  @handle("reservation_detail_button", "click")
  def reservation_detail_button_click(self, **event_args):
    reservation_id = str(self.reservation_id_input.text or "").strip()
    if not reservation_id:
      self._set_message("inventory_message", "Podaj identyfikator rezerwacji.")
      return
    result = self._server_call("mvp_inventory_reservation", reservation_id)
    if self._handle_result(result, target="inventory_message"):
      self._set_text("reservation_result", json.dumps(result_data(result, {}), ensure_ascii=False, indent=2))

  @handle("receipt_inventory_button", "click")
  def receipt_inventory_button_click(self, **event_args):
    try:
      payload = json.loads(self.inventory_receipt_input.text or "{}")
    except (TypeError, ValueError):
      self._set_message("inventory_message", "Przyjęcie magazynowe musi być poprawnym JSON-em.")
      return
    if not isinstance(payload, dict):
      self._set_message("inventory_message", "Przyjęcie magazynowe musi być obiektem JSON.")
      return
    result = self._server_call("mvp_inventory_receipt", payload)
    if self._handle_result(result, target="inventory_message"):
      self._set_text("receipt_result", json.dumps(result_data(result, {}), ensure_ascii=False, indent=2))
      self._refresh_inventory()

  def _logout(self):
    self._server_call("mvp_logout")
    self.state.clear()
    self._show_login("Wylogowano.")

  @handle("owner_logout_button", "click")
  def owner_logout_button_click(self, **event_args): self._logout()

  @handle("settings_logout_button", "click")
  def settings_logout_button_click(self, **event_args): self._logout()
