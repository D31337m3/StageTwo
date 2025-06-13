import time
import board
import displayio
from digitalio import DigitalInOut, Direction

class TFTBlinky:
    """
    A class to handle display backlight blinking while preserving display functionality.
    """
    
    def __init__(self):
        """Initialize the backlight controller and detect the appropriate control method."""
        self.display = None
        self.backlight = None
        self.control_method = None
        self.original_brightness = None
        
        # Try to get the built-in display
        try:
            self.display = board.DISPLAY
            
            # Check if display has brightness control
            if hasattr(self.display, 'brightness'):
                self.control_method = "brightness"
                self.original_brightness = self.display.brightness
                print("Using display brightness control")
            else:
                # Try common backlight pin names
                backlight_pins = ['DISPLAY_BACKLIGHT', 'TFT_BACKLIGHT', 'BACKLIGHT']
                for pin_name in backlight_pins:
                    if hasattr(board, pin_name):
                        self.backlight = DigitalInOut(getattr(board, pin_name))
                        self.backlight.direction = Direction.OUTPUT
                        self.control_method = "pin"
                        self.original_state = self.backlight.value
                        print(f"Using {pin_name} pin for backlight control")
                        break
                
                if not self.control_method:
                    print("Could not find backlight control method. Please check your board documentation.")
        except (AttributeError, TypeError):
            print("No built-in display detected.")
    
    def set_backlight(self, state):
        """Set the backlight to on or off.
        
        Args:
            state (bool): True for on, False for off
        """
        if self.control_method == "brightness":
            self.display.brightness = 1.0 if state else 0.0
        elif self.control_method == "pin":
            self.backlight.value = state
        return state
    
    def blink(self, count=5, on_time=1.0, off_time=1.0):
        """Blink the backlight a specified number of times.
        
        Args:
            count (int): Number of times to blink
            on_time (float): Time in seconds to keep backlight on
            off_time (float): Time in seconds to keep backlight off
        """
        if not self.control_method:
            print("No backlight control method available")
            return
            
        for i in range(count):
            self.set_backlight(True)
           # print("Backlight ON")
            time.sleep(on_time)
            
            self.set_backlight(False)
           # print("Backlight OFF")
            time.sleep(off_time)
        
        # Restore original state
        self.restore_original_state()
        
    def restore_original_state(self):
        """Restore the original backlight state."""
        if self.control_method == "brightness" and self.original_brightness is not None:
            self.display.brightness = self.original_brightness
            print(f"Restored original brightness: {self.original_brightness}")
        elif self.control_method == "pin" and hasattr(self, 'original_state'):
            self.backlight.value = self.original_state
            print(f"Restored original backlight state: {self.original_state}")


# Example usage
if __name__ == "__main__":
    # No need to release displays, the class handles detection without disrupting
    backlight_controller = TFTBlinky()
    
    # Blink 5 times with 0.5 seconds on and 0.5 seconds off
    backlight_controller.blink(count=5, on_time=0.5, off_time=0.5)
    
    # The class will automatically restore the original backlight state
    print("Blinking complete, display restored to original state")