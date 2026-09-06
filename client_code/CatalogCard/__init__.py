from anvil import handle

from ..App.helpers import value
from ._anvil_designer import CatalogCardTemplate
import anvil.server


class CatalogCard(CatalogCardTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self._render()

    @handle("", "show")
    def form_show(self, **event_args):
        self._render()

    def _render(self):
        product = getattr(self, "item", None) or {}
        self.product_name.text = value(product, "name", default="Produkt katalogowy")
        self.product_formulation.text = f"Formulacja: {value(product, 'formulation', default='—')}"
        self.product_source.text = value(product, "source", "source_name", "label_source", default="Źródło katalogowe MVP")
