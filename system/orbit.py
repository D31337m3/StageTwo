"""
@name: Satellite Orbit Animation
@description: Satellite orbiting Earth viewed from Moon perspective
@version: 1.0
@author: Animation Demo
@category: Demos
"""

import board
import displayio
import time
import math
from adafruit_display_shapes.circle import Circle
from adafruit_display_shapes.rect import Rect
import digitalio
import supervisor
import gc

class SatelliteOrbitAnimation:
    """Satellite orbiting Earth animation from Moon's perspective"""
    
    def __init__(self):
        self.display = board.DISPLAY
        self.display.auto_refresh = True
        
        # Initialize button for exit
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
        except:
            self.button = None
        
        # Animation parameters
        self.center_x = 120  # Center of display
        self.center_y = 67
        
        # Earth parameters
        self.earth_radius = 35
        self.earth_color = 0x4169E1  # Royal Blue
        
        # Satellite parameters
        self.satellite_radius = 3
        self.satellite_color = 0xFFFFFF  # White
        self.orbit_radius = 55  # Distance from Earth center
        
        # Animation state
        self.angle = 0
        self.speed = 0.08  # Radians per frame
        
        # Stars for background
        self.stars = []
        self.generate_stars()
        
        # Animation control
        self.running = True
        self.frame_count = 0
        
    def generate_stars(self):
        """Generate random stars for background"""
        import random
        
        self.stars = []
        for _ in range(30):
            # Avoid placing stars too close to Earth
            while True:
                x = random.randint(5, 235)
                y = random.randint(5, 130)
                
                # Check distance from Earth center
                dist = math.sqrt((x - self.center_x)**2 + (y - self.center_y)**2)
                if dist > self.earth_radius + 25:  # Give some buffer around Earth
                    self.stars.append((x, y))
                    break
    
    def create_frame(self):
        """Create a single animation frame"""
        try:
            # Create display group
            group = displayio.Group()
            
            # Black space background
            background = Rect(0, 0, 240, 135, fill=0x000000)
            group.append(background)
            
            # Add stars
            for star_x, star_y in self.stars:
                # Vary star brightness
                brightness = 0x444444 if (star_x + star_y) % 3 == 0 else 0x888888
                star = Circle(star_x, star_y, 1, fill=brightness)
                group.append(star)
            
            # Add Earth
            earth = Circle(self.center_x, self.center_y, self.earth_radius, fill=self.earth_color)
            group.append(earth)
            
            # Add Earth's atmosphere glow (optional)
            atmosphere = Circle(self.center_x, self.center_y, self.earth_radius + 2, 
                              fill=0x87CEEB, outline=0x87CEEB)
            group.append(atmosphere)
            
            # Re-add Earth on top
            earth = Circle(self.center_x, self.center_y, self.earth_radius, fill=self.earth_color)
            group.append(earth)
            
            # Add some Earth surface features (continents)
            self.add_earth_features(group)
            
            # Calculate satellite position
            sat_x = self.center_x + int(self.orbit_radius * math.cos(self.angle))
            sat_y = self.center_y + int(self.orbit_radius * math.sin(self.angle))
            
            # Add satellite
            satellite = Circle(sat_x, sat_y, self.satellite_radius, fill=self.satellite_color)
            group.append(satellite)
            
            # Add satellite solar panels (small rectangles)
            panel_offset = 6
            panel_width = 8
            panel_height = 2
            
            # Calculate panel positions (perpendicular to orbit direction)
            panel_angle = self.angle + math.pi/2
            panel_dx = int(panel_offset * math.cos(panel_angle))
            panel_dy = int(panel_offset * math.sin(panel_angle))
            
            # Left panel
            left_panel = Rect(
                sat_x + panel_dx - panel_width//2,
                sat_y + panel_dy - panel_height//2,
                panel_width, panel_height,
                fill=0x4169E1
            )
            group.append(left_panel)
            
            # Right panel
            right_panel = Rect(
                sat_x - panel_dx - panel_width//2,
                sat_y - panel_dy - panel_height//2,
                panel_width, panel_height,
                fill=0x4169E1
            )
            group.append(right_panel)
            
            # Add orbit path (faint circle)
            if self.frame_count % 60 < 30:  # Blink orbit path
                self.add_orbit_path(group)
            
            # Add title and info
            self.add_info_text(group)
            
            return group
            
        except Exception as e:
            print(f"Frame creation error: {e}")
            return displayio.Group()
    
    def add_earth_features(self, group):
        """Add simple continent features to Earth"""
        try:
            # Simple continent shapes (very basic)
            # North America-ish
            continent1 = Circle(self.center_x - 10, self.center_y - 8, 8, fill=0x228B22)
            group.append(continent1)
            
            # Europe/Africa-ish
            continent2 = Circle(self.center_x + 5, self.center_y - 5, 6, fill=0x228B22)
            group.append(continent2)
            
            # Asia-ish
            continent3 = Circle(self.center_x + 12, self.center_y + 8, 7, fill=0x228B22)
            group.append(continent3)
            
        except Exception as e:
            print(f"Earth features error: {e}")
    
    def add_orbit_path(self, group):
        """Add orbit path visualization"""
        try:
            # Draw orbit path as series of small dots
            num_dots = 24
            for i in range(num_dots):
                dot_angle = (2 * math.pi * i) / num_dots
                dot_x = self.center_x + int(self.orbit_radius * math.cos(dot_angle))
                dot_y = self.center_y + int(self.orbit_radius * math.sin(dot_angle))
                
                # Only draw dots that aren't behind Earth
                dist_from_earth = math.sqrt((dot_x - self.center_x)**2 + (dot_y - self.center_y)**2)
                if dist_from_earth > self.earth_radius + 3:
                    dot = Circle(dot_x, dot_y, 1, fill=0x444444)
                    group.append(dot)
                    
        except Exception as e:
            print(f"Orbit path error: {e}")
    
    def add_info_text(self, group):
        """Add information text"""
        try:
            import terminalio
            from adafruit_display_text import label
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="SATELLITE ORBIT",
                color=0xFFFFFF,
                x=5,
                y=10
            )
            group.append(title)
            
            # View info
            view_info = label.Label(
                terminalio.FONT,
                text="View: From Moon",
                color=0xAAAAAA,
                x=5,
                y=25
            )
            group.append(view_info)
            
            # Orbital period info
            period_text = f"Period: {int(self.frame_count / 10)}s"
            period_label = label.Label(
                terminalio.FONT,
                text=period_text,
                color=0xAAAAAA,
                x=150,
                y=10
            )
            group.append(period_label)
            
            # Exit instruction
            exit_text = label.Label(
                terminalio.FONT,
                text="Button: Exit",
                color=0x666666,
                x=5,
                y=125
            )
            group.append(exit_text)
            
        except Exception as e:
            print(f"Info text error: {e}")
    
    def update_animation(self):
        """Update animation state"""
        try:
            # Update satellite angle
            self.angle += self.speed
            
            # Keep angle in range [0, 2π]
            if self.angle >= 2 * math.pi:
                self.angle -= 2 * math.pi
            
            # Update frame counter
            self.frame_count += 1
            
            # Vary speed slightly for more realistic motion
            if self.frame_count % 120 == 0:
                self.speed = 0.08 + (math.sin(self.frame_count / 100) * 0.02)
            
        except Exception as e:
            print(f"Animation update error: {e}")
    
    def check_input(self):
        """Check for user input"""
        try:
            if self.button and not self.button.value:
                self.running = False
                return True
            return False
        except Exception as e:
            print(f"Input check error: {e}")
            return False
    
    def run(self):
        """Run the animation"""
        print("Starting Satellite Orbit Animation")
        print("View: Earth from Moon's perspective")
        print("Press button to exit")
        
        try:
            while self.running:
                # Check for exit
                if self.check_input():
                    break
                
                # Create and display frame
                frame = self.create_frame()
                self.display.root_group = frame
                
                # Update animation
                self.update_animation()
                
                # Control frame rate
                time.sleep(0.1)  # ~10 FPS
                
                # Memory management
                if self.frame_count % 100 == 0:
                    gc.collect()
                
                # Auto-exit after a while to prevent infinite loop
                if self.frame_count > 3000:  # About 5 minutes
                    print("Auto-exit after timeout")
                    break
            
        except KeyboardInterrupt:
            print("Animation interrupted")
        except Exception as e:
            print(f"Animation error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Clear display
            self.display.root_group = displayio.Group()
            
            # Force garbage collection
            gc.collect()
            
            print("Satellite orbit animation ended")
            print(f"Total frames: {self.frame_count}")
            
        except Exception as e:
            print(f"Cleanup error: {e}")


def main():
    """Main function"""
    try:
        # Show startup message
        print("=" * 40)
        print("SATELLITE ORBIT ANIMATION")
        print("=" * 40)
        print("Satellite orbiting Earth")
        print("Perspective: View from Moon")
        print("Press button to exit")
        print("=" * 40)
        
        # Create and run animation
        animation = SatelliteOrbitAnimation()
        animation.run()
        
        # Return to loader
        print("Returning to system...")
        time.sleep(1)
        
        # Try to return to loader
        try:
            supervisor.set_next_code_file("/lib/system/loader.py")
            supervisor.reload()
        except:
            try:
                supervisor.set_next_code_file("/boot.py")
                supervisor.reload()
            except:
                print("Could not return to system")
        
    except Exception as e:
        print(f"Main error: {e}")
        time.sleep(3)


# Enhanced version with more features
class AdvancedSatelliteAnimation(SatelliteOrbitAnimation):
    """Advanced version with multiple satellites and features"""
    
    def __init__(self):
        super().__init__()
        
        # Multiple satellites
        self.satellites = [
            {"angle": 0, "radius": 55, "speed": 0.08, "color": 0xFFFFFF, "name": "ISS"},
            {"angle": math.pi, "radius": 65, "speed": 0.06, "color": 0xFF6600, "name": "HST"},
            {"angle": math.pi/2, "radius": 45, "speed": 0.12, "color": 0x00FF00, "name": "GPS"}
        ]
        
        # Moon in background
        self.show_moon = True
        self.moon_x = 200
        self.moon_y = 30
        self.moon_radius = 15
    
    def create_frame(self):
        """Create advanced frame with multiple satellites"""
        try:
            group = displayio.Group()
            
            # Background
            background = Rect(0, 0, 240, 135, fill=0x000011)
            group.append(background)
            
            # Add stars
            for star_x, star_y in self.stars:
                brightness = 0x333333 if (star_x + star_y) % 3 == 0 else 0x666666
                star = Circle(star_x, star_y, 1, fill=brightness)
                group.append(star)
            
            # Add Moon in background
            if self.show_moon:
                moon = Circle(self.moon_x, self.moon_y, self.moon_radius, fill=0xC0C0C0)
                group.append(moon)
                
                # Moon craters
                crater1 = Circle(self.moon_x - 3, self.moon_y - 2, 2, fill=0x808080)
                crater2 = Circle(self.moon_x + 2, self.moon_y + 3, 1, fill=0x808080)
                group.append(crater1)
                group.append(crater2)
            
            # Add Earth with atmosphere
            atmosphere = Circle(self.center_x, self.center_y, self.earth_radius + 3, 
                              fill=0x87CEEB)
            group.append(atmosphere)
            
            earth = Circle(self.center_x, self.center_y, self.earth_radius, fill=self.earth_color)
            group.append(earth)
            
            # Earth features
            self.add_earth_features(group)
            
            # Add all satellites
            for i, sat in enumerate(self.satellites):
                sat_x = self.center_x + int(sat["radius"] * math.cos(sat["angle"]))
                sat_y = self.center_y + int(sat["radius"] * math.sin(sat["angle"]))
                
                # Satellite body
                satellite = Circle(sat_x, sat_y, 2, fill=sat["color"])
                group.append(satellite)
                
                # Solar panels for each satellite
                panel_angle = sat["angle"] + math.pi/2
                panel_dx = int(5 * math.cos(panel_angle))
                panel_dy = int(5 * math.sin(panel_angle))
                
                # Left panel
                left_panel = Rect(
                    sat_x + panel_dx - 3,
                    sat_y + panel_dy - 1,
                    6, 2,
                    fill=0x000080
                )
                group.append(left_panel)
                
                # Right panel
                right_panel = Rect(
                    sat_x - panel_dx - 3,
                    sat_y - panel_dy - 1,
                    6, 2,
                    fill=0x000080
                )
                group.append(right_panel)
                
                # Satellite trail (fading dots)
                self.add_satellite_trail(group, sat, i)
            
            # Add orbit paths
            if self.frame_count % 120 < 60:  # Show paths half the time
                for sat in self.satellites:
                    self.add_orbit_path_colored(group, sat["radius"], sat["color"])
            
            # Add advanced info
            self.add_advanced_info(group)
            
            return group
            
        except Exception as e:
            print(f"Advanced frame creation error: {e}")
            return super().create_frame()
    
    def add_satellite_trail(self, group, satellite, sat_index):
        """Add trailing dots behind satellite"""
        try:
            trail_length = 8
            for i in range(trail_length):
                trail_angle = satellite["angle"] - (i + 1) * satellite["speed"] * 2
                trail_x = self.center_x + int(satellite["radius"] * math.cos(trail_angle))
                trail_y = self.center_y + int(satellite["radius"] * math.sin(trail_angle))
                
                # Fade the trail
                alpha = max(0, 255 - (i * 32))
                trail_color = self.fade_color(satellite["color"], alpha)
                
                # Only draw if not behind Earth
                dist_from_earth = math.sqrt((trail_x - self.center_x)**2 + (trail_y - self.center_y)**2)
                if dist_from_earth > self.earth_radius + 2:
                    trail_dot = Circle(trail_x, trail_y, 1, fill=trail_color)
                    group.append(trail_dot)
                    
        except Exception as e:
            print(f"Trail error: {e}")
    
    def fade_color(self, color, alpha):
        """Fade a color by alpha amount"""
        try:
            # Simple color fading
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            
            fade_factor = alpha / 255.0
            r = int(r * fade_factor)
            g = int(g * fade_factor)
            b = int(b * fade_factor)
            
            return (r << 16) | (g << 8) | b
        except:
            return color
    
    def add_orbit_path_colored(self, group, radius, color):
        """Add colored orbit path"""
        try:
            num_dots = 32
            for i in range(num_dots):
                dot_angle = (2 * math.pi * i) / num_dots
                dot_x = self.center_x + int(radius * math.cos(dot_angle))
                dot_y = self.center_y + int(radius * math.sin(dot_angle))
                
                # Only draw dots that aren't behind Earth
                dist_from_earth = math.sqrt((dot_x - self.center_x)**2 + (dot_y - self.center_y)**2)
                if dist_from_earth > self.earth_radius + 3:
                    # Fade the orbit color
                    faded_color = self.fade_color(color, 64)
                    dot = Circle(dot_x, dot_y, 1, fill=faded_color)
                    group.append(dot)
                    
        except Exception as e:
            print(f"Colored orbit path error: {e}")
    
    def add_advanced_info(self, group):
        """Add advanced information display"""
        try:
            import terminalio
            from adafruit_display_text import label
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="EARTH ORBIT VIEW",
                color=0xFFFFFF,
                x=5,
                y=10
            )
            group.append(title)
            
            # Satellite count
            sat_count = label.Label(
                terminalio.FONT,
                text=f"Satellites: {len(self.satellites)}",
                color=0xAAAAAA,
                x=5,
                y=25
            )
            group.append(sat_count)
            
            # Current satellite info (cycle through them)
            current_sat_index = (self.frame_count // 60) % len(self.satellites)
            current_sat = self.satellites[current_sat_index]
            
            sat_info = label.Label(
                terminalio.FONT,
                text=f"Focus: {current_sat['name']}",
                color=current_sat['color'],
                x=130,
                y=10
            )
            group.append(sat_info)
            
            # Orbital info
            altitude = int(current_sat['radius'] - self.earth_radius) * 10  # Fake km
            orbital_info = label.Label(
                terminalio.FONT,
                text=f"Alt: {altitude}km",
                color=0xAAAAAA,
                x=130,
                y=25
            )
            group.append(orbital_info)
            
            # Time display
            mission_time = self.frame_count // 10
            time_info = label.Label(
                terminalio.FONT,
                text=f"T+{mission_time:03d}s",
                color=0x00FF00,
                x=180,
                y=125
            )
            group.append(time_info)
            
            # Exit instruction
            exit_text = label.Label(
                terminalio.FONT,
                text="Button: Exit",
                color=0x666666,
                x=5,
                y=125
            )
            group.append(exit_text)
            
        except Exception as e:
            print(f"Advanced info error: {e}")
    
    def update_animation(self):
        """Update advanced animation state"""
        try:
            # Update all satellites
            for sat in self.satellites:
                sat["angle"] += sat["speed"]
                
                # Keep angle in range
                if sat["angle"] >= 2 * math.pi:
                    sat["angle"] -= 2 * math.pi
            
            # Update frame counter
            self.frame_count += 1
            
            # Occasionally adjust satellite speeds for realism
            if self.frame_count % 200 == 0:
                for sat in self.satellites:
                    variation = math.sin(self.frame_count / 150) * 0.01
                    sat["speed"] = max(0.02, sat["speed"] + variation)
            
        except Exception as e:
            print(f"Advanced animation update error: {e}")


# Simple demo mode
class SimpleSatelliteDemo:
    """Simplified version for demonstration"""
    
    def __init__(self):
        self.display = board.DISPLAY
        self.display.auto_refresh = True
        
        # Simple parameters
        self.earth_x = 120
        self.earth_y = 67
        self.earth_radius = 30
        self.sat_angle = 0
        self.sat_distance = 45
        
    def run_demo(self, duration=30):
        """Run a simple demo for specified duration"""
        print(f"Running satellite demo for {duration} seconds...")
        
        start_time = time.monotonic()
        
        try:
            while time.monotonic() - start_time < duration:
                # Create simple frame
                group = displayio.Group()
                
                # Black background
                bg = Rect(0, 0, 240, 135, fill=0x000000)
                group.append(bg)
                
                # Earth
                earth = Circle(self.earth_x, self.earth_y, self.earth_radius, fill=0x0066CC)
                group.append(earth)
                
                # Satellite position
                sat_x = self.earth_x + int(self.sat_distance * math.cos(self.sat_angle))
                sat_y = self.earth_y + int(self.sat_distance * math.sin(self.sat_angle))
                
                # Satellite
                satellite = Circle(sat_x, sat_y, 3, fill=0xFFFFFF)
                group.append(satellite)
                
                # Show frame
                self.display.root_group = group
                
                # Update
                self.sat_angle += 0.1
                if self.sat_angle >= 2 * math.pi:
                    self.sat_angle = 0
                
                time.sleep(0.1)
                
        except Exception as e:
            print(f"Demo error: {e}")
        finally:
            self.display.root_group = displayio.Group()
            print("Demo complete")


# Animation selection menu
def show_animation_menu():
    """Show menu to select animation type"""
    try:
        import terminalio
        from adafruit_display_text import label
        
        display = board.DISPLAY
        
        # Try to get button
        try:
            button = digitalio.DigitalInOut(board.BUTTON)
            button.direction = digitalio.Direction.INPUT
            button.pull = digitalio.Pull.UP
        except:
            button = None
        
        options = [
            "Simple Satellite",
            "Advanced Multi-Sat",
            "Quick Demo",
            "Exit"
        ]
        
        selected = 0
        
        while True:
            # Create menu
            group = displayio.Group()
            
            # Background
            bg = Rect(0, 0, 240, 135, fill=0x000033)
            group.append(bg)
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="SATELLITE ANIMATIONS",
                color=0xFFFFFF,
                x=50,
                y=20
            )
            group.append(title)
            
            # Menu options
            for i, option in enumerate(options):
                color = 0xFFFF00 if i == selected else 0xAAAAAA
                prefix = "> " if i == selected else "  "
                
                option_label = label.Label(
                    terminalio.FONT,
                    text=f"{prefix}{option}",
                    color=color,
                    x=20,
                    y=50 + (i * 15)
                )
                group.append(option_label)
            
            # Instructions
            instructions = label.Label(
                terminalio.FONT,
                text="Short: Next | Long: Select",
                color=0x666666,
                x=20,
                y=120
            )
            group.append(instructions)
            
            display.root_group = group
            
            # Handle input
            if button:
                button_pressed = False
                press_start = 0
                
                while True:
                    current_state = not button.value
                    current_time = time.monotonic()
                    
                    if current_state and not button_pressed:
                        button_pressed = True
                        press_start = current_time
                    elif not current_state and button_pressed:
                        button_pressed = False
                        press_duration = current_time - press_start
                        
                        if press_duration >= 1.0:  # Long press
                            return selected
                        else:  # Short press
                            selected = (selected + 1) % len(options)
                            break
                    
                    time.sleep(0.05)
            else:
                # Auto-select if no button
                time.sleep(3)
                return 0
                
    except Exception as e:
        print(f"Menu error: {e}")
        return 0


