"""
CircuitPython Smart Home Device
Companion code for the Debian detector app
"""

import wifi
import socketpool
import json
import time
import board
import displayio
import terminalio
from adafruit_display_text import label
import microcontroller
import supervisor
import gc

# BLE imports (if available)
try:
    import _bleio
    import adafruit_ble
    from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
    from adafruit_ble.services.nordic import UARTService
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False

# HTTP server imports
try:
    from adafruit_httpserver import Server as HTTPServer
    HTTP_AVAILABLE = True
except ImportError:
    HTTP_AVAILABLE = False

server = HTTPServer
class SmartHomeDevice:
    """Smart home device handler"""
    
    def __init__(self):
        print("Initializing Smart Home Device...")
        
        self.display = board.DISPLAY
        self.awake = True
        self.last_command_time = 0
        
        # Device info
        self.device_info = {
            "name": "MEDUSA",
            "type": "CircuitPython",
            "version": "1.0",
            "board": board.board_id
        }
        
        # Initialize components
        self.wifi_handler = WiFiHandler(self) if wifi else None
        self.ble_handler = BLEHandler(self) if BLE_AVAILABLE else None
        self.display_handler = DisplayHandler(self)
        
        print("Smart Home Device initialized")
    
    def start(self):
        """Start the smart home device"""
        print("Starting Smart Home Device...")
        
        # Start WiFi
        if self.wifi_handler:
            self.wifi_handler.start()
        
        # Start BLE
        if self.ble_handler:
            self.ble_handler.start()
        
        # Main loop
        self.main_loop()
    
    def main_loop(self):
        """Main device loop"""
        while True:
            try:
                # Handle WiFi requests
                if self.wifi_handler:
                    self.wifi_handler.handle_requests()
                
                # Handle BLE
                if self.ble_handler:
                    self.ble_handler.handle_ble()
                
                # Update display
                self.display_handler.update()
                
                # Sleep management
                if self.awake and (time.monotonic() - self.last_command_time) > 30:
                    self.sleep_device()
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Main loop error: {e}")
                time.sleep(1)
    
    def handle_command(self, command_data):
        """Handle incoming command"""
        try:
            command_type = command_data.get("type", "unknown")
            print(f"Received command: {command_type}")
            
            self.last_command_time = time.monotonic()
            
            if command_type == "wake":
                self.wake_device()
            elif command_type == "sleep":
                self.sleep_device()
            elif command_type == "welcome":
                self.show_welcome_message(command_data)
            elif command_type == "test":
                self.show_test_message(command_data)
            else:
                print(f"Unknown command: {command_type}")
                
        except Exception as e:
            print(f"Command handling error: {e}")
    
    def wake_device(self):
        """Wake up the device"""
        print("Waking device...")
        self.awake = True
        self.display_handler.wake_display()
    
    def sleep_device(self):
        """Put device to sleep"""
        print("Sleeping device...")
        self.awake = False
        self.display_handler.sleep_display()
    
    def show_welcome_message(self, message_data):
        """Show welcome message"""
        message = message_data.get("message", "Welcome!")
        user = message_data.get("user", "User")
        
        self.display_handler.show_message(f"Welcome!\n{user}", duration=10)
    
    def show_test_message(self, message_data):
        """Show test message"""
        message = message_data.get("message", "Test")
        self.display_handler.show_message(f"Test Message:\n{message}", duration=5)


