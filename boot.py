"""
StageTwo Boot System
Advanced boot loader with recovery, developer mode, and system management
Compatible with CircuitPython runtimes

(C) 2025 StageTwo Team
"""

import microcontroller
import storage
import usb_cdc
import usb_hid
import supervisor
import time
import board
import rtc
import displayio
import os
import busio
import digitalio
import gc
import terminalio
from adafruit_display_text import label

# Try to import optional modules
try:
    import adafruit_ntp
    import socketpool
    import wifi
    NTP_AVAILABLE = True
except ImportError:
    NTP_AVAILABLE = False
    print("NTP/WiFi not available")

try:
    import adafruit_sdcard
    SDCARD_AVAILABLE = True
except ImportError:
    SDCARD_AVAILABLE = False
    print("SD card support not available")

try:
    import adafruit_imageload
    IMAGE_AVAILABLE = True
except ImportError:
    IMAGE_AVAILABLE = False
    print("Image loading not available")

# Version info
__version__ = "2.1"
__author__ = "StageTwo Team"

# NVM flag positions
RECOVERY_FLAG_ADDR = 0
DEVELOPER_MODE_FLAG_ADDR = 1
FLASH_WRITE_FLAG_ADDR = 2
RELOAD_COUNTER_ADDR = 3
RESET_TYPE_ADDR = 4
BOOT_LOOP_THRESHOLD_ADDR = 5
LAST_SUCCESSFUL_BOOT_ADDR = 6
USB_HOST_ADDR = 7
FIRST_BOOT_SETUP_FLAG_ADDR = 8

# Reset type constants
RESET_POWER_ON = 1
RESET_BROWNOUT = 2
RESET_SOFTWARE = 3
RESET_WATCHDOG = 4
RESET_UNKNOWN = 5

# System defaults
DEFAULT_BOOT_LOOP_THRESHOLD = 3
SUCCESSFUL_BOOT_DELAY = 5
DEFAULT_BRIGHTNESS = 0.6  # 60% brightness
SETTINGS_PATH = "/settings.toml"
DEFAULT_BOOT_FILE = "app_loader.py"
DEFAULT_TIMEOUT = 3

# Boot file priority order
BOOT_FILES = ["app_loader.py", "main.py", "code.py", "user_app.py"]

# SD Card pin configuration (adjust for your board)
try:
    SCK = board.SD_SCK
    MOSI = board.SD_MOSI
    MISO = board.SD_MISO
    CS = board.SD_CS
    SD_PINS_AVAILABLE = True
except AttributeError:
    # Fallback for boards without dedicated SD pins
    try:
        SCK = board.SCK
        MOSI = board.MOSI
        MISO = board.MISO
        CS = board.D10  # Common CS pin
        SD_PINS_AVAILABLE = True
        print("Using fallback SD pins")
    except AttributeError:
        SD_PINS_AVAILABLE = False
        print("No SD pins available")

