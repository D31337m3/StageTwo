# SPDX-FileCopyrightText: 2019 Limor Fried for Adafruit Industries
# SPDX-FileCopyrightText: 2024 Channing Ramos
#
# SPDX-License-Identifier: MIT

"""
`adafruit_button.button`
================================================================================

UI Buttons for displayio


* Author(s): Limor Fried, Channing Ramos

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.roundrect import RoundRect
from micropython import const

from adafruit_button.button_base import ButtonBase, _check_color

try:
    from typing import Optional, Tuple, Union

    from displayio import Group
    from fontio import FontProtocol
except ImportError:
    pass

__version__ = "1.11.4"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_Display_Button.git"


class Button(ButtonBase):
    """Helper class for creating UI buttons for ``displayio``. Provides the following
    buttons:
    RECT: A rectangular button. SHAWDOWRECT adds a drop shadow.
    ROUNDRECT: A rectangular button with rounded corners. SHADOWROUNDRECT adds
    a drop shadow.

    :param int x: The x position of the button.
    :param int y: The y position of the button.
    :param int width: The width of the button in pixels.
    :param int height: The height of the button in pixels.
    :param Optional[str] name: The name of the button.
    :param style: The style of the button. Can be RECT, ROUNDRECT, SHADOWRECT, SHADOWROUNDRECT.
                  Defaults to RECT.
    :param Optional[Union[int, Tuple[int, int, int]]] fill_color: The color to fill the button.
     Accepts an int or a tuple of 3 integers representing RGB values. Defaults to 0xFFFFFF.
    :param Optional[Union[int, Tuple[int, int, int]]] outline_color: The color of the outline of
     the button. Accepts an int or a tuple of 3 integers representing RGB values. Defaults to 0x0.
    :param Optional[str] label: The text that appears inside the button.
    :param Optional[FontProtocol] label_font: The button label font. Defaults to
     ''terminalio.FONT''
    :param Optional[Union[int, Tuple[int, int, int]]] label_color: The color of the button label
     text. Accepts an int or a tuple of 3 integers representing RGB values. Defaults to 0x0.
    :param Optional[Union[int, Tuple[int, int, int]]] selected_fill: The fill color when the
     button is selected. Accepts an int or a tuple of 3 integers representing RGB values.
     Defaults to the inverse of the fill_color.
    :param Optional[Union[int, Tuple[int, int, int]]] selected_outline: The outline color when the
     button is selected. Accepts an int or a tuple of 3 integers representing RGB values.
     Defaults to the inverse of outline_color.
    :param Optional[Union[int, Tuple[int, int, int]]] selected_label: The label color when the
     button is selected. Accepts an int or a tuple of 3 integers representing RGB values.
     Defaults to inverting the label_color.
    :param Optional[int] label_scale: The scale factor used for the label. Defaults to 1.
    """

    def _empty_self_group(self) -> None:
        while len(self) > 0:
            self.pop()

    def _create_body(self) -> None:
        if (self.outline_color is not None) or (self.fill_color is not None):
            if self.style == Button.RECT:
                self.body = Rect(
                    0,
                    0,
                    self.width,
                    self.height,
                    fill=self._fill_color,
                    outline=self._outline_color,
                )
            elif self.style == Button.ROUNDRECT:
                self.body = RoundRect(
                    0,
                    0,
                    self.width,
                    self.height,
                    r=10,
                    fill=self._fill_color,
                    outline=self._outline_color,
                )
            elif self.style == Button.SHADOWRECT:
                self.shadow = Rect(2, 2, self.width - 2, self.height - 2, fill=self.outline_color)
                self.body = Rect(
                    0,
                    0,
                    self.width - 2,
                    self.height - 2,
                    fill=self._fill_color,
                    outline=self._outline_color,
                )
            elif self.style == Button.SHADOWROUNDRECT:
                self.shadow = RoundRect(
                    2,
                    2,
                    self.width - 2,
                    self.height - 2,
                    r=10,
                    fill=self._outline_color,
                )
                self.body = RoundRect(
                    0,
                    0,
                    self.width - 2,
                    self.height - 2,
                    r=10,
                    fill=self._fill_color,
                    outline=self._outline_color,
                )
            if self.shadow:
                self.append(self.shadow)

    RECT = const(0)
    ROUNDRECT = const(1)
    SHADOWRECT = const(2)
    SHADOWROUNDRECT = const(3)

    def __init__(  # noqa: PLR0913 Too many arguments
        self,
        *,
        x: int,
        y: int,
        width: int,
        height: int,
        name: Optional[str] = None,
        style=RECT,
        fill_color: Optional[Union[int, Tuple[int, int, int]]] = 0xFFFFFF,
        outline_color: Optional[Union[int, Tuple[int, int, int]]] = 0x0,
        label: Optional[str] = None,
        label_font: Optional[FontProtocol] = None,
        label_color: Optional[Union[int, Tuple[int, int, int]]] = 0x0,
        selected_fill: Optional[Union[int, Tuple[int, int, int]]] = None,
        selected_outline: Optional[Union[int, Tuple[int, int, int]]] = None,
        selected_label: Optional[Union[int, Tuple[int, int, int]]] = None,
        label_scale: Optional[int] = 1,
    ):
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

        self.body = self.fill = self.shadow = None
        self.style = style

        self._fill_color = _check_color(fill_color)
        self._outline_color = _check_color(outline_color)

        # Selecting inverts the button colors!
        self._selected_fill = _check_color(selected_fill)
        self._selected_outline = _check_color(selected_outline)

        if self.selected_fill is None and fill_color is not None:
            self.selected_fill = (~_check_color(self._fill_color)) & 0xFFFFFF
        if self.selected_outline is None and outline_color is not None:
            self.selected_outline = (~_check_color(self._outline_color)) & 0xFFFFFF

        self._create_body()
        if self.body:
            self.append(self.body)

        self.label = label

    def _subclass_selected_behavior(self, value: bool) -> None:
        if self._selected:
            new_fill = self.selected_fill
            new_out = self.selected_outline
        else:
            new_fill = self._fill_color
            new_out = self._outline_color
        # update all relevant colors!
        if self.body is not None:
            self.body.fill = new_fill
            self.body.outline = new_out

    @property
    def group(self) -> Group:
        """Return self for compatibility with old API."""
        print(
            "Warning: The group property is being deprecated. "
            "User code should be updated to add the Button directly to the "
            "Display or other Groups."
        )
        return self

    @property
    def fill_color(self) -> Optional[int]:
        """The fill color of the button body"""
        return self._fill_color

    @fill_color.setter
    def fill_color(self, new_color: Union[int, Tuple[int, int, int]]) -> None:
        self._fill_color = _check_color(new_color)
        if not self.selected:
            self.body.fill = self._fill_color

    @property
    def outline_color(self) -> Optional[int]:
        """The outline color of the button body"""
        return self._outline_color

    @outline_color.setter
    def outline_color(self, new_color: Union[int, Tuple[int, int, int]]) -> None:
        self._outline_color = _check_color(new_color)
        if not self.selected:
            self.body.outline = self._outline_color

    @property
    def selected_fill(self) -> Optional[int]:
        """The fill color of the button body when selected"""
        return self._selected_fill

    @selected_fill.setter
    def selected_fill(self, new_color: Union[int, Tuple[int, int, int]]) -> None:
        self._selected_fill = _check_color(new_color)
        if self.selected:
            self.body.fill = self._selected_fill

    @property
    def selected_outline(self) -> Optional[int]:
        """The outline color of the button body when selected"""
        return self._selected_outline

    @selected_outline.setter
    def selected_outline(self, new_color: Union[int, Tuple[int, int, int]]) -> None:
        self._selected_outline = _check_color(new_color)
        if self.selected:
            self.body.outline = self._selected_outline

    @property
    def width(self) -> int:
        """The width of the button"""
        return self._width

    @width.setter
    def width(self, new_width: int) -> None:
        self._width = new_width
        self._empty_self_group()
        self._create_body()
        if self.body:
            self.append(self.body)
        self.label = self.label

    @property
    def height(self) -> int:
        """The height of the button"""
        return self._height

    @height.setter
    def height(self, new_height: int) -> None:
        self._height = new_height
        self._empty_self_group()
        self._create_body()
        if self.body:
            self.append(self.body)
        self.label = self.label

    def resize(self, new_width: int, new_height: int) -> None:
        """Resize the button to the new width and height given
        :param int new_width: The desired width in pixels.
        :param int new_height: he desired height in pixels.
        """
        self._width = new_width
        self._height = new_height
        self._empty_self_group()
        self._create_body()
        if self.body:
            self.append(self.body)
        self.label = self.label
