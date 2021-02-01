from flask import request, redirect


class Ceton_API():
    endpoints = ["/api/ceton"]
    endpoint_name = "api_ceton"
    endpoint_methods = ["GET", "POST"]

    def __init__(self, plugin_utils):
        self.plugin_utils = plugin_utils

    def __call__(self, *args):
        return self.get(*args)

    def get(self, *args):

        method = request.args.get('method', None, type=str)

        tuner_number = request.args.get('tuner', None, type=str)

        redirect_url = request.args.get('redirect', default=None, type=str)

        if method == "close":
            self.plugin_utils.origin.startstop_ceton_tuner(tuner_number, 0)

        if redirect_url:
            return redirect(redirect_url)
        else:
            return "%s Success" % method
