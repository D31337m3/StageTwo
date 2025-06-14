#clock / timesoze setup tool, 
# allows user to configure the local timezone and make adjustments to time, 
# also allows option to update time on rtc via ntp 
import board
import time
import os
import digitalio
import displayio
import terminalio
from adafruit_display_text import label

SETTINGS_PATH = "/settings.toml"
TIMEZONES = [
    "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
    "Europe/London", "Europe/Berlin", "Europe/Paris", "Asia/Tokyo", "Asia/Shanghai",
    "Australia/Sydney"
]

import os

def save_settings(SETTINGS_PATH, timezone, dst, hour, minute):
    # Read existing lines if file exists
    lines = []
    keys_found = {"TIMEZONE": False, "DST": False, "MANUAL_HOUR": False, "MANUAL_MINUTE": False}
    if SETTINGS_PATH in os.listdir("/"):
        with open(SETTINGS_PATH, "r") as f:
            for line in f:
                if line.startswith("TIMEZONE"):
                    lines.append(f'TIMEZONE = "{timezone}"\n')
                    keys_found["TIMEZONE"] = True
                elif line.startswith("DST"):
                    lines.append(f'DST = {dst}\n')
                    keys_found["DST"] = True
                elif line.startswith("MANUAL_HOUR"):
                    lines.append(f'MANUAL_HOUR = {hour}\n')
                    keys_found["MANUAL_HOUR"] = True
                elif line.startswith("MANUAL_MINUTE"):
                    lines.append(f'MANUAL_MINUTE = {minute}\n')
                    keys_found["MANUAL_MINUTE"] = True
                else:
                    lines.append(line)
    # If any keys were not found, append them
    if not keys_found["TIMEZONE"]:
        lines.append(f'TIMEZONE = "{timezone}"\n')
    if not keys_found["DST"]:
        lines.append(f'DST = {dst}\n')
    if not keys_found["MANUAL_HOUR"]:
        lines.append(f'MANUAL_HOUR = {hour}\n')
    if not keys_found["MANUAL_MINUTE"]:
        lines.append(f'MANUAL_MINUTE = {minute}\n')

    # Write all lines back to the file
    with open(SETTINGS_PATH, "w") as f:
        for line in lines:
            f.write(line)

def select_from_list(options, prompt="Select:", display=None, button=None):
    idx = 0
    last_button = button.value
    select_label = None
    if display:
        group = displayio.Group()
        display.root_group = group
        select_label = label.Label(terminalio.FONT, text="", color=0x00FFFF, x=10, y=10, scale=2)
        group.append(select_label)
    print(prompt)
    while True:
        if display:
            select_label.text = f"{prompt}\n{options[idx]}"
        else:
            print(f"> {options[idx]}")
        # Button or console
        if button and not button.value and last_button:
            press_time = time.monotonic()
            while not button.value:
                if time.monotonic() - press_time > 1.0:
                    return idx
                time.sleep(0.01)
            idx = (idx + 1) % len(options)
        last_button = button.value
        # Console input
        try:
            import supervisor
            if hasattr(supervisor, "runtime") and supervisor.runtime.serial_bytes_available:
                cmd = input("Enter number or press enter for next: ").strip()
                if cmd.isdigit() and 0 <= int(cmd) < len(options):
                    return int(cmd)
                elif cmd == "":
                    idx = (idx + 1) % len(options)
                elif cmd.lower() in ["s", "select"]:
                    return idx
        except ImportError:
            pass
        time.sleep(0.05)

def toggle_dst(prompt="DST On?", display=None, button=None):
    state = False
    last_button = button.value
    dst_label = None
    if display:
        group = displayio.Group()
        display.root_group = group
        dst_label = label.Label(terminalio.FONT, text="", color=0x00FF00, x=10, y=10, scale=2)
        group.append(dst_label)
    print(prompt)
    while True:
        if display:
            dst_label.text = f"{prompt}\n{'ON' if state else 'OFF'}"
        else:
            print(f"{prompt} {'ON' if state else 'OFF'}")
        if button and not button.value and last_button:
            press_time = time.monotonic()
            while not button.value:
                if time.monotonic() - press_time > 1.0:
                    return state
                time.sleep(0.01)
            state = not state
        last_button = button.value
        # Console input
        try:
            import supervisor
            if hasattr(supervisor, "runtime") and supervisor.runtime.serial_bytes_available:
                cmd = input("Type on/off or enter to toggle: ").strip().lower()
                if cmd in ["on", "1", "yes"]:
                    return True
                elif cmd in ["off", "0", "no"]:
                    return False
                elif cmd == "":
                    state = not state
        except ImportError:
            pass
        time.sleep(0.05)

