import board
import displayio
import terminalio
from adafruit_display_text import label
import digitalio
import supervisor
import time
import microcontroller
import storage
import os
import wifi
import socketpool
import adafruit_requests
import json
import gc
import zipper

# Import boot functions for flag management
try:
    from boot import set_nvm_flag, RECOVERY_FLAG_ADDR, show_status
except ImportError:
    def set_nvm_flag(addr, val):
        microcontroller.nvm[addr] = 1 if val else 0
    RECOVERY_FLAG_ADDR = 0
    def show_status():
        print("Status unavailable")

# Recovery menu items
RECOVERY_MENU_ITEMS = [
    ("File System Check", "fs_check"),
    ("Restore Core Files", "restore_core"),
    ("Web Recovery", "web_recovery"),
    ("System Status", "show_status"),
    ("Clear All Flags", "clear_flags"),
    ("Reboot Normal", "reboot_normal"),
    ("Factory Reset", "factory_reset"),
    ("Backup System", "backup_system"),
]

# Core system manifest - essential files for basic operation
CORE_MANIFEST = {
    "boot.py": {"required": True, "description": "Boot loader"},
    "code.py": {"required": True, "description": "Main application"},
    "bootmenu.py": {"required": False, "description": "Boot menu"},
    "recovery.py": {"required": True, "description": "Recovery system"},
    "settings.toml": {"required": False, "description": "Configuration"},
    "lib/": {"required": True, "description": "Libraries directory"},
}