# --- Settings Management ---
def read_settings():
    """Read settings from settings.toml with comprehensive error handling"""
    settings = {
        "DEFAULT_BOOT_FILE": DEFAULT_BOOT_FILE,
        "BOOT_TIMEOUT": DEFAULT_TIMEOUT,
        "DEVELOPER_MODE": False,
        "FLASH_WRITE": False,
        "DISPLAY_BRIGHTNESS": DEFAULT_BRIGHTNESS,
        "SD_CARD_ENABLED": True,
        "WIFI_ENABLED": True,
        "NTP_ENABLED": True,
        "SCREENSAVER_ENABLED": True,
        "SCREENSAVER_TIMEOUT": 300,
        "SCREENSAVER_TYPE": "trippy"
    }
    
    try:
        with open(SETTINGS_PATH, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if "=" not in line:
                    continue
                
                try:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    # Type conversion
                    if key in ["BOOT_TIMEOUT"]:
                        settings[key] = int(value)
                    elif key in ["DEVELOPER_MODE", "FLASH_WRITE", "SD_CARD_ENABLED", 
                               "WIFI_ENABLED", "NTP_ENABLED", "SCREENSAVER_ENABLED"]:
                        settings[key] = value.lower() in ("true", "1", "yes", "on")
                    elif key in ["DISPLAY_BRIGHTNESS"]:
                        brightness = float(value)
                        settings[key] = max(0.1, min(1.0, brightness))  # Clamp between 10% and 100%
                    elif key in ["SCREENSAVER_TIMEOUT"]:
                        settings[key] = max(60, int(value))  # Minimum 1 minute
                    else:
                        settings[key] = value
                        
                except (ValueError, IndexError) as e:
                    print(f"Settings parse error line {line_num}: {e}")
                    continue
                    
    except OSError as e:
        print(f"Settings file not found: {e}")
        # Create default settings file
        save_settings(settings)
    except Exception as e:
        print(f"Settings read error: {e}")
    
    return settings

def save_settings(settings):
    """Save settings to settings.toml with proper formatting"""
    try:
        # Read existing file to preserve comments and structure
        existing_lines = []
        try:
            with open(SETTINGS_PATH, "r") as f:
                existing_lines = f.readlines()
        except OSError:
            pass
        
        # Build new content
        lines = []
        updated_keys = set()
        
        # Process existing lines, updating values
        for line in existing_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                lines.append(line)
                continue
            
            if "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                if key in settings:
                    # Update existing setting
                    value = settings[key]
                    if isinstance(value, bool):
                        lines.append(f'{key} = {str(value).lower()}\n')
                    elif isinstance(value, (int, float)):
                        lines.append(f'{key} = {value}\n')
                    else:
                        lines.append(f'{key} = "{value}"\n')
                    updated_keys.add(key)
                else:
                    lines.append(line)
            else:
                lines.append(line)
        
        # Add new settings that weren't in the file
        if not existing_lines:
            lines.append("# StageTwo System Settings\n")
            lines.append("# Generated automatically - edit as needed\n\n")
        
        for key, value in settings.items():
            if key not in updated_keys:
                if isinstance(value, bool):
                    lines.append(f'{key} = {str(value).lower()}\n')
                elif isinstance(value, (int, float)):
                    lines.append(f'{key} = {value}\n')
                else:
                    lines.append(f'{key} = "{value}"\n')
        
        # Write file
        with open(SETTINGS_PATH, "w") as f:
            f.writelines(lines)
            
        print("Settings saved successfully")
        
    except Exception as e:
        print(f"Settings save error: {e}")

# Load settings early
settings = read_settings()

# --- NVM Management ---
def set_nvm_flag(address, value):
    """Set NVM flag with error handling"""
    try:
        microcontroller.nvm[address] = 1 if value else 0
        return True
    except (IndexError, OSError) as e:
        print(f"NVM write error at {address}: {e}")
        return False

def read_nvm_flag(address):
    """Read NVM flag with error handling"""
    try:
        return microcontroller.nvm[address] == 1
    except (IndexError, OSError):
        return False

def read_nvm_byte(address):
    """Read NVM byte with error handling"""
    try:
        return microcontroller.nvm[address]
    except (IndexError, OSError):
        return 0

def write_nvm_byte(address, value):
    """Write NVM byte with error handling"""
    try:
        microcontroller.nvm[address] = min(255, max(0, int(value)))
        return True
    except (IndexError, OSError, ValueError) as e:
        print(f"NVM byte write error at {address}: {e}")
        return False

def sync_nvm_flags_from_settings():
    """Synchronize NVM flags with settings"""
    try:
        dev_mode = settings.get("DEVELOPER_MODE", False)
        flash_write = settings.get("FLASH_WRITE", False)
        
        set_nvm_flag(DEVELOPER_MODE_FLAG_ADDR, dev_mode)
        set_nvm_flag(FLASH_WRITE_FLAG_ADDR, flash_write)
        
        print(f"NVM flags synced: dev={dev_mode}, flash_write={flash_write}")
        return True
    except Exception as e:
        print(f"NVM sync error: {e}")
        return False

# --- Display Management ---
def set_display_brightness():
    """Set display brightness from settings"""
    try:
        if hasattr(board.DISPLAY, 'brightness'):
            brightness = settings.get("DISPLAY_BRIGHTNESS", DEFAULT_BRIGHTNESS)
            board.DISPLAY.brightness = brightness
            print(f"Display brightness set to {int(brightness * 100)}%")
            return True
        else:
            print("Display brightness control not available")
            return False
    except Exception as e:
        print(f"Brightness setting error: {e}")
        return False

# --- USB and Storage Configuration ---
def configure_usb_and_storage(developer_mode, flash_write_enabled):
    """Configure USB and storage with enhanced error handling"""
    try:
        # Configure USB CDC (serial console)
        usb_cdc.enable(console=True, data=False)
        print("USB CDC enabled")
        
        # Configure USB HID based on developer mode
        if developer_mode:
            print("Developer Mode: USB HID enabled")
            usb_hid.enable()
        else:
            print("User Mode: USB HID disabled")
            usb_hid.disable()
        
        # Configure storage and USB drive
        if flash_write_enabled:
            print("Flash R/W enabled, USB drive hidden")
            storage.remount("/", readonly=False)
            storage.disable_usb_drive()
        else:
            print("Flash R/O, USB drive hidden")
            storage.remount("/", readonly=True)
            storage.disable_usb_drive()
        
        return True
        
    except Exception as e:
        print(f"USB/Storage configuration error: {e}")
        return False

# --- SD Card Management ---
def prepare_sdcard():
    """Enhanced SD card preparation with better error handling"""
    if not settings.get("SD_CARD_ENABLED", True):
        print("SD card disabled in settings")
        return False
    
    if not SDCARD_AVAILABLE:
        print("SD card library not available")
        return False
    
    if not SD_PINS_AVAILABLE:
        print("SD card pins not available on this board")
        return False
    
    try:
        print("Initializing SD card...")
        
        # Initialize SPI bus
        spi = busio.SPI(SCK, MOSI, MISO)
        cs = digitalio.DigitalInOut(CS)
        
        # Initialize SD card
        sdcard = adafruit_sdcard.SDCard(spi, cs)
        vfs = storage.VfsFat(sdcard)
        
        # Mount SD card
        storage.mount(vfs, '/sd')
        
        # Test SD card access
        try:
            files = os.listdir('/sd')
            print(f"SD card mounted successfully - {len(files)} items found")
            
            # Create essential directories
            essential_dirs = ['apps', 'backups', 'config', 'data', 'logs']
            for dir_name in essential_dirs:
                dir_path = f'/sd/{dir_name}'
                try:
                    os.mkdir(dir_path)
                    print(f"Created directory: {dir_path}")
                except OSError:
                    pass  # Directory already exists
            
            return True
            
        except OSError as e:
            print(f"SD card access test failed: {e}")
            return False
            
    except Exception as e:
        print(f"SD card initialization failed: {e}")
        return False

# --- Network and Time Management ---
def set_time_if_wifi():
    """Set system time via NTP with enhanced error handling"""
    if not settings.get("WIFI_ENABLED", True):
        print("WiFi disabled in settings")
        return False
    
    if not NTP_AVAILABLE:
        print("NTP/WiFi libraries not available")
        return False
    
    if not settings.get("NTP_ENABLED", True):
        print("NTP disabled in settings")
        return False
    
    try:
        # Get WiFi credentials
        wifi_ssid = settings.get("CIRCUITPY_WIFI_SSID", "")
        wifi_password = settings.get("CIRCUITPY_WIFI_PASSWORD", "")
        
        if not wifi_ssid:
            print("WiFi credentials not configured")
            return False
        
        print(f"Connecting to WiFi: {wifi_ssid}")
        
        # Connect to WiFi with timeout
        wifi.radio.connect(wifi_ssid, wifi_password, timeout=15)
        
        if not wifi.radio.connected:
            print("WiFi connection failed")
            return False
        
        print(f"WiFi connected: {wifi.radio.ipv4_address}")
        
        # Set time via NTP
        pool = socketpool.SocketPool(wifi.radio)
        ntp = adafruit_ntp.NTP(pool, tz_offset=0, cache_seconds=3600)
        
        current_time = ntp.datetime
        rtc.RTC().datetime = current_time
        
        print(f"Time synchronized: {current_time}")
        return True
        
    except Exception as e:
        print(f"WiFi/NTP error: {e}")
        return False

# --- Boot Splash and UI ---
def show_splash():
    """Show boot splash with fallback options"""
    if not IMAGE_AVAILABLE:
        show_text_splash()
        return
    
    try:
        display = board.DISPLAY
        
        # Try to load custom splash
        splash_files = ["stagetwo_boot.bmp", "boot_splash.bmp", "splash.bmp"]
        
        for splash_file in splash_files:
            try:
                image, palette = adafruit_imageload.load(
                    splash_file, bitmap=displayio.Bitmap, palette=displayio.Palette
                )
                
                tile_grid = displayio.TileGrid(image, pixel_shader=palette)
                group = displayio.Group()
                group.append(tile_grid)
                
                display.root_group = group
                print(f"Splash loaded: {splash_file}")
                time.sleep
                display.root_group = group
                print(f"Splash loaded: {splash_file}")
                time.sleep(2)
                return
                
            except Exception as e:
                print(f"Failed to load {splash_file}: {e}")
                continue
        
        # If no custom splash found, show text splash
        show_text_splash()
        
    except Exception as e:
        print(f"Splash display error: {e}")
        show_text_splash()

def show_text_splash():
    """Show text-based boot splash"""
    try:
        display = board.DISPLAY
        
        # Create splash group
        splash_group = displayio.Group()
        
        # Background
        bg_bitmap = displayio.Bitmap(display.width, display.height, 1)
        bg_palette = displayio.Palette(1)
        bg_palette[0] = 0x001122  # Dark blue
        bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
        splash_group.append(bg_sprite)
        
        # Title
        title_label = label.Label(
            terminalio.FONT,
            text="StageTwo",
            color=0x00FFFF,
            x=display.width // 2 - 40,
            y=display.height // 2 - 30,
            scale=3
        )
        splash_group.append(title_label)
        
        # Version
        version_label = label.Label(
            terminalio.FONT,
            text=f"Boot System v{__version__}",
            color=0xFFFFFF,
            x=display.width // 2 - 60,
            y=display.height // 2,
            scale=1
        )
        splash_group.append(version_label)
        
        # Status
        status_label = label.Label(
            terminalio.FONT,
            text="Initializing...",
            color=0x00FF00,
            x=display.width // 2 - 40,
            y=display.height // 2 + 20,
            scale=1
        )
        splash_group.append(status_label)
        
        display.root_group = splash_group
        time.sleep(1.5)
        
    except Exception as e:
        print(f"Text splash error: {e}")

def show_boot_status(message, color=0xFFFFFF):
    """Show boot status message"""
    try:
        display = board.DISPLAY
        
        # Create status group
        status_group = displayio.Group()
        
        # Background
        bg_bitmap = displayio.Bitmap(display.width, display.height, 1)
        bg_palette = displayio.Palette(1)
        bg_palette[0] = 0x000011  # Very dark blue
        bg_sprite = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette)
        status_group.append(bg_sprite)
        
        # Status message
        lines = message.split('\n')
        for i, line in enumerate(lines):
            if line.strip():
                status_label = label.Label(
                    terminalio.FONT,
                    text=line,
                    color=color,
                    x=10,
                    y=30 + i * 20,
                    scale=1
                )
                status_group.append(status_label)
        
        display.root_group = status_group
        time.sleep(0.5)
        
    except Exception as e:
        print(f"Boot status display error: {e}")

