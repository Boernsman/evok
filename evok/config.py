
import multiprocessing
import re
import struct
import ConfigParser
from log import *
from devices import *

try:
  import unipig
  from apigpio import I2cBus, GpioBus
except:
  pass


globals = {
    'version': "1.0",
    'devices': {
        'ai': {
            '1': 5.564920867,
            '2': 5.564920867,
        }
    },
    'version1': None,
    'version2': None,
}


def read_eprom_config():
    try:
        with open('/sys/class/i2c-dev/i2c-1/device/1-0050/eeprom','r') as f:
            bytes=f.read(256)
            if bytes[224:226] == '\xfa\x55':
                if ord(bytes[226]) == 1 and ord(bytes[227]) == 1:
                    globals['version'] = "UniPi 1.1"
                elif ord(bytes[226]) == 11 and ord(bytes[227]) == 1:
                    globals['version'] = "UniPi Lite 1.1"
                else:
                    globals['version'] = "UniPi 1.0"
                globals['version1'] = globals['version']
                #AIs coeff
                if globals['version'] in ("UniPi 1.1", "UniPi 1.0"):
                    globals['devices'] = { 'ai': {
                                              '1': struct.unpack('!f', bytes[240:244])[0],
                                              '2': struct.unpack('!f', bytes[244:248])[0],
                                         }}
                else:
                    globals['devices'] = { 'ai': {
                                              '1': 0,
                                              '2': 0,
                                         }}
                globals['serial'] = struct.unpack('i', bytes[228:232])[0]
                logger.debug("eprom: UniPi version %s, serial: %d", globals['version'], globals['serial'])
    except Exception, E:
        pass

    try:
        with open('/sys/class/i2c-dev/i2c-1/device/1-0057/eeprom','r') as f:
            bytes=f.read(128)
            if bytes[96:98] == '\xfa\x55':
                globals['version2'] = "%d.%d" % (ord(bytes[99]), ord(bytes[98]))
                globals['model'] = "%s" % (bytes[106:110],)
                globals['serial'] = struct.unpack('i', bytes[100:104])[0]
                logger.debug("eprom: UniPi Neuron %s version: %s serial: 0x%x", globals["model"],globals['version2'],globals["serial"])
    except Exception, E:
        pass


class EvokConfig(ConfigParser.RawConfigParser):

    def __init__(self):
        ConfigParser.RawConfigParser.__init__(self)

    def configtojson(self):
        return dict(
             ( section, 
               dict(
                ( option,
                  self.get(section, option)
                ) for option in self.options(section))
             ) for section in self.sections())

    def getintdef(self, section, key, default):
        try:
            return self.getint(section, key)
        except:
            return default


    def getfloatdef(self, section, key, default):
        try:
            return self.getfloat(section, key)
        except:
            return default


    def getbooldef(self, section, key, default):
        true_booleans = ['yes', 'true', '1']
        false_booleans = ['no', 'false', '0']
        try:
            val = self.get(section, key).lower()
            if val in true_booleans:
                return True
            if val in false_booleans:
                return False
            return default
        except:
            return default


    def getstringdef(self, section, key, default):
        try:
            return self.get(section, key)
        except:
            return default


def hexint(value):
    if value.startswith('0x'):
        return int(value[2:], 16)
    return int(value)


