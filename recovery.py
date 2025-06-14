"""
StageTwo Recovery System
Advanced recovery and maintenance tools with modern GUI
Compatible with CircuitPython runtimes

(C) 2025 StageTwo Team
"""

import board
import displayio
import terminalio
from adafruit_display_text import label
import digitalio
import supervisor
import time
import microcontroller
import storage
import os
import gc
import json

# Try to import optional modules
try:
    import wifi
    import socketpool
    import adafruit_requests
    WIFI_AVAILABLE = True
except ImportError:
    WIFI_AVAILABLE = False

try:
    import zipper
    ZIPPER_AVAILABLE = True
except ImportError:
    ZIPPER_AVAILABLE = False

# Version info
__version__ = "2.0"
__author__ = "StageTwo Team"

# Display constants
SCREEN_WIDTH = board.DISPLAY.width
SCREEN_HEIGHT = board.DISPLAY.height
STATUS_BAR_HEIGHT = 20
MENU_START_Y = STATUS_BAR_HEIGHT + 10

# Import boot functions for flag management
try:
    from boot import set_nvm_flag, RECOVERY_FLAG_ADDR, show_status
except ImportError:
    def set_nvm_flag(addr, val):
        microcontroller.nvm[addr] = 1 if val else 0
    RECOVERY_FLAG_ADDR = 0
    def show_status():
        print("Status unavailable")

# Core system manifest - essential files for basic operation
CORE_MANIFEST = {
    "boot.py": {"required": True, "description": "Boot loader"},
    "code.py": {"required": True, "description": "Main application"},
    "bootmenu.py": {"required": False, "description": "Boot menu"},
    "recovery.py": {"required": True, "description": "Recovery system"},
    "settings.toml": {"required": False, "description": "Configuration"},
    "lib/": {"required": True, "description": "Libraries directory"},
}

class StatusBar:
    """Status bar for recovery system"""
    
    def __init__(self, display_group):
        self.group = displayio.Group()
        self.display_group = display_group
        
        # Create status bar background
        self.bg_bitmap = displayio.Bitmap(SCREEN_WIDTH, STATUS_BAR_HEIGHT, 1)
        self.bg_palette = displayio.Palette(1)
        self.bg_palette[0] = 0x220000  # Dark red background for recovery
        self.bg_sprite = displayio.TileGrid(self.bg_bitmap, pixel_shader=self.bg_palette, x=0, y=0)
        self.group.append(self.bg_sprite)
        
        # Recovery mode indicator
        self.mode_label = label.Label(
            terminalio.FONT, text="RECOVERY", color=0xFF0000, x=5, y=12
        )
        self.group.append(self.mode_label)
        
        # System status
        self.status_label = label.Label(
            terminalio.FONT, text="Ready", color=0xFFFFFF, x=80, y=12
        )
        self.group.append(self.status_label)
        
        # Memory display
        self.memory_label = label.Label(
            terminalio.FONT, text="", color=0xFF8000, x=SCREEN_WIDTH - 60, y=12
        )
        self.group.append(self.memory_label)
        
        self.display_group.append(self.group)
    
    def set_status(self, status_text, color=0xFFFFFF):
        """Set the status message"""
        self.status_label.text = status_text[:20]
        self.status_label.color = color
    
    def update_memory(self):
        """Update memory usage display"""
        try:
            gc.collect()
            free_mem = gc.mem_free()
            if free_mem < 1024:
                mem_text = f"{free_mem}B"
                color = 0xFF0000  # Red - low memory
            elif free_mem < 10240:
                mem_text = f"{free_mem//1024}K"
                color = 0xFF8000  # Orange - medium memory
            else:
                mem_text = f"{free_mem//1024}K"
                color = 0x00FF00  # Green - good memory
                
            self.memory_label.text = mem_text
            self.memory_label.color = color
            
            # Adjust position
            self.memory_label.x = SCREEN_WIDTH - len(mem_text) * 6 - 5
        except Exception:
            self.memory_label.text = ""
    
    def update_all(self):
        """Update all status bar elements"""
        self.update_memory()

