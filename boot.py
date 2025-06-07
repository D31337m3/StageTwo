### Boot.py ==========================================================\
# StageTwo - Bootloader       *for ESP32-S3*                   V 0.9   |
# =========================================================================\
#                                                                           \
#  BOOT.PY -                                                                 |
#            Enhanced Bootloader for ESP32-S3 Microcontrollers               |
#                                                                            |
#     System Dependants - CircuitPython 9.x.x / 10.x.x 
#                       - Adafruit Libraries (Bundle 9.x)
# 
#     Internal to StageTwo Dependancies - 
#                      - Boot.py * This File 
#                      - Recovery.py * StageTwo Recovery / Web Recovery 
#                        platform
#                      - web_interface_server.py * WebUI Framework
#                      - psycho.py * P$yCho Tool Suite library (provides 
#                        addons , plugins and custom implements ie: AppLoader)
# ============================================================================


print("STAGETWO BOOTLOADER V0.9    (C) 2025 Devin Ranger")
import time
time.sleep(1)
print('SYSTEM: INITIALIZING STAGETWO BOOT SYSTEM')

# Core imports - minimal dependencies
import usb_cdc
import usb_hid
import board
import digitalio
import wifi
import microcontroller
import supervisor
import os
import storage
import busio
import random
import gc
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_display_shapes.rect import Rect
import json

# Try to import SD card support
try:
    import adafruit_sdcard
    import sdcardio
    SD_AVAILABLE = True
except ImportError:
    SD_AVAILABLE = False
    print("SD card libraries not available")

