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
MAX_NETWORKS = 50
MAX_PASSWORD_LEN = 63  # WPA2 max length
CHAR_GROUPS = [
    "abcdefghijklmnopqrstuvwxyz",  # Lowercase
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # Uppercase
    "0123456789",                  # Numbers
    "!@#$%^&*()-_=+[]{};:',.<>/?\\|\"`~ "  # Symbols + space
    ]
    
CHARSET = "".join(CHAR_GROUPS)

def load_settings():
    """Load all settings as a dict of key: value."""
    settings = {}
    if SETTINGS_PATH in os.listdir("/"):
        with open(SETTINGS_PATH, "r") as f:
            for line in f:
                if "=" in line:
                    key, value = line.split("=", 1)
                    settings[key.strip()] = value.strip().strip('"')
    return settings

def save_settings(settings):
    """Write all settings back to the file, preserving all keys."""
    with open(SETTINGS_PATH, "w") as f:
        for key, value in settings.items():
            if value.isdigit() or value in ("True", "False"):
                f.write(f"{key} = {value}\n")
            else:
                f.write(f'{key} = "{value}"\n')

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
    # Update indexed keys
    for i, (s, p) in enumerate(networks, 1):
        settings[f"WIFI_SSID_{i}"] = s
        settings[f"WIFI_PASSWORD_{i}"] = p
    # Remove any old keys beyond the new list
    for i in range(len(networks) + 1, MAX_NETWORKS + 1):
        settings.pop(f"WIFI_SSID_{i}", None)
        settings.pop(f"WIFI_PASSWORD_{i}", None)
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
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except Exception:
            self.has_button = False
            print("No button available - console only mode")
        self.selected = 0
        self.networks = []
        self.status_message = ""
        self.password_entry = ""
        self.password_char_index = 0

    def scan_networks(self):
        """Scan for WiFi networks."""
        self.networks = []
        self.show_message("Scanning for networks...")
        try:
            if not wifi.radio.enabled:
                wifi.radio.enabled = True
                time.sleep(2)
            if wifi.radio.connected:
                wifi.radio.disconnect()
                time.sleep(1)
            gc.collect()
            found = {}
            for network in wifi.radio.start_scanning_networks():
                ssid = network.ssid.decode("utf-8") if isinstance(network.ssid, bytes) else str(network.ssid)
                if not ssid or not ssid.strip():
                    continue
                rssi = getattr(network, "rssi", -100)
                if ssid not in found or found[ssid][1] < rssi:
                    found[ssid] = (ssid, rssi)
            wifi.radio.stop_scanning_networks()
            self.networks = sorted(found.values(), key=lambda x: x[1], reverse=True)
        except Exception as e:
            self.show_message("Scan failed:\n" + str(e), color=0xFF0000)
            time.sleep(2)
        return len(self.networks) > 0

    def show_message(self, msg, color=0xFFFFFF):
        group = displayio.Group()
        lines = msg.split("\n")
        for i, line in enumerate(lines):
            text = label.Label(terminalio.FONT, text=line, color=color, x=10, y=20 + i*20)
            group.append(text)
        self.display.root_group = group
        time.sleep(0.1)

    def show_network_list(self):
        group = displayio.Group()
        title = label.Label(terminalio.FONT, text="Select Network", color=0x00FFFF, x=10, y=10)
        group.append(title)
        max_visible = min(8, (self.screen_height - 60) // 20)
        start_idx = max(0, self.selected - max_visible // 2)
        end_idx = min(len(self.networks), start_idx + max_visible)
        if end_idx - start_idx < max_visible and len(self.networks) > max_visible:
            start_idx = max(0, end_idx - max_visible)
        for i in range(start_idx, end_idx):
            ssid, rssi = self.networks[i]
            y_pos = 35 + (i - start_idx) * 20
            color = 0xFFFF00 if i == self.selected else 0xFFFFFF
            net_label = label.Label(terminalio.FONT, text=f"{ssid[:20]} ({rssi}dBm)", color=color, x=15, y=y_pos)
            group.append(net_label)
        status = label.Label(terminalio.FONT, text=f"{self.selected+1}/{len(self.networks)}", color=0x888888, x=10, y=self.screen_height-30)
        group.append(status)
        instructions = label.Label(terminalio.FONT, text="Short: next, Long: select", color=0x888888, x=10, y=self.screen_height-15)
        group.append(instructions)
        self.display.root_group = group

    def handle_button_input(self):
        if not self.has_button:
            return 0
        if not self.button.value:
            time.sleep(0.05)
            if not self.button.value:
                press_start = time.monotonic()
                while not self.button.value:
                    press_duration = time.monotonic() - press_start
                    time.sleep(0.01)
                return press_duration
        return 0

    def enter_password_interactive(self, ssid):
        self.password_entry = ""
        self.password_char_index = 0
        click_times = []
        while True:
            self.show_password_entry(ssid)
            if self.has_button:
                press_duration = self.handle_button_input()
                now = time.monotonic()
                # Triple click detection (three short presses within 1s)
                if 0.05 < press_duration < 0.5:
                    click_times.append(now)
                    # Keep only last 3 clicks
                    click_times = [t for t in click_times if now - t < 1.0]
                    if len(click_times) >= 3:
                        # Triple click detected: jump to next group
                        self.password_char_index = self.next_group_index(self.password_char_index)
                        click_times = []
                    else:
                        # Normal short press: next char
                        self.password_char_index = (self.password_char_index + 1) % len(CHARSET)
                elif 1.0 < press_duration < 3.0:
                    # Long press: add char
                    current_char = CHARSET[self.password_char_index]
                    self.password_entry += current_char
                    self.password_char_index = 0
                    click_times = []
                    if len(self.password_entry) >= MAX_PASSWORD_LEN:
                        return self.password_entry
                elif press_duration >= 3.0:
                    # Very long press: finish
                    if self.password_entry:
                        return self.password_entry
                    click_times = []
            time.sleep(0.1)
            
    CHAR_GROUPS = [
    "abcdefghijklmnopqrstuvwxyz",  # Lowercase
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # Uppercase
    "0123456789",                  # Numbers
    "!@#$%^&*()-_=+[]{};:',.<>/?\\|\"`~ "  # Symbols + space
    ]
    
    CHARSET = "".join(CHAR_GROUPS)
    MAX_PASSWORD_LEN = 63

    def get_group_start_indices():
        indices = []
        idx = 0
        for group in CHAR_GROUPS:
            indices.append(idx)
            idx += len(group)
        return indices

    GROUP_STARTS = get_group_start_indices()

    def next_group_index(self, current_index):
        # Find which group we're in
        for i, start in enumerate(GROUP_STARTS):
            if current_index < start + len(CHAR_GROUPS[i]):
                next_group = (i + 1) % len(CHAR_GROUPS)
                return GROUP_STARTS[next_group]
        return 0

    def show_password_entry(self, ssid):
        group = displayio.Group()
        title = label.Label(terminalio.FONT, text="Enter Password", color=0x00FFFF, x=10, y=20)
        group.append(title)
        ssid_label = label.Label(terminalio.FONT, text=f"Network: {ssid[:25]}", color=0xFFFFFF, x=10, y=45)
        group.append(ssid_label)
        current_char = CHARSET[self.password_char_index]
        display_password = "*" * len(self.password_entry) + current_char
        if len(display_password) > 30:
            display_password = "..." + display_password[-27:]
        password_label = label.Label(terminalio.FONT, text=f"Password: {display_password}", color=0x00FF00, x=10, y=70)
        group.append(password_label)
        display_char = "[space]" if current_char == " " else current_char
        char_help = label.Label(terminalio.FONT, text=f"Current char: '{display_char}'", color=0xFFFF00, x=10, y=100)
        group.append(char_help)
        instructions = [
            "Short: next char",
            "Long (1s): add char",
            "Very long (3s): finish",
            "Triple short: next group"
        ]
        for i, instruction in enumerate(instructions):
            inst_label = label.Label(terminalio.FONT, text=instruction, color=0x888888, x=10, y=130 + i * 15)
            group.append(inst_label)
        self.display.root_group = group

# ...rest of your code...

    def try_connect(self, ssid, password, max_attempts=3):
        for attempt in range(max_attempts):
            self.show_message(f"Connecting to {ssid}\nAttempt {attempt+1}/{max_attempts}")
            try:
                if wifi.radio.connected:
                    wifi.radio.disconnect()
                    time.sleep(1)
                wifi.radio.connect(ssid, password, timeout=15)
                if wifi.radio.connected:
                    self.show_message(f"Connected!\nIP: {wifi.radio.ipv4_address}", color=0x00FF00)
                    return True
            except Exception as e:
                self.show_message(f"Failed: {e}", color=0xFF0000)
                time.sleep(1)
        return False

    def wait_for_continue(self):
        while True:
            if self.has_button and self.handle_button_input() > 0.05:
                return
            time.sleep(0.1)

    def run(self):
        while True:
            if not self.scan_networks():
                self.show_message("No networks found.\nPress button to retry.", color=0xFF0000)
                self.wait_for_continue()
                continue
            self.selected = 0
            while True:
                self.show_network_list()
                press_duration = self.handle_button_input()
                if press_duration > 1.0:
                    break
                elif press_duration > 0.05:
                    self.selected = (self.selected + 1) % len(self.networks)
                time.sleep(0.1)
            ssid, _ = self.networks[self.selected]
            password = self.enter_password_interactive(ssid)
            if self.try_connect(ssid, password):
                save_wifi_network(ssid, password, make_primary=True)
                self.show_message("WiFi saved!\nPress button to finish.", color=0x00FF00)
                self.wait_for_continue()
                break
            else:
                self.show_message("Connection failed.\nPress button to retry.", color=0xFF0000)
                self.wait_for_continue()

def main():
    wifi_ui = WiFiConfigUI()
    wifi_ui.run()

if __name__ == "__main__":
    main()