class RecoverySystem:
    """Enhanced recovery system with modern GUI"""
    
    def __init__(self):
        gc.collect()
        
        self.display = board.DISPLAY
        self.main_group = displayio.Group()
        self.display.root_group = self.main_group
        
        # Initialize status bar
        self.status_bar = StatusBar(self.main_group)
        
        # Setup button if available
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except Exception:
            self.has_button = False
            print("No button available - console only mode")
        
        # Recovery state
        self.selected = 0
        self.current_mode = "main_menu"
        self.status_messages = []
        
        # Recovery menu items
        self.recovery_menu_items = [
            ("File System Check", "fs_check", "Check system files integrity"),
            ("Restore Core Files", "restore_core", "Restore essential system files"),
            ("Web Recovery", "web_recovery", "Download recovery tools via WiFi"),
            ("System Status", "show_status", "Display detailed system information"),
            ("Clear All Flags", "clear_flags", "Reset all system flags"),
            ("Backup System", "backup_system", "Create system backup"),
            ("Factory Reset", "factory_reset", "Reset to factory defaults"),
            ("Reboot Normal", "reboot_normal", "Exit recovery and reboot"),
        ]
        
        # Clear recovery flag on startup
        self.clear_recovery_flag()
        
        # Initial system check
        self.log_message("Recovery system initialized")
        gc.collect()
    
    def clear_recovery_flag(self):
        """Clear the recovery flag"""
        try:
            set_nvm_flag(RECOVERY_FLAG_ADDR, False)
            self.log_message("Recovery flag cleared")
        except Exception as e:
            self.log_message(f"Flag clear error: {e}")
    
    def log_message(self, message):
        """Log a message to console and status list"""
        print(f"RECOVERY: {message}")
        self.status_messages.append(message)
        if len(self.status_messages) > 20:
            self.status_messages.pop(0)
    
    def show_message(self, message, color=0xFFFFFF, duration=None):
        """Show a message on screen"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        self.status_bar.update_all()
        
        message_group = displayio.Group()
        lines = message.split("\n")
        
        for i, line in enumerate(lines):
            if line.strip():
                text_label = label.Label(
                    terminalio.FONT,
                    text=line[:35],
                    color=color,
                    x=10,
                    y=MENU_START_Y + 20 + i * 15
                )
                message_group.append(text_label)
        
        self.main_group.append(message_group)
        
        if duration:
            time.sleep(duration)
    
    def draw_main_menu(self):
        """Draw the main recovery menu"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        self.status_bar.update_all()
        
        menu_group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT,
            text="RECOVERY MODE",
            color=0xFF00FF,
            x=10,
            y=MENU_START_Y + 10,
            scale=2
        )
        menu_group.append(title)
        
        # Menu items
        if self.recovery_menu_items:
            # Calculate visible items
            list_start_y = MENU_START_Y + 35
            max_visible = (SCREEN_HEIGHT - list_start_y - 50) // 15
            start_idx = max(0, self.selected - max_visible // 2)
            end_idx = min(len(self.recovery_menu_items), start_idx + max_visible)
            
            if end_idx - start_idx < max_visible and len(self.recovery_menu_items) > max_visible:
                start_idx = max(0, end_idx - max_visible)
            
            for i in range(start_idx, end_idx):
                item_name, _, item_desc = self.recovery_menu_items[i]
                prefix = ">" if i == self.selected else " "
                
                if i == self.selected:
                    color = 0x00FF00  # Green for selected
                else:
                    color = 0xFFFFFF  # White for normal
                
                # Main item text
                item_label = label.Label(
                    terminalio.FONT,
                    text=f"{prefix} {item_name}",
                    color=color,
                    x=10,
                    y=list_start_y + (i - start_idx) * 15
                )
                menu_group.append(item_label)
        
        # Help text
        help_label = label.Label(
            terminalio.FONT,
            text="Short: Next  Long: Select  Hold: Details",
            color=0x888888,
            x=10,
            y=SCREEN_HEIGHT - 35
        )
        menu_group.append(help_label)
        
        # Position indicator
        pos_text = f"{self.selected+1}/{len(self.recovery_menu_items)}"
        pos_label = label.Label(
            terminalio.FONT,
            text=pos_text,
            color=0x888888,
            x=SCREEN_WIDTH - 60,
            y=SCREEN_HEIGHT - 35
        )
        menu_group.append(pos_label)
        
        # System status indicator
        status_color = 0x00FF00  # Assume OK
        try:
            fs_ok, _ = self.filesystem_check_silent()
            if not fs_ok:
                status_color = 0xFF8000  # Orange for issues
        except Exception:
            status_color = 0xFF0000  # Red for errors
        
        status_indicator = label.Label(
            terminalio.FONT,
            text="SYS",
            color=status_color,
            x=10,
            y=SCREEN_HEIGHT - 20
        )
        menu_group.append(status_indicator)
        
        self.main_group.append(menu_group)
    
    def show_item_details(self, index):
        """Show detailed information about a menu item"""
        if index >= len(self.recovery_menu_items):
            return
        
        item_name, action, description = self.recovery_menu_items[index]
        
        details = f"Recovery Tool Details\n\n"
        details += f"Name: {item_name}\n"
        details += f"Action: {action}\n\n"
        details += f"Description:\n{description}\n\n"
        
        # Add specific warnings or info
        if action == "factory_reset":
            details += "WARNING: This will erase\nall user data and settings!\n\n"
        elif action == "web_recovery":
            details += f"WiFi Required: {'Available' if WIFI_AVAILABLE else 'Not Available'}\n\n"
        elif action == "restore_core":
            details += f"Zipper Required: {'Available' if ZIPPER_AVAILABLE else 'Not Available'}\n\n"
        
        details += "Long press to execute\nShort press to return"
        
        self.show_message(details, color=0x00FFFF)
        
        # Wait for input
        action_result = self._wait_for_button_action()
        if action_result == "long":
            self.run_action(index)
        # Return to menu on any other input
    
    def filesystem_check_silent(self):
        """Silent filesystem check for status indicator"""
        try:
            storage.remount("/", readonly=False)
            missing_files = []
            
            for file_path, info in CORE_MANIFEST.items():
                if info.get("required", False):
                    try:
                        if file_path.endswith("/"):
                            os.listdir(file_path)
                        else:
                            os.stat(file_path)
                    except OSError:
                        missing_files.append(file_path)
            
            return len(missing_files) == 0, missing_files
        except Exception:
            return False, []
    
    def filesystem_check(self):
        """Comprehensive filesystem check with progress display"""
        self.status_bar.set_status("Checking filesystem...", 0xFFFF00)
        self.show_message("Checking filesystem...\nPlease wait", 0x00FFFF)
        
        self.log_message("Starting filesystem check")
        
        try:
            storage.remount("/", readonly=False)
            
            # Check/create system manifest
            manifest_path = "/system/manifest.json"
            manifest_exists = False
            
            try:
                try:
                    os.mkdir("/system")
                except OSError:
                    pass
                
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
                    manifest_exists = True
                    self.log_message("Manifest found")
            except OSError:
                self.log_message("Manifest not found, creating default")
                manifest = CORE_MANIFEST
            
            if not manifest_exists:
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f)
                self.log_message("Manifest created")
            
            # Check files
            missing_files = []
            corrupted_files = []
            
            for file_path, info in manifest.items():
                self.show_message(f"Checking filesystem...\nScanning: {file_path}", 0x00FFFF)
                
                if info.get("required", False):
                    try:
                        if file_path.endswith("/"):
                            os.listdir(file_path)
                        else:
                            stat_result = os.stat(file_path)
                            # Basic corruption check - zero-size critical files
                            if stat_result[6] == 0 and file_path.endswith('.py'):
                                corrupted_files.append(file_path)
                    except OSError:
                        missing_files.append(file_path)
            
            # Generate report
            report = "Filesystem Check Results\n\n"
            # Generate report
            report = "Filesystem Check Results\n\n"
            
            if not missing_files and not corrupted_files:
                report += "✅ All core files present\n"
                report += "✅ No corruption detected\n"
                self.status_bar.set_status("Filesystem OK", 0x00FF00)
                status_color = 0x00FF00
            else:
                if missing_files:
                    report += f"❌ Missing files ({len(missing_files)}):\n"
                    for file in missing_files[:5]:  # Show first 5
                        report += f"  • {file}\n"
                    if len(missing_files) > 5:
                        report += f"  ... and {len(missing_files)-5} more\n"
                    report += "\n"
                
                if corrupted_files:
                    report += f"⚠️ Corrupted files ({len(corrupted_files)}):\n"
                    for file in corrupted_files[:5]:
                        report += f"  • {file}\n"
                    if len(corrupted_files) > 5:
                        report += f"  ... and {len(corrupted_files)-5} more\n"
                    report += "\n"
                
                self.status_bar.set_status("Issues found", 0xFF8000)
                status_color = 0xFF8000
            
            # Storage info
            try:
                statvfs = os.statvfs("/")
                total_space = statvfs[0] * statvfs[2]
                free_space = statvfs[0] * statvfs[3]
                used_space = total_space - free_space
                
                report += f"Storage Info:\n"
                report += f"Total: {total_space//1024}KB\n"
                report += f"Used: {used_space//1024}KB\n"
                report += f"Free: {free_space//1024}KB\n\n"
            except Exception:
                report += "Storage info unavailable\n\n"
            
            report += "Press button to continue"
            
            self.log_message(f"Check complete: {len(missing_files)} missing, {len(corrupted_files)} corrupted")
            self.show_message(report, status_color)
            self._wait_for_button_action()
            
        except Exception as e:
            error_msg = f"Filesystem check failed:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Filesystem check error: {e}")
            self.status_bar.set_status("Check failed", 0xFF0000)
            self._wait_for_button_action()
    
    def restore_core_files(self):
        """Restore core system files"""
        self.status_bar.set_status("Restoring files...", 0xFFFF00)
        
        if not ZIPPER_AVAILABLE:
            self.show_message("Restore failed:\nZipper library not available\n\nPress button to continue", 0xFF0000)
            self._wait_for_button_action()
            return
        
        self.show_message("Core File Restoration\n\nSearching for backup...", 0x00FFFF)
        
        # Look for backup files
        backup_locations = ["/backups/", "/sd/backups/", "/recovery/"]
        backup_found = False
        backup_path = None
        
        for location in backup_locations:
            try:
                files = os.listdir(location)
                for file in files:
                    if file.endswith('.zip') and 'core' in file.lower():
                        backup_path = location + file
                        backup_found = True
                        break
                if backup_found:
                    break
            except OSError:
                continue
        
        if not backup_found:
            self.show_message("No core backup found!\n\nChecked locations:\n/backups/\n/sd/backups/\n/recovery/\n\nPress button to continue", 0xFF0000)
            self._wait_for_button_action()
            return
        
        # Confirm restoration
        confirm_msg = f"Restore from backup?\n\nFile: {backup_path}\n\nLong: Confirm\nShort: Cancel"
        self.show_message(confirm_msg, 0xFFFF00)
        
        action = self._wait_for_button_action()
        if action != "long":
            self.show_message("Restoration cancelled", 0xFF8000, 1)
            return
        
        try:
            self.log_message(f"Restoring from {backup_path}")
            
            # Extract backup
            with zipper.ZipFile(backup_path, 'r') as zip_file:
                file_list = zip_file.namelist()
                
                for i, file_name in enumerate(file_list):
                    self.show_message(f"Restoring files...\n{i+1}/{len(file_list)}\n{file_name[:20]}", 0x00FFFF)
                    
                    # Extract file
                    zip_file.extract(file_name, "/")
                    
                    # Brief pause for display update
                    time.sleep(0.1)
            
            self.log_message("Core files restored successfully")
            self.status_bar.set_status("Restore complete", 0x00FF00)
            self.show_message("Core files restored!\n\nSystem should now be\nfunctional.\n\nPress button to continue", 0x00FF00)
            self._wait_for_button_action()
            
        except Exception as e:
            error_msg = f"Restoration failed:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Restore error: {e}")
            self.status_bar.set_status("Restore failed", 0xFF0000)
            self._wait_for_button_action()
    
    def web_recovery(self):
        """Web-based recovery system"""
        self.status_bar.set_status("Web recovery...", 0xFFFF00)
        
        if not WIFI_AVAILABLE:
            self.show_message("Web recovery failed:\nWiFi not available\n\nPress button to continue", 0xFF0000)
            self._wait_for_button_action()
            return
        
        self.show_message("Web Recovery System\n\nInitializing WiFi...", 0x00FFFF)
        
        try:
            # Initialize WiFi
            if not wifi.radio.enabled:
                wifi.radio.enabled = True
                time.sleep(2)
            
            # Try to connect using saved settings
            self.show_message("Web Recovery System\n\nConnecting to WiFi...", 0x00FFFF)
            
            settings = self.load_settings()
            ssid = settings.get("CIRCUITPY_WIFI_SSID", "")
            password = settings.get("CIRCUITPY_WIFI_PASSWORD", "")
            
            if not ssid:
                self.show_message("No WiFi credentials!\n\nConfigure WiFi first\nin settings.toml\n\nPress button to continue", 0xFF0000)
                self._wait_for_button_action()
                return
            
            # Connect
            wifi.radio.connect(ssid, password, timeout=15)
            
            if not wifi.radio.connected:
                self.show_message("WiFi connection failed!\n\nCheck credentials\nin settings.toml\n\nPress button to continue", 0xFF0000)
                self._wait_for_button_action()
                return
            
            self.show_message(f"Connected to WiFi!\nIP: {wifi.radio.ipv4_address}\n\nStarting recovery...", 0x00FF00)
            time.sleep(2)
            
            # Recovery URLs (example - customize for your needs)
            recovery_urls = [
                "https://github.com/D31337m3/StageTwo/releases/latest/download/core_files.zip",
                "https://raw.githubusercontent.com/D31337m3/StageTwo/main/recovery/boot.py",
                "https://raw.githubusercontent.com/D31337m3/StageTwo/main/recovery/code.py"
            ]
            
            pool = socketpool.SocketPool(wifi.radio)
            requests = adafruit_requests.Session(pool)
            
            success_count = 0
            
            for i, url in enumerate(recovery_urls):
                try:
                    self.show_message(f"Downloading...\n{i+1}/{len(recovery_urls)}\n{url.split('/')[-1][:20]}", 0x00FFFF)
                    
                    response = requests.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        filename = url.split('/')[-1]
                        
                        # Save file
                        if filename.endswith('.zip'):
                            save_path = f"/recovery/{filename}"
                        else:
                            save_path = f"/{filename}"
                        
                        # Ensure directory exists
                        try:
                            os.mkdir("/recovery")
                        except OSError:
                            pass
                        
                        with open(save_path, 'wb') as f:
                            f.write(response.content)
                        
                        success_count += 1
                        self.log_message(f"Downloaded: {filename}")
                    
                    response.close()
                    
                except Exception as e:
                    self.log_message(f"Download failed for {url}: {e}")
                    continue
            
            if success_count > 0:
                self.show_message(f"Web recovery complete!\n\n{success_count}/{len(recovery_urls)} files\ndownloaded successfully.\n\nPress button to continue", 0x00FF00)
                self.status_bar.set_status("Web recovery OK", 0x00FF00)
            else:
                self.show_message("Web recovery failed!\n\nNo files downloaded.\nCheck internet connection.\n\nPress button to continue", 0xFF0000)
                self.status_bar.set_status("Web recovery failed", 0xFF0000)
            
            self._wait_for_button_action()
            
        except Exception as e:
            error_msg = f"Web recovery error:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Web recovery error: {e}")
            self.status_bar.set_status("Web recovery failed", 0xFF0000)
            self._wait_for_button_action()
    
    def show_system_status(self):
        """Show detailed system status"""
        self.status_bar.set_status("Getting status...", 0xFFFF00)
        self.show_message("Gathering system info...\nPlease wait", 0x00FFFF)
        
        try:
            gc.collect()
            
            # System info
            status_info = "System Status Report\n\n"
            
            # Memory info
            free_mem = gc.mem_free()
            status_info += f"Memory: {free_mem} bytes free\n"
            
            # Storage info
            try:
                statvfs = os.statvfs("/")
                total_space = statvfs[0] * statvfs[2]
                free_space = statvfs[0] * statvfs[3]
                status_info += f"Storage: {free_space//1024}KB free\n"
                status_info += f"  of {total_space//1024}KB total\n"
            except Exception:
                status_info += "Storage: Info unavailable\n"
            
            # Hardware info
            try:
                status_info += f"CPU Freq: {microcontroller.cpu.frequency//1000000}MHz\n"
                status_info += f"CPU Temp: {microcontroller.cpu.temperature:.1f}°C\n"
            except Exception:
                status_info += "CPU: Info unavailable\n"
            
            # WiFi status
            if WIFI_AVAILABLE:
                try:
                    if wifi.radio.connected:
                        status_info += f"WiFi: Connected\n"
                        status_info += f"  SSID: {wifi.radio.ap_info.ssid}\n"
                        status_info += f"  IP: {wifi.radio.ipv4_address}\n"
                    else:
                        status_info += "WiFi: Disconnected\n"
                except Exception:
                    status_info += "WiFi: Status unknown\n"
            else:
                status_info += "WiFi: Not available\n"
            
            # NVM flags status
            try:
                nvm_data = microcontroller.nvm
                status_info += f"\nNVM Flags:\n"
                status_info += f"  Recovery: {bool(nvm_data[0])}\n"
                status_info += f"  Developer: {bool(nvm_data[1])}\n"
                status_info += f"  Flash Write: {bool(nvm_data[2])}\n"
            except Exception:
                status_info += "\nNVM: Access failed\n"
            
            # Recent log messages
            if self.status_messages:
                status_info += f"\nRecent Messages:\n"
                for msg in self.status_messages[-3:]:
                    status_info += f"  • {msg[:25]}\n"
            
            status_info += "\nPress button to continue"
            
            self.show_message(status_info, 0x00FFFF)
            self.status_bar.set_status("Status ready", 0x00FF00)
            self._wait_for_button_action()
            
        except Exception as e:
            error_msg = f"Status error:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Status error: {e}")
            self._wait_for_button_action()
    
    def clear_all_flags(self):
        """Clear all NVM flags"""
        self.status_bar.set_status("Clearing flags...", 0xFFFF00)
        
        confirm_msg = "Clear all system flags?\n\nThis will reset:\n• Recovery flag\n• Developer mode\n• Flash write flag\n\nLong: Confirm\nShort: Cancel"
        self.show_message(confirm_msg, 0xFFFF00)
        
        action = self._wait_for_button_action()
        if action != "long":
            self.show_message("Operation cancelled", 0xFF8000, 1)
            return
        
        try:
            # Clear all flags
            for i in range(10):  # Clear first 10 bytes
                set_nvm_flag(i, False)
            
            self.log_message("All flags cleared")
            self.status_bar.set_status("Flags cleared", 0x00FF00)
            self.show_message("All system flags cleared!\n\nSystem will boot normally\non next restart.\n\nPress button to continue", 0x00FF00)
            self._wait_for_button_action()
            
        except Exception as e:
            error_msg = f"Flag clear failed:\n{str(e)[:50]}\n\nPress button to continue"
            error_msg = f"Flag clear failed:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Flag clear error: {e}")
            self.status_bar.set_status("Clear failed", 0xFF0000)
            self._wait_for_button_action()
    
    def backup_system(self):
        """Create system backup"""
        self.status_bar.set_status("Creating backup...", 0xFFFF00)
        
        if not ZIPPER_AVAILABLE:
            self.show_message("Backup failed:\nZipper library not available\n\nPress button to continue", 0xFF0000)
            self._wait_for_button_action()
            return
        
        self.show_message("System Backup\n\nPreparing backup...", 0x00FFFF)
        
        try:
            # Ensure backup directory exists
            try:
                os.mkdir("/backups")
            except OSError:
                pass
            
            # Generate backup filename with timestamp
            try:
                current_time = time.localtime()
                timestamp = f"{current_time.tm_year:04d}{current_time.tm_mon:02d}{current_time.tm_mday:02d}_{current_time.tm_hour:02d}{current_time.tm_min:02d}"
            except Exception:
                timestamp = f"{int(time.monotonic())}"
            
            backup_filename = f"/backups/system_backup_{timestamp}.zip"
            
            # Files to backup
            backup_files = []
            
            # Core system files
            core_files = ["boot.py", "code.py", "settings.toml", "recovery.py"]
            for file in core_files:
                try:
                    os.stat(file)
                    backup_files.append(file)
                except OSError:
                    pass
            
            # System directory
            try:
                system_files = os.listdir("/system")
                for file in system_files:
                    if not file.startswith('.'):
                        backup_files.append(f"/system/{file}")
            except OSError:
                pass
            
            # Apps directory
            try:
                app_files = os.listdir("/apps")
                for file in app_files:
                    if not file.startswith('.'):
                        backup_files.append(f"/apps/{file}")
            except OSError:
                pass
            
            if not backup_files:
                self.show_message("No files to backup!\n\nPress button to continue", 0xFF8000)
                self._wait_for_button_action()
                return
            
            # Confirm backup
            confirm_msg = f"Create system backup?\n\nFiles: {len(backup_files)}\nLocation: {backup_filename}\n\nLong: Confirm\nShort: Cancel"
            self.show_message(confirm_msg, 0xFFFF00)
            
            action = self._wait_for_button_action()
            if action != "long":
                self.show_message("Backup cancelled", 0xFF8000, 1)
                return
            
            # Create backup
            with zipper.ZipFile(backup_filename, 'w') as zip_file:
                for i, file_path in enumerate(backup_files):
                    try:
                        self.show_message(f"Backing up files...\n{i+1}/{len(backup_files)}\n{file_path[:20]}", 0x00FFFF)
                        
                        zip_file.write(file_path)
                        time.sleep(0.05)  # Brief pause for display
                        
                    except Exception as e:
                        self.log_message(f"Backup skip {file_path}: {e}")
                        continue
            
            # Verify backup
            try:
                backup_stat = os.stat(backup_filename)
                backup_size = backup_stat[6]
                
                if backup_size > 0:
                    self.log_message(f"Backup created: {backup_filename} ({backup_size} bytes)")
                    self.status_bar.set_status("Backup complete", 0x00FF00)
                    self.show_message(f"Backup created!\n\nFile: {backup_filename.split('/')[-1]}\nSize: {backup_size} bytes\n\nPress button to continue", 0x00FF00)
                else:
                    raise Exception("Backup file is empty")
                    
            except Exception as e:
                raise Exception(f"Backup verification failed: {e}")
            
            self._wait_for_button_action()
            
        except Exception as e:
            error_msg = f"Backup failed:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Backup error: {e}")
            self.status_bar.set_status("Backup failed", 0xFF0000)
            self._wait_for_button_action()
    
    def factory_reset(self):
        """Perform factory reset"""
        self.status_bar.set_status("Factory reset...", 0xFF8000)
        
        # Multiple confirmation steps
        confirm_msg1 = "FACTORY RESET WARNING!\n\nThis will DELETE ALL:\n• User files\n• Settings\n• Apps\n• Data\n\nLong: Continue\nShort: Cancel"
        self.show_message(confirm_msg1, 0xFF0000)
        
        action = self._wait_for_button_action()
        if action != "long":
            self.show_message("Factory reset cancelled", 0xFF8000, 1)
            return
        
        confirm_msg2 = "FINAL WARNING!\n\nThis action CANNOT be undone!\n\nAll data will be lost!\n\nLong: RESET NOW\nShort: Cancel"
        self.show_message(confirm_msg2, 0xFF0000)
        
        action = self._wait_for_button_action()
        if action != "long":
            self.show_message("Factory reset cancelled", 0xFF8000, 1)
            return
        
        try:
            self.show_message("FACTORY RESET IN PROGRESS\n\nDO NOT POWER OFF!\n\nDeleting files...", 0xFF0000)
            
            # List of directories to clear
            dirs_to_clear = ["/apps", "/system", "/backups", "/logs"]
            
            # Files to delete (keep core system files)
            files_to_delete = ["settings.toml"]
            
            deleted_count = 0
            
            # Delete directories
            for dir_path in dirs_to_clear:
                try:
                    files = os.listdir(dir_path)
                    for file in files:
                        file_path = f"{dir_path}/{file}"
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            if deleted_count % 5 == 0:
                                self.show_message(f"FACTORY RESET IN PROGRESS\n\nDO NOT POWER OFF!\n\nDeleted {deleted_count} files...", 0xFF0000)
                        except Exception:
                            pass
                    
                    # Try to remove directory
                    try:
                        os.rmdir(dir_path)
                    except Exception:
                        pass
                        
                except OSError:
                    pass  # Directory doesn't exist
            
            # Delete individual files
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except OSError:
                    pass
            
            # Clear all NVM flags
            try:
                for i in range(10):
                    set_nvm_flag(i, False)
            except Exception:
                pass
            
            # Create fresh settings.toml with defaults
            try:
                default_settings = """# StageTwo Default Settings
# WiFi Configuration (configure as needed)
CIRCUITPY_WIFI_SSID = ""
CIRCUITPY_WIFI_PASSWORD = ""

# Screensaver Settings
SCREENSAVER_ENABLED = true
SCREENSAVER_TIMEOUT = 300
SCREENSAVER_TYPE = "trippy"

# System Settings
DEVELOPER_MODE = false
"""
                with open("/settings.toml", "w") as f:
                    f.write(default_settings)
            except Exception:
                pass
            
            self.log_message(f"Factory reset complete: {deleted_count} files deleted")
            self.status_bar.set_status("Reset complete", 0x00FF00)
            
            self.show_message(f"FACTORY RESET COMPLETE!\n\n{deleted_count} files deleted\nSystem restored to defaults\n\nPress button to reboot", 0x00FF00)
            self._wait_for_button_action()
            
            # Reboot
            self.show_message("Rebooting system...", 0x00FFFF, 2)
            microcontroller.reset()
            
        except Exception as e:
            error_msg = f"Factory reset failed:\n{str(e)[:50]}\n\nSystem may be unstable!\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Factory reset error: {e}")
            self.status_bar.set_status("Reset failed", 0xFF0000)
            self._wait_for_button_action()
    
    def reboot_normal(self):
        """Exit recovery and reboot normally"""
        self.status_bar.set_status("Rebooting...", 0x00FFFF)
        
        confirm_msg = "Exit recovery mode?\n\nSystem will reboot normally\n\nLong: Reboot\nShort: Cancel"
        self.show_message(confirm_msg, 0x00FFFF)
        
        action = self._wait_for_button_action()
        if action != "long":
            self.show_message("Reboot cancelled", 0xFF8000, 1)
            return
        
        try:
            # Clear recovery flag
            self.clear_recovery_flag()
            
            self.log_message("Exiting recovery mode")
            self.show_message("Exiting recovery mode...\n\nRebooting to normal mode\n\nPlease wait...", 0x00FFFF)
            
            time.sleep(2)
            microcontroller.reset()
            
        except Exception as e:
            error_msg = f"Reboot failed:\n{str(e)[:50]}\n\nPress button to continue"
            self.show_message(error_msg, 0xFF0000)
            self.log_message(f"Reboot error: {e}")
            self._wait_for_button_action()
    
    def load_settings(self):
        """Load settings from settings.toml"""
        settings = {}
        try:
            with open("/settings.toml", "r") as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        settings[key] = value
        except Exception as e:
            self.log_message(f"Settings load error: {e}")
        return settings
    
    def run_action(self, index):
        """Execute the selected recovery action"""
        if index >= len(self.recovery_menu_items):
            return
        
        _, action, _ = self.recovery_menu_items[index]
        
        self.log_message(f"Executing action: {action}")
        
        # Map actions to methods
        action_map = {
            "fs_check": self.filesystem_check,
            "restore_core": self.restore_core_files,
            "web_recovery": self.web_recovery,
            "show_status": self.show_system_status,
            "clear_flags": self.clear_all_flags,
            "backup_system": self.backup_system,
            "factory_reset": self.factory_reset,
            "reboot_normal": self.reboot_normal,
        }
        
        if action in action_map:
            try:
                action_map[action]()
            except Exception as e:
                error_msg = f"Action failed:\n{action}\n{str(e)[:30]}\n\nPress button to continue"
                self.show_message(error_msg, 0xFF0000)
                self.log_message(f"Action {action} failed: {e}")
                self._wait_for_button_action()
        else:
            self.show_message(f"Unknown action:\n{action}\n\nPress button to continue", 0xFF8000)
            self._wait_for_button_action()
    
    def _handle_button_input(self):
        """Handle button input and return press duration"""
        if not self.has_button:
            time.sleep(0.1)
            return 0
        
        # Wait for button press
        while self.button.value:
            time.sleep(0.01)
        
        # Measure press duration
        press_start = time.monotonic()
        while not self.button.value:
            time.sleep(0.01)
        
        return time.monotonic() - press_start
    
    def _wait_for_button_action(self):
        """Wait for button press and return action type"""
        if not self.has_button:
            time.sleep(2)
            return "timeout"
        
        press_duration = self._handle_button_input()
        
        if press_duration > 2.0:
            return "hold"
        elif press_duration > 1.0:
            return "long"
        elif press_duration > 0.05:
            return "short"
        else:
            return "none"
    
    def main_loop(self):
        """Main recovery system loop"""
        self.status_bar.set_status("Recovery ready")
        self.log_message("Recovery system started")
        
        while True:
            try:
                if self.current_mode == "main_menu":
                    self.draw_main_menu()
                    
                    press_duration = self._handle_button_input()
                    
                    if press_duration > 2.0:  # Hold - show details
                        self.show_item_details(self.selected)
                        
                    elif press_duration > 1.0:  # Long press - execute action
                        self.run_action(self.selected)
                        
                    elif press_duration > 0.05:  # Short press - navigate
                        self.selected = (self.selected + 1) % len(self.recovery_menu_items)
                
                else:
                    # Handle other modes if needed
                    time.sleep(0.1)
                
            except KeyboardInterrupt:
                self.log_message("Recovery interrupted by user")
                break
                
            except Exception as e:
                self.log_message(f"Recovery loop error: {e}")
                self.show_message(f"System Error:\n{str(e)[:50]}\n\nPress button to continue", 0xFF0000)
                self._wait_for_button_action()
                self.current_mode = "main_menu"
                self.selected = 0

