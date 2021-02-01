
from .ceton_api import Ceton_API
from .ceton_html import Ceton_HTML


class Plugin_OBJ():

    def __init__(self, fhdhr, plugin_utils):
        self.fhdhr = fhdhr
        self.plugin_utils = plugin_utils

        self.ceton_api = Ceton_API(plugin_utils)
        self.ceton_html = Ceton_HTML(fhdhr, plugin_utils)
