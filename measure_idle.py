from smbus2 import SMBus
from ens160 import Ens160
import datetime
import time

"""
    DESCRIPTION:
    
    Sample script to do sporadic readings from the sensor, where most of the time the sensor is put in idle/low power mode.
    The sensor will be initialized and, after taking a measurement, it will be kept in idle mode for 1 minute.
    Then it will be wake up and, after taking a valid measurement, it will be put again in idle mode.

    This script is ideal if the sensor is nearby other temperature or humidity sensors and this kind of cycling will
    reduce the reading issues from other sensors. The larger the idle times, the less interferences are to other nearby
    sensors.
    
    Also this cycle mode reduces a lot the power consumption of the chip, so it is handy in low-power applications too. 
"""

bus_id = 1

bus = SMBus(bus_id)
ens160 = Ens160(bus, 0x53)

print("Detected ENS160")
print("Firmware version: %s" % (ens160.firmware,))

try:
    while True:

        time.sleep(1)

        new_data = ens160.do_measure()
        if new_data is False:
            continue

        # If there is new data, print out what we found
        reading_time = datetime.datetime.fromtimestamp(ens160.time)
        print("Acquisition at %s - isInitialStartup: %s, isWarmUp: %s, Air quality index: %d, TVOC (ppb): %d, eCO2 (ppm): %d" %
              (reading_time.strftime("%Y-%m-%d %H:%M:%S"), ens160.is_initial_startup, ens160.is_warm_up, ens160.aqi, ens160.tvoc, ens160.eco2))

        # Put the ens160 chip in idle and wait for 60 seconds
        ens160.idle()
        time.sleep(60)

        # Wake up the sensor again and bring it into standard mode to take measurement
        ens160.wakeup()

except KeyboardInterrupt:
    pass
except Exception as e:
    print("Exception: %s" % (e,))

ens160.shutdown()

print("done")