def main():
    """Main entry point for recovery system"""
    try:
        print("=" * 50)
        print("🔧 StageTwo Recovery System")
        print(f"📋 Version: {__version__}")
        print("=" * 50)
        print("🔧 StageTwo Recovery System")
        print(f"📋 Version: {__version__}")
        print("=" * 50)
        
        # Initial memory cleanup
        gc.collect()
        print(f"💾 Starting with {gc.mem_free()} bytes free memory")
        
        # Check display
        if not (hasattr(board, 'DISPLAY') and board.DISPLAY):
            print("❌ No display available - cannot run recovery GUI")
            return False
        
        # Check button
        if not hasattr(board, 'BUTTON'):
            print("⚠️ No button available - recovery will have limited functionality")
        
        # Initialize and start recovery system
        recovery = RecoverySystem()
        
        print("🚀 Starting recovery system...")
        print("📱 Use button to navigate:")
        print("   • Short press: Navigate menu")
        print("   • Long press: Select action")
        print("   • Hold: Show details")
        print("   • Ctrl+C: Exit to console")
        print("=" * 50)
        
        # Run main loop
        recovery.main_loop()
        
        print("🛑 Recovery system stopped")
        return True
        
    except Exception as e:
        print(f"❌ Recovery system failed: {e}")
        import traceback
        traceback.print_exception()
        return False
    
    finally:
        # Final cleanup
        gc.collect()
        print(f"💾 Final memory: {gc.mem_free()} bytes free")

