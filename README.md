# ens160
ENS160 is small python library and companion measurement example scripts. Reduces traffic on the i2c bus to the least amount required to get a fully working device and aims to completely cover the ens160 features.
Only i2c bus is supported with this library.

# Dependencies
The only dependency is smbus2 library

# Power modes

Before delving into simple and advanced usage and patterns, it is important to know that the ENS160 chip has three modes of operation: **deep sleep**, **idle** and **standard**. 

The only mode that provides valid data is **standard**, which continuously reads the sensors raw data and produces refined data to be read by end user.

When in **standard** mode, the chip also heats up due to the built-in heaters that are used to get accurate values from the sensors; this is also makes the chip require more power.

This library provides methods to switch the chip from a mode into another. You can leverage such facility to implement different patterns of operation. This is particularly sensible when the ENS160 chip is physically mounted nearby other temperature/humidity sensors like AHT20 or BMP280.

The chip is also designed to provide most accurate data when it has warmed up for enough time (3 minutes), but there are caveats on very first time it is turn on (see the datasheet at chapter 10) 

# Basic usage

```python
from smbus2 import SMBus
from ens160 import Ens160
import time

bus_id = 1
address = 0x53

bus = SMBus(bus_id)
ens160 = Ens160(bus, address)

# After initialization, the chip is in idle mode.
# We use wakeup() to switch the chip in standard mode and do measurements
ens160.wakeup()

# Try to take a reading from the sensor. 
# do_measure() returns True if there is new data and False if there is no new data.
# In case it returns False, we wait for 1 second and try again 
while ens160.do_measure() is False:
    time.sleep(1)   

# Print out the data we found
print("AIQ=%d - TVOC=%d ppb - eCO2=%d ppm" % (ens160.aiq, ens160.tvoc, ens160.eco2))

# Bring the chip into deep sleep
ens160.shutdown()

```

# Advanced usage

More advanced usage is available in the sample scripts:

- **measure.py**: relatively simple script that runs continuously peeking data from the ens160 every second
- **measure_idle.py**: do a reading from the ens160 and then put it into **idle** for an amount of time; this kind of behaviour is supposed to reduce the power usage and heat produced by the chip
- **measure_irq.py**: similar to measure.py, but more advanced which leverages interrupt request using Linux GPIO sysfs object and poll() syscall in place of simple polling