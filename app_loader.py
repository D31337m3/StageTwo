import board
import displayio
import terminalio
from adafruit_display_text import label
import digitalio
import supervisor
import time
import rtc
import wifi
import os
import gc
import json
import microcontroller
# Try to import BLE if available
try:
    import _bleio
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False

# Status bar constants
STATUS_BAR_HEIGHT = 15
SCREEN_WIDTH = board.DISPLAY.width
SCREEN_HEIGHT = board.DISPLAY.height
MENU_START_Y = STATUS_BAR_HEIGHT + 10
 
# App configuration
APPS_CONFIG_FILE = "/system/apps.json"

# Default apps if config file doesn't exist
DEFAULT_APPS = [
    {"name": "Serial Monitor", "file": "/system/serialmon_esp32.py", "description": "Seriar/Uart Monitor"},
    {"name": "File Manager", "file": "/filemgr.py", "description": "Browse and manage files"},
    {"name": "Network Tools", "file": "/wifi_config.py", "description": "WiFi and network utilities"},
    {"name": "Settings", "file": "/settings.py", "description": "System configuration"},
    {"name": "Terminal", "file": "/terminal.py", "description": "Command line interface"},
    {"name": "Recovery Mode", "file": "/recovery.py", "description": "System recovery tools"},
    {"name": "Boot Menu", "file": "/bootmenu.py", "description": "Boot options menu"},
    {"name": "Reboot System", "file": "REBOOT", "description": "Restart the device"},
]

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
            terminalio.FONT, text="", color=0x00FF00, x=5, y=6
        )
        self.group.append(self.wifi_label)
        
        # BLE status icon (left side, next to WiFi)
        self.ble_label = label.Label(
            terminalio.FONT, text="", color=0x0080FF, x=25, y=6
        )
        self.group.append(self.ble_label)
        
        # System status (center-left)
        self.status_label = label.Label(
            terminalio.FONT, text="Ready", color=0xFFFFFF, x=50, y=6
        )
        self.group.append(self.status_label)
        
        # Time display (right side)
        self.time_label = label.Label(
            terminalio.FONT, text="--:--", color=0xFFFF00, x=SCREEN_WIDTH - 50, y=6
        )
        self.group.append(self.time_label)
        
        # Memory usage (far right)
        self.memory_label = label.Label(
            terminalio.FONT, text="", color=0xFF8000, x=SCREEN_WIDTH - 80, y=6
        )
        self.group.append(self.memory_label)
        
        self.display_group.append(self.group)
        
    def update_wifi_status(self):
        """Update WiFi status icon"""
        try:
            if wifi.radio.connected:
                # Show signal strength with different colors
                rssi = wifi.radio.ap_info.rssi if wifi.radio.ap_info else -100
                if rssi > -50:
                    self.wifi_label.text = "WiFi"
                    self.wifi_label.color = 0x00FF00  # Green - excellent
                elif rssi > -70:
                    self.wifi_label.text = "WiFi"
                    self.wifi_label.color = 0xFFFF00  # Yellow - good
                else:
                    self.wifi_label.text = "WiFi"
                    self.wifi_label.color = 0xFF8000  # Orange - weak
            else:
                self.wifi_label.text = ""
        except:
            self.wifi_label.text = ""
            
    def update_ble_status(self):
        """Update BLE status icon"""
        if not BLE_AVAILABLE:
            self.ble_label.text = ""
            return
            
        try:
            # Check if BLE is enabled/active
            if _bleio.adapter.enabled:
                if _bleio.adapter.connected:
                    self.ble_label.text = "BLE"
                    self.ble_label.color = 0x00FF00  # Green - connected
                else:
                    self.ble_label.text = "BLE"
                    self.ble_label.color = 0x0080FF  # Blue - advertising/available
            else:
                self.ble_label.text = ""
        except:
            self.ble_label.text = ""
            
    def update_time(self):
        """Update time display"""
        try:
            current_time = time.localtime()
            time_str = f"{current_time.tm_hour:02d}:{current_time.tm_min:02d}"
            self.time_label.text = time_str
            
            # Adjust position based on text width
            self.time_label.x = SCREEN_WIDTH - len(time_str) * 6 - 5
        except:
            self.time_label.text = "--:--"
            
    def update_memory(self):
        """Update memory usage display"""
        try:
            gc.collect()
            free_mem = gc.mem_free()
            if free_mem < 1024:
                mem_text = f"{free_mem}B"
                color = 0xFF0000  # Red - low memory
            elif free_mem < 10240:
                mem_text = f"{free_mem//1024}K"
                color = 0xFF8000  # Orange - medium memory
            else:
                mem_text = f"{free_mem//1024}K"
                color = 0x00FF00  # Green - good memory
                
            self.memory_label.text = mem_text
            self.memory_label.color = color
            
            # Adjust position
            self.memory_label.x = SCREEN_WIDTH - len(mem_text) * 6 - 5
            self.time_label.x = self.memory_label.x - 35
        except:
            self.memory_label.text = ""
            
    def set_status(self, status_text, color=0xFFFFFF):
        """Set the status message"""
        self.status_label.text = status_text[:15]  # Limit length
        self.status_label.color = color
        
    def update_all(self):
        """Update all status bar elements"""
        self.update_wifi_status()
        self.update_ble_status()
        self.update_time()
        self.update_memory()