def emergency_recovery():
    """Emergency recovery function for critical failures"""
    print("🚨 EMERGENCY RECOVERY MODE")
    print("=" * 30)
    
    try:
        # Basic system check without GUI
        print("Checking critical files...")
        
        critical_files = ["boot.py", "code.py"]
        missing_files = []
        
        for file in critical_files:
            try:
                os.stat(file)
                print(f"✅ {file} - OK")
            except OSError:
                print(f"❌ {file} - MISSING")
                missing_files.append(file)
        
        if missing_files:
            print(f"\n🔥 CRITICAL: {len(missing_files)} essential files missing!")
            print("System may not boot properly.")
            
            # Try to create minimal boot.py
            if "boot.py" in missing_files:
                try:
                    with open("boot.py", "w") as f:
                        f.write("""# Emergency boot.py
import storage
storage.remount("/", readonly=False)
print("Emergency boot mode active")
""")
                    print("✅ Created emergency boot.py")
                except Exception as e:
                    print(f"❌ Failed to create boot.py: {e}")
            
            # Try to create minimal code.py
            if "code.py" in missing_files:
                try:
                    with open("code.py", "w") as f:
                        f.write("""# Emergency code.py
print("Emergency mode - system needs recovery")
print("Run recovery.py to restore system")

try:
    import recovery
    recovery.main()
except Exception as e:
    print(f"Recovery failed: {e}")
    print("Manual intervention required")
""")
                    print("✅ Created emergency code.py")
                except Exception as e:
                    print(f"❌ Failed to create code.py: {e}")
        
        # Clear any problematic flags
        try:
            import microcontroller
            for i in range(5):
                microcontroller.nvm[i] = 0
            print("✅ Cleared system flags")
        except Exception as e:
            print(f"⚠️ Flag clear failed: {e}")
        
        print("\n🔧 Emergency recovery complete")
        print("System should now boot to recovery mode")
        
        return True
        
    except Exception as e:
        print(f"❌ Emergency recovery failed: {e}")
        return False

