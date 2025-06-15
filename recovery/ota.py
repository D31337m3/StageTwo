"""
StageTwo OTA (Over-The-Air) Update System
Downloads and installs library and application updates with version checking
Ensures only newer versions are installed

(C) 2025 StageTwo Team
"""

import os
import gc
import time
import json
import wifi
import socketpool
import adafruit_requests
import microcontroller
import storage
import re

# Try to import zipper - will auto-download if needed
try:
    import zipper
    ZIPPER_AVAILABLE = True
except ImportError:
    ZIPPER_AVAILABLE = False
    print("WARNING: zipper library not available - will attempt to download")

# Configuration
CORE_LIB_URL = "https://raw.githubusercontent.com/D31337m3/StageTwo/main/OTA/core_lib.zip"
CORE_APPLICATIONS_URL = "https://raw.githubusercontent.com/D31337m3/StageTwo/main/OTA/core_applications.zip"
ZIPPER_URL = "https://raw.githubusercontent.com/D31337m3/StageTwo/main/recovery/zipper.py"
TEMP_DIR = "/temp"
OTA_DIR = "/temp/ota"
BACKUP_DIR = "/temp/ota_backup"

# Version info
__version__ = "1.0"
__author__ = "StageTwo Team"

class OTAError(Exception):
    """Custom exception for OTA errors"""
    pass

