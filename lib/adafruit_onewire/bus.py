# SPDX-FileCopyrightText: 2017 Carter Nelson for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_onewire.bus`
====================================================

Provide access to a 1-Wire bus.

* Author(s): Carter Nelson
"""

__version__ = "2.0.10"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_OneWire.git"

import onewireio
from micropython import const

try:
    from typing import List, Optional, Tuple

    from circuitpython_typing import ReadableBuffer, WriteableBuffer
    from microcontroller import Pin
except ImportError:
    pass

_SEARCH_ROM = const(0xF0)
_MATCH_ROM = const(0x55)
_SKIP_ROM = const(0xCC)
_MAX_DEV = const(10)


class OneWireError(Exception):
    """A class to represent a 1-Wire exception."""


class OneWireAddress:
    """A class to represent a 1-Wire address."""

    def __init__(self, rom: bytearray) -> None:
        self._rom = rom

    @property
    def rom(self) -> bytearray:
        """The unique 64 bit ROM code."""
        return self._rom

    @property
    def crc(self) -> int:
        """The 8 bit CRC."""
        return self._rom[7]

    @property
    def serial_number(self) -> bytearray:
        """The 48 bit serial number."""
        return self._rom[1:7]

    @property
    def family_code(self) -> int:
        """The 8 bit family code."""
        return self._rom[0]


class OneWireBus:
    """A class to represent a 1-Wire bus."""

    def __init__(self, pin: Pin) -> None:
        self._ow = onewireio.OneWire(pin)
        self._readbit = self._ow.read_bit
        self._writebit = self._ow.write_bit
        self._maximum_devices = _MAX_DEV

    @property
    def maximum_devices(self) -> int:
        """The maximum number of devices the bus will scan for. Valid range is 1 to 255.
        It is an error to have more devices on the bus than this number. Having less is OK.
        """
        return self._maximum_devices

    @maximum_devices.setter
    def maximum_devices(self, count: int) -> None:
        if not isinstance(count, int):
            raise ValueError("Maximum must be an integer value 1 - 255.")
        if count < 1 or count > 0xFF:
            raise ValueError("Maximum must be an integer value 1 - 255.")
        self._maximum_devices = count

    def reset(self, required: bool = False) -> bool:
        """
        Perform a reset and check for presence pulse.

        :param bool required: require presence pulse
        """
        reset = self._ow.reset()
        if required and reset:
            raise OneWireError("No presence pulse found. Check devices and wiring.")
        return not reset

    def readinto(self, buf: WriteableBuffer, *, start: int = 0, end: Optional[int] = None) -> None:
        """
        Read into ``buf`` from the device. The number of bytes read will be the
        length of ``buf``.

        If ``start`` or ``end`` is provided, then the buffer will be sliced
        as if ``buf[start:end]``. This will not cause an allocation like
        ``buf[start:end]`` will so it saves memory.

        :param ~WriteableBuffer buf: Buffer to write into
        :param int start: Index to start writing at
        :param int end: Index to write up to but not include
        """
        if end is None:
            end = len(buf)
        for i in range(start, end):
            buf[i] = self._readbyte()

    def write(self, buf: ReadableBuffer, *, start: int = 0, end: Optional[int] = None) -> None:
        """
        Write the bytes from ``buf`` to the device.

        If ``start`` or ``end`` is provided, then the buffer will be sliced
        as if ``buffer[start:end]``. This will not cause an allocation like
        ``buffer[start:end]`` will so it saves memory.

        :param ReadableBuffer buf: Buffer containing the bytes to write
        :param int start: Index to start writing from
        :param int end: Index to read up to but not include
        """
        if end is None:
            end = len(buf)
        for i in range(start, end):
            self._writebyte(buf[i])

    def scan(self) -> List[OneWireAddress]:
        """Scan for devices on the bus and return a list of addresses."""
        devices = []
        diff = 65
        rom = None
        count = 0
        for _ in range(0xFF):
            rom, diff = self._search_rom(rom, diff)
            if rom:
                count += 1
                if count > self.maximum_devices:
                    raise RuntimeError(f"Maximum device count of {self.maximum_devices} exceeded.")
                devices.append(OneWireAddress(rom))
            if diff == 0:
                break
        return devices

    def _readbyte(self) -> int:
        val = 0
        for i in range(8):
            val |= self._ow.read_bit() << i
        return val

    def _writebyte(self, value: int) -> None:
        for i in range(8):
            bit = (value >> i) & 0x1
            self._ow.write_bit(bit)

    def _search_rom(self, l_rom: Optional[ReadableBuffer], diff: int) -> Tuple[bytearray, int]:
        if not self.reset():
            return None, 0
        self._writebyte(_SEARCH_ROM)
        if not l_rom:
            l_rom = bytearray(8)
        rom = bytearray(8)
        next_diff = 0
        i = 64
        for byte in range(8):
            r_b = 0
            for bit in range(8):
                b = self._readbit()
                if self._readbit():
                    if b:  # there are no devices or there is an error on the bus
                        return None, 0
                elif not b:  # collision, two devices with different bit meaning
                    if diff > i or ((l_rom[byte] & (1 << bit)) and diff != i):
                        b = 1
                        next_diff = i
                self._writebit(b)
                r_b |= b << bit
                i -= 1
            rom[byte] = r_b
        return rom, next_diff

    @staticmethod
    def crc8(data: ReadableBuffer) -> int:
        """
        Perform the 1-Wire CRC check on the provided data.

        :param ReadableBuffer data: 8 byte array representing 64 bit ROM code
        """
        crc = 0

        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x01:
                    crc = (crc >> 1) ^ 0x8C
                else:
                    crc >>= 1
                crc &= 0xFF
        return crc
