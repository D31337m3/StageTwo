# SPDX-FileCopyrightText: 2022 Tim Cocks for Adafruit Industries
# SPDX-FileCopyrightText: 2024 Channing Ramos
#
# SPDX-License-Identifier: MIT

"""
`adafruit_button.button`
================================================================================

Bitmap 3x3 Spritesheet based UI Button for displayio


* Author(s): Tim Cocks, Channing Ramos

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

from adafruit_imageload import load
from adafruit_imageload.tilegrid_inflator import inflate_tilegrid

from adafruit_button.button_base import ButtonBase

try:
    from typing import Optional, Tuple, Union

    from fontio import FontProtocol
except ImportError:
    pass


class SpriteButton(ButtonBase):
    """Helper class for creating 3x3 Bitmap Spritesheet UI buttons for ``displayio``.
    Compatible with any format supported by ''adafruit_imageload''.

    :param int x: The x position of the button.
    :param int y: The y position of the button.
    :param int width: The width of the button in tiles.
    :param int height: The height of the button in tiles.
    :param Optional[str] name: A name, or miscellaneous string that is stored on the button.
    :param Optional[str] label: The text that appears inside the button.
    :param Optional[FontProtocol] label_font: The button label font.
    :param Optional[Union[int, Tuple[int, int, int]]] label_color: The color of the label text.
     Accepts either an integer or a tuple of 3 integers representing RGB values. Defaults to 0x0.
    :param Optional[Union[int, Tuple[int, int, int]]] selected_label: The color of the button label
     text when the button is selected. Accepts either an integer or a tuple of 3 integers
     representing RGB values. Defaults to the inverse of label_color.
    :param str bmp_path: The path of the 3x3 spritesheet mage file
    :param Optional[str] selected_bmp_path: The path of the 3x3 spritesheet image file to use when
     pressed
    :param Optional[Union[int, Tuple]] transparent_index: Palette index(s) that will be set to
     transparent. PNG files have these index(s) set automatically. Not compatible with JPG files.
    :param Optional[int] label_scale: The scale multiplier of the button label. Defaults to 1.
    """

    def __init__(  # noqa: PLR0913 Too many arguments
        self,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        name: Optional[str] = None,
        label: Optional[str] = None,
        label_font: Optional[FontProtocol] = None,
        label_color: Optional[Union[int, Tuple[int, int, int]]] = 0x0,
        selected_label: Optional[Union[int, Tuple[int, int, int]]] = None,
        bmp_path: str = None,
        selected_bmp_path: Optional[str] = None,
        transparent_index: Optional[Union[int, Tuple]] = None,
        label_scale: Optional[int] = 1,
    ):
        if bmp_path is None:
            raise ValueError("Please supply bmp_path. It cannot be None.")

        super().__init__(
            x=x,
            y=y,
            width=width,
            height=height,
            name=name,
            label=label,
            label_font=label_font,
            label_color=label_color,
            selected_label=selected_label,
            label_scale=label_scale,
        )

        self._bmp, self._bmp_palette = load(bmp_path)

        self._selected_bmp = None
        self._selected_bmp_palette = None
        self._selected = False

        if selected_bmp_path is not None:
            self._selected_bmp, self._selected_bmp_palette = load(selected_bmp_path)
            if transparent_index is not None:
                if isinstance(transparent_index, tuple):
                    for _index in transparent_index:
                        self._selected_bmp_palette.make_transparent(_index)
                elif isinstance(transparent_index, int):
                    self._selected_bmp_palette.make_transparent(transparent_index)

        self._btn_tilegrid = inflate_tilegrid(
            bmp_obj=self._bmp,
            bmp_palette=self._bmp_palette,
            target_size=(
                width // (self._bmp.width // 3),
                height // (self._bmp.height // 3),
            ),
            transparent_index=transparent_index,
        )
        self.append(self._btn_tilegrid)

        self.label = label

    @property
    def width(self) -> int:
        """The width of the button. Read-Only"""
        return self._width

    @property
    def height(self) -> int:
        """The height of the button. Read-Only"""
        return self._height

    def _subclass_selected_behavior(self, value: bool) -> None:
        if self._selected:
            if self._selected_bmp is not None:
                self._btn_tilegrid.bitmap = self._selected_bmp
                self._btn_tilegrid.pixel_shader = self._selected_bmp_palette
        else:
            self._btn_tilegrid.bitmap = self._bmp
            self._btn_tilegrid.pixel_shader = self._bmp_palette