# Main execution
if __name__ == "__main__":
    main()
else:
    # Module loaded
    print("Satellite Orbit Animation module loaded")


# Additional utility functions
def quick_satellite_demo():
    """Quick satellite demonstration"""
    demo = SimpleSatelliteDemo()
    demo.run_demo(15)


def run_basic_animation():
    """Run basic satellite animation"""
    animation = SatelliteOrbitAnimation()
    animation.run()


def run_advanced_animation():
    """Run advanced multi-satellite animation"""
    animation = AdvancedSatelliteAnimation()
    animation.run()


# Export functions
__all__ = [
    'SatelliteOrbitAnimation',
    'AdvancedSatelliteAnimation', 
    'SimpleSatelliteDemo',
    'quick_satellite_demo',
    'run_basic_animation',
    'run_advanced_animation',
    'show_animation_menu',
    'main'
]


# Enhanced main function with menu
def main():
    """Enhanced main function with animation selection"""
    try:
        print("=" * 50)
        print("SATELLITE ORBIT ANIMATION SUITE")
        print("=" * 50)
        print("Multiple animation modes available")
        print("View: Earth from Moon's perspective")
        print("=" * 50)
        animation = AdvancedSatelliteAnimation()
        animation.run()
        # Show selection menu
        # Return to system
        print("Returning to system...")
        time.sleep(1)
        
        try:
            supervisor.set_next_code_file("/system/loader.py")
            supervisor.reload()
        except:
            try:
                supervisor.set_next_code_file("/boot.py")
                supervisor.reload()
            except:
                print("Could not return to system")
        
    except Exception as e:
        print(f"Main execution error: {e}")
        time.sleep(3)


# Performance monitoring
def get_animation_stats():
    """Get animation performance statistics"""
    try:
        import gc
        return {
            "free_memory": gc.mem_free(),
            "animation_types": len(__all__),
            "module_loaded": True
        }
    except:
        return {"error": "Stats unavailable"}


# Add stats function to exports
__all__.append('get_animation_stats')

print("Satellite Orbit Animation Suite loaded successfully")
print("Available modes: Simple, Advanced Multi-Satellite, Quick Demo")
print("Features: Earth view from Moon, multiple satellites, orbital trails")

# Memory cleanup
try:
    import gc
    gc.collect()
    print(f"Memory after module load: {gc.mem_free()} bytes free")
except:
    pass
