from anvil import handle

from ..App.helpers import format_number, value
from ._anvil_designer import RecipeCardTemplate
import anvil.server


class RecipeCard(RecipeCardTemplate):
    def __init__(self, **properties):
        super().__init__(**properties)
        self._render()

    @handle("", "show")
    def form_show(self, **event_args):
        self._render()

    def _render(self):
        recipe = getattr(self, "item", None) or {}
        self.recipe_name.text = value(recipe, "name", default="Receptura bez nazwy")
        self.recipe_target.text = f"Cel: {value(recipe, 'target', default='—')}"
        self.recipe_water.text = f"Woda: {format_number(value(recipe, 'water_l_per_ha', default=''), ' l/ha')}"
        self.recipe_products.text = f"Składniki: {value(recipe, 'products_count', default='—')}"
