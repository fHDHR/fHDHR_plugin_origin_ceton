from flask import request, render_template_string
import pathlib
from io import StringIO
import subprocess


class Ceton_HTML():
    endpoints = ["/ceton", "/ceton.html"]
    endpoint_name = "page_ceton_html"
    endpoint_category = "pages"
    pretty_name = "Ceton"

    def __init__(self, fhdhr, plugin_utils):
        self.fhdhr = fhdhr
        self.plugin_utils = plugin_utils

        self.origin_obj = plugin_utils.origin_obj
        self.origin_name = self.origin_obj.name

        self.template_file = pathlib.Path(plugin_utils.path).joinpath('ceton.html')
        self.template = StringIO()
        self.template.write(open(self.template_file).read())

        self.hwtype = self.plugin_utils.origin_obj.get_ceton_getvar(0, "HostConnection")
        if 'pci' in self.hwtype:
            self.ceton_pcie = True
        else:
            self.ceton_pcie = False

    def __call__(self, *args):
        return self.get(*args)

    def devinuse(self, instance):
        filename = self.plugin_utils.origin_obj.tunerstatus[str(instance)]['streamurl']
        if '/dev' in filename:
            try:
                subprocess.check_output(['fuser', filename], stderr=subprocess.DEVNULL)
                # man: if access has been found, fuser returns zero
                # => Return True, device is in use
                return "In Use"
            except subprocess.CalledProcessError:
                # man: fuser returns a non-zero return code if none of the specified files is accessed
                # => Return False, device is not in use
                return "Available"
        else:
            # Not PCIe card, so don't check device
            return "Not PCIe Card"

    def get(self, *args):

        if self.origin_obj.setup_success:
            origin_status_dict = {"Devices": len(self.fhdhr.config.dict["ceton"]["device_tuners"])}
            for i in range(len(self.fhdhr.config.dict["ceton"]["device_tuners"])):
                device = self.plugin_utils.origin_obj.tunerstatus[str(i)]['ceton_ip']
                origin_status_dict["Device"+str(i)] = {}
                origin_status_dict["Device"+str(i)]["Setup"] = "Success"
                origin_status_dict["Device"+str(i)]["Temp"] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "Temperature")
                origin_status_dict["Device"+str(i)]["HWType"] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "HostConnection")
                origin_status_dict["Device"+str(i)]["HostHardware"] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "HostHardware")
                origin_status_dict["Device"+str(i)]["HostFirmware"] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "HostFirmware")
                origin_status_dict["Device"+str(i)]["HostSerial"] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "HostSerial")

            for i in range(int(self.fhdhr.config.dict["ceton"]["tuners"])):
                origin_status_dict["Tuner"+str(i)] = {}
                origin_status_dict["Tuner"+str(i)]['Device'] = int(self.plugin_utils.origin_obj.tunerstatus[str(i)]['ceton_device'])
                origin_status_dict["Tuner"+str(i)]['Transport'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "TransportState")
                origin_status_dict["Tuner"+str(i)]['HWState'] = self.devinuse(i)
                origin_status_dict["Tuner"+str(i)]['Channel'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "Signal_Channel")
                origin_status_dict["Tuner"+str(i)]['SignalLock'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "SignalCarrierLock")
                origin_status_dict["Tuner"+str(i)]['PCRLock'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "SignalPCRLock")
                origin_status_dict["Tuner"+str(i)]['Signal'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "Signal_Level")
                origin_status_dict["Tuner"+str(i)]['SNR'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "Signal_SNR")
                origin_status_dict["Tuner"+str(i)]['BER'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "Signal_BER")
                origin_status_dict["Tuner"+str(i)]['Modulation'] = self.plugin_utils.origin_obj.get_ceton_getvar(i, "Signal_Modulation")
        else:
            origin_status_dict = {"Setup": "Failed"}

        return render_template_string(self.template.getvalue(), request=request, fhdhr=self.fhdhr, origin_name=self.origin_name, origin_status_dict=origin_status_dict, list=list)
