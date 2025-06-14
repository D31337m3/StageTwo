"""
StageTwo Web Recovery Script
Downloads and installs core system files from GitHub repository
Designed to be fetched and executed by the recovery system

(C) 2025 StageTwo Team
"""

import os
import gc
import time
import wifi
import socketpool
import adafruit_requests
import microcontroller
import storage

# Try to import zipper - required for extraction
try:
    import zipper
    ZIPPER_AVAILABLE = True
except ImportError:
    ZIPPER_AVAILABLE = False
    print("WARNING: zipper library not available - will attempt to download")

# Configuration
CORE_SYSTEM_URL = "https://raw.githubusercontent.com/D31337m3/StageTwo/main/recovery/core_system.zip"
ZIPPER_URL = "https://raw.githubusercontent.com/D31337m3/StageTwo/main/recovery/zipper.py"
TEMP_DIR = "/temp"
TEMP_ZIP_PATH = "/temp/core_system.zip"
BACKUP_DIR = "/temp/backup"

# Version info
__version__ = "1.1"
__author__ = "StageTwo Team"

class WebRecoveryError(Exception):
    """Custom exception for web recovery errors"""
    pass

class WebRecovery:
    """Web recovery system for downloading and installing core files"""
    
    def __init__(self):
        self.session = None
        self.pool = None
        self.downloaded_size = 0
        self.total_size = 0
        self.status_callback = None
        
    def set_status_callback(self, callback):
        """Set callback function for status updates"""
        self.status_callback = callback
        
    def _update_status(self, message, progress=None):
        """Update status with optional progress"""
        print(f"WEB_RECOVERY: {message}")
        if self.status_callback:
            try:
                self.status_callback(message, progress)
            except Exception:
                pass
    
    def _ensure_wifi_connected(self):
        """Ensure WiFi is connected"""
        self._update_status("Checking WiFi connection...")
        
        if not wifi.radio.enabled:
            self._update_status("Enabling WiFi radio...")
            wifi.radio.enabled = True
            time.sleep(2)
        
        if not wifi.radio.connected:
            self._update_status("WiFi not connected - attempting connection...")
            
            # Try to get credentials from settings
            wifi_ssid = ""
            wifi_password = ""
            
            try:
                # Try to load from settings.toml
                with open("/settings.toml", "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("CIRCUITPY_WIFI_SSID"):
                            wifi_ssid = line.split("=", 1)[1].strip().strip('"').strip("'")
                        elif line.startswith("CIRCUITPY_WIFI_PASSWORD"):
                            wifi_password = line.split("=", 1)[1].strip().strip('"').strip("'")
            except Exception as e:
                self._update_status(f"Could not load WiFi settings: {e}")
            
            if not wifi_ssid:
                raise WebRecoveryError("WiFi credentials not configured in settings.toml")
            
            self._update_status(f"Connecting to WiFi: {wifi_ssid}")
            
            try:
                wifi.radio.connect(wifi_ssid, wifi_password, timeout=20)
            except Exception as e:
                raise WebRecoveryError(f"WiFi connection failed: {e}")
        
        if not wifi.radio.connected:
            raise WebRecoveryError("WiFi connection failed")
        
        self._update_status(f"WiFi connected: {wifi.radio.ipv4_address}")
        
        # Initialize HTTP session
        if not self.pool:
            self.pool = socketpool.SocketPool(wifi.radio)
        if not self.session:
            self.session = adafruit_requests.Session(self.pool)
    
    def _download_zipper_library(self):
        """Download zipper.py library if not available"""
        global ZIPPER_AVAILABLE, zipper
        
        if ZIPPER_AVAILABLE:
            return True
        
        self._update_status("Downloading zipper library...")
        
        try:
            # Ensure we have a session
            if not self.session:
                self._ensure_wifi_connected()
            
            # Download zipper.py
            self._update_status(f"Requesting: {ZIPPER_URL}")
            response = self.session.get(ZIPPER_URL, timeout=30)
            
            if response.status_code != 200:
                raise WebRecoveryError(f"HTTP {response.status_code}: Failed to download zipper library")
            
            # Save zipper.py to root directory
            zipper_content = response.text
            response.close()
            
            # Validate content (basic check)
            if "def zip_files" not in zipper_content or "def unzip" not in zipper_content:
                raise WebRecoveryError("Downloaded zipper library appears to be invalid")
            
            # Write zipper.py
            with open("/zipper.py", "w") as f:
                f.write(zipper_content)
            
            self._update_status("Zipper library downloaded successfully")
            
            # Try to import the downloaded zipper module
            try:
                # Force reload if already imported
                if 'zipper' in globals():
                    del globals()['zipper']
                
                # Clear from sys.modules if present
                import sys
                if 'zipper' in sys.modules:
                    del sys.modules['zipper']
                
                # Import the newly downloaded module
                import zipper
                ZIPPER_AVAILABLE = True
                
                self._update_status("Zipper library imported successfully")
                return True
                
            except ImportError as e:
                raise WebRecoveryError(f"Failed to import downloaded zipper library: {e}")
            
        except Exception as e:
            # Clean up partial download
            try:
                os.remove("/zipper.py")
            except:
                pass
            raise WebRecoveryError(f"Zipper download failed: {e}")
    
    def _prepare_directories(self):
        """Prepare necessary directories"""
        self._update_status("Preparing directories...")
        
        # Ensure storage is writable
        try:
            storage.remount("/", readonly=False)
        except Exception as e:
            self._update_status(f"Warning: Could not remount storage: {e}")
        
        # Create temp directory
        try:
            os.mkdir(TEMP_DIR)
            self._update_status(f"Created directory: {TEMP_DIR}")
        except OSError:
            self._update_status(f"Directory already exists: {TEMP_DIR}")
        
        # Create backup directory
        try:
            os.mkdir(BACKUP_DIR)
            self._update_status(f"Created backup directory: {BACKUP_DIR}")
        except OSError:
            self._update_status(f"Backup directory already exists: {BACKUP_DIR}")
    
    def _backup_existing_files(self):
        """Backup existing core files before replacement"""
        self._update_status("Backing up existing files...")
        
        core_files = [
            "boot.py",
            "code.py", 
            "recovery.py",
            "settings.toml"
        ]
        
        backup_count = 0
        
        for file_path in core_files:
            try:
                # Check if file exists
                os.stat(file_path)
                
                # Create backup
                backup_path = f"{BACKUP_DIR}/{file_path}.bak"
                
                # Copy file to backup
                with open(file_path, "rb") as src:
                    with open(backup_path, "wb") as dst:
                        while True:
                            chunk = src.read(1024)
                            if not chunk:
                                break
                            dst.write(chunk)
                
                backup_count += 1
                self._update_status(f"Backed up: {file_path}")
                
            except OSError:
                # File doesn't exist, skip backup
                self._update_status(f"File not found (skipping backup): {file_path}")
            except Exception as e:
                self._update_status(f"Backup failed for {file_path}: {e}")
        
        self._update_status(f"Backup complete: {backup_count} files backed up")
    
    def _download_core_system(self):
        """Download core system ZIP file"""
        self._update_status("Starting download of core system files...")
        
        try:
            # Make HTTP request with streaming
            self._update_status(f"Requesting: {CORE_SYSTEM_URL}")
            response = self.session.get(CORE_SYSTEM_URL, stream=True, timeout=60)
            
            if response.status_code != 200:
                raise WebRecoveryError(f"HTTP {response.status_code}: Failed to download core system")
            
            # Get content length if available
            try:
                self.total_size = int(response.headers.get('content-length', 0))
                self._update_status(f"Download size: {self.total_size} bytes")
            except:
                self.total_size = 0
                self._update_status("Download size: Unknown")
            
            # Download with progress tracking
            self.downloaded_size = 0
            
            with open(TEMP_ZIP_PATH, "wb") as f:
                while True:
                    chunk = response.raw.read(1024)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    self.downloaded_size += len(chunk)
                    
                    # Update progress
                    if self.total_size > 0:
                        progress = (self.downloaded_size / self.total_size) * 100
                        self._update_status(f"Downloading: {progress:.1f}% ({self.downloaded_size}/{self.total_size} bytes)", progress)
                    else:
                        self._update_status(f"Downloaded: {self.downloaded_size} bytes")
                    
                    # Garbage collection to prevent memory issues
                    if self.downloaded_size % 10240 == 0:  # Every 10KB
                        gc.collect()
            
            response.close()
            
            # Verify download
            try:
                file_stat = os.stat(TEMP_ZIP_PATH)
                actual_size = file_stat[6]
                
                if actual_size == 0:
                    raise WebRecoveryError("Downloaded file is empty")
                
                if self.total_size > 0 and actual_size != self.total_size:
                    self._update_status(f"Warning: Size mismatch - expected {self.total_size}, got {actual_size}")
                
                self._update_status(f"Download complete: {actual_size} bytes")
                
            except Exception as e:
                raise WebRecoveryError(f"Download verification failed: {e}")
                
        except Exception as e:
            # Clean up partial download
            try:
                os.remove(TEMP_ZIP_PATH)
            except:
                pass
            raise WebRecoveryError(f"Download failed: {e}")
    
    def _extract_core_system(self):
        """Extract core system files to root directory"""
        if not ZIPPER_AVAILABLE:
            raise WebRecoveryError("Zipper library not available for extraction")
        
        self._update_status("Extracting core system files...")
        
        try:
            # Verify ZIP file exists
            os.stat(TEMP_ZIP_PATH)
            
            # Extract files using zipper library
            extracted_count = 0
            
            with open(TEMP_ZIP_PATH, "rb") as zf:
                # Read ZIP file header to get file list first
                file_list = []
                
                # Simple ZIP parsing to get file count
                zf.seek(0)
                while True:
                    sig = zf.read(4)
                    if sig == b"PK\x03\x04":  # Local file header
                        zf.read(2)  # version
                        zf.read(2)  # flags
                        zf.read(2)  # compression
                        zf.read(2)  # mod time
                        zf.read(2)  # mod date
                        zf.read(4)  # crc32
                        comp_size = int.from_bytes(zf.read(4), 'little')
                        zf.read(4)  # uncompressed size
                        name_len = int.from_bytes(zf.read(2), 'little')
                        extra_len = int.from_bytes(zf.read(2), 'little')
                        
                        filename = zf.read(name_len).decode('utf-8')
                        zf.read(extra_len)  # extra field
                        zf.read(comp_size)  # file data
                        
                        file_list.append(filename)
                        
                    elif sig == b"PK\x01\x02" or sig == b"PK\x05\x06" or not sig:
                        break
                    else:
                        break
            
            total_files = len(file_list)
            self._update_status(f"Found {total_files} files to extract")
            
            # Now extract using zipper.unzip
            zipper.unzip(TEMP_ZIP_PATH, "/")
            
            self._update_status(f"Extraction complete: {total_files} files extracted to root directory")
            
        except Exception as e:
            raise WebRecoveryError(f"Extraction failed: {e}")
    
    def _verify_installation(self):
        """Verify that core files were installed correctly"""
        self._update_status("Verifying installation...")
        
        required_files = [
            "boot.py",
            "code.py",
            "recovery.py"
        ]
        
        verified_count = 0
        missing_files = []
        
        for file_path in required_files:
            try:
                file_stat = os.stat(file_path)
                if file_stat[6] > 0:  # File size > 0
                    verified_count += 1
                    self._update_status(f"Verified: {file_path} ({file_stat[6]} bytes)")
                else:
                    missing_files.append(f"{file_path} (empty)")
            except OSError:
                missing_files.append(f"{file_path} (missing)")
        
        if missing_files:
            raise WebRecoveryError(f"Installation verification failed - missing files: {', '.join(missing_files)}")
        
        self._update_status(f"Installation verified: {verified_count}/{len(required_files)} core files present")
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        self._update_status("Cleaning up temporary files...")
        
        try:
            os.remove(TEMP_ZIP_PATH)
            self._update_status("Removed temporary ZIP file")
        except Exception as e:
            self._update_status(f"Could not remove temp ZIP: {e}")
        
        # Keep backup directory for safety
        self._update_status("Backup files preserved in /temp/backup/")
    
    def run_recovery(self):
        """Run the complete web recovery process"""
        start_time = time.monotonic()
        
        try:
            self._update_status("=== StageTwo Web Recovery Started ===")
            self._update_status(f"Version: {__version__}")
            
            # Step 1: Ensure WiFi connection
            self._ensure_wifi_connected()
            
            # Step 2: Download zipper library if needed
            if not ZIPPER_AVAILABLE:
                self._update_status("Zipper library not available - downloading...")
                if not self._download_zipper_library():
                    raise WebRecoveryError("Failed to download zipper library")
            else:
                self._update_status("Zipper library already available")
            
            # Step 3: Prepare directories
            self._prepare_directories()
            
            # Step 4: Backup existing files
            self._backup_existing_files()
            
            # Step 5: Download core system
            self._download_core_system()
            
            # Step 6: Extract core system
            self._extract_core_system()
            
            # Step 7: Verify installation
            self._verify_installation()
            
            # Step 8: Cleanup
            self._cleanup_temp_files()
            
            elapsed_time = time.monotonic() - start_time
            self._update_status(f"=== Web Recovery Complete ({elapsed_time:.1f}s) ===")
            self._update_status("System files have been restored from GitHub repository")
            self._update_status("Reboot recommended to apply changes")
            
            return True
            
        except WebRecoveryError as e:
            self._update_status(f"RECOVERY FAILED: {e}")
            return False
        except Exception as e:
            self._update_status(f"UNEXPECTED ERROR: {e}")
            return False
        finally:
            # Cleanup session
            if self.session:
                try:
                    self.session.close()
                except:
                    pass
            
            # Force garbage collection
            gc.collect()

def download_zipper_standalone():
    """Standalone function to download zipper library"""
    global ZIPPER_AVAILABLE, zipper
    
    print("📥 Downloading zipper library...")
    
    try:
        # Check WiFi connection
        if not wifi.radio.connected:
            print("❌ WiFi not connected")
            return False
        
        # Download zipper.py
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool)
        
        print(f"🌐 Requesting: {ZIPPER_URL}")
        response = session.get(ZIPPER_URL, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ HTTP {response.status_code}: Failed to download zipper library")
            return False
        
        # Validate content
        zipper_content = response.text
        if "def zip_files" not in zipper_content or "def unzip" not in zipper_content:
            print("❌ Downloaded zipper library appears to be invalid")
            return False
        
        # Ensure storage is writable
        try:
            storage.remount("/", readonly=False)
        except Exception as e:
            print(f"⚠️ Storage remount warning: {e}")
        
        # Write zipper.py
        with open("/zipper.py", "w") as f:
            f.write(zipper_content)
        
        print("✅ Zipper library downloaded successfully")
        
        # Try to import
        try:
            # Clear any existing import
            import sys
            if 'zipper' in sys.modules:
                del sys.modules['zipper']
            
            # Import the new module
            import zipper
            ZIPPER_AVAILABLE = True
            
            print("✅ Zipper library imported successfully")
            return True
            
        except ImportError as e:
            print(f"❌ Failed to import downloaded zipper library: {e}")
            return False
        
        finally:
            response.close()
            session.close()
            
    except Exception as e:
        print(f"❌ Zipper download failed: {e}")
        return False

def main():
    """Main entry point for web recovery"""
    print("=" * 60)
    print("🌐 StageTwo Web Recovery System")
    print(f"📋 Version: {__version__}")
    print("=" * 60)
    
    # Check and download zipper if needed
    if not ZIPPER_AVAILABLE:
        print("⚠️ Zipper library not available - attempting download...")
        if not download_zipper_standalone():
            print("❌ FATAL: Could not download zipper library")
            print("   Manual intervention required")
            return False
        print("✅ Zipper library now available")
    
    try:
        # Create recovery instance
        recovery = WebRecovery()
        
        # Run recovery process
        success = recovery.run_recovery()
        
        if success:
            print("\n✅ Web recovery completed successfully!")
            print("🔄 Reboot system to apply changes")
            
            # Offer to reboot
            try:
                print("Reboot recommended to apply changes")
                print("Use microcontroller.reset() or supervisor.reload()")
            except:
                pass
            
            return True
        else:
            print("\n❌ Web recovery failed!")
            print("Check error messages above for details")
            print("Backup files are available in /temp/backup/")
            return False
            
    except Exception as e:
        print(f"\n💥 Fatal error in web recovery: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        return False
    
    finally:
        # Final cleanup
        gc.collect()
        print(f"💾 Final memory: {gc.mem_free()} bytes free")

def quick_recovery():
    """Quick recovery function for integration with recovery.py"""
    try:
        # Auto-download zipper if needed
        if not ZIPPER_AVAILABLE:
            if not download_zipper_standalone():
                print("❌ Quick recovery failed: Could not download zipper library")
                return False
        
        recovery = WebRecovery()
        return recovery.run_recovery()
    except Exception as e:
        print(f"Quick recovery failed: {e}")
        return False

def recovery_with_callback(status_callback):
    """Recovery with status callback for GUI integration"""
    try:
        # Auto-download zipper if needed
        if not ZIPPER_AVAILABLE:
            if status_callback:
                status_callback("Downloading zipper library...", 0)
            if not download_zipper_standalone():
                if status_callback:
                    status_callback("Failed to download zipper library", 0)
                return False
        
        recovery = WebRecovery()
        recovery.set_status_callback(status_callback)
        return recovery.run_recovery()
    except Exception as e:
        print(f"Recovery with callback failed: {e}")
        if status_callback:
            status_callback(f"Recovery failed: {e}", 0)
        return False

def restore_from_backup():
    """Restore files from backup if recovery failed"""
    print("🔄 Attempting to restore from backup...")
    
    try:
        backup_files = os.listdir(BACKUP_DIR)
        restored_count = 0
        
        for backup_file in backup_files:
            if backup_file.endswith('.bak'):
                original_name = backup_file[:-4]  # Remove .bak extension
                backup_path = f"{BACKUP_DIR}/{backup_file}"
                restore_path = f"/{original_name}"
                
                try:
                    # Copy backup back to original location
                    with open(backup_path, "rb") as src:
                        with open(restore_path, "wb") as dst:
                            while True:
                                chunk = src.read(1024)
                                if not chunk:
                                    break
                                dst.write(chunk)
                    
                    restored_count += 1
                    print(f"✅ Restored: {original_name}")
                    
                except Exception as e:
                    print(f"❌ Failed to restore {original_name}: {e}")
        
        print(f"🔄 Backup restore complete: {restored_count} files restored")
        return restored_count > 0
        
    except Exception as e:
        print(f"❌ Backup restore failed: {e}")
        return False

def check_recovery_prerequisites():
    """Check if web recovery can run"""
    issues = []
    
    # Check zipper library (will be auto-downloaded)
    if not ZIPPER_AVAILABLE:
        # Try to download zipper first
        try:
            if wifi.radio.connected:
                issues.append("zipper library not available (will auto-download)")
            else:
                issues.append("zipper library not available and WiFi not connected")
        except:
            issues.append("zipper library not available and WiFi check failed")
    
    # Check WiFi
    try:
        if not hasattr(wifi, 'radio'):
            issues.append("WiFi not available")
        elif not wifi.radio.connected:
            issues.append("WiFi not connected")
    except:
        issues.append("WiFi module error")
    
    # Check storage writability
    try:
        storage.remount("/", readonly=False)
    except Exception as e:
        issues.append(f"Storage not writable: {e}")
    
    # Check available memory
    try:
        free_mem = gc.mem_free()
        if free_mem < 50000:  # Less than 50KB
            issues.append(f"Low memory: {free_mem} bytes free")
    except:
        issues.append("Memory check failed")
    
    return issues

def emergency_download():
    """Emergency download of just the essential files"""
    print("🚨 Emergency Download Mode")
    print("Downloading only essential files...")
    
    essential_urls = {
        "boot.py": "https://raw.githubusercontent.com/D31337m3/StageTwo/main/boot.py",
        "code.py": "https://raw.githubusercontent.com/D31337m3/StageTwo/main/code.py",
        "recovery.py": "https://raw.githubusercontent.com/D31337m3/StageTwo/main/recovery.py"
    }
    
    try:
        # Ensure WiFi
        if not wifi.radio.connected:
            print("❌ WiFi not connected for emergency download")
            return False
        
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool)
        
        success_count = 0
        
        # Also download zipper if needed
        if not ZIPPER_AVAILABLE:
            essential_urls["zipper.py"] = ZIPPER_URL
        
        for filename, url in essential_urls.items():
            try:
                print(f"📥 Downloading {filename}...")
                response = session.get(url, timeout=30)
                
                if response.status_code == 200:
                    # Backup existing file if it exists
                    try:
                        os.stat(filename)
                        backup_name = f"/temp/{filename}.emergency_bak"
                        try:
                            os.mkdir("/temp")
                        except:
                            pass
                        
                        with open(filename, "rb") as src:
                            with open(backup_name, "wb") as dst:
                                dst.write(src.read())
                        print(f"📦 Backed up existing {filename}")
                    except:
                        pass
                    
                    # Write new file
                    with open(filename, "w") as f:
                        f.write(response.text)
                    
                    success_count += 1
                    print(f"✅ Downloaded {filename}")
                    
                    # If we downloaded zipper, try to import it
                    if filename == "zipper.py":
                        try:
                            import sys
                            if 'zipper' in sys.modules:
                                del sys.modules['zipper']
                            import zipper
                            global ZIPPER_AVAILABLE
                            ZIPPER_AVAILABLE = True
                            print("✅ Zipper library imported")
                        except:
                            print("⚠️ Zipper downloaded but import failed")
                    
                else:
                    print(f"❌ Failed to download {filename}: HTTP {response.status_code}")
                
                response.close()
                
            except Exception as e:
                print(f"❌ Error downloading {filename}: {e}")
        
        session.close()
        
        print(f"🚨 Emergency download complete: {success_count}/{len(essential_urls)} files")
        return success_count > 0
        
    except Exception as e:
        print(f"❌ Emergency download failed: {e}")
        return False

def get_recovery_status():
    """Get current recovery status and system info"""
    status = {
        "version": __version__,
        "prerequisites": check_recovery_prerequisites(),
        "zipper_available": ZIPPER_AVAILABLE,
        "zipper_can_download": False,
        "temp_dir_exists": False,
        "backup_dir_exists": False,
        "wifi_connected": False,
        "memory_free": 0
    }
    
    try:
        # Check if we can download zipper
        try:
            if wifi.radio.connected:
                status["zipper_can_download"] = True
        except:
            pass
        
        # Check directories
        try:
            os.listdir(TEMP_DIR)
            status["temp_dir_exists"] = True
        except:
            pass
        
        try:
            os.listdir(BACKUP_DIR)
            status["backup_dir_exists"] = True
        except:
            pass
        
        # Check WiFi
        try:
            status["wifi_connected"] = wifi.radio.connected
        except:
            pass
        
        # Check memory
        try:
            status["memory_free"] = gc.mem_free()
        except:
            pass
        
    except Exception as e:
        status["error"] = str(e)
    
    return status

def auto_setup_zipper():
    """Automatically setup zipper library if needed"""
    global ZIPPER_AVAILABLE
    
    if ZIPPER_AVAILABLE:
        print("✅ Zipper library already available")
        return True
    
    print("🔧 Auto-setup: Zipper library needed")
    
    # Check if zipper.py exists but wasn't imported
    try:
        os.stat("/zipper.py")
        print("📁 Found zipper.py file, attempting import...")
        
        try:
            import sys
            if 'zipper' in sys.modules:
                del sys.modules['zipper']
            import zipper
            ZIPPER_AVAILABLE = True
            print("✅ Zipper library imported from existing file")
            return True
        except ImportError as e:
            print(f"❌ Failed to import existing zipper.py: {e}")
            # Continue to download
    except OSError:
        print("📁 No existing zipper.py found")
    
    # Try to download
    if download_zipper_standalone():
        print("✅ Zipper library auto-setup complete")
        return True
    else:
        print("❌ Zipper library auto-setup failed")
        return False

# Integration functions for recovery.py
def integrate_with_recovery():
    """Integration point for recovery.py"""
    # Auto-setup zipper if needed
    zipper_ready = ZIPPER_AVAILABLE or auto_setup_zipper()
    
    prerequisites = check_recovery_prerequisites()
    # Filter out zipper warning if we can auto-download
    if zipper_ready:
                        if not p.startswith("zipper library not available")]
    
    return {
        "name": "Web Recovery",
        "description": "Download and install core system files from GitHub",
        "function": quick_recovery,
        "prerequisites": prerequisites,
        "available": len(prerequisites) == 0,
        "auto_zipper": not ZIPPER_AVAILABLE and zipper_ready
    }

