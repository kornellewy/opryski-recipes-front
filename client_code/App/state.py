"""Ephemeral server-backed view state; no Anvil Data Tables are used."""

from anvil import server

from .helpers import normalise_recipe, normalise_task, result_data


class AppState:
    def __init__(self):
        self.user = None
        self.role = None
        self.dashboard = {}
        self.tasks = []
        self.kwatery = []
        self.recipes = []
        self.workers = []
        self.catalog = []
        self.catalog_total = 0
        self.catalog_offset = 0
        self.weather = None
        self.active_task = None
        self.selected_task_id = None

    def apply_session(self, result):
        self.user = result_data(result)
        self.role = self.user.get("role") if isinstance(self.user, dict) else None
        return self.user

    def apply_dashboard(self, result):
        data = result_data(result, {}) or {}
        self.dashboard = data
        self.user = data.get("me") or self.user
        self.role = self.user.get("role") if isinstance(self.user, dict) else self.role
        self.tasks = [normalise_task(task) for task in data.get("tasks", [])]
        self.kwatery = data.get("kwatery", []) if isinstance(data.get("kwatery", []), list) else []
        self.weather = data.get("weather")
        self.active_task = self._find_active_task()
        if self.active_task:
            self.selected_task_id = self.active_task.get("id")
        return data

    def apply_tasks(self, result):
        raw_tasks = result_data(result, [])
        if isinstance(raw_tasks, dict):
            raw_tasks = raw_tasks.get("items", raw_tasks.get("results", []))
        self.tasks = [normalise_task(task) for task in (raw_tasks or [])]
        self.active_task = self._find_active_task()
        return self.tasks

    def apply_recipes(self, result):
        raw_recipes = result_data(result, [])
        if isinstance(raw_recipes, dict):
            raw_recipes = raw_recipes.get("items", raw_recipes.get("results", []))
        self.recipes = [normalise_recipe(recipe) for recipe in (raw_recipes or [])]
        return self.recipes

    def apply_catalog(self, result, offset):
        data = result_data(result, {}) or {}
        self.catalog = data.get("items", data.get("results", [])) if isinstance(data, dict) else []
        self.catalog_total = data.get("total", len(self.catalog)) if isinstance(data, dict) else len(self.catalog)
        self.catalog_offset = offset
        return self.catalog

    def clear(self):
        self.__init__()

    def _find_active_task(self):
        terminal = {"execution_completed", "cancelled"}
        for task in self.tasks:
            if task.get("status") not in terminal:
                return task
        return self.tasks[0] if self.tasks else None


def call(name, *args, **kwargs):
    """Call one gateway function; responses retain the explicit result shape."""
    return server.call(name, *args, **kwargs)