def ask_ntp_sync(prompt="Sync with NTP?", display=None, button=None):
    state = True
    last_button = button.value
    ntp_label = None
    if display:
        group = displayio.Group()
        display.root_group = group
        ntp_label = label.Label(terminalio.FONT, text="", color=0xFF00FF, x=10, y=10, scale=2)
        group.append(ntp_label)
    print(prompt)
    while True:
        if display:
            ntp_label.text = f"{prompt}\n{'YES' if state else 'NO'}"
        else:
            print(f"{prompt} {'YES' if state else 'NO'}")
        if button and not button.value and last_button:
            press_time = time.monotonic()
            while not button.value:
                if time.monotonic() - press_time > 1.0:
                    return state
                time.sleep(0.01)
            state = not state
        last_button = button.value
        # Console input
        try:
            import supervisor
            if hasattr(supervisor, "runtime") and supervisor.runtime.serial_bytes_available:
                cmd = input("Type yes/no or enter to toggle: ").strip().lower()
                if cmd in ["yes", "y", "1"]:
                    return True
                elif cmd in ["no", "n", "0"]:
                    return False
                elif cmd == "":
                    state = not state
        except ImportError:
            pass
        time.sleep(0.05)

def manual_time_adjust(display=None, button=None):
    hour = 12
    minute = 0
    field = 0  # 0 = hour, 1 = minute
    last_button = button.value
    time_label = None
    if display:
        group = displayio.Group()
        display.root_group = group
        time_label = label.Label(terminalio.FONT, text="", color=0xFFFF00, x=10, y=10, scale=2)
        group.append(time_label)
    print("Manual time adjust")
    while True:
        if display:
            time_label.text = f"Set {'Hour' if field==0 else 'Minute'}:\n{hour:02d}:{minute:02d}\n(Hold to set, short to next)"
        else:
            print(f"Set {'Hour' if field==0 else 'Minute'}: {hour:02d}:{minute:02d}")
        if button and not button.value and last_button:
            press_time = time.monotonic()
            while not button.value:
                if time.monotonic() - press_time > 1.0:
                    if field == 0:
                        field = 1
                    else:
                        return hour, minute
                    break
                time.sleep(0.01)
            else:
                # Short press: increment
                if field == 0:
                    hour = (hour + 1) % 24
                else:
                    minute = (minute + 1) % 60
        last_button = button.value
        # Console input
        try:
            import supervisor
            if hasattr(supervisor, "runtime") and supervisor.runtime.serial_bytes_available:
                cmd = input("Enter hour:minute or enter to increment: ").strip()
                if ":" in cmd:
                    try:
                        h, m = map(int, cmd.split(":"))
                        return h % 24, m % 60
                    except Exception:
                        pass
                elif cmd == "":
                    if field == 0:
                        hour = (hour + 1) % 24
                    else:
                        minute = (minute + 1) % 60
        except ImportError:
            pass
        time.sleep(0.05)

def sync_ntp_and_set_rtc():
    try:
        import rtc
        import socketpool
        import wifi
        import adafruit_ntp
        pool = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool, tz_offset=0)
        now = ntp.datetime
        rtc.RTC().datetime = now
        print("RTC set via NTP:", now)
        return True
    except Exception as e:
        print("NTP sync failed:", e)
        return False

def main():
    display = board.DISPLAY if hasattr(board, "DISPLAY") else None
    button = digitalio.DigitalInOut(board.BUTTON)
    button.switch_to_input(pull=digitalio.Pull.UP)

    # Welcome screen
    if display:
        group = displayio.Group()
        display.root_group = group
        welcome = label.Label(terminalio.FONT, text="Timezone Setup", color=0x00FFFF, x=10, y=10, scale=2)
        group.append(welcome)
        time.sleep(1.5)
        group.pop()

    print("Welcome to Timezone Setup!")

    # 1. Select timezone
    tz_idx = select_from_list(TIMEZONES, prompt="Select Timezone:", display=display, button=button)
    timezone = TIMEZONES[tz_idx]
    print(f"Selected timezone: {timezone}")

    # 2. DST on/off
    dst = toggle_dst(prompt="Daylight Saving Time?", display=display, button=button)
    print(f"DST: {'ON' if dst else 'OFF'}")

    # 3. NTP sync option
    do_ntp = ask_ntp_sync(prompt="Sync with NTP?", display=display, button=button)
    if do_ntp:
        synced = sync_ntp_and_set_rtc()
        if display:
            group = displayio.Group()
            display.root_group = group
            msg = "NTP Sync OK!" if synced else "NTP Sync Failed"
            ntp_label = label.Label(terminalio.FONT, text=msg, color=0x00FF00 if synced else 0xFF0000, x=10, y=10, scale=2)
            group.append(ntp_label)
            time.sleep(1.5)
            group.pop()
    else:
        # 4. Manual time adjust
        hour, minute = manual_time_adjust(display=display, button=button)
        try:
            import rtc
            now = time.localtime()
            rtc.RTC().datetime = (now.tm_year, now.tm_mon, now.tm_mday, now.tm_wday, hour, minute, 0, 0)
            print(f"RTC set manually: {hour:02d}:{minute:02d}")
        except Exception as e:
            print("Manual RTC set failed:", e)
    # Save settings
        save_settings(SETTINGS_PATH, timezone, dst, hour if not do_ntp else 0, minute if not do_ntp else 0)
    if display:
        group = displayio.Group()
        display.root_group = group
        done = label.Label(terminalio.FONT, text="Setup Complete!", color=0x00FF00, x=10, y=10, scale=2)
        group.append(done)
        time.sleep(2)
        display.root_group = None

    print("Timezone setup complete.")

if __name__ == "__main__":
    main()