def test_zipper_functionality():
    """Test zipper library functionality"""
    print("🧪 Testing zipper functionality...")
    
    if not ZIPPER_AVAILABLE:
        print("❌ Zipper not available for testing")
        return False
    
    try:
        # Test basic zipper functions exist
        if not hasattr(zipper, 'zip_files'):
            print("❌ zipper.zip_files function not found")
            return False
        
        if not hasattr(zipper, 'unzip'):
            print("❌ zipper.unzip function not found")
            return False
        
        print("✅ Zipper library functions available")
        
        # Create a simple test
        test_content = "# Test file for zipper\nprint('Zipper test successful')\n"
        
        # Write test file
        with open("/temp_test.py", "w") as f:
            f.write(test_content)
        
        # Test zip creation
        zipper.zip_files("/temp_test.zip", ["/temp_test.py"])
        print("✅ ZIP creation test passed")
        
        # Test extraction
        os.remove("/temp_test.py")  # Remove original
        zipper.unzip("/temp_test.zip", "/")
        print("✅ ZIP extraction test passed")
        
        # Verify extracted content
        with open("/temp_test.py", "r") as f:
            extracted_content = f.read()
        
        if extracted_content == test_content:
            print("✅ Content verification test passed")
        else:
            print("❌ Content verification failed")
            return False
        
        # Cleanup
        os.remove("/temp_test.py")
        os.remove("/temp_test.zip")
        
        print("✅ All zipper tests passed")
        return True
        
    except Exception as e:
        print(f"❌ Zipper test failed: {e}")
        
        # Cleanup on failure
        try:
            os.remove("/temp_test.py")
        except:
            pass
        try:
            os.remove("/temp_test.zip")
        except:
            pass
        
        return False

