from ._anvil_designer import Form1Template
from anvil import *
import m3.components as m3

class Form1(Form1Template):
  def __init__(self, **properties):
    # Set Form properties and Data Bindings.
    super().__init__(**properties)

    # Any code you write here will run before the form opens.
