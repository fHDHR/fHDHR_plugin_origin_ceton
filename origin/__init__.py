import base64
import re
import time
import xmltodict

from random import randint


class Plugin_OBJ():

    def __init__(self, plugin_utils):
        self.plugin_utils = plugin_utils

        self.tuners = self.plugin_utils.config.dict["ceton"]["tuners"]
        self.stream_method = self.plugin_utils.config.dict["ceton"]["stream_method"]

        count = int(self.plugin_utils.config.dict["ceton"]["tuners"])
        for i in range(count):
            self.startstop_ceton_tuner(i, 0)

    def get_ceton_getvar(self, instance, query):
        query_type = {
                      "Frequency": "&s=tuner&v=Frequency",
                      "ProgramNumber": "&s=mux&v=ProgramNumber",
                      "CopyProtectionStatus": "&s=diag&v=CopyProtectionStatus",
                      "Temperature": "&s=diag&v=Temperature",
                      "Signal_Level": "&s=diag&v=Signal_Level",
                      "Signal_SNR": "&s=diag&v=Signal_SNR",
                      "TransportState": "&s=av&v=TransportState"
                     }

        getVarUrl = ('http://%s/get_var?i=%s%s' % (self.plugin_utils.config.dict["ceton"]["ceton_ip"], instance, query_type[query]))

        try:
            getVarUrlReq = self.plugin_utils.web.session.get(getVarUrl)
            getVarUrlReq.raise_for_status()
        except self.plugin_utils.web.exceptions.HTTPError as err:
            self.plugin_utils.logger.error('Error while getting Ceton tuner variable for %s: %s' % (query, err))
            return None

        result = re.search('get.>(.*)</body', getVarUrlReq.text)

        return result.group(1)

    def get_ceton_tuner_status(self, chandict):
        found = 0
        count = int(self.plugin_utils.config.dict["ceton"]["tuners"])
        for instance in range(count):

            result = self.get_ceton_getvar(instance, "TransportState")

            if result == "STOPPED":
                self.plugin_utils.logger.info('Selected Ceton tuner#: %s' % instance)
                found = 1
                break

        return found, instance

    def startstop_ceton_tuner(self, instance, startstop):
        if not startstop:
            port = 0
            self.plugin_utils.logger.info('Ceton tuner %s to be stopped' % str(instance))
        else:
            port = randint(41001, 49999)
            self.plugin_utils.logger.info('Ceton tuner %s to be started' % str(instance))

        StartStopUrl = ('http://' + self.plugin_utils.config.dict["ceton"]["ceton_ip"] +
                        '/stream_request.cgi'
                        )

        StartStop_data = {"instance_id": instance,
                          "dest_ip": self.plugin_utils.config.dict["fhdhr"]["address"],
                          "dest_port": port,
                          "protocol": 0,
                          "start": startstop}
        # StartStopUrl_headers = {
        #                    'Content-Type': 'application/json',
        #                    'User-Agent': "curl/7.64.1"}

        try:
            StartStopUrlReq = self.plugin_utils.web.session.post(StartStopUrl, StartStop_data)
            StartStopUrlReq.raise_for_status()
        except self.plugin_utils.web.exceptions.HTTPError as err:
            self.plugin_utils.logger.error('Error while setting station stream: %s' % err)
            return None

        return port

    def set_ceton_tuner(self, chandict, instance):
        tuneChannelUrl = ('http://' + self.plugin_utils.config.dict["ceton"]["ceton_ip"] +
                          '/channel_request.cgi'
                          )
        tuneChannel_data = {"instance_id": instance,
                            "channel": chandict['number']}

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

        count_url = ('http://' + self.plugin_utils.config.dict["ceton"]["ceton_ip"] +
                     '/view_channel_map.cgi?page=1')

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
            stations_url = "http://%s/view_channel_map.cgi?page=%s&xml=1" % (self.plugin_utils.config.dict["ceton"]["ceton_ip"], page)

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
            self.plugin_utils.logger.info('Initiate streaming channel %s from Ceton tuner#: %s ' % (chandict['number'], instance))
            streamurl = "udp://127.0.0.1:%s" % port
        else:
            streamurl = None

        stream_info = {"url": streamurl}

        return stream_info

    def close_stream(self, instance, args):

        self.startstop_ceton_tuner(instance, 0)

        return
