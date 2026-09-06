from anvil import handle

from ..App.helpers import status_copy, value
from ._anvil_designer import KwateraCardTemplate
import anvil.server


class KwateraCard(KwateraCardTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self._render()

    @handle("", "show")
    def form_show(self, **event_args):
        self._render()

    def _render(self):
        parcel = getattr(self, "item", None) or {}
        self.parcel_name.text = value(parcel, "name", "label", default="Kwatera")
        self.parcel_number.text = f"Nr działki: {value(parcel, 'nr_dzialki_ewidencyjnej', 'parcel_number', default='—')}"
        karencja = value(parcel, "karencja_until", default=None)
        if karencja:
            self.parcel_status.text, self.parcel_status.role = "× Karencja aktywna", "op-status-danger"
        else:
            self.parcel_status.text, self.parcel_status.role = status_copy("green")
        osm_url = value(parcel, "osm_url", "openstreetmap_url", default="")
        setattr(self.osm_link, "url", osm_url)
        self.osm_link.visible = bool(osm_url)