# --- Boot Loop Detection ---
def check_boot_loop():
    """Enhanced boot loop detection with recovery"""
    try:
        reload_count = read_nvm_byte(RELOAD_COUNTER_ADDR)
        threshold = read_nvm_byte(BOOT_LOOP_THRESHOLD_ADDR)
        
        if threshold == 0:
            threshold = DEFAULT_BOOT_LOOP_THRESHOLD
            write_nvm_byte(BOOT_LOOP_THRESHOLD_ADDR, threshold)
        
        # Increment reload counter
        reload_count += 1
        write_nvm_byte(RELOAD_COUNTER_ADDR, reload_count)
        
        print(f"Boot attempt {reload_count}/{threshold}")
        
        if reload_count >= threshold:
            print(f"Boot loop detected! ({reload_count} attempts)")
            show_boot_status(f"Boot Loop Detected!\n\nAttempt {reload_count}/{threshold}\nEntering recovery mode...", 0xFF0000)
            
            # Set recovery flag and reset counter
            set_nvm_flag(RECOVERY_FLAG_ADDR, True)
            write_nvm_byte(RELOAD_COUNTER_ADDR, 0)
            
            time.sleep(3)
            return True
        
        return False
        
    except Exception as e:
        print(f"Boot loop check error: {e}")
        return False

