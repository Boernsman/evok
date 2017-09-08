# Evok - the UniPi API

Evok is the primary WEB API for the [NEURON] and [UniPi 1.1]. It provides a RESTful interface over HTTP, remote-procedure calls and WebSocket interface to relays, digital and analog inputs, digital and analog outputs, board information, leds, and more.

_**Support for Neuron is available only in the master branch (for now), not in the legacy release version. Please see [intructions below]!**_
 
Evok is still very much in active development, so any testing, contributions or feedback is welcome and appreciated.

Access to GPIOs is done using the fantastic [PIGPIO] library. Make sure to install it first before use.

It also uses some other python libraries that are not installed on Raspbian by default:
* python-ow
* [tornado]
* [toro]
* modified version of [tornardorpc] available in this repo tornadorpc_evok
* [jsonrpclib]

# Installation process for UniPi 1.1

Download the latest release from our repository via wget (alternatively you can clone the repository using git):

    wget https://github.com/UniPiTechnology/evok/archive/v.1.0.2.tar.gz
    tar -zxvf v.1.0.2.tar.gz && mv evok-* evok  

Please note that the folder that you downloaded the package into is not used later and can be safely deleted after the installation. Configuration files are installed directly into /etc/, /opt/ and /boot/

Run the installation script using the following instructions

    cd evok
    chmod +x install-evok.sh uninstall-evok.sh
    sudo ./install-evok.sh

To uninstall it, run the uninstallation script, which is located in the `/opt/evok/` folder after Evok has been installed

    sudo ./uninstall-evok.sh


If you wish to manually changed the configuration of evok, it can be done through the /etc/evok.conf file.

Note that after uninstalling Evok you have to reboot your device to ensure all the files and settings are gone. 

The installation script also enables the I2C subsystem (if not enabled before), but the uninstallation script does not disable it again.

# Debugging

When reporting a bug or posting questions to [our forum] please set proper logging levels in /etc/evok.conf, restart your device and check the log file (/var/log/evok.log). For more detailed log information you can also run evok by hand. To do that you need to first stop the service by executing the

    systemctl stop evok

command and then run it manually as root user 
    
    sudo python /opt/evok/evok.py

and look through/paste the output of the script.

# Installing Evok for Neuron (Beta only for now)

The installation script should take care of everything, but be aware there may be some issues with limited and/or broken functionality. Please report any bugs you find on this github repository.

To install first connect to your Neuron via SSH (username root: password unipi; or whichever you have changed it to from the default) and run the following:

    wget https://github.com/UniPiTechnology/evok/archive/master.zip
    unzip master.zip
    cd evok-master
    bash install-evok.sh

# API examples

There are many ways of controlling your UniPi device, the easiest is using a web browser (make sure to copy the www folder to your desired location and edit evok.conf file) and them simply visit

    http://your.pi.ip.address:88

It will show you something like this

todo: gif

The example web interface is using websocket to receive all events from the UniPi and controls the UniPi device via the REST api.

## REST API:
### HTTP GET
To get a state of your device you can send a HTTP GET request to evok:

    GET /rest/DEVICE/CIRCUIT

or:

    GET /rest/DEVICE/CIRCUIT/PROPERTY

Where DEVICE can be substituted by any of these: 'relay', 'di' or 'input', 'ai' or 'analoginput, 'ao' or 'analogoutput', 'sensor', 'neuron', 'led', 'register' CIRCUIT is the number of circuit (in case of 1Wire sensor, it is its address) corresponding to the number in your configuration file and PROPERTY is mostly 'value'.

### HTTP POST
Simple example using wget to get status of devices:
* `wget -qO- http://your.pi.ip.address/rest/all` returns status of all devices configured in evok.conf
* `wget -qO- http://your.pi.ip.address/rest/relay/1` returns status of relay with circuit nr. 1
* `wget -qO- http://your.pi.ip.address/rest/relay/1/value` returns whether the relay 1 is on or of (1/0)
* `wget -qO- http://your.pi.ip.address/rest/ao/1/value` returns the value of analog output
* `wget -qO- http://your.pi.ip.address/rest/ai/1/value` returns the value of analog input

To control a device, all requests must be sent by HTTP POST. Here is a small example of controlling a relay:
* `wget -qO- http://your.pi.ip.address/rest/relay/3 --post-data='value=1'` sets relay on
* `wget -qO- http://your.pi.ip.address/rest/relay/3 --post-data='value=0'` sets relay off
* `wget -qO- http://your.pi.ip.address/rest/ao/1 --post-data='value=5'` set AO to 5V 

