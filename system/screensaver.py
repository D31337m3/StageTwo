"""
StageTwo Clock Screensaver
Bouncing rainbow clock with day/night effects and real constellations
Compatable with Circuit python runtimes

(C) 2025 Devin Ranger

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
__version__ = "1.3"
__author__ = "StageTwo Team"

class ClockScreensaver:
    """Animated clock screensaver with day/night themes and real constellations"""
    
    def __init__(self):
        # Initial garbage collection
        gc.collect()
        
        self.display = None
        self.button = None
        self.running = False
        self.return_callback = None
        
        # Display setup
        self._setup_display()
        self._setup_button()
        
        # Clock properties
        self.clock_x = 50
        self.clock_y = 50
        self.velocity_x = 2
        self.velocity_y = 1
        self.color_hue = 0
        
        # Animation properties
        self.frame_count = 0
        self.last_time_update = 0
        self.time_string = "12:00:00 AM"  # Initialize with default value
        
        # Day/night properties
        self.is_daytime = True
        self.sun_angle = 0
        self.moon_phase = 0
        
        # Constellation properties
        self.constellations = self._define_constellations()
        self.current_constellation_index = 0
        self.constellation_alpha = 0.0  # 0.0 to 1.0 for fade effect
        self.constellation_phase = "fading_in"  # "fading_in", "visible", "fading_out"
        self.constellation_timer = 0
        self.constellation_start_time = 0
        
        # Constellation timing (in seconds)
        self.fade_in_duration = 8.0
        self.visible_duration = 35.0
        self.fade_out_duration = 8.0
        
        # Display dimensions
        self.width = self.display.width if self.display else 240
        self.height = self.display.height if self.display else 135
        
        # Force night mode for testing
        self.force_night_mode = False
        
        # Memory management
        gc.collect()
        
       
    
    def _setup_display(self):
        """Initialize display"""
        try:
            if hasattr(board, 'DISPLAY') and board.DISPLAY:
                self.display = board.DISPLAY
                # print("✅ Display available")
            else:
                # print("❌ No display available")
                self.display = None
        except Exception as e:
            # print(f"❌ Display setup error: {e}")
            self.display = None
    
    def _setup_button(self):
        """Initialize button for exit"""
        try:
            if hasattr(board, 'BUTTON'):
                self.button = digitalio.DigitalInOut(board.BUTTON)
                self.button.direction = digitalio.Direction.INPUT
                self.button.pull = digitalio.Pull.UP
                # print("✅ Button available for exit")
            else:
                # print("❌ No button available")
                self.button = None
        except Exception as e:
            # print(f"❌ Button setup error: {e}")
            self.button = None
    
    def _define_constellations(self):
        """Define constellation star patterns with accurate star positions and connections"""
        # Coordinates are relative to display size (0.0 to 1.0)
        # Brightness values: 255=brightest, 150=medium, 100=dim
        constellations = [
            {
                "name": "Big Dipper (Ursa Major)",
                "stars": [
                    # The actual Big Dipper shape - like a ladle/cup with handle
                    (0.15, 0.35, 255),  # Dubhe (cup corner)
                    (0.25, 0.45, 240),  # Merak (cup corner)
                    (0.35, 0.55, 220),  # Phecda (cup corner)
                    (0.45, 0.50, 255),  # Megrez (cup corner, handle start)
                    (0.55, 0.40, 230),  # Alioth (handle middle)
                    (0.65, 0.30, 210),  # Mizar (handle)
                    (0.75, 0.25, 200),  # Alkaid (handle end)
                ],
                "lines": [
                    # Cup/bowl of the dipper
                    (0, 1), (1, 2), (2, 3), (3, 0),  # Square cup
                    # Handle of the dipper
                    (3, 4), (4, 5), (5, 6)  # Curved handle
                ]
            },
            {
                "name": "Orion the Hunter",
                "stars": [
                    # Orion's distinctive shape with belt and shoulders
                    (0.35, 0.25, 255),  # Betelgeuse (left shoulder, red giant)
                    (0.65, 0.20, 240),  # Bellatrix (right shoulder)
                    (0.40, 0.45, 220),  # Alnitak (belt left)
                    (0.50, 0.47, 255),  # Alnilam (belt center, brightest)
                    (0.60, 0.49, 230),  # Mintaka (belt right)
                    (0.30, 0.70, 210),  # Saiph (left foot)
                    (0.70, 0.75, 250),  # Rigel (right foot, very bright)
                    (0.50, 0.60, 180),  # Orion Nebula area
                    # Additional stars for better shape
                    (0.25, 0.40, 150),  # Left arm star
                    (0.75, 0.35, 150),  # Right arm star
                ],
                "lines": [
                    # Shoulders
                    (0, 1),
                    # Left side (shoulder to belt to foot)
                    (0, 2), (2, 5),
                    # Right side (shoulder to belt to foot)
                    (1, 4), (4, 6),
                    # Belt (the three stars)
                    (2, 3), (3, 4),
                    # Sword (hanging from belt)
                    (3, 7),
                    # Arms
                    (0, 8), (1, 9)
                ]
            },
            {
                "name": "Cassiopeia the Queen",
                "stars": [
                    # The distinctive "W" or "M" shape
                    (0.15, 0.45, 240),  # Caph
                    (0.30, 0.25, 255),  # Schedar (brightest)
                    (0.50, 0.35, 230),  # Gamma Cas (center of W)
                    (0.70, 0.20, 220),  # Ruchbah
                    (0.85, 0.40, 210),  # Segin
                    # Additional fainter stars for completeness
                    (0.25, 0.50, 150),  # Additional star
                    (0.75, 0.50, 150),  # Additional star
                ],
                "lines": [
                    # Main W shape
                    (0, 1), (1, 2), (2, 3), (3, 4),
                    # Additional connections for fuller shape
                    (0, 5), (4, 6)
                ]
            },
            {
                "name": "Leo the Lion",
                "stars": [
                    # Leo with the distinctive "sickle" head and triangle body
                    (0.25, 0.40, 255),  # Regulus (heart of the lion, very bright)
                    (0.20, 0.25, 200),  # Eta Leonis (sickle top)
                    (0.30, 0.20, 220),  # Gamma Leonis (Algieba, sickle)
                    (0.40, 0.25, 180),  # Zeta Leonis (sickle)
                    (0.35, 0.35, 190),  # Mu Leonis (sickle)
                    (0.55, 0.45, 230),  # Zosma (back)
                    (0.75, 0.50, 240),  # Denebola (tail, bright)
                    (0.45, 0.55, 170),  # Theta Leonis (hind leg)
                    (0.35, 0.60, 160),  # Delta Leonis (hind leg)
                ],
                "lines": [
                    # Sickle (head and mane) - backwards question mark
                    (1, 2), (2, 3), (3, 4), (4, 0),
                    # Body triangle
                    (0, 5), (5, 6),
                    # Legs
                    (0, 7), (7, 8), (5, 7)
                ]
            },
            {
                "name": "Cygnus the Swan",
                "stars": [
                    # The Northern Cross / Swan flying south
                    (0.50, 0.20, 255),  # Deneb (tail, very bright)
                    (0.50, 0.35, 220),  # Sadr (center/body)
                    (0.50, 0.55, 200),  # Gienah (body)
                    (0.50, 0.70, 210),  # Albireo (head, double star)
                    (0.30, 0.35, 190),  # Left wing tip
                    (0.70, 0.35, 190),  # Right wing tip
                    (0.40, 0.30, 150),  # Left wing
                    (0.60, 0.30, 150),  # Right wing
                ],
                "lines": [
                    # Main cross body (north-south)
                    (0, 1), (1, 2), (2, 3),
                    # Wings (east-west)
                    (4, 1), (1, 5),
                    # Wing details
                    (4, 6), (5, 7), (6, 1), (7, 1)
                ]
            },
            {
                "name": "Scorpius the Scorpion",
                "stars": [
                    # Scorpion with curved tail and claws
                    (0.25, 0.40, 255),  # Antares (heart, red supergiant)
                    (0.20, 0.30, 200),  # Tau Scorpii (claw)
                    (0.15, 0.35, 180),  # Beta Scorpii (claw)
                    (0.30, 0.35, 190),  # Delta Scorpii (body)
                    (0.35, 0.45, 170),  # Pi Scorpii (body)
                    (0.45, 0.55, 160),  # Sigma Scorpii (tail start)
                    (0.55, 0.65, 150),  # Tail middle
                    (0.70, 0.70, 180),  # Tail curve
                    (0.80, 0.60, 200),  # Shaula (stinger)
                    (0.10, 0.25, 160),  # Extended claw
                ],
                "lines": [
                    # Claws
                    (9, 1), (1, 2), (2, 0),
                    # Body
                    (0, 3), (3, 4), (4, 5),
                    # Curved tail
                    (5, 6), (6, 7), (7, 8)
                ]
            }
        ]
        
        return constellations

    
    def _update_constellation_animation(self):
        """Update constellation fade animation"""
        current_time = time.monotonic()
        
        if self.constellation_start_time == 0:
            self.constellation_start_time = current_time
        
        elapsed = current_time - self.constellation_start_time
        
        if self.constellation_phase == "fading_in":
            # Fade in phase
            progress = elapsed / self.fade_in_duration
            self.constellation_alpha = min(1.0, progress)
            
            if progress >= 1.0:
                self.constellation_phase = "visible"
                self.constellation_start_time = current_time
                constellation_name = self.constellations[self.current_constellation_index]["name"]
                # print(f"⭐ Now showing: {constellation_name}")
        
        elif self.constellation_phase == "visible":
            # Visible phase
            self.constellation_alpha = 1.0
            
            if elapsed >= self.visible_duration:
                self.constellation_phase = "fading_out"
                self.constellation_start_time = current_time
        
        elif self.constellation_phase == "fading_out":
            # Fade out phase
            progress = elapsed / self.fade_out_duration
            self.constellation_alpha = max(0.0, 1.0 - progress)
            
            if progress >= 1.0:
                # Move to next constellation
                self.current_constellation_index = (self.current_constellation_index + 1) % len(self.constellations)
                self.constellation_phase = "fading_in"
                self.constellation_start_time = current_time
                self.constellation_alpha = 0.0
                
                # Garbage collection when switching constellations
                gc.collect()

    def _get_current_time(self):
        """Get current time in 12-hour format"""
        time_string = "12:00:00 AM"  # Default fallback
        
        try:
            current_time = time.localtime()
            hour = current_time.tm_hour
            minute = current_time.tm_min
          
            
            # Convert to 12-hour format
            am_pm = "AM"
            if hour >= 12:
                am_pm = "PM"
                if hour > 12:
                    hour -= 12
            elif hour == 0:
                hour = 12
            
            # Determine day/night (6 AM to 6 PM is day) - or force night for testing
            if self.force_night_mode:
                self.is_daytime = False
            else:
                self.is_daytime = 6 <= current_time.tm_hour < 18
            
            time_string = f"{hour:2d}:{minute:02d}:{am_pm}"
            
        except Exception as e:
            # print(f"Time error: {e}")
            # Fallback to monotonic time - force night mode for testing
            self.is_daytime = False if self.force_night_mode else True
            mono_time = int(time.monotonic())
            hours = (mono_time // 3600) % 12
            if hours == 0:
                hours = 12
            minutes = (mono_time // 60) % 60
            time_string = f"{hours:2d}:{minutes:02d} --"
        
        return time_string
    
    def _hue_to_rgb(self, hue):
        """Convert HSV hue to RGB color (simplified)"""
        hue = hue % 360
        
        if hue < 60:
            r, g, b = 255, int(255 * hue / 60), 0
        elif hue < 120:
            r, g, b = int(255 * (120 - hue) / 60), 255, 0
        elif hue < 180:
            r, g, b = 0, 255, int(255 * (hue - 120) / 60)
        elif hue < 240:
            r, g, b = 0, int(255 * (240 - hue) / 60), 255
        elif hue < 300:
            r, g, b = int(255 * (hue - 240) / 60), 0, 255
        else:
            r, g, b = 255, 0, int(255 * (360 - hue) / 60)
        
        return (r << 16) | (g << 8) | b
    
    def _update_clock_position(self):
        """Update bouncing clock position"""
        # Update position
        self.clock_x += self.velocity_x
        self.clock_y += self.velocity_y
        
        # Bounce off edges (account for text size)
        text_width = len(self.time_string) * 12  # Approximate text width
        text_height = 16  # Approximate text height
        
        if self.clock_x <= 0 or self.clock_x >= self.width - text_width:
            self.velocity_x = -self.velocity_x
            self.clock_x = max(0, min(self.clock_x, self.width - text_width))
        
        if self.clock_y <= text_height or self.clock_y >= self.height - 5:
            self.velocity_y = -self.velocity_y
            self.clock_y = max(text_height, min(self.clock_y, self.height - 5))
        
        # Update color (rainbow effect)
        self.color_hue = (self.color_hue + 2) % 360
    
    def _create_constellation_group(self):
        """Create constellation display group with better visibility"""
        constellation_group = displayio.Group()
        
        # Always show constellations in night mode or when forced
        if self.is_daytime and not self.force_night_mode:
            return constellation_group
        
        try:
            # Update constellation animation
            self._update_constellation_animation()
            
            if self.constellation_alpha <= 0:
                return constellation_group
            
            current_constellation = self.constellations[self.current_constellation_index]
            stars = current_constellation["stars"]
            lines = current_constellation.get("lines", [])
            
            # print(f"Drawing constellation: {current_constellation['name']}, alpha: {self.constellation_alpha:.2f}")
            
            # Create constellation lines first (behind stars)
            line_brightness = int(100 * self.constellation_alpha)  # Dimmer lines
            if line_brightness > 0:
                for line in lines:
                    start_idx, end_idx = line
                    if start_idx < len(stars) and end_idx < len(stars):
                        start_star = stars[start_idx]
                        end_star = stars[end_idx]
                        
                        # Convert relative coordinates to screen coordinates
                        x1 = int(start_star[0] * self.width)
                        y1 = int(start_star[1] * self.height)
                        x2 = int(end_star[0] * self.width)
                        y2 = int(end_star[1] * self.height)
                        
                        # Draw line using multiple dots
                        dx = x2 - x1
                        dy = y2 - y1
                        distance = max(abs(dx), abs(dy))
                        
                        if distance > 0:
                            for i in range(distance + 1):
                                t = i / distance if distance > 0 else 0
                                dot_x = int(x1 + t * dx)
                                dot_y = int(y1 + t * dy)
                                
                                if 0 <= dot_x < self.width and 0 <= dot_y < self.height:
                                    line_color_rgb = (line_brightness << 16) | (line_brightness << 8) | line_brightness
                                    
                                    dot_label = label.Label(
                                        terminalio.FONT,
                                        text=".",
                                        color=line_color_rgb,
                                        x=dot_x,
                                        y=dot_y
                                    )
                                    constellation_group.append(dot_label)
            
            # Create constellation stars with high visibility
            for i, star in enumerate(stars):
                x, y, brightness = star
                
                # Convert relative coordinates to screen coordinates
                screen_x = int(x * self.width)
                screen_y = int(y * self.height)
                
                # Ensure stars are within screen bounds
                screen_x = max(5, min(screen_x, self.width - 5))
                screen_y = max(15, min(screen_y, self.height - 15))
                
                # Calculate star brightness with constellation alpha
                base_brightness = int(brightness * self.constellation_alpha)
                
                # Add twinkling effect
                twinkle_factor = 0.8 + 0.4 * math.sin(self.frame_count * 0.15 + i * 1.2)
                final_brightness = min(255, int(base_brightness * twinkle_factor))
                
                # Ensure minimum visibility
                if final_brightness < 80:
                    final_brightness = 80
                
                # Create bright white/blue star color
                star_color = (final_brightness << 16) | (final_brightness << 8) | min(255, int(final_brightness * 1.1))
                
                # Use different symbols and scales for different brightnesses
                if final_brightness > 200:
                    star_symbol = "*"
                    star_scale = 2
                elif final_brightness > 150:
                    star_symbol = "*"
                    star_scale = 1
                else:
                    star_symbol = "."
                    star_scale = 1
                
                # Create star label
                star_label = label.Label(
                    terminalio.FONT,
                    text=star_symbol,
                    color=star_color,
                    x=screen_x,
                    y=screen_y,
                    scale=star_scale
                )
                constellation_group.append(star_label)
                
                # Add extra bright center for main stars
                if final_brightness > 180:
                    center_label = label.Label(
                        terminalio.FONT,
                        text="·",
                        color=0xFFFFFF,  # Pure white center
                        x=screen_x + 1,
                        y=screen_y,
                        scale=1
                    )
                    constellation_group.append(center_label)
            
            # Add constellation name with better visibility
            if self.constellation_alpha > 0.3:
                name_alpha = min(1.0, (self.constellation_alpha - 0.3) / 0.7)
                name_brightness = int(200 * name_alpha)
                name_color = (name_brightness << 16) | (name_brightness << 8) | min(255, int(name_brightness * 1.2))
                
                name_label = label.Label(
                    terminalio.FONT,
                    text=current_constellation["name"],
                    color=name_color,
                    x=5,
                    y=15,
                    scale=1
                )
                constellation_group.append(name_label)
            
            # print(f"Created {len(constellation_group)} constellation elements")
        
        except Exception as e:
            # print(f"Constellation creation error: {e}")
            import traceback
            traceback.print_exception()
        
        return constellation_group
    
    def _create_background_group(self):
        """Create background with day/night theme"""
        bg_group = displayio.Group()
        
        try:
            # Background color - make night darker for better star contrast
            if self.is_daytime and not self.force_night_mode:
                # Day: Light blue sky
                bg_color = 0x87CEEB  # Sky blue
            else:
                # Night: Very dark blue/black for better star visibility
                bg_color = 0x000011  # Very dark blue
            
            # Create background rectangle
            bg_bitmap = displayio.Bitmap(self.width, self.height, 1)
            bg_palette = displayio.Palette(1)
            bg_palette[0] = bg_color
            bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
            bg_group.append(bg_sprite)
            
            # Add constellations at night
            if not self.is_daytime or self.force_night_mode:
                constellation_group = self._create_constellation_group()
                if len(constellation_group) > 0:
                    bg_group.append(constellation_group)
                    # print(f"Added constellation group with {len(constellation_group)} elements")
            
            # Add sun or moon
            if self.is_daytime and not self.force_night_mode:
                # Sun
                self.sun_angle += 2
                sun_x = self.width - 30 + int(5 * math.sin(math.radians(self.sun_angle)))
                sun_y = 20 + int(3 * math.cos(math.radians(self.sun_angle)))
                
                sun_label = label.Label(
                    terminalio.FONT,
                    text="☀",
                    color=0xFFD700,  # Gold
                    x=sun_x,
                    y=sun_y,
                    scale=2
                )
                bg_group.append(sun_label)
            else:
                # Moon
                self.moon_phase = (self.moon_phase + 0.5) % 360
                moon_brightness = int(180 + 75 * math.sin(math.radians(self.moon_phase)))
                moon_color = (moon_brightness << 16) | (moon_brightness << 8) | moon_brightness
                
                moon_label = label.Label(
                    terminalio.FONT,
                    text="☽",
                    color=moon_color,
                    x=self.width - 25,
                    y=25,
                    scale=2
                )
                bg_group.append(moon_label)
        
        except Exception as e:
            # print(f"Background creation error: {e}")
            import traceback
            traceback.print_exception()
        
        return bg_group
    
    def _create_clock_group(self):
        """Create the bouncing clock display"""
        clock_group = displayio.Group()
        
        try:
            # Update time every second
            current_time = time.monotonic()
            if current_time - self.last_time_update >= 1.0:
                self.time_string = self._get_current_time()
                self.last_time_update = current_time
            
            # Update position and color
            self._update_clock_position()
            
            # Create rainbow colored time text
            rainbow_color = self._hue_to_rgb(self.color_hue)
            
            # Add shadow effect first
            shadow_color = 0x222222 if (self.is_daytime and not self.force_night_mode) else 0x000000
            shadow_label = label.Label(
                terminalio.FONT,
                text=self.time_string,
                color=shadow_color,
                x=int(self.clock_x + 2),
                y=int(self.clock_y + 2),
                scale=2
            )
            clock_group.append(shadow_label)
            
            # Main clock text
            clock_label = label.Label(
                terminalio.FONT,
                text=self.time_string,
                color=rainbow_color,
                x=int(self.clock_x),
                y=int(self.clock_y),
                scale=2
            )
            clock_group.append(clock_label)
            
        except Exception as e:
            # print(f"Clock creation error: {e}")
            pass
        return clock_group
    
    def _create_info_group(self):
        """Create info display"""
        info_group = displayio.Group()
        
        try:
            # Show screensaver info
            info_text = "Press button to exit"
            info_color = 0x888888 if (self.is_daytime and not self.force_night_mode) else 0x666666
            
            info_label = label.Label(
                terminalio.FONT,
                text=info_text,
                color=info_color,
                x=5,
                y=self.height - 10
            )
            info_group.append(info_label)
        except Exception as e:
            # print(f"Info creation error: {e}")
            pass
        return info_group
    
    def _check_exit_condition(self):
        """Check if user wants to exit"""
        if self.button:
            try:
                if not self.button.value:  # Button pressed (active low)
                    return True
            except:
                pass
        return False
    
    def set_force_night_mode(self, force=True):
        """Force night mode for testing constellations"""
        self.force_night_mode = force
        if force:
            # print("🌙 Forced night mode enabled - constellations will always show")
            pass
        else:
            #print("☀️ Normal day/night cycle restored")
            pass
    def start(self, return_callback=None):
        """Start the screensaver"""
        if not self.display:
            # print("❌ Cannot start screensaver - no display available")
            return False
        
        self.return_callback = return_callback
        self.running = True
        self.frame_count = 0
        self.constellation_start_time = 0  # Reset constellation timer
        
        # Initial memory cleanup
        gc.collect()
        
        
        # Force night mode for testing if it's daytime
        try:
            current_hour = time.localtime().tm_hour if hasattr(time, 'localtime') else 12
            if 6 <= current_hour < 18:
                # print("🌙 Forcing night mode for constellation testing")
                self.set_force_night_mode(True)
        except:
            # print("🌙 Forcing night mode for constellation testing (time unavailable)")
            self.set_force_night_mode(True)
        
        try:
            while self.running:
                # Create display groups
                main_group = displayio.Group()
                
                # Add background (includes constellations)
                bg_group = self._create_background_group()
                main_group.append(bg_group)
                
                # Add clock
                clock_group = self._create_clock_group()
                main_group.append(clock_group)
                
                # Add info
                info_group = self._create_info_group()
                main_group.append(info_group)
                
                # Update display
                self.display.root_group = main_group
                
                # Check for exit
                if self._check_exit_condition():
                    # print("🔘 Button pressed - exiting screensaver")
                    break
                
                # Frame timing
                self.frame_count += 1
                time.sleep(0.1)  # Slower refresh for better visibility
                
                # Debug output every few seconds
                if self.frame_count % 50 == 0:
                   gc.collect()
                   # Regular memory cleanup every 2 seconds
                if self.frame_count % 20 == 0:
                    gc.collect()
                    if self.frame_count % 100 == 0:  # Less frequent detailed memory info
                        # print(f"💾 Memory cleanup: {gc.mem_free()} bytes free")
                        pass
            
        except KeyboardInterrupt:
            # print("🛑 Screensaver interrupted")
            pass
        except Exception as e:
            # print(f"❌ Screensaver error: {e}")
            import traceback
            traceback.print_exception()
        
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
            
            # Final memory cleanup
            gc.collect()
            # print(f"🛑 Clock screensaver stopped - {gc.mem_free()} bytes free")
            
            # Call return callback if provided
            if self.return_callback:
                # print("🔄 Returning to previous app...")
                self.return_callback()
            
        except Exception as e:
            # print(f"❌ Screensaver stop error: {e}")
            pass

# Standalone functions for direct loading
def start_screensaver(return_callback=None):
    """Start the clock screensaver"""
    gc.collect()  # Clean up before starting
    screensaver = ClockScreensaver()
    return screensaver.start(return_callback)

def start_screensaver_night_mode(return_callback=None):
    """Start the screensaver in forced night mode to see constellations"""
    gc.collect()  # Clean up before starting
    screensaver = ClockScreensaver()
    screensaver.set_force_night_mode(True)
    return screensaver.start(return_callback)

def demo_screensaver():
    """Demo the screensaver"""
    # print("🎬 Clock Screensaver Demo with Constellations")
    print("=" * 40)
    
    def demo_return():
        # print("🎬 Demo completed - would return to calling app")
        gc.collect()  # Clean up after demo
    
    start_screensaver_night_mode(demo_return)

def test_constellation_visibility():
    """Test constellation visibility with debug info"""
    # print("🧪 Testing Constellation Visibility")
    # print("=" * 40)
    
    gc.collect()
    # print(f"💾 Starting test with {gc.mem_free()} bytes free")
    
    screensaver = ClockScreensaver()
    screensaver.set_force_night_mode(True)
    
    # print("Testing constellation creation...")
    constellation_group = screensaver._create_constellation_group()
    # print(f"Created constellation group with {len(constellation_group)} elements")
    
    # Test each constellation
    for i, constellation in enumerate(screensaver.constellations):
        screensaver.current_constellation_index = i
        screensaver.constellation_alpha = 1.0
        test_group = screensaver._create_constellation_group()
        # print(f"{i+1}. {constellation['name']}: {len(test_group)} elements created")
        
        # Memory cleanup after each test
        del test_group
        gc.collect()
    
    # print("=" * 40)
    # print(f"🧪 Constellation visibility test completed - {gc.mem_free()} bytes free")

# Main execution for direct loading
def main():
    """Main function for direct execution"""
    try:
        # print("🕐 StageTwo Constellation Clock Screensaver")
        # print(f"📋 Version: {__version__}")
        # print("=" * 50)
        
        # Initial memory status
        gc.collect()
        # print(f"💾 Starting with {gc.mem_free()} bytes free memory")
        
        # Check display
        if not (hasattr(board, 'DISPLAY') and board.DISPLAY):
            # print("❌ No display available - cannot run screensaver")
            return False
        
        # Check button
        if not hasattr(board, 'BUTTON'):
            # print("⚠️ No button available - screensaver will run indefinitely")
            # print("💡 Use Ctrl+C to stop")
            pass
        # Test constellation visibility first
        print("🧪 Testing constellation visibility...")
        test_constellation_visibility()
        
        print("\n🚀 Starting screensaver in night mode...")
        # Start screensaver in night mode to see constellations
        screensaver = ClockScreensaver()
        screensaver.set_force_night_mode(True)
        success = screensaver.start()
        
        if success:
            # print("✅ Screensaver completed successfully")
            pass
        else:
            # print("❌ Screensaver failed to start")
            pass
        # Final memory cleanup
        del screensaver
        gc.collect()
        # print(f"💾 Final memory: {gc.mem_free()} bytes free")
        
        return success
        
    except Exception as e:
        # print(f"❌ Main execution error: {e}")
        import traceback
        traceback.print_exception()
        return False


# Integration helper for other apps
class ScreensaverManager:
    """Helper class for integrating screensaver into other apps"""
    
    def __init__(self):
        gc.collect()  # Clean up on initialization
        self.screensaver = None
        self.previous_app_state = None
    
    def save_app_state(self, state_data):
        """Save current app state before starting screensaver"""
        self.previous_app_state = state_data
        # print("💾 App state saved for screensaver")
    
    def start_with_return(self, return_function, force_night=False):
        """Start screensaver with custom return function"""
        def combined_return():
            if return_function:
                return_function()
            if self.previous_app_state:
                # print("🔄 Restoring previous app state")
            # Clean up after return
                gc.collect()
        
        gc.collect()  # Clean up before starting
        self.screensaver = ClockScreensaver()
        if force_night:
            self.screensaver.set_force_night_mode(True)
        return self.screensaver.start(combined_return)
    
    def quick_start(self, force_night=False):
        """Quick start screensaver (no return callback)"""
        gc.collect()  # Clean up before starting
        self.screensaver = ClockScreensaver()
        if force_night:
            self.screensaver.set_force_night_mode(True)
        return self.screensaver.start()


# Utility functions
def test_screensaver_components():
    """Test individual screensaver components"""
    # print("🧪 Testing Screensaver Components")
    # print("=" * 40)
    
    gc.collect()
    # print(f"💾 Starting component test with {gc.mem_free()} bytes free")
    
    # Test display
    try:
        if hasattr(board, 'DISPLAY') and board.DISPLAY:
            # print("✅ Display: Available")
            # print(f"   Size: {board.DISPLAY.width}x{board.DISPLAY.height}")
            pass
        else:
            print("❌ Display: Not available")
    except Exception as e:
        # print(f"❌ Display test error: {e}")
        pass
    
    # Test button
    try:
        if hasattr(board, 'BUTTON'):
            button = digitalio.DigitalInOut(board.BUTTON)
            button.direction = digitalio.Direction.INPUT
            button.pull = digitalio.Pull.UP
            # print(f"✅ Button: Available (current state: {'pressed' if not button.value else 'released'})")
            button.deinit()  # Clean up
        else:
            # print("❌ Button: Not available")
            pass
    except Exception as e:
        # print(f"❌ Button test error: {e}")
        pass
    
    # Test time functions
    try:
        screensaver = ClockScreensaver()
        test_time = screensaver._get_current_time()
        print(f"✅ Time: {test_time}")
        del screensaver  # Clean up
        gc.collect()
    except Exception as e:
        # print(f"❌ Time test error: {e}")
        pass
    # Test color functions
    try:
        screensaver = ClockScreensaver()
        test_color = screensaver._hue_to_rgb(180)
        # print(f"✅ Color: RGB(180°) = 0x{test_color:06X}")
        del screensaver  # Clean up
        gc.collect()
    except Exception as e:
        # print(f"❌ Color test error: {e}")
        pass
    
    # Test constellation data
    try:
        screensaver = ClockScreensaver()
        # print(f"✅ Constellations: {len(screensaver.constellations)} loaded")
        for i, constellation in enumerate(screensaver.constellations):
            stars_count = len(constellation["stars"])
            lines_count = len(constellation.get("lines", []))
            # print(f"   {i+1:2d}. {constellation['name']} ({stars_count} stars, {lines_count} lines)")
        del screensaver  # Clean up
        gc.collect()
    except Exception as e:
        # print(f"❌ Constellation test error: {e}")
        pass
    
    # print("=" * 40)


def list_constellations():
    """List all available constellations"""
    # print("⭐ Available Constellations:")
    # print("=" * 50)
    
    try:
        gc.collect()
        screensaver = ClockScreensaver()
        total_time = screensaver.fade_in_duration + screensaver.visible_duration + screensaver.fade_out_duration
        
        for i, constellation in enumerate(screensaver.constellations):
            name = constellation["name"]
            stars_count = len(constellation["stars"])
            lines_count = len(constellation.get("lines", []))
            
                       # Show star positions
            # print("    Star positions:")
            for j, star in enumerate(constellation["stars"]):
                x, y, brightness = star
                # print(f"      {j+1}: ({x:.2f}, {y:.2f}) brightness={brightness}")
            
          
        
        total_cycle_time = len(screensaver.constellations) * total_time
        # print(f"🕐 Complete cycle time: {total_cycle_time/60:.1f} minutes")
        
        # Clean up
        del screensaver
        gc.collect()
        # print(f"💾 Memory after listing: {gc.mem_free()} bytes free")
        
    except Exception as e:
        # print(f"❌ Error listing constellations: {e}")
        pass

def show_integration_example():
    """Show integration example"""
    # print("📖 Integration Example:")
    # print("=" * 50)
    # print(INTEGRATION_EXAMPLE)
    # print("=" * 50)


# Example integration code for other apps
INTEGRATION_EXAMPLE = '''
# Example: How to integrate constellation screensaver into your app

from screensaver import ScreensaverManager, start_screensaver_night_mode
import gc

class MyApp:
    def __init__(self):
        self.screensaver_manager = ScreensaverManager()
        self.app_data = {"current_screen": "main", "user_settings": {}}
    
    def start_screensaver(self, force_night=False):
        """Start screensaver from your app"""
        # Clean up before starting
        gc.collect()
        
        # Save current state
        self.screensaver_manager.save_app_state(self.app_data)
        
        # Define return function
        def return_to_app():
            print("Returning to MyApp...")
            self.restore_app_state()
            self.resume_app()
            gc.collect()  # Clean up after return
        
        # Start screensaver (with optional night mode)
        self.screensaver_manager.start_with_return(return_to_app, force_night)
    
    def start_constellation_demo(self):
        """Start screensaver in night mode to show constellations"""
        self.start_screensaver(force_night=True)
    
    def restore_app_state(self):
        """Restore app state after screensaver"""
        if self.screensaver_manager.previous_app_state:
            self.app_data = self.screensaver_manager.previous_app_state
            # print("App state restored")
    
    def resume_app(self):
        """Resume app after screensaver"""
        print("App resumed from constellation screensaver")
        # Continue your app logic here

# Usage:
# app = MyApp()
# app.start_constellation_demo()  # Force night mode to see constellations
# app.start_screensaver()         # Normal day/night cycle
'''

# Auto-start if run directly
if __name__ == "__main__":
    success = main()
    if success:
        print("")
    else:
        print("❌ Constellation clock screensaver failed")
else:
    print(f"📦 Constellation Clock Screensaver V{__version__} module loaded")
    # print("🕐 Use start_screensaver() for normal mode")
    # print("🌙 Use start_screensaver_night_mode() to force constellations")
    # print("⭐ Use list_constellations() to see available constellations")
    # print("🧪 Use test_constellation_visibility() to debug constellation display")

# Export main classes and functions
__all__ = [
    'ClockScreensaver',
    'ScreensaverManager', 
    'start_screensaver',
    'start_screensaver_night_mode',
    'demo_screensaver',
    'test_screensaver_components',
    'test_constellation_visibility',
    'list_constellations',
    'show_integration_example',
    'main'
]

# Quick start examples
QUICK_START_EXAMPLES = {
    "basic_screensaver": '''
# Basic constellation screensaver
from screensaver import start_screensaver
start_screensaver()
''',
    
    "night_mode_screensaver": '''
# Force night mode to see constellations
from screensaver import start_screensaver_night_mode
start_screensaver_night_mode()
''',
    
    "test_constellations": '''
# Test constellation visibility
from screensaver import test_constellation_visibility
test_constellation_visibility()
''',
    
    "with_return_callback": '''
# Screensaver with return callback
from screensaver import start_screensaver_night_mode

def my_return_function():
    print("Returned from constellation screensaver!")
    # Resume your app here

start_screensaver_night_mode(my_return_function)
''',
    
    "managed_screensaver": '''
# Using ScreensaverManager with night mode
from screensaver import ScreensaverManager

manager = ScreensaverManager()
manager.save_app_state({"my_data": "important"})
manager.start_with_return(lambda: print("Back to app!"), force_night=True)
''',
    
    "list_constellations": '''
# See all available constellations
from screensaver import list_constellations
list_constellations()
''',
    
    "test_components": '''
# Test screensaver components
from screensaver import test_screensaver_components
test_screensaver_components()
'''
}

def show_examples():
    """Show quick start examples"""
    print("\n📚 Quick Start Examples:")
    print("=" * 50)
    
    for name, code in QUICK_START_EXAMPLES.items():
        print(f"\n🔹 {name.replace('_', ' ').title()}:")
        print(code.strip())
    
    print("\n" + "=" * 50)

print("🎯 Constellation Clock Screensaver module ready!")

# Initial memory cleanup and status
gc.collect()
try:
    print(f"💾 Memory after module load: {gc.mem_free()} bytes free")
except:
    print("💾 Memory management active")

# End of constellation clock screensaver