def quick_fix():
    """Quick fix for common issues"""
    print("🔧 Quick Fix Utility")
    print("=" * 20)
    
    fixes_applied = 0
    
    # Fix 1: Ensure storage is writable
    try:
        import storage
        storage.remount("/", readonly=False)
        print("✅ Storage made writable")
        fixes_applied += 1
    except Exception as e:
        print(f"❌ Storage fix failed: {e}")
    
    # Fix 2: Clear problematic flags
    try:
        import microcontroller
        microcontroller.nvm[0] = 0  # Clear recovery flag
        print("✅ Recovery flag cleared")
        fixes_applied += 1
    except Exception as e:
        print(f"❌ Flag fix failed: {e}")
    
    # Fix 3: Create system directory
    try:
        os.mkdir("/system")
        print("✅ System directory created")
        fixes_applied += 1
    except OSError:
        print("ℹ️ System directory already exists")
    except Exception as e:
        print(f"❌ Directory fix failed: {e}")
    
    # Fix 4: Basic settings file
    try:
        if not os.path.exists("/settings.toml"):
            with open("/settings.toml", "w") as f:
                f.write("""# Basic settings
CIRCUITPY_WIFI_SSID = ""
CIRCUITPY_WIFI_PASSWORD = ""
SCREENSAVER_ENABLED = true
SCREENSAVER_TIMEOUT = 300
""")
            print("✅ Basic settings.toml created")
            fixes_applied += 1
        else:
            print("ℹ️ Settings file already exists")
    except Exception as e:
        print(f"❌ Settings fix failed: {e}")
    
    print(f"\n🔧 Quick fix complete: {fixes_applied} fixes applied")
    return fixes_applied > 0