class RecoverySystem:
    def __init__(self):
        self.display = board.DISPLAY
        self.group = displayio.Group()
        self.display.root_group = self.group

        # Setup button if available
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except Exception:
            self.has_button = False

        self.selected = 0
        self.status_messages = []
        self.clear_recovery_flag()

    def clear_recovery_flag(self):
        set_nvm_flag(RECOVERY_FLAG_ADDR, False)
        self.log_message("Recovery flag cleared")

    def log_message(self, message):
        print(f"RECOVERY: {message}")
        self.status_messages.append(message)
        if len(self.status_messages) > 10:
            self.status_messages.pop(0)

    def draw_menu(self, selected_index):
        while len(self.group) > 0:
            self.group.pop()

        menu_group = displayio.Group()

        # Title
        title = label.Label(
            terminalio.FONT, text="RECOVERY MODE", color=0xFF00FF, x=10, y=8, scale=2
        )
        menu_group.append(title)

        # Menu items
        for i, (item, _) in enumerate(RECOVERY_MENU_ITEMS):
            y = 30 + i * 20
            if i == selected_index:
                # Highlight selected item
                highlight_bitmap = displayio.Bitmap(200, 18, 1)
                highlight_palette = displayio.Palette(1)
                highlight_palette[0] = 0x330066  # dark magenta
                highlight_tile = displayio.TileGrid(
                    highlight_bitmap, pixel_shader=highlight_palette, x=5, y=y - 10
                )
                menu_group.append(highlight_tile)
                color = 0xFFFF00  # yellow for selected
            else:
                color = 0xFFFFFF  # white

            text = label.Label(
                terminalio.FONT, text=f"{i}: {item}", color=color, x=10, y=y
            )
            menu_group.append(text)

        # Status area
        status_y = 190
        status_text = label.Label(
            terminalio.FONT, text="Press button or use serial", color=0x00FF00, x=10, y=status_y
        )
        menu_group.append(status_text)

        self.group.append(menu_group)

    def show_progress(self, message, progress=None):
        while len(self.group) > 0:
            self.group.pop()

        progress_group = displayio.Group()

        title = label.Label(
            terminalio.FONT, text="RECOVERY MODE", color=0xFF00FF, x=10, y=8, scale=2
        )
        progress_group.append(title)

        msg = label.Label(
            terminalio.FONT, text=message, color=0xFFFFFF, x=10, y=60
        )
        progress_group.append(msg)

        if progress is not None:
            prog_text = label.Label(
                terminalio.FONT, text=f"Progress: {progress}%", color=0x00FF00, x=10, y=80
            )
            progress_group.append(prog_text)

        self.group.append(progress_group)

    def filesystem_check(self):
        self.show_progress("Checking filesystem...")
        self.log_message("Starting filesystem check")
        try:
            storage.remount("/", readonly=False)
            manifest_path = "/system/manifest.json"
            manifest_exists = False
            try:
                try:
                    os.mkdir("/system")
                except OSError:
                    pass
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    manifest_exists = True
                    self.log_message("Manifest found")
            except OSError:
                self.log_message("Manifest not found, creating default")
                manifest = CORE_MANIFEST

            if not manifest_exists:
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f)
                self.log_message("Manifest created")

            missing_files = []
            for file_path, info in manifest.items():
                if info.get("required", False):
                    try:
                        if file_path.endswith("/"):
                            os.listdir(file_path)
                        else:
                            os.stat(file_path)
                    except OSError:
                        missing_files.append(file_path)

            if missing_files:
                self.log_message(f"Missing files: {', '.join(missing_files)}")
                return False, missing_files
            else:
                self.log_message("All core files present")
                return True, []

        except Exception as e:
            self.log_message(f"Filesystem check failed: {e}")
            return False, []

    def restore_core_files(self):
        self.show_progress("Restoring core files...")
        self.log_message("Starting core file restoration")
        try:
            recovery_zip_path = "/system/recovery.zip"
            # Defensive: Ensure path is a string before unzip
            if not isinstance(recovery_zip_path, str):
                self.log_message(f"Invalid recovery zip path: {recovery_zip_path}")
                return False
            try:
                os.stat(recovery_zip_path)
            except OSError:
                self.log_message("Recovery zip not found!")
                return False
            zipper.unzip(recovery_zip_path, "/")
            self.log_message("Core files restored from recovery.zip")

            system_zip_path = "/system/system.zip"
            if isinstance(system_zip_path, str):
                try:
                    os.stat(system_zip_path)
                    zipper.unzip(system_zip_path, "/system")
                    self.log_message("System files restored from system.zip")
                except OSError:
                    self.log_message("No system.zip found in /system (skipped)")
            else:
                self.log_message(f"Invalid system zip path: {system_zip_path}")

            # Backup settings.toml to /sd/config/settings.toml if possible
            try:
                src = "/settings.toml"
                dst_dir = "/sd/config"
                dst = dst_dir + "/settings.toml"
                try:
                    os.stat("/sd")
                    try:
                        os.mkdir(dst_dir)
                    except OSError:
                        pass
                    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
                        fdst.write(fsrc.read())
                    self.log_message("settings.toml backed up to /sd/config/")
                except OSError:
                    self.log_message("SD card or /sd/config not available, backup skipped")
            except Exception as e:
                self.log_message(f"Backup failed: {e}")

            self.log_message("Core files restored successfully")
            return True

        except Exception as e:
            self.log_message(f"Core file restoration failed: {e}")
            return False

    def backup_system(self):
        self.show_progress("Backing up system files...")
        self.log_message("Starting system backup")
        try:
            backup_zip_path = "/system/backup.zip"
            files_to_backup = []
            for entry in os.listdir("/"):
                path = "/" + entry
                try:
                    stat = os.stat(path)
                    # Only backup files and directories, skip pins/devices
                    if (stat[0] & 0x4000) or (stat[0] & 0x8000):
                        files_to_backup.append(path)
                except OSError:
                    continue
                except Exception as e:
                    self.log_message(f"Skipping {path}: {e}")
                    continue
            # Defensive: Only pass string paths to zipper.zip
            files_to_backup = [p for p in files_to_backup if isinstance(p, str)]
            zipper.zip(files_to_backup, backup_zip_path)
            self.log_message("System backup completed")
            self.show_progress("Backup complete!")
            time.sleep(2)
            return True
        except Exception as e:
            self.log_message(f"Backup error: {e}")
            self.show_progress(f"Backup error: {e}")
            time.sleep(2)
            return False

    def web_recovery(self):
        self.show_progress("Initializing web recovery...")
        self.log_message("Starting web recovery")
        try:
            if not wifi.radio.connected:
                self.log_message("WiFi not connected, attempting connection...")
                wifi_ssid = os.getenv("CIRCUITPY_WIFI_SSID")
                wifi_password = os.getenv("CIRCUITPY_WIFI_PASSWORD")
                if not wifi_ssid:
                    self.log_message("WiFi credentials not found in settings.toml")
                    return False
                wifi.radio.connect(wifi_ssid, wifi_password)
            self.show_progress("Downloading web recovery...")
            pool = socketpool.SocketPool(wifi.radio)
            requests = adafruit_requests.Session(pool)
            url = "https://raw.githubusercontent.com/d31337m3/stagetwo/main/web_recovery.py"
            response = requests.get(url)
            if response.status_code == 200:
                with open("/webrecovery.py", "w") as f:
                    f.write(response.text)
                self.log_message("Web recovery downloaded successfully")
                supervisor.set_next_code_file("webrecovery.py")
                self.show_progress("Launching web recovery...")
                time.sleep(2)
                supervisor.reload()
            else:
                self.log_message(f"Download failed: HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_message(f"Web recovery failed: {e}")
            return False

    def clear_all_flags(self):
        self.show_progress("Clearing all flags...")
        try:
            for i in range(10):
                microcontroller.nvm[i] = 0
            self.log_message("All flags cleared")
            return True
        except Exception as e:
            self.log_message(f"Failed to clear flags: {e}")
            return False

    def factory_reset(self):
        self.show_progress("Factory reset in progress...")
        self.log_message("WARNING: Factory reset initiated")
        try:
            self.clear_all_flags()
            user_files = ["code.py", "settings.toml", "bootmenu.py"]
            for file in user_files:
                try:
                    os.remove(file)
                    self.log_message(f"Removed: {file}")
                except OSError:
                    pass
            if self.restore_core_files():
                self.log_message("Factory reset completed")
                time.sleep(3)
                microcontroller.reset()
            else:
                self.log_message("Factory reset failed")
                return False
        except Exception as e:
            self.log_message(f"Factory reset error: {e}")
            return False

    def run_action(self, index):
        _, action = RECOVERY_MENU_ITEMS[index]
        if action == "fs_check":
            success, missing = self.filesystem_check()
            if success:
                self.show_progress("Filesystem OK!")
            else:
                self.show_progress(f"Issues found: {len(missing)} missing files")
            time.sleep(3)
        elif action == "restore_core":
            if self.restore_core_files():
                self.show_progress("Core files restored!")
            else:
                self.show_progress("Restoration failed!")
            time.sleep(3)
        elif action == "web_recovery":
            self.web_recovery()
        elif action == "show_status":
            show_status()
            self.show_status_screen()
        elif action == "clear_flags":
            if self.clear_all_flags():
                self.show_progress("Flags cleared!")
            else:
                self.show_progress("Failed to clear flags!")
            time.sleep(2)
        elif action == "reboot_normal":
            self.show_progress("Rebooting to normal mode...")
            time.sleep(2)
            supervisor.set_next_code_file("boot.py")
            supervisor.reload()
        elif action == "factory_reset":
            self.factory_reset()
        elif action == "backup_system":
            self.backup_system()

    def show_status_screen(self):
        while len(self.group) > 0:
            self.group.pop()
        status_group = displayio.Group()
        title = label.Label(
            terminalio.FONT, text="SYSTEM STATUS", color=0x00FFFF, x=10, y=8, scale=2
        )
        status_group.append(title)
        for i, msg in enumerate(self.status_messages[-8:]):
            y = 30 + i * 15
            text = label.Label(
                terminalio.FONT, text=msg[:30], color=0xFFFFFF, x=10, y=y
            )
            status_group.append(text)
        inst = label.Label(
            terminalio.FONT, text="Press any key to return", color=0x00FF00, x=10, y=200
        )
        status_group.append(inst)
        self.group.append(status_group)
        while True:
            if supervisor.runtime.serial_bytes_available:
                input()
                break
            if self.has_button and not self.button.value:
                time.sleep(0.5)
                break
            time.sleep(0.1)

    def menu_loop(self):
        self.draw_menu(self.selected)
        last_button = True if self.has_button else True
        self.log_message("Performing initial filesystem check...")
        fs_ok, missing = self.filesystem_check()
        if not fs_ok and missing:
            self.log_message("Attempting automatic core file restoration...")
            self.restore_core_files()
        print("RECOVERY MODE ACTIVE")
        print("Commands: up/down/select or 0-7")
        while True:
            if supervisor.runtime.serial_bytes_available:
                try:
                    cmd = input().strip().lower()
                    if cmd in ["up", "u"]:
                        self.selected = (self.selected - 1) % len(RECOVERY_MENU_ITEMS)
                        self.draw_menu(self.selected)
                    elif cmd in ["down", "d"]:
                        self.selected = (self.selected + 1) % len(RECOVERY_MENU_ITEMS)
                        self.draw_menu(self.selected)
                    elif cmd in ["select", "s", "enter"]:
                        self.run_action(self.selected)
                        self.draw_menu(self.selected)
                    elif cmd.isdigit() and 0 <= int(cmd) < len(RECOVERY_MENU_ITEMS):
                        self.selected = int(cmd)
                        self.run_action(self.selected)
                        self.draw_menu(self.selected)
                    elif cmd in ["help", "h"]:
                        print("Recovery Commands:")
                        print("  up/u - Move up")
                        print("  down/d - Move down")
                        print("  select/s/enter - Execute")
                        print("  0-7 - Direct selection")
                        print("  help/h - Show this help")
                        print("  status - Show system status")
                    elif cmd == "status":
                        show_status()
                        for msg in self.status_messages:
                            print(f"  {msg}")
                    else:
                        print("Invalid command. Type 'help' for commands.")
                except Exception:
                    pass
            if self.has_button:
                current_button = self.button.value
                if not current_button and last_button:
                    time.sleep(0.05)
                    if not self.button.value:
                        press_start = time.monotonic()
                        while not self.button.value:
                            if time.monotonic() - press_start > 1.0:
                                self.run_action(self.selected)
                                self.draw_menu(self.selected)
                                break
                            time.sleep(0.1)
                        else:
                            self.selected = (self.selected + 1) % len(RECOVERY_MENU_ITEMS)
                            self.draw_menu(self.selected)
                last_button = current_button
            time.sleep(0.05)
            gc.collect()

def main():
    print("=" * 50)
    print("RECOVERY MODE ACTIVATED")
    print("=" * 50)
    try:
        recovery = RecoverySystem()
        recovery.menu_loop()
    except Exception as e:
        print(f"CRITICAL RECOVERY ERROR: {e}")
        print("Attempting basic recovery...")
        basic_recovery()

def basic_recovery():
    print("=== BASIC RECOVERY MODE ===")
    print("Display system failed, using text-only mode")
    try:
        set_nvm_flag(RECOVERY_FLAG_ADDR, False)
        print("Recovery flag cleared")
    except Exception:
        pass
    while True:
        print("\nBasic Recovery Options:")
        print("1. Clear all flags and reboot")
        print("2. Show system status")
        print("3. Reboot to normal mode")
        print("4. Factory reset")
        print("5. Exit recovery")
        try:
            choice = input("Select option (1-5): ").strip()
            if choice == "1":
                try:
                    for i in range(10):
                        microcontroller.nvm[i] = 0
                    print("All flags cleared")
                    time.sleep(2)
                    microcontroller.reset()
                except Exception as e:
                    print(f"Error clearing flags: {e}")
            elif choice == "2":
                try:
                    show_status()
                except Exception:
                    print("Status unavailable")
            elif choice == "3":
                print("Rebooting to normal mode...")
                time.sleep(2)
                try:
                    supervisor.set_next_code_file("boot.py")
                    supervisor.reload()
                except Exception:
                    microcontroller.reset()
            elif choice == "4":
                confirm = input("Factory reset will erase settings. Continue? (yes/no): ")
                if confirm.lower() == "yes":
                    try:
                        for i in range(10):
                            microcontroller.nvm[i] = 0
                        try:
                            os.remove("settings.toml")
                        except Exception:
                            pass
                        print("Factory reset completed")
                        time.sleep(2)
                        microcontroller.reset()
                    except Exception as e:
                        print(f"Factory reset error: {e}")
            elif choice == "5":
                print("Exiting recovery mode...")
                break
            else:
                print("Invalid option")
        except KeyboardInterrupt:
            print("\nExiting recovery...")
            break
        except Exception:
            print("Input error, try again")

if __name__ == "__main__":
    main()