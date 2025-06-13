# WiFi configuration tool for CircuitPython devices with built-in displays
# Edits settings.toml to configure boot-time WiFi access via user-friendly UI
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

SETTINGS_PATH = "/settings.toml"
CHARSET = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{};:',.<>/?\\|\"`~"
MAX_PASSWORD_LEN = 63  # WPA2 max length

class WiFiConfigUI:
    def __init__(self):
        self.display = board.DISPLAY
        self.screen_width = self.display.width
        self.screen_height = self.display.height
        
        # Setup button
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except:
            self.has_button = False
            print("No button available - console only mode")
        
        # UI state
        self.selected = 0
        self.networks = []
        self.known_networks = {}
        self.current_screen = "scan"
        self.password_entry = ""
        self.password_char_index = 0
        self.status_message = ""
        
        # Load known networks
        self.load_known_networks()
        
        # Check WiFi capabilities
        self.check_wifi_capabilities()
        
    def check_wifi_capabilities(self):
        """Check what WiFi methods are available"""
        self.has_disconnect = hasattr(wifi.radio, 'disconnect')
        self.has_stop_scanning = hasattr(wifi.radio, 'stop_scanning_networks')
        self.has_start_scanning = hasattr(wifi.radio, 'start_scanning_networks')
        
        print(f"WiFi capabilities:")
        print(f"  - disconnect: {self.has_disconnect}")
        print(f"  - stop_scanning: {self.has_stop_scanning}")
        print(f"  - start_scanning: {self.has_start_scanning}")
        
    def safe_disconnect(self):
        """Safely disconnect from WiFi if method exists"""
        try:
            if self.has_disconnect and wifi.radio.connected:
                wifi.radio.disconnect()
                time.sleep(1)
                return True
        except Exception as e:
            print(f"Disconnect warning: {e}")
        return False
        
    def safe_stop_scanning(self):
        """Safely stop scanning if method exists"""
        try:
            if self.has_stop_scanning:
                wifi.radio.stop_scanning_networks()
                time.sleep(0.5)
                return True
        except Exception as e:
            print(f"Stop scanning warning: {e}")
        return False
    
    def load_known_networks(self):
        """Load known networks from settings.toml"""
        self.known_networks = {}
        try:
            with open(SETTINGS_PATH, "r") as f:
                current_ssid = None
                for line in f:
                    line = line.strip()
                    if line.startswith("CIRCUITPY_WIFI_SSID"):
                        # Extract SSID value
                        current_ssid = line.split("=", 1)[1].strip().strip('"\'')
                    elif line.startswith("CIRCUITPY_WIFI_PASSWORD") and current_ssid:
                        # Extract password value
                        password = line.split("=", 1)[1].strip().strip('"\'')
                        self.known_networks[current_ssid] = password
                        current_ssid = None
        except OSError:
            pass  # File doesn't exist yet
        
        print(f"Loaded {len(self.known_networks)} known networks")
    
    def save_wifi_settings(self, ssid, password):
        """Save WiFi settings to settings.toml"""
        lines = []
        
        # Read existing file and filter out WiFi settings
        try:
            with open(SETTINGS_PATH, "r") as f:
                skip_next = False
                for line in f:
                    if line.strip().startswith("CIRCUITPY_WIFI_SSID"):
                        skip_next = True
                        continue
                    elif line.strip().startswith("CIRCUITPY_WIFI_PASSWORD") and skip_next:
                        skip_next = False
                        continue
                    else:
                        lines.append(line)
        except OSError:
            pass  # File doesn't exist
        
        # Add new WiFi settings
        lines.append(f'CIRCUITPY_WIFI_SSID = "{ssid}"\n')
        lines.append(f'CIRCUITPY_WIFI_PASSWORD = "{password}"\n')
        
        # Write back to file
        with open(SETTINGS_PATH, "w") as f:
            f.writelines(lines)
        
        # Update known networks
        self.known_networks[ssid] = password
        print(f"WiFi settings saved for {ssid}")
    
    def scan_networks(self, max_attempts=3):
        """Scan for WiFi networks with improved compatibility"""
        self.networks = []
        
        for attempt in range(max_attempts):
            self.show_scan_screen(f"Scanning... ({attempt + 1}/{max_attempts})")
            print(f"Scan attempt {attempt + 1}/{max_attempts}")
            
            try:
                # Ensure WiFi is enabled
                if not wifi.radio.enabled:
                    print("Enabling WiFi radio...")
                    wifi.radio.enabled = True
                    time.sleep(3)  # Give more time for radio to initialize
                
                print(f"WiFi radio enabled: {wifi.radio.enabled}")
                print(f"WiFi radio connected: {wifi.radio.connected}")
                
                # Try to disconnect if connected (if method exists)
                if wifi.radio.connected:
                    print("Currently connected, attempting disconnect...")
                    self.safe_disconnect()
                
                # Stop any existing scan
                print("Stopping any existing scan...")
                self.safe_stop_scanning()
                
                # Clear memory
                gc.collect()
                
                # Start scanning
                print("Starting network scan...")
                found_networks = {}  # Use dict to avoid duplicates by SSID
                scan_timeout = time.monotonic() + 20  # Increased timeout
                networks_processed = 0
                
                try:
                    if self.has_start_scanning:
                        scan_iterator = wifi.radio.start_scanning_networks()
                    else:
                        # Fallback - try direct scan if available
                        scan_iterator = wifi.radio.scan_networks()
                    
                    for network in scan_iterator:
                        current_time = time.monotonic()
                        if current_time > scan_timeout:
                            print("Scan timeout reached")
                            break
                        
                        networks_processed += 1
                        if networks_processed % 10 == 0:
                            print(f"Processed {networks_processed} networks...")
                        
                        try:
                            # Get network properties
                            if hasattr(network, 'ssid'):
                                if isinstance(network.ssid, bytes):
                                    ssid = network.ssid.decode('utf-8', errors='ignore')
                                elif isinstance(network.ssid, str):
                                    ssid = network.ssid
                                else:
                                    ssid = str(network.ssid)
                            else:
                                continue  # Skip if no SSID
                            
                            # Skip empty/invalid SSIDs
                            if not ssid or not ssid.strip():
                                continue
                            
                            # Get signal strength
                            rssi = getattr(network, 'rssi', -100)
                            
                            # Get channel
                            channel = getattr(network, 'channel', 0)
                            
                            # Store network (dict automatically handles duplicates)
                            if ssid not in found_networks or found_networks[ssid][1] < rssi:
                                found_networks[ssid] = (ssid, rssi, channel)
                                
                                # Show progress
                                if len(found_networks) <= 10:
                                    print(f"  Found: {ssid} ({rssi}dBm, Ch{channel})")
                            
                        except Exception as e:
                            print(f"Error processing network {networks_processed}: {e}")
                            continue
                        
                        # Update display periodically
                        if len(found_networks) % 5 == 0:
                            self.show_scan_screen(f"Found {len(found_networks)} networks...")
                        
                        # Small delay to prevent overwhelming
                        time.sleep(0.05)
                
                except Exception as e:
                    print(f"Scan iteration error: {e}")
                    # Try alternative scanning method
                    try:
                        print("Trying alternative scan method...")
                        # Some CircuitPython versions have different scan methods
                        if hasattr(wifi.radio, 'scan'):
                            for network in wifi.radio.scan():
                                try:
                                    ssid = network.ssid.decode('utf-8', errors='ignore') if isinstance(network.ssid, bytes) else str(network.ssid)
                                    if ssid and ssid.strip():
                                        rssi = getattr(network, 'rssi', -100)
                                        channel = getattr(network, 'channel', 0)
                                        found_networks[ssid] = (ssid, rssi, channel)
                                except:
                                    continue
                    except Exception as e2:
                        print(f"Alternative scan also failed: {e2}")
                
                # Convert to sorted list
                if found_networks:
                    self.networks = sorted(list(found_networks.values()), key=lambda x: x[1], reverse=True)
                    print(f"Scan successful: {len(self.networks)} unique networks found")
                else:
                    print("No networks found in this attempt")
                
            except Exception as e:
                print(f"Scan attempt {attempt + 1} failed: {e}")
                self.show_scan_screen(f"Scan failed: {str(e)[:30]}")
                time.sleep(2)
            
            finally:
                # Always try to stop scanning
                self.safe_stop_scanning()
                gc.collect()
            
            # If we found networks, break
            if self.networks:
                break
            
            if attempt < max_attempts - 1:
                print("Waiting before retry...")
                time.sleep(3)
        
        print(f"Final scan result: {len(self.networks)} networks found")
        if self.networks:
            print("Networks found:")
            for i, (ssid, rssi, channel) in enumerate(self.networks[:10]):  # Show first 10
                print(f"  {i+1}. {ssid} ({rssi}dBm, Ch{channel})")
        
        return len(self.networks) > 0
    
    def show_scan_screen(self, message="Scanning for networks..."):
        """Display scanning screen"""
        group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, text="WiFi Scanner", color=0x00FFFF,
            x=10, y=20, scale=2
        )
        group.append(title)
        
        # Status message
        status = label.Label(
            terminalio.FONT, text=message, color=0xFFFFFF,
            x=10, y=50
        )
        group.append(status)
        
        # WiFi status
        wifi_status = f"Radio: {'ON' if wifi.radio.enabled else 'OFF'}"
        if wifi.radio.connected:
            wifi_status += " (Connected)"
        
        status_label = label.Label(
            terminalio.FONT, text=wifi_status, color=0x00FF00 if wifi.radio.enabled else 0xFF0000,
            x=10, y=80
        )
        group.append(status_label)
        
        # Instructions
        if self.has_button:
            instructions = label.Label(
                terminalio.FONT, text="Please wait...", color=0x888888,
                x=10, y=self.screen_height - 20
            )
        else:
            instructions = label.Label(
                terminalio.FONT, text="Console mode - check serial output", color=0x888888,
                x=10, y=self.screen_height - 20
            )
        group.append(instructions)
        
        self.display.root_group = group
        time.sleep(0.1)  # Brief pause for display update
    
    def show_network_list(self):
        """Display list of found networks"""
        group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, text="Select Network", color=0x00FFFF,
            x=10, y=15, scale=2
        )
        group.append(title)
        
        # Calculate visible networks (account for screen size)
        max_visible = min(8, (self.screen_height - 80) // 20)
        start_idx = max(0, self.selected - max_visible // 2)
        end_idx = min(len(self.networks), start_idx + max_visible)
        
        # Adjust start if we're near the end
        if end_idx - start_idx < max_visible and len(self.networks) > max_visible:
            start_idx = max(0, end_idx - max_visible)
        
        # Display networks
        for i in range(start_idx, end_idx):
            ssid, rssi, channel = self.networks[i]
            y_pos = 40 + (i - start_idx) * 20
            
            # Highlight selected network
            if i == self.selected:
                # Background highlight
                highlight_bitmap = displayio.Bitmap(self.screen_width - 20, 18, 1)
                highlight_palette = displayio.Palette(1)
                highlight_palette[0] = 0x003366
                highlight_tile = displayio.TileGrid(
                    highlight_bitmap, pixel_shader=highlight_palette,
                    x=10, y=y_pos - 8
                )
                group.append(highlight_tile)
                text_color = 0xFFFF00  # Yellow for selected
            else:
                text_color = 0x00FF00 if ssid in self.known_networks else 0xFFFFFF
            
            # Network info
            display_ssid = ssid[:20] if len(ssid) > 20 else ssid
            signal_bars = "●" * max(1, min(4, (rssi + 100) // 15))
            
            net_label = label.Label(
                terminalio.FONT, 
                text=f"{display_ssid} {signal_bars}",
                color=text_color, x=15, y=y_pos
            )
            group.append(net_label)
            
            # Show "saved" indicator
            if ssid in self.known_networks:
                saved_label = label.Label(terminalio.FONT, text="*", color=0x00FF00, x=self.screen_width - 25, y=y_pos)
                group.append(saved_label)
        
        # Status bar
        status_text = f"{self.selected + 1}/{len(self.networks)}"
        if self.status_message:
            status_text += f" - {self.status_message}"
        
        status = label.Label(
            terminalio.FONT, text=status_text, color=0x888888,
            x=10, y=self.screen_height - 30
        )
        group.append(status)
        
        # Instructions
        if self.has_button:
            instructions = label.Label(
                terminalio.FONT, text="Short press: next, Long press: select",
                color=0x888888, x=10, y=self.screen_height - 15
            )
        else:
            instructions = label.Label(
                terminalio.FONT, text="Console: up/down/select or number",
                color=0x888888, x=10, y=self.screen_height - 15
            )
        group.append(instructions)
        
        self.display.root_group = group
    
    def show_password_entry(self, ssid):
        """Display password entry screen"""
        group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, text="Enter Password", color=0x00FFFF,
            x=10, y=20, scale=2
        )
        group.append(title)
        
        # SSID
        ssid_display = ssid[:25] if len(ssid) > 25 else ssid
        ssid_label = label.Label(
            terminalio.FONT, text=f"Network: {ssid_display}", color=0xFFFFFF,
            x=10, y=45
        )
        group.append(ssid_label)
        
        # Password field
        current_char = CHARSET[self.password_char_index]
        display_password = "*" * len(self.password_entry) + current_char
        
        # Limit display length
        if len(display_password) > 30:
            display_password = "..." + display_password[-27:]
        
        password_label = label.Label(
            terminalio.FONT, text=f"Password: {display_password}", color=0x00FF00,
            x=10, y=70, scale=2
        )
        group.append(password_label)
        
        # Character selection help
        char_help = label.Label(
            terminalio.FONT, text=f"Current char: '{current_char}'", color=0xFFFF00,
            x=10, y=100
        )
        group.append(char_help)
        
        # Instructions
        instructions = [
            "Short press: next character",
            "Long press (1s): add character", 
            "Very long press (3s): finish",
            "Console: type password directly"
        ]
        
        for i, instruction in enumerate(instructions):
            inst_label = label.Label(
                terminalio.FONT, text=instruction, color=0x888888,
                x=10, y=130 + i * 15
            )
            group.append(inst_label)
        
        self.display.root_group = group
    
    def show_connecting_screen(self, ssid, attempt=1, max_attempts=3):
        """Display connection attempt screen"""
        group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, text="Connecting...", color=0x00FFFF,
            x=10, y=20, scale=2
        )
        group.append(title)
        
        # Network name
        ssid_display = ssid[:25] if len(ssid) > 25 else ssid
        ssid_label = label.Label(
            terminalio.FONT, text=f"Network: {ssid_display}", color=0xFFFFFF,
            x=10, y=50
        )
        group.append(ssid_label)
        
        # Attempt counter
        attempt_label = label.Label(
            terminalio.FONT, text=f"Attempt {attempt} of {max_attempts}", color=0xFFFF00,
            x=10, y=80
        )
        group.append(attempt_label)
        
        # Animation dots
        dots = "." * (int(time.monotonic()) % 4)
        status_label = label.Label(
            terminalio.FONT, text=f"Please wait{dots}", color=0x888888,
            x=10, y=110
        )
        group.append(status_label)
        
        self.display.root_group = group
    
    def show_result_screen(self, success, ssid, message=""):
        """Display connection result"""
        group = displayio.Group()
        
        if success:
            title = label.Label(
                terminalio.FONT, text="Connected!", color=0x00FF00,
                x=10, y=20, scale=2
            )
            status_color = 0x00FF00
        else:
            title = label.Label(
                terminalio.FONT, text="Failed", color=0xFF0000,
                x=10, y=20, scale=2
            )
            status_color = 0xFF0000
        
        group.append(title)
        
        # Network name
        ssid_display = ssid[:25] if len(ssid) > 25 else ssid
        ssid_label = label.Label(
            terminalio.FONT, text=f"Network: {ssid_display}", color=0xFFFFFF,
            x=10, y=50
        )
        group.append(ssid_label)
        
        # Status message
        if message:
            msg_lines = [message[i:i+35] for i in range(0, len(message), 35)]
            for i, line in enumerate(msg_lines[:3]):  # Max 3 lines
                msg_label = label.Label(
                    terminalio.FONT, text=line, color=status_color,
                    x=10, y=80 + i * 15
                )
                group.append(msg_label)
        
        # Additional info for successful connection
        if success:
            try:
                ip_label = label.Label(
                    terminalio.FONT, text=f"IP: {wifi.radio.ipv4_address}", color=0x00FF00,
                    x=10, y=130
                )
                group.append(ip_label)
                
                if hasattr(wifi.radio, 'ap_info') and wifi.radio.ap_info:
                    signal_label = label.Label(
                        terminalio.FONT, text=f"Signal: {wifi.radio.ap_info.rssi} dBm", color=0x00FF00,
                        x=10, y=145
                    )
                    group.append(signal_label)
            except:
                pass
        
        # Instructions
        instruction_text = "Press button to continue" if self.has_button else "Press Enter to continue"
        instructions = label.Label(
            terminalio.FONT, text=instruction_text, color=0x888888,
            x=10, y=self.screen_height - 20
        )
        group.append(instructions)
        
        self.display.root_group = group
    
    def try_connect(self, ssid, password, max_attempts=3):
        """Attempt to connect to WiFi network"""
        for attempt in range(max_attempts):
            self.show_connecting_screen(ssid, attempt + 1, max_attempts)
            print(f"Connection attempt {attempt + 1}/{max_attempts} to {ssid}")
            
            try:
                # Disconnect first if connected and method exists
                if wifi.radio.connected:
                    print("Disconnecting from current network...")
                    self.safe_disconnect()
                
                # Attempt connection with timeout
                print(f"Connecting to {ssid}...")
                wifi.radio.connect(ssid, password, timeout=15)
                
                # Verify connection
                if wifi.radio.connected:
                    print(f"Successfully connected to {ssid}")
                    try:
                        print(f"IP Address: {wifi.radio.ipv4_address}")
                    except:
                        pass
                    self.show_result_screen(True, ssid, "Connection successful!")
                    return True
                else:
                    raise Exception("Connection failed - not connected after attempt")
                    
            except Exception as e:
                error_msg = str(e)
                print(f"Connection attempt {attempt + 1} failed: {error_msg}")
                
                if attempt < max_attempts - 1:
                    print("Waiting before retry...")
                    time.sleep(2)  # Wait before retry
                else:
                    self.show_result_screen(False, ssid, f"Error: {error_msg}")
        
        return False
    
    def handle_button_input(self):
        """Handle button press events"""
        if not self.has_button:
            return False
        
        if not self.button.value:  # Button pressed (active low)
            time.sleep(0.05)  # Debounce
            if not self.button.value:  # Still pressed
                press_start = time.monotonic()
                
                # Wait for release and measure duration
                while not self.button.value:
                    press_duration = time.monotonic() - press_start
                    time.sleep(0.01)
                
                return press_duration
        
        return 0
    
    def handle_console_input(self):
        """Handle console input"""
        if not supervisor.runtime.serial_bytes_available:
            return None
        
        try:
            return input().strip()
        except:
            return None
    
    def enter_password_interactive(self, ssid):
        """Interactive password entry"""
        self.password_entry = ""
        self.password_char_index = 0
        
        # Check if we have a saved password
        if ssid in self.known_networks:
            print(f"Using saved password for {ssid}")
            return self.known_networks[ssid]
        
        print(f"Enter password for {ssid}")
        print("Button: short press = next char, long press = add char, very long = finish")
        print("Console: type password directly and press Enter")
        
        while True:
            self.show_password_entry(ssid)
            
            # Handle console input (direct password entry)
            console_input = self.handle_console_input()
            if console_input is not None:
                if console_input == "":
                    if self.password_entry:
                        return self.password_entry
                else:
                    return console_input
            
            # Handle button input
            if self.has_button:
                press_duration = self.handle_button_input()
                
                if press_duration > 3.0:  # Very long press - finish
                    if self.password_entry:
                        return self.password_entry
                elif press_duration > 1.0:  # Long press - add character
                    current_char = CHARSET[self.password_char_index]
                    self.password_entry += current_char
                    self.password_char_index = 0
                    
                    if len(self.password_entry) >= MAX_PASSWORD_LEN:
                        return self.password_entry
                elif press_duration > 0.05:  # Short press - next character
                    self.password_char_index = (self.password_char_index + 1) % len(CHARSET)
            
            time.sleep(0.1)
    
    def network_selection_loop(self):
        """Main network selection loop"""
        self.selected = 0
        last_input_time = time.monotonic()
        
        while True:
            self.show_network_list()
            
            # Handle console input
            console_input = self.handle_console_input()
            if console_input is not None:
                last_input_time = time.monotonic()
                
                cmd = console_input.lower()
                if cmd in ['up', 'u']:
                    self.selected = (self.selected - 1) % len(self.networks)
                elif cmd in ['down', 'd']:
                    self.selected = (self.selected + 1) % len(self.networks)
                elif cmd in ['select', 's', 'enter', '']:
                    return self.networks[self.selected][0]  # Return selected SSID
                elif cmd.isdigit():
                    idx = int(cmd)
                    if 0 <= idx < len(self.networks):
                        self.selected = idx
                        return self.networks[self.selected][0]
                elif cmd in ['rescan', 'r']:
                    return 'RESCAN'
                elif cmd in ['quit', 'q', 'exit']:
                    return 'QUIT'
                else:
                    self.status_message = "Invalid command"
                    time.sleep(1)
                    self.status_message = ""
            
            # Handle button input
            if self.has_button:
                press_duration = self.handle_button_input()
                
                if press_duration > 1.0:  # Long press - select
                    return self.networks[self.selected][0]
                elif press_duration > 0.05:  # Short press - navigate
                    self.selected = (self.selected + 1) % len(self.networks)
                    last_input_time = time.monotonic()
            
            # Auto-timeout after 30 seconds of inactivity
            if time.monotonic() - last_input_time > 30:
                self.status_message = "Timeout - selecting current network"
                self.show_network_list()
                time.sleep(2)
                return self.networks[self.selected][0]
            
            time.sleep(0.1)
    
    def wait_for_continue(self):
        """Wait for user input to continue"""
        while True:
            # Console input
            console_input = self.handle_console_input()
            if console_input is not None:
                return
            
            # Button input
            if self.has_button:
                if self.handle_button_input() > 0.05:
                    return
            
            time.sleep(0.1)
    
    def run(self):
        """Main application loop"""
        print("WiFi Configuration Tool")
        print("=" * 40)
        
        while True:
            # Scan for networks
            if not self.scan_networks():
                # No networks found
                group = displayio.Group()
                
                title = label.Label(
                    terminalio.FONT, text="No Networks Found", color=0xFF0000,
                    x=10, y=20, scale=2
                )
                group.append(title)
                
                message = label.Label(
                    terminalio.FONT, text="Check WiFi is enabled nearby", color=0xFFFFFF,
                    x=10, y=50
                )
                group.append(message)
                
                # Show troubleshooting info
                troubleshoot_lines = [
                    "Troubleshooting:",
                    "- Move closer to router",
                    "- Check 2.4GHz networks available",
                    "- Restart device if needed"
                ]
                
                for i, line in enumerate(troubleshoot_lines):
                    trouble_label = label.Label(
                        terminalio.FONT, text=line, color=0x888888,
                        x=10, y=80 + i * 15
                    )
                    group.append(trouble_label)
        
        # Status bar
        status_text = f"{self.selected + 1}/{len(self.networks)}"
        if self.status_message:
            status_text += f" - {self.status_message}"
        
        status = label.Label(
            terminalio.FONT, text=status_text, color=0x888888,
            x=10, y=self.screen_height - 30
        )
        group.append(status)
        
        # Instructions
        if self.has_button:
            instructions = label.Label(
                terminalio.FONT, text="Short press: next, Long press: select",
                color=0x888888, x=10, y=self.screen_height - 15
            )
        else:
            instructions = label.Label(
                terminalio.FONT, text="Console: up/down/select or number",
                color=0x888888, x=10, y=self.screen_height - 15
            )
        group.append(instructions)
        

        self.display.root_group = group    
    def show_password_entry(self, ssid):
        """Display password entry screen"""
        group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, text="Enter Password", color=0x00FFFF,
            x=10, y=20, scale=2
        )
        group.append(title)
        
        # SSID
        ssid_display = ssid[:25] if len(ssid) > 25 else ssid
        ssid_label = label.Label(
            terminalio.FONT, text=f"Network: {ssid_display}", color=0xFFFFFF,
            x=10, y=45
        )
        group.append(ssid_label)
        
        # Password field
        current_char = CHARSET[self.password_char_index]
        display_password = "*" * len(self.password_entry) + current_char
        
        # Limit display length
        if len(display_password) > 30:
            display_password = "..." + display_password[-27:]
        
        password_label = label.Label(
            terminalio.FONT, text=f"Password: {display_password}", color=0x00FF00,
            x=10, y=70, scale=2
        )
        group.append(password_label)
        
        # Character selection help
        char_help = label.Label(
            terminalio.FONT, text=f"Current char: '{current_char}'", color=0xFFFF00,
            x=10, y=100
        )
        group.append(char_help)
        
        # Instructions
        instructions = [
            "Short press: next character",
            "Long press (1s): add character", 
            "Very long press (3s): finish",
            "Console: type password directly"
        ]
        
        for i, instruction in enumerate(instructions):
            inst_label = label.Label(
                terminalio.FONT, text=instruction, color=0x888888,
                x=10, y=130 + i * 15
            )
            group.append(inst_label)
        
        self.display.root_group = group
    
    def show_connecting_screen(self, ssid, attempt=1, max_attempts=3):
        """Display connection attempt screen"""
        group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT, text="Connecting...", color=0x00FFFF,
            x=10, y=20, scale=2
        )
        group.append(title)
        
        # Network name
        ssid_display = ssid[:25] if len(ssid) > 25 else ssid
        ssid_label = label.Label(
            terminalio.FONT, text=f"Network: {ssid_display}", color=0xFFFFFF,
            x=10, y=50
        )
        group.append(ssid_label)
        
        # Attempt counter
        attempt_label = label.Label(
            terminalio.FONT, text=f"Attempt {attempt} of {max_attempts}", color=0xFFFF00,
            x=10, y=80
        )
        group.append(attempt_label)
        
        # Animation dots
        dots = "." * (int(time.monotonic()) % 4)
        status_label = label.Label(
            terminalio.FONT, text=f"Please wait{dots}", color=0x888888,
            x=10, y=110
        )
        group.append(status_label)
        
        self.display.root_group = group
    
    def show_result_screen(self, success, ssid, message=""):
        """Display connection result"""
        group = displayio.Group()
        
        if success:
            title = label.Label(
                terminalio.FONT, text="Connected!", color=0x00FF00,
                x=10, y=20, scale=2
            )
            status_color = 0x00FF00
        else:
            title = label.Label(
                terminalio.FONT, text="Failed", color=0xFF0000,
                x=10, y=20, scale=2
            )
            status_color = 0xFF0000
        
        group.append(title)
        
        # Network name
        ssid_display = ssid[:25] if len(ssid) > 25 else ssid
        ssid_label = label.Label(
            terminalio.FONT, text=f"Network: {ssid_display}", color=0xFFFFFF,
            x=10, y=50
        )
        group.append(ssid_label)
        
        # Status message
        if message:
            msg_lines = [message[i:i+35] for i in range(0, len(message), 35)]
            for i, line in enumerate(msg_lines[:3]):  # Max 3 lines
                msg_label = label.Label(
                    terminalio.FONT, text=line, color=status_color,
                    x=10, y=80 + i * 15
                )
                group.append(msg_label)
        
        # Additional info for successful connection
        if success:
            try:
                ip_label = label.Label(
                    terminalio.FONT, text=f"IP: {wifi.radio.ipv4_address}", color=0x00FF00,
                    x=10, y=130
                )
                group.append(ip_label)
                
                if hasattr(wifi.radio, 'ap_info') and wifi.radio.ap_info:
                    signal_label = label.Label(
                        terminalio.FONT, text=f"Signal: {wifi.radio.ap_info.rssi} dBm", color=0x00FF00,
                        x=10, y=145
                    )
                    group.append(signal_label)
            except:
                pass
        
        # Instructions
        instruction_text = "Press button to continue" if self.has_button else "Press Enter to continue"
        instructions = label.Label(
            terminalio.FONT, text=instruction_text, color=0x888888,
            x=10, y=self.screen_height - 20
        )
        group.append(instructions)
        
        self.display.root_group = group
    
    def try_connect(self, ssid, password, max_attempts=3):
        """Attempt to connect to WiFi network"""
        for attempt in range(max_attempts):
            self.show_connecting_screen(ssid, attempt + 1, max_attempts)
            print(f"Connection attempt {attempt + 1}/{max_attempts} to {ssid}")
            
            try:
                # Disconnect first if connected and method exists
                if wifi.radio.connected:
                    print("Disconnecting from current network...")
                    self.safe_disconnect()
                
                # Attempt connection with timeout
                print(f"Connecting to {ssid}...")
                wifi.radio.connect(ssid, password, timeout=15)
                
                # Verify connection
                if wifi.radio.connected:
                    print(f"Successfully connected to {ssid}")
                    try:
                        print(f"IP Address: {wifi.radio.ipv4_address}")
                    except:
                        pass
                    self.show_result_screen(True, ssid, "Connection successful!")
                    return True
                else:
                    raise Exception("Connection failed - not connected after attempt")
                    
            except Exception as e:
                error_msg = str(e)
                print(f"Connection attempt {attempt + 1} failed: {error_msg}")
                
                if attempt < max_attempts - 1:
                    print("Waiting before retry...")
                    time.sleep(2)  # Wait before retry
                else:
                    self.show_result_screen(False, ssid, f"Error: {error_msg}")
        
        return False
    
    def handle_button_input(self):
        """Handle button press events"""
        if not self.has_button:
            return False
        
        if not self.button.value:  # Button pressed (active low)
            time.sleep(0.05)  # Debounce
            if not self.button.value:  # Still pressed
                press_start = time.monotonic()
                
                # Wait for release and measure duration
                while not self.button.value:
                    press_duration = time.monotonic() - press_start
                    time.sleep(0.01)
                
                return press_duration
        
        return 0
    
    def handle_console_input(self):
        """Handle console input"""
        if not supervisor.runtime.serial_bytes_available:
            return None
        
        try:
            return input().strip()
        except:
            return None
    
    def enter_password_interactive(self, ssid):
        """Interactive password entry"""
        self.password_entry = ""
        self.password_char_index = 0
        
        # Check if we have a saved password
        if ssid in self.known_networks:
            print(f"Using saved password for {ssid}")
            return self.known_networks[ssid]
        
        print(f"Enter password for {ssid}")
        print("Button: short press = next char, long press = add char, very long = finish")
        print("Console: type password directly and press Enter")
        
        while True:
            self.show_password_entry(ssid)
            
            # Handle console input (direct password entry)
            console_input = self.handle_console_input()
            if console_input is not None:
                if console_input == "":
                    if self.password_entry:
                        return self.password_entry
                else:
                    return console_input
            
            # Handle button input
            if self.has_button:
                press_duration = self.handle_button_input()
                
                if press_duration > 3.0:  # Very long press - finish
                    if self.password_entry:
                        return self.password_entry
                elif press_duration > 1.0:  # Long press - add character
                    current_char = CHARSET[self.password_char_index]
                    self.password_entry += current_char
                    self.password_char_index = 0
                    
                    if len(self.password_entry) >= MAX_PASSWORD_LEN:
                        return self.password_entry
                elif press_duration > 0.05:  # Short press - next character
                    self.password_char_index = (self.password_char_index + 1) % len(CHARSET)
            
            time.sleep(0.1)
    
    def network_selection_loop(self):
        """Main network selection loop"""
        self.selected = 0
        last_input_time = time.monotonic()
        
        while True:
            self.show_network_list()
            
            # Handle console input
            console_input = self.handle_console_input()
            if console_input is not None:
                last_input_time = time.monotonic()
                
                cmd = console_input.lower()
                if cmd in ['up', 'u']:
                    self.selected = (self.selected - 1) % len(self.networks)
                elif cmd in ['down', 'd']:
                    self.selected = (self.selected + 1) % len(self.networks)
                elif cmd in ['select', 's', 'enter', '']:
                    return self.networks[self.selected][0]  # Return selected SSID
                elif cmd.isdigit():
                    idx = int(cmd)
                    if 0 <= idx < len(self.networks):
                        self.selected = idx
                        return self.networks[self.selected][0]
                elif cmd in ['rescan', 'r']:
                    return 'RESCAN'
                elif cmd in ['quit', 'q', 'exit']:
                    return 'QUIT'
                else:
                    self.status_message = "Invalid command"
                    time.sleep(1)
                    self.status_message = ""
            
            # Handle button input
            if self.has_button:
                press_duration = self.handle_button_input()
                
                if press_duration > 1.0:  # Long press - select
                    return self.networks[self.selected][0]
                elif press_duration > 0.05:  # Short press - navigate
                    self.selected = (self.selected + 1) % len(self.networks)
                    last_input_time = time.monotonic()
            
            # Auto-timeout after 30 seconds of inactivity
            if time.monotonic() - last_input_time > 30:
                self.status_message = "Timeout - selecting current network"
                self.show_network_list()
                time.sleep(2)
                return self.networks[self.selected][0]
            
            time.sleep(0.1)
    
    def wait_for_continue(self):
        """Wait for user input to continue"""
        while True:
            # Console input
            console_input = self.handle_console_input()
            if console_input is not None:
                return
            
            # Button input
            if self.has_button:
                if self.handle_button_input() > 0.05:
                    return
            
            time.sleep(0.1)
    
    def run(self):
        """Main application loop"""
        print("WiFi Configuration Tool")
        print("=" * 40)
        
        while True:
            # Scan for networks
            if not self.scan_networks():
                # No networks found
                group = displayio.Group()
                
                title = label.Label(
                    terminalio.FONT, text="No Networks Found", color=0xFF0000,
                    x=10, y=20, scale=2
                )
                group.append(title)
                
                message = label.Label(
                    terminalio.FONT, text="Check WiFi is enabled nearby", color=0xFFFFFF,
                    x=10, y=50
                )
                group.append(message)
                
                # Show troubleshooting info
                troubleshoot_lines = [
                    "Troubleshooting:",
                    "- Move closer to router",
                    "- Check 2.4GHz networks available",
                    "- Restart device if needed"
                ]
                
                for i, line in enumerate(troubleshoot_lines):
                    trouble_label = label.Label(
                        terminalio.FONT, text=line, color=0x888888,
                        x=10, y=80 + i * 15
                    )
                    group.append(trouble_label)
                
                retry_label = label.Label(
                    terminalio.FONT, text="Press button/Enter to retry, 'q' to quit", color=0x888888,
                    x=10, y=self.screen_height - 20
                )
                group.append(retry_label)
                
                self.display.root_group = group
                
                print("No WiFi networks found!")
                print("Troubleshooting tips:")
                print("- Ensure you're close to a WiFi router")
                print("- Check that 2.4GHz networks are available")
                print("- Some devices only support 2.4GHz, not 5GHz")
                print("- Try restarting the device")
                print("\nPress button or Enter to retry, 'q' to quit")
                
                # Wait for input
                while True:
                    console_input = self.handle_console_input()
                    if console_input is not None:
                        if console_input.lower() in ['q', 'quit', 'exit']:
                            return
                        else:
                            break
                    
                    if self.has_button and self.handle_button_input() > 0.05:
                        break
                    
                    time.sleep(0.1)
                
                continue  # Retry scan
            
            # Show network selection
            selected_ssid = self.network_selection_loop()
            
            if selected_ssid == 'QUIT':
                break
            elif selected_ssid == 'RESCAN':
                continue
            
            # Get password
            password = self.enter_password_interactive(selected_ssid)
            
            # Attempt connection
            if self.try_connect(selected_ssid, password):
                # Save settings
                self.save_wifi_settings(selected_ssid, password)
                print(f"WiFi configured successfully for {selected_ssid}")
                
                # Wait for user acknowledgment
                self.wait_for_continue()
                
                # Ask if user wants to configure another network
                group = displayio.Group()
                
                title = label.Label(
                    terminalio.FONT, text="Configure Another?", color=0x00FFFF,
                    x=10, y=20, scale=2
                )
                group.append(title)
                
                success_msg = label.Label(
                    terminalio.FONT, text=f"Successfully saved {selected_ssid}", color=0x00FF00,
                    x=10, y=50
                )
                group.append(success_msg)
                
                instructions = label.Label(
                    terminalio.FONT, text="Press button/Enter: Yes, 'q': Quit", color=0xFFFFFF,
                    x=10, y=80
                )
                group.append(instructions)
                
                self.display.root_group = group
                
                # Wait for decision
                while True:
                    console_input = self.handle_console_input()
                    if console_input is not None:
                        if console_input.lower() in ['q', 'quit', 'exit', 'n', 'no']:
                            return
                        else:
                            break
                    
                    if self.has_button and self.handle_button_input() > 0.05:
                        break
                    
                    time.sleep(0.1)
            else:
                # Connection failed - wait for acknowledgment
                self.wait_for_continue()
                
                # Ask if user wants to try again
                group = displayio.Group()
                
                title = label.Label(
                    terminalio.FONT, text="Connection Failed", color=0xFF0000,
                    x=10, y=20, scale=2
                )
                group.append(title)
                
                retry_msg = label.Label(
                    terminalio.FONT, text="Try again or select different network?", color=0xFFFFFF,
                    x=10, y=50
                )
                group.append(retry_msg)
                
                instructions = label.Label(
                    terminalio.FONT, text="Press button/Enter: Retry, 'q': Quit", color=0x888888,
                    x=10, y=80
                )
                group.append(instructions)
                
                self.display.root_group = group
                
                # Wait for decision
                while True:
                    console_input = self.handle_console_input()
                    if console_input is not None:
                        if console_input.lower() in ['q', 'quit', 'exit']:
                            return
                        else:
                            break
                    
                    if self.has_button and self.handle_button_input() > 0.05:
                        break
                    
                    time.sleep(0.1)
                
                # Continue to try again or select different network
                continue