class WiFiHandler:
    """Handle WiFi communication"""
    
    def __init__(self, parent):
        self.parent = parent
        self.pool = None
        self.server = None
        self.connected = False
    
    def start(self):
        """Start WiFi and HTTP server"""
        try:
            # Connect to WiFi
            self.connect_wifi()
            
            if self.connected and HTTP_AVAILABLE:
                self.start_server()
                
        except Exception as e:
            print(f"WiFi start error: {e}")
    
    def connect_wifi(self):
        """Connect to WiFi"""
        try:
            import os
            
            ssid = os.getenv('CIRCUITPY_WIFI_SSID')
            password = os.getenv('CIRCUITPY_WIFI_PASSWORD')
            
            if ssid and password:
                print(f"Connecting to WiFi: {ssid}")
                wifi.radio.connect(ssid, password)
                
                if wifi.radio.connected:
                    print(f"WiFi connected: {wifi.radio.ipv4_address}")
                    self.connected = True
                    self.pool = socketpool.SocketPool(wifi.radio)
                else:
                    print("WiFi connection failed")
            else:
                print("WiFi credentials not found")
                
        except Exception as e:
            print(f"WiFi connection error: {e}")
    
    def start_server(self):
        """Start HTTP server"""
        try:
            self.server = server.HTTPServer(self.pool)
            
            # Add routes
            @self.server.route("/")
            def index(request):
                return server.HTTPResponse(body="CircuitPython Smart Home Device")
            
            @self.server.route("/status")
            def status(request):
                status_data = {
                    "device": self.parent.device_info,
                    "awake": self.parent.awake,
                    "timestamp": time.monotonic()
                }
                return server.HTTPResponse(
                    body=json.dumps(status_data),
                    content_type="application/json"
                )
            
            @self.server.route("/api/info")
            def device_info(request):
                return server.HTTPResponse(
                    body=json.dumps(self.parent.device_info),
                    content_type="application/json"
                )
            
            @self.server.route("/api/command", methods=["POST"])
            def handle_command(request):
                try:
                    command_data = json.loads(request.body)
                    self.parent.handle_command(command_data)
                    
                    response_data = {"status": "success", "command": command_data.get("type")}
                    return server.HTTPResponse(
                        body=json.dumps(response_data),
                        content_type="application/json"
                    )
                except Exception as e:
                    error_data = {"status": "error", "message": str(e)}
                    return server.HTTPResponse(
                        body=json.dumps(error_data),
                        content_type="application/json",
                        status=400
                    )
            
            self.server.start(host=str(wifi.radio.ipv4_address), port=8080)
            print(f"HTTP server started on {wifi.radio.ipv4_address}:8080")
            
        except Exception as e:
            print(f"Server start error: {e}")
    
    def handle_requests(self):
        """Handle incoming HTTP requests"""
        try:
            if self.server:
                self.server.poll()
        except Exception as e:
            print(f"Request handling error: {e}")


class BLEHandler:
    """Handle BLE communication"""
    
    def __init__(self, parent):
        self.parent = parent
class BLEHandler:
    """Handle BLE communication"""
    
    def __init__(self, parent):
        self.parent = parent
        self.ble = None
        self.uart_service = None
        self.advertisement = None
        self.connected = False
    
    def start(self):
        """Start BLE advertising"""
        try:
            self.ble = adafruit_ble.BLERadio()
            self.uart_service = UARTService()
            
            # Create advertisement
            self.advertisement = ProvideServicesAdvertisement(self.uart_service)
            self.advertisement.complete_name = self.parent.device_info["name"]
            
            # Start advertising
            self.ble.start_advertising(self.advertisement)
            print("BLE advertising started")
            
        except Exception as e:
            print(f"BLE start error: {e}")
    
    def handle_ble(self):
        """Handle BLE communication"""
        try:
            if not self.ble:
                return
            
            # Check for connections
            if self.ble.connected and not self.connected:
                print("BLE device connected")
                self.connected = True
            elif not self.ble.connected and self.connected:
                print("BLE device disconnected")
                self.connected = False
                # Restart advertising
                self.ble.start_advertising(self.advertisement)
            
            # Handle incoming data
            if self.ble.connected and self.uart_service.in_waiting:
                data = self.uart_service.read()
                if data:
                    try:
                        command_data = json.loads(data.decode('utf-8'))
                        self.parent.handle_command(command_data)
                    except Exception as e:
                        print(f"BLE data parsing error: {e}")
            
        except Exception as e:
            print(f"BLE handling error: {e}")


