"""
Trippy Time Screensaver
Simple colorful time display with psychedelic effects
Compatible with Circuit Python runtimes

(C) 2025 StageTwo Team
"""

import board
import displayio
import terminalio
import digitalio
import time
import math
import random
import gc
from adafruit_display_text import label

# Version info
__version__ = "1.0"
__author__ = "StageTwo Team"

class TrippyTimeScreensaver:
    """Trippy time screensaver with colorful effects"""
    
    def __init__(self):
        gc.collect()
        
        self.display = None
        self.button = None
        self.running = False
        self.return_callback = None
        
        # Setup hardware
        self._setup_display()
        self._setup_button()
        
        # Display dimensions
        self.width = self.display.width if self.display else 240
        self.height = self.display.height if self.display else 135
        
        # Animation properties
        self.frame_count = 0
        self.last_time_update = 0
        self.time_string = "12:00:00"
        
        # Color cycling
        self.hue_offset = 0
        self.color_speed = 3
        
        # Position animation
        self.time_x = self.width // 2
        self.time_y = self.height // 2
        self.orbit_radius = 30
        self.orbit_speed = 2
        
        # Background effects
        self.bg_hue = 0
        self.bg_pulse = 0
        
        # Particle effects
        self.particles = []
        self.max_particles = 8
        
        gc.collect()
    
    def _setup_display(self):
        """Initialize display"""
        try:
            if hasattr(board, 'DISPLAY') and board.DISPLAY:
                self.display = board.DISPLAY
            else:
                self.display = None
        except Exception as e:
            print(f"Display setup error: {e}")
            self.display = None
    
    def _setup_button(self):
        """Initialize button for exit"""
        try:
            if hasattr(board, 'BUTTON'):
                self.button = digitalio.DigitalInOut(board.BUTTON)
                self.button.direction = digitalio.Direction.INPUT
                self.button.pull = digitalio.Pull.UP
            else:
                self.button = None
        except Exception as e:
            print(f"Button setup error: {e}")
            self.button = None
    
    def _get_current_time(self):
        """Get current time in 12-hour format"""
        try:
            current_time = time.localtime()
            hour = current_time.tm_hour
            minute = current_time.tm_min
            second = current_time.tm_sec
            
            # Convert to 12-hour format
            am_pm = "AM"
            if hour >= 12:
                am_pm = "PM"
                if hour > 12:
                    hour -= 12
            elif hour == 0:
                hour = 12
            
            return f"{hour:2d}:{minute:02d}:{second:02d} {am_pm}"
            
        except Exception:
            # Fallback to monotonic time
            mono_time = int(time.monotonic())
            hours = (mono_time // 3600) % 12
            if hours == 0:
                hours = 12
            minutes = (mono_time // 60) % 60
            seconds = mono_time % 60
            return f"{hours:2d}:{minutes:02d}:{seconds:02d} ??"
    
    def _hue_to_rgb(self, hue, saturation=1.0, value=1.0):
        """Convert HSV to RGB color"""
        hue = hue % 360
        c = value * saturation
        x = c * (1 - abs((hue / 60) % 2 - 1))
        m = value - c
        
        if hue < 60:
            r, g, b = c, x, 0
        elif hue < 120:
            r, g, b = x, c, 0
        elif hue < 180:
            r, g, b = 0, c, x
        elif hue < 240:
            r, g, b = 0, x, c
        elif hue < 300:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        
        r = int((r + m) * 255)
        g = int((g + m) * 255)
        b = int((b + m) * 255)
        
        return (r << 16) | (g << 8) | b
    
    def _update_particles(self):
        """Update particle system"""
        # Add new particles
        while len(self.particles) < self.max_particles:
            particle = {
                'x': random.randint(0, self.width),
                'y': random.randint(0, self.height),
                'vx': random.uniform(-1, 1),
                'vy': random.uniform(-1, 1),
                'hue': random.randint(0, 360),
                'life': random.randint(30, 60)
            }
            self.particles.append(particle)
        
        # Update existing particles
        for particle in self.particles[:]:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            particle['life'] -= 1
            particle['hue'] = (particle['hue'] + 5) % 360
            
            # Bounce off edges
            if particle['x'] <= 0 or particle['x'] >= self.width:
                particle['vx'] = -particle['vx']
                particle['x'] = max(0, min(particle['x'], self.width))
            
            if particle['y'] <= 0 or particle['y'] >= self.height:
                particle['vy'] = -particle['vy']
                particle['y'] = max(0, min(particle['y'], self.height))
            
            # Remove dead particles
            if particle['life'] <= 0:
                self.particles.remove(particle)
    
    def _create_background(self):
        """Create animated background"""
        bg_group = displayio.Group()
        
        try:
            # Animated background color
            self.bg_hue = (self.bg_hue + 1) % 360
            self.bg_pulse = (self.bg_pulse + 3) % 360
            
            # Pulsing background brightness
            pulse_brightness = 0.1 + 0.05 * math.sin(math.radians(self.bg_pulse))
            bg_color = self._hue_to_rgb(self.bg_hue, 0.3, pulse_brightness)
            
            # Create background
            bg_bitmap = displayio.Bitmap(self.width, self.height, 1)
            bg_palette = displayio.Palette(1)
            bg_palette[0] = bg_color
            bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
            bg_group.append(bg_sprite)
            
        except Exception as e:
            print(f"Background creation error: {e}")
        
        return bg_group
    
    def _create_particles(self):
        """Create particle effects"""
        particle_group = displayio.Group()
        
        try:
            self._update_particles()
            
            for particle in self.particles:
                # Create particle as colored dot
                particle_color = self._hue_to_rgb(particle['hue'], 1.0, 0.8)
                
                particle_label = label.Label(
                    terminalio.FONT,
                    text="*",
                    color=particle_color,
                    x=int(particle['x']),
                    y=int(particle['y'])
                )
                particle_group.append(particle_label)
                
        except Exception as e:
            print(f"Particle creation error: {e}")
        
        return particle_group
    
    def _create_time_display(self):
        """Create the trippy time display"""
        time_group = displayio.Group()
        
        try:
            # Update time every second
            current_time = time.monotonic()
            if current_time - self.last_time_update >= 1.0:
                self.time_string = self._get_current_time()
                self.last_time_update = current_time
            
            # Orbital motion for time position
            orbit_angle = (self.frame_count * self.orbit_speed) % 360
            center_x = self.width // 2
            center_y = self.height // 2
            
            self.time_x = center_x + int(self.orbit_radius * math.cos(math.radians(orbit_angle)))
            self.time_y = center_y + int(self.orbit_radius * math.sin(math.radians(orbit_angle)))
            
            # Create multiple colored time displays for trippy effect
            for i in range(3):
                # Different hues for each layer
                layer_hue = (self.hue_offset + i * 120) % 360
                layer_color = self._hue_to_rgb(layer_hue, 1.0, 0.9)
                
                # Slight offset for each layer
                offset_x = i * 2
                offset_y = i * 2
                
                time_label = label.Label(
                    terminalio.FONT,
                    text=self.time_string,
                    color=layer_color,
                    x=self.time_x + offset_x - len(self.time_string) * 3,
                    y=self.time_y + offset_y,
                    scale=2
                )
                time_group.append(time_label)
            
            # Update color cycling
            self.hue_offset = (self.hue_offset + self.color_speed) % 360
            
        except Exception as e:
            print(f"Time display creation error: {e}")
        
        return time_group
    
    def _create_effects(self):
        """Create additional visual effects"""
        effects_group = displayio.Group()
        
        try:
            # Corner sparkles
            for corner in [(10, 10), (self.width-20, 10), (10, self.height-20), (self.width-20, self.height-20)]:
                sparkle_hue = (self.hue_offset + self.frame_count * 5) % 360
                sparkle_color = self._hue_to_rgb(sparkle_hue, 1.0, 0.6)
                
                sparkle_char = "*" if (self.frame_count // 10) % 2 else "+"
                
                sparkle_label = label.Label(
                    terminalio.FONT,
                    text=sparkle_char,
                    color=sparkle_color,
                    x=corner[0],
                    y=corner[1]
                )
                effects_group.append(sparkle_label)
            
            # Pulsing border dots
            border_dots = 8
            for i in range(border_dots):
                angle = (360 / border_dots) * i + (self.frame_count * 2)
                border_hue = (angle + self.hue_offset) % 360
                border_color = self._hue_to_rgb(border_hue, 1.0, 0.7)
                
                # Position dots around screen border
                if i < border_dots // 4:
                    dot_x = int((self.width / (border_dots // 4)) * i)
                    dot_y = 5
                elif i < border_dots // 2:
                    dot_x = self.width - 5
                    dot_y = int((self.height / (border_dots // 4)) * (i - border_dots // 4))
                elif i < 3 * border_dots // 4:
                    dot_x = self.width - int((self.width / (border_dots // 4)) * (i - border_dots // 2))
                    dot_y = self.height - 5
                else:
                    dot_x = 5
                    dot_y = self.height - int((self.height / (border_dots // 4)) * (i - 3 * border_dots // 4))
                
                dot_label = label.Label(
                    terminalio.FONT,
                    text="•",
                    color=border_color,
                    x=dot_x,
                    y=dot_y
                )
                effects_group.append(dot_label)
                
        except Exception as e:
            print(f"Effects creation error: {e}")
        
        return effects_group
    
    def _check_exit_condition(self):
        """Check if user wants to exit"""
        if self.button:
            try:
                if not self.button.value:  # Button pressed (active low)
                    return True
            except:
                pass
        return False
    
    def start(self, return_callback=None):
        """Start the screensaver"""
        if not self.display:
            print("Cannot start screensaver - no display available")
            return False
        
        self.return_callback = return_callback
        self.running = True
        self.frame_count = 0
        
        # Initial cleanup
        gc.collect()
        
        try:
            while self.running:
                # Create display groups
                main_group = displayio.Group()
                
                # Add background
                bg_group = self._create_background()
                main_group.append(bg_group)
                
                # Add particles
                particle_group = self._create_particles()
                main_group.append(particle_group)
                
                # Add effects
                effects_group = self._create_effects()
                main_group.append(effects_group)
                
                # Add time display (on top)
                time_group = self._create_time_display()
                main_group.append(time_group)
                
                # Update display
                self.display.root_group = main_group
                
                # Check for exit
                if self._check_exit_condition():
                    break
                
                # Frame timing
                self.frame_count += 1
                time.sleep(0.05)  # 20 FPS for smooth animation
                
                # Periodic cleanup
                if self.frame_count % 200 == 0:  # Every 10 seconds
                    gc.collect()
            
        except KeyboardInterrupt:
            print("Screensaver interrupted")
        except Exception as e:
            print(f"Screensaver error: {e}")
        
        finally:
            self.stop()
        
        return True
    
    def stop(self):
        """Stop the screensaver"""
        self.running = False
        
        try:
            # Clear display
            if self.display:
                empty_group = displayio.Group()
                self.display.root_group = empty_group
            
            # Final cleanup
            gc.collect()
            print("Trippy screensaver stopped")
            
            # Call return callback if provided
            if self.return_callback:
                self.return_callback()
            
        except Exception as e:
            print(f"Screensaver stop error: {e}")
def start_screensaver(return_callback=None):
    """Start the trippy screensaver"""
    gc.collect()
    screensaver = TrippyTimeScreensaver()
    return screensaver.start(return_callback)

def main():
    """Main function for direct execution"""
    try:
        print("🌈 Trippy Time Screensaver")
        print(f"📋 Version: {__version__}")
        print("=" * 40)
        
        # Check display
        if not (hasattr(board, 'DISPLAY') and board.DISPLAY):
            print("❌ No display available")
            return False
        
        # Check button
        if not hasattr(board, 'BUTTON'):
            print("⚠️ No button - use Ctrl+C to stop")
        
        # Start screensaver
        screensaver = TrippyTimeScreensaver()
        success = screensaver.start()
        
        if success:
            print("✅ Screensaver completed")
        else:
            print("❌ Screensaver failed")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    main()

# Export main classes and functions
__all__ = [
    'TrippyTimeScreensaver',
    'start_screensaver',
    'main'
]


