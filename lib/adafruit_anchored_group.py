# SPDX-FileCopyrightText: Copyright (c) 2025 Tim Cocks for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_anchored_group`
================================================================================

A displayio Group that supports placement by anchor_point and anchored_position properties

* Author(s): Tim Cocks

Implementation Notes
--------------------

**Hardware:**

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://circuitpython.org/downloads

"""

# imports
import vectorio
from displayio import Group, TileGrid

__version__ = "1.0.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_Anchored_Group.git"


try:
    from typing import Tuple
except ImportError:
    pass


class AnchoredGroup(Group):
    """
    Displayio Group that supports having its positions set by
    anchor_point and anchored_position properties.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._anchor_point = (0, 0)

        self._anchored_position = (
            0 if "x" not in kwargs else kwargs["x"],
            0 if "y" not in kwargs else kwargs["y"],
        )

    def _measure_group(self, group_to_measure):  # noqa: PLR0912
        min_x = 0
        min_y = 0
        max_x = 0
        max_y = 0

        for i, element in enumerate(group_to_measure):
            if isinstance(element, (TileGrid)):
                if element.x < min_x:
                    min_x = element.x
                if element.y < min_y:
                    min_y = element.y

                _element_max_x = element.x + (element.width * element.tile_width)
                _element_max_y = element.y + (element.height * element.tile_height)
                if _element_max_x > max_x:
                    max_x = _element_max_x
                if _element_max_y > max_y:
                    max_y = _element_max_y
            elif isinstance(element, AnchoredGroup):
                if element.x < min_x:
                    min_x = element.x
                if element.y < min_y:
                    min_y = element.y
                _element_size = element.size
                _element_max_x = element.x + (_element_size[0] * element.scale)
                _element_max_y = element.y + (_element_size[1] * element.scale)
                if _element_max_x > max_x:
                    max_x = _element_max_x
                if _element_max_y > max_y:
                    max_y = _element_max_y
            elif isinstance(element, (vectorio.Rectangle, vectorio.Circle, vectorio.Polygon)):
                raise NotImplemented("Vectorio not supported yet")
            elif isinstance(element, Group):
                _size = self._measure_group(element)

                if element.x < min_x:
                    min_x = _size[0]
                if element.y < min_y:
                    min_y = _size[1]

                _element_max_x = element.x + _size[0]
                _element_max_y = element.y + _size[1]
                if _element_max_x > max_x:
                    max_x = _element_max_x
                if _element_max_y > max_y:
                    max_y = _element_max_y

        return max_x - min_x, max_y - min_y

    @property
    def size(self):
        """
        The width and height of the Group in pixels, readonly.

        :return: tuple (width, height)
        """
        return self._measure_group(self)

    @property
    def width(self):
        """
        The width of the Group in pixels, readonly.

        :return: int width in pixels
        """
        return self.size[0]

    @property
    def height(self):
        """
        The height of the Group in pixels, readonly.

        :return int width in pixels
        """
        return self.size[1]

    @property
    def anchor_point(self):
        """
        The anchor point. tuple containing x and y values ranging
        from 0.0 to 1.0.
        """
        return self._anchor_point

    @anchor_point.setter
    def anchor_point(self, new_anchor_point: Tuple[float, float]) -> None:
        self._anchor_point = new_anchor_point
        # update the anchored_position using setter
        self.anchored_position = self._anchored_position

    @property
    def anchored_position(self) -> Tuple[int, int]:
        """
        Position relative to the anchor_point. Tuple containing x,y
        pixel coordinates.
        """
        return self._anchored_position

    @anchored_position.setter
    def anchored_position(self, new_position: Tuple[int, int]) -> None:
        self._anchored_position = new_position
        _size = self.size

        if (self._anchor_point is not None) and (self._anchored_position is not None):
            # Calculate (x,y) position
            self.x = int(new_position[0] - round(self._anchor_point[0] * _size[0]))

            self.y = int(new_position[1] - round(self._anchor_point[1] * _size[1]))