class AppLoader:
    def __init__(self):
        self.display = board.DISPLAY
        self.main_group = displayio.Group()
        self.display.root_group = self.main_group
        
        # Initialize status bar
        self.status_bar = StatusBar(self.main_group)
        
        # Setup button if available
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except:
            self.has_button = False
            
        # Menu state
        self.selected = 0
        self.apps = self.load_apps()
        self.menu_group = displayio.Group()
        self.main_group.append(self.menu_group)
        
        # Last update time for status bar
        self.last_status_update = 0
        self.status_update_interval = 1.0  # Update every second
        
    def load_apps(self):
        """Load app configuration from file or use defaults"""
        try:
            with open(APPS_CONFIG_FILE, 'r') as f:
                apps = json.load(f)
                self.status_bar.set_status("Apps loaded", 0x00FF00)
                return apps
        except:
            self.status_bar.set_status("Using defaults", 0xFFFF00)
            self.save_apps(DEFAULT_APPS)
            return DEFAULT_APPS
            
    def save_apps(self, apps):
        """Save app configuration to file"""
        try:
            # Ensure system directory exists
            try:
                os.mkdir("/system")
            except OSError:
                pass
                
            with open(APPS_CONFIG_FILE, 'w') as f:
                json.dump(apps, f)
        except Exception as e:
            print(f"Failed to save apps config: {e}")
            
    def draw_menu(self):
        """Draw the application menu"""
        # Clear existing menu
        while len(self.menu_group) > 0:
            self.menu_group.pop()
            
        # Title
        title = label.Label(
            terminalio.FONT, text="Application Menu:", color=0x00FFFF, 
            x=10, y=MENU_START_Y + 8, scale=1
        )
        self.menu_group.append(title)
        
        # Calculate visible items (account for screen size)
        visible_items = min(8, (SCREEN_HEIGHT - MENU_START_Y - 40) // 20)
        start_index = max(0, self.selected - visible_items // 2)
        end_index = min(len(self.apps), start_index + visible_items)
        
        # Adjust start_index if we're near the end
        if end_index - start_index < visible_items:
            start_index = max(0, end_index - visible_items)
            
        # Draw menu items
        for i in range(start_index, end_index):
            app = self.apps[i]
            y_pos = MENU_START_Y + 35 + (i - start_index) * 20
            
            # Highlight selected item
            if i == self.selected:
                # Create highlight background
                highlight_bitmap = displayio.Bitmap(SCREEN_WIDTH - 20, 18, 1)
                highlight_palette = displayio.Palette(1)
                highlight_palette[0] = 0x003366  # Dark blue highlight
                highlight_sprite = displayio.TileGrid(
                    highlight_bitmap, pixel_shader=highlight_palette, 
                    x=10, y=y_pos - 12
                )
                self.menu_group.append(highlight_sprite)
                text_color = 0xFFFF00  # Yellow for selected
            else:
                text_color = 0xFFFFFF  # White for normal
                
            # App name
            app_label = label.Label(
                terminalio.FONT, text=f"{i}: {app['name']}", 
                color=text_color, x=15, y=y_pos
            )
            self.menu_group.append(app_label)
            
            # App description (smaller, dimmer)
            if i == self.selected and 'description' in app:
                desc_text = app['description'][:40]  # Limit description length
                desc_label = label.Label(
                    terminalio.FONT, text=desc_text, 
                    color=0x888888, x=15, y=y_pos + 12
                )
                self.menu_group.append(desc_label)
                
        # Scroll indicators
        if start_index > 0:
            up_arrow = label.Label(
                terminalio.FONT, text="^ More above", 
                color=0x888888, x=SCREEN_WIDTH - 80, y=MENU_START_Y + 35
            )
            self.menu_group.append(up_arrow)
            
        if end_index < len(self.apps):
            down_arrow = label.Label(
                terminalio.FONT, text="v More below", 
                color=0x888888, x=SCREEN_WIDTH - 80, y=SCREEN_HEIGHT - 20
            )
            self.menu_group.append(down_arrow)
            
        # Instructions
        instructions = label.Label(
            terminalio.FONT, text="Use buttons or console (up/dn/itm #)", 
            color=0x00FF00, x=10, y=SCREEN_HEIGHT - 10
        )
        self.menu_group.append(instructions)
        
    def show_loading(self, app_name):
        """Show loading screen"""
        # Clear menu
        while len(self.menu_group) > 0:
            self.menu_group.pop()
            
        loading_group = displayio.Group()
        
        # Loading message
        loading_label = label.Label(
            terminalio.FONT, text=f"Loading: {app_name}", 
            color=0xFFFF00, x=10, y=SCREEN_HEIGHT // 2, scale=1
        )
        loading_group.append(loading_label)
        
        # Progress animation
        progress_label = label.Label(
            terminalio.FONT, text="Please wait...", 
            color=0xFFFFFF, x=10, y=SCREEN_HEIGHT // 2 + 30
        )
        loading_group.append(progress_label)
        
        self.menu_group.append(loading_group)
        
        # Animate loading
        for i in range(3):
            progress_label.text = "Loading" + "." * (i + 1)
            time.sleep(0.3)
            
    def run_app(self, app_index):
        """Execute selected application"""
        if app_index >= len(self.apps):
            return
            
        app = self.apps[app_index]
        app_name = app['name']
        app_file = app['file']
        
        self.status_bar.set_status(f"Loading {app_name}", 0xFFFF00)
        self.show_loading(app_name)
        
        try:
            if app_file == "REBOOT":
                self.status_bar.set_status("Rebooting...", 0xFF0000)
                time.sleep(1)
                microcontroller.reset()
                
            else:
                # Check if file exists
                try:
                    with open(app_file, 'r') as f:
                        pass  # Just check if file can be opened
                except OSError:
                    self.status_bar.set_status("App not found!", 0xFF0000)
                    time.sleep(2)
                    return
                    
                # Execute the application
                if app_file.endswith('.py'):
                    supervisor.set_next_code_file(app_file)
                    supervisor.reload()
                else:
                    # Try to execute directly
                    exec(open(app_file).read())
                    
        except Exception as e:
            self.status_bar.set_status(f"Error: {e}", 0xFF0000)
            time.sleep(2)
        except:
            time.sleep(2)
            microcontroller.reset()

    def main_loop(self):
        """Main menu loop for app selection and launching"""
        self.draw_menu()
        last_button = self.button.value if self.has_button else True
        prev_selected = self.selected
        start_time = time.monotonic()
        timeout = 30  # Optional: auto-exit after 30s inactivity

        while True:
            # Update status bar every second
            now = time.monotonic()
            if now - self.last_status_update > self.status_update_interval:
                self.status_bar.update_all()
                self.last_status_update = now

            input_received = False

            # Serial/console input
            if supervisor.runtime.serial_bytes_available:
                try:
                    cmd = input().strip().lower()
                    input_received = True
                    if cmd in ["up", "u"]:
                        self.selected = (self.selected - 1) % len(self.apps)
                    elif cmd in ["down", "d"]:
                        self.selected = (self.selected + 1) % len(self.apps)
                    elif cmd in ["select", "s", "enter"]:
                        self.run_app(self.selected)
                        self.draw_menu()
                    elif cmd.isdigit() and 0 <= int(cmd) < len(self.apps):
                        self.selected = int(cmd)
                    else:
                        print("Commands: up/down/select or 0-9")
                except Exception as e:
                    print(f"Input error: {e}")

            # Button navigation
            if self.has_button:
                if not self.button.value and last_button:
                    press_time = time.monotonic()
                    while not self.button.value:
                        if time.monotonic() - press_time > 1.0:
                            # Long press: select
                            self.run_app(self.selected)
                            self.draw_menu()
                            break
                        time.sleep(0.01)
                    else:
                        # Short press: next item
                        self.selected = (self.selected + 1) % len(self.apps)
                        input_received = True
                last_button = self.button.value

            # Redraw menu if selection changed
            if self.selected != prev_selected:
                self.draw_menu()
                prev_selected = self.selected

            # Reset inactivity timer on input
            if input_received:
                start_time = time.monotonic()

            # Optional: auto-exit after timeout
            if time.monotonic() - start_time > timeout:
                self.status_bar.set_status("Timeout", 0xFF0000)
                time.sleep(1)
                break

            time.sleep(0.02)

# Entry point
if __name__ == "__main__":
    loader = AppLoader()
    loader.main_loop()
