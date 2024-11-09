import math
from smbus2 import SMBus
import time

class Ens160(object):
    """
        Class to interact with ENS160 MOX sensor chip
    """

    ENS160_PART_ID = 0x160

    REG_PART_ID = 0x00

    REG_OP_MODE = 0x10
    REG_CONFIG = 0x11
    REG_COMMAND = 0x12
    REG_TEMP_IN = 0x13
    REG_RH_IN = 0x15

    REG_STATUS = 0x20
    REG_DATA_AQI = 0x21
    REG_DATA_TVOC = 0x22
    REG_DATA_ECO2 = 0x24
    REG_DATA_T = 0x30
    REG_DATA_RH = 0x32
    REG_DATA_MISR = 0x38

    # There are 8 GPR_WRITE registers, this attribute
    # declares the offset of the first one
    REG_GPR_WRITE_START = 0x40

    # There are 8 GPR_READ registers, this attribute
    # declares the offset of the first one
    REG_GPR_READ_START = 0x48

    # Status register bitmasks
    BIT_STATAS = 1 << 7
    BIT_STATER = 1 << 6
    BIT_VALIDITY = (1 << 2) | (1 << 3)
    SHIFT_VALIDITY = 2
    BIT_NEWDAT = 1 << 1
    BIT_NEWGPR = 1 << 0

    # Validity flag values
    VALIDITY_NORMAL = 0x0
    VALIDITY_WARM_UP = 0x1
    VALIDITY_INITIAL_STARTUP = 0x2
    VALIDITY_INVALID = 0x3

    COMMAND_NOP = 0x00
    COMMAND_GET_APPVER = 0x0e
    COMMAND_CLRGPR = 0xcc

    OPMODE_DEEP_SLEEP = 0x0
    OPMODE_IDLE = 0x1
    OPMODE_STANDARD = 0x2
    OPMODE_RESET = 0xf0

    DEFAULT_ADDRESS = 0x52

    DEFAULT_TEMPERATURE = 20.0
    DEFAULT_HUMIDITY = 50.0

    def __init__(self, bus: SMBus, address: int = DEFAULT_ADDRESS):
        """
        :param bus: SMBus instance of the bus where the sensor is allocated
        :param address: address of the sensor on the bus
        """
        # i2c instance
        self.bus = bus

        # address of the sensor
        self.address = address

        # Read only: air quality parameter
        self._aqi = None

        # Read only: total volatile compounds parameter
        self._tvoc = None

        # Read only: equivalent CO2 parameter
        self._eco2 = None

        # Read only: timestamp of the last valid reading
        self._time = None

        # Read only: reference temperature and humidity used by the sensor to calibrate the values
        self._ref_temp = None
        self._ref_humidity = None

        # Validity of the reading: when the sensor is turn on for the first time, it requires 48 hours to
        # reach a stable status (initial startup) and approximate readings are available after one hour
        # When it is going back from an off/idle state, it requires 3 minutes to become operative (warm-up)
        #
        # See chapters 10 and 11 of the datasheet for further reference
        self._validity = None

        # Do the initialization of the chip and proper checks
        self._initialize()

    def _wait_on_status_bit(self, bit):
        """
        Waits for a status bit to turn on
        :param bit:
        :return:
        """
        while True:
            status = self.bus.read_byte_data(self.address, Ens160.REG_STATUS)
            if status & bit:
                break
            time.sleep(0.001)

    def _set_operating_mode(self, mode: int):
        """
            Private method to set the operating mode of the chip
        :param mode: int One of the Ens160.OPMODE_* values, except for OPMODE_RESET, which is for internal use only
        :return:
        """
        if mode not in (Ens160.OPMODE_DEEP_SLEEP, Ens160.OPMODE_IDLE, Ens160.OPMODE_STANDARD):
            raise ValueError("Invalid operating mode")

        self.bus.write_byte_data(self.address, Ens160.REG_OP_MODE, mode)

    def _initialize(self):
        """
            Private initialization of the chip
        :return:
        """
        bus = self.bus
        address = self.address

        # Reset the chip
        bus.write_byte_data(address, Ens160.REG_OP_MODE, Ens160.OPMODE_RESET)
        time.sleep(0.01)

        # Move the chip into idle mode, otherwise we can't read or write the registers
        # and expect they get changed or return anything useful
        self.idle()

        # Get the part ID of the chip and verify it matches with expected
        part_id = bus.read_word_data(address, self.REG_PART_ID)
        if part_id != Ens160.ENS160_PART_ID:
            raise ValueError("The I2C part on the given bus and address is not an ENS160 chip")

        # Get the firmware version, three bytes starting from GPR_READ4
        bus.write_byte_data(address, self.REG_COMMAND, Ens160.COMMAND_GET_APPVER)
        self._wait_on_status_bit(self.BIT_NEWGPR)
        data = bus.read_i2c_block_data(address, Ens160.REG_GPR_READ_START + 4, 3)
        self._firmware = ".".join(str(digit) for digit in data)

        # Initialize the chip with IRQ line disabled. If the users wants IRQ, has to enable it when opportune
        self.irq_setup(False)

        # Set a default value for temperature and relative humidity, otherwise
        # we can't get valid readings. These values should be set to real values
        # for best precision
        self.ref_temp = Ens160.DEFAULT_TEMPERATURE
        self.ref_humidity = Ens160.DEFAULT_HUMIDITY

        self.wakeup()

    @property
    def firmware(self):
        """
        :return: str The firmware version of the chip
        """
        return self._firmware

    @property
    def aqi(self) -> int:
        return self._aqi

    @property
    def tvoc(self) -> int:
        return self._tvoc

    @property
    def eco2(self) -> int:
        return self._eco2

    @property
    def time(self) -> float:
        return self._time

    @property
    def ref_temp(self) -> float:
        return self._ref_temp

    @property
    def ref_humidity(self) -> float:
        return self._ref_humidity

    @ref_temp.setter
    def ref_temp(self, temperature: float):
        """
        Set the current reference ambient temperature in Celsius degrees to allow the chip do proper calibration
        :param temperature:
        :return:
        """
        kelvin = temperature + 273.15
        word = round(kelvin * 64.0)
        self.bus.write_word_data(self.address, Ens160.REG_TEMP_IN, word)

    @ref_humidity.setter
    def ref_humidity(self, humidity: float):
        """
        Set the current reference ambient relative humidity in percentage to allow the chip do proper calibration
        :param humidity:
        :return:
        """
        word = round(humidity * 512)
        self.bus.write_word_data(self.address, Ens160.REG_RH_IN, word)

    @property
    def is_warm_up(self) -> bool:
        return self._validity == Ens160.VALIDITY_WARM_UP

    @property
    def is_initial_startup(self) -> bool:
        return self._validity == Ens160.VALIDITY_INITIAL_STARTUP

    def do_measure(self) -> bool:
        """
        Do a measurement cycle reading data from the chip.
        The chip, when in an operating mode, will continuously produce data; this method will ask the chip if
        there is new data and transfer the last valid values to instance attribute for reading by end user
        application.
        :return: bool True if new data have been read, False if there is no new data from the sensor
        """

        # Read the status register to check if the chip contains new data to be read
        status = self.bus.read_byte_data(self.address, Ens160.REG_STATUS)

        # statas bit: if set, indicates and OPMODE is running, otherwise the chip is idling/sleeping
        statas = status & Ens160.BIT_STATAS
        if not statas:
            return False  # The chip is not in a running mode, hence no measurements can be taken

        # stater bit: if set, the chip is indicating an error, like an invalid operating mode
        stater = status & Ens160.BIT_STATER
        if stater:
            return False  # The chip in indicating and error condition

        # validity flag: if the value is 3, the output is invalid and we trigger and exception
        validity = (status & Ens160.BIT_VALIDITY) >> Ens160.SHIFT_VALIDITY
        if validity == Ens160.VALIDITY_INVALID:
            return False  # The chip is indicating an invalid output

        # new data flag: if set, the AQI/TVOC and ECO2 registers have new data
        new_data = status & Ens160.BIT_NEWDAT

        # new gpr flag: if set, the GPR registers have new data, otherwise they don't
        new_gpr = status & Ens160.BIT_NEWGPR

        # In case the chips is reporting that new data is available, we gather:
        # - the aqi/tvoc/eco2 data
        # - the reference temperature and humidity from the registers
        # - the MISR byte for the validation checksum
        # then we do the proper calculations and update the instance status
        if new_data:
            data_air_quality = self.bus.read_i2c_block_data(self.address, Ens160.REG_DATA_AQI, 5)
            data_reference_params = self.bus.read_i2c_block_data(self.address, Ens160.REG_DATA_T, 4)
            data_misr = self.bus.read_byte_data(self.address, Ens160.REG_DATA_MISR)

            # Update the instance timestamp of the reading
            self._time = time.time()

            self._aqi = data_air_quality[0]
            self._tvoc = data_air_quality[1] | (data_air_quality[2] << 8)
            self._eco2 = data_air_quality[3] | (data_air_quality[4] << 8)

            reference_temp = data_reference_params[0] | (data_reference_params[1] << 8)
            reference_temp = (reference_temp / 64.0) - 273.15
            self._ref_temp = reference_temp

            self._ref_humidity = (data_reference_params[2] | (data_reference_params[3] << 8)) / 512.0

            self._validity = validity

        # Return True if there is new data, False if data is from older iterations
        return bool(new_data)

    def shutdown(self):
        """
        Put the chip in deep sleep mode. Ideally, this mode should be set when the application is exiting
        and the chip is not in use anymore
        :return:
        """
        self._set_operating_mode(Ens160.OPMODE_DEEP_SLEEP)

    def idle(self):
        """
        Put the chip in idle mode, useful to trigger a low power state between measurements. The chip, when in
        standard/running mode, heats up because of the built-in heaters necessary for the measurements and the heat
        may disturb nearby temperature/humidity sensors. It could be handy to put the chip in idle state when not
        in active use.
        :return:
        """
        self._set_operating_mode(Ens160.OPMODE_IDLE)

    def wakeup(self):
        """
        Put the chip in standard operating mode
        :return:
        """
        self._set_operating_mode(Ens160.OPMODE_STANDARD)

    def irq_setup(self, enable: bool, active_low: bool = True, open_drain: bool = True, assert_data: bool = True,
                  assert_gpr: bool = False):
        """
        Set up the irq line of the ENS160 chip with given parameters. This method will just set the register in the
        chip with the proper values, handling the interrupt is outside the scope of this library
        :param enable: if true, the interrupt line of the ENS160 chip in active
        :param active_low: if true, the interrupt pin is configured to be active low, otherwise is active high
        :param open_drain: if true, the pin is open drain, otherwise it is push-pull
        :param assert_data: if true, the interrupt will be triggered when new data is available
        :param assert_gpr: if true, the interrupt will be triggered when new data in GPR registers is available
        :return:
        """
        reg = (int(enable) << 0
               | int(active_low) << 6
               | int(open_drain) << 5
               | int(assert_data) << 1
               | int(assert_gpr) << 3)

        self.bus.write_byte_data(self.address, self.REG_CONFIG, reg)