class DisplayHandler:
    """Handle display operations"""
    
    def __init__(self, parent):
        self.parent = parent
        self.current_group = None
        self.message_timeout = 0
        self.default_brightness = 0.8
        self.sleep_brightness = 0.1
    
    def wake_display(self):
        """Wake up display"""
        try:
            if hasattr(self.parent.display, 'brightness'):
                self.parent.display.brightness = self.default_brightness
            
            self.show_status_screen()
            print("Display awakened")
            
        except Exception as e:
            print(f"Display wake error: {e}")
    
    def sleep_display(self):
        """Put display to sleep"""
        try:
            if hasattr(self.parent.display, 'brightness'):
                self.parent.display.brightness = self.sleep_brightness
            
            self.show_sleep_screen()
            print("Display sleeping")
            
        except Exception as e:
            print(f"Display sleep error: {e}")
    
    def show_message(self, message, duration=5):
        """Show message on display"""
        try:
            self.create_message_screen(message)
            self.message_timeout = time.monotonic() + duration
            print(f"Showing message: {message}")
            
        except Exception as e:
            print(f"Show message error: {e}")
    
    def update(self):
        """Update display"""
        try:
            # Check message timeout
            if self.message_timeout > 0 and time.monotonic() > self.message_timeout:
                self.message_timeout = 0
                if self.parent.awake:
                    self.show_status_screen()
                else:
                    self.show_sleep_screen()
            
        except Exception as e:
            print(f"Display update error: {e}")
    
    def create_message_screen(self, message):
        """Create message display screen"""
        try:
            group = displayio.Group()
            
            # Background
            from adafruit_display_shapes.rect import Rect
            bg = Rect(0, 0, 240, 135, fill=0x001122)
            group.append(bg)
            
            # Message text
            lines = message.split('\n')
            for i, line in enumerate(lines[:4]):  # Max 4 lines
                y_pos = 30 + (i * 25)
                text_label = label.Label(
                    terminalio.FONT,
                    text=line,
                    color=0xFFFFFF,
                    x=10,
                    y=y_pos
                )
                group.append(text_label)
            
            # Timestamp
            timestamp = time.localtime()
            time_str = f"{timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
            time_label = label.Label(
                terminalio.FONT,
                text=time_str,
                color=0x888888,
                x=10,
                y=120
            )
            group.append(time_label)
            
            self.parent.display.root_group = group
            self.current_group = group
            
        except Exception as e:
            print(f"Message screen error: {e}")
    
    def show_status_screen(self):
        """Show status screen"""
        try:
            group = displayio.Group()
            
            # Background
            from adafruit_display_shapes.rect import Rect
            bg = Rect(0, 0, 240, 135, fill=0x000033)
            group.append(bg)
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="SMART HOME DEVICE",
                color=0x00FFFF,
                x=50,
                y=20
            )
            group.append(title)
            
            # Status
            status_text = "AWAKE" if self.parent.awake else "SLEEPING"
            status_color = 0x00FF00 if self.parent.awake else 0xFF6600
            
            status_label = label.Label(
                terminalio.FONT,
                text=f"Status: {status_text}",
                color=status_color,
                x=10,
                y=50
            )
            group.append(status_label)
            
            # WiFi status
            wifi_status = "Connected" if (self.parent.wifi_handler and self.parent.wifi_handler.connected) else "Disconnected"
            wifi_label = label.Label(
                terminalio.FONT,
                text=f"WiFi: {wifi_status}",
                color=0xFFFFFF,
                x=10,
                y=70
            )
            group.append(wifi_label)
            
            # BLE status
            ble_status = "Active" if (self.parent.ble_handler and self.parent.ble_handler.ble) else "Inactive"
            ble_label = label.Label(
                terminalio.FONT,
                text=f"BLE: {ble_status}",
                color=0xFFFFFF,
                x=10,
                y=90
            )
            group.append(ble_label)
            
            # Time
            timestamp = time.localtime()
            time_str = f"{timestamp.tm_hour:02d}:{timestamp.tm_min:02d}:{timestamp.tm_sec:02d}"
            time_label = label.Label(
                terminalio.FONT,
                text=time_str,
                color=0x888888,
                x=10,
                y=120
            )
            group.append(time_label)
            
            self.parent.display.root_group = group
            self.current_group = group
            
        except Exception as e:
            print(f"Status screen error: {e}")
    
    def show_sleep_screen(self):
        """Show sleep screen"""
        try:
            group = displayio.Group()
            
            # Dark background
            from adafruit_display_shapes.rect import Rect
            bg = Rect(0, 0, 240, 135, fill=0x000000)
            group.append(bg)
            
            # Dim clock
            timestamp = time.localtime()
            time_str = f"{timestamp.tm_hour:02d}:{timestamp.tm_min:02d}"
            time_label = label.Label(
                terminalio.FONT,
                text=time_str,
                color=0x333333,
                x=90,
                y=70
            )
            group.append(time_label)
            
            self.parent.display.root_group = group
            self.current_group = group
            
        except Exception as e:
            print(f"Sleep screen error: {e}")