### Websocket
Register your client at ws://your.unipi.ip.address/ws to receive status messages. Once it is connected, you can also send various commands to the UniPi
All messages in websocket are sent in JSON string format, eg. {"dev":"relay", "circuit":"1", "value":"1"} to set Relay 1 On.
Check the wsbase.js in www/js/ folder to see example of controlling the UniPi using websocket.

### Python using JsonRPC
You can also control the UniPi using Python library [jsonrpclib]. See the list of all available methods below.

    from jsonrpclib import Server
    s=Server("http://your.pi.ip.address/rpc")
    s.relay_set(1,1)
    s.relay_get(1)
    s.relay_set(1,0)
    s.relay_get(0)
    s.ai_get(1)

### Python using WebSocket

    import websocket
    import json

    url = "ws://your.unipi.ip.address/ws"

    def on_message(ws, message):
        obj = json.loads(message)
        dev = obj['dev']
        circuit = obj['circuit']
        value = obj['value']
        print message

    def on_error(ws, error):
        print error

    def on_close(ws):
        print "Connection closed"

    #receiving messages
    ws = websocket.WebSocketApp(url, on_message = on_message, on_error = on_error, on_close = on_close)
    ws.run_forever()

    #sending messages
    ws = websocket.WebSocket()
    ws.connect(url)
    ws.send('{"cmd":"set","dev":"relay","circuit":"3","value":"1"}')
    ws.close()

### Perl using JsonRPC
A simple example of controlling the UniPi via RPC
    use JSON::RPC::Client;

    use JSON::RPC::Client;

    my $client = new JSON::RPC::Client;
    my $url    = 'http://your.pi.ip.address/rpc';

    $client->prepare($url, ['relay_set']);
    $client->relay_set(1,1);

There is also a [websocket client library for Perl] to get more control.

##List of available devices:
* `relay` - relay
* `input` or `di` - digital input 
* `ai` - analog input
* `ao` - analog output
* `ee` - onboard eeprom
* `sensor` - 1wire sensor
* the rest can be found in devices.py 

##List of available methods:

* Digital Inputs
    * `input_get(circuit)` - get all information of input by circuit number
    * `input_get_value(circuit)` - get actual state f input by circuit number, returns 0=off/1=on
    * `input_set(circuit)` - sets the debounce timeout
* Relays
    * `relay_get(circuit)` - get state of relay by circuit number
    * `relay_set(circuit, value)` - set relay by circuit number according value 0=off, 1=on
    * `relay_set_for_time(circuit, value, timeout)` - set relay by circuit number according value 0=off, 1=on for time(seconds) timeout
* Analog Inputs
    * `ai_get(circuit)` - get value of analog input by circuit number
    * `input_get`
* Analog Output
    * `ao_set_value(circuit, value)` - set the value(0-10) of Analog Output by circuit number
* 1-Wire bus
    * `owbus_scan(circuit)` - force to scan 1Wire network for new devices
* 1-Wire sensors
    * `sensor_get(circuit)` - returns all information in array [value, is_lost, timestamp_of_value, scan_interval] of sensor by given circuit or 1Wire address
    * `sensor_get_value(circuit)` - returns value of a circuit by given circuit or 1Wire address

More methods can be found in the src file evok.py or owclient.py.

Todo list:
============
* authentication

Known issues/bugs
============
* todo

Development
============
Want to contribute? Have any improvements or ideas? Great! We are open to all ideas. Contact us on info at unipi DOT technology

License
============
Apache License, Version 2.0

----
Raspberry Pi is a trademark of the Raspberry Pi Foundation

[IndieGogo]:https://www.indiegogo.com/projects/unipi-the-universal-raspberry-pi-add-on-board
[NEURON]:http://www.unipi.technology
[UniPi 1.1]:https://www.unipi.technology/products/unipi-1-1-19?categoryId=1&categorySlug=unipi-1-1
[PIGPIO]:http://abyz.co.uk/rpi/pigpio/
[tornado]:https://pypi.python.org/pypi/tornado/
[toro]:https://pypi.python.org/pypi/toro/
[tornardorpc]:https://github.com/joshmarshall/tornadorpc
[jsonrpclib]:https://github.com/joshmarshall/jsonrpclib
[websocket client library for Perl]:https://metacpan.org/pod/AnyEvent::WebSocket::Client
[websocket Python library]:https://pypi.python.org/pypi/websocket-client/
[our forum]:http://forum.unipi.technology/
[intructions below]:https://github.com/UniPiTechnology/evok#testing-latest-git-versions
