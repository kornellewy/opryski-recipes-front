from anvil import handle

from ..App.helpers import value
from ._anvil_designer import WorkerCardTemplate
import anvil.server


class WorkerCard(WorkerCardTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self._render()

    @handle("", "show")
    def form_show(self, **event_args):
        self._render()

    def _render(self):
        worker = getattr(self, "item", None) or {}
        self.worker_name.text = value(worker, "full_name", "name", default="Pracownik")
        self.worker_email.text = value(worker, "email", default="—")
        self.worker_status.text = "Aktywny" if worker.get("enabled", True) else "Wyłączony"