class VersionManager:
    """Handles version comparison and tracking"""
    
    @staticmethod
    def parse_version(version_string):
        """Parse version string into comparable tuple"""
        if not version_string:
            return (0, 0, 0)
        
        # Remove 'v' prefix if present
        version_string = version_string.lstrip('v').strip()
        
        # Handle different version formats
        # Examples: "1.2.3", "1.2", "1.2.3-beta", "1.2.3.4"
        try:
            # Split on dots and take first 3 parts
            parts = version_string.split('.')
            major = int(parts[0]) if len(parts) > 0 else 0
            minor = int(parts[1]) if len(parts) > 1 else 0
            
            # Handle patch version with possible suffixes
            patch = 0
            if len(parts) > 2:
                patch_str = parts[2].split('-')[0]  # Remove suffixes like -beta
                patch = int(patch_str) if patch_str.isdigit() else 0
            
            return (major, minor, patch)
            
        except (ValueError, IndexError):
            # Fallback for unparseable versions
            return (0, 0, 0)
    
    @staticmethod
    def is_newer_version(current, new):
        """Check if new version is newer than current"""
        current_tuple = VersionManager.parse_version(current)
        new_tuple = VersionManager.parse_version(new)
        return new_tuple > current_tuple
    
    @staticmethod
    def extract_version_from_file(file_path):
        """Extract version from Python file"""
        try:
            with open(file_path, 'r') as f:
                content = f.read(2048)  # Read first 2KB to find version
            
            # Look for common version patterns
            patterns = [
                r'__version__\s*=\s*["\']([^"\']+)["\']',
                r'VERSION\s*=\s*["\']([^"\']+)["\']',
                r'version\s*=\s*["\']([^"\']+)["\']',
                r'# Version:\s*([^\n]+)',
                r'# V\s*([^\n]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def extract_version_from_content(content):
        """Extract version from file content"""
        try:
            # Look for common version patterns
            patterns = [
                r'__version__\s*=\s*["\']([^"\']+)["\']',
                r'VERSION\s*=\s*["\']([^"\']+)["\']',
                r'version\s*=\s*["\']([^"\']+)["\']',
                r'# Version:\s*([^\n]+)',
                r'# V\s*([^\n]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            
            return None
            
        except Exception:
            return None

class StageTwo_OTA:
    """StageTwo Over-The-Air update system"""
    
    def __init__(self):
        self.session = None
        self.pool = None
        self.status_callback = None
        self.update_log = []
        self.stats = {
            "libraries_updated": 0,
            "applications_updated": 0,
            "files_skipped": 0,
            "errors": 0
        }
        
    def set_status_callback(self, callback):
        """Set callback function for status updates"""
        self.status_callback = callback
        
    def _update_status(self, message, progress=None):
        """Update status with optional progress"""
        timestamp = time.monotonic()
        log_entry = f"[{timestamp:.1f}] {message}"
        print(f"OTA: {message}")
        self.update_log.append(log_entry)
        
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
                raise OTAError("WiFi credentials not configured in settings.toml")
            
            self._update_status(f"Connecting to WiFi: {wifi_ssid}")
            
            try:
                wifi.radio.connect(wifi_ssid, wifi_password, timeout=20)
            except Exception as e:
                raise OTAError(f"WiFi connection failed: {e}")
        
        if not wifi.radio.connected:
            raise OTAError("WiFi connection failed")
        
        self._update_status(f"WiFi connected: {wifi.radio.ipv4_address}")
        
        # Initialize HTTP session
        if not self.pool:
            self.pool = socketpool.SocketPool(wifi.radio)
        if not self.session:
            self.session = adafruit_requests.Session(self.pool)
    
    def _download_zipper_if_needed(self):
        """Download zipper library if not available"""
        global ZIPPER_AVAILABLE, zipper
        
        if ZIPPER_AVAILABLE:
            return True
        
        self._update_status("Downloading zipper library...")
        
        try:
            response = self.session.get(ZIPPER_URL, timeout=30)
            
            if response.status_code != 200:
                raise OTAError(f"HTTP {response.status_code}: Failed to download zipper library")
            
            zipper_content = response.text
            response.close()
            
            # Validate content
            if "def zip_files" not in zipper_content or "def unzip" not in zipper_content:
                raise OTAError("Downloaded zipper library appears to be invalid")
            
            # Write zipper.py
            with open("/zipper.py", "w") as f:
                f.write(zipper_content)
            
            # Import the downloaded module
            try:
                import sys
                if 'zipper' in sys.modules:
                    del sys.modules['zipper']
                
                import zipper
                ZIPPER_AVAILABLE = True
                
                self._update_status("Zipper library downloaded and imported successfully")
                return True
                
            except ImportError as e:
                raise OTAError(f"Failed to import downloaded zipper library: {e}")
            
        except Exception as e:
            try:
                os.remove("/zipper.py")
            except:
                pass
            raise OTAError(f"Zipper download failed: {e}")
    
    def _prepare_directories(self):
        """Prepare necessary directories"""
        self._update_status("Preparing directories...")
        
        # Ensure storage is writable
        try:
            storage.remount("/", readonly=False)
        except Exception as e:
            self._update_status(f"Warning: Could not remount storage: {e}")
        
        # Create directories
        directories = [TEMP_DIR, OTA_DIR, BACKUP_DIR, "/lib"]
        
        for directory in directories:
            try:
                os.mkdir(directory)
                self._update_status(f"Created directory: {directory}")
            except OSError:
                pass  # Directory already exists
    
    def _download_file(self, url, local_path, description="file"):
        """Download a file with progress tracking"""
        self._update_status(f"Downloading {description}...")
        
        try:
            response = self.session.get(url, stream=True, timeout=60)
            
            if response.status_code != 200:
                raise OTAError(f"HTTP {response.status_code}: Failed to download {description}")
            
            # Get content length if available
            try:
                total_size = int(response.headers.get('content-length', 0))
                self._update_status(f"Download size: {total_size} bytes")
            except:
                total_size = 0
                self._update_status("Download size: Unknown")
            
            # Download with progress tracking
            downloaded_size = 0
            
            with open(local_path, "wb") as f:
                while True:
                    chunk = response.raw.read(1024)
                    if not chunk:
                        break
                    
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Update progress
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        self._update_status(f"Downloading {description}: {progress:.1f}%", progress)
                    else:
                        self._update_status(f"Downloaded: {downloaded_size} bytes")
                    
                    # Garbage collection
                    if downloaded_size % 10240 == 0:  # Every 10KB
                        gc.collect()
            
            response.close()
            
            # Verify download
            file_stat = os.stat(local_path)
            actual_size = file_stat[6]
            
            if actual_size == 0:
                raise OTAError(f"Downloaded {description} is empty")
            
            self._update_status(f"Download complete: {actual_size} bytes")
            return True
            
        except Exception as e:
            # Clean up partial download
            try:
                os.remove(local_path)
            except:
                pass
            raise OTAError(f"Download failed for {description}: {e}")
    
    def _extract_and_process_zip(self, zip_path, target_dir, update_type="files"):
        """Extract ZIP and process files with version checking"""
        if not ZIPPER_AVAILABLE:
            raise OTAError("Zipper library not available for extraction")
        
        self._update_status(f"Processing {update_type} from ZIP...")
        
        try:
            # Create temporary extraction directory
            extract_temp = f"{OTA_DIR}/extract_{update_type}"
            try:
                os.mkdir(extract_temp)
            except OSError:
                pass
            
            # Extract to temporary directory first
            zipper.unzip(zip_path, extract_temp)
            self._update_status(f"Extracted {update_type} to temporary directory")
            
            # Process extracted files
            processed_count = 0
            skipped_count = 0
            error_count = 0
            
            for root, dirs, files in self._walk_directory(extract_temp):
                for file in files:
                    if file.startswith('.'):
                        continue  # Skip hidden files
                    
                    source_path = f"{root}/{file}"
                    
                    # Calculate relative path from extract directory
                    rel_path = source_path[len(extract_temp):].lstrip('/')
                    target_path = f"{target_dir}/{rel_path}"
                    
                    try:
                        if self._should_update_file(source_path, target_path):
                            # Create target directory if needed
                            target_parent = '/'.join(target_path.split('/')[:-1])
                            if target_parent and target_parent != target_dir.rstrip('/'):
                                self._ensure_directory_exists(target_parent)
                            
                            # Backup existing file if it exists
                            if self._file_exists(target_path):
                                backup_path = f"{BACKUP_DIR}/{rel_path}.bak"
                                backup_parent = '/'.join(backup_path.split('/')[:-1])
                                self._ensure_directory_exists(backup_parent)
                                self._copy_file(target_path, backup_path)
                            
                            # Copy new file
                            self._copy_file(source_path, target_path)
                            processed_count += 1
                            
                            self._update_status(f"Updated: {rel_path}")
                            
                            if update_type == "libraries":
                                self.stats["libraries_updated"] += 1
                            else:
                                self.stats["applications_updated"] += 1
                        else:
                            skipped_count += 1
                            self.stats["files_skipped"] += 1
                            self._update_status(f"Skipped (same/older version): {rel_path}")
                    
                    except Exception as e:
                        error_count += 1
                        self.stats["errors"] += 1
                        self._update_status(f"Error processing {rel_path}: {e}")
            
            self._update_status(f"Processing complete: {processed_count} updated, {skipped_count} skipped, {error_count} errors")
            
            # Cleanup temporary extraction directory
            self._remove_directory_recursive(extract_temp)
            
            return processed_count > 0
            
        except Exception as e:
            raise OTAError(f"ZIP processing failed for {update_type}: {e}")
    
    def _walk_directory(self, path):
        """Walk directory tree (simple implementation for CircuitPython)"""
        try:
            items = os.listdir(path)
            files = []
            dirs = []
            
            for item in items:
                item_path = f"{path}/{item}"
                try:
                    # Try to list directory to see if it's a directory
                    os.listdir(item_path)
                    dirs.append(item)
                except OSError:
                    # Not a directory, must be a file
                    files.append(item)
            
            # Yield current directory
            yield path, dirs, files
            
            # Recursively walk subdirectories
            for dir_name in dirs:
                dir_path = f"{path}/{dir_name}"
                for result in self._walk_directory(dir_path):
                    yield result
                    
        except Exception as e:
            self._update_status(f"Error walking directory {path}: {e}")
    
    def _should_update_file(self, source_path, target_path):
        """Determine if file should be updated based on version"""
        try:
            # If target doesn't exist, always update
            if not self._file_exists(target_path):
                return True
            
            # Read source content to get version
            with open(source_path, 'r') as f:
                source_content = f.read()
            
            source_version = VersionManager.extract_version_from_content(source_content)
            target_version = VersionManager.extract_version_from_file(target_path)
            
            # If we can't determine versions, update anyway (safer)
            if not source_version and not target_version:
                return True
            
            # If only source has version, update
            if source_version and not target_version:
                return True
            
            # If only target has version, don't update (preserve existing)
            if not source_version and target_version:
                return False
            
            # Compare versions
            if VersionManager.is_newer_version(target_version, source_version):
                self._update_status(f"Version check: {source_version} > {target_version}")
                return True
            else:
                self._update_status(f"Version check: {source_version} <= {target_version} (skipping)")
                return False
                
        except Exception as e:
            self._update_status(f"Version check error for {target_path}: {e}")
            # On error, default to updating
            return True
    
    def _file_exists(self, path):
        """Check if file exists"""
        try:
            os.stat(path)
            return True
        except OSError:
            return False
    
    def _ensure_directory_exists(self, path):
        """Ensure directory exists, creating if necessary"""
        if not path or path == '/':
            return
        
        try:
            os.listdir(path)
        except OSError:
            # Directory doesn't exist, create it
            parent = '/'.join(path.split('/')[:-1])
            if parent and parent != '/':
                self._ensure_directory_exists(parent)
            
            try:
                os.mkdir(path)
            except OSError:
                pass  # May have been created by another process
    
    def _copy_file(self, source, destination):
        """Copy file from source to destination"""
        with open(source, 'rb') as src:
            with open(destination, 'wb') as dst:
                while True:
                    chunk = src.read(1024)
                    if not chunk:
                        break
                    dst.write(chunk)
                    gc.collect()  # Prevent memory issues
    
    def _remove_directory_recursive(self, path):
        """Remove directory and all contents"""
        try:
            for root, dirs, files in self._walk_directory(path):
                # Remove files first
                for file in files:
                    try:
                        os.remove(f"{root}/{file}")
                    except:
                        pass
            
            # Remove directories (deepest first)
            all_dirs = []
            for root, dirs, files in self._walk_directory(path):
                all_dirs.extend([f"{root}/{d}" for d in dirs])
            
            # Sort by depth (deepest first)
            all_dirs.sort(key=lambda x: x.count('/'), reverse=True)
            
            for dir_path in all_dirs:
                try:
                    os.rmdir(dir_path)
                except:
                    pass
            
            # Finally remove the root directory
            try:
                os.rmdir(path)
            except:
                pass
                
        except Exception as e:
            self._update_status(f"Error removing directory {path}: {e}")
    
    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        self._update_status("Cleaning up temporary files...")
        
        temp_files = [
            f"{OTA_DIR}/core_lib.zip",
            f"{OTA_DIR}/core_applications.zip"
        ]
        
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
                self._update_status(f"Removed: {temp_file}")
            except:
                pass
    
    def _generate_update_report(self):
        """Generate update report"""
        report = "\n" + "=" * 50
        report += "\nStageTwo OTA Update Report"
        report += "\n" + "=" * 50
        report += f"\nLibraries updated: {self.stats['libraries_updated']}"
        report += f"\nApplications updated: {self.stats['applications_updated']}"
        report += f"\nFiles skipped: {self.stats['files_skipped']}"
        report += f"\nErrors encountered: {self.stats['errors']}"
        report += "\n" + "=" * 50
        
        if self.update_log:
            report += "\nDetailed Log:"
            report += "\n" + "-" * 30
            for entry in self.update_log[-20:]:  # Last 20 entries
                report += f"\n{entry}"
        
        report += "\n" + "=" * 50
        return report
    
    def run_ota_update(self, update_libraries=True, update_applications=True):
        """Run the complete OTA update process"""
        start_time = time.monotonic()
        
        try:
            self._update_status("=== StageTwo OTA Update Started ===")
            self._update_status(f"Version: {__version__}")
            
            # Step 1: Ensure WiFi connection
            self._ensure_wifi_connected()
            
            # Step 2: Download zipper if needed
            if not ZIPPER_AVAILABLE:
                self._download_zipper_if_needed()
            
            # Step 3: Prepare directories
            self._prepare_directories()
            
            # Step 4: Update libraries
            if update_libraries:
                self._update_status("Starting library updates...")
                lib_zip_path = f"{OTA_DIR}/core_lib.zip"
                
                try:
                    self._download_file(CORE_LIB_URL, lib_zip_path, "core libraries")
                    self._extract_and_process_zip(lib_zip_path, "/lib", "libraries")
                    self._update_status("Library updates completed")
                except Exception as e:
                    self._update_status(f"Library update failed: {e}")
                    self.stats["errors"] += 1
            
            # Step 5: Update applications
            if update_applications:
                self._update_status("Starting application updates...")
                app_zip_path = f"{OTA_DIR}/core_applications.zip"
                
                try:
                    self._download_file(CORE_APPLICATIONS_URL, app_zip_path, "core applications")
                    self._extract_and_process_zip(app_zip_path, "/", "applications")
                    self._update_status("Application updates completed")
                except Exception as e:
                    self._update_status(f"Application update failed: {e}")
                    self.stats["errors"] += 1
            
            # Step 6: Cleanup
            self._cleanup_temp_files()
            
            # Step 7: Generate report
            elapsed_time = time.monotonic() - start_time
            self._update_status(f"=== OTA Update Complete ({elapsed_time:.1f}s) ===")
            
            report = self._generate_update_report()
            print(report)
            
            # Save report to file
            try:
                with open("/temp/ota_report.txt", "w") as f:
                    f.write(report)
                self._update_status("Update report saved to /temp/ota_report.txt")
            except:
                pass
            
            return True
            
        except OTAError as e:
            self._update_status(f"OTA UPDATE FAILED: {e}")
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

def check_for_updates():
    """Check if updates are available without downloading"""
    print("🔍 Checking for available updates...")
    
    try:
        # This is a simplified check - in a full implementation,
        # you might check version manifests or timestamps
        
        if not wifi.radio.connected:
            print("❌ WiFi not connected")
            return False
        
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool)
        
        # Check if update files exist
        updates_available = {"libraries": False, "applications": False}
        
        # Check libraries
        try:
            response = session.head(CORE_LIB_URL, timeout=10)
            if response.status_code == 200:
                updates_available["libraries"] = True
                print("✅ Library updates available")
            response.close()
        except:
            print("❌ Could not check library updates")
        
        # Check applications
        try:
            response = session.head(CORE_APPLICATIONS_URL, timeout=10)
            if response.status_code == 200:
                updates_available["applications"] = True
                print("✅ Application updates available")
            response.close()
        except:
            print("❌ Could not check application updates")
        
        session.close()
        
        return updates_available
        
    except Exception as e:
        print(f"❌ Update check failed: {e}")
        return False

def quick_update():
    """Quick update function for integration"""
    try:
        ota = StageTwo_OTA()
        return ota.run_ota_update()
    except Exception as e:
        print(f"Quick update failed: {e}")
        return False

def update_libraries_only():
    """Update only libraries"""
    try:
        ota = StageTwo_OTA()
        return ota.run_ota_update(update_libraries=True, update_applications=False)
    except Exception as e:
        print(f"Library update failed: {e}")
        return False

def update_applications_only():
    """Update only applications"""
    try:
        ota = StageTwo_OTA()
        return ota.run_ota_update(update_libraries=False, update_applications=True)
    except Exception as e:
        print(f"Application update failed: {e}")
        return False

def update_with_callback(status_callback):
    """Update with status callback for GUI integration"""
    try:
        ota = StageTwo_OTA()
        ota.set_status_callback(status_callback)
        return ota.run_ota_update()
    except Exception as e:
        print(f"Update with callback failed: {e}")
        if status_callback:
            status_callback(f"Update failed: {e}", 0)
        return False

def rollback_updates():
    """Rollback updates from backup"""
    print("🔄 Rolling back updates from backup...")
    
    try:
        if not os.path.exists(BACKUP_DIR):
            print("❌ No backup directory found")
            return False
        
        rollback_count = 0
        
        for root, dirs, files in os.walk(BACKUP_DIR):
            for file in files:
                if file.endswith('.bak'):
                    backup_path = f"{root}/{file}"
                    
                    # Calculate original path
                    rel_path = backup_path[len(BACKUP_DIR):].lstrip('/')
                    original_path = f"/{rel_path[:-4]}"  # Remove .bak extension
                    
                    try:
                        # Restore from backup
                        with open(backup_path, 'rb') as src:
                            with open(original_path, 'wb') as dst:
                                while True:
                                    chunk = src.read(1024)
                                    if not chunk:
                                        break
                                    dst.write(chunk)
                        
                        rollback_count += 1
                        print(f"✅ Restored: {original_path}")
                        
                    except Exception as e:
                        print(f"❌ Failed to restore {original_path}: {e}")
        
        print(f"🔄 Rollback complete: {rollback_count} files restored")
        return rollback_count > 0
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False

def get_update_status():
    """Get current update system status"""
    status = {
        "version": __version__,
        "zipper_available": ZIPPER_AVAILABLE,
        "wifi_connected": False,
        "memory_free": 0,
        "temp_dir_exists": False,
        "backup_dir_exists": False,
        "last_update": None
    }
    
    try:
        # Check WiFi
        status["wifi_connected"] = wifi.radio.connected
        
        # Check memory
        status["memory_free"] = gc.mem_free()
        
        # Check directories
        status["temp_dir_exists"] = os.path.exists(TEMP_DIR)
        status["backup_dir_exists"] = os.path.exists(BACKUP_DIR)
        
        # Check for last update report
        try:
            with open("/temp/ota_report.txt", "r") as f:
                report_content = f.read()
                # Extract timestamp or other info from report
                status["last_update"] = "Report available"
        except:
            status["last_update"] = "No previous updates"
        
    except Exception as e:
        status["error"] = str(e)
    
    return status

def clean_update_cache():
    """Clean update cache and temporary files"""
    print("🧹 Cleaning update cache...")
    
    try:
        cleaned_count = 0
        
        # Remove OTA directory
        if os.path.exists(OTA_DIR):
            for root, dirs, files in os.walk(OTA_DIR):
                for file in files:
                    try:
                        os.remove(f"{root}/{file}")
                        cleaned_count += 1
                    except:
                        pass
            
            # Remove directories
            try:
                os.rmdir(OTA_DIR)
            except:
                pass
        
        # Clean old backup files (keep only recent ones)
        # Clean old backup files (keep only recent ones)
        if os.path.exists(BACKUP_DIR):
            try:
                backup_files = os.listdir(BACKUP_DIR)
                # Keep only the most recent 10 backup files
                if len(backup_files) > 10:
                    # Sort by modification time (approximate)
                    backup_files.sort()
                    files_to_remove = backup_files[:-10]  # Remove all but last 10
                    
                    for file in files_to_remove:
                        try:
                            os.remove(f"{BACKUP_DIR}/{file}")
                            cleaned_count += 1
                        except:
                            pass
            except:
                pass
        
        print(f"🧹 Cache cleanup complete: {cleaned_count} files removed")
        return True
        
    except Exception as e:
        print(f"❌ Cache cleanup failed: {e}")
        return False

def verify_installation():
    """Verify installation integrity after update"""
    print("🔍 Verifying installation integrity...")
    
    try:
        issues = []
        
        # Check critical library files
        critical_libs = [
            "/lib/adafruit_display_text",
            "/lib/adafruit_requests.py",
            "/lib/adafruit_connection_manager.py"
        ]
        
        for lib_path in critical_libs:
            try:
                if lib_path.endswith('.py'):
                    os.stat(lib_path)
                else:
                    os.listdir(lib_path)
                print(f"✅ {lib_path}")
            except OSError:
                issues.append(f"Missing: {lib_path}")
                print(f"❌ {lib_path}")
        
        # Check critical application files
        critical_apps = [
            "/boot.py",
            "/code.py",
            "/recovery.py"
        ]
        
        for app_path in critical_apps:
            try:
                stat_result = os.stat(app_path)
                if stat_result[6] == 0:  # File size is 0
                    issues.append(f"Empty file: {app_path}")
                    print(f"⚠️ {app_path} (empty)")
                else:
                    print(f"✅ {app_path} ({stat_result[6]} bytes)")
            except OSError:
                issues.append(f"Missing: {app_path}")
                print(f"❌ {app_path}")
        
        if issues:
            print(f"\n⚠️ Verification found {len(issues)} issues:")
            for issue in issues:
                print(f"   • {issue}")
            return False
        else:
            print("\n✅ Installation verification passed")
            return True
            
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

def create_version_manifest():
    """Create a manifest of current file versions"""
    print("📋 Creating version manifest...")
    
    try:
        manifest = {
            "created": time.monotonic(),
            "system_version": __version__,
            "files": {}
        }
        
        # Scan important directories
        scan_dirs = ["/", "/lib", "/system", "/apps"]
        
        for scan_dir in scan_dirs:
            try:
                if not os.path.exists(scan_dir):
                    continue
                
                for root, dirs, files in os.walk(scan_dir):
                    for file in files:
                        if file.endswith('.py') or file.endswith('.toml'):
                            file_path = f"{root}/{file}"
                            
                            try:
                                # Get file info
                                stat_result = os.stat(file_path)
                                file_size = stat_result[6]
                                
                                # Extract version if possible
                                version = VersionManager.extract_version_from_file(file_path)
                                
                                manifest["files"][file_path] = {
                                    "size": file_size,
                                    "version": version
                                }
                                
                            except Exception:
                                continue
            except Exception:
                continue
        
        # Save manifest
        manifest_path = "/temp/version_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        
        print(f"📋 Version manifest created: {len(manifest['files'])} files tracked")
        print(f"💾 Saved to: {manifest_path}")
        return True
        
    except Exception as e:
        print(f"❌ Manifest creation failed: {e}")
        return False

def compare_versions():
    """Compare current versions with manifest"""
    print("🔍 Comparing current versions with manifest...")
    
    try:
        # Load manifest
        with open("/temp/version_manifest.json", "r") as f:
            manifest = json.load(f)
        
        changes = []
        
        for file_path, file_info in manifest["files"].items():
            try:
                # Check if file still exists
                if not os.path.exists(file_path):
                    changes.append(f"DELETED: {file_path}")
                    continue
                
                # Check size
                current_stat = os.stat(file_path)
                current_size = current_stat[6]
                
                if current_size != file_info["size"]:
                    changes.append(f"SIZE CHANGED: {file_path} ({file_info['size']} -> {current_size})")
                
                # Check version
                current_version = VersionManager.extract_version_from_file(file_path)
                manifest_version = file_info.get("version")
                
                if current_version != manifest_version:
                    changes.append(f"VERSION CHANGED: {file_path} ({manifest_version} -> {current_version})")
                
            except Exception:
                changes.append(f"ERROR CHECKING: {file_path}")
        
        if changes:
            print(f"\n📋 Found {len(changes)} changes:")
            for change in changes[:20]:  # Show first 20
                print(f"   • {change}")
            if len(changes) > 20:
                print(f"   ... and {len(changes) - 20} more")
        else:
            print("✅ No changes detected since last manifest")
        
        return len(changes)
        
    except Exception as e:
        print(f"❌ Version comparison failed: {e}")
        return -1

def main():
    """Main entry point for OTA system"""
    print("=" * 60)
    print("🚀 StageTwo OTA Update System")
    print(f"📋 Version: {__version__}")
    print("=" * 60)
    
    try:
        # Check prerequisites
        print("\n🔍 Checking prerequisites...")
        
        # Check WiFi
        if not wifi.radio.connected:
            print("❌ WiFi not connected")
            print("   Configure WiFi in settings.toml and connect first")
            return False
        
        print("✅ WiFi connected")
        
        # Check memory
        free_mem = gc.mem_free()
        print(f"💾 Available memory: {free_mem} bytes")
        
        if free_mem < 50000:
            print("⚠️ Low memory - running garbage collection...")
            gc.collect()
            free_mem = gc.mem_free()
            print(f"💾 Memory after cleanup: {free_mem} bytes")
        
        # Check zipper
        if not ZIPPER_AVAILABLE:
            print("⚠️ Zipper library not available - will auto-download")
        else:
            print("✅ Zipper library available")
        
        # Create version manifest before update
        print("\n📋 Creating pre-update version manifest...")
        create_version_manifest()
        
        # Run OTA update
        print("\n🚀 Starting OTA update process...")
        ota = StageTwo_OTA()
        success = ota.run_ota_update()
        
        if success:
            print("\n✅ OTA update completed successfully!")
            
            # Verify installation
            print("\n🔍 Verifying installation...")
            if verify_installation():
                print("✅ Installation verification passed")
            else:
                print("⚠️ Installation verification found issues")
            
            # Compare versions
            print("\n📊 Analyzing changes...")
            changes = compare_versions()
            if changes > 0:
                print(f"📈 {changes} files were updated")
            
            print("\n🔄 Reboot recommended to apply all changes")
            print("💡 Use microcontroller.reset() or supervisor.reload()")
            
            return True
        else:
            print("\n❌ OTA update failed!")
            print("📋 Check the update report for details")
            print("🔄 Use rollback_updates() if needed")
            return False
            
    except Exception as e:
        print(f"\n💥 Fatal error in OTA system: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        return False
    
    finally:
        # Final cleanup
        gc.collect()
        print(f"\n💾 Final memory: {gc.mem_free()} bytes free")

def interactive_update():
    """Interactive update with user choices"""
    print("🎯 StageTwo Interactive Update")
    print("=" * 30)
    
    try:
        # Check what's available
        print("🔍 Checking for available updates...")
        available = check_for_updates()
        
        if not available:
            print("❌ Could not check for updates")
            return False
        
        # Show options
        print("\nUpdate Options:")
        if available.get("libraries"):
            print("1. Update Libraries (/lib)")
        if available.get("applications"):
            print("2. Update Applications (/)")
        print("3. Update Both")
        print("4. Check Status Only")
        print("5. Rollback Previous Update")
        print("6. Clean Cache")
        print("7. Exit")
        
        # In a real interactive system, you'd get user input here
        # For now, we'll default to updating both
        choice = "3"
        
        if choice == "1":
            return update_libraries_only()
        elif choice == "2":
            return update_applications_only()
        elif choice == "3":
            return quick_update()
        elif choice == "4":
            status = get_update_status()
            print("\nSystem Status:")
            for key, value in status.items():
                print(f"  {key}: {value}")
            return True
        elif choice == "5":
            return rollback_updates()
        elif choice == "6":
            return clean_update_cache()
        elif choice == "7":
            print("Update cancelled")
            return True
        else:
            print("Invalid choice")
            return False
            
    except Exception as e:
        print(f"Interactive update failed: {e}")
        return False

def schedule_update():
    """Schedule an update for later (placeholder for future implementation)"""
    print("📅 Update scheduling not yet implemented")
    print("💡 For now, run updates manually when convenient")
    return False

def get_integration_info():
    """Get integration information for recovery.py and other systems"""
    return {
        "module_name": "stagetwo_ota",
        "version": __version__,
        "functions": {
            "main": "Full OTA update with user interaction",
            "quick_update": "Simple update for integration",
            "update_libraries_only": "Update only library files",
            "update_applications_only": "Update only application files",
            "check_for_updates": "Check if updates are available",
            "rollback_updates": "Rollback to previous versions"
        },
        "features": {
            "version_checking": True,
            "automatic_backup": True,
            "rollback_support": True,
            "progress_callbacks": True,
            "zipper_auto_download": True
        },
        "target_directories": {
            "libraries": "/lib",
            "applications": "/"
        },
        "update_sources": {
            "libraries": CORE_LIB_URL,
            "applications": CORE_APPLICATIONS_URL
        }
    }

# Export main functions
__all__ = [
    'StageTwo_OTA',
    'VersionManager',
    'main',
    'quick_update',
    'update_libraries_only',
    'update_applications_only',
    'update_with_callback',
    'check_for_updates',
    'rollback_updates',
    'get_update_status',
    'clean_update_cache',
    'verify_installation',
    'create_version_manifest',
    'compare_versions',
    'interactive_update',
    'get_integration_info'
]

# Auto-execution check
if __name__ == "__main__":
    # Direct execution
    success = main()
    exit(0 if success else 1)
else:
    # Module import
    print(f"📦 StageTwo OTA System V{__version__} loaded")
    print("🚀 Use main() for full OTA update")
    print("⚡ Use quick_update() for simple update")
    print("📚 Use update_libraries_only() for library updates")
    print("🎯 Use update_applications_only() for app updates")
    print("🔍 Use check_for_updates() to check availability")
    
    # Auto-setup zipper if needed
    if not ZIPPER_AVAILABLE:
        print("🔧 Zipper library will be auto-downloaded when needed")
    
    # Show current status
    try:
        status = get_update_status()
        if status.get("wifi_connected"):
            print("✅ WiFi connected - ready for updates")
        else:
            print("⚠️ WiFi not connected - connect before updating")
        
        print(f"💾 Memory available: {status.get('memory_free', 0)} bytes")
        
    except Exception:
        print("⚠️ Status check failed - system may need attention")

# Usage examples
USAGE_EXAMPLES = """
Usage Examples:

1. Full OTA update:
   python stagetwo_ota.py
   
2. From another module:
   import stagetwo_ota
   stagetwo_ota.main()

3. Quick update (libraries + applications):
   import stagetwo_ota
   success = stagetwo_ota.quick_update()

4. Update only libraries:
   import stagetwo_ota
   success = stagetwo_ota.update_libraries_only()

5. Update only applications:
   import stagetwo_ota
   success = stagetwo_ota.update_applications_only()

6. Check for updates without downloading:
   import stagetwo_ota
   available = stagetwo_ota.check_for_updates()

7. Update with progress callback:
   def progress_callback(message, progress):
       print(f"Progress: {message} ({progress}%)")
   
   import stagetwo_ota
   success = stagetwo_ota.update_with_callback(progress_callback)

8. Rollback updates:
   import stagetwo_ota
   success = stagetwo_ota.rollback_updates()

9. Verify installation:
   import stagetwo_ota
   ok = stagetwo_ota.verify_installation()

10. Clean update cache:
    import stagetwo_ota
    stagetwo_ota.clean_update_cache()
"""

def show_usage():
    """Show usage examples"""
    print(USAGE_EXAMPLES)

# Integration with recovery.py
def integrate_with_recovery():
    """Integration point for recovery.py"""
    prerequisites = []
    
    # Check WiFi
    try:
        if not wifi.radio.connected:
            prerequisites.append("WiFi not connected")
    except:
        prerequisites.append("WiFi module error")
    
    # Check memory
    try:
        free_mem = gc.mem_free()
        if free_mem < 30000:
            prerequisites.append(f"Low memory: {free_mem} bytes")
    except:
        prerequisites.append("Memory check failed")
    
    return {
        "name": "OTA Updates",
        "description": "Download and install library and application updates",
        "function": quick_update,
        "prerequisites": prerequisites,
        "available": len(prerequisites) == 0,
        "version_checking": True,
        "backup_support": True
    }

# Advanced features
def create_update_package(source_dir, package_name, target_zip):
    """Create an update package from a directory"""
    print(f"📦 Creating update package: {package_name}")
    
    if not ZIPPER_AVAILABLE:
        print("❌ Zipper library required for package creation")
        return False
    
    try:
        # Collect files to package
        files_to_zip = []
        
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if not file.startswith('.'):
                    file_path = f"{root}/{file}"
                    files_to_zip.append(file_path)
        
        if not files_to_zip:
            print("❌ No files found to package")
            return False
        
        # Create ZIP package
        zipper.zip_files(target_zip, files_to_zip)
        
        # Verify package
        zip_stat = os.stat(target_zip)
        print(f"✅ Package created: {target_zip} ({zip_stat[6]} bytes)")
        print(f"📁 Contains {len(files_to_zip)} files")
        
        return True
        
    except Exception as e:
        print(f"❌ Package creation failed: {e}")
        return False

def install_custom_package(package_path, target_dir="/"):
    """Install a custom update package"""
    print(f"📦 Installing custom package: {package_path}")
    
    if not ZIPPER_AVAILABLE:
        print("❌ Zipper library required for package installation")
        return False
    
    try:
        # Verify package exists
        if not os.path.exists(package_path):
            print(f"❌ Package not found: {package_path}")
            return False
        
        # Create OTA instance for processing
        ota = StageTwo_OTA()
        ota._prepare_directories()
        
        # Process the package
        success = ota._extract_and_process_zip(package_path, target_dir, "custom package")
        
        if success:
            print("✅ Custom package installed successfully")
            return True
        else:
            print("❌ Custom package installation failed")
            return False
            
    except Exception as e:
        print(f"❌ Custom package installation failed: {e}")
        return False

def export_current_system():
    """Export current system as update packages"""
    print("📤 Exporting current system...")
    
    try:
        # Ensure directories exist
        try:
            os.mkdir("/exports")
        except:
            pass
        
        # Export libraries
        if os.path.exists("/lib"):
            lib_success = create_update_package("/lib", "libraries", "/exports/exported_lib.zip")
            if lib_success:
                print("✅ Libraries exported to /exports/exported_lib.zip")
        
        # Export applications (selective)
        app_files = []
        important_apps = ["boot.py", "code.py", "recovery.py", "settings.toml"]
        
        for app in important_apps:
            if os.path.exists(f"/{app}"):
                app_files.append(f"/{app}")
        
        # Add system directory if it exists
        if os.path.exists("/system"):
            for root, dirs, files in os.walk("/system"):
                for file in files:
                    app_files.append(f"{root}/{file}")
        
        if app_files and ZIPPER_AVAILABLE:
            try:
                zipper.zip_files("/exports/exported_apps.zip", app_files)
                print("✅ Applications exported to /exports/exported_apps.zip")
            except Exception as e:
                print(f"❌ Application export failed: {e}")
        
        print("📤 System export complete")
        return True
        
    except Exception as e:
        print(f"❌ System export failed: {e}")
        return False

def validate_update_urls():
    """Validate that update URLs are accessible"""
    print("🔗 Validating update URLs...")
    
    try:
        if not wifi.radio.connected:
            print("❌ WiFi not connected")
            return False
        
        pool = socketpool.SocketPool(wifi.radio)
        session = adafruit_requests.Session(pool)
        
        urls_to_check = [
            ("Core Libraries", CORE_LIB_URL),
            ("Core Applications", CORE_APPLICATIONS_URL),
            ("Zipper Library", ZIPPER_URL)
        ]
        
        results = {}
        
        for name, url in urls_to_check:
            try:
                print(f"🔍 Checking {name}...")
                response = session.head(url, timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ {name}: Available")
                    results[name] = True
                else:
                    print(f"❌ {name}: HTTP {response.status_code}")
                    results[name] = False
                
                response.close()
                
            except Exception as e:
                print(f"❌ {name}: {e}")
                results[name] = False
        
        session.close()
        
        # Summary
        available_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        print(f"\n📊 URL Validation Results: {available_count}/{total_count} available")
        
        return available_count == total_count
        
    except Exception as e:
        print(f"❌ URL validation failed: {e}")
        return False

def get_system_info():
    """Get comprehensive system information"""
    info = {
        "ota_version": __version__,
        "zipper_available": ZIPPER_AVAILABLE,
        "memory_free": gc.mem_free(),
        "wifi_connected": False,
        "update_urls": {
            "libraries": CORE_LIB_URL,
            "applications": CORE_APPLICATIONS_URL,
            "zipper": ZIPPER_URL
        },
        "directories": {
            "temp": TEMP_DIR,
            "ota": OTA_DIR,
            "backup": BACKUP_DIR
        },
        "features": {
            "version_checking": True,
            "automatic_backup": True,
            "rollback_support": True,
            "custom_packages": True,
            "system_export": True
        }
    }
    
    try:
        # WiFi status
        info["wifi_connected"] = wifi.radio.connected
        if wifi.radio.connected:
            info["wifi_ip"] = str(wifi.radio.ipv4_address)
        
        # Directory status
        info["directories"]["temp_exists"] = os.path.exists(TEMP_DIR)
        info["directories"]["ota_exists"] = os.path.exists(OTA_DIR)
        info["directories"]["backup_exists"] = os.path.exists(BACKUP_DIR)
        
        # Last update info
        try:
            with open("/temp/ota_report.txt", "r") as f:
                info["last_update_report"] = "Available"
        except:
            info["last_update_report"] = "None"
        
        # Version manifest
        try:
            with open("/temp/version_manifest.json", "r") as f:
                manifest = json.load(f)
                info["version_manifest"] = {
                    "exists": True,
                    "files_tracked": len(manifest.get("files", {})),
                    "created": manifest.get("created", 0)
                }
        except:
            info["version_manifest"] = {"exists": False}
        
    except Exception as e:
        info["error"] = str(e)
    
    return info

# Enhanced initialization
try:
    gc.collect()
    print(f"🎯 StageTwo OTA ready - {gc.mem_free()} bytes available")
    
    # Check system status
    if ZIPPER_AVAILABLE:
        print("📚 Zipper library: Ready")
    else:
        print("📚 Zipper library: Will auto-download")
    
    # Check WiFi
    try:
        if wifi.radio.connected:
            print(f"🌐 WiFi: Connected ({wifi.radio.ipv4_address})")
        else:
            print("🌐 WiFi: Not connected")
    except:
        print("🌐 WiFi: Status unknown")
    
    # Check directories
    dirs_exist = sum(1 for d in [TEMP_DIR, OTA_DIR, BACKUP_DIR] if os.path.exists(d))
    print(f"📁 Directories: {dirs_exist}/3 exist")
    
    print("✅ OTA system ready for updates")
    
except Exception as e:
    print(f"⚠️ OTA initialization warning: {e}")

# Final integration helpers
def get_menu_integration():
    """Get menu integration data for GUI systems"""
    return {
        "menu_items": [
            {
                "name": "Check for Updates",
                "function": check_for_updates,
                "description": "Check if updates are available"
            },
            {
                "name": "Update All",
                "function": quick_update,
                "description": "Update libraries and applications"
            },
            {
                "name": "Update Libraries Only",
                "function": update_libraries_only,
                "description": "Update only library files"
            },
            {
                "name": "Update Applications Only",
                "function": update_applications_only,
                "description": "Update only application files"
            },
            {
                "name": "Rollback Updates",
                "function": rollback_updates,
                "description": "Restore previous versions"
            },
            {
                "name": "System Status",
                "function": get_system_info,
                "description": "Show OTA system status"
            },
            {
                "name": "Clean Cache",
                "function": clean_update_cache,
                "description": "Clean temporary files"
            }
        ]
    }

print("🔗 Integration ready:")
print("  • get_integration_info() - Full integration data")
print("  • get_menu_integration() - Menu system integration")
print("  • integrate_with_recovery() - Recovery system integration")
print("  • show_usage() - Usage examples")

# End of StageTwo OTA system


