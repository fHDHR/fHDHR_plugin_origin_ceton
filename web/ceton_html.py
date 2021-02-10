from flask import request, render_template_string
import pathlib
from io import StringIO


class Ceton_HTML():
    endpoints = ["/ceton", "/ceton.html"]
    endpoint_name = "page_ceton_html"
    endpoint_category = "pages"
    pretty_name = "Ceton"

    def __init__(self, fhdhr, plugin_utils):
        self.fhdhr = fhdhr
        self.plugin_utils = plugin_utils

        self.origin = plugin_utils.origin

        self.template_file = pathlib.Path(plugin_utils.config.dict["plugin_web_paths"][plugin_utils.namespace]["path"]).joinpath('ceton.html')
        self.template = StringIO()
        self.template.write(open(self.template_file).read())

    def __call__(self, *args):
        return self.get(*args)

    def get(self, *args):

        if self.origin.setup_success:
            origin_status_dict = {"Setup": "Success"}
        else:
            origin_status_dict = {"Setup": "Failed"}

        origin_status_dict["Temp"] = self.plugin_utils.origin.get_ceton_getvar(0, "Temperature")

        for i in range(int(self.fhdhr.config.dict["ceton"]["tuners"])):
            origin_status_dict["Tuner"+str(i)] = {}
            origin_status_dict["Tuner"+str(i)]['State'] = self.plugin_utils.origin.get_ceton_getvar(i, "TransportState")
            origin_status_dict["Tuner"+str(i)]['Signal'] = self.plugin_utils.origin.get_ceton_getvar(i, "Signal_Level")
            origin_status_dict["Tuner"+str(i)]['SNR'] = self.plugin_utils.origin.get_ceton_getvar(i, "Signal_SNR")
        return render_template_string(self.template.getvalue(), request=request, fhdhr=self.fhdhr, origin_status_dict=origin_status_dict, list=list)