# Utility functions for integration
def check_system_health():
    """Quick system health check"""
    try:
        recovery = RecoverySystem()
        fs_ok, missing = recovery.filesystem_check_silent()
        
        health_status = {
            "filesystem_ok": fs_ok,
            "missing_files": missing,
            "memory_free": gc.mem_free(),
            "wifi_available": WIFI_AVAILABLE,
            "zipper_available": ZIPPER_AVAILABLE
        }
        
        return health_status
    except Exception as e:
        return {"error": str(e)}

def auto_repair():
    """Automatic repair attempt"""
    print("🔄 Auto-repair starting...")
    
    try:
        recovery = RecoverySystem()
        
        # Run filesystem check
        fs_ok, missing = recovery.filesystem_check_silent()
        
        if not fs_ok:
            print(f"⚠️ Found {len(missing)} missing files")
            
            # Try quick fixes first
            if quick_fix():
                print("✅ Quick fixes applied")
            
            # If core files missing, try emergency recovery
            critical_missing = [f for f in missing if f in ["boot.py", "code.py"]]
            if critical_missing:
                print("🚨 Critical files missing - running emergency recovery")
                emergency_recovery()
        
        print("🔄 Auto-repair complete")
        return True
        
    except Exception as e:
        print(f"❌ Auto-repair failed: {e}")
        return False

