import board
import displayio
import terminalio
from adafruit_display_text import label
import digitalio
import supervisor
import time
import os

STATUS_BAR_HEIGHT = 15
SCREEN_WIDTH = board.DISPLAY.width
SCREEN_HEIGHT = board.DISPLAY.height
MENU_START_Y = STATUS_BAR_HEIGHT + 10

class StatusBar:
    def __init__(self, display_group):
        self.group = displayio.Group()
        self.display_group = display_group
        self.bg_bitmap = displayio.Bitmap(SCREEN_WIDTH, STATUS_BAR_HEIGHT, 1)
        self.bg_palette = displayio.Palette(1)
        self.bg_palette[0] = 0x001122
        self.bg_sprite = displayio.TileGrid(self.bg_bitmap, pixel_shader=self.bg_palette, x=0, y=0)
        self.group.append(self.bg_sprite)
        self.status_label = label.Label(
            terminalio.FONT, text="Ready", color=0xFFFFFF, x=10, y=6
        )
        self.group.append(self.status_label)
        self.display_group.append(self.group)
    def set_status(self, status_text, color=0xFFFFFF):
        self.status_label.text = status_text[:30]
        self.status_label.color = color

class FileManager:
    def __init__(self):
        self.display = board.DISPLAY
        self.main_group = displayio.Group()
        self.display.root_group = self.main_group
        self.status_bar = StatusBar(self.main_group)
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except:
            self.has_button = False
        self.menu_group = displayio.Group()
        self.main_group.append(self.menu_group)
        self.cwd = "/"
        self.entries = []
        self.selected = 0
        self.mode = "browse"  # browse, action, input, warning
        self.action = None
        self.input_buffer = ""
        self.last_status_update = 0
        self.status_update_interval = 1.0
        self.refresh_entries()

    def refresh_entries(self):
        try:
            all_entries = sorted(os.listdir(self.cwd))
            dirs = []
            files = []
            for entry in all_entries:
                path = self.join(entry)
                try:
                    stat = os.stat(path)
                    if stat[0] & 0x4000:
                        dirs.append(entry)
                    else:
                        files.append(entry)
                except:
                    files.append(entry)
            self.entries = [".."] + dirs + files
        except Exception as e:
            self.entries = [".."]
            self.status_bar.set_status(f"Error: {e}", 0xFF0000)
        self.selected = 0

    def draw_menu(self):
        while len(self.menu_group) > 0:
            self.menu_group.pop()
        title = label.Label(
            terminalio.FONT, text=f"File Manager: {self.cwd}", color=0x00FFFF,
            x=10, y=MENU_START_Y + 8, scale=1
        )
        self.menu_group.append(title)
        visible_items = min(8, (SCREEN_HEIGHT - MENU_START_Y - 40) // 20)
        total_items = len(self.entries)
        if total_items <= visible_items:
            start_index = 0
            end_index = total_items
        else:
            if self.selected < visible_items // 2:
                start_index = 0
                end_index = visible_items
            elif self.selected > total_items - (visible_items // 2) - 1:
                end_index = total_items
                start_index = total_items - visible_items
            else:
                start_index = self.selected - visible_items // 2
                end_index = start_index + visible_items
        for i in range(start_index, end_index):
            entry = self.entries[i]
            y_pos = MENU_START_Y + 35 + (i - start_index) * 20
            is_dir = False
            is_system = False
            if entry == "..":
                is_dir = True
            else:
                try:
                    stat = os.stat(self.join(entry))
                    is_dir = stat[0] & 0x4000
                except:
                    pass
                is_system = self.is_system_file(self.join(entry))
            if i == self.selected:
                highlight_bitmap = displayio.Bitmap(SCREEN_WIDTH - 20, 18, 1)
                highlight_palette = displayio.Palette(1)
                highlight_palette[0] = 0x003366
                highlight_sprite = displayio.TileGrid(
                    highlight_bitmap, pixel_shader=highlight_palette,
                    x=10, y=y_pos - 12
                )
                self.menu_group.append(highlight_sprite)
                if is_system:
                    text_color = 0xFF55FF  # Pink for system files
                elif is_dir:
                    text_color = 0x00AAFF  # Blue for directories
                else:
                    text_color = 0xFFFF00  # Yellow for selected file
            else:
                if is_system:
                    text_color = 0xFF55FF  # Pink for system files
                elif is_dir:
                    text_color = 0x00AAFF  # Blue for directories
                else:
                    text_color = 0xFFFFFF  # White for files
            icon = "/" if is_dir else ""
            entry_label = label.Label(
                terminalio.FONT, text=f"{i}: {entry}{icon}",
                color=text_color, x=15, y=y_pos
            )
            self.menu_group.append(entry_label)
        if start_index > 0:
            up_arrow = label.Label(
                terminalio.FONT, text="^ More above",
                color=0x888888, x=SCREEN_WIDTH - 80, y=MENU_START_Y + 35
            )
            self.menu_group.append(up_arrow)
        if end_index < total_items:
            down_arrow = label.Label(
                terminalio.FONT, text="v More below",
                color=0x888888, x=SCREEN_WIDTH - 80, y=SCREEN_HEIGHT - 20
            )
            self.menu_group.append(down_arrow)
        instructions = label.Label(
            terminalio.FONT, text="Long: action  Short: next", color=0x00FF00, x=10, y=SCREEN_HEIGHT - 10
        )
        self.menu_group.append(instructions)

    def join(self, entry):
        if self.cwd.endswith("/"):
            return self.cwd + entry
        else:
            return self.cwd + "/" + entry

    def show_action_menu(self):
        entry = self.entries[self.selected]
        is_dir = False
        if entry == "..":
            actions = ["Open"]
        else:
            try:
                stat = os.stat(self.join(entry))
                is_dir = stat[0] & 0x4000
            except:
                pass
            actions = ["Open"] if is_dir else ["Launch", "Copy", "Move", "Delete", "Rename"]
        self.action_list = actions
        self.action_selected = 0
        self.mode = "action"
        self.draw_action_menu()

    def draw_action_menu(self):
        while len(self.menu_group) > 0:
            self.menu_group.pop()
        entry = self.entries[self.selected]
        title = label.Label(
            terminalio.FONT, text=f"Action: {entry}", color=0x00FFFF,
            x=10, y=MENU_START_Y + 8, scale=1
        )
        self.menu_group.append(title)
        for i, action in enumerate(self.action_list):
            y_pos = MENU_START_Y + 35 + i * 20
            if i == self.action_selected:
                highlight_bitmap = displayio.Bitmap(SCREEN_WIDTH - 20, 18, 1)
                highlight_palette = displayio.Palette(1)
                highlight_palette[0] = 0x003366
                highlight_sprite = displayio.TileGrid(
                    highlight_bitmap, pixel_shader=highlight_palette,
                    x=10, y=y_pos - 12
                )
                self.menu_group.append(highlight_sprite)
                text_color = 0xFFFF00
            else:
                text_color = 0xFFFFFF
            action_label = label.Label(
                terminalio.FONT, text=action, color=text_color, x=15, y=y_pos
            )
            self.menu_group.append(action_label)
        instructions = label.Label(
            terminalio.FONT, text="Long: select  Short: next", color=0x00FF00, x=10, y=SCREEN_HEIGHT - 10
        )
        self.menu_group.append(instructions)

    def show_input(self, prompt):
        self.input_buffer = ""
        self.input_prompt = prompt
        self.mode = "input"
        self.draw_input()

    def draw_input(self):
        while len(self.menu_group) > 0:
            self.menu_group.pop()
        prompt_label = label.Label(
            terminalio.FONT, text=self.input_prompt, color=0x00FFFF, x=10, y=MENU_START_Y + 8, scale=1
        )
        self.menu_group.append(prompt_label)
        input_label = label.Label(
            terminalio.FONT, text=self.input_buffer, color=0xFFFF00, x=15, y=MENU_START_Y + 40
        )
        self.menu_group.append(input_label)
        instructions = label.Label(
            terminalio.FONT, text="Long: confirm  Short: next char", color=0x00FF00, x=10, y=SCREEN_HEIGHT - 10
        )
        self.menu_group.append(instructions)

    def show_warning(self, message, on_confirm, on_cancel=None):
        self.mode = "warning"
        self.warning_message = message
        self.warning_on_confirm = on_confirm
        self.warning_on_cancel = on_cancel
        self.draw_warning()

    def draw_warning(self):
        while len(self.menu_group) > 0:
            self.menu_group.pop()
        warning_label = label.Label(
            terminalio.FONT, text="WARNING!", color=0xFF0000, x=10, y=MENU_START_Y + 8, scale=2
        )
        self.menu_group.append(warning_label)
        msg_label = label.Label(
            terminalio.FONT, text=self.warning_message, color=0xFFFF00, x=10, y=MENU_START_Y + 40, scale=1
        )
        self.menu_group.append(msg_label)
        instructions = label.Label(
            terminalio.FONT, text="Long: confirm  Short: cancel", color=0x00FF00, x=10, y=SCREEN_HEIGHT - 10
        )
        self.menu_group.append(instructions)

    def is_system_file(self, path):
        # Consider .py, .toml, .json, and anything in /system/ as important
        if path.startswith("/system/"):
            return True
        for ext in (".py", ".toml", ".json"):
            if path.endswith(ext):
                return True
        return False

    def main_loop(self):
        self.draw_menu()
        last_button = self.button.value if self.has_button else True
        prev_selected = self.selected
        start_time = time.monotonic()
        timeout = 60
        input_chars = "abcdefghijklmnopqrstuvwxyz0123456789._- /"
        input_index = 0
        button_hold_start = None
        while True:
            now = time.monotonic()
            if now - self.last_status_update > self.status_update_interval:
                self.status_bar.set_status(f"{self.cwd}", 0x00FFFF)
                self.last_status_update = now

            # --- Exit to app_loader if button held for 10s (non-blocking) ---
            if self.has_button:
                if not self.button.value:
                    if button_hold_start is None:
                        button_hold_start = now
                    elif now - button_hold_start > 10.0:
                        self.status_bar.set_status("Exiting...", 0xFF0000)
                        time.sleep(0.5)
                        try:
                            supervisor.set_next_code_file("/app_loader.py")
                            supervisor.reload()
                        except Exception as e:
                            self.status_bar.set_status(f"Exit error: {e}", 0xFF0000)
                            time.sleep(2)
                        return
                else:
                    button_hold_start = None

            # --- Navigation and modes ---
            if self.mode == "browse":
                if self.has_button:
                    if not self.button.value and last_button:
                        press_time = time.monotonic()
                        while not self.button.value:
                            if time.monotonic() - press_time > 1.0:
                                self.show_action_menu()
                                break
                            time.sleep(0.01)
                        else:
                            self.selected = (self.selected + 1) % len(self.entries)
                    last_button = self.button.value
                if self.selected != prev_selected:
                    self.draw_menu()
                    prev_selected = self.selected
            elif self.mode == "action":
                if self.has_button:
                    if not self.button.value and last_button:
                        press_time = time.monotonic()
                        while not self.button.value:
                            if time.monotonic() - press_time > 1.0:
                                self.handle_action()
                                self.mode = "browse"
                                self.refresh_entries()
                                self.draw_menu()
                                break
                            time.sleep(0.01)
                        else:
                            self.action_selected = (self.action_selected + 1) % len(self.action_list)
                            self.draw_action_menu()
                    last_button = self.button.value
            elif self.mode == "input":
                if self.has_button:
                    if not self.button.value and last_button:
                        press_time = time.monotonic()
                        while not self.button.value:
                            if time.monotonic() - press_time > 1.0:
                                self.handle_input()
                                self.mode = "browse"
                                self.refresh_entries()
                                self.draw_menu()
                                break
                            time.sleep(0.01)
                        else:
                            # Next char
                            input_index = (input_index + 1) % len(input_chars)
                            self.input_buffer = self.input_buffer[:-1] + input_chars[input_index] if self.input_buffer else input_chars[input_index]
                            self.draw_input()
                    last_button = self.button.value
            elif self.mode == "warning":
                if self.has_button:
                    if not self.button.value and last_button:
                        press_time = time.monotonic()
                        while not self.button.value:
                            if time.monotonic() - press_time > 1.0:
                                # Long press: confirm
                                if self.warning_on_confirm:
                                    self.warning_on_confirm()
                                self.mode = "browse"
                                self.refresh_entries()
                                self.draw_menu()
                                break
                            time.sleep(0.01)
                        else:
                            # Short press: cancel
                            if self.warning_on_cancel:
                                self.warning_on_cancel()
                            self.mode = "browse"
                            self.draw_menu()
                    last_button = self.button.value
            if time.monotonic() - start_time > timeout:
                self.status_bar.set_status("Timeout", 0xFF0000)
                time.sleep(1)
                break
            time.sleep(0.02)

    def handle_action(self):
        entry = self.entries[self.selected]
        path = self.join(entry)
        action = self.action_list[self.action_selected]
        def do_delete():
            try:
                os.remove(path)
                self.status_bar.set_status("Deleted", 0xFF0000)
            except Exception as e:
                self.status_bar.set_status(f"Error: {e}", 0xFF0000)
        def do_move():
            self.show_input("Move to:")
            self.input_buffer = entry
            self.input_action = "move"
        def do_rename():
            self.show_input("Rename to:")
            self.input_buffer = entry
            self.input_action = "rename"
        if action == "Open":
            if entry == "..":
                if self.cwd != "/":
                    self.cwd = "/".join(self.cwd.rstrip("/").split("/")[:-1]) or "/"
                    self.refresh_entries()
            else:
                try:
                    stat = os.stat(path)
                    if stat[0] & 0x4000:
                        self.cwd = path
                        self.refresh_entries()
                except Exception as e:
                    self.status_bar.set_status(f"Error: {e}", 0xFF0000)
        elif action == "Launch":
            if path.endswith(".py"):
                self.status_bar.set_status(f"Launching {entry}", 0xFFFF00)
                time.sleep(0.5)
                supervisor.set_next_code_file(path)
                supervisor.reload()
        elif action == "Copy":
            self.show_input("Copy to:")
            self.input_buffer = entry
            self.input_action = "copy"
        elif action == "Move":
            if self.is_system_file(path):
                self.show_warning(f"Move system file?\n{entry}", do_move)
            else:
                do_move()
        elif action == "Delete":
            if self.is_system_file(path):
                self.show_warning(f"Delete system file?\n{entry}", do_delete)
            else:
                do_delete()
        elif action == "Rename":
            if self.is_system_file(path):
                self.show_warning(f"Rename system file?\n{entry}", do_rename)
            else:
                do_rename()

    def handle_input(self):
        entry = self.entries[self.selected]
        path = self.join(entry)
        if self.input_action == "copy":
            dest = self.join(self.input_buffer)
            try:
                with open(path, "rb") as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                self.status_bar.set_status("Copied", 0x00FF00)
            except Exception as e:
                self.status_bar.set_status(f"Error: {e}", 0xFF0000)
        elif self.input_action == "move":
            dest = self.join(self.input_buffer)
            try:
                os.rename(path, dest)
                self.status_bar.set_status("Moved", 0x00FF00)
            except Exception as e:
                self.status_bar.set_status(f"Error: {e}", 0xFF0000)
        elif self.input_action == "rename":
            dest = self.join(self.input_buffer)
            try:
                os.rename(path, dest)
                self.status_bar.set_status("Renamed", 0x00FF00)
            except Exception as e:
                self.status_bar.set_status(f"Error: {e}", 0xFF0000)

if __name__ == "__main__":
    fm = FileManager()
    fm.main_loop()