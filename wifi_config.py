import board
import wifi
import time
import os
import digitalio
import displayio
import terminalio
from adafruit_display_text import label
import microcontroller
import gc
import supervisor

# Display constants
SCREEN_WIDTH = board.DISPLAY.width
SCREEN_HEIGHT = board.DISPLAY.height
STATUS_BAR_HEIGHT = 20
MENU_START_Y = STATUS_BAR_HEIGHT + 10

SETTINGS_PATH = "/settings.toml"
MAX_NETWORKS = 50
MAX_PASSWORD_LEN = 63  # WPA2 max length

# Character groups for password entry
CHAR_GROUPS = [
    "abcdefghijklmnopqrstuvwxyz",  # Lowercase
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # Uppercase  
    "0123456789!@#$%^&*()-_=+[]{};:',.<>/?\\|\"`~ "  # Numbers + symbols + space
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
        
        # WiFi status
        self.wifi_label = label.Label(
            terminalio.FONT, text="WiFi Scan", color=0x00FFFF, x=5, y=12
        )
        self.group.append(self.wifi_label)
        
        # Status message
        self.status_label = label.Label(
            terminalio.FONT, text="Ready", color=0xFFFFFF, x=80, y=12
        )
        self.group.append(self.status_label)
        
        # Time display
        self.time_label = label.Label(
            terminalio.FONT, text="--:-- --", color=0xFFFF00, x=SCREEN_WIDTH - 70, y=12
        )
        self.group.append(self.time_label)
        
        self.display_group.append(self.group)
    
    def update_wifi_status(self):
        """Update WiFi status display with better error handling"""
        try:
            if not hasattr(wifi, 'radio'):
                self.wifi_label.text = "No WiFi"
                self.wifi_label.color = 0x888888
                return
            
            if not hasattr(wifi.radio, 'connected'):
                self.wifi_label.text = "WiFi?"
                self.wifi_label.color = 0xFF0000
                return
                
            if wifi.radio.connected:
                rssi = -100  # Default
                try:
                    if hasattr(wifi.radio, 'ap_info') and wifi.radio.ap_info:
                        if hasattr(wifi.radio.ap_info, 'rssi'):
                            rssi = wifi.radio.ap_info.rssi
                except Exception:
                    pass
                
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
        except Exception as e:
            print(f"WiFi status error: {e}")
            self.wifi_label.text = "WiFi?"
            self.wifi_label.color = 0xFF0000

    
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
            self.time_label.x = SCREEN_WIDTH - len(time_str) * 6 - 5
        except Exception:
            self.time_label.text = "--:-- --"
    
    def set_status(self, status_text, color=0xFFFFFF):
        """Set the status message"""
        self.status_label.text = status_text[:20]
        self.status_label.color = color
    
    def update_all(self):
        """Update all status bar elements"""
        self.update_wifi_status()
        self.update_time()

def load_settings():
    """Load all settings as a dict of key: value."""
    settings = {}
    if SETTINGS_PATH in os.listdir("/"):
        try:
            with open(SETTINGS_PATH, "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        settings[key] = value
        except Exception as e:
            print(f"Error loading settings: {e}")
    return settings

def save_settings(settings):
    """Write all settings back to the file, preserving all keys."""
    try:
        with open(SETTINGS_PATH, "w") as f:
            for key, value in settings.items():
                if value.isdigit() or value in ("True", "False"):
                    f.write(f"{key} = {value}\n")
                else:
                    f.write(f'{key} = "{value}"\n')
    except Exception as e:
        print(f"Error saving settings: {e}")

def get_saved_networks():
    """Return a list of (ssid, password) tuples for all saved networks."""
    settings = load_settings()
    networks = []
    for i in range(1, MAX_NETWORKS + 1):
        s_key = f"WIFI_SSID_{i}"
        p_key = f"WIFI_PASSWORD_{i}"
        if s_key in settings and p_key in settings:
            networks.append((settings[s_key], settings[p_key]))
    return networks

def get_primary_network():
    """Return (ssid, password) for the current primary network."""
    settings = load_settings()
    return (
        settings.get("CIRCUITPY_WIFI_SSID", ""),
        settings.get("CIRCUITPY_WIFI_PASSWORD", "")
    )

def save_wifi_network(ssid, password, make_primary=True):
    """
    Save a WiFi network. If make_primary, set as CIRCUITPY_WIFI_SSID/PASSWORD.
    Preserves all other settings and avoids duplicates.
    """
    settings = load_settings()
    
    # Gather all existing networks, remove any duplicates of this SSID
    networks = []
    for i in range(1, MAX_NETWORKS + 1):
        s_key = f"WIFI_SSID_{i}"
        p_key = f"WIFI_PASSWORD_{i}"
        if s_key in settings and p_key in settings:
            if settings[s_key] != ssid:
                networks.append((settings[s_key], settings[p_key]))
    
    # Insert new/updated network at the front if primary, else append
    if make_primary:
        networks.insert(0, (ssid, password))
        settings["CIRCUITPY_WIFI_SSID"] = ssid
        settings["CIRCUITPY_WIFI_PASSWORD"] = password
    else:
        networks.append((ssid, password))
    
    # Truncate to MAX_NETWORKS
    networks = networks[:MAX_NETWORKS]
    
    # Clear old WiFi entries
    for i in range(1, MAX_NETWORKS + 1):
        settings.pop(f"WIFI_SSID_{i}", None)
        settings.pop(f"WIFI_PASSWORD_{i}", None)
    
    # Update indexed keys
    for i, (s, p) in enumerate(networks, 1):
        settings[f"WIFI_SSID_{i}"] = s
        settings[f"WIFI_PASSWORD_{i}"] = p
    
    save_settings(settings)

def rotate_primary(index):
    """
    Set the indexed network (1-based) as primary.
    Moves the selected network to the top and updates CIRCUITPY_WIFI_SSID/PASSWORD.
    """
    settings = load_settings()
    s_key = f"WIFI_SSID_{index}"
    p_key = f"WIFI_PASSWORD_{index}"
    if s_key in settings and p_key in settings:
        save_wifi_network(settings[s_key], settings[p_key], make_primary=True)

class WiFiConfigUI:
    def __init__(self):
        self.display = board.DISPLAY
        self.screen_width = self.display.width
        self.screen_height = self.display.height
        
        # Initialize button
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except Exception:
            self.has_button = False
            print("No button available - console only mode")
        
        # Initialize status bar
        self.main_group = displayio.Group()
        self.status_bar = StatusBar(self.main_group)
        
        # State variables
        self.selected = 0
        self.networks = []
        self.saved_networks = []
        self.current_mode = "main_menu"  # main_menu, scan, saved_networks, password_entry
        self.password_entry = ""
        self.password_char_group = 0  # Current character group
        self.password_char_index = 0  # Index within current group
        self.selected_ssid = ""
        
        # Load saved networks
        self.refresh_saved_networks()

    def refresh_saved_networks(self):
        """Refresh the list of saved networks"""
        self.saved_networks = get_saved_networks()

    def _wait_for_button_action(self):
        """Wait for button action and return the type"""
        if not self.has_button:
            time.sleep(0.5)
            return "short"
        
        # Wait for button press
        while self.button.value:
            time.sleep(0.01)
        
        # Button is now pressed, measure duration
        press_start = time.monotonic()
        
        # Wait for release
        while not self.button.value:
            time.sleep(0.01)
        
        press_duration = time.monotonic() - press_start
        
        # Add delay to prevent bouncing
        time.sleep(0.1)
        
        if press_duration > 3.0:
            return "very_long"  # 3+ seconds
        elif press_duration > 1.5:
            return "long"  # 1.5-3 seconds
        elif press_duration > 0.05:
            return "short"  # 0.05-1.5 seconds
        else:
            return "none"

    def show_main_menu(self):
        """Show the main WiFi configuration menu"""
        menu_options = [
            "Scan Networks",
            "Saved Networks", 
            "Current Status",
            "Exit"
        ]
        
        while self.current_mode == "main_menu":
            # Clear display but keep status bar
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.update_all()
            
            menu_group = displayio.Group()
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="WiFi Configuration",
                color=0x00FFFF,
                x=10,
                y=MENU_START_Y + 10
            )
            menu_group.append(title)
            
            # Menu options
            for i, option in enumerate(menu_options):
                prefix = ">" if i == self.selected else " "
                color = 0x00FF00 if i == self.selected else 0xFFFFFF
                
                option_label = label.Label(
                    terminalio.FONT,
                    text=f"{prefix} {option}",
                    color=color,
                    x=10,
                    y=MENU_START_Y + 35 + i * 20
                )
                menu_group.append(option_label)
            
            # Help text
            help_label = label.Label(
                terminalio.FONT,
                text="Short: Next  Long: Select",
                color=0x888888,
                x=10,
                y=self.screen_height - 20
            )
            menu_group.append(help_label)
            
            self.main_group.append(menu_group)
            self.display.root_group = self.main_group
            
            # Handle input
            action = self._wait_for_button_action()
            
            if action == "long":  # Select option
                if self.selected == 0:  # Scan Networks
                    self.current_mode = "scan"
                    self.scan_networks()
                elif self.selected == 1:  # Saved Networks
                    self.current_mode = "saved_networks"
                    self.show_saved_networks()
                elif self.selected == 2:  # Current Status
                    self.show_current_status()
                elif self.selected == 3:  # Exit
                    return
                    
            elif action == "short":  # Navigate
                self.selected = (self.selected + 1) % len(menu_options)

    def scan_networks(self):
        """Scan for WiFi networks with improved reliability and error handling"""
        self.networks = []
        self.selected = 0
        
        self.status_bar.set_status("Scanning...", 0xFFFF00)
        self.show_message("Scanning for networks...\nPlease wait", 0x00FFFF)
        
        try:
            # Ensure WiFi radio is available and enabled
            if not hasattr(wifi, 'radio'):
                raise Exception("WiFi radio not available")
            
            if not wifi.radio.enabled:
                wifi.radio.enabled = True
                time.sleep(2)
            
            # Disconnect if connected to get better scan results
            try:
                if hasattr(wifi.radio, 'connected') and wifi.radio.connected:
                    wifi.radio.disconnect()
                    time.sleep(1)
            except Exception:
                pass  # Ignore disconnect errors
            
            # Force garbage collection
            gc.collect()
            
            # Perform multiple scans for reliability
            found_networks = {}
            scan_attempts = 2  # Reduced from 3 to avoid timeout issues
            
            for attempt in range(scan_attempts):
                self.status_bar.set_status(f"Scan {attempt+1}/{scan_attempts}", 0xFFFF00)
                
                try:
                    # Check if scanning methods are available
                    if not hasattr(wifi.radio, 'start_scanning_networks'):
                        raise Exception("Scanning not supported")
                    
                    scan_results = wifi.radio.start_scanning_networks()
                    
                    for network in scan_results:
                        try:
                            # Safely get SSID
                            if hasattr(network, 'ssid'):
                                ssid = network.ssid
                                if isinstance(ssid, bytes):
                                    ssid = ssid.decode("utf-8", errors='ignore')
                                elif not isinstance(ssid, str):
                                    ssid = str(ssid)
                            else:
                                continue  # Skip if no SSID attribute
                            
                            # Skip empty or invalid SSIDs
                            if not ssid or not ssid.strip() or len(ssid.strip()) == 0:
                                continue
                            
                            # Safely get RSSI
                            rssi = -100  # Default weak signal
                            if hasattr(network, 'rssi'):
                                try:
                                    rssi = int(network.rssi)
                                except (ValueError, TypeError):
                                    rssi = -100
                            
                            # Keep the strongest signal for each SSID
                            if ssid not in found_networks or found_networks[ssid][1] < rssi:
                                found_networks[ssid] = (ssid, rssi)
                                
                        except Exception as e:
                            print(f"Error processing network: {e}")
                            continue
                    
                    # Stop scanning
                    try:
                        if hasattr(wifi.radio, 'stop_scanning_networks'):
                            wifi.radio.stop_scanning_networks()
                    except Exception:
                        pass
                    
                    time.sleep(0.5)  # Brief pause between scans
                    
                except Exception as e:
                    print(f"Scan attempt {attempt+1} failed: {e}")
                    try:
                        if hasattr(wifi.radio, 'stop_scanning_networks'):
                            wifi.radio.stop_scanning_networks()
                    except Exception:
                        pass
                    time.sleep(1)
            
            # Sort networks by signal strength (strongest first)
            self.networks = sorted(found_networks.values(), key=lambda x: x[1], reverse=True)
            
            if self.networks:
                self.status_bar.set_status(f"Found {len(self.networks)} networks", 0x00FF00)
                self.show_network_list()
            else:
                self.status_bar.set_status("No networks found", 0xFF0000)
                self.show_message("No networks found.\nLong press to retry\nShort press for menu", 0xFF0000)
                
                action = self._wait_for_button_action()
                if action == "long":
                    self.scan_networks()  # Retry scan
                else:
                    self.current_mode = "main_menu"
                    self.selected = 0
                    
        except Exception as e:
            error_msg = str(e)
            print(f"Scan failed: {error_msg}")
            self.status_bar.set_status("Scan failed", 0xFF0000)
            self.show_message(f"Scan failed:\n{error_msg[:30]}\nLong: Retry  Short: Menu", 0xFF0000)
            
            action = self._wait_for_button_action()
            if action == "long":
                self.scan_networks()  # Retry scan
            else:
                self.current_mode = "main_menu"
                self.selected = 0

    
    def show_network_list(self):
        """Show scanned networks list"""
        while self.current_mode == "scan":
            # Clear display but keep status bar
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.update_all()
            
            network_group = displayio.Group()
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="Select Network",
                color=0x00FFFF,
                x=10,
                y=MENU_START_Y + 10
            )
            network_group.append(title)
            
            # Network list
            if self.networks:
                # Calculate visible networks
                list_start_y = MENU_START_Y + 30
                max_visible = (self.screen_height - list_start_y - 50) // 15
                start_idx = max(0, self.selected - max_visible // 2)
                end_idx = min(len(self.networks), start_idx + max_visible)
                
                if end_idx - start_idx < max_visible and len(self.networks) > max_visible:
                    start_idx = max(0, end_idx - max_visible)
                
                for i in range(start_idx, end_idx):
                    ssid, rssi = self.networks[i]
                    prefix = ">" if i == self.selected else " "
                    
                    # Color based on signal strength
                    if i == self.selected:
                        color = 0x00FF00  # Green for selected
                    elif rssi > -50:
                        color = 0x00FF00  # Green - excellent
                    elif rssi > -70:
                        color = 0xFFFF00  # Yellow - good
                    else:
                        color = 0xFF8000  # Orange - weak
                    
                    # Check if this network is saved
                    is_saved = any(saved_ssid == ssid for saved_ssid, _ in self.saved_networks)
                    saved_indicator = "*" if is_saved else " "
                    
                    # Format display text
                    display_text = f"{prefix}{saved_indicator}{ssid[:18]} ({rssi}dBm)"
                    
                    network_label = label.Label(
                        terminalio.FONT,
                        text=display_text,
                        color=color,
                        x=10,
                        y=list_start_y + (i - start_idx) * 15
                    )
                    network_group.append(network_label)
            
            # Status and help
            status_text = f"{self.selected+1}/{len(self.networks)}" if self.networks else "0/0"
            status_label = label.Label(
                terminalio.FONT,
                text=status_text,
                color=0x888888,
                x=10,
                y=self.screen_height - 35
            )
            network_group.append(status_label)
            
            help_label = label.Label(
                terminalio.FONT,
                text="Short: Next  Long: Connect  Hold: Menu",
                color=0x888888,
                x=10,
                y=self.screen_height - 20
            )
            network_group.append(help_label)
            
            # Legend
            legend_label = label.Label(
                terminalio.FONT,
                text="* = Saved network",
                color=0x888888,
                x=self.screen_width - 100,
                y=self.screen_height - 35
            )
            network_group.append(legend_label)
            
            self.main_group.append(network_group)
            self.display.root_group = self.main_group
            
            # Handle input
            action = self._wait_for_button_action()
            
            if action == "very_long":  # Very long press - back to main menu
                self.current_mode = "main_menu"
                self.selected = 0
                
            elif action == "long":  # Long press - connect to network
                if self.networks and self.selected < len(self.networks):
                    ssid, _ = self.networks[self.selected]
                    self.selected_ssid = ssid
                    
                    # Check if we have saved password
                    saved_password = None
                    for saved_ssid, saved_pass in self.saved_networks:
                        if saved_ssid == ssid:
                            saved_password = saved_pass
                            break
                    
                    if saved_password:
                        # Try connecting with saved password
                        if self.try_connect(ssid, saved_password):
                            save_wifi_network(ssid, saved_password, make_primary=True)
                            self.show_message("Connected successfully!\nPress button to continue", 0x00FF00)
                            self._wait_for_button_action()
                            self.current_mode = "main_menu"
                            self.selected = 0
                        else:
                            # Saved password failed, enter new one
                            self.current_mode = "password_entry"
                            self.enter_password()
                    else:
                        # No saved password, enter new one
                        self.current_mode = "password_entry"
                        self.enter_password()
                        
            elif action == "short":  # Short press - navigate
                if self.networks:
                    self.selected = (self.selected + 1) % len(self.networks)

    def show_saved_networks(self):
        """Show saved networks management"""
        self.refresh_saved_networks()
        saved_selected = 0
        
        while self.current_mode == "saved_networks":
            # Clear display but keep status bar
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.update_all()
            
            saved_group = displayio.Group()
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="Saved Networks",
                color=0x00FFFF,
                x=10,
                y=MENU_START_Y + 10
            )
            saved_group.append(title)
            
            if not self.saved_networks:
                no_networks_label = label.Label(
                    terminalio.FONT,
                    text="No saved networks",
                    color=0xFF8000,
                    x=10,
                    y=MENU_START_Y + 35
                )
                saved_group.append(no_networks_label)
            else:
                # Get current primary network
                primary_ssid, _ = get_primary_network()
                
                # Show saved networks
                list_start_y = MENU_START_Y + 35
                max_visible = (self.screen_height - list_start_y - 50) // 15
                start_idx = max(0, saved_selected - max_visible // 2)
                end_idx = min(len(self.saved_networks), start_idx + max_visible)
                
                if end_idx - start_idx < max_visible and len(self.saved_networks) > max_visible:
                    start_idx = max(0, end_idx - max_visible)
                
                for i in range(start_idx, end_idx):
                    ssid, _ = self.saved_networks[i]
                    prefix = ">" if i == saved_selected else " "
                    
                    # Highlight current primary network
                    if ssid == primary_ssid:
                        color = 0x00FF00 if i == saved_selected else 0x00FF00
                        primary_indicator = "* "
                    else:
                        color = 0x00FF00 if i == saved_selected else 0xFFFFFF
                        primary_indicator = "  "
                    
                    display_text = f"{prefix}{primary_indicator}{ssid[:20]}"
                    
                    network_label = label.Label(
                        terminalio.FONT,
                        text=display_text,
                        color=color,
                        x=10,
                        y=list_start_y + (i - start_idx) * 15
                    )
                    saved_group.append(network_label)
            
            # Help text
            if self.saved_networks:
                help_text = "Short: Next  Long: Connect  Hold: Menu"
                status_text = f"{saved_selected+1}/{len(self.saved_networks)}"
            else:
                help_text = "Hold: Back to menu"
                status_text = "0/0"
            
            status_label = label.Label(
                terminalio.FONT,
                text=status_text,
                color=0x888888,
                x=10,
                y=self.screen_height - 35
            )
            saved_group.append(status_label)
            
            help_label = label.Label(
                terminalio.FONT,
                text=help_text,
                color=0x888888,
                x=10,
                y=self.screen_height - 20
            )
            saved_group.append(help_label)
            
            # Legend
            if self.saved_networks:
                legend_label = label.Label(
                    terminalio.FONT,
                    text="* = Primary network",
                    color=0x888888,
                    x=self.screen_width - 120,
                    y=self.screen_height - 35
                )
                saved_group.append(legend_label)
            
            self.main_group.append(saved_group)
            self.display.root_group = self.main_group
            
            # Handle input
            action = self._wait_for_button_action()
            
            if action == "very_long":  # Very long press - back to main menu
                self.current_mode = "main_menu"
                self.selected = 0
                
            elif action == "long" and self.saved_networks:  # Long press - connect
                if saved_selected < len(self.saved_networks):
                    ssid, password = self.saved_networks[saved_selected]
                    
                    if self.try_connect(ssid, password):
                        # Make this the primary network
                        save_wifi_network(ssid, password, make_primary=True)
                        self.show_message("Connected successfully!\nNow primary network\nPress button to continue", 0x00FF00)
                        self._wait_for_button_action()
                        self.refresh_saved_networks()  # Refresh to show new primary
                    else:
                        self.show_message("Connection failed!\nPress button to continue", 0xFF0000)
                        self._wait_for_button_action()
                        
            elif action == "short" and self.saved_networks:  # Short press - navigate
                saved_selected = (saved_selected + 1) % len(self.saved_networks)

    def enter_password(self):
        """Enhanced password entry with character groups"""
        self.password_entry = ""
        self.password_char_group = 0
        self.password_char_index = 0
        
        while self.current_mode == "password_entry":
            # Clear display but keep status bar
            while len(self.main_group) > 1:
                self.main_group.pop()
            
            self.status_bar.set_status("Password Entry", 0xFFFF00)
            
            password_group = displayio.Group()
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="Enter Password",
                color=0x00FFFF,
                x=10,
                y=MENU_START_Y + 10
            )
            password_group.append(title)
            
            # Network name
            network_label = label.Label(
                terminalio.FONT,
                text=f"Network: {self.selected_ssid[:20]}",
                color=0xFFFFFF,
                x=10,
                y=MENU_START_Y + 30
            )
            password_group.append(network_label)
            
            # Current password (masked)
            display_password = "*" * len(self.password_entry)
            if len(display_password) > 25:
                display_password = "..." + display_password[-22:]
            
            # Add current character being selected
            current_char = CHAR_GROUPS[self.password_char_group][self.password_char_index]
            display_password += f"[{current_char}]"
            
            password_label = label.Label(
                terminalio.FONT,
                text=f"Pass: {display_password}",
                color=0x00FF00,
                x=10,
                y=MENU_START_Y + 50
            )
            password_group.append(password_label)
            
            # Character group info
            group_names = ["Lowercase", "Uppercase", "Numbers+Symbols"]
            group_label = label.Label(
                terminalio.FONT,
                text=f"Group: {group_names[self.password_char_group]}",
                color=0xFFFF00,
                x=10,
                y=MENU_START_Y + 70
            )
            password_group.append(group_label)
            
            # Current character display
            char_display = "[space]" if current_char == " " else current_char
            char_label = label.Label(
                terminalio.FONT,
                text=f"Char: '{char_display}'",
                color=0xFFFF00,
                x=10,
                y=MENU_START_Y + 90
            )
            password_group.append(char_label)
            
            # Instructions
            instructions = [
                "Short: Next char in group",
                "Long: Add char to password", 
                "Very Long: Next group",
                "Hold 5s: Finish/Connect"
            ]
            
            for i, instruction in enumerate(instructions):
                inst_label = label.Label(
                    terminalio.FONT,
                    text=instruction,
                    color=0x888888,
                    x=10,
                    y=MENU_START_Y + 115 + i * 12
                )
                password_group.append(inst_label)
            
            self.main_group.append(password_group)
            self.display.root_group = self.main_group
            
            # Handle input
            action = self._wait_for_button_action()
            
            if action == "short":  # Next character in current group
                current_group = CHAR_GROUPS[self.password_char_group]
                self.password_char_index = (self.password_char_index + 1) % len(current_group)
                
            elif action == "long":  # Add character to password
                if len(self.password_entry) < MAX_PASSWORD_LEN:
                    current_char = CHAR_GROUPS[self.password_char_group][self.password_char_index]
                    self.password_entry += current_char
                    # Reset to start of current group
                    self.password_char_index = 0
                else:
                    self.show_message("Password too long!\nPress button to continue", 0xFF0000)
                    self._wait_for_button_action()
                    
            elif action == "very_long":  # Switch to next character group
                self.password_char_group = (self.password_char_group + 1) % len(CHAR_GROUPS)
                self.password_char_index = 0
                
            elif action == "hold_5s":  # Finish password entry
                if self.password_entry:
                    # Try to connect
                    if self.try_connect(self.selected_ssid, self.password_entry):
                        save_wifi_network(self.selected_ssid, self.password_entry, make_primary=True)
                        self.show_message("Connected and saved!\nPress button to continue", 0x00FF00)
                        self._wait_for_button_action()
                        self.current_mode = "main_menu"
                        self.selected = 0
                    else:
                        self.show_message("Connection failed!\nLong: Retry  Short: Re-enter", 0xFF0000)
                        retry_action = self._wait_for_button_action()
                        if retry_action == "long":
                            # Try again with same password
                            continue
                        else:
                            # Clear password and start over
                            self.password_entry = ""
                            self.password_char_group = 0
                            self.password_char_index = 0
                else:
                    self.show_message("Password is empty!\nPress button to continue", 0xFF8000)
                    self._wait_for_button_action()

    def _wait_for_button_action(self):
        """Enhanced button handling with 5-second hold detection"""
        if not self.has_button:
            time.sleep(0.5)
            return "short"
        
        # Wait for button press
        while self.button.value:
            time.sleep(0.01)
        
        # Button is now pressed, measure duration
        press_start = time.monotonic()
        
        # Wait for release
        while not self.button.value:
            time.sleep(0.01)
        
        press_duration = time.monotonic() - press_start
        
        # Add delay to prevent bouncing
        time.sleep(0.1)
        
        if press_duration > 5.0:
            return "hold_5s"  # 5+ seconds for password finish
        elif press_duration > 3.0:
            return "very_long"  # 3-5 seconds
        elif press_duration > 1.5:
            return "long"  # 1.5-3 seconds
        elif press_duration > 0.05:
            return "short"  # 0.05-1.5 seconds
        else:
            return "none"

    def show_current_status(self):
        """Show current WiFi connection status"""
        try:
            status_text = "WiFi Status\n\n"
            
            if wifi.radio.connected:
                status_text += f"Connected: YES\n"
                status_text += f"SSID: {wifi.radio.ap_info.ssid}\n" if wifi.radio.ap_info else "SSID: Unknown\n"
                status_text += f"IP: {wifi.radio.ipv4_address}\n"
                status_text += f"Signal: {wifi.radio.ap_info.rssi}dBm\n" if wifi.radio.ap_info else "Signal: Unknown\n"
            else:
                status_text += "Connected: NO\n"
                
            # Show primary network from settings
            primary_ssid, _ = get_primary_network()
            if primary_ssid:
                status_text += f"Primary: {primary_ssid}\n"
            else:
                status_text += "Primary: Not set\n"
                
            status_text += f"Saved: {len(self.saved_networks)} networks\n\n"
            status_text += "Press button to return"
            
            self.show_message(status_text, 0x00FFFF)
            self._wait_for_button_action()
            
        except Exception as e:
            self.show_message(f"Error getting status:\n{str(e)[:30]}\nPress button to return", 0xFF0000)
            self._wait_for_button_action()

    def try_connect(self, ssid, password, max_attempts=3):
        """Try to connect to WiFi network with better error handling"""
        for attempt in range(max_attempts):
            self.status_bar.set_status(f"Connecting {attempt+1}/{max_attempts}", 0xFFFF00)
            self.show_message(f"Connecting to:\n{ssid}\n\nAttempt {attempt+1} of {max_attempts}\nPlease wait...", 0x00FFFF)
            
            try:
                # Check if WiFi radio is available
                if not hasattr(wifi, 'radio'):
                    raise Exception("WiFi radio not available")
                
                # Disconnect if already connected
                try:
                    if hasattr(wifi.radio, 'connected') and wifi.radio.connected:
                        wifi.radio.disconnect()
                        time.sleep(1)
                except Exception:
                    pass  # Ignore disconnect errors
                
                # Attempt connection
                if hasattr(wifi.radio, 'connect'):
                    wifi.radio.connect(ssid, password, timeout=15)  # Reduced timeout
                else:
                    raise Exception("Connect method not available")
                
                # Verify connection
                time.sleep(2)  # Give it time to establish
                if hasattr(wifi.radio, 'connected') and wifi.radio.connected:
                    self.status_bar.set_status("Connected!", 0x00FF00)
                    return True
                    
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(2)  # Wait before retry
        
        self.status_bar.set_status("Connection failed", 0xFF0000)
        return False


    def show_message(self, message, color=0xFFFFFF):
        """Show a message on screen"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        message_group = displayio.Group()
        lines = message.split("\n")
        
        for i, line in enumerate(lines):
            if line.strip():  # Skip empty lines
                text_label = label.Label(
                    terminalio.FONT,
                    text=line[:35],  # Limit line length
                    color=color,
                    x=10,
                    y=MENU_START_Y + 20 + i * 15
                )
                message_group.append(text_label)
        
        self.main_group.append(message_group)
        self.display.root_group = self.main_group

    def run(self):
        """Main WiFi configuration loop"""
        self.display.root_group = self.main_group
        
        # Show welcome message
        self.show_message("WiFi Configuration\nStarting...", 0x00FFFF)
        time.sleep(1)
        
        # Initialize WiFi radio
        try:
            if not wifi.radio.enabled:
                wifi.radio.enabled = True
                time.sleep(1)
        except Exception as e:
            self.show_message(f"WiFi init failed:\n{str(e)[:30]}\nPress button to continue", 0xFF0000)
            self._wait_for_button_action()
        
        # Main application loop
        while True:
            try:
                if self.current_mode == "main_menu":
                    self.show_main_menu()
                    break  # Exit when main menu exits
                    
            except KeyboardInterrupt:
                print("WiFi Config interrupted")
                break
            except Exception as e:
                print(f"Error in WiFi config: {e}")
                self.status_bar.set_status("System Error", 0xFF0000)
                self.show_message(f"System Error:\n{str(e)[:30]}\nPress button to continue", 0xFF0000)
                self._wait_for_button_action()
                self.current_mode = "main_menu"
                self.selected = 0
        
        # Clean exit
        self.show_message("WiFi Config Exiting...", 0x00FF00)
        time.sleep(1)

def main():
    """Main entry point"""
    try:
        print("Starting WiFi Configuration...")
        wifi_ui = WiFiConfigUI()
        wifi_ui.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        # Try to show error on display if possible
        try:
            display = board.DISPLAY
            group = displayio.Group()
            error_label = label.Label(
                terminalio.FONT,
                text=f"Fatal Error:\n{str(e)[:50]}",
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