def create_devices(Config):
    for section in Config.sections():
        # split section name ITEM123 or ITEM_123 or ITEM-123 into device=ITEM and circuit=123
        res = re.search('^([^_-]+)[_-]+(.+)$', section)
        if not res:
            res = re.search('^(.*\D)(\d+)$', section)
            if not res: continue
        devclass = res.group(1)
        # devclass = re.sub('[_-]*$','',devclass)
        # circuit = int(res.group(2))
        circuit = res.group(2)
        # print "%s %s %s" % (section,devclass, circuit)
        try:
            if devclass == 'OWBUS':
                import owclient
                bus = Config.get(section, "owbus")
                interval = Config.getfloat(section, "interval")
                scan_interval = Config.getfloat(section, "scan_interval")

                #### prepare 1wire process ##### (using thread affects timing!)
                resultPipe = multiprocessing.Pipe()
                taskPipe = multiprocessing.Pipe()
                owbus = owclient.OwBusDriver(circuit, taskPipe, resultPipe, bus=bus,
                                             interval=interval, scan_interval=scan_interval)
                Devices.register_device(OWBUS, owbus)
            elif devclass == 'SENSOR' or devclass == '1WDEVICE':
                #permanent thermometer
                bus = Config.get(section, "bus")
                owbus = Devices.by_int(OWBUS, bus)
                typ = Config.get(section, "type")
                address = Config.get(section, "address")
                interval = Config.getintdef(section, "interval", 15)
                sensor = owclient.MySensorFabric(address, typ, owbus, interval=interval, circuit=circuit,
                                                 is_static=True)
                Devices.register_device(SENSOR, sensor)
            elif devclass == '1WRELAY':
                # Relays on DS2404
                sensor = Config.get(section, "sensor")
                sensor = Devices.by_int(SENSOR, sensor)
                pin = Config.getint(section, "pin")
                r = unipig.DS2408_relay(circuit, sensor, pin)
                Devices.register_device(RELAY, r)
            elif devclass == '1WINPUT':
                # Inputs on DS2404
                sensor = Config.get(section, "sensor")
                sensor = Devices.by_int(SENSOR, sensor)
                pin = Config.getint(section, "pin")
                i = unipig.DS2408_input(circuit, sensor, pin)
                Devices.register_device(INPUT, i)
            elif devclass == 'I2CBUS':
                # I2C bus on /dev/i2c-1 via pigpio daemon
                busid = Config.getint(section, "busid")
                i2cbus = I2cBus(circuit=circuit, host='localhost', busid=busid)
                Devices.register_device(I2CBUS, i2cbus)
            elif devclass == 'MCP':
                # MCP on I2c
                i2cbus = Config.get(section, "i2cbus")
                address = hexint(Config.get(section, "address"))
                bus = Devices.by_int(I2CBUS, i2cbus)
                mcp = unipig.UnipiMcp(bus, circuit, address=address)
                Devices.register_device(MCP, mcp)
            elif devclass == 'RELAY':
                # Relays on MCP
                mcp = Config.get(section, "mcp")
                mcp = Devices.by_int(MCP, mcp)
                pin = Config.getint(section, "pin")
                r = unipig.Relay(circuit, mcp, pin)
                Devices.register_device(RELAY, r)
            elif devclass == 'GPIOBUS':
                # access to GPIO via pigpio daemon
                bus = GpioBus(circuit=circuit, host='localhost')
                Devices.register_device(GPIOBUS, bus)
            elif devclass == 'PCA9685':
                #PCA9685 on I2C
                i2cbus = Config.get(section, "i2cbus")
                address = hexint(Config.get(section, "address"))
                frequency = Config.getintdef(section, "frequency", 400)
                bus = Devices.by_int(I2CBUS, i2cbus)
                pca = unipig.UnipiPCA9685(bus, int(circuit), address=address, frequency=frequency)
                Devices.register_device(PCA9685, pca)
            elif devclass in ('AO', 'ANALOGOUTPUT'):
                try:
                    #analog output on PCA9685
                    pca = Config.get(section, "pca")
                    channel = Config.getint(section, "channel")
                    #value = Config.getfloatdef(section, "value", 0)
                    driver = Devices.by_int(PCA9685, pca)
                    ao = unipig.AnalogOutputPCA(circuit, driver, channel)
                except:
                    # analog output (PWM) on GPIO via pigpio daemon
                    gpiobus = Config.get(section, "gpiobus")
                    bus = Devices.by_int(GPIOBUS, gpiobus)
                    frequency = Config.getintdef(section, "frequency", 100)
                    value = Config.getfloatdef(section, "value", 0)
                    ao = unipig.AnalogOutputGPIO(bus, circuit, frequency=frequency, value=value)
                Devices.register_device(AO, ao)
            elif devclass in ('DI', 'INPUT'):
                # digital inputs on GPIO via pigpio daemon
                gpiobus = Config.get(section, "gpiobus")
                bus = Devices.by_int(GPIOBUS, gpiobus)
                pin = Config.getint(section, "pin")
                debounce = Config.getintdef(section, "debounce", 0)
                counter_mode = Config.getstringdef(section, "counter_mode", "disabled")
                inp = unipig.Input(bus, circuit, pin, debounce=debounce, counter_mode=counter_mode)
                Devices.register_device(INPUT, inp)
            elif devclass in ('EPROM', 'EE'):
                i2cbus = Config.get(section, "i2cbus")
                address = hexint(Config.get(section, "address"))
                size = Config.getintdef(section, "size", 256)
                bus = Devices.by_int(I2CBUS, i2cbus)
                ee = unipig.Eprom(bus, circuit, size=size, address=address)
                Devices.register_device(EE, ee)
            elif devclass in ('AICHIP',):
                i2cbus = Config.get(section, "i2cbus")
                address = hexint(Config.get(section, "address"))
                bus = Devices.by_int(I2CBUS, i2cbus)
                mcai = unipig.UnipiMCP342x(bus, circuit, address=address)
                Devices.register_device(ADCHIP, mcai)
            elif devclass in ('AI', 'ANALOGINPUT'):
                chip = Config.get(section, "chip")
                channel = Config.getint(section, "channel")
                interval = Config.getfloatdef(section, "interval", 0)
                bits = Config.getintdef(section, "bits", 14)
                gain = Config.getintdef(section, "gain", 1)
                if circuit in ('1', '2'):
                    correction = Config.getfloatdef(section, "correction", globals['devices']['ai'][circuit])
                else:
                    correction = Config.getfloatdef(section, "correction", 5.564920867)
                #print correction
                mcai = Devices.by_int(ADCHIP, chip)
                try:
                    corr_rom = Config.get(section, "corr_rom")
                    eeprom = Devices.by_int(EE, corr_rom)
                    corr_addr = hexint(Config.get(section, "corr_addr"))
                    ai = unipig.AnalogInput(circuit, mcai, channel, bits=bits, gain=gain,
                                            continuous=False, interval=interval, correction=correction, rom=eeprom,
                                            corr_addr=corr_addr)
                except:
                    ai = unipig.AnalogInput(circuit, mcai, channel, bits=bits, gain=gain,
                                            continuous=False, interval=interval, correction=correction)
                Devices.register_device(AI, ai)
            elif devclass == 'NEURON':
                from neuron import Neuron
                modbus_server =  Config.getstringdef(section, "modbus_server", "127.0.0.1")
                modbus_port   =  Config.getintdef(section, "modbus_port", 502)
                scanfreq = Config.getfloatdef(section, "scan_frequency", 1)
                scan_enabled = Config.getbooldef(section, "scan_enabled", True)
                neuron = Neuron(circuit, modbus_server, modbus_port, scanfreq, scan_enabled)
                Devices.register_device(NEURON, neuron)
            elif devclass == 'UNIPI2':
                '''from spiarm import ArmSpiAsync, ArmUart
                # UNIPI2 on SPI bus
                busdevice = Config.get(section, "busdevice")
                gpioint  = Config.getint(section, "gpioint")
                arm = ArmSpiAsync(circuit, busdevice, gpioint)
                Devices.register_device(UNIPI2, arm)
                if True:
                    import unipi2
                    for i in range(arm.nDO):
                        _r = unipi2.Relay("%s%02d" % (circuit,i+1),arm,i, 1, 0x1<<i)
                        Devices.register_device(RELAY, _r)
                    for i in range(arm.nDI):
                        _inp = unipi2.Input("%s%02d" % (circuit,i+1),arm, 0, 0x1<<i, ]#
                        
                        
                                            regdebounce=1006+i, 
                                            regcounter=arm.counter_reg+(2*i))
                        Devices.register_device(INPUT, _inp)
                    for i in range(arm.nAO):
                        _ao = unipi2.AnalogOutput("%s%02d" % (circuit,i+1),arm, 2+i)
                        Devices.register_device(AO, _ao)
                    for i in range(arm.nAI):
                        correction = 1.0 if i==0 else 1.0/3
                        _ai = unipi2.AnalogInput("%s%02d" % (circuit,i+1),arm, 3+i,
                                                 correction = correction)
                        Devices.register_device(AI, _ai)
                    arm.scanning = True
                '''

            elif devclass == 'UART':
                # UART on UNIPI2
                '''
                unipi2 = Config.get(section, "unipi2")
                unipi2 = Devices.by_int(UNIPI2, unipi2)
                uart = ArmUart(circuit,unipi2)
                Devices.register_device(UART, uart)
                '''
        except Exception, E:
            logger.debug("Error in config section %s - %s", section, str(E))
            #raise