def debug_wifi_info():
    """Print detailed WiFi debugging information"""
    print("\n" + "="*50)
    print("WiFi Debug Information")
    print("="*50)
    
    try:
        print(f"WiFi radio enabled: {wifi.radio.enabled}")
        print(f"WiFi radio connected: {wifi.radio.connected}")
        
        # Check available methods
        methods = [
            'connect', 'disconnect', 'scan_networks', 
            'start_scanning_networks', 'stop_scanning_networks',
            'enabled', 'connected', 'ipv4_address', 'ap_info'
        ]
        
        print("\nAvailable WiFi methods:")
        for method in methods:
            has_method = hasattr(wifi.radio, method)
            print(f"  {method}: {'✓' if has_method else '✗'}")
        
        # Try to get current connection info
        if wifi.radio.connected:
            try:
                print(f"\nCurrent connection:")
                print(f"  IP Address: {wifi.radio.ipv4_address}")
                if hasattr(wifi.radio, 'ap_info') and wifi.radio.ap_info:
                    print(f"  SSID: {wifi.radio.ap_info.ssid}")
                    print(f"  RSSI: {wifi.radio.ap_info.rssi} dBm")
            except Exception as e:
                print(f"  Error getting connection info: {e}")
        
        # Try a simple scan test
        print(f"\nTesting scan capability...")
        try:
            if hasattr(wifi.radio, 'start_scanning_networks'):
                print("  Using start_scanning_networks method")
                count = 0
                for network in wifi.radio.start_scanning_networks():
                    count += 1
                    if count >= 3:  # Just test first few
                        break
                    try:
                        ssid = network.ssid.decode('utf-8', errors='ignore') if isinstance(network.ssid, bytes) else str(network.ssid)
                        print(f"    Found: {ssid} ({network.rssi}dBm)")
                    except Exception as e:
                        print(f"    Error processing network: {e}")
                
                try:
                    wifi.radio.stop_scanning_networks()
                except:
                    pass
                    
                print(f"  Scan test completed - found {count} networks")
                
            elif hasattr(wifi.radio, 'scan_networks'):
                print("  Using scan_networks method")
                networks = wifi.radio.scan_networks()
                print(f"  Found {len(networks)} networks")
                
            else:
                print("  No known scan method available")
                
        except Exception as e:
            print(f"  Scan test failed: {e}")
            
    except Exception as e:
        print(f"WiFi debug failed: {e}")
    
    print("="*50)

def main():
    """Main entry point"""
    try:
        # Ensure we have a display
        if not hasattr(board, 'DISPLAY'):
            print("ERROR: This device does not have a built-in display")
            print("Use console-only version instead")
            return
        
        # Check for debug mode
        import sys
        if len(sys.argv) > 1 and sys.argv[1].lower() == 'debug':
            debug_wifi_info()
            return
        
        # Initialize and run WiFi config UI
        wifi_ui = WiFiConfigUI()
        wifi_ui.run()
        
        print("WiFi configuration completed")
        
    except KeyboardInterrupt:
        print("\nWiFi configuration cancelled")
    except Exception as e:
        print(f"WiFi configuration error: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
    
    finally:
        # Clean up display
        try:
            # Show exit message
            group = displayio.Group()
            exit_label = label.Label(
                terminalio.FONT, text="WiFi Config Complete", color=0x00FF00,
                x=10, y=board.DISPLAY.height // 2, scale=2
            )
            group.append(exit_label)
            board.DISPLAY.root_group = group
            time.sleep(2)
            
            # Clear display
            board.DISPLAY.root_group = displayio.Group()
            
        except:
            pass

if __name__ == "__main__":
    main()
