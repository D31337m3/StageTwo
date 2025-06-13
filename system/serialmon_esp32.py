"""
Simple ESP32 Serial Monitor - Robust Version
usage: USB<->SERIAL monitoring ESP32 Microcontrollers via Serial connection
"""

import board
import busio
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
import time
import gc

class SimpleESP32Monitor:
    """Simple, robust ESP32 serial monitor"""
    
    def __init__(self, baudrate=115200):
        print(f"Starting Simple ESP32 Monitor at {baudrate} baud")
        
        # Initialize display
        try:
            self.display = board.DISPLAY
            self.display.auto_refresh = True
            print("Display OK")
        except Exception as e:
            print(f"Display error: {e}")
            self.display = None
        
        # Initialize UART
        try:
            self.uart = busio.UART(
                tx=board.TX,
                rx=board.RX,
                baudrate=baudrate,
                timeout=0.1
            )
            print(f"UART OK at {baudrate} baud")
        except Exception as e:
            print(f"UART error: {e}")
            self.uart = None
            return
        
        # Simple data storage
        self.lines = []
        self.buffer = ""
        self.byte_count = 0
        self.line_count = 0
        
        print("Monitor initialized successfully")
    
    def read_data(self):
        """Read and process UART data"""
        if not self.uart:
            return
        
        try:
            # Read raw bytes
            data = self.uart.read(32)
            if not data:
                return
            
            self.byte_count += len(data)
            
            # Convert to string
            try:
                text = data.decode('utf-8')
            except:
                text = data.decode('utf-8', 'replace')
            
            # Add to buffer
            self.buffer += text
            
            # Process complete lines
            while '\n' in self.buffer:
                line, self.buffer = self.buffer.split('\n', 1)
                line = line.strip('\r\n ')
                
                if line:  # Skip empty lines
                    self.line_count += 1
                    print(f"RX: {line}")
                    
                    # Add to display lines
                    self.lines.append(line)
                    if len(self.lines) > 8:  # Keep only last 8 lines
                        self.lines.pop(0)
            
            # Prevent buffer overflow
            if len(self.buffer) > 500:
                self.buffer = self.buffer[-250:]
                
        except Exception as e:
            print(f"Read error: {e}")
            self.buffer = ""
    
    def update_display(self):
        """Update the display"""
        if not self.display:
            return
        
        try:
            group = displayio.Group()
            
            # Background
            bg = Rect(0, 0, 240, 135, fill=0x000000)
            group.append(bg)
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="ESP32 MONITOR",
                color=0x00FFFF,
                x=5,
                y=10
            )
            group.append(title)
            
            # Stats
            stats = label.Label(
                terminalio.FONT,
                text=f"Bytes:{self.byte_count} Lines:{self.line_count}",
                color=0x888888,
                x=5,
                y=25
            )
            group.append(stats)
            
            # Data lines
            for i, line in enumerate(self.lines):
                y_pos = 40 + (i * 12)
                
                # Truncate long lines
                display_line = line
                if len(display_line) > 35:
                    display_line = display_line[:32] + "..."
                
                line_label = label.Label(
                    terminalio.FONT,
                    text=display_line,
                    color=0xFFFFFF,
                    x=5,
                    y=y_pos
                )
                group.append(line_label)
            
            # Status
            status_text = "ACTIVE" if self.byte_count > 0 else "WAITING"
            status_color = 0x00FF00 if self.byte_count > 0 else 0xFF0000
            
            status = label.Label(
                terminalio.FONT,
                text=status_text,
                color=status_color,
                x=5,
                y=125
            )
            group.append(status)
            
            self.display.root_group = group
            
        except Exception as e:
            print(f"Display error: {e}")
    
    def run(self):
        """Main monitoring loop"""
        if not self.uart:
            print("UART not available - cannot monitor")
            return
        
        print("Starting monitoring...")
        print("Connect ESP32-WROOM:")
        print("  S3-RX <-- WROOM-TX")
        print("  S3-TX --> WROOM-RX") 
        print("  GND <--> GND")
        print("Press Ctrl+C to stop")
        
        last_update = 0
        
        try:
            while True:
                current_time = time.monotonic()
                
                # Read data
                self.read_data()
                
                # Update display every 200ms
                if current_time - last_update > 0.2:
                    self.update_display()
                    last_update = current_time
                
                # Memory cleanup every 10 seconds
                if int(current_time) % 10 == 0:
                    gc.collect()
                
                time.sleep(0.05)  # 50ms delay
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            print(f"\nMonitoring error: {e}")
        finally:
            try:
                if self.uart:
                    self.uart.deinit()
                print("Cleanup complete")
            except:
                pass


def test_uart_only():
    """Test UART without display"""
    print("Testing UART only...")
    
    try:
        uart = busio.UART(
            tx=board.TX,
            rx=board.RX,
            baudrate=115200,
            timeout=0.5
        )
        
        print("UART initialized - reading for 10 seconds...")
        start_time = time.monotonic()
        
        while time.monotonic() - start_time < 10:
            data = uart.read(32)
            if data:
                try:
                    text = data.decode('utf-8', 'replace')
                    print(f"Data: {repr(text)}")
                except Exception as e:
                    print(f"Decode error: {e}")
                    print(f"Raw: {data}")
            
            time.sleep(0.1)
        
        uart.deinit()
        print("UART test complete")
        
    except Exception as e:
        print(f"UART test failed: {e}")


def test_display_only():
    """Test display without UART"""
    print("Testing display only...")
    
    try:
        display = board.DISPLAY
        
        group = displayio.Group()
        
        bg = Rect(0, 0, 240, 135, fill=0x000000)
        group.append(bg)
        
        title = label.Label(
            terminalio.FONT,
            text="DISPLAY TEST",
            color=0x00FFFF,
            x=50,
            y=50
        )
        group.append(title)
        
        message = label.Label(
            terminalio.FONT,
            text="Display working OK",
            color=0xFFFFFF,
            x=30,
            y=70
        )
        group.append(message)
        
        display.root_group = group
        
        print("Display test - check screen")
        time.sleep(5)
        
        print("Display test complete")
        
    except Exception as e:
        print(f"Display test failed: {e}")


def quick_start():
    """Quick start with error handling"""
    print("Quick Start ESP32 Monitor")
    print("=" * 30)
    
    try:
        # Test components first
        print("1. Testing display...")
        test_display_only()
        
        print("2. Testing UART...")
        test_uart_only()
        
        print("3. Starting monitor...")
        monitor = SimpleESP32Monitor(115200)
        monitor.run()
        
    except Exception as e:
        print(f"Quick start failed: {e}")


def main():
    """Main function with fallbacks"""
    try:
        print("ESP32 Serial Monitor Starting...")
        
        # Try simple monitor first
        monitor = SimpleESP32Monitor(115200)
        if monitor.uart:
            monitor.run()
        else:
            print("Monitor failed to initialize")
            
    except Exception as e:
        print(f"Main error: {e}")
        print("Trying fallback...")
        test_uart_only()


# Auto-run
if __name__ == "__main__":
    main()
else:
    print("ESP32 Monitor loaded")
    print("Functions available:")
    print("- main() - Start monitor")
    print("- quick_start() - Test and start")
    print("- test_uart_only() - Test UART")
    print("- test_display_only() - Test display")