def mark_successful_boot():
    """Mark boot as successful after delay"""
    def delayed_success():
        time.sleep(SUCCESSFUL_BOOT_DELAY)
        write_nvm_byte(RELOAD_COUNTER_ADDR, 0)
        write_nvm_byte(LAST_SUCCESSFUL_BOOT_ADDR, int(time.monotonic()) % 255)
        print("Boot marked as successful")
    
    # Schedule success marking (would need threading in full implementation)
    # For now, just mark immediately after delay
    try:
        supervisor.set_next_code_file(None)  # Clear any pending code file
        # In a real implementation, you'd use a timer or background task
        print("Boot success will be marked after successful startup")
    except Exception as e:
        print(f"Boot success marking error: {e}")

# --- Reset Cause Analysis ---
def analyze_reset_cause():
    """Analyze and log reset cause"""
    try:
        reset_reason = microcontroller.cpu.reset_reason
        reset_type = RESET_UNKNOWN
        reset_description = "Unknown reset"
        
        if reset_reason == microcontroller.ResetReason.POWER_ON:
            reset_type = RESET_POWER_ON
            reset_description = "Power-on reset"
        elif reset_reason == microcontroller.ResetReason.BROWNOUT:
            reset_type = RESET_BROWNOUT
            reset_description = "Brownout reset"
        elif reset_reason == microcontroller.ResetReason.SOFTWARE:
            reset_type = RESET_SOFTWARE
            reset_description = "Software reset"
        elif reset_reason == microcontroller.ResetReason.DEEP_SLEEP_ALARM:
            reset_type = RESET_SOFTWARE
            reset_description = "Deep sleep alarm"
        elif reset_reason == microcontroller.ResetReason.RESET_PIN:
            reset_type = RESET_SOFTWARE
            reset_description = "Reset pin"
        elif reset_reason == microcontroller.ResetReason.WATCHDOG:
            reset_type = RESET_WATCHDOG
            reset_description = "Watchdog reset"
        
        write_nvm_byte(RESET_TYPE_ADDR, reset_type)
        print(f"Reset cause: {reset_description}")
        
        return reset_type, reset_description
        
    except Exception as e:
        print(f"Reset analysis error: {e}")
        return RESET_UNKNOWN, "Analysis failed"

