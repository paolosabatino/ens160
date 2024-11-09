#!/usr/bin/python

from smbus2 import SMBus
from ens160 import Ens160
import datetime
import sys
import select

"""
    DESCRIPTION:

    Sample script to do continuous measurements from the ENS160 sensor via IRQ line instead of simple polling
    The sensor will be kept in STANDARD mode after initialization (ie: the normal running mode).
    
    The main thread will sleep on poll() syscall on a GPIO offered by the kernel interface, so whenever new
    data is available, the main thread will be woken up and can read new data.
    
    The GPIO file object has to be supplied as an argument to the command line script.
     
"""

if len(sys.argv) < 2:
    print("ENS160 sample script with IRQ line")
    print()
    print("Instructions:")
    print()
    print("1) Export the interrupt GPIO to userspace in /sys/class/gpio")
    print("2) Run the program like this: %s < /sys/kernel/gpio/gpio6" % (sys.argv[0],))
    print()
    print("Notes:")
    print("The exported GPIO must show the \"edge\" file, otherwise it is not capable of")
    print("handling interrupts and thus won't work")
    print()
    print("References:")
    print("https://stackoverflow.com/questions/56166622/how-to-handle-gpio-interrupt-like-handling-in-linux-userspace")
    print("https://mjmwired.net/kernel/Documentation/gpio.txt#621")
    print("https://stackoverflow.com/questions/8723911/linux-userspace-gpio-interrupts-using-sysfs")
    exit(0)

# Set up the sysfs gpio as interrupt configuring it as falling edge
# and active low. These parameters must be set accordingly when calling
# Ens160.irq_setup() method
try:
    gpio = sys.argv[1]
    open(f"{gpio}/direction", "wt").write("in")
    open(f"{gpio}/edge", "wt").write("falling")
    open(f"{gpio}/active_low", "wt").write("1")
    gpio_value = open(f"{gpio}/value", "rt")
    poll = select.poll()
    poll.register(gpio_value, select.POLLPRI | select.POLLERR)
except Exception as e:
    print("Could not configure sysfs GPIO as interrupt. Reason: %s" % (e,))
    exit(1)

bus_id = 1

bus = SMBus(bus_id)
ens160 = Ens160(bus, 0x53)

print("Detected ENS160")
print("Firmware version: %s" % (ens160.firmware,))

ens160.irq_setup(True)
ens160.wakeup()

try:
    while True:

        # Read the data from the gpio sysfs object.
        # This acts like an "interrupt acknowledged" signal, so poll() will wait for an actual
        # interrupt to happen
        gpio_value.seek(0)
        gpio_value.read()

        # Wait on poll(), when the IRQ is set, this call will unblock
        poll.poll()

        # Since we have been acknowledged by an interrupt, we are safe to do_measure() to get
        # the actual data.
        new_data = ens160.do_measure()

        # If there is new data, print out what we found
        reading_time = datetime.datetime.fromtimestamp(ens160.time)

        print(
            "Acquisition at %s - isInitialStartup: %s, isWarmUp: %s, Air quality index: %d, TVOC (ppb): %d, eCO2 (ppm): %d" %
            (reading_time.strftime("%Y-%m-%d %H:%M:%S"), ens160.is_initial_startup, ens160.is_warm_up, ens160.aqi,
             ens160.tvoc, ens160.eco2))

except KeyboardInterrupt:
    pass
except Exception as e:
    print("Exception: %s" % (e,))

# Cleanup, bring the ens160 into deep sleep
ens160.shutdown()

# Unregister the poll facility and close the gpio sysfs object
poll.unregister(gpio_value.fileno())
gpio_value.close()

print("done")