# Console interface for headless operation
def console_recovery():
    """Console-based recovery for systems without display"""
    print("💻 Console Recovery Mode")
    print("=" * 25)
    
    while True:
        print("\nRecovery Options:")
        print("1. System Status")
        print("2. Filesystem Check")
        print("3. Quick Fix")
        print("4. Emergency Recovery")
        print("5. Clear Flags")
        print("6. Exit")
        
        try:
            choice = input("\nSelect option (1-6): ").strip()
            
            if choice == "1":
                health = check_system_health()
                print("\nSystem Status:")
                for key, value in health.items():
                    print(f"  {key}: {value}")
            
            elif choice == "2":
                recovery = RecoverySystem()
                recovery.filesystem_check()
            
            elif choice == "3":
                quick_fix()
            
            elif choice == "4":
                emergency_recovery()
            
            elif choice == "5":
                try:
                    import microcontroller
                    for i in range(10):
                        microcontroller.nvm[i] = 0
                    print("✅ All flags cleared")
                except Exception as e:
                    print(f"❌ Flag clear failed: {e}")
            
            elif choice == "6":
                print("Exiting console recovery")
                break
            
            else:
                print("Invalid option")
                
        except KeyboardInterrupt:
            print("\nExiting console recovery")
            break
        except Exception as e:
            print(f"Error: {e}")

