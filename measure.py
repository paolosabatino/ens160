from smbus2 import SMBus
from ens160 import Ens160
import datetime
import time

"""
    DESCRIPTION:
    
    Sample script to do continuous (every second) measurements from the ENS160 sensor.
    The sensor will be kept in STANDARD mode after initialization (ie: the normal running mode) and will be peeked
    every second for new data.

    This script is ideal if the sensor has to report the measurement perpetually but, since the sensor heats up to 
    take accurate measurements, will severely interfere with other nearby temperature of humidity sensors 
"""

bus_id = 1

bus = SMBus(bus_id)
ens160 = Ens160(bus, 0x53)

ens160.irq_setup(True)

print("Detected ENS160")
print("Firmware version: %s" % (ens160.firmware,))

try:
    while True:

        time.sleep(1)

        # Try to take a reading from the sensor.
        # If there is no new data, try again later
        new_data = ens160.do_measure()
        if new_data is False:
            continue

        # If there is new data, print out what we found
        reading_time = datetime.datetime.fromtimestamp(ens160.time)
        print("Acquisition at %s - isInitialStartup: %s, isWarmUp: %s, Air quality index: %d, TVOC (ppb): %d, eCO2 (ppm): %d" %
              (reading_time.strftime("%Y-%m-%d %H:%M:%S"), ens160.is_initial_startup, ens160.is_warm_up, ens160.aqi, ens160.tvoc, ens160.eco2))

except KeyboardInterrupt:
    pass
except Exception as e:
    print("Exception: %s" % (e,))

ens160.shutdown()

print("done")
