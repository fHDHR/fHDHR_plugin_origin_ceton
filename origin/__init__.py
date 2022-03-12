import base64
import re
import xmltodict
import subprocess

from random import randint
import fHDHR.exceptions


class Plugin_OBJ():

    def __init__(self, plugin_utils):
        self.plugin_utils = plugin_utils

        if not self.ceton_ip:
            raise fHDHR.exceptions.OriginSetupError("Ceton IP not set.")

        hwtype = self.get_ceton_getvar(0, "HostConnection")
        self.plugin_utils.logger.info('Ceton hardware type: %s' % hwtype)
        if 'pci' in hwtype:
            self.ceton_pcie = True
            if not self.pcie_ip:
                raise fHDHR.exceptions.OriginSetupError("Ceton PCIe IP not set.")
        else:
            self.ceton_pcie = False

        self.tunerstatus = {}
        count = int(self.tuners)
        for i in range(count):
            self.startstop_ceton_tuner(i, 0)

    @property
    def config_dict(self):
        return self.plugin_utils.config.dict["ceton"]

    @property
    def tuners(self):
        return self.config_dict["tuners"]

    @property
    def stream_method(self):
        return self.config_dict["stream_method"]

    @property
    def ceton_ip(self):
        return self.config_dict["ceton_ip"]

    @property
    def pcie_ip(self):
        return self.plugin_utils.config.dict["ceton"]["pcie_ip"]

    def get_ceton_getvar(self, instance, query):
        query_type = {
                      "Frequency": "&s=tuner&v=Frequency",
                      "ProgramNumber": "&s=mux&v=ProgramNumber",
                      "CopyProtectionStatus": "&s=diag&v=CopyProtectionStatus",
                      "Temperature": "&s=diag&v=Temperature",
                      "Signal_Channel": "&s=diag&v=Signal_Channel",
                      "Signal_Level": "&s=diag&v=Signal_Level",
                      "Signal_SNR": "&s=diag&v=Signal_SNR",
                      "Signal_BER": "&s=tuner&v=BER",
                      "Signal_Modulation": "&s=tuner&v=Modulation",
                      "TransportState": "&s=av&v=TransportState",
                      "HostConnection": "&s=diag&v=Host_Connection",
                      "HostSerial": "&s=diag&v=Host_Serial_Number",
                      "HostFirmware": "&s=diag&v=Host_Firmware",
                      "HostHardware": "&s=diag&v=Hardware_Revision",
                      "SignalCarrierLock": "&s=diag&v=Signal_Carrier_Lock",
                      "SignalPCRLock": "&s=diag&v=Signal_PCR_Lock",
                      "OOBStatus": "&s=diag&v=OOB_Status",
        }

        getVarUrl = ('http://%s/get_var?i=%s%s' % (self.ceton_ip, instance, query_type[query]))

        try:
            getVarUrlReq = self.plugin_utils.web.session.get(getVarUrl)
            getVarUrlReq.raise_for_status()
        except self.plugin_utils.web.exceptions.HTTPError as err:
            self.plugin_utils.logger.error('Error while getting Ceton tuner variable for %s: %s' % (query, err))
            return None

        result = re.search('get.>(.*)</body', getVarUrlReq.text)

        return result.group(1)

    def devinuse(self, filename):
        if self.ceton_pcie:
            try:
                subprocess.check_output(['fuser', filename], stderr=subprocess.DEVNULL)
                # man: if access has been found, fuser returns zero
                # => Return True, device is in use
                return True
            except subprocess.CalledProcessError:
                # man: fuser returns a non-zero return code if none of the specified files is accessed
                # => Return False, device is not in use
                return False
        else:
            # Not PCIe card, so don't check device
            return False

    def get_ceton_tuner_status(self, chandict, scan=False):
        found = 0
        count = int(self.tuners)
        for instance in range(count):

            transport = self.get_ceton_getvar(instance, "TransportState")
            hwinuse = self.devinuse("/dev/ceton/ctn91xx_mpeg0_%s" % instance)
            # Check to see if transport on (rtp/udp streaming), or direct HW device access (pcie)
            # This also handles the case of another client accessing the tuner!
            if (transport == "STOPPED") and (not hwinuse):
                self.plugin_utils.logger.info('Selected Ceton tuner#: %s' % instance)
                # And, clear tunerstatus (just in case external client stopped using it)
                self.tunerstatus[str(instance)] = {"status": "Inactive"}
                # Return needed info now (if not in scan mode)
                if not scan:
                    found = 1
                    break
            else:
                # Tuner is in use, flag as external if not expected to be (in use)
                if self.tunerstatus[str(instance)]['status'] != "Active":
                    self.tunerstatus[str(instance)] = {"status": "External"}

        return found, instance

    def startstop_ceton_tuner(self, instance, startstop):
        if not startstop:
            port = 0
            self.plugin_utils.logger.info('Ceton tuner %s to be stopped' % str(instance))
            self.tunerstatus[str(instance)] = { "status": "Inactive" }
        else:
            port = randint(41001, 49999)
            self.plugin_utils.logger.info('Ceton tuner %s to be started' % str(instance))
            self.tunerstatus[str(instance)]["status"] = "Active"

        StartStopUrl = 'http://%s/stream_request.cgi' % self.ceton_ip

        if not self.ceton_pcie:
            dest_ip = self.plugin_utils.config.dict["fhdhr"]["address"]
            dest_port = port
        else:
            dest_ip = self.pcie_ip
            dest_port = 8000 + int(instance)
        StartStop_data = {"instance_id": instance,
                          "dest_ip": dest_ip,
                          "dest_port": dest_port,
                          "protocol": 0,
                          "start": startstop}
        # StartStopUrl_headers = {
        #                    'Content-Type': 'application/json',
        #                    'User-Agent': "curl/7.64.1"}

        # StartStop ... OK to Stop tuner for pcie (and safe), but do not Start => or blocks pcie (/dev)!
        if not (startstop and self.ceton_pcie):
            try:
                StartStopUrlReq = self.plugin_utils.web.session.post(StartStopUrl, StartStop_data)
                StartStopUrlReq.raise_for_status()
            except self.plugin_utils.web.exceptions.HTTPError as err:
                self.plugin_utils.logger.error('Error while setting station stream: %s' % err)
                return None

        return port

    def set_ceton_tuner(self, chandict, instance):
        tuneChannelUrl = 'http://%s/channel_request.cgi' % self.ceton_ip
        tuneChannel_data = {"instance_id": instance,
                            "channel": chandict['origin_number']}

        try:
            tuneChannelUrlReq = self.plugin_utils.web.session.post(tuneChannelUrl, tuneChannel_data)
            tuneChannelUrlReq.raise_for_status()
        except self.plugin_utils.web.exceptions.HTTPError as err:
            self.plugin_utils.logger.error('Error while tuning station URL: %s' % err)
            return None

        return 1

    def get_channels(self):
        cleaned_channels = []
        url_headers = {'accept': 'application/xml;q=0.9, */*;q=0.8'}

        count_url = 'http://%s/view_channel_map.cgi?page=1' % self.ceton_ip

        try:
            countReq = self.plugin_utils.web.session.get(count_url, headers=url_headers)
            countReq.raise_for_status()
        except self.plugin_utils.web.exceptions.HTTPError as err:
            self.plugin_utils.logger.error('Error while getting channel count: %s' % err)
            return []

        count = re.search('(?<=1 to 50 of )\w+', countReq.text)
        count = int(count.group(0))
        page = 0

        while True:
            stations_url = "http://%s/view_channel_map.cgi?page=%s&xml=1" % (self.ceton_ip, page)

            try:
                stationsReq = self.plugin_utils.web.session.get(stations_url, headers=url_headers)
                stationsReq.raise_for_status()
            except self.plugin_utils.web.exceptions.HTTPError as err:
                self.plugin_utils.logger.error('Error while getting stations: %s' % err)
                return []

            stationsRes = xmltodict.parse(stationsReq.content)

            for station_item in stationsRes['channels']['channel']:
                nameTmp = station_item["name"]
                nameTmp_bytes = nameTmp.encode('ascii')
                namebytes = base64.b64decode(nameTmp_bytes)
                name = namebytes.decode('ascii')
                clean_station_item = {
                                        "name": name,
                                        "callsign": name,
                                        "number": station_item["number"],
                                        "eia": station_item["eia"],
                                        "id": station_item["sourceid"],
                                        }

                cleaned_channels.append(clean_station_item)

            if (count > 1024):
                count -= 1024
                page = 21
                continue
            else:
                break

            if (count > 0):
                count -= 50
                page += 1
            else:
                break

        return cleaned_channels

    def get_channel_stream(self, chandict, stream_args):
        found, instance = self.get_ceton_tuner_status(chandict)
        self.tunerstatus[str(instance)]["stream_args"] = stream_args

        # 1 to start or 0 to stop
        if found:
            port = self.startstop_ceton_tuner(instance, 1)
        else:
            port = None
            self.plugin_utils.logger.error('No Ceton tuners available')

        if port:
            tuned = self.set_ceton_tuner(chandict, instance)
            self.plugin_utils.logger.info('Preparing Ceton tuner %s on port: %s' % (instance, port))
        else:
            tuned = None

        self.get_ceton_getvar(instance, "Frequency")
        self.get_ceton_getvar(instance, "ProgramNumber")
        self.get_ceton_getvar(instance, "CopyProtectionStatus")

        if tuned:
            if not self.ceton_pcie:
                self.plugin_utils.logger.info('Initiate streaming channel %s from Ceton tuner#: %s ' % (chandict['origin_number'], instance))
                streamurl = "udp://127.0.0.1:%s" % port
            else:
                # PCIe, only use /dev, not rtp => no additional logic needed to handle this then, and can still change stream_method (direct, ffmpeg)
                self.plugin_utils.logger.info('Initiate PCIe direct streaming, channel %s from Ceton tuner#: %s ' % (chandict['origin_number'], instance))
                streamurl = "/dev/ceton/ctn91xx_mpeg0_%s" % instance
        else:
            streamurl = None

        stream_info = {"url": streamurl, "tuner": instance}

        return stream_info

    def close_stream(self, instance, stream_args):
        closetuner = stream_args["stream_info"]["tuner"]
        self.plugin_utils.logger.noob('Closing Ceton tuner %s (fHDHR tuner %s)' % (closetuner, instance))
        self.startstop_ceton_tuner(closetuner, 0)
        return