# Export main classes and functions
__all__ = [
    'RecoverySystem',
    'StatusBar',
    'main',
    'emergency_recovery',
    'quick_fix',
    'check_system_health',
    'auto_repair',
    'console_recovery',
    'CORE_MANIFEST'
]

# Auto-start based on how the module is loaded
if __name__ == "__main__":
    # Direct execution
    success = main()
    if not success:
        print("\n🚨 GUI recovery failed - trying console mode")
        console_recovery()
else:
    # Module import
    print(f"📦 StageTwo Recovery System V{__version__} loaded")
    print("🔧 Use main() for GUI recovery")
    print("💻 Use console_recovery() for headless operation")
    print("🚨 Use emergency_recovery() for critical failures")
    print("⚡ Use quick_fix() for common issues")

# Initial system health check on import
try:
    gc.collect()
    health = check_system_health()
    if "error" not in health:
        if not health.get("filesystem_ok", True):
            print("⚠️ System health warning: filesystem issues detected")
            print("💡 Run recovery.main() or recovery.auto_repair()")
    print(f"💾 Recovery module ready - {gc.mem_free()} bytes free")
except Exception:
    print("⚠️ Initial health check failed - system may need attention")

# Integration examples
INTEGRATION_EXAMPLES = {
    "health_check": '''
# Quick system health check
from recovery import check_system_health
health = check_system_health()
print(f"System OK: {health.get('filesystem_ok', False)}")
''',
    
    "auto_repair": '''
# Automatic repair attempt
from recovery import auto_repair
if auto_repair():
    print("System repaired successfully")
else:
    print("Manual intervention required")
''',
    
    "emergency_mode": '''
# Emergency recovery for critical failures
from recovery import emergency_recovery
emergency_recovery()
''',
    
    "gui_recovery": '''
# Full GUI recovery system
from recovery import main
main()
''',
    
    "console_recovery": '''
# Console-based recovery
from recovery import console_recovery
console_recovery()
'''
}

def show_integration_examples():
    """Show integration examples"""
    print("\n📚 Integration Examples:")
    print("=" * 30)
    
    for name, code in INTEGRATION_EXAMPLES.items():
        print(f"\n🔹 {name.replace('_', ' ').title()}:")
        print(code.strip())
    
    print("\n" + "=" * 30)

# Quick start message
print("🎯 StageTwo Recovery System ready!")
print("💡 Quick commands:")
print("  • recovery.main() - Start GUI recovery")
print("  • recovery.quick_fix() - Apply common fixes")
print("  • recovery.emergency_recovery() - Critical failure recovery")
print("  • recovery.show_integration_examples() - See usage examples")

# End of recovery system


