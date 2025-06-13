import board
import displayio
import terminalio
from adafruit_display_text import label
import digitalio
import supervisor
import time
import microcontroller
import os

SETTINGS_PATH = "/settings.toml"
DEFAULT_BOOT_FILE = "app_loader.py"
DEFAULT_TIMEOUT = 3

# Helper functions for settings.toml
def read_settings():
    settings = {
        "DEFAULT_BOOT_FILE": DEFAULT_BOOT_FILE,
        "BOOT_TIMEOUT": DEFAULT_TIMEOUT,
        "DEVELOPER_MODE": False,
        "FLASH_WRITE": False,
    }
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r") as f:
            for line in f:
                if line.startswith("DEFAULT_BOOT_FILE"):
                    settings["DEFAULT_BOOT_FILE"] = line.split("=")[1].strip().replace('"', "")
                elif line.startswith("BOOT_TIMEOUT"):
                    try:
                        settings["BOOT_TIMEOUT"] = int(line.split("=")[1].strip())
                    except Exception:
                        pass
                elif line.startswith("DEVELOPER_MODE"):
                    settings["DEVELOPER_MODE"] = "True" in line or "1" in line
                elif line.startswith("FLASH_WRITE"):
                    settings["FLASH_WRITE"] = "True" in line or "1" in line
    return settings

def save_settings(settings):
    lines = []
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r") as f:
            for line in f:
                if line.startswith("DEFAULT_BOOT_FILE"):
                    continue
                elif line.startswith("BOOT_TIMEOUT"):
                    continue
                elif line.startswith("DEVELOPER_MODE"):
                    continue
                elif line.startswith("FLASH_WRITE"):
                    continue
                lines.append(line)
    lines.append(f'DEFAULT_BOOT_FILE = "{settings["DEFAULT_BOOT_FILE"]}"\n')
    lines.append(f'BOOT_TIMEOUT = {settings["BOOT_TIMEOUT"]}\n')
    lines.append(f'DEVELOPER_MODE = {int(settings["DEVELOPER_MODE"])}\n')
    lines.append(f'FLASH_WRITE = {int(settings["FLASH_WRITE"])}\n')
    with open(SETTINGS_PATH, "w") as f:
        f.writelines(lines)

settings = read_settings()

MENU_ITEMS = [
    ("Boot Normal", "boot"),
    ("Recovery Mode", "recovery.py"),
    ("Boot Settings", "settings"),
    ("Factory Reset", "factory.py"),
    ("Backup System Files", "backup"),
]

BOOT_FILES = ["app_loader.py", "main.py", "code.py", "user_app.py"]

display = board.DISPLAY
group = displayio.Group()
display.root_group = group

button = digitalio.DigitalInOut(board.BUTTON)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

selected = 0

def draw_menu(selected_index):
    if len(group) > 0:
        group.pop()
    menu_group = displayio.Group()
    title = label.Label(
        terminalio.FONT, text="Boot Menu", color=0x00FFFF, x=10, y=8, scale=2
    )
    menu_group.append(title)
    for i, (item, _) in enumerate(MENU_ITEMS):
        y = 30 + i * 24
        if i == selected_index:
            highlight_bitmap = displayio.Bitmap(120, 20, 1)
            highlight_palette = displayio.Palette(1)
            highlight_palette[0] = 0x003366
            highlight_tile = displayio.TileGrid(
                highlight_bitmap, pixel_shader=highlight_palette, x=6, y=y - 12
            )
            menu_group.append(highlight_tile)
            color = 0xFFFF00
        else:
            color = 0xFFFFFF
        text = label.Label(
            terminalio.FONT, text=item, color=color, x=10, y=y
        )
        menu_group.append(text)
    group.append(menu_group)