def repair_zipper_installation():
    """Repair or reinstall zipper library"""
    global ZIPPER_AVAILABLE
    
    print("🔧 Repairing zipper installation...")
    
    # Remove existing zipper.py if corrupted
    try:
        os.remove("/zipper.py")
        print("🗑️ Removed existing zipper.py")
    except:
        pass
    
    # Clear from memory
    try:
        import sys
        if 'zipper' in sys.modules:
            del sys.modules['zipper']
        if 'zipper' in globals():
            del globals()['zipper']
        ZIPPER_AVAILABLE = False
        print("🧹 Cleared zipper from memory")
    except:
        pass
    
    # Download fresh copy
    if download_zipper_standalone():
        print("✅ Zipper repair successful")
        return test_zipper_functionality()
    else:
        print("❌ Zipper repair failed")
        return False

def comprehensive_recovery():
    """Comprehensive recovery with all safety checks"""
    print("🛡️ Starting comprehensive recovery...")
    
    # Step 1: System checks
    print("\n📋 Step 1: System Prerequisites")
    issues = check_recovery_prerequisites()
    if issues:
        print("⚠️ Issues found:")
        for issue in issues:
            print(f"   • {issue}")
        
        # Try to resolve zipper issue
        if any("zipper" in issue for issue in issues):
            print("🔧 Attempting to resolve zipper dependency...")
            if not auto_setup_zipper():
                print("❌ Could not resolve zipper dependency")
                return False
    
    # Step 2: Test zipper if available
    if ZIPPER_AVAILABLE:
        print("\n🧪 Step 2: Testing zipper functionality")
        if not test_zipper_functionality():
            print("🔧 Zipper test failed, attempting repair...")
            if not repair_zipper_installation():
                print("❌ Could not repair zipper installation")
                return False
    
    # Step 3: Memory check
    print("\n💾 Step 3: Memory optimization")
    gc.collect()
    free_mem = gc.mem_free()
    print(f"Available memory: {free_mem} bytes")
    
    if free_mem < 30000:
        print("⚠️ Low memory detected, running cleanup...")
        # Additional cleanup could go here
        gc.collect()
        free_mem = gc.mem_free()
        print(f"Memory after cleanup: {free_mem} bytes")
    
    # Step 4: Run recovery
    print("\n🌐 Step 4: Web recovery execution")
    try:
        recovery = WebRecovery()
        success = recovery.run_recovery()
        
        if success:
            print("\n✅ Comprehensive recovery completed successfully!")
            return True
        else:
            print("\n❌ Recovery failed during execution")
            return False
            
    except Exception as e:
        print(f"\n💥 Recovery failed with error: {e}")
        return False

