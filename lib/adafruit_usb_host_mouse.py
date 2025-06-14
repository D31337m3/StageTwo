# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_usb_host_mouse`
================================================================================

Helper class that encapsulates the objects needed for user code to interact with
a USB mouse, draw a visible cursor, and determine when buttons are pressed.


* Author(s): Tim Cocks

Implementation Notes
--------------------

**Hardware:**

* `USB Wired Mouse - Two Buttons plus Wheel <https://www.adafruit.com/product/2025>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads


# * Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice
# * Adafruit's Register library: https://github.com/adafruit/Adafruit_CircuitPython_Register
"""

import array

import adafruit_usb_host_descriptors
import supervisor
import usb
from displayio import OnDiskBitmap, TileGrid

__version__ = "1.2.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_USB_Host_Mouse.git"

BUTTONS = ["left", "right", "middle"]


def find_and_init_boot_mouse(cursor_image="/launcher_assets/mouse_cursor.bmp"):
    """
    Scan for an attached boot mouse connected via USB host.
    If one is found initialize an instance of BootMouse class
    and return it.
    :return: The BootMouse instance or None if no mouse was found.
    """
    mouse_interface_index, mouse_endpoint_address = None, None
    mouse_device = None

    # scan for connected USB device and loop over any found
    print("scanning usb")
    for device in usb.core.find(find_all=True):
        # print device info
        print(f"{device.idVendor:04x}:{device.idProduct:04x}")
        print(device.manufacturer, device.product)
        print()
        config_descriptor = adafruit_usb_host_descriptors.get_configuration_descriptor(device, 0)
        print(config_descriptor)

        _possible_interface_index, _possible_endpoint_address = (
            adafruit_usb_host_descriptors.find_boot_mouse_endpoint(device)
        )
        if _possible_interface_index is not None and _possible_endpoint_address is not None:
            mouse_device = device
            mouse_interface_index = _possible_interface_index
            mouse_endpoint_address = _possible_endpoint_address
            print(
                f"mouse interface: {mouse_interface_index} "
                + f"endpoint_address: {hex(mouse_endpoint_address)}"
            )

    mouse_was_attached = None
    if mouse_device is not None:
        # detach the kernel driver if needed
        if mouse_device.is_kernel_driver_active(0):
            mouse_was_attached = True
            mouse_device.detach_kernel_driver(0)
        else:
            mouse_was_attached = False

        # set configuration on the mouse so we can use it
        mouse_device.set_configuration()

        # load the mouse cursor bitmap
        if not isinstance(cursor_image, str):
            raise TypeError("cursor_image must be a string")
        mouse_bmp = OnDiskBitmap(cursor_image)

        # make the background pink pixels transparent
        mouse_bmp.pixel_shader.make_transparent(0)

        # create a TileGrid for the mouse, using its bitmap and pixel_shader
        mouse_tg = TileGrid(mouse_bmp, pixel_shader=mouse_bmp.pixel_shader)

        return BootMouse(mouse_device, mouse_endpoint_address, mouse_tg, mouse_was_attached)

    # if no mouse found
    return None


class BootMouse:
    """
    Helpler class that encapsulates the objects needed to interact with a boot
    mouse, show a visible cursor on the display, and determine when buttons
    were pressed.

    :param device: The usb device instance for the mouse
    :param endpoint_address: The address of the mouse endpoint
    :param tilegrid: The TileGrid that holds the visible mouse cursor
    :param was_attached: Whether the usb device was attached to the kernel
    """

    def __init__(self, device, endpoint_address, tilegrid, was_attached, scale=1):  # noqa: PLR0913, too many args
        self.device = device
        self.tilegrid = tilegrid
        self.endpoint = endpoint_address
        self.buffer = array.array("b", [0] * 4)
        self.was_attached = was_attached
        self.scale = scale

        self.display_size = (supervisor.runtime.display.width, supervisor.runtime.display.height)

    @property
    def x(self):
        """
        The x coordinate of the mouse cursor
        """
        return self.tilegrid.x

    @x.setter
    def x(self, new_x):
        self.tilegrid.x = new_x

    @property
    def y(self):
        """
        The y coordinate of the mouse cursor
        """
        return self.tilegrid.y

    @y.setter
    def y(self, new_y):
        self.tilegrid.y = new_y

    def release(self):
        """
        Release the mouse cursor and re-attach it to the kernel
        if it was attached previously.
        """
        if self.was_attached and not self.device.is_kernel_driver_active(0):
            self.device.attach_kernel_driver(0)

    def update(self):
        """
        Read data from the USB mouse and update the location of the visible cursor
        and check if any buttons are pressed.

        :return: a List containing one or more of the strings "left", "right", "middle"
          indicating which buttons are pressed.
        """
        try:
            # attempt to read data from the mouse
            # 20ms timeout, so we don't block long if there
            # is no data
            count = self.device.read(self.endpoint, self.buffer, timeout=20)  # noqa: F841, var assigned but not used
        except usb.core.USBTimeoutError:
            # skip the rest if there is no data
            return None
        except usb.core.USBError:
            return None

        # update the mouse tilegrid x and y coordinates
        # based on the delta values read from the mouse
        self.tilegrid.x = max(
            0, min((self.display_size[0] // self.scale) - 1, self.tilegrid.x + self.buffer[1])
        )
        self.tilegrid.y = max(
            0, min((self.display_size[1] // self.scale) - 1, self.tilegrid.y + self.buffer[2])
        )

        pressed_btns = []
        for i, button in enumerate(BUTTONS):
            # check if each button is pressed using bitwise AND shifted
            # to the appropriate index for this button
            if self.buffer[0] & (1 << i) != 0:
                # append the button name to the string to show if
                # it is being clicked.
                pressed_btns.append(button)

        if len(pressed_btns) > 0:
            return pressed_btns