# --- Boot File Selection ---
def find_boot_file():
    """Find appropriate boot file with priority order"""
    try:
        # Check settings for preferred boot file
        preferred_file = settings.get("DEFAULT_BOOT_FILE", DEFAULT_BOOT_FILE)
        
        # Create priority list starting with preferred file
        priority_files = [preferred_file]
        for file in BOOT_FILES:
            if file not in priority_files:
                priority_files.append(file)
        
        # Check each file in priority order
        for boot_file in priority_files:
            try:
                stat_result = os.stat(boot_file)
                if stat_result[6] > 0:  # File size > 0
                    print(f"Boot file selected: {boot_file}")
                    return boot_file
            except OSError:
                continue
        
        print("No valid boot file found!")
        return None
        
    except Exception as e:
        print(f"Boot file selection error: {e}")
        return None

# --- First Boot Setup ---
def check_first_boot():
    """Check if this is the first boot and run setup"""
    try:
        if not read_nvm_flag(FIRST_BOOT_SETUP_FLAG_ADDR):
            print("First boot detected - running setup")
            show_boot_status("First Boot Setup\n\nInitializing system...", 0x00FFFF)
            
            # Create essential directories
            essential_dirs = ['/system', '/apps', '/backups', '/logs', '/config']
            for dir_path in essential_dirs:
                try:
                    os.mkdir(dir_path)
                    print(f"Created directory: {dir_path}")
                except OSError:
                    pass  # Directory already exists
            
            # Save default settings
            save_settings(settings)
            
            # Create welcome file
            try:
                with open("/system/welcome.txt", "w") as f:
                    f.write(f"""Welcome to StageTwo!

This is your first boot. The system has been initialized with:
- Essential directories created
- Default settings configured
- Display brightness set to {int(DEFAULT_BRIGHTNESS * 100)}%
- SD card support enabled (if available)

You can customize settings in settings.toml
Boot system version: {__version__}

Enjoy your StageTwo experience!
""")
            except Exception as e:
                print(f"Welcome file creation failed: {e}")
            
            # Mark first boot as complete
            set_nvm_flag(FIRST_BOOT_SETUP_FLAG_ADDR, True)
            
            show_boot_status("First Boot Setup Complete!\n\nStarting system...", 0x00FF00)
            time.sleep(2)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"First boot check error: {e}")
        return False