# Export main functions
__all__ = [
    'WebRecovery',
    'main',
    'quick_recovery',
    'recovery_with_callback',
    'restore_from_backup',
    'check_recovery_prerequisites',
    'emergency_download',
    'get_recovery_status',
    'integrate_with_recovery',
    'download_zipper_standalone',
    'auto_setup_zipper',
    'test_zipper_functionality',
    'repair_zipper_installation',
    'comprehensive_recovery'
]

# Auto-execution check
if __name__ == "__main__":
    # Direct execution
    success = main()
    exit(0 if success else 1)
else:
    # Module import
    print(f"📦 StageTwo Web Recovery V{__version__} loaded")
    print("🌐 Use main() for full recovery")
    print("⚡ Use quick_recovery() for simple recovery")
    print("🚨 Use emergency_download() for critical files only")
    print("🛡️ Use comprehensive_recovery() for full safety checks")
    
    # Auto-setup zipper if needed
    if not ZIPPER_AVAILABLE:
        print("🔧 Auto-setup: Checking zipper availability...")
        auto_setup_zipper()
    
    # Show current status
    status = get_recovery_status()
    if status["prerequisites"]:
        print(f"⚠️ Prerequisites: {', '.join(status['prerequisites'])}")
    else:
        print("✅ All prerequisites met")
    
    print(f"💾 Memory available: {status['memory_free']} bytes")
    print(f"📚 Zipper library: {'Available' if ZIPPER_AVAILABLE else 'Will auto-download'}")