def main():
    """Main entry point"""
    try:
        print("=" * 40)
        print("CIRCUITPYTHON SMART HOME DEVICE")
        print("=" * 40)
        
        # Check for screensaver mode flag
        screensaver_mode = microcontroller.nvm[10] == 1
        
        if screensaver_mode:
            print("Running in screensaver mode")
            # Clear the flag
            microcontroller.nvm[10] = 0
            
            # Run screensaver for a limited time
            run_screensaver_mode()
        else:
            # Normal smart home device mode
            device = SmartHomeDevice()
            device.start()
            
    except Exception as e:
        print(f"Main error: {e}")
        # Fallback to basic operation
        basic_operation()


def run_screensaver_mode():
    """Run as screensaver with timeout"""
    try:
        # Import the satellite animation
        try:
            from apps.satellite_orbit import safe_satellite_animation
            print("Running satellite screensaver...")
            safe_satellite_animation()
        except ImportError:
            # Fallback screensaver
            print("Running basic screensaver...")
            basic_screensaver()
        
        # Return to loader after screensaver
        print("Screensaver complete - returning to system")
        supervisor.set_next_code_file("/lib/system/loader.py")
        supervisor.reload()
        
    except Exception as e:
        print(f"Screensaver mode error: {e}")
        # Return to system
        supervisor.set_next_code_file("/lib/system/loader.py")
        supervisor.reload()


def basic_screensaver():
    """Basic screensaver fallback"""
    try:
        import board
        import displayio
        import time
        import math
        from adafruit_display_shapes.circle import Circle
        
        display = board.DISPLAY
        
        # Simple moving dot screensaver
        for frame in range(300):  # 30 seconds at 10fps
            group = displayio.Group()
            
            # Black background
            from adafruit_display_shapes.rect import Rect
            bg = Rect(0, 0, 240, 135, fill=0x000000)
            group.append(bg)
            
            # Moving dot
            angle = (frame * 0.1) % (2 * math.pi)
            x = int(120 + 50 * math.cos(angle))
            y = int(67 + 30 * math.sin(angle))
            
            dot = Circle(x, y, 5, fill=0x0066CC)
            group.append(dot)
            
            display.root_group = group
            time.sleep(0.1)
            
            # Memory cleanup
            if frame % 30 == 0:
                gc.collect()
        
    except Exception as e:
        print(f"Basic screensaver error: {e}")


def basic_operation():
    """Basic operation fallback"""
    try:
        print("Running in basic mode...")
        
        import board
        import displayio
        import terminalio
        from adafruit_display_text import label
        
        display = board.DISPLAY
        
        # Show basic status
        group = displayio.Group()
        
        # Background
        from adafruit_display_shapes.rect import Rect
        bg = Rect(0, 0, 240, 135, fill=0x001122)
        group.append(bg)
        
        # Status text
        status_label = label.Label(
            terminalio.FONT,
            text="Smart Home Device\nBasic Mode\nReady",
            color=0xFFFFFF,
            x=50,
            y=50
        )
        group.append(status_label)
        
        display.root_group = group
        
        # Simple loop
        while True:
            time.sleep(1)
            
    except Exception as e:
        print(f"Basic operation error: {e}")


# Auto-start
if __name__ == "__main__":
    main()
else:
    print("CircuitPython Smart Home Device module loaded")
