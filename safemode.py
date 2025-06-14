import board
import displayio
import terminalio
from adafruit_display_text import label, wrap_text_to_lines
import digitalio
import microcontroller
import supervisor
import time

# --- CONFIGURABLES ---
BUTTON_PIN = board.BUTTON
DISPLAY_WIDTH = board.DISPLAY.width
DISPLAY_HEIGHT = board.DISPLAY.height
TEXTBOX_WIDTH = DISPLAY_WIDTH - 20
TEXTBOX_HEIGHT = DISPLAY_HEIGHT - 50
FONT = terminalio.FONT
LINE_SPACING = 1.2

# --- SETUP DISPLAY ---
display = board.DISPLAY  # Use built-in display

# --- SETUP BUTTON ---
button = digitalio.DigitalInOut(BUTTON_PIN)
button.switch_to_input(pull=digitalio.Pull.UP)

def wait_for_button_press():
    while button.value:
        time.sleep(0.01)
    while not button.value:
        time.sleep(0.01)

def get_exception_text():
    try:
        tb = supervisor.get_previous_traceback()
        if tb:
            return tb
    except AttributeError:
        pass
    return "Unknown exception. No traceback available."

def make_textbox(text, width, height):
    lines = wrap_text_to_lines(text, width)
    line_height = 12  # Fixed for terminalio.FONT
    max_lines = int(height // (line_height * LINE_SPACING))
    def render(offset):
        group = displayio.Group()
        for i in range(max_lines):
            if i + offset >= len(lines):
                break
            lbl = label.Label(
                terminalio.FONT,
                text=lines[i + offset],
                color=0xFFFFFF,
                x=10,
                y=10 + i * int(line_height * LINE_SPACING)
            )
            group.append(lbl)
        return group
    return lines, max_lines, render

def main():
    exception_text = get_exception_text()
    splash = displayio.Group()

    # Title
    title = label.Label(
        FONT, text="Safe Mode Exception", color=0xFF0000, x=10, y=10
    )
    splash.append(title)

    # Textbox
    lines, max_lines, render = make_textbox(
    exception_text, TEXTBOX_WIDTH, TEXTBOX_HEIGHT
)
    scroll_offset = 0
    textbox_group = render(scroll_offset)
    textbox_group.y = 30
    splash.append(textbox_group)

    # OK Button
    ok_label = label.Label(
        FONT, text="[OK]", color=0x00FF00, x=DISPLAY_WIDTH // 2 - 15, y=DISPLAY_HEIGHT - 20
    )
    splash.append(ok_label)

    display.root_group = splash

    cleared = False
    while True:
        if not button.value:
            press_time = time.monotonic()
            while not button.value:
                time.sleep(0.01)
            duration = time.monotonic() - press_time

            if not cleared:
                # Scroll or clear
                if scroll_offset + max_lines < len(lines):
                    scroll_offset += max_lines
                    splash.pop(-2)  # Remove old textbox
                    textbox_group = render(scroll_offset)
                    textbox_group.y = 30
                    splash.insert(-1, textbox_group)
                    display.root_group = splash
                else:
                    # Clear dialog
                    ok_label.text = "[Press to Reset]"
                    cleared = True
                    display.root_group = splash
            else:
                # Reset on next press
                microcontroller.reset()
        time.sleep(0.01)

main()