# Usage examples with zipper auto-download
USAGE_EXAMPLES = """
Usage Examples (with automatic zipper download):

1. Direct execution:
   python web_recovery.py

2. From recovery system:
   import web_recovery
   web_recovery.main()

3. Quick recovery (auto-downloads zipper):
   import web_recovery
   success = web_recovery.quick_recovery()

4. Comprehensive recovery (full safety checks):
   import web_recovery
   success = web_recovery.comprehensive_recovery()

5. Emergency mode (downloads essentials + zipper):
   import web_recovery
   web_recovery.emergency_download()

6. Auto-setup zipper only:
   import web_recovery
   web_recovery.auto_setup_zipper()

7. Test zipper functionality:
   import web_recovery
   web_recovery.test_zipper_functionality()

8. Repair zipper installation:
   import web_recovery
   web_recovery.repair_zipper_installation()

9. Check status (includes zipper availability):
   import web_recovery
   status = web_recovery.get_recovery_status()
   print(f"Zipper available: {status['zipper_available']}")
   print(f"Can download zipper: {status['zipper_can_download']}")
"""

def show_usage():
    """Show usage examples"""
    print(USAGE_EXAMPLES)

# Enhanced initialization with zipper auto-setup
try:
    gc.collect()
    print(f"🎯 Web Recovery ready - {gc.mem_free()} bytes available")
    
    # Check and report zipper status
    if ZIPPER_AVAILABLE:
        print("📚 Zipper library: Ready")
    else:
        print("📚 Zipper library: Will auto-download when needed")
    
    # Check other prerequisites
    issues = check_recovery_prerequisites()
    critical_issues = [i for i in issues if not i.startswith("zipper library")]
    
    if critical_issues:
        print(f"⚠️ Critical issues: {', '.join(critical_issues)}")
    else:
        print("✅ Ready for web recovery operations")
        
except Exception as e:
    print(f"⚠️ Initialization warning: {e}")

# Integration helper for recovery.py
def get_integration_info():
    """Get integration information for recovery.py"""
    return {
        "module_name": "web_recovery",
        "version": __version__,
        "functions": {
            "main": "Full web recovery with user interaction",
            "quick_recovery": "Simple recovery for integration",
            "comprehensive_recovery": "Recovery with full safety checks",
            "emergency_download": "Download essential files only",
            "auto_setup_zipper": "Automatically setup zipper library"
        },
        "zipper_handling": "Automatic download and setup",
        "prerequisites_auto_resolve": True,
        "backup_support": True,
        "progress_callbacks": True
    }

print("🔗 Integration ready - use get_integration_info() for details")