def settings_menu():
    idx = 0
    options = [
        f"Boot File: {settings['DEFAULT_BOOT_FILE']}",
        f"Timeout: {settings['BOOT_TIMEOUT']}s",
        f"Developer Mode: {'ON' if settings['DEVELOPER_MODE'] else 'OFF'}",
        f"Flash Write: {'ON' if settings['FLASH_WRITE'] else 'OFF'}",
        "Back"
    ]
    while True:
        if len(group) > 0:
            group.pop()
        menu_group = displayio.Group()
        title = label.Label(
            terminalio.FONT, text="Boot Settings", color=0x00FFFF, x=10, y=8, scale=2
        )
        menu_group.append(title)
        for i, item in enumerate(options):
            y = 30 + i * 24
            if i == idx:
                highlight_bitmap = displayio.Bitmap(120, 20, 1)
                highlight_palette = displayio.Palette(1)
                highlight_palette[0] = 0x003366
                highlight_tile = displayio.TileGrid(
                    highlight_bitmap, pixel_shader=highlight_palette, x=6, y=y - 12
                )
                menu_group.append(highlight_tile)
                color = 0xFFFF00
            else:
                color = 0xFFFFFF
            text = label.Label(
                terminalio.FONT, text=item, color=color, x=10, y=y
            )
            menu_group.append(text)
        group.append(menu_group)

        last_button = button.value
        while True:
            if not button.value and last_button:
                press_time = time.monotonic()
                while not button.value:
                    if time.monotonic() - press_time > 1.0:
                        # Long press: select
                        if idx == 0:
                            # Boot file select
                            bf_idx = BOOT_FILES.index(settings["DEFAULT_BOOT_FILE"]) if settings["DEFAULT_BOOT_FILE"] in BOOT_FILES else 0
                            bf_idx = (bf_idx + 1) % len(BOOT_FILES)
                            settings["DEFAULT_BOOT_FILE"] = BOOT_FILES[bf_idx]
                            options[0] = f"Boot File: {settings['DEFAULT_BOOT_FILE']}"
                        elif idx == 1:
                            # Timeout adjust
                            settings["BOOT_TIMEOUT"] = (settings["BOOT_TIMEOUT"] + 1) % 11 or 1
                            options[1] = f"Timeout: {settings['BOOT_TIMEOUT']}s"
                        elif idx == 2:
                            # Toggle developer mode
                            settings["DEVELOPER_MODE"] = not settings["DEVELOPER_MODE"]
                            options[2] = f"Developer Mode: {'ON' if settings['DEVELOPER_MODE'] else 'OFF'}"
                        elif idx == 3:
                            # Toggle flash write
                            settings["FLASH_WRITE"] = not settings["FLASH_WRITE"]
                            options[3] = f"Flash Write: {'ON' if settings['FLASH_WRITE'] else 'OFF'}"
                        elif idx == 4:
                            save_settings(settings)
                            return
                        save_settings(settings)
                        break
                    time.sleep(0.01)
                else:
                    # Short press: next option
                    idx = (idx + 1) % len(options)
                    break
            last_button = button.value
            time.sleep(0.02)

def run_action(index):
    name, action = MENU_ITEMS[index]
    if action == "boot":
        supervisor.set_next_code_file(settings["DEFAULT_BOOT_FILE"])
        supervisor.reload()
    elif action == "settings":
        settings_menu()
        draw_menu(selected)
    elif action == "factory.py":
        # Set first boot setup flag before rebooting
        FIRST_BOOT_SETUP_FLAG_ADDR = 8
        microcontroller.nvm[FIRST_BOOT_SETUP_FLAG_ADDR] = 1
        supervisor.set_next_code_file(action)
        supervisor.reload()
    elif action == "backup":
        # Import and call backup from recovery.py
        try:
            import recovery
            rec = recovery.RecoverySystem()
            result = rec.backup_system_files()
            msg = "Backup complete!" if result else "Backup failed!"
        except Exception as e:
            msg = f"Backup error: {e}"
        # Show result on display
        if len(group) > 0:
            group.pop()
        msg_group = displayio.Group()
        msg_label = label.Label(terminalio.FONT, text=msg, color=0x00FF00 if "complete" in msg else 0xFF0000, x=10, y=60, scale=2)
        msg_group.append(msg_label)
        group.append(msg_group)
        time.sleep(2)
        draw_menu(selected)
    else:
        supervisor.set_next_code_file(action)
        supervisor.reload()

def menu_loop():
    global selected
    draw_menu(selected)
    last_button = button.value
    start_time = time.monotonic()
    timeout = settings["BOOT_TIMEOUT"]
    button_press_time = None
    prev_selected = selected
    long_press_handled = False

    while True:
        input_received = False
        # Console control
        if supervisor.runtime.serial_bytes_available:
            cmd = input().strip().lower()
            input_received = True
            if cmd in ["up", "u"]:
                selected = (selected - 1) % len(MENU_ITEMS)
            elif cmd in ["down", "d"]:
                selected = (selected + 1) % len(MENU_ITEMS)
            elif cmd in ["select", "s", "enter"]:
                run_action(selected)
            elif cmd.isdigit() and 0 <= int(cmd) < len(MENU_ITEMS):
                selected = int(cmd)
            else:
                print("Commands: up/down/select or 0-3")
        # Button navigation
        if not button.value and last_button:
            button_press_time = time.monotonic()
            long_press_handled = False
        elif not button.value and button_press_time is not None:
            if not long_press_handled and (time.monotonic() - button_press_time > 1.0):
                run_action(selected)
                long_press_handled = True
        elif button.value and not last_button:
            if button_press_time is not None and not long_press_handled:
                selected = (selected + 1) % len(MENU_ITEMS)
                input_received = True
            button_press_time = None
            long_press_handled = False
        last_button = button.value

        if selected != prev_selected:
            draw_menu(selected)
            prev_selected = selected

        if input_received:
            start_time = time.monotonic()
        if time.monotonic() - start_time > timeout:
            print(f"Timeout reached. Booting default: {MENU_ITEMS[selected][0]}")
            run_action(selected)

        time.sleep(0.02)

draw_menu(selected)
print("Boot Menu: Use button or console (up/down/select/0-3)")
menu_loop()