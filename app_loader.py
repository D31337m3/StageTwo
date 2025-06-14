import board
import displayio
import terminalio
from adafruit_display_text import label
import time
import os
import digitalio
import supervisor
import sys
import io
import traceback
import json
import gc

# Try to import WiFi and BLE modules
try:
    import wifi
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

try:
    import _bleio
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False

# Display constants
SCREEN_WIDTH = board.DISPLAY.width
SCREEN_HEIGHT = board.DISPLAY.height
STATUS_BAR_HEIGHT = 20
MENU_START_Y = STATUS_BAR_HEIGHT + 10

def load_settings():
    """Load settings from settings.toml"""
    settings = {}
    try:
        with open("/settings.toml", "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Convert numeric values
                    if value.isdigit():
                        value = int(value)
                    elif value.lower() in ("true", "false"):
                        value = value.lower() == "true"
                    
                    settings[key] = value
    except Exception as e:
        print(f"Error loading settings: {e}")
    return settings

def save_settings(settings):
    """Save settings to settings.toml"""
    try:
        with open("/settings.toml", "w") as f:
            for key, value in settings.items():
                if isinstance(value, bool):
                    f.write(f"{key} = {str(value).lower()}\n")
                elif isinstance(value, int):
                    f.write(f"{key} = {value}\n")
                else:
                    f.write(f'{key} = "{value}"\n')
    except Exception as e:
        print(f"Error saving settings: {e}")


class StatusBar:
    def __init__(self, display_group):
        self.group = displayio.Group()
        self.display_group = display_group
        
        # Create status bar background
        self.bg_bitmap = displayio.Bitmap(SCREEN_WIDTH, STATUS_BAR_HEIGHT, 1)
        self.bg_palette = displayio.Palette(1)
        self.bg_palette[0] = 0x001122  # Dark blue background
        self.bg_sprite = displayio.TileGrid(self.bg_bitmap, pixel_shader=self.bg_palette, x=0, y=0)
        self.group.append(self.bg_sprite)
        
        # WiFi status icon (left side)
        self.wifi_label = label.Label(
            terminalio.FONT, text="", color=0x00FF00, x=5, y=12
        )
        self.group.append(self.wifi_label)
        
        # BLE status icon (left side, next to WiFi)
        self.ble_label = label.Label(
            terminalio.FONT, text="", color=0x0080FF, x=45, y=12
        )
        self.group.append(self.ble_label)
        
        # System status (center-left)
        self.status_label = label.Label(
            terminalio.FONT, text="Ready", color=0xFFFFFF, x=80, y=12
        )
        self.group.append(self.status_label)
        
        # Time display (right side)
        self.time_label = label.Label(
            terminalio.FONT, text="--:-- --", color=0xFFFF00, x=SCREEN_WIDTH - 70, y=12
        )
        self.group.append(self.time_label)
        
        self.display_group.append(self.group)
        
    def update_wifi_status(self):
        """Update WiFi status icon with signal quality"""
        if not WIFI_AVAILABLE:
            self.wifi_label.text = ""
            return
            
        try:
            if wifi.radio.connected:
                # Show signal strength with different colors
                rssi = wifi.radio.ap_info.rssi if wifi.radio.ap_info else -100
                if rssi > -50:
                    self.wifi_label.text = "WiFi+"
                    self.wifi_label.color = 0x00FF00  # Green - excellent
                elif rssi > -70:
                    self.wifi_label.text = "WiFi"
                    self.wifi_label.color = 0xFFFF00  # Yellow - good
                else:
                    self.wifi_label.text = "WiFi-"
                    self.wifi_label.color = 0xFF8000  # Orange - weak
            else:
                self.wifi_label.text = "WiFi?"
                self.wifi_label.color = 0xFF0000  # Red - disconnected
        except Exception:
            self.wifi_label.text = "WiFi?"
            self.wifi_label.color = 0xFF0000
            
    def update_ble_status(self):
        """Update BLE status icon"""
        if not BLE_AVAILABLE:
            self.ble_label.text = ""
            return
            
        try:
            # Check if BLE is enabled/active
            if _bleio.adapter.enabled:
                if _bleio.adapter.connected:
                    self.ble_label.text = "BLE+"
                    self.ble_label.color = 0x00FF00  # Green - connected
                else:
                    self.ble_label.text = "BLE"
                    self.ble_label.color = 0x0080FF  # Blue - advertising/available
            else:
                self.ble_label.text = "BLE-"
                self.ble_label.color = 0x888888  # Gray - disabled
        except Exception:
            self.ble_label.text = ""
            
    def update_time(self):
        """Update time display in 12-hour format"""
        try:
            current_time = time.localtime()
            hour = current_time.tm_hour
            minute = current_time.tm_min
            
            # Convert to 12-hour format
            if hour == 0:
                hour_12 = 12
                am_pm = "AM"
            elif hour < 12:
                hour_12 = hour
                am_pm = "AM"
            elif hour == 12:
                hour_12 = 12
                am_pm = "PM"
            else:
                hour_12 = hour - 12
                am_pm = "PM"
                
            time_str = f"{hour_12:2d}:{minute:02d} {am_pm}"
            self.time_label.text = time_str
            
            # Adjust position based on text width
            self.time_label.x = SCREEN_WIDTH - len(time_str) * 6 - 5
        except Exception:
            self.time_label.text = "--:-- --"
            
    def set_status(self, status_text, color=0xFFFFFF):
        """Set the status message"""
        self.status_label.text = status_text[:20]  # Limit length
        self.status_label.color = color
        
    def update_all(self):
        """Update all status bar elements"""
        self.update_wifi_status()
        self.update_ble_status()
        self.update_time()

class AppLoader:
    def __init__(self):
        self.display = board.DISPLAY
        self.screen_width = self.display.width
        self.screen_height = self.display.height
        
        # Initialize button if available
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.switch_to_input(pull=digitalio.Pull.UP)
            self.has_button = True
        except Exception:
            self.has_button = False
            print("No button available - console only mode")
        
        # Initialize status bar
        self.main_group = displayio.Group()
        self.status_bar = StatusBar(self.main_group)
        
        # Load apps configuration
        self.apps_config_path = "/system/apps.json"
        self.apps = []
        self.selected = 0
        
        # Load screensaver settings
        self.settings = load_settings()
        self.screensaver_timeout = self.settings.get("SCREENSAVER_TIMEOUT", 60)  # 60s default
        self.screensaver_enabled = self.settings.get("SCREENSAVER_ENABLED", True)
        self.screensaver_type = self.settings.get("SCREENSAVER_TYPE", "trippy")  # "trippy" or "constellation"
        
        # Screensaver timing
        self.last_activity_time = time.monotonic()
        self.screensaver_active = False
        
        # Ensure system directory exists
        self._ensure_system_dir()
        
        # Discover and load apps
        self._discover_apps()
        self._load_apps_config()

    def _check_screensaver_timeout(self):
        """Check if screensaver should activate"""
        if not self.screensaver_enabled:
            return False
        
        current_time = time.monotonic()
        if current_time - self.last_activity_time >= self.screensaver_timeout:
            return True
        return False
    
    def _reset_screensaver_timer(self):
        """Reset screensaver timer on user activity"""
        self.last_activity_time = time.monotonic()
    
    def _start_screensaver(self):
        """Start the appropriate screensaver"""
        self.screensaver_active = True
        
        def return_to_app_loader():
            """Return from screensaver to app loader"""
            self.screensaver_active = False
            self._reset_screensaver_timer()
            self.draw_menu()
        
        try:
            if self.screensaver_type == "constellation":
                # Try to import constellation screensaver
                try:
                    from system.screensaver import start_screensaver_night_mode
                    start_screensaver_night_mode(return_to_app_loader)
                except ImportError:
                    print("Constellation screensaver not available, using trippy")
                    from system.trippy_screensaver import start_screensaver
                    start_screensaver(return_to_app_loader)
            else:  # Default to trippy
                from system.trippy_screensaver import start_screensaver
                start_screensaver(return_to_app_loader)
                
        except Exception as e:
            print(f"Screensaver error: {e}")
            self.screensaver_active = False
            self._reset_screensaver_timer()

    def _is_developer_mode(self):
        """Check if developer mode is enabled via NVM flag"""
        try:
            import microcontroller
            # Read the developer mode flag from NVM
            nvm_data = microcontroller.nvm
            if len(nvm_data) > 1:  # DEVELOPER_MODE_FLAG_ADDR = 1
                return bool(nvm_data[1])  # Check byte at address 1
            return False
        except Exception as e:
            print(f"Error checking developer mode: {e}")
            return False  # Default to non-developer mode if we can't read NVM

    
    def _ensure_system_dir(self):
        """Ensure /system directory exists"""
        try:
            os.mkdir("/system")
        except OSError:
            pass  # Directory already exists or other error


    def _discover_apps(self):
        """Discover apps in /apps directories on flash and SD"""
        discovered_apps = []
        
        # Search locations
        search_paths = ["/apps"]
        
        # Check for SD card mount (common mount points)
        sd_paths = ["/sd/apps", "/mnt/sd/apps", "/external/apps"]
        for sd_path in sd_paths:
            try:
                if os.path.exists(sd_path):
                    search_paths.append(sd_path)
            except Exception:
                continue
        
        # Discover apps in each path
        for search_path in search_paths:
            try:
                if os.path.exists(search_path):
                    self._scan_directory_for_apps(search_path, discovered_apps)
            except Exception as e:
                print(f"Error scanning {search_path}: {e}")
        
        # Check developer mode before scanning root directory
        if self._is_developer_mode():
            # Also check root directory for standalone apps
            try:
                root_files = os.listdir("/")
                for filename in root_files:
                    if (filename.endswith(".py") and 
                        filename not in ("code.py", "boot.py", "app_loader.py") and
                        not filename.startswith(".")):
                        
                        app_info = {
                            "name": filename[:-3],  # Remove .py extension
                            "path": "/" + filename,
                            "description": f"Standalone app: {filename}",
                            "enabled": True,
                            "location": "root"
                        }
                        discovered_apps.append(app_info)
            except Exception as e:
                print(f"Error scanning root: {e}")
        
        self.discovered_apps = discovered_apps
        print(f"Discovered {len(discovered_apps)} apps")


    def _scan_directory_for_apps(self, directory, apps_list):
        """Scan a directory for Python apps"""
        try:
            items = os.listdir(directory)
            for item in items:
                item_path = directory + "/" + item
                
                if item.endswith(".py"):
                    # Single Python file app
                    app_info = {
                        "name": item[:-3],  # Remove .py extension
                        "path": item_path,
                        "description": f"App from {directory}",
                        "enabled": True,
                        "location": directory
                    }
                    apps_list.append(app_info)
                    
                elif self._is_directory(item_path):
                    # Directory-based app (look for main.py or app.py)
                    main_files = ["main.py", "app.py", item + ".py"]
                    for main_file in main_files:
                        main_path = item_path + "/" + main_file
                        if self._file_exists(main_path):
                            app_info = {
                                "name": item,
                                "path": main_path,
                                "description": f"Directory app: {item}",
                                "enabled": True,
                                "location": directory
                            }
                            apps_list.append(app_info)
                            break
                            
        except Exception as e:
            print(f"Error scanning {directory}: {e}")

    def _is_directory(self, path):
        """Check if path is a directory"""
        try:
            stat = os.stat(path)
            return bool(stat[0] & 0x4000)
        except Exception:
            return False

    def _file_exists(self, path):
        """Check if file exists"""
        try:
            os.stat(path)
            return True
        except Exception:
            return False

    def _load_apps_config(self):
        """Load apps configuration from JSON file"""
        try:
            with open(self.apps_config_path, "r") as f:
                config = json.load(f)
                saved_apps = config.get("apps", [])
                
            # Merge discovered apps with saved configuration
            self.apps = []
            
            # First, add apps from config that still exist
            for saved_app in saved_apps:
                if self._file_exists(saved_app["path"]):
                    self.apps.append(saved_app)
            
            # Then add newly discovered apps not in config
            for discovered_app in self.discovered_apps:
                if not any(app["path"] == discovered_app["path"] for app in self.apps):
                    self.apps.append(discovered_app)
            
            # Save updated configuration
            self._save_apps_config()
            
        except Exception as e:
            print(f"Error loading apps config: {e}")
            # Use discovered apps as fallback
            self.apps = self.discovered_apps
            self._save_apps_config()

    def _save_apps_config(self):
        """Save apps configuration to JSON file"""
        try:
            config = {
                "apps": self.apps,
                "last_updated": time.time()
            }
            with open(self.apps_config_path, "w") as f:
                json.dump(config, f)
        except Exception as e:
            print(f"Error saving apps config: {e}")

    def draw_menu(self):
        """Draw the main menu with status bar"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        # Update status bar
        self.status_bar.update_all()
        
        # Create menu group
        menu_group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, 
            text="App Loader", 
            color=0x00FFFF, 
            x=10, 
            y=MENU_START_Y + 10
        )
        menu_group.append(title)

        if not self.apps:
            no_apps_label = label.Label(
                terminalio.FONT, 
                text="No apps found.", 
                color=0xFF0000, 
                x=10, 
                y=MENU_START_Y + 30
            )
            menu_group.append(no_apps_label)
        else:
            # Calculate visible apps
            menu_height = self.screen_height - MENU_START_Y - 40
            max_visible = menu_height // 15
            start_idx = max(0, self.selected - max_visible // 2)
            end_idx = min(len(self.apps), start_idx + max_visible)
            
            if end_idx - start_idx < max_visible and len(self.apps) > max_visible:
                start_idx = max(0, end_idx - max_visible)
            
            # Display apps
            enabled_apps = [app for app in self.apps if app.get("enabled", True)]
            
            for i in range(start_idx, end_idx):
                if i < len(enabled_apps):
                    app = enabled_apps[i]
                    prefix = ">" if i == self.selected else " "
                    color = 0x00FF00 if i == self.selected else 0xFFFFFF
                    
                    # Truncate long names
                    display_name = app["name"]
                    if len(display_name) > 25:
                        display_name = display_name[:22] + "..."
                    
                    app_label = label.Label(
                        terminalio.FONT,
                        text=f"{prefix} {display_name}",
                        color=color,
                        x=10,
                        y=MENU_START_Y + 30 + (i - start_idx) * 15
                    )
                    menu_group.append(app_label)
            
            # Navigation help
            help_text = "Short: Next  Long: Run  Hold: Menu"
            help_label = label.Label(
                terminalio.FONT,
                text=help_text,
                color=0x888888,
                x=10,
                y=self.screen_height - 30
            )
            menu_group.append(help_label)
            
            # Position indicator
            pos_text = f"{self.selected+1}/{len(enabled_apps)}"
            pos_label = label.Label
            pos_label = label.Label(
                terminalio.FONT,
                text=pos_text,
                color=0x888888,
                x=self.screen_width - 60,
                y=self.screen_height - 30
            )
            menu_group.append(pos_label)

        self.main_group.append(menu_group)
        self.display.root_group = self.main_group

    def show_message(self, msg, color=0xFFFFFF, duration=None):
        """Show a message on screen"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        # Update status bar
        self.status_bar.update_all()
        
        message_group = displayio.Group()
        lines = msg.split("\n")
        
        for i, line in enumerate(lines):
            if line.strip():  # Skip empty lines
                text_label = label.Label(
                    terminalio.FONT, 
                    text=line, 
                    color=color, 
                    x=10, 
                    y=MENU_START_Y + 20 + i * 20
                )
                message_group.append(text_label)
        
        self.main_group.append(message_group)
        self.display.root_group = self.main_group
        
        if duration:
            time.sleep(duration)

    def show_app_details(self, app):
        """Show detailed information about an app"""
        details = f"Name: {app['name']}\n"
        details += f"Path: {app['path']}\n"
        details += f"Location: {app.get('location', 'unknown')}\n"
        details += f"Description: {app.get('description', 'No description')}\n\n"
        details += "Long press to run\nShort press to return"
        
        self.show_message(details, color=0x00FFFF)

    def run_app(self, app):
        """Run the selected app"""
        app_path = app["path"]
        app_name = app["name"]
        
        self.status_bar.set_status(f"Loading {app_name}...", 0xFFFF00)
        self.show_message(f"Starting {app_name}...", color=0x00FF00, duration=1)
        
        # Method 1: Try supervisor.set_next_code_file (preferred)
        try:
            if hasattr(supervisor, "set_next_code_file"):
                supervisor.set_next_code_file(app_path)
                time.sleep(0.1)
                supervisor.reload()
                return  # This should restart the system
        except Exception as e:
            print(f"set_next_code_file failed: {e}")
            self.show_message(f"Reload method failed:\n{str(e)}", color=0xFF8000, duration=2)

        # Method 2: Try to exec the file directly
        try:
            self.status_bar.set_status(f"Executing {app_name}...", 0xFF8000)
            
            # Save current working directory
            original_cwd = os.getcwd() if hasattr(os, 'getcwd') else "/"
            
            # Change to app directory if it's a directory-based app
            app_dir = "/".join(app_path.split("/")[:-1])
            if app_dir and app_dir != "/":
                try:
                    os.chdir(app_dir)
                except Exception:
                    pass
            
            # Read and execute the app
            with open(app_path, "r") as f:
                app_code = f.read()
            
            # Create a clean namespace for the app
            app_globals = {
                "__name__": "__main__",
                "__file__": app_path,
            }
            
            # Redirect stdout/stderr to capture output
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            output_buffer = io.StringIO()
            error_buffer = io.StringIO()
            
            sys.stdout = output_buffer
            sys.stderr = error_buffer
            
            success = True
            error_msg = ""
            
            try:
                exec(app_code, app_globals)
            except SystemExit:
                # App called sys.exit(), this is normal
                pass
            except Exception as e:
                success = False
                error_msg = traceback.format_exc()
            finally:
                # Restore stdout/stderr
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                
                # Restore working directory
                try:
                    os.chdir(original_cwd)
                except Exception:
                    pass
            
            # Show results
            output = output_buffer.getvalue()
            errors = error_buffer.getvalue()
            
            if success:
                if output:
                    self.show_message(f"{app_name} output:\n{output[:200]}", color=0x00FF00)
                else:
                    self.show_message(f"{app_name} completed successfully", color=0x00FF00)
            else:
                error_display = error_msg if error_msg else errors
                self.show_message(f"Error in {app_name}:\n{error_display[:200]}", color=0xFF0000)
                
        except Exception as e:
            self.show_message(f"Failed to run {app_name}:\n{str(e)}", color=0xFF0000)
        
        # Wait for user input before returning to menu
        self.status_bar.set_status("Press button to continue", 0x888888)
        self._wait_for_button_release()
        self._wait_for_button_press()
        self.status_bar.set_status("Ready", 0xFFFFFF)

    def refresh_apps(self):
        """Refresh the apps list"""
        self.status_bar.set_status("Refreshing apps...", 0xFFFF00)
        self.show_message("Scanning for apps...", color=0x00FFFF, duration=1)
        
        self._discover_apps()
        self._load_apps_config()
        self.selected = 0
        
        self.status_bar.set_status("Apps refreshed", 0x00FF00)
        time.sleep(1)
        self.status_bar.set_status("Ready", 0xFFFFFF)

    def show_settings_menu(self):
        """Show settings/management menu"""
        settings_options = [
            "Refresh Apps",
            "Toggle App Status",
            "View App Details", 
            "Screensaver Settings",
            "System Info",
            "Back to Main Menu"
        ]
        
        settings_selected = 0
        
        while True:
            # Clear main group but keep status bar
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.update_all()
            
            settings_group = displayio.Group()
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="Settings",
                color=0xFF8000,
                x=10,
                y=MENU_START_Y + 10
            )
            settings_group.append(title)
            
            # Options
            for i, option in enumerate(settings_options):
                prefix = ">" if i == settings_selected else " "
                color = 0x00FF00 if i == settings_selected else 0xFFFFFF
                
                option_label = label.Label(
                    terminalio.FONT,
                    text=f"{prefix} {option}",
                    color=color,
                    x=10,
                    y=MENU_START_Y + 30 + i * 15
                )
                settings_group.append(option_label)
            
            self.main_group.append(settings_group)
            self.display.root_group = self.main_group
            
            # Handle input
            press_duration = self._handle_button_input()
            
            if press_duration > 1.0:  # Long press - select option
                if settings_selected == 0:  # Refresh Apps
                    self.refresh_apps()
                elif settings_selected == 1:  # Toggle App Status
                    self._toggle_app_status()
                elif settings_selected == 2:  # View App Details
                    self._view_app_details_menu()
                elif settings_selected == 3:  # Screensaver Settings
                    self._show_screensaver_settings()
                elif settings_selected == 4:  # System Info
                    self._show_system_info()
                elif settings_selected == 5:  # Back
                    break
                    
            elif press_duration > 0.05:  # Short press - navigate
                settings_selected = (settings_selected + 1) % len(settings_options)
            
            # Reset screensaver timer on any activity
            self._reset_screensaver_timer()


    def _show_screensaver_settings(self):
        """Show screensaver configuration"""
        screensaver_options = [
            f"Enabled: {'Yes' if self.screensaver_enabled else 'No'}",
            f"Timeout: {self.screensaver_timeout//60}min {self.screensaver_timeout%60}s",
            f"Type: {self.screensaver_type.title()}",
            "Test Screensaver",
            "Back"
        ]
        
        screensaver_selected = 0
        
        while True:
            # Clear main group but keep status bar
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.update_all()
            
            screensaver_group = displayio.Group()
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="Screensaver Settings",
                color=0xFF8000,
                x=10,
                y=MENU_START_Y + 10
            )
            screensaver_group.append(title)
            
            # Update options with current values
            screensaver_options[0] = f"Enabled: {'Yes' if self.screensaver_enabled else 'No'}"
            screensaver_options[1] = f"Timeout: {self.screensaver_timeout//60}min {self.screensaver_timeout%60}s"
            screensaver_options[2] = f"Type: {self.screensaver_type.title()}"
            
            # Options
            for i, option in enumerate(screensaver_options):
                prefix = ">" if i == screensaver_selected else " "
                color = 0x00FF00 if i == screensaver_selected else 0xFFFFFF
                
                option_label = label.Label(
                    terminalio.FONT,
                    text=f"{prefix} {option}",
                    color=color,
                    x=10,
                    y=MENU_START_Y + 30 + i * 15
                )
                screensaver_group.append(option_label)
            
            # Help text
            help_label = label.Label(
                terminalio.FONT,
                text="Long: Select  Short: Next",
                color=0x888888,
                x=10,
                y=self.screen_height - 20
            )
            screensaver_group.append(help_label)
            
            self.main_group.append(screensaver_group)
            self.display.root_group = self.main_group
            
            # Handle input
            press_duration = self._handle_button_input()
            
            if press_duration > 1.0:  # Long press - select option
                if screensaver_selected == 0:  # Toggle enabled
                    self.screensaver_enabled = not self.screensaver_enabled
                    self.settings["SCREENSAVER_ENABLED"] = self.screensaver_enabled
                    save_settings(self.settings)
                    
                elif screensaver_selected == 1:  # Change timeout
                    timeouts = [60, 120, 300, 600, 900, 1800]  # 1min, 2min, 5min, 10min, 15min, 30min
                    current_index = 0
                    for i, timeout in enumerate(timeouts):
                        if timeout >= self.screensaver_timeout:
                            current_index = i
                            break
                    
                    next_index = (current_index + 1) % len(timeouts)
                    self.screensaver_timeout = timeouts[next_index]
                    self.settings["SCREENSAVER_TIMEOUT"] = self.screensaver_timeout
                    save_settings(self.settings)
                    
                elif screensaver_selected == 2:  # Change type
                    types = ["trippy", "constellation"]
                    current_index = types.index(self.screensaver_type) if self.screensaver_type in types else 0
                    next_index = (current_index + 1) % len(types)
                    self.screensaver_type = types[next_index]
                    self.settings["SCREENSAVER_TYPE"] = self.screensaver_type
                    save_settings(self.settings)
                    
                elif screensaver_selected == 3:  # Test screensaver
                    self.show_message("Starting screensaver test...", color=0x00FFFF, duration=1)
                    self._start_screensaver()
                    
                elif screensaver_selected == 4:  # Back
                    break
                    
            elif press_duration > 0.05:  # Short press - navigate
                screensaver_selected = (screensaver_selected + 1) % len(screensaver_options)
            
            # Reset screensaver timer on any activity
            self._reset_screensaver_timer()



    def _toggle_app_status(self):
        """Toggle enabled/disabled status of apps"""
        if not self.apps:
            self.show_message("No apps to configure", color=0xFF8000, duration=2)
            return
            
        app_selected = 0
        
        while True:
            # Show app list with status
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.update_all()
            toggle_group = displayio.Group()
            
            title = label.Label(
                terminalio.FONT,
                text="Toggle App Status",
                color=0xFF8000,
                x=10,
                y=MENU_START_Y + 10
            )
            toggle_group.append(title)
            
            for i, app in enumerate(self.apps[:10]):  # Show first 10 apps
                prefix = ">" if i == app_selected else " "
                status = "ON" if app.get("enabled", True) else "OFF"
                color = 0x00FF00 if i == app_selected else (0xFFFFFF if app.get("enabled", True) else 0x888888)
                
                text = f"{prefix} {app['name'][:15]} [{status}]"
                app_label = label.Label(
                    terminalio.FONT,
                    text=text,
                    color=color,
                    x=10,
                    y=MENU_START_Y + 30 + i * 15
                )
                toggle_group.append(app_label)
            
            help_label = label.Label(
                terminalio.FONT,
                text="Long: Toggle  Short: Next  Hold: Exit",
                color=0x888888,
                x=10,
                y=self.screen_height - 20
            )
            toggle_group.append(help_label)
            
            self.main_group.append(toggle_group)
            self.display.root_group = self.main_group
            
            press_duration = self._handle_button_input()
            
            if press_duration > 2.0:  # Very long press - exit
                break
            elif press_duration > 1.0:  # Long press - toggle
                if app_selected < len(self.apps):
                    self.apps[app_selected]["enabled"] = not self.apps[app_selected].get("enabled", True)
                    self._save_apps_config()
            elif press_duration > 0.05:  # Short press - navigate
                app_selected = (app_selected + 1) % min(len(self.apps), 10)

    def _view_app_details_menu(self):
        """Show detailed view of apps"""
        if not self.apps:
            self.show_message("No apps available", color=0xFF8000, duration=2)
            return
            
        app_selected = 0
        
        while True:
            if app_selected < len(self.apps):
                self.show_app_details(self.apps[app_selected])
            
            press_duration = self._handle_button_input()
            
            if press_duration > 2.0:  # Very long press - exit
                break
            elif press_duration > 1.0:  # Long press - run app
                if app_selected < len(self.apps):
                    self.run_app(self.apps[app_selected])
                    break
            elif press_duration > 0.05:  # Short press - next app
                app_selected = (app_selected + 1) % len(self.apps)

    def _show_system_info(self):
        """Show system information"""
        try:
            gc.collect()
            free_mem = gc.mem_free()
            total_apps = len(self.apps)
            enabled_apps = len([app for app in self.apps if app.get("enabled", True)])
            
            info = f"System Information\n\n"
            info += f"Free Memory: {free_mem} bytes\n"
            info += f"Total Apps: {total_apps}\n"
            info += f"Enabled Apps: {enabled_apps}\n"
            info += f"WiFi: {'Available' if WIFI_AVAILABLE else 'Not Available'}\n"
            info += f"BLE: {'Available' if BLE_AVAILABLE else 'Not Available'}\n"
            info += f"Display: {self.screen_width}x{self.screen_height}\n\n"
            info += "Press button to return"
            
            self.show_message(info, color=0x00FFFF)
            self._wait_for_button_press()
            
        except Exception as e:
            self.show_message(f"Error getting system info:\n{str(e)}", color=0xFF0000)
            time.sleep(2)

    def _handle_button_input(self):
        """Handle button input and return press duration"""
        if not self.has_button:
            time.sleep(0.1)
            return 0
            
        # Wait for button press
        while self.button.value:
            time.sleep(0.01)
        
        # Measure press duration
        press_start = time.monotonic()
        while not self.button.value:
            time.sleep(0.01)
        
        return time.monotonic() - press_start

    def _wait_for_button_press(self):
        """Wait for button press"""
        if not self.has_button:
            time.sleep(1)
            return
            
        while self.button.value:
            time.sleep(0.01)

    def _wait_for_button_release(self):
        """Wait for button release"""
        if not self.has_button:
            return
            
        while not self.button.value:
            time.sleep(0.01)

    def main_loop(self):
        """Main application loop"""
        self.status_bar.set_status("Ready")
        self.draw_menu()
        
        last_status_update = time.monotonic()
        
        while True:
            try:
                # Check for screensaver timeout
                if self._check_screensaver_timeout() and not self.screensaver_active:
                    self._start_screensaver()
                    continue  # Skip other processing while screensaver is active
                
                # Skip input handling if screensaver is active
                if self.screensaver_active:
                    time.sleep(0.1)
                    continue
                
                # Update status bar periodically
                if time.monotonic() - last_status_update > 5:
                    self.status_bar.update_all()
                    last_status_update = time.monotonic()
                
                if self.has_button:
                    press_duration = self._handle_button_input()
                    
                    if press_duration > 0:  # Any button press resets screensaver timer
                        self._reset_screensaver_timer()
                    
                    if press_duration > 3.0:  # Very long press - settings menu
                        self.show_settings_menu()
                        self.draw_menu()
                    elif press_duration > 1.0:  # Long press - run app
                        enabled_apps = [app for app in self.apps if app.get("enabled", True)]
                        if enabled_apps and self.selected < len(enabled_apps):
                            self.run_app(enabled_apps[self.selected])
                            self.draw_menu()
                    elif press_duration > 0.05:  # Short press - navigate
                        enabled_apps = [app for app in self.apps if app.get("enabled", True)]
                        if enabled_apps:
                            self.selected = (self.selected + 1) % len(enabled_apps)
                            self.draw_menu()
                else:
                    # Console mode - basic functionality
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                print("App Loader interrupted")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                self.show_message(f"System Error:\n{str(e)}", color=0xFF0000, duration=3)
                self.draw_menu()
                self._reset_screensaver_timer()  # Reset on error too

    # Update the _handle_button_input method to reset screensaver timer
    def _handle_button_input(self):
        """Handle button input and return press duration"""
        if not self.has_button:
            time.sleep(0.1)
            return 0
            
        # Wait for button press
        while self.button.value:
            time.sleep(0.01)
        
        # Reset screensaver timer on button press
        self._reset_screensaver_timer()
        
        # Measure press duration
        press_start = time.monotonic()
        while not self.button.value:
            time.sleep(0.01)
        
        return time.monotonic() - press_start


def main():
    """Main entry point"""
    try:
        print("Starting App Loader...")
        loader = AppLoader()
        loader.main_loop()
    except Exception as e:
        print(f"Fatal error: {e}")
        # Try to show error on display if possible
        try:
            display = board.DISPLAY
            group = displayio.Group()
            error_label = label.Label(
                terminalio.FONT,
                text=f"Fatal Error:\n{str(e)[:100]}",
                color=0xFF0000,
                x=10,
                y=30
            )
            group.append(error_label)
            display.root_group = group
        except Exception:
            pass
        
        # Keep system alive for debugging
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()

