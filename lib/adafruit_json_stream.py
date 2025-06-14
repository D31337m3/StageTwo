# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2023 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_json_stream`
================================================================================
Minimal version of `json_stream <https://github.com/daggaz/json-stream>`_ for
CircuitPython use.

* Author(s): Scott Shawcroft

"""

import array
import json

__version__ = "0.9.1"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_JSON_Stream.git"


class _IterToStream:
    """Converts an iterator to a JSON data stream."""

    def __init__(self, data_iter):
        self.data_iter = data_iter
        self.i = 0
        self.chunk = b""
        self.last_char = None

    def read(self):
        """Read the next character from the stream."""
        if self.i >= len(self.chunk):
            try:
                self.chunk = next(self.data_iter)
            except StopIteration as exc:
                raise EOFError from exc
            self.i = 0
        char = self.chunk[self.i]
        self.i += 1
        return char

    def fast_forward(self, closer, *, return_object=False):
        """
        Read through the stream until the character is ``closer``, ``]``
        (ending a list) or ``}`` (ending an object.) Intermediate lists and
        objects are skipped.

        :param str closer: the character to read until
        :param bool return_object: read until the closer,
          and then parse the data and return as an object
        """

        closer = ord(closer)
        close_stack = [closer]
        count = 0

        buffer = None
        if return_object:
            buffer = bytearray(32)
            # ] = 93, [ = 91
            # } = 125, { = 123
            buffer[0] = closer - 2

        ignore_next = False
        while close_stack:
            char = self.read()
            count += 1
            if buffer:
                if count == len(buffer):
                    new_buffer = bytearray(len(buffer) + 32)
                    new_buffer[: len(buffer)] = buffer
                    buffer = new_buffer
                buffer[count] = char
            if ignore_next:
                # that character was escaped, skip it
                ignore_next = False
            elif char == close_stack[-1]:
                close_stack.pop()
            elif char == ord("\\") and close_stack[-1] == ord('"'):
                # if backslash, ignore the next character
                ignore_next = True
            elif char == ord('"'):
                close_stack.append(ord('"'))
            elif close_stack[-1] == ord('"'):
                # in a string so ignore [] and {}
                pass
            elif char in {ord("}"), ord("]")}:
                # Mismatched list or object means we're done and already past the last comma.
                return True
            elif char == ord("{"):
                close_stack.append(ord("}"))
            elif char == ord("["):
                close_stack.append(ord("]"))
        if buffer:
            value_string = bytes(memoryview(buffer)[: count + 1]).decode("utf-8")
            return json.loads(value_string)
        return False

    def next_value(self, endswith=None):
        """Read and parse the next JSON data."""
        buf = array.array("B")
        if isinstance(endswith, str):
            endswith = ord(endswith)
        in_string = False
        ignore_next = False
        while True:
            try:
                char = self.read()
            except EOFError:
                char = endswith
                in_string = False
                ignore_next = False

            if not in_string:
                # end character or object/list end
                if char == endswith or char in {ord("]"), ord("}")}:
                    self.last_char = char
                    if len(buf) == 0:
                        return None
                    value_string = bytes(buf).decode("utf-8")
                    return json.loads(value_string)
                # string or sub object
                if char == ord("{"):
                    return TransientObject(self)
                if char == ord("["):
                    return TransientList(self)
                # start a string
                if char == ord('"'):
                    in_string = True

            # skipping any closing or opening character if in a string
            # also skipping escaped characters (like quotes in string)
            elif ignore_next:
                ignore_next = False
            elif char == ord("\\"):
                ignore_next = True
            elif char == ord('"'):
                in_string = False

            buf.append(char)


class Transient:
    """Transient object representing a JSON object."""

    def __init__(self, stream):
        self.active_child = None
        self.data = stream
        self.done = False
        self.has_read = False
        self.finish_char = ""

    def finish(self):
        """Consume all of the characters for this container from the stream."""
        if not self.done:
            if self.active_child:
                self.active_child.finish()
                self.active_child = None
            self.data.fast_forward(self.finish_char)
        self.done = True

    def as_object(self):
        """Consume all of the characters for this container from the stream
        and return as an object."""
        if self.has_read:
            raise BufferError("Object has already been partly read.")

        self.done = True
        return self.data.fast_forward(self.finish_char, return_object=True)


class TransientList(Transient):
    """Transient object that acts like a list through the stream."""

    def __init__(self, stream):
        super().__init__(stream)
        self.finish_char = "]"

    def __iter__(self):
        return self

    def __next__(self):
        self.has_read = True

        if self.active_child:
            self.active_child.finish()
            self.done = self.data.fast_forward(",")
            self.active_child = None
        if self.done:
            raise StopIteration()
        next_value = self.data.next_value(",")
        if self.data.last_char == ord("]"):
            self.done = True
        if next_value is None:
            self.done = True
            raise StopIteration()
        if isinstance(next_value, Transient):
            self.active_child = next_value
        return next_value


class TransientObject(Transient):
    """Transient object that acts like a dictionary through the stream."""

    def __init__(self, stream):
        super().__init__(stream)
        self.finish_char = "}"
        self.active_key = None

    def finish(self):
        """Consume all of the characters for this container from the stream."""
        if self.active_key and not self.active_child:
            self.done = self.data.fast_forward(",")
            self.active_key = None
        super().finish()

    def __getitem__(self, key):
        if self.active_child and self.active_key == key:
            return self.active_child

        self.has_read = True

        if self.active_child:
            self.active_child.finish()
            self.done = self.data.fast_forward(",")
            self.active_child = None
            self.active_key = None
        if self.done:
            raise KeyError(key)

        while not self.done:
            if self.active_key:
                current_key = self.active_key
                self.active_key = None
            else:
                current_key = self.data.next_value(":")
            if current_key is None:
                self.done = True
                break
            if current_key == key:
                next_value = self.data.next_value(",")
                if self.data.last_char == ord("}"):
                    self.done = True
                if isinstance(next_value, Transient):
                    self.active_child = next_value
                    self.active_key = key
                return next_value
            self.done = self.data.fast_forward(",")
        raise KeyError(key)

    def __iter__(self):
        return self

    def _next_key(self):
        """Return the next item's key, without consuming the value."""
        if self.active_key:
            if self.active_child:
                self.active_child.finish()
                self.active_child = None
            self.done = self.data.fast_forward(",")
            self.active_key = None
        if self.done:
            raise StopIteration()

        self.has_read = True

        current_key = self.data.next_value(":")
        if current_key is None:
            self.done = True
            raise StopIteration()

        self.active_key = current_key
        return current_key

    def __next__(self):
        return self._next_key()

    def items(self):
        """Return iterator in the dictionary’s items ((key, value) pairs)."""
        try:
            while not self.done:
                key = self._next_key()
                yield (key, self[key])
        except StopIteration:
            return


def load(data_iter):
    """Returns an object to represent the top level of the given JSON stream."""
    stream = _IterToStream(data_iter)
    return stream.next_value(None)
