# SPDX-FileCopyrightText: 2019 Dave Astels for Adafruit Industries
# SPDX-FileCopyrightText: 2022 Matt Land
#
# SPDX-License-Identifier: MIT

"""
`adafruit_bitmapsaver`
================================================================================

Save a displayio.Bitmap (and associated displayio.Palette) in a BMP file.
Make a screenshot (the contents of a busdisplay.BusDisplay) and save in a BMP file.


* Author(s): Dave Astels, Matt Land

Implementation Notes
--------------------

**Hardware:**


**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

# imports

import gc
import struct

import board
from displayio import Bitmap, ColorConverter, Palette

try:
    from io import BufferedWriter
    from typing import Optional, Tuple, Union

    from busdisplay import BusDisplay
    from framebufferio import FramebufferDisplay
except ImportError:
    pass

__version__ = "1.3.6"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_BitmapSaver.git"


def _write_bmp_header(output_file: BufferedWriter, filesize: int) -> None:
    output_file.write(bytes("BM", "ascii"))
    output_file.write(struct.pack("<I", filesize))
    output_file.write(b"\00\x00")
    output_file.write(b"\00\x00")
    output_file.write(struct.pack("<I", 54))


def _write_dib_header(output_file: BufferedWriter, width: int, height: int) -> None:
    output_file.write(struct.pack("<I", 40))
    output_file.write(struct.pack("<I", width))
    output_file.write(struct.pack("<I", height))
    output_file.write(struct.pack("<H", 1))
    output_file.write(struct.pack("<H", 24))
    for _ in range(24):
        output_file.write(b"\x00")


def _bytes_per_row(source_width: int) -> int:
    pixel_bytes = 3 * source_width
    padding_bytes = (4 - (pixel_bytes % 4)) % 4
    return pixel_bytes + padding_bytes


def _rotated_height_and_width(
    pixel_source: Union[Bitmap, BusDisplay, FramebufferDisplay],
) -> Tuple[int, int]:
    # flip axis if the display is rotated
    if hasattr(pixel_source, "rotation") and (pixel_source.rotation % 180 != 0):
        return pixel_source.height, pixel_source.width
    return pixel_source.width, pixel_source.height


def _rgb565_to_bgr_tuple(color: int) -> Tuple[int, int, int]:
    blue = (color << 3) & 0x00F8  # extract each of the RGB triple into it's own byte
    green = (color >> 3) & 0x00FC
    red = (color >> 8) & 0x00F8
    return blue, green, red


def rgb565_to_rgb888(rgb565):
    """
    Convert from an integer representing rgb565 color into an integer
    representing rgb888 color.
    :param rgb565: Color to convert
    :return int: rgb888 color value
    """
    # Shift the red value to the right by 11 bits.
    red5 = rgb565 >> 11
    # Shift the green value to the right by 5 bits and extract the lower 6 bits.
    green6 = (rgb565 >> 5) & 0b111111
    # Extract the lower 5 bits for blue.
    blue5 = rgb565 & 0b11111

    # Convert 5-bit red to 8-bit red.
    red8 = round(red5 / 31 * 255)
    # Convert 6-bit green to 8-bit green.
    green8 = round(green6 / 63 * 255)
    # Convert 5-bit blue to 8-bit blue.
    blue8 = round(blue5 / 31 * 255)

    # Combine the RGB888 values into a single integer
    rgb888_value = (red8 << 16) | (green8 << 8) | blue8

    return rgb888_value


def _write_pixels(
    output_file: BufferedWriter,
    pixel_source: Union[Bitmap, BusDisplay, FramebufferDisplay],
    palette: Optional[Union[Palette, ColorConverter]],
) -> None:
    saving_bitmap = isinstance(pixel_source, Bitmap)
    width, height = _rotated_height_and_width(pixel_source)
    row_buffer = bytearray(_bytes_per_row(width))
    result_buffer = False
    for y in range(height, 0, -1):
        buffer_index = 0
        if saving_bitmap:
            # pixel_source: Bitmap
            for x in range(width):
                pixel = pixel_source[x, y - 1]
                if isinstance(palette, Palette):
                    color = palette[pixel]  # handled by save_pixel's guardians
                elif isinstance(palette, ColorConverter):
                    converted = palette.convert(pixel)
                    converted_888 = rgb565_to_rgb888(converted)
                    color = converted_888

                for _ in range(3):
                    row_buffer[buffer_index] = color & 0xFF
                    color >>= 8
                    buffer_index += 1
        else:
            # pixel_source: display
            result_buffer = bytearray(2048)
            data = pixel_source.fill_row(y - 1, result_buffer)
            for i in range(width):
                pixel565 = (data[i * 2] << 8) + data[i * 2 + 1]
                for b in _rgb565_to_bgr_tuple(pixel565):
                    row_buffer[buffer_index] = b & 0xFF
                    buffer_index += 1
        output_file.write(row_buffer)
        if result_buffer:
            for i in range(width * 2):
                result_buffer[i] = 0
        gc.collect()


def save_pixels(
    file_or_filename: Union[str, BufferedWriter],
    pixel_source: Union[BusDisplay, FramebufferDisplay, Bitmap] = None,
    palette: Optional[Union[Palette, ColorConverter]] = None,
) -> None:
    """Save pixels to a 24 bit per pixel BMP file.
    If pixel_source if a displayio.Bitmap, save it's pixels through palette.
    If it's a displayio display, a palette isn't required. To be supported,
    a display must implement `busdisplay.BusDisplay.fill_row`. Known supported
    display types are `busdisplay.BusDisplay` and `framebufferio.FramebufferDisplay`.

    :param file_or_filename: either the file to save to, or it's absolute name
    :param pixel_source: the Bitmap or display to save
    :param palette: the Palette to use for looking up colors in the bitmap
    """
    if not pixel_source:
        if not getattr(board, "DISPLAY", None):
            raise ValueError("Second argument must be a Bitmap or Display")
        pixel_source = board.DISPLAY

    if isinstance(pixel_source, Bitmap):
        if not isinstance(palette, Palette) and not isinstance(palette, ColorConverter):
            raise ValueError("Third argument must be a Palette or ColorConverter for a Bitmap save")
    elif not hasattr(pixel_source, "fill_row"):
        raise ValueError("Second argument must be a Bitmap or supported display type")
    try:
        if isinstance(file_or_filename, str):
            output_file = open(file_or_filename, "wb")
        else:
            output_file = file_or_filename

        width, height = _rotated_height_and_width(pixel_source)
        filesize = 54 + height * _bytes_per_row(width)
        _write_bmp_header(output_file, filesize)
        _write_dib_header(output_file, width, height)
        _write_pixels(output_file, pixel_source, palette)
    except Exception as ex:
        raise ex
    output_file.close()