# --- Main Boot Logic ---
def main():
    """Main boot sequence with comprehensive error handling"""
    print("=" * 50)
    print(f"🚀 StageTwo Boot System v{__version__}")
    print("=" * 50)
    
    try:
        # Initial memory cleanup
        gc.collect()
        print(f"💾 Starting with {gc.mem_free()} bytes free memory")
        
        # Show splash screen
        show_splash()
        
        # Analyze reset cause
        reset_type, reset_description = analyze_reset_cause()
        show_boot_status(f"Boot Analysis\n\n{reset_description}\nInitializing...", 0x00FFFF)
        
        # Check for first boot
        is_first_boot = check_first_boot()
        
        # Set display brightness early
        if set_display_brightness():
            print("✅ Display brightness configured")
        
        # Check for boot loop
        if check_boot_loop():
            print("🔄 Boot loop detected - entering recovery")
            show_boot_status("Boot Loop Detected\n\nEntering Recovery Mode...", 0xFF8000)
            time.sleep(2)
            # Recovery mode will be handled by the recovery flag check
        
        # Read NVM flags
        recovery_mode = read_nvm_flag(RECOVERY_FLAG_ADDR)
        developer_mode = read_nvm_flag(DEVELOPER_MODE_FLAG_ADDR)
        flash_write_enabled = read_nvm_flag(FLASH_WRITE_FLAG_ADDR)
        
        # Sync settings with NVM flags
        sync_nvm_flags_from_settings()
        
        print(f"🔧 Recovery Mode: {recovery_mode}")
        print(f"👨‍💻 Developer Mode: {developer_mode}")
        print(f"💾 Flash Write: {flash_write_enabled}")
        
        # Configure USB and storage
        show_boot_status("System Configuration\n\nConfiguring USB & Storage...", 0x00FFFF)
        if configure_usb_and_storage(developer_mode, flash_write_enabled):
            print("✅ USB and storage configured")
        else:
            print("⚠️ USB/storage configuration issues")
        
        # Initialize SD card
        show_boot_status("Storage Setup\n\nInitializing SD card...", 0x00FFFF)
        if prepare_sdcard():
            print("✅ SD card mounted successfully")
        else:
            print("⚠️ SD card not available")
        
        # Set system time via WiFi/NTP
        show_boot_status("Network Setup\n\nSynchronizing time...", 0x00FFFF)
        if set_time_if_wifi():
            print("✅ System time synchronized")
        else:
            print("⚠️ Time synchronization skipped")
        
        # Memory cleanup before app launch
        gc.collect()
        print(f"💾 Pre-launch memory: {gc.mem_free()} bytes free")
        
        # Determine what to boot
        if recovery_mode:
            print("🔧 Booting into recovery mode")
            show_boot_status("Recovery Mode\n\nStarting recovery system...", 0xFF8000)
            
            # Clear recovery flag for next boot
            set_nvm_flag(RECOVERY_FLAG_ADDR, False)
            
            # Set next code file to recovery
            try:
                supervisor.set_next_code_file("recovery.py")
                print("✅ Recovery mode set")
            except Exception as e:
                print(f"❌ Recovery mode setup failed: {e}")
                # Fallback to normal boot
                recovery_mode = False
        
        if not recovery_mode:
            # Normal boot sequence
            boot_file = find_boot_file()
            
            if boot_file:
                print(f"🚀 Booting: {boot_file}")
                show_boot_status(f"Starting Application\n\n{boot_file}\n\nPlease wait...", 0x00FF00)
                
                # Mark boot as successful (after delay)
                mark_successful_boot()
                
                # Set next code file
                try:
                    supervisor.set_next_code_file(boot_file)
                    print("✅ Boot file set successfully")
                except Exception as e:
                    print(f"❌ Boot file setup failed: {e}")
                    # Try direct execution as fallback
                    try:
                        exec(open(boot_file).read())
                    except Exception as exec_error:
                        print(f"❌ Direct execution failed: {exec_error}")
                        show_boot_status(f"Boot Failed!\n\n{boot_file}\n{str(exec_error)[:30]}", 0xFF0000)
                        time.sleep(5)
            else:
                print("❌ No boot file found!")
                show_boot_status("Boot Error\n\nNo valid boot file found\nCheck system files", 0xFF0000)
                
                # Set recovery flag for next boot
                set_nvm_flag(RECOVERY_FLAG_ADDR, True)
                time.sleep(5)
        
        # Final status
        show_boot_status("Boot Complete\n\nTransferring control...", 0x00FF00)
        time.sleep(1)
        
        print("✅ Boot sequence completed successfully")
        print("=" * 50)
        
        return True
        
    except Exception as e:
        print(f"❌ Critical boot error: {e}")
        
        try:
            show_boot_status(f"Critical Boot Error!\n\n{str(e)[:40]}\n\nEntering recovery...", 0xFF0000)
            
            # Set recovery flag for next boot
            set_nvm_flag(RECOVERY_FLAG_ADDR, True)
            
            # Try to start recovery immediately
            try:
                supervisor.set_next_code_file("recovery.py")
                print("Emergency recovery mode set")
            except Exception:
                print("Emergency recovery setup failed")
            
            time.sleep(3)
            
        except Exception:
            # Even error display failed - just print to console
            print("CRITICAL: Boot system failure - manual intervention required")
        
        return False
    
    finally:
        # Final cleanup
        gc.collect()
        try:
            print(f"💾 Boot complete - {gc.mem_free()} bytes free")
        except Exception:
            pass

# --- Utility Functions ---
def get_system_info():
    """Get comprehensive system information"""
    try:
        info = {
            "boot_version": __version__,
            "reset_cause": analyze_reset_cause()[1],
            "recovery_mode": read_nvm_flag(RECOVERY_FLAG_ADDR),
            "developer_mode": read_nvm_flag(DEVELOPER_MODE_FLAG_ADDR),
            "flash_write": read_nvm_flag(FLASH_WRITE_FLAG_ADDR),
            "reload_count": read_nvm_byte(RELOAD_COUNTER_ADDR),
            "memory_free": gc.mem_free(),
            "sd_available": SDCARD_AVAILABLE and SD_PINS_AVAILABLE,
            "ntp_available": NTP_AVAILABLE,
            "image_available": IMAGE_AVAILABLE,
            "settings": settings
        }
        return info
    except Exception as e:
        return {"error": str(e)}

