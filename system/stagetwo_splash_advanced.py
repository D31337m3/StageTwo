"""
StageTwo Advanced Splash Animation - Fixed Version
Memory-optimized with better error handling
"""

import time
import math
import random
import gc
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
from adafruit_display_shapes.circle import Circle

# Constants
SCREEN_WIDTH = 240
SCREEN_HEIGHT = 135
FRAME_DELAY = 0.15
ANIMATION_DURATION = 18.0  # Reduced duration

# Color palette - simplified
COLORS = {
    'black': 0x000000,
    'white': 0xFFFFFF,
    'red': 0xFF0000,
    'orange': 0xFF8000,
    'yellow': 0xFFFF00,
    'green': 0x00FF00,
    'blue': 0x0000FF,
    'cyan': 0x00FFFF,
    'purple': 0x800080,
    'silver': 0xC0C0C0,
    'dark_blue': 0x000080,
    'dark_red': 0x800000,
    'brown': 0x8B4513
}

class SimpleParticle:
    """Lightweight particle class"""
    def __init__(self, x, y, vx, vy, color, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.max_life = life
    
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        return self.life > 0

class SimpleRocket:
    """Simplified rocket with basic physics"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.velocity = 0
        self.altitude = 0
        self.fuel = 100
        self.stage = 0  # 0=boosters, 1=main, 2=upper
        self.separated_boosters = False
        self.separated_main = False
        
        # Stage positions for separation animation
        self.booster_left_x = x - 8
        self.booster_right_x = x + 8
        self.main_stage_y = y
        
        # Separation velocities
        self.booster_left_vx = -1
        self.booster_right_vx = 1
        self.main_stage_vy = 2
    
    def update(self, frame_count):
        """Update rocket physics"""
        try:
            # Stage progression
            if frame_count > 60 and not self.separated_boosters:
                self.separated_boosters = True
                self.stage = 1
            
            if frame_count > 120 and not self.separated_main:
                self.separated_main = True
                self.stage = 2
            
            # Basic physics
            if frame_count > 20:  # Start moving after ignition
                self.velocity += 0.15
                self.y -= self.velocity
                self.altitude = max(0, (240 - self.y) / 4)  # Simplified altitude
            
            # Update separated stages
            if self.separated_boosters:
                self.booster_left_x += self.booster_left_vx
                self.booster_right_x += self.booster_right_vx
            
            if self.separated_main:
                self.main_stage_y += self.main_stage_vy
            
            # Fuel consumption
            if frame_count > 20 and self.fuel > 0:
                self.fuel -= 0.5
            
        except Exception as e:
            print(f"Rocket update error: {e}")

class AdvancedSplashFixed:
    """Memory-optimized advanced splash animation"""
    
    def __init__(self, display):
        self.display = display
        if self.display:
            self.display.auto_refresh = False
        
        # Animation state
        self.frame_count = 0
        self.start_time = time.monotonic()
        self.phase = 0
        
        # Create rocket
        self.rocket = SimpleRocket(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 30)
        
        # Particle system - limited size
        self.particles = []
        self.max_particles = 30  # Reduced for memory
        
        # Stars - pre-generated
        self.stars = []
        self._generate_stars()
        
        # Error tracking
        self.error_count = 0
        self.max_errors = 15
        
        print("Advanced splash (fixed) initialized")
    
    def _generate_stars(self):
        """Pre-generate star field"""
        try:
            for i in range(50):  # Reduced star count
                self.stars.append({
                    'x': random.randint(0, SCREEN_WIDTH),
                    'y': random.randint(0, SCREEN_HEIGHT // 2),
                    'size': random.choice([1, 1, 2]),
                    'blink': random.randint(0, 60)
                })
        except Exception as e:
            print(f"Star generation error: {e}")
    
    def _add_particle(self, x, y, vx, vy, color, life):
        """Add particle with memory management"""
        try:
            if len(self.particles) < self.max_particles:
                particle = SimpleParticle(x, y, vx, vy, color, life)
                self.particles.append(particle)
        except Exception as e:
            print(f"Particle creation error: {e}")
    
    def _update_particles(self):
        """Update particle system"""
        try:
            # Update existing particles
            self.particles = [p for p in self.particles if p.update()]
            
            # Generate new exhaust particles
            if self.phase >= 1 and self.phase <= 3:
                if self.frame_count % 3 == 0:  # Reduce frequency
                    # Main exhaust
                    self._add_particle(
                        self.rocket.x + random.uniform(-2, 2),
                        self.rocket.y + 20,
                        random.uniform(-0.5, 0.5),
                        random.uniform(2, 4),
                        random.choice([COLORS['orange'], COLORS['red']]),
                        20
                    )
            
            # Separation effects
            if self.frame_count == 60:  # Booster separation
                for i in range(5):
                    self._add_particle(
                        self.rocket.x + random.uniform(-10, 10),
                        self.rocket.y + random.uniform(-5, 5),
                        random.uniform(-3, 3),
                        random.uniform(-2, 2),
                        COLORS['yellow'],
                        30
                    )
            
        except Exception as e:
            print(f"Particle update error: {e}")
            self.error_count += 1
    
    def _update_phase(self):
        """Update animation phase"""
        try:
            elapsed = time.monotonic() - self.start_time
            
            if elapsed < 1.0:
                self.phase = 0  # Pre-launch
            elif elapsed < 2.0:
                self.phase = 1  # Liftoff
            elif elapsed < 4.0:
                self.phase = 2  # Ascent
            elif elapsed < 6.0:
                self.phase = 3  # Upper stage
            else:
                self.phase = 4  # Complete
                
        except Exception as e:
            print(f"Phase update error: {e}")
            self.error_count += 1
    
    def _create_background(self, group):
        """Create background elements"""
        try:
            # Background color based on altitude
            if self.rocket.altitude < 20:
                bg_color = COLORS['dark_blue']
            else:
                bg_color = COLORS['black']
            
            background = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=bg_color)
            group.append(background)
            
            # Stars in space
            if self.rocket.altitude > 15:
                for star in self.stars:
                    if (self.frame_count + star['blink']) % 60 < 30:
                        star_obj = Circle(star['x'], star['y'], star['size'], fill=COLORS['white'])
                        group.append(star_obj)
            
        except Exception as e:
            print(f"Background creation error: {e}")
            self.error_count += 1
    
    def _create_ground(self, group):
        """Create ground elements"""
        try:
            if self.rocket.y > SCREEN_HEIGHT - 80:
                # Ground
                ground = Rect(0, SCREEN_HEIGHT - 15, SCREEN_WIDTH, 15, fill=COLORS['brown'])
                group.append(ground)
                
                # Simple launch pad
                pad = Rect(SCREEN_WIDTH // 2 - 20, SCREEN_HEIGHT - 20, 40, 5, fill=COLORS['silver'])
                group.append(pad)
                
                # Launch tower
                tower = Rect(SCREEN_WIDTH // 2 - 25, SCREEN_HEIGHT - 40, 3, 25, fill=COLORS['silver'])
                group.append(tower)
                
        except Exception as e:
            print(f"Ground creation error: {e}")
            self.error_count += 1
    
    def _create_rocket(self, group):
        """Create rocket stages"""
        try:
            # Boosters (if not separated)
            if not self.rocket.separated_boosters:
                # Left booster
                left_booster = Rect(int(self.rocket.x) - 10, int(self.rocket.y), 3, 15, fill=COLORS['orange'])
                group.append(left_booster)
                
                # Right booster
                right_booster = Rect(int(self.rocket.x) + 7, int(self.rocket.y), 3, 15, fill=COLORS['orange'])
                group.append(right_booster)
            else:
                # Separated boosters
                if self.rocket.booster_left_x > -10:
                    left_sep = Rect(int(self.rocket.booster_left_x), int(self.rocket.y) + 10, 3, 15, fill=COLORS['dark_red'])
                    group.append(left_sep)
                
                if self.rocket.booster_right_x < SCREEN_WIDTH + 10:
                    right_sep = Rect(int(self.rocket.booster_right_x), int(self.rocket.y) + 10, 3, 15, fill=COLORS['dark_red'])
                    group.append(right_sep)
            
            # Main stage (if not separated)
            if not self.rocket.separated_main:
                main_stage = Rect(int(self.rocket.x) - 3, int(self.rocket.y), 6, 20, fill=COLORS['silver'])
                group.append(main_stage)
            else:
                # Separated main stage
                if self.rocket.main_stage_y < SCREEN_HEIGHT + 20:
                    main_sep = Rect(int(self.rocket.x) - 3, int(self.rocket.main_stage_y), 6, 20, fill=COLORS['silver'])
                    group.append(main_sep)
            
            # Upper stage (always visible after main separation)
            if self.rocket.separated_main or self.phase >= 2:
                upper_stage = Rect(int(self.rocket.x) - 2, int(self.rocket.y) - 10, 4, 10, fill=COLORS['white'])
                group.append(upper_stage)
            
        except Exception as e:
            print(f"Rocket creation error: {e}")
            self.error_count += 1
    
    def _create_particles(self, group):
        """Render particles"""
        try:
            for particle in self.particles:
                if (0 <= particle.x < SCREEN_WIDTH and 
                    0 <= particle.y < SCREEN_HEIGHT):
                    
                    particle_obj = Circle(int(particle.x), int(particle.y), 2, fill=particle.color)
                    group.append(particle_obj)
                    
        except Exception as e:
            print(f"Particle rendering error: {e}")
            self.error_count += 1
    
    def _create_ui(self, group):
        """Create UI elements"""
        try:
            # Phase indicator
            phase_text = ""
            if self.phase == 0:
                phase_text = "PRE-LAUNCH"
            elif self.phase == 1:
                phase_text = "LIFTOFF"
            elif self.phase == 2:
                phase_text = "ASCENT"
            elif self.phase == 3:
                phase_text = "UPPER STAGE"
            elif self.phase == 4:
                phase_text = "STAGETWO LAUNCHER"
            
            if phase_text:
                text_label = label.Label(
                    terminalio.FONT,
                    text=phase_text,
                    color=COLORS['white'],
                    x=10,
                    y=15
                )
                group.append(text_label)
            
            # Simple telemetry
            if self.phase >= 2:
                alt_text = f"ALT: {int(self.rocket.altitude)}km"
                alt_label = label.Label(
                    terminalio.FONT,
                    text=alt_text,
                    color=COLORS['green'],
                    x=10,
                    y=SCREEN_HEIGHT - 15
                )
                group.append(alt_label)
            
        except Exception as e:
            print(f"UI creation error: {e}")
            self.error_count += 1
    
    def update(self):
        """Update animation"""
        try:
            self.frame_count += 1
            self._update_phase()
            self.rocket.update(self.frame_count)
            self._update_particles()
            
            # Force garbage collection every 30 frames
            if self.frame_count % 30 == 0:
                gc.collect()
                
        except Exception as e:
            print(f"Update error: {e}")
            self.error_count += 1
    
    def render(self):
        """Render frame with error handling"""
        try:
            # Check error count
            if self.error_count >= self.max_errors:
                print("Too many errors, stopping animation")
                return False
            
            # Create display group
            main_group = displayio.Group()
            
            # Build scene
            self._create_background(main_group)
            self._create_ground(main_group)
            self._create_particles(main_group)
            self._create_rocket(main_group)
            self._create_ui(main_group)
            
            # Update display
            if self.display:
                self.display.root_group = main_group
                self.display.refresh()
            
            return True
            
        except Exception as e:
            print(f"Render error: {e}")
            self.error_count += 1
            return False
    
 
    def run(self):
        """Run the animation with robust error handling"""
        print("Starting StageTwo Advanced Splash (Fixed)")
        
        try:
            while time.monotonic() - self.start_time < ANIMATION_DURATION:
                frame_start = time.monotonic()
                
                # Update animation
                self.update()
                
                # Check for too many errors
                if self.error_count >= self.max_errors:
                    print("Animation stopped due to errors")
                    break
                
                # Render frame
                if not self.render():
                    print("Render failed, stopping animation")
                    break
                
                # Frame rate control
                frame_time = time.monotonic() - frame_start
                if frame_time < FRAME_DELAY:
                    time.sleep(FRAME_DELAY - frame_time)
            
            # Hold final frame
            time.sleep(0.5)
            
            print("StageTwo Advanced Splash Complete")
            return True
            
        except Exception as e:
            print(f"Animation error: {e}")
            return False
        finally:
            # Cleanup
            try:
                self.particles.clear()
                gc.collect()
            except:
                pass

class BasicSplashFallback:
    """Ultra-simple fallback animation"""
    
    def __init__(self, display):
        self.display = display
        if self.display:
            self.display.auto_refresh = False
        
        self.frame_count = 0
        self.start_time = time.monotonic()
    
    def run(self):
        """Run basic animation"""
        print("Starting Basic Splash Fallback")
        
        try:
            for frame in range(60):  # 3 seconds at 20fps
                main_group = displayio.Group()
                
                # Background
                background = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=COLORS['black'])
                main_group.append(background)
                
                # Simple rocket
                rocket_y = SCREEN_HEIGHT - 30 - (frame * 2)
                if rocket_y > -20:
                    rocket = Rect(SCREEN_WIDTH // 2 - 2, rocket_y, 4, 15, fill=COLORS['silver'])
                    main_group.append(rocket)
                
                # Simple exhaust
                if frame > 10:
                    for i in range(3):
                        exhaust_y = rocket_y + 15 + i * 3
                        exhaust = Circle(
                            SCREEN_WIDTH // 2 + random.randint(-1, 1),
                            exhaust_y,
                            2,
                            fill=COLORS['orange']
                        )
                        main_group.append(exhaust)
                
                # Title
                if frame > 40:
                    title = label.Label(
                        terminalio.FONT,
                        text="STAGETWO ",
                        color=COLORS['white'],
                        x=SCREEN_WIDTH // 2 - 70,
                        y=30
                    )
                    main_group.append(title)
                
                # Update display
                if self.display:
                    self.display.root_group = main_group
                    self.display.refresh()
                
                time.sleep(0.05)
            
            return True
            
        except Exception as e:
            print(f"Basic splash error: {e}")
            return False

def show_advanced_splash_safe(display, force_simple=False):
    """
    Safely show advanced splash with multiple fallback levels
    
    Args:
        display: Display object
        force_simple: Force simple mode
    
    Returns:
        bool: True if any animation succeeded
    """
    if not display:
        print("No display available")
        return False
    
    # Check memory
    gc.collect()
    free_memory = gc.mem_free()
    print(f"Available memory: {free_memory} bytes")
    
    # Try advanced animation first (if enough memory)
    if not force_simple and free_memory > 40000:
        try:
            print("Attempting advanced animation...")
            splash = AdvancedSplashFixed(display)
            success = splash.run()
            del splash
            gc.collect()
            
            if success:
                return True
            else:
                print("Advanced animation failed, trying fallback...")
        except Exception as e:
            print(f"Advanced animation exception: {e}")
    
    # Try basic fallback
    try:
        print("Using basic fallback animation...")
        basic_splash = BasicSplashFallback(display)
        success = basic_splash.run()
        del basic_splash
        gc.collect()
        return success
        
    except Exception as e:
        print(f"Basic fallback failed: {e}")
    
    # Final fallback - static display
    try:
        print("Using static fallback...")
        main_group = displayio.Group()
        
        background = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=COLORS['black'])
        main_group.append(background)
        
        title = label.Label(
            terminalio.FONT,
            text="STAGETWO ",
            color=COLORS['white'],
            x=SCREEN_WIDTH // 2 - 70,
            y=SCREEN_HEIGHT // 2 - 10
        )
        main_group.append(title)
        
        subtitle = label.Label(
            terminalio.FONT,
            text="ADVANCED LOADER V2.0",
            color=COLORS['cyan'],
            x=SCREEN_WIDTH // 2 - 80,
            y=SCREEN_HEIGHT // 2 + 10
        )
        main_group.append(subtitle)
        
        display.root_group = main_group
        display.refresh()
        time.sleep(2.0)
        
        return True
        
    except Exception as e:
        print(f"Static fallback failed: {e}")
        return False

def show_recovery_splash_safe(display):
    """Safe recovery splash"""
    if not display:
        return False
    
    try:
        main_group = displayio.Group()
        
        # Dark background
        background = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=COLORS['black'])
        main_group.append(background)
        
        # Recovery title
        title = label.Label(
            terminalio.FONT,
            text="RECOVERY MODE",
            color=COLORS['red'],
            x=SCREEN_WIDTH // 2 - 60,
            y=30
        )
        main_group.append(title)
        
        # Subtitle
        subtitle = label.Label(
            terminalio.FONT,
            text="STAGETWO ",
            color=COLORS['orange'],
            x=SCREEN_WIDTH // 2 - 70,
            y=50
        )
        main_group.append(subtitle)
        
        # Animated elements
        for frame in range(40):
            # Clear previous frame elements
            while len(main_group) > 3:
                main_group.pop()
            
            # Blinking warning
            if frame % 20 < 10:
                warning = Circle(30, 70, 4, fill=COLORS['red'])
                main_group.append(warning)
                
                warning2 = Circle(SCREEN_WIDTH - 30, 70, 4, fill=COLORS['red'])
                main_group.append(warning2)
            
            # Status
            status = label.Label(
                terminalio.FONT,
                text="SYSTEM RECOVERY ACTIVE",
                color=COLORS['yellow'],
                x=SCREEN_WIDTH // 2 - 90,
                y=90
            )
            main_group.append(status)
            
            display.root_group = main_group
            display.refresh()
            time.sleep(0.05)
        
        time.sleep(1.0)
        return True
        
    except Exception as e:
        print(f"Recovery splash error: {e}")
        return False

def show_loader_splash_safe(display):
    """Safe loader splash"""
    if not display:
        return False
    
    try:
        main_group = displayio.Group()
        
        # Background
        background = Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, fill=COLORS['dark_blue'])
        main_group.append(background)
        
        # Title
        title = label.Label(
            terminalio.FONT,
            text="S2 LOADER",
            color=COLORS['cyan'],
            x=SCREEN_WIDTH // 2 - 65,
            y=30
        )
        main_group.append(title)
        
        # Simple loading animation
        for frame in range(60):
            # Clear previous loading elements
            while len(main_group) > 2:
                main_group.pop()
            
            # Loading dots
            dots = "." * ((frame // 10) % 4)
            loading_text = f"Loading{dots}"
            loading_label = label.Label(
                terminalio.FONT,
                text=loading_text,
                color=COLORS['white'],
                x=SCREEN_WIDTH // 2 - 30,
                y=70
            )
            main_group.append(loading_label)
            
            # Progress bar
            progress = int((frame / 60) * 100)
            progress_bg = Rect(50, 90, 140, 8, fill=COLORS['black'])
            main_group.append(progress_bg)
            
            if progress > 0:
                progress_fill = Rect(50, 90, int(140 * progress / 100), 8, fill=COLORS['cyan'])
                main_group.append(progress_fill)
            
            display.root_group = main_group
            display.refresh()
            time.sleep(0.05)
        
        return True
        
    except Exception as e:
        print(f"Loader splash error: {e}")
        return False

# Integration functions for bootloader
def show_boot_splash():
    """Show boot splash - called from bootloader"""
    try:
        import board
        display = board.DISPLAY
        return show_advanced_splash_safe(display, force_simple=False)
    except Exception as e:
        print(f"Boot splash integration error: {e}")
        return False

def show_recovery_splash():
    """Show recovery splash - called from recovery system"""
    try:
        import board
        display = board.DISPLAY
        return show_recovery_splash_safe(display)
    except Exception as e:
        print(f"Recovery splash integration error: {e}")
        return False

def show_loader_splash():
    """Show loader splash - called from loader"""
    try:
        import board
        display = board.DISPLAY
        return show_loader_splash_safe(display)
    except Exception as e:
        print(f"Loader splash integration error: {e}")
        return False

# Memory diagnostic function
def check_memory_status():
    """Check memory status for debugging"""
    try:
        gc.collect()
        free = gc.mem_free()
        print(f"Free memory: {free} bytes")
        
        if free < 30000:
            print("WARNING: Low memory - using basic animations only")
            return "basic"
        elif free < 50000:
            print("NOTICE: Limited memory - using simplified animations")
            return "simple"
        else:
            print("OK: Sufficient memory for advanced animations")
            return "advanced"
    except Exception as e:
        print(f"Memory check error: {e}")
        return "basic"

# Export all functions
__all__ = [
    'AdvancedSplashFixed',
    'BasicSplashFallback',
    'show_advanced_splash_safe',
    'show_recovery_splash_safe',
    'show_loader_splash_safe',
    'show_boot_splash',
    'show_recovery_splash',
    'show_loader_splash',
    'check_memory_status'
]

print("StageTwo Advanced Splash (Fixed) System Loaded")
gc.collect()
import board
display = board.DISPLAY
show_advanced_splash_safe(display, force_simple=False)
gc.collect()
# Safe way to run animation after another
from system.orbit import launch_animation_safely, clear_display_completely, run_advanced_animation

# Clear display first
clear_display_completely()
run_advanced_animation()
# Launch animation safely
  # or "advanced" or "demo"



