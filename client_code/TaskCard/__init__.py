from anvil import handle

from ..App.helpers import format_datetime, status_copy, value
from ._anvil_designer import TaskCardTemplate
import anvil.server


class TaskCard(TaskCardTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self._render()

    @handle("", "show")
    def form_show(self, **event_args):
        self._render()

    def _render(self):
        task = getattr(self, "item", None) or {}
        self.task_title.text = value(task, "name", default="Zabieg ochronny")
        self.task_parcel.text = f"Kwatera: {value(task, 'parcel', default='—')}"
        self.task_recipe.text = f"Receptura: {value(task, 'recipe_name', default='—')}"
        self.task_worker.text = f"Pracownik: {value(task, 'worker_name', default='—')}"
        self.task_schedule.text = f"Termin: {value(task, 'scheduled_at', default=format_datetime(task.get('scheduled_at')))}"
        label, role = status_copy(value(task, "weather_status", default="unknown"))
        self.task_weather.text = label
        self.task_weather.role = role
        self.task_status.text = value(task, "status", default="created")
