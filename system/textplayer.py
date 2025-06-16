'''
TextPlayer   - Text animation library created for compatability with CircuitPython and StageTwo

Version 1.0   - By D. Ranger AKA D31337m3
   * Loads text from a script file containing text and embeded commands to control parsing of text. 
   * uses displayio to handle custom font loading and board.DISPLAY to print text to boards with built in displays.
   * currently supports CircuitPython 9.x.x and StageTwo 1.0.0 (fork of CircuitPython)
   NOTES: with more planned for future releases, this program currently produces the following animation styles
    * 80sDOS  - A retro 1980 DOS terminal simulation , created to make nostalgic animation of typed text on old dos machines with crts
                using a font of the era but that of a cold cathode display / neon display used on calculators from 80s
Example usage:
   *config*
         my_font = adafruit_bitmap_font.bitmap_font.load_font("/fonts/MyFont.bdf")
         playtext = ScriptDisplayer(button_pin=board.BUTTON, font=my_font)
    *playback*
         playtext.run_script("/myscript.txt")
'''

import board
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_bitmap_font.bitmap_font
import adafruit_bitmap_font 
import time
import digitalio

class TxtPlayer:
    def __init__(self, display=None, button_pin=None, font=None, typing_speed=0.04, cursor_blink_speed=0.5):
        self.display = display or board.DISPLAY
        self.button = None
        if button_pin is not None:
            self.button = digitalio.DigitalInOut(button_pin)
            self.button.switch_to_input(pull=digitalio.Pull.UP)
        self.font = font or terminalio.FONT
        self.typing_speed = typing_speed
        self.cursor_blink_speed = cursor_blink_speed
        self.line_spacing = 18
        self.margin = 10
        try:
            font_height = self.font.get_bounding_box()[1]
            self.line_spacing = int(font_height * 1.2)
        except Exception:
            pass
        self.max_lines = (self.display.height - self.margin) // self.line_spacing

        # For typewriter effect
        self.text_label = label.Label(self.font, text="", color=0x00FF00, x=self.margin, y=self.margin)
        self.cursor_label = label.Label(self.font, text="_", color=0x000000, x=self.margin, y=self.margin)
        self.cursor_label.hidden = True

    def wait_for_button(self):
        if not self.button:
            time.sleep(1)
            return
        while self.button.value:
            time.sleep(0.01)
        while not self.button.value:
            time.sleep(0.01)

    def update_cursor_position(self, line_idx, text):
        self.cursor_label.x = self.margin + self.font.get_bounding_box()[0] * len(text)
        self.cursor_label.y = self.margin + line_idx * self.line_spacing

    def blink_cursor(self, blink):
        self.cursor_label.hidden = not blink

    def typewriter_effect(self, text, line_idx, color=0xFFFF00):
        group = displayio.Group()
        # Add previous lines if any
        for i, prev in enumerate(self.prev_lines):
            group.append(label.Label(self.font, text=prev, color=color, x=self.margin, y=self.margin + i*self.line_spacing))
        # Add the label for the current line
        self.text_label = label.Label(self.font, text="", color=color, x=self.margin, y=self.margin + line_idx*self.line_spacing)
        group.append(self.text_label)
        # Add the cursor label
        self.cursor_label = label.Label(self.font, text="_", color=0xFFFFFF, x=self.margin, y=self.margin + line_idx*self.line_spacing)
        group.append(self.cursor_label)
        self.display.root_group = group

        typed = ""
        last_blink = time.monotonic()
        cursor_visible = True
        for char in text:
            typed += char
            self.text_label.text = typed
            self.update_cursor_position(line_idx, typed)
            self.blink_cursor(True)
            time.sleep(self.typing_speed)
        # After typing, blink cursor for a moment
        blink_time = time.monotonic()
        while time.monotonic() - blink_time < 2:
            now = time.monotonic()
            if now - last_blink > self.cursor_blink_speed:
                cursor_visible = not cursor_visible
                self.blink_cursor(cursor_visible)
                last_blink = now
            time.sleep(0.05)
        self.blink_cursor(False)

    def clear(self):
        self.display.root_group = displayio.Group()
        self.prev_lines = []

    def disp_ext_output(self, text, color=0xFFFFFF):
        """Display a string (possibly multiline) with typewriter effect."""
        self.clear()
        lines = text.split("\n")
        self.prev_lines = []
        for line in lines:
            if len(self.prev_lines) >= self.max_lines:
                self.prev_lines.pop(0)
            self.typewriter_effect(line, len(self.prev_lines), color=color)
            self.prev_lines.append(line)
        # After displaying, blink cursor at end
        if self.prev_lines:
            self.typewriter_effect("", len(self.prev_lines))


    def run_script(self, filename):
        with open(filename, "r") as f:
            lines = [line.rstrip("\r\n") for line in f]
        self.prev_lines = []
        for line in lines:
            if line.startswith("*") and line.endswith("*"):
                cmd = line.strip("*").upper()
                if cmd == "PAUSE":
                    self.wait_for_button()
                elif cmd == "CLEAR":
                    self.clear()
                elif cmd.startswith("WAIT:"):
                    try:
                        seconds = float(cmd.split(":", 1)[1])
                        time.sleep(seconds)
                    except Exception:
                        pass
                # Add more commands here as needed
            else:
                if len(self.prev_lines) >= self.max_lines:
                    self.prev_lines.pop(0)
                self.typewriter_effect(line, len(self.prev_lines))
                self.prev_lines.append(line)
        # After script, blink cursor at end
        if self.prev_lines:
            self.typewriter_effect("", len(self.prev_lines))
def main():
    display = board.DISPLAY
    button_pin = board.BUTTON
    custombdfont = adafruit_bitmap_font.bitmap_font.load_font("./fonts/digitron.bdf")
    typing_speed = 0.04
    cursor_blink_speed = 0.5
    script_displayer = TxtPlayer(
        display=display,
        button_pin=button_pin,
        font=custombdfont,
        typing_speed=typing_speed,
        cursor_blink_speed=cursor_blink_speed
    )
    script_displayer.run_script("./script.txt")


if "__main__":
    pass

    