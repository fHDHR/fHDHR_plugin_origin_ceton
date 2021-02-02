<p align="center">fHDHR origin Plugin Ceton    <img src="docs/images/logo.ico" alt="Logo"/></p>



Welcome to the world of streaming content as a DVR device! We use some fancy python here to achieve a system of:

**f**un
**H**ome
**D**istribution
**H**iatus
**R**ecreation

fHDHR is labeled as beta until we reach v1.0.0

Join us in `#fHDHR <irc://irc.freenode.net/#fHDHR>`_ on Freenode.


# Installation

1) Review Installation guide located at [Docs](https://github.com/fHDHR/fHDHR/blob/main/docs/README.md)

2) Insert this plugin into the `plugins` directory of fHDHR using `git clone` or downloading a release zip file.

3) Adjust your configuration file with the below settings:

````
[ceton]
# ceton_ip = 
# tuners =
# streaming_method =
````
=======
Support for the stand-alone eth4 and eth6 versions of Ceton devices is confirmed.
The PCI devices might work, but due to a lack of hardware, have not been tested.

Unlike the other origin plugins, this one requires the fHDHR_plugin_stream_ffmpeg.