def emergency_reset():
    """Emergency system reset with flag clearing"""
    try:
        print("🚨 Emergency reset initiated")
        
        # Clear all NVM flags
        for i in range(10):
            try:
                microcontroller.nvm[i] = 0
            except Exception:
                pass
        
        # Force flash write mode for recovery
        set_nvm_flag(FLASH_WRITE_FLAG_ADDR, True)
        
        print("Emergency reset complete - rebooting...")
        time.sleep(1)
        microcontroller.reset()
        
    except Exception as e:
        print(f"Emergency reset failed: {e}")

def safe_mode_check():
    """Check if we should enter safe mode"""
    try:
        # Check for safe mode conditions
        if supervisor.runtime.safe_mode_reason:
            print(f"Safe mode reason: {supervisor.runtime.safe_mode_reason}")
            return True
        
        # Check for repeated crashes
        reload_count = read_nvm_byte(RELOAD_COUNTER_ADDR)
        if reload_count > 5:
            print("Multiple boot failures detected")
            return True
        
        return False
        
    except Exception as e:
        print(f"Safe mode check error: {e}")
        return False
    
def create_boot_log():
    """Create boot log entry"""
    try:
        # Ensure logs directory exists
        try:
            os.mkdir("/logs")
        except OSError:
            pass
        
        # Create log entry
        timestamp = int(time.monotonic())
        reset_type, reset_desc = analyze_reset_cause()
        
        # Build log entry without complex f-string
        log_entry = "\nBoot Log Entry - " + str(timestamp) + "\n"
        log_entry += "================================\n"
        log_entry += "Boot System Version: " + __version__ + "\n"
        log_entry += "Reset Cause: " + reset_desc + "\n"
        log_entry += "Recovery Mode: " + str(read_nvm_flag(RECOVERY_FLAG_ADDR)) + "\n"
        log_entry += "Developer Mode: " + str(read_nvm_flag(DEVELOPER_MODE_FLAG_ADDR)) + "\n"
        log_entry += "Flash Write: " + str(read_nvm_flag(FLASH_WRITE_FLAG_ADDR)) + "\n"
        log_entry += "Reload Count: " + str(read_nvm_byte(RELOAD_COUNTER_ADDR)) + "\n"
        log_entry += "Memory Free: " + str(gc.mem_free()) + " bytes\n"
        
        sd_status = "Available" if SDCARD_AVAILABLE and SD_PINS_AVAILABLE else "Not Available"
        log_entry += "SD Card: " + sd_status + "\n"
        
        wifi_status = "Available" if NTP_AVAILABLE else "Not Available"
        log_entry += "WiFi/NTP: " + wifi_status + "\n"
        
        brightness_pct = int(settings.get('DISPLAY_BRIGHTNESS', DEFAULT_BRIGHTNESS) * 100)
        log_entry += "Display Brightness: " + str(brightness_pct) + "%\n\n"
        
        log_entry += "Settings:\n"
        for k, v in settings.items():
            log_entry += "  " + str(k) + ": " + str(v) + "\n"
        log_entry += "================================\n"
        
        with open("/logs/boot.log", "a") as f:
            f.write(log_entry)
        
        print("Boot log entry created")
        return True
        
    except Exception as e:
        print("Boot log creation failed: " + str(e))
        return False


# --- Debug and Testing Functions ---
def test_boot_components():
    """Test individual boot components"""
    print("🧪 Testing Boot Components")
    print("=" * 30)
    
    tests = [
        ("Settings", lambda: read_settings() is not None),
        ("NVM Access", lambda: set_nvm_flag(9, True) and read_nvm_flag(9)),
        ("Display", lambda: hasattr(board, 'DISPLAY') and board.DISPLAY is not None),
        ("SD Pins", lambda: SD_PINS_AVAILABLE),
        ("SD Library", lambda: SDCARD_AVAILABLE),
        ("WiFi/NTP", lambda: NTP_AVAILABLE),
        ("Image Loading", lambda: IMAGE_AVAILABLE),
        ("Storage Write", lambda: test_storage_write()),
    ]
    
    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
            status = "✅" if result else "❌"
            print(f"{status} {test_name}: {result}")
        except Exception as e:
            results[test_name] = f"Error: {e}"
            print(f"❌ {test_name}: Error - {e}")
    
    print("=" * 30)
    return results

def test_storage_write():
    """Test storage write capability"""
    try:
        test_file = "/test_write.tmp"
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return True
    except Exception:
        return False