# Built-in logging system
class StageTwoLogger:
    """Built-in logging system for StageTwoBootloader"""
    
    def __init__(self):
        self.initialized = False
        self.log_to_file = False
        self.log_file_path = None
        self.console_only = True
        
    def init(self, log_path="/logs"):
        """Initialize logging system"""
        try:
            # Ensure log directory exists
            if not self._dir_exists(log_path):
                try:
                    os.makedirs(log_path)
                except OSError:
                    pass  # Directory might already exist
            
            # Set log file path
            timestamp = int(time.monotonic())
            self.log_file_path = f"{log_path}/boot_{timestamp}.log"
            
            # Test write access
            try:
                with open(self.log_file_path, "w") as f:
                    f.write(f"StageTwoBootloader V1.0 Log Started\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write("="*50 + "\n")
                
                self.log_to_file = True
                self.console_only = False
                self.initialized = True
                print(f"Logging initialized: {self.log_file_path}")
                return True
                
            except OSError:
                print("File logging unavailable - console only")
                self.console_only = True
                self.initialized = True
                return False
                
        except Exception as e:
            print(f"Logger init failed: {e}")
            self.console_only = True
            self.initialized = True
            return False
    
    def _dir_exists(self, path):
        """Check if directory exists"""
        try:
            os.listdir(path)
            return True
        except OSError:
            return False
    
    def log(self, level, category, message):
        """Log message with level and category"""
        try:
            log_line = f"[{level}] {category}: {message}"
            
            # Always print to console
            print(log_line)
            
            # Write to file if available
            if self.log_to_file and self.log_file_path:
                try:
                    with open(self.log_file_path, "a") as f:
                        timestamp = int(time.monotonic())
                        f.write(f"{timestamp} {log_line}\n")
                except OSError:
                    # File system might be read-only
                    pass
                    
        except Exception:
            # Fallback to simple print
            try:
                print(f"[{level}] {category}: {message}")
            except:
                pass
    
    def info(self, category, message):
        self.log("INFO", category, message)
    
    def warn(self, category, message):
        self.log("WARN", category, message)
    
    def error(self, category, message):
        self.log("ERROR", category, message)
    
    def debug(self, category, message):
        self.log("DEBUG", category, message)
    
    def critical(self, category, message):
        self.log("CRITICAL", category, message)

# Initialize global logger
_logger = StageTwoLogger()

def log_safe(category, message, level="INFO"):
    """Safe logging function"""
    if _logger.initialized:
        _logger.log(level, category, message)
    else:
        print(f"[{level}] {category}: {message}")

# TOML parser (minimal implementation)
def parse_toml_simple(content):
    """Simple TOML parser for basic key=value pairs"""
    config = {}
    try:
        lines = content.strip().split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Section headers
            if line.startswith('[') and line.endswith(']'):
                current_section = line[1:-1]
                if current_section not in config:
                    config[current_section] = {}
                continue
            
            # Key-value pairs
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                # Convert boolean and numeric values
                if value.lower() in ('true', 'false'):
                    value = value.lower() == 'true'
                elif value.isdigit():
                    value = int(value)
                elif value.replace('.', '').isdigit():
                    value = float(value)
                
                if current_section:
                    config[current_section][key] = value
                else:
                    config[key] = value
    
    except Exception as e:
        log_safe("TOML", f"Parse error: {e}", "ERROR")
    
    return config

def load_toml_config(file_path):
    """Load TOML configuration file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        return parse_toml_simple(content)
    except Exception as e:
        log_safe("CONFIG", f"Failed to load {file_path}: {e}", "WARN")
        return {}

def save_toml_config(file_path, config):
    """Save configuration to TOML file"""
    try:
        content = ""
        
        # Write non-section keys first
        for key, value in config.items():
            if not isinstance(value, dict):
                if isinstance(value, str):
                    content += f'{key} = "{value}"\n'
                elif isinstance(value, bool):
                    content += f'{key} = {str(value).lower()}\n'
                else:
                    content += f'{key} = {value}\n'
        
        # Write sections
        for section, section_data in config.items():
            if isinstance(section_data, dict):
                content += f'\n[{section}]\n'
                for key, value in section_data.items():
                    if isinstance(value, str):
                        content += f'{key} = "{value}"\n'
                    elif isinstance(value, bool):
                        content += f'{key} = {str(value).lower()}\n'
                    else:
                        content += f'{key} = {value}\n'
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        return True
        
    except Exception as e:
        log_safe("CONFIG", f"Failed to save {file_path}: {e}", "ERROR")
        return False

def auto_connect_wifi():
    """Auto-connect to WiFi using settings.toml or config files"""
    try:
        if wifi.radio.connected:
            log_safe("WIFI", f"Already connected: {wifi.radio.ipv4_address}")
            return True
        
        # Try CircuitPython settings.toml first
        try:
            ssid = os.getenv('CIRCUITPY_WIFI_SSID')
            password = os.getenv('CIRCUITPY_WIFI_PASSWORD')
            
            if ssid and password:
                log_safe("WIFI", f"Connecting via settings.toml: {ssid}")
                wifi.radio.connect(ssid, password)
                
                timeout = 15
                while not wifi.radio.connected and timeout > 0:
                    time.sleep(1)
                    timeout -= 1
                
                if wifi.radio.connected:
                    log_safe("WIFI", f"Connected: {wifi.radio.ipv4_address}")
                    return True
        
        except Exception as e:
            log_safe("WIFI", f"Settings.toml connection failed: {e}", "WARN")
        
        # Try config files
        config_paths = ["/sd/config/wifi.toml", "/config/wifi.toml"]
        
        for config_path in config_paths:
            try:
                wifi_config = load_toml_config(config_path)
                
                ssid = wifi_config.get("ssid") or wifi_config.get("wifi", {}).get("ssid")
                password = wifi_config.get("password") or wifi_config.get("wifi", {}).get("password")
                
                if ssid and password:
                    log_safe("WIFI", f"Connecting via {config_path}: {ssid}")
                    wifi.radio.connect(ssid, password)
                    
                    timeout = 15
                    while not wifi.radio.connected and timeout > 0:
                        time.sleep(1)
                        timeout -= 1
                    
                    if wifi.radio.connected:
                        log_safe("WIFI", f"Connected: {wifi.radio.ipv4_address}")
                        return True
            
            except Exception as e:
                log_safe("WIFI", f"Config {config_path} failed: {e}", "WARN")
                continue
        
        log_safe("WIFI", "Auto-connect failed - no valid credentials", "WARN")
        return False
        
    except Exception as e:
        log_safe("WIFI", f"WiFi connection error: {e}", "ERROR")
        return False

# Auto-connect WiFi early
auto_connect_wifi()

# Disable autoreload
supervisor.runtime.autoreload = False

class StageTwoBootloader:
    """StageTwoBootloader V1.0 - Advanced bootloader with graphical interface"""
    
    # NVM memory map (maintaining compatibility)
    NVM_RECOVERY_FLAG = 0
    NVM_BOOT_MODE = 1
    NVM_DEVELOPER_MODE = 2
    NVM_CUSTOM_BOOT_INDEX = 3
    NVM_SETTINGS_VERSION = 4
    NVM_GRAPHICS_MODE = 5
    NVM_LOG_LEVEL = 6
    NVM_USER_START = 10
    
    # Boot modes
    MODE_NORMAL = 0
    MODE_MENU = 1
    MODE_RECOVERY = 2
    MODE_CUSTOM = 3
    MODE_GRAPHICS = 4
    
    def __init__(self):
        """Initialize StageTwoBootloader"""
        log_safe("BOOT", "StageTwoBootloader V1.0 - Initializing")
        
        # Initialize core components
        self.display = None
        self.button = None
        self.sd_mounted = False
        self.flash_writable = False
        
        # Boot state
        self.recovery_mode = False
        self.developer_mode = False
        self.graphics_mode = True
        self.boot_mode = self.MODE_NORMAL
        
        # Configuration
        self.config = {}
        self.boot_files = []
        
        # Paths
        self.CONFIG_DIR = "/sd/config"
        self.BOOT_CONFIG = "/sd/config/boot.toml"
        self.APPS_CONFIG = "/sd/config/apps.toml"
        self.FALLBACK_CONFIG_DIR = "/config"
        
        # Initialize in stages
        self._init_hardware()
        self._init_logging()
        self._detect_boot_conditions()
        self._init_filesystems()
        self._ensure_config_structure()
        self._load_configuration()
        self._scan_boot_files()
        self._determine_boot_path()
        
        # Log system info
        self._log_system_startup()
    
    def _init_hardware(self):
        """Initialize hardware components"""
        try:
            # Initialize display
            try:
                self.display = board.DISPLAY
                self.display.auto_refresh = True
                log_safe("HW", "Display initialized")
            except Exception as e:
                log_safe("HW", f"Display init failed: {e}", "WARN")
                self.display = None
                self.graphics_mode = False
            
            # Initialize button
            try:
                self.button = digitalio.DigitalInOut(board.BUTTON)
                self.button.direction = digitalio.Direction.INPUT
                self.button.pull = digitalio.Pull.UP
                log_safe("HW", "Button initialized")
            except Exception as e:
                log_safe("HW", f"Button init failed: {e}", "WARN")
                self.button = None
            
        except Exception as e:
            log_safe("HW", f"Hardware init error: {e}", "ERROR")
    
    def _init_logging(self):
        """Initialize logging system"""
        try:
            # Try SD card logging first
            if self._dir_exists("/sd"):
                if _logger.init("/sd/logs"):
                    log_safe("LOG", "Logging initialized to SD card")
                    return
            
            # Fall back to flash logging
            if _logger.init("/logs"):
                log_safe("LOG", "Logging initialized to flash")
                return
            
            log_safe("LOG", "File logging unavailable - console only")
            
        except Exception as e:
            log_safe("LOG", f"Logging init failed: {e}", "ERROR")
    
    def _detect_boot_conditions(self):
        """Detect boot conditions from NVM and hardware"""
        try:
            # Read NVM flags
            self.recovery_mode = microcontroller.nvm[self.NVM_RECOVERY_FLAG] == 1
            self.boot_mode = microcontroller.nvm[self.NVM_BOOT_MODE]
            self.developer_mode = microcontroller.nvm[self.NVM_DEVELOPER_MODE] == 1
            self.graphics_mode = microcontroller.nvm[self.NVM_GRAPHICS_MODE] != 0  # Default to graphics
            
            # Check button for recovery
            if self.button and not self.button.value:
                self.recovery_mode = True
                log_safe("BOOT", "Button recovery mode detected", "WARN")
            
            # Log boot conditions
            log_safe("BOOT", f"Boot conditions - Recovery: {self.recovery_mode}, Developer: {self.developer_mode}, Graphics: {self.graphics_mode}, Mode: {self.boot_mode}")

            
        except Exception as e:
            log_safe("BOOT", f"Boot condition detection failed: {e}", "ERROR")
            self.recovery_mode = True
    
    def _init_filesystems(self):
        """Initialize and mount filesystems"""
        try:
            log_safe("FS", "Initializing filesystems")
            
            # Check flash filesystem
            self.flash_writable = self._test_flash_write()
            
            # Mount SD card if available
            if SD_AVAILABLE:
                self._mount_sd_card()
            
            # Set up filesystem access for developer mode
            if self.developer_mode and not self.flash_writable:
                self._remount_flash_rw()
            
            log_safe("FS", f"Filesystems ready - Flash: {'R/W' if self.flash_writable else 'R/O'}, SD: {'OK' if self.sd_mounted else 'N/A'}")

            
        except Exception as e:
            log_safe("FS", f"Filesystem init failed: {e}", "ERROR")
    
    def _test_flash_write(self):
        """Test if flash filesystem is writable"""
        try:
            test_file = "/stagetwo_test.tmp"
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            return True
        except OSError:
            return False
        except Exception:
            return False
    
    def _remount_flash_rw(self):
        """Remount flash filesystem as read-write"""
        try:
            storage.remount("/", readonly=False)
            self.flash_writable = True
            log_safe("FS", "Flash remounted R/W")
            return True
        except Exception as e:
            log_safe("FS", f"Flash remount failed: {e}", "WARN")
            return False
    
    def _mount_sd_card(self):
        """Mount SD card with error handling"""
        try:
            # Check if already mounted
            try:
                os.listdir("/sd")
                self.sd_mounted = True
                log_safe("FS", "SD card already mounted")
                return
            except OSError:
                pass
            
            # Initialize and mount SD card
            spi = busio.SPI(board.SD_SCK, board.SD_MOSI, board.SD_MISO)
            cs = digitalio.DigitalInOut(board.SD_CS)
            sdcard = adafruit_sdcard.SDCard(spi, cs)
            vfs = storage.VfsFat(sdcard)
            storage.mount(vfs, "/sd", readonly=False)
            
            # Verify mount
            os.listdir("/sd")
            self.sd_mounted = True
            log_safe("FS", "SD card mounted successfully")
            
            # Test write access
            test_file = f"/sd/test_{random.randint(1000, 9999)}.tmp"
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            log_safe("FS", "SD card write test passed")
            
        except Exception as e:
            log_safe("FS", f"SD card mount failed: {e}", "ERROR")
            self.sd_mounted = False
            self._show_error_animation()
    
    def _show_error_animation(self):
        """Show error animation on display"""
        if not self.display or not self.graphics_mode:
            return
        
        try:
            # Simple error display
            group = displayio.Group()
            
            # Red background
            bg = Rect(0, 0, 240, 135, fill=0xFF0000)
            group.append(bg)
            
            # Error text
            error_text = label.Label(
                terminalio.FONT,
                text="SD CARD ERROR",
                color=0xFFFFFF,
                x=60,
                y=60
            )
            group.append(error_text)
            
            self.display.root_group = group
            time.sleep(2)
            
        except Exception:
            pass
    
    def _dir_exists(self, path):
        """Check if directory exists"""
        try:
            os.listdir(path)
            return True
        except OSError:
            return False
    
    def _file_exists(self, path):
        """Check if file exists"""
        try:
            os.stat(path)
            return True
        except OSError:
            return False
    
    def _ensure_config_structure(self):
        """Ensure configuration directory structure exists"""
        try:
            config_dirs = []
            
            # Prefer SD card config
            if self.sd_mounted:
                config_dirs = ["/sd/config", "/sd/logs", "/sd/apps"]
            
            # Fallback to flash
            config_dirs.extend(["/config", "/logs", "/apps"])
            
            for config_dir in config_dirs:
                if not self._dir_exists(config_dir):
                    try:
                        # Create directory using mkdir (CircuitPython doesn't have makedirs)
                        self._create_directory_recursive(config_dir)
                        log_safe("CONFIG", f"Created directory: {config_dir}")
                    except OSError as e:
                        log_safe("CONFIG", f"Failed to create {config_dir}: {e}", "WARN")
            
            # Set primary config directory
            if self.sd_mounted and self._dir_exists("/sd/config"):
                self.CONFIG_DIR = "/sd/config"
                self.BOOT_CONFIG = "/sd/config/boot.toml"
                self.APPS_CONFIG = "/sd/config/apps.toml"
            else:
                self.CONFIG_DIR = "/config"
                self.BOOT_CONFIG = "/config/boot.toml"
                self.APPS_CONFIG = "/config/apps.toml"
            
            log_safe("CONFIG", f"Config directory: {self.CONFIG_DIR}")
            
        except Exception as e:
            log_safe("CONFIG", f"Config structure setup failed: {e}", "ERROR")

    def _create_directory_recursive(self, path):
        """Create directory recursively (CircuitPython compatible)"""
        try:
            # Split path into parts
            parts = [p for p in path.split('/') if p]
            
            # Build path incrementally
            current_path = ""
            for part in parts:
                current_path += "/" + part
                
                if not self._dir_exists(current_path):
                    try:
                        os.mkdir(current_path)
                    except OSError as e:
                        # Directory might already exist or permission denied
                        if not self._dir_exists(current_path):
                            raise e
            
            return True
            
        except Exception as e:
            log_safe("CONFIG", f"Recursive directory creation failed for {path}: {e}", "ERROR")
            return False

    def _apply_configuration(self):
        """Apply loaded configuration"""
        try:
            # Apply system settings
            system_config = self.config.get("system", {})
            self.developer_mode = system_config.get("developer_mode", self.developer_mode)
            
            # Apply display settings
            display_config = self.config.get("display", {})
            self.graphics_mode = display_config.get("graphics_mode", self.graphics_mode)
            
            # Update NVM with current settings
            microcontroller.nvm[self.NVM_DEVELOPER_MODE] = 1 if self.developer_mode else 0
            microcontroller.nvm[self.NVM_GRAPHICS_MODE] = 1 if self.graphics_mode else 0
            
            log_safe("CONFIG", "Configuration applied")
            
        except Exception as e:
            log_safe("CONFIG", f"Config apply failed: {e}", "ERROR")
    
    def _save_configuration(self):
        """Save current configuration"""
        try:
            if save_toml_config(self.BOOT_CONFIG, self.config):
                log_safe("CONFIG", "Configuration saved")
                return True
            else:
                log_safe("CONFIG", "Configuration save failed", "ERROR")
                return False
        except Exception as e:
            log_safe("CONFIG", f"Config save error: {e}", "ERROR")
            return False
    
    def _scan_boot_files(self):
        """Scan for available boot files"""
        try:
            self.boot_files = []
            
            # Get scan directories from config
            apps_config = self.config.get("apps", {})
            scan_dirs = apps_config.get("scan_directories", ["/apps", "/sd/apps", "/lib/apps"])
            
            # Add standard files
            standard_files = [
                "/main.py",
                "/code.py", 
                "/recovery.py",
                "/lib/system/loader.py"
            ]
            
            for file_path in standard_files:
                if self._file_exists(file_path):
                    self.boot_files.append({
                        "name": self._get_filename(file_path),
                        "path": file_path,
                        "type": "system"
                    })
            
            # Scan app directories - filter out problematic paths
            safe_scan_dirs = []
            for scan_dir in scan_dirs:
                # Skip root directory and other system directories
                if scan_dir in ["/", "/lib", "/system"]:
                    continue
                # Only scan if directory exists
                if self._dir_exists(scan_dir):
                    safe_scan_dirs.append(scan_dir)
            
            for scan_dir in safe_scan_dirs:
                log_safe("BOOT", f"Scanning directory: {scan_dir}")
                self._scan_directory(scan_dir)
            
            log_safe("BOOT", f"Found {len(self.boot_files)} boot files")
            
            # Save apps config
            self._save_apps_config()
            
        except Exception as e:
            log_safe("BOOT", f"Boot file scan failed: {e}", "ERROR")

    def _scan_directory(self, directory):
        """Scan directory for boot files"""
        try:
            # Ensure directory path is clean
            if not isinstance(directory, str):
                log_safe("BOOT", f"Invalid directory type: {type(directory)}", "WARN")
                return
            
            # Skip system directories that might cause issues
            skip_dirs = ["/", "/lib", "/system", "/boot"]
            if directory in skip_dirs:
                log_safe("BOOT", f"Skipping system directory: {directory}", "DEBUG")
                return
            
            items = os.listdir(directory)
            
            for item in items:
                # Skip hidden files and system files
                if item.startswith('.') or item.startswith('_'):
                    continue
                
                # Ensure proper string concatenation
                if directory.endswith('/'):
                    item_path = directory + str(item)
                else:
                    item_path = directory + "/" + str(item)
                
                try:
                    # Check for Python files
                    if str(item).endswith(('.py', '.mpy')):
                        self.boot_files.append({
                            "name": str(item),
                            "path": item_path,
                            "type": "app"
                        })
                    
                    # Check for app directories (but don't recurse too deep)
                    elif self._dir_exists(item_path):
                        if self._is_app_directory(item_path):
                            self.boot_files.append({
                                "name": str(item),
                                "path": item_path,
                                "type": "app_dir"
                            })
                except Exception as item_error:
                    log_safe("BOOT", f"Error processing item {item}: {item_error}", "DEBUG")
                    continue
            
        except Exception as e:
            log_safe("BOOT", f"Directory scan failed {directory}: {e}", "WARN")

    def _is_app_directory(self, path):
        """Check if directory contains a bootable app"""
        try:
            contents = os.listdir(path)
            return any(f in contents for f in ['main.py', 'code.py', 'app.py'])
        except:
            return False
    
    def _get_filename(self, path):
        """Extract filename from path"""
        return path.split('/')[-1] if '/' in path else path
    
    def _save_apps_config(self):
        """Save apps configuration"""
        try:
            apps_data = {
                "apps": {
                    "last_scan": int(time.monotonic()),
                    "total_found": len(self.boot_files)
                },
                "files": []
            }
            
            for boot_file in self.boot_files:
                apps_data["files"].append(boot_file)
            
            save_toml_config(self.APPS_CONFIG, apps_data)
            
        except Exception as e:
            log_safe("CONFIG", f"Apps config save failed: {e}", "WARN")
    
    def _determine_boot_path(self):
        """Determine which boot path to take"""
        try:
            log_safe("BOOT", "Determining boot path")
            
            # Recovery mode takes priority
            if self.recovery_mode:
                log_safe("BOOT", "Entering recovery mode")
                self._boot_recovery()
                return
            
            # Check for menu request
            if self._check_menu_request():
                log_safe("BOOT", "Entering boot menu")
                self._show_boot_menu()
                return
            
            # Custom boot mode
            if self.boot_mode == self.MODE_CUSTOM:
                log_safe("BOOT", "Attempting custom boot")
                if self._boot_custom():
                    return
                else:
                    log_safe("BOOT", "Custom boot failed, falling back", "WARN")
            
            # Normal boot
            log_safe("BOOT", "Starting normal boot")
            self._boot_normal()
            
        except Exception as e:
            log_safe("BOOT", f"Boot path determination failed: {e}", "ERROR")
            self._emergency_boot()
    
    def _check_menu_request(self):
        """Check if user is requesting boot menu"""
        if not self.button:
            return False
        
        # Check if button is held
        if not self.button.value:  # Button pressed
            start_time = time.monotonic()
            while time.monotonic() - start_time < 2.0:
                if self.button.value:  # Button released
                    return False
                time.sleep(0.1)
            return True  # Button held for 2 seconds
        
        return False
    
    def _show_boot_menu(self):
        """Show boot menu (graphical or console)"""
        if self.graphics_mode and self.display:
            self._show_graphical_menu()
        else:
            self._show_console_menu()
    
    def _show_graphical_menu(self):
        """Show graphical boot menu"""
        try:
            log_safe("UI", "Showing graphical boot menu")
            
            menu_items = [
                "Normal Boot",
                "Recovery Mode", 
                "Developer Mode",
                "Select App",
                "System Settings",
                "System Info"
            ]
            
            selected = 0
            last_button_time = 0
            
            while True:
                # Create menu display
                group = displayio.Group()
                
                # Background gradient effect
                bg = Rect(0, 0, 240, 135, fill=0x001122)
                group.append(bg)
                
                # Header
                header_bg = Rect(0, 0, 240, 25, fill=0x003366)
                group.append(header_bg)
                
                title = label.Label(
                    terminalio.FONT,
                    text="STAGETWO BOOTLOADER V1.0",
                    color=0xFFFFFF,
                    x=10,
                    y=15
                )
                group.append(title)
                
                # Menu items
                for i, item in enumerate(menu_items):
                    y_pos = 40 + (i * 15)
                    
                    if i == selected:
                        # Highlight selected item
                        highlight = Rect(5, y_pos - 8, 230, 14, fill=0x0066CC)
                        group.append(highlight)
                        color = 0xFFFFFF
                        prefix = "► "
                    else:
                        color = 0xCCCCCC
                        prefix = "  "
                    
                    item_label = label.Label(
                        terminalio.FONT,
                        text=prefix + item,
                        color=color,
                        x=10,
                        y=y_pos
                    )
                    group.append(item_label)
                
                # Footer with instructions
                footer_bg = Rect(0, 110, 240, 25, fill=0x003366)
                group.append(footer_bg)
                
                instructions = label.Label(
                    terminalio.FONT,
                    text="Click: Next | Hold 2s: Select | Auto-boot in 30s",
                    color=0xAAAAA,
                    x=5,
                    y=122
                )
                group.append(instructions)
                
                # System status indicators
                status_text = f"SD:{'OK' if self.sd_mounted else 'NO'} DEV:{'ON' if self.developer_mode else 'OFF'}"
                status = label.Label(
                    terminalio.FONT,
                    text=status_text,
                    color=0x888888,
                    x=180,
                    y=15
                )
                group.append(status)
                
                # Display the menu
                self.display.root_group = group
                
                # Handle input with timeout
                start_time = time.monotonic()
                timeout = 30  # 30 second auto-boot timeout
                
                while time.monotonic() - start_time < timeout:
                    current_time = time.monotonic()
                    
                    if self.button and not self.button.value:  # Button pressed
                        if current_time - last_button_time > 0.3:  # Debounce
                            button_start = current_time
                            
                            # Wait for release or hold
                            while not self.button.value and time.monotonic() - button_start < 3.0:
                                if time.monotonic() - button_start > 2.0:  # Hold detected
                                    self._execute_menu_option(selected)
                                    return
                                time.sleep(0.05)
                            
                            # Short press - navigate
                            if self.button.value:  # Button was released
                                selected = (selected + 1) % len(menu_items)
                                last_button_time = current_time
                                break  # Refresh display
                    
                    time.sleep(0.1)
                
                # If we get here, timeout occurred
                if time.monotonic() - start_time >= timeout:
                    log_safe("UI", "Menu timeout - auto-booting")
                    self._boot_normal()
                    return
            
        except Exception as e:
            log_safe("UI", f"Graphical menu error: {e}", "ERROR")
            self._show_console_menu()
    
    def _show_console_menu(self):
        """Show console-based boot menu"""
        try:
            log_safe("UI", "Showing console boot menu")
            
            print("\n" + "="*50)
            print("STAGETWO BOOTLOADER V1.0 - BOOT MENU")
            print("="*50)
            print("1. Normal Boot")
            print("2. Recovery Mode")
            print("3. Toggle Developer Mode")
            print("4. Select App")
            print("5. System Settings")
            print("6. System Info")
            print("\nAuto-boot in 10 seconds...")
            print("="*50)
            
            # Simple timeout
            start_time = time.monotonic()
            while time.monotonic() - start_time < 10:
                time.sleep(0.5)
            
            log_safe("UI", "Console menu timeout - auto-booting")
            self._boot_normal()
            
        except Exception as e:
            log_safe("UI", f"Console menu error: {e}", "ERROR")
            self._boot_normal()
    
    def _execute_menu_option(self, option):
        """Execute selected menu option"""
        try:
            if option == 0:  # Normal Boot
                self._boot_normal()
            elif option == 1:  # Recovery Mode
                self._boot_recovery()
            elif option == 2:  # Developer Mode
                self._toggle_developer_mode()
            elif option == 3:  # Select App
                self._select_app()
            elif option == 4:  # System Settings
                self._show_settings()
            elif option == 5:  # System Info
                self._show_system_info()
        except Exception as e:
            log_safe("UI", f"Menu option execution failed: {e}", "ERROR")
            self._emergency_boot()
    
    def _toggle_developer_mode(self):
        """Toggle developer mode"""
        try:
            self.developer_mode = not self.developer_mode
            
            # Update NVM
            microcontroller.nvm[self.NVM_DEVELOPER_MODE] = 1 if self.developer_mode else 0
            
            # Update config
            if "system" not in self.config:
                self.config["system"] = {}
            self.config["system"]["developer_mode"] = self.developer_mode
            
            # Save config
            self._save_configuration()
            
            # Update filesystem access
            if self.developer_mode and not self.flash_writable:
                self._remount_flash_rw()
            
            mode_text = "ENABLED" if self.developer_mode else "DISABLED"
            log_safe("DEV", f"Developer mode {mode_text}")
            
            # Show confirmation
            message = f"Developer Mode\n{mode_text}\n\nFilesystem: {'R/W' if self.developer_mode else 'R/O'}\nLogging: Enhanced\nDebugging: {'ON' if self.developer_mode else 'OFF'}"
            self._show_message(message, 4)
            
            # Return to menu
            self._show_boot_menu()
            
        except Exception as e:
            log_safe("DEV", f"Developer mode toggle failed: {e}", "ERROR")
            self._show_boot_menu()
    
    def _select_app(self):
        """Show app selection menu"""
        try:
            if not self.boot_files:
                self._show_message("No apps found\n\nPlease add apps to:\n/apps or /sd/apps", 3)
                self._show_boot_menu()
                return
            
            if self.graphics_mode and self.display:
                self._show_app_selection_gui()
            else:
                self._show_app_selection_console()
                
        except Exception as e:
            log_safe("APP", f"App selection failed: {e}", "ERROR")
            self._show_boot_menu()
    
    def _show_app_selection_gui(self):
        """Show graphical app selection"""
        try:
            selected = 0
            last_button_time = 0
            
            while True:
                group = displayio.Group()
                
                # Background
                bg = Rect(0, 0, 240, 135, fill=0x001122)
                group.append(bg)
                
                # Header
                header_bg = Rect(0, 0, 240, 20, fill=0x003366)
                group.append(header_bg)
                
                title = label.Label(
                    terminalio.FONT,
                    text=f"SELECT APP ({len(self.boot_files)} found)",
                    color=0xFFFFFF,
                    x=5,
                    y=12
                )
                group.append(title)
                
                # App list (show 6 items max)
                start_idx = max(0, selected - 2)
                end_idx = min(len(self.boot_files), start_idx + 6)
                
                for i in range(start_idx, end_idx):
                    y_pos = 30 + ((i - start_idx) * 15)
                    boot_file = self.boot_files[i]
                    
                    if i == selected:
                        highlight = Rect(2, y_pos - 8, 236, 14, fill=0x0066CC)
                        group.append(highlight)
                        color = 0xFFFFFF
                        prefix = "► "
                    else:
                        color = 0xCCCCCC
                        prefix = "  "
                    
                    # Truncate long names
                    name = boot_file["name"]
                    if len(name) > 25:
                        name = name[:22] + "..."
                    
                    app_label = label.Label(
                        terminalio.FONT,
                        text=prefix + name,
                        color=color,
                        x=5,
                        y=y_pos
                    )
                    group.append(app_label)
                    
                    # Show type indicator
                    type_color = 0x00FF00 if boot_file["type"] == "system" else 0x00AAFF
                    type_label = label.Label(
                        terminalio.FONT,
                        text=boot_file["type"][:3].upper(),
                        color=type_color,
                        x=200,
                        y=y_pos
                    )
                    group.append(type_label)
                
                # Footer
                footer_bg = Rect(0, 115, 240, 20, fill=0x003366)
                group.append(footer_bg)
                
                instructions = label.Label(
                    terminalio.FONT,
                    text="Click: Next | Hold: Boot | Long Hold: Back",
                    color=0xAAAAA,
                    x=5,
                    y=127
                )
                group.append(instructions)
                
                self.display.root_group = group
                
                # Handle input
                current_time = time.monotonic()
                if self.button and not self.button.value:
                    if current_time - last_button_time > 0.3:
                        button_start = current_time
                        
                        while not self.button.value and time.monotonic() - button_start < 5.0:
                            hold_time = time.monotonic() - button_start
                            
                            if hold_time > 4.0:  # Very long hold - back to menu
                                self._show_boot_menu()
                                return
                            elif hold_time > 2.0:  # Long hold - boot selected app
                                selected_app = self.boot_files[selected]
                                self._boot_file(selected_app["path"])
                                return
                            
                            time.sleep(0.05)
                        
                        # Short press - navigate
                        if self.button.value:
                            selected = (selected + 1) % len(self.boot_files)
                            last_button_time = current_time
                
                time.sleep(0.1)
                
        except Exception as e:
            log_safe("APP", f"GUI app selection failed: {e}", "ERROR")
            self._show_boot_menu()
    
    
    def _load_configuration(self):
        """Load bootloader configuration"""
        try:
            # Load boot configuration
            if self._file_exists(self.BOOT_CONFIG):
                self.config = load_toml_config(self.BOOT_CONFIG)
                log_safe("CONFIG", "Boot config loaded")
            else:
                self._create_default_config()
                self._save_configuration()
                log_safe("CONFIG", "Default config created")
            
            # Apply configuration
            self._apply_configuration()
            
        except Exception as e:
            log_safe("CONFIG", f"Config load failed: {e}", "ERROR")
            self._create_default_config()

    def _create_default_config(self):
        """Create default configuration"""
        self.config = {
            "boot": {
                "version": "1.0",
                "auto_boot_delay": 3,
                "default_app": "/lib/system/loader.py",
                "recovery_on_error": True,
                "boot_timeout": 30,
                "graphics_mode": True,
                "show_splash": True
            },
            "system": {
                "developer_mode": self.developer_mode,
                "logging_enabled": True,
                "logging_level": "INFO",
                "wifi_auto_connect": True
            },
            "display": {
                "brightness": 0.8,
                "theme": "dark",
                "show_animations": True,
                "menu_timeout": 30
            },
            "apps": {
                "custom_boot_index": 0,
                # Only scan safe app directories, not system directories
                "scan_directories": ["/apps", "/sd/apps"],
                "auto_scan": True
            }
        }


    def _apply_configuration(self):
        """Apply loaded configuration"""
        try:
            # Apply system settings
            system_config = self.config.get("system", {})
            self.developer_mode = system_config.get("developer_mode", self.developer_mode)
            
            # Apply display settings
            display_config = self.config.get("display", {})
            self.graphics_mode = display_config.get("graphics_mode", self.graphics_mode)
            
            # Update NVM with current settings
            microcontroller.nvm[self.NVM_DEVELOPER_MODE] = 1 if self.developer_mode else 0
            microcontroller.nvm[self.NVM_GRAPHICS_MODE] = 1 if self.graphics_mode else 0
            
            log_safe("CONFIG", "Configuration applied")
            
        except Exception as e:
            log_safe("CONFIG", f"Config apply failed: {e}", "ERROR")

    def _save_configuration(self):
        """Save current configuration"""
        try:
            if save_toml_config(self.BOOT_CONFIG, self.config):
                log_safe("CONFIG", "Configuration saved")
                return True
            else:
                log_safe("CONFIG", "Configuration save failed", "ERROR")
                return False
        except Exception as e:
            log_safe("CONFIG", f"Config save error: {e}", "ERROR")
            return False

    def _create_directory_recursive(self, path):
        """Create directory recursively (CircuitPython compatible)"""
        try:
            # Split path into parts
            parts = [p for p in path.split('/') if p]
            
            # Build path incrementally
            current_path = ""
            for part in parts:
                current_path += "/" + part
                
                if not self._dir_exists(current_path):
                    try:
                        os.mkdir(current_path)
                    except OSError as e:
                        # Directory might already exist or permission denied
                        if not self._dir_exists(current_path):
                            raise e
            
            return True
            
        except Exception as e:
            log_safe("CONFIG", f"Recursive directory creation failed for {path}: {e}", "ERROR")
            return False

    
    def _show_app_selection_console(self):
        """Show console app selection"""
        try:
            print("\n" + "="*50)
            print("AVAILABLE APPS")
            print("="*50)
            
            for i, boot_file in enumerate(self.boot_files):
                print(f"{i+1}. {boot_file['name']} ({boot_file['type']})")
                print(f"   Path: {boot_file['path']}")
            
            print("\nAuto-boot first app in 5 seconds...")
            time.sleep(5)
            
            if self.boot_files:
                self._boot_file(self.boot_files[0]["path"])
            else:
                self._show_boot_menu()
                
        except Exception as e:
            log_safe("APP", f"Console app selection failed: {e}", "ERROR")
            self._show_boot_menu()
    
    def _show_settings(self):
        """Show system settings"""
        try:
            settings_text = "SYSTEM SETTINGS\n\n"
            settings_text += f"Developer Mode: {'ON' if self.developer_mode else 'OFF'}\n"
            settings_text += f"Graphics Mode: {'ON' if self.graphics_mode else 'OFF'}\n"
            settings_text += f"Auto WiFi: {self.config.get('system', {}).get('wifi_auto_connect', True)}\n"
            settings_text += f"Log Level: {self.config.get('system', {}).get('logging_level', 'INFO')}\n"
            settings_text += f"Boot Timeout: {self.config.get('boot', {}).get('boot_timeout', 30)}s\n"
            settings_text += f"Config Dir: {self.CONFIG_DIR}\n"
            settings_text += "\nSettings stored in TOML files"
            
            self._show_message(settings_text, 8)
            self._show_boot_menu()
            
        except Exception as e:
            log_safe("SETTINGS", f"Settings display failed: {e}", "ERROR")
            self._show_boot_menu()
    
    def _show_system_info(self):
        """Show system information"""
        try:
            info_text = "STAGETWO BOOTLOADER V1.0\n\n"
            info_text += f"Board: {board.board_id}\n"
            info_text += f"Memory: {gc.mem_free()} bytes free\n"
            info_text += f"Flash: {'R/W' if self.flash_writable else 'R/O'}\n"
            info_text += f"SD Card: {'Mounted' if self.sd_mounted else 'Not Available'}\n"
            info_text += f"Display: {'Available' if self.display else 'Not Available'}\n"
            info_text += f"WiFi: {'Connected' if wifi.radio.connected else 'Disconnected'}\n"
            info_text += f"Apps Found: {len(self.boot_files)}\n"
            info_text += f"Logging: {'File+Console' if _logger.log_to_file else 'Console Only'}"
            
            self._show_message(info_text, 10)
            self._show_boot_menu()
            
        except Exception as e:
            log_safe("INFO", f"System info display failed: {e}", "ERROR")
            self._show_boot_menu()
    
    def _show_message(self, message, duration=3):
        """Show message on display or console"""
        if self.graphics_mode and self.display:
            try:
                group = displayio.Group()
                
                # Background
                bg = Rect(0, 0, 240, 135, fill=0x000000)
                group.append(bg)
                
                # Border
                border = Rect(3, 3, 234, 129, fill=0x0066CC)
                group.append(border)
                
                inner = Rect(5, 5, 230, 125, fill=0x000000)
                group.append(inner)
                
                # Message text
                lines = message.split('\n')
                for i, line in enumerate(lines[:9]):  # Max 9 lines
                    if line.strip():  # Skip empty lines
                        y_pos = 15 + (i * 12)
                        text_label = label.Label(
                            terminalio.FONT,
                            text=line[:35],  # Truncate long lines
                            color=0xFFFFFF,
                            x=10,
                            y=y_pos
                        )
                        group.append(text_label)
                
                self.display.root_group = group
                time.sleep(duration)
                
            except Exception as e:
                log_safe("UI", f"Display message error: {e}", "ERROR")
                # Fallback to console
                print("\n" + "="*50)
                print(message)
                print("="*50)
                time.sleep(duration)
        else:
            print("\n" + "="*50)
            print(message)
            print("="*50)
            time.sleep(duration)
    
    def _boot_normal(self):
        """Boot to default application"""
        try:
            log_safe("BOOT", "Starting normal boot sequence")
            
            # Clear recovery flags
            microcontroller.nvm[self.NVM_RECOVERY_FLAG] = 0
            microcontroller.nvm[self.NVM_BOOT_MODE] = self.MODE_NORMAL
            
            # Get default app from config
            boot_config = self.config.get("boot", {})
            default_app = boot_config.get("default_app", "/lib/system/loader.py")
            
            # Show boot splash if enabled
            if boot_config.get("show_splash", True):
                self._show_boot_splash()
            
            log_safe("BOOT", f"Booting to: {default_app}")
            
            if self._file_exists(default_app):
                self._boot_file(default_app)
            else:
                log_safe("BOOT", f"Default app not found: {default_app}", "ERROR")
                # Try fallback apps
                fallback_apps = ["/main.py", "/code.py", "/recovery.py"]
                for fallback in fallback_apps:
                    if self._file_exists(fallback):
                        log_safe("BOOT", f"Using fallback: {fallback}")
                        self._boot_file(fallback)
                        return
                
                self._emergency_boot()
            
        except Exception as e:
            log_safe("BOOT", f"Normal boot failed: {e}", "ERROR")
            self._emergency_boot()
    
    def _show_boot_splash(self):
        """Show boot splash screen"""
        if not self.graphics_mode or not self.display:
            return
        
        try:
            group = displayio.Group()
            
            # Gradient background
            bg = Rect(0, 0, 240, 135, fill=0x001133)
            group.append(bg)
            
            # Logo area
            logo_bg = Rect(20, 20, 200, 60, fill=0x003366)
            group.append(logo_bg)
            
            # Title
            title = label.Label(
                terminalio.FONT,
                text="STAGETWO",
                color=0x00AAFF,
                x=80,
                y=40
            )
            group.append(title)
            
            subtitle = label.Label(
                terminalio.FONT,
                text="BOOTLOADER V1.0",
                color=0xFFFFFF,
                x=70,
                y=60
            )
            group.append(subtitle)
            
            # Status
            status = label.Label(
                terminalio.FONT,
                text="Initializing...",
                color=0x888888,
                x=80,
                y=100
            )
            group.append(status)
            
            # Progress bar
            progress_bg = Rect(40, 110, 160, 8, fill=0x333333)
            group.append(progress_bg)
            
            progress = Rect(42, 112, 80, 4, fill=0x00FF00)
            group.append(progress)
            
            self.display.root_group = group
            time.sleep(2)
            
        except Exception as e:
            log_safe("UI", f"Boot splash error: {e}", "WARN")
    
    def _boot_recovery(self):
        """Boot to recovery mode"""
        try:
            log_safe("BOOT", "Starting recovery boot")
            
            # Set recovery flags
            microcontroller.nvm[self.NVM_RECOVERY_FLAG] = 1
            microcontroller.nvm[self.NVM_BOOT_MODE] = self.MODE_RECOVERY
            
            # Show recovery message
            if self.graphics_mode and self.display:
                self._show_message("RECOVERY MODE\n\nSearching for recovery system...", 2)
            
            # Try recovery locations in order of preference
            recovery_paths = [
                "/recovery.py",
                "/sd/recovery.py",
                "/system/recovery.py",
                "/lib/system/recovery.py",
                "/apps/recovery.py",
                "/sd/apps/recovery.py"
            ]
            
            for recovery_path in recovery_paths:
                if self._file_exists(recovery_path):
                    log_safe("BOOT", f"Loading recovery from: {recovery_path}")
                    self._boot_file(recovery_path)
                    return
            
            log_safe("BOOT", "No recovery system found", "ERROR")
            self._show_message("RECOVERY ERROR\n\nNo recovery system found!\nSystem will restart in 5 seconds", 5)
            self._emergency_boot()
            
        except Exception as e:
            log_safe("BOOT", f"Recovery boot failed: {e}", "ERROR")
            self._emergency_boot()
    
    def _boot_custom(self):
        """Boot to custom selected file"""
        try:
            apps_config = self.config.get("apps", {})
            custom_index = apps_config.get("custom_boot_index", 0)
            
            if custom_index < len(self.boot_files):
                custom_file = self.boot_files[custom_index]
                log_safe("BOOT", f"Custom boot: {custom_file['path']}")
                
                if self._file_exists(custom_file["path"]):
                    self._boot_file(custom_file["path"])
                    return True
                else:
                    log_safe("BOOT", f"Custom boot file not found: {custom_file['path']}", "ERROR")
            else:
                log_safe("BOOT", "Invalid custom boot index", "ERROR")
            
            return False
            
        except Exception as e:
            log_safe("BOOT", f"Custom boot failed: {e}", "ERROR")
            return False
    
    def _boot_file(self, file_path):
        """Boot to specific file"""
        try:
            log_safe("BOOT", f"Booting to: {file_path}")
            
            # Show boot message
            if self.graphics_mode and self.display:
                filename = self._get_filename(file_path)
                self._show_message(f"BOOTING\n\n{filename}\n\nPlease wait...", 2)
            
            # Flush logs before boot
            if _logger.log_to_file:
                try:
                    # Simple log flush - just ensure file is closed
                    pass
                except:
                    pass
            
            # Clean up memory
            gc.collect()
            
            # Log final boot message
            log_safe("BOOT", f"Transferring control to: {file_path}")
            
            # Set next code file and reload
            supervisor.set_next_code_file(file_path)
            supervisor.reload()
            
        except Exception as e:
            log_safe("BOOT", f"Boot file failed: {e}", "ERROR")
            raise
    
    def _emergency_boot(self):
        """Emergency boot fallback"""
        try:
            log_safe("BOOT", "EMERGENCY BOOT ACTIVATED", "CRITICAL")
            
            # Show emergency message
            if self.graphics_mode and self.display:
                self._show_message("EMERGENCY BOOT\n\nSystem Error Detected\nAttempting Recovery...\n\nPlease Wait", 3)
            
            # Emergency boot sequence - try in order of reliability
            emergency_files = [
                "/recovery.py",              # Primary recovery
                "/sd/recovery.py",           # SD recovery backup
                "/code.py",                  # Standard CircuitPython file
                "/main.py",                  # Alternative standard file
                "/lib/system/loader.py",     # System loader if available
                "/system/emergency.py"       # Emergency system
            ]
            
            for emergency_file in emergency_files:
                if self._file_exists(emergency_file):
                    log_safe("BOOT", f"Emergency boot to: {emergency_file}")
                    try:
                        supervisor.set_next_code_file(emergency_file)
                        supervisor.reload()
                        return
                    except Exception as e:
                        log_safe("BOOT", f"Emergency boot failed for {emergency_file}: {e}", "ERROR")
                        continue
            
            # No emergency files found - show error and reset
            log_safe("BOOT", "No emergency boot files found - system reset required", "CRITICAL")
            
            if self.graphics_mode and self.display:
                self._show_message("CRITICAL ERROR\n\nNo bootable files found!\n\nSystem will reset\nin 10 seconds", 10)
            else:
                print("CRITICAL ERROR: No bootable files found!")
                print("System will reset in 10 seconds...")
                time.sleep(10)
            
            microcontroller.reset()

        except Exception as final_error:
            log_safe("BOOT", f"EMERGENCY FALLBACK FAILED: {final_error}", "CRITICAL")
            # Last resort - immediate hardware reset
            time.sleep(2)
            microcontroller.reset()
    
    def _log_system_startup(self):
        """Log comprehensive system startup information"""
        try:
            log_safe("STARTUP", "=== STAGETWO BOOTLOADER V1.0 STARTUP ===")
            log_safe("STARTUP", f"Board: {board.board_id}")
            log_safe("STARTUP", f"Free memory: {gc.mem_free()} bytes")
            log_safe("STARTUP", f"Flash filesystem: {'R/W' if self.flash_writable else 'R/O'}")
            log_safe("STARTUP", f"SD card: {'Mounted' if self.sd_mounted else 'Not Available'}")
            log_safe("STARTUP", f"Display: {'Available' if self.display else 'Not Available'}")
            log_safe("STARTUP", f"Graphics mode: {'Enabled' if self.graphics_mode else 'Disabled'}")
            log_safe("STARTUP", f"Developer mode: {'Enabled' if self.developer_mode else 'Disabled'}")
            log_safe("STARTUP", f"Recovery mode: {'Active' if self.recovery_mode else 'Normal'}")
            log_safe("STARTUP", f"Boot mode: {self.boot_mode}")
            log_safe("STARTUP", f"Config directory: {self.CONFIG_DIR}")
            log_safe("STARTUP", f"Boot files found: {len(self.boot_files)}")
            log_safe("STARTUP", f"WiFi status: {'Connected' if wifi.radio.connected else 'Disconnected'}")
            log_safe("STARTUP", f"Logging: {'File+Console' if _logger.log_to_file else 'Console Only'}")
            log_safe("STARTUP", "=== STARTUP COMPLETE ===")
            
        except Exception as e:
            log_safe("STARTUP", f"Startup logging failed: {e}", "ERROR")


def main():
    """Main bootloader entry point"""
    try:
        # Initialize and run bootloader
        bootloader = StageTwoBootloader()
        log_safe("BOOT", "StageTwoBootloader initialization complete")
        
        # Auto-connect WiFi if enabled in config
        system_config = bootloader.config.get("system", {})
        if system_config.get("wifi_auto_connect", True):
            auto_connect_wifi()
        
    except Exception as e:
        log_safe("BOOT", f"BOOTLOADER INITIALIZATION FAILED: {e}", "CRITICAL")
        
        # Emergency fallback sequence
        try:
            # Show error animation if possible
            try:
                if board.DISPLAY:
                    group = displayio.Group()
                    bg = Rect(0, 0, 240, 135, fill=0xFF0000)
                    group.append(bg)
                    error_text = label.Label(
                        terminalio.FONT,
                        text="BOOTLOADER ERROR",
                        color=0xFFFFFF,
                        x=60,
                        y=60
                    )
                    group.append(error_text)
                    board.DISPLAY.root_group = group
                    time.sleep(3)
            except:
                pass
            
            # Try emergency boot sequence
            emergency_boot_order = [
                "/recovery.py",          # Primary recovery
                "/sd/recovery.py",       # SD recovery
                "/code.py",              # Standard code.py
                "/main.py",              # Standard main.py
                "/lib/system/loader.py"  # System loader
            ]
            
            for boot_file in emergency_boot_order:
                try:
                    if os.path.exists(boot_file):
                        log_safe("BOOT", f"Emergency fallback to: {boot_file}")
                        time.sleep(2)
                        supervisor.set_next_code_file(boot_file)
                        supervisor.reload()
                        return
                except:
                    continue
            
            # Final resort
            log_safe("BOOT", "All emergency options failed - resetting system", "CRITICAL")
            time.sleep(5)
            microcontroller.reset()
            
        except Exception as final_error:
            print(f"FINAL EMERGENCY BOOT FAILED: {final_error}")
            time.sleep(5)
            microcontroller.reset()


# Legacy compatibility functions (maintaining 100% compatibility)
def recovery_true():
    """Legacy recovery function for backward compatibility"""
    log_safe("BOOT", "Legacy recovery mode triggered")
    
    # Set recovery flag and reboot with StageTwoBootloader
    microcontroller.nvm[0] = 1  # Recovery flag
    microcontroller.nvm[1] = 2  # Recovery mode
    
    # Try to start recovery directly
    try:
        bootloader = StageTwoBootloader()
        bootloader._boot_recovery()
    except Exception as e:
        log_safe("BOOT", f"Legacy recovery failed: {e}", "ERROR")
        basic_recovery()

def basic_recovery():
    """Basic recovery fallback"""
    print("BASIC RECOVERY MODE")
    log_safe("RECOVERY", "Basic recovery mode activated")
    
    # Try to boot recovery.py
    recovery_files = ["/recovery.py", "/sd/recovery.py", "/system/recovery.py"]
    
    for recovery_file in recovery_files:
        try:
            if os.path.exists(recovery_file):
                log_safe("RECOVERY", f"Booting to: {recovery_file}")
                supervisor.set_next_code_file(recovery_file)
                supervisor.reload()
                return
        except:
            continue
    
    # If no recovery file found, reset
    log_safe("RECOVERY", "No recovery files found - system will restart in 5 seconds")
    time.sleep(5)
    microcontroller.reset()

def reset_flag():
    """Legacy flag reset function"""
    return reset_recovery_flag()

def reset_recovery_flag():
    """Reset recovery flag in NVM"""
    try:
        microcontroller.nvm[0] = 0  # Recovery flag
        log_safe("BOOT", "Recovery flag reset")
        return True
    except Exception as e:
        log_safe("BOOT", f"Failed to reset recovery flag: {e}", "ERROR")
        return False

def check_system_health():
    """Perform basic system health check"""
    try:
        health_issues = []
        
        # Check memory
        free_mem = gc.mem_free()
        if free_mem < 10000:  # Less than 10KB free
            health_issues.append(f"Low memory: {free_mem} bytes")
        
        # Check filesystems
        try:
            os.listdir("/")
        except:
            health_issues.append("Flash filesystem error")
        
        try:
            os.listdir("/sd")
        except:
            health_issues.append("SD card not accessible")
        
        # Check critical files
        critical_files = ["/boot.py"]
        for file_path in critical_files:
            try:
                os.stat(file_path)
            except:
                health_issues.append(f"Missing critical file: {file_path}")
        
        if health_issues:
            log_safe("HEALTH", f"System health issues detected: {', '.join(health_issues)}", "WARN")
            return False
        else:
            log_safe("HEALTH", "System health check passed")
            return True
            
    except Exception as e:
        log_safe("HEALTH", f"Health check failed: {e}", "ERROR")
        return False

def log_boot_performance():
    """Log boot performance metrics"""
    try:
        boot_time = time.monotonic()
        free_mem = gc.mem_free()
        
        log_safe("PERF", f"Boot completed in {boot_time:.2f}s")
        log_safe("PERF", f"Free memory: {free_mem} bytes")
        log_safe("PERF", f"Logger status: {'File+Console' if _logger.log_to_file else 'Console Only'}")
        
    except Exception as e:
        log_safe("PERF", f"Performance logging failed: {e}", "WARN")

def cleanup_boot_resources():
    """Clean up resources used during boot"""
    try:
        # Force garbage collection
        gc.collect()
        
        # Log cleanup
        log_safe("BOOT", "Boot resources cleaned up")
        log_safe("BOOT", f"Free memory after cleanup: {gc.mem_free()} bytes")
        
    except Exception as e:
        log_safe("BOOT", f"Cleanup failed: {e}", "WARN")

def get_nvm_status():
    """Get current NVM status for debugging"""
    try:
        status = {
            "recovery_flag": microcontroller.nvm[0],
            "boot_mode": microcontroller.nvm[1], 
            "developer_mode": microcontroller.nvm[2],
            "custom_boot_index": microcontroller.nvm[3],
            "settings_version": microcontroller.nvm[4],
            "graphics_mode": microcontroller.nvm[5],
            "log_level": microcontroller.nvm[6]
        }
        return status
    except Exception as e:
        log_safe("NVM", f"Failed to read NVM status: {e}", "ERROR")
        return {}

def factory_reset():
    """Perform factory reset - clear all NVM and config files"""
    try:
        log_safe("FACTORY", "Factory reset initiated")
        
        # Clear all NVM
        for i in range(32):  # Clear more NVM space
            microcontroller.nvm[i] = 0
        
        # Remove config files
        config_files = [
            "/sd/config/boot.toml",
            "/sd/config/apps.toml", 
            "/sd/config/wifi.toml",
            "/config/boot.toml",
            "/config/apps.toml",
            "/config/wifi.toml"
        ]
        
        for config_file in config_files:
            try:
                if os.path.exists(config_file):
                    os.remove(config_file)
                    log_safe("FACTORY", f"Removed: {config_file}")
            except Exception as e:
                log_safe("FACTORY", f"Failed to remove {config_file}: {e}", "WARN")
        
        log_safe("FACTORY", "Factory reset complete - system will restart")
        time.sleep(2)
        microcontroller.reset()
        
    except Exception as e:
        log_safe("FACTORY", f"Factory reset failed: {e}", "ERROR")
        return False

# Export functions for compatibility
__all__ = [
    'StageTwoBootloader',
    'main',
    'recovery_true',
    'basic_recovery', 
    'reset_flag',
    'reset_recovery_flag',
    'auto_connect_wifi',
    'log_safe',
    'check_system_health',
    'log_boot_performance',
    'cleanup_boot_resources',
    'get_nvm_status',
    'factory_reset',
    'load_toml_config',
    'save_toml_config',
    'parse_toml_simple'
]

# Version and metadata
__version__ = "1.0"
__author__ = "Devin Ranger"
__description__ = "StageTwoBootloader - Advanced graphical bootloader with TOML config support"
__compatibility__ = "Maintains 100% backward compatibility with Medusa Bootloader"

# Main execution
if __name__ == "__main__":
    try:
        # Log startup
        log_safe("BOOT", f"StageTwoBootloader V{__version__} starting")
        
        # Perform system health check
        health_ok = check_system_health()
        if not health_ok:
            log_safe("BOOT", "System health issues detected - consider recovery mode", "WARN")
        
        # Run main bootloader
        main()
        
        # Log performance metrics
        log_boot_performance()
        
        # Cleanup
        cleanup_boot_resources()
        
    except Exception as e:
        log_safe("BOOT", f"Boot execution failed: {e}", "CRITICAL")
        
        # Emergency fallback
        try:
            basic_recovery()
        except:
            microcontroller.reset()
else:
    # Module imported - initialize logger and auto-connect WiFi
    log_safe("BOOT", f"StageTwoBootloader V{__version__} module loaded")
    
    # Initialize logging when imported
    if not _logger.initialized:
        _logger.init()
    
    # Auto-connect WiFi when module is imported
    try:
        auto_connect_wifi()
    except:
        pass  # Don't fail if WiFi connection fails during import

# System status logging
try:
    log_safe("BOOT", "=== STAGETWO BOOTLOADER READY ===")
    log_safe("BOOT", f"Version: {__version__}")
    log_safe("BOOT", f"Logging: {'File+Console' if _logger.log_to_file else 'Console Only'}")
    log_safe("BOOT", f"Free Memory: {gc.mem_free()} bytes")
    log_safe("BOOT", f"SD Support: {'Available' if SD_AVAILABLE else 'Not Available'}")
    log_safe("BOOT", f"WiFi Status: {'Connected' if wifi.radio.connected else 'Disconnected'}")
    
    # Log NVM status in debug mode
    nvm_status = get_nvm_status()
    if nvm_status.get("developer_mode"):
        log_safe("DEBUG", f"NVM Status: {nvm_status}")
    
    log_safe("BOOT", "=== SYSTEM READY ===")
        
except Exception as e:
    print(f"Final status logging failed: {e}")

print("StageTwoBootloader V1.0 initialization complete")

# Configuration file templates for reference
BOOT_CONFIG_TEMPLATE = """
# StageTwoBootloader Boot Configuration
# This file uses TOML format

[boot]
version = "1.0"
auto_boot_delay = 3
default_app = "/lib/system/loader.py"
recovery_on_error = true
boot_timeout = 30
graphics_mode = true
show_splash = true

[system]
developer_mode = false
logging_enabled = true
logging_level = "INFO"
wifi_auto_connect = true

[display]
brightness = 0.8
theme = "dark"
show_animations = true
menu_timeout = 30

[apps]
custom_boot_index = 0
scan_directories = ["/apps", "/sd/apps", "/lib/apps"]
auto_scan = true
"""

WIFI_CONFIG_TEMPLATE = """
# WiFi Configuration
# This file uses TOML format

[wifi]
ssid = "YourNetworkName"
password = "YourPassword"
auto_connect = true
timeout = 15

# Multiple networks can be configured
[backup_wifi]
ssid = "BackupNetwork"
password = "BackupPassword"
"""

APPS_CONFIG_TEMPLATE = """
# Applications Configuration
# This file uses TOML format

[apps]
last_scan = 0
total_found = 0

# Custom app configurations can be added here
[custom_apps]
# Example:
# my_app = "/sd/apps/my_app.py"
"""

# Helper function to create default config files
def create_default_configs():
    """Create default configuration files"""
    try:
        config_templates = [
            ("/sd/config/boot.toml", BOOT_CONFIG_TEMPLATE),
            ("/sd/config/wifi.toml", WIFI_CONFIG_TEMPLATE), 
            ("/sd/config/apps.toml", APPS_CONFIG_TEMPLATE)
        ]
        
        for config_path, template in config_templates:
            if not os.path.exists(config_path):
                try:
                    # Ensure directory exists
                    config_dir = "/".join(config_path.split("/")[:-1])
                    if not os.path.exists(config_dir):
                        os.makedirs(config_dir)
                    
                    # Write template
                    with open(config_path, "w") as f:
                        f.write(template.strip())
                    
                    log_safe("CONFIG", f"Created default config: {config_path}")
                    
                except Exception as e:
                    log_safe("CONFIG", f"Failed to create {config_path}: {e}", "WARN")
        
        return True
        
    except Exception as e:
        log_safe("CONFIG", f"Default config creation failed: {e}", "ERROR")
        return False

# Add to exports
__all__.append('create_default_configs')
__all__.append('BOOT_CONFIG_TEMPLATE')
__all__.append('WIFI_CONFIG_TEMPLATE') 
__all__.append('APPS_CONFIG_TEMPLATE')

# Final initialization message
log_safe("INIT", "StageTwoBootloader module initialization complete")
log_safe("INIT", "Ready for boot sequence or module import")