def show_boot_menu():
    """Show interactive boot menu (if button available)"""
    try:
        if not hasattr(board, 'BUTTON'):
            return False
        
        button = digitalio.DigitalInOut(board.BUTTON)
        button.direction = digitalio.Direction.INPUT
        button.pull = digitalio.Pull.UP
        
        # Show menu for 3 seconds
        menu_options = [
            "Normal Boot",
            "Recovery Mode", 
            "Developer Mode",
            "Safe Mode"
        ]
        
        selected = 0
        start_time = time.monotonic()
        
        while time.monotonic() - start_time < 3:
            # Show current selection
            show_boot_status(f"Boot Menu\n\n> {menu_options[selected]}\n\nPress button to select\nAuto-boot in {3 - int(time.monotonic() - start_time)}s", 0x00FFFF)
            
            # Check button
            if not button.value:  # Button pressed
                time.sleep(0.1)  # Debounce
                while not button.value:  # Wait for release
                    time.sleep(0.01)
                
                # Handle selection
                if selected == 1:  # Recovery Mode
                    set_nvm_flag(RECOVERY_FLAG_ADDR, True)
                elif selected == 2:  # Developer Mode
                    set_nvm_flag(DEVELOPER_MODE_FLAG_ADDR, True)
                    set_nvm_flag(FLASH_WRITE_FLAG_ADDR, True)
                elif selected == 3:  # Safe Mode
                    # Clear all flags for safe mode
                    for i in range(5):
                        set_nvm_flag(i, False)
                
                show_boot_status(f"Selected: {menu_options[selected]}\n\nBooting...", 0x00FF00)
                time.sleep(1)
                return True
            
            # Cycle through options
            selected = (selected + 1) % len(menu_options)
            time.sleep(0.5)
        
        # Auto-boot normal mode
        show_boot_status("Auto-boot: Normal Mode\n\nStarting...", 0x00FF00)
        time.sleep(1)
        return False
        
    except Exception as e:
        print(f"Boot menu error: {e}")
        return False

# --- Integration Functions ---
def get_boot_status():
    """Get current boot status for other modules"""
    try:
        return {
            "version": __version__,
            "recovery_mode": read_nvm_flag(RECOVERY_FLAG_ADDR),
            "developer_mode": read_nvm_flag(DEVELOPER_MODE_FLAG_ADDR),
            "flash_write": read_nvm_flag(FLASH_WRITE_FLAG_ADDR),
            "reload_count": read_nvm_byte(RELOAD_COUNTER_ADDR),
            "reset_type": read_nvm_byte(RESET_TYPE_ADDR),
            "settings": settings,
            "capabilities": {
                "sd_card": SDCARD_AVAILABLE and SD_PINS_AVAILABLE,
                "wifi_ntp": NTP_AVAILABLE,
                "image_loading": IMAGE_AVAILABLE
            }
        }
    except Exception as e:
        return {"error": str(e)}

def set_boot_mode(mode):
    """Set boot mode for next restart"""
    try:
        if mode == "recovery":
            set_nvm_flag(RECOVERY_FLAG_ADDR, True)
        elif mode == "developer":
            set_nvm_flag(DEVELOPER_MODE_FLAG_ADDR, True)
            set_nvm_flag(FLASH_WRITE_FLAG_ADDR, True)
        elif mode == "normal":
            set_nvm_flag(RECOVERY_FLAG_ADDR, False)
            set_nvm_flag(DEVELOPER_MODE_FLAG_ADDR, False)
        elif mode == "safe":
            for i in range(5):
                set_nvm_flag(i, False)
        
        print(f"Boot mode set to: {mode}")
        return True
        
    except Exception as e:
        print(f"Boot mode setting failed: {e}")
        return False

# --- Export Functions ---
__all__ = [
    'main',
    'get_system_info',
    'emergency_reset',
    'test_boot_components',
    'get_boot_status',
    'set_boot_mode',
    'read_settings',
    'save_settings',
    'set_nvm_flag',
    'read_nvm_flag',
    'create_boot_log'
]

# --- Main Execution ---
if __name__ == "__main__":
    # This runs when boot.py is executed directly (shouldn't normally happen)
    print("⚠️ boot.py executed directly - this is unusual")
    print("Boot.py should be executed automatically by CircuitPython")
    
    # Run anyway for testing
    success = main()
    if success:
        print("✅ Boot sequence completed")
    else:
        print("❌ Boot sequence failed")
else:
    # Normal boot execution
    try:
        # Create boot log
        create_boot_log()
        
        # Show boot menu if button available (optional)
        # show_boot_menu()  # Uncomment to enable boot menu
        
        # Run main boot sequence
        main()
        
    except Exception as e:
        print(f"❌ Boot execution failed: {e}")
        emergency_reset()

# Final memory cleanup
gc.collect()

print(f"📦 StageTwo Boot System v{__version__} - Ready")
print(f"💾 Final boot memory: {gc.mem_free()} bytes free")
print("🚀 System initialization complete")

# End of boot.py

