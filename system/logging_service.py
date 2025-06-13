"""
Advanced Logging Service for Medusa Bootloader V2.0
Provides comprehensive logging with multiple outputs and rotation
"""

import time
import os
import gc
import json
from micropython import const

# Log levels
LOG_LEVEL_DEBUG = const(0)
LOG_LEVEL_INFO = const(1)
LOG_LEVEL_WARN = const(2)
LOG_LEVEL_ERROR = const(3)
LOG_LEVEL_CRITICAL = const(4)

LOG_LEVEL_NAMES = {
    LOG_LEVEL_DEBUG: "DEBUG",
    LOG_LEVEL_INFO: "INFO",
    LOG_LEVEL_WARN: "WARN",
    LOG_LEVEL_ERROR: "ERROR",
    LOG_LEVEL_CRITICAL: "CRITICAL"
}

# Default settings
DEFAULT_LOG_LEVEL = LOG_LEVEL_INFO
DEFAULT_MAX_FILE_SIZE = 50000  # 50KB
DEFAULT_MAX_FILES = 5
DEFAULT_BUFFER_SIZE = 1024

class LogRotator:
    """Handles log file rotation"""
    
    def __init__(self, base_path, max_files=5):
        self.base_path = base_path
        self.max_files = max_files
    
    def rotate_logs(self):
        """Rotate log files when they get too large"""
        try:
            # Check if base log file exists and get its size
            try:
                stat = os.stat(self.base_path)
                if stat[6] < DEFAULT_MAX_FILE_SIZE:
                    return False  # No rotation needed
            except OSError:
                return False  # File doesn't exist
            
            print(f"Rotating logs: {self.base_path}")
            
            # Remove oldest log if we're at max files
            oldest_log = f"{self.base_path}.{self.max_files}"
            try:
                os.remove(oldest_log)
            except OSError:
                pass
            
            # Shift all log files
            for i in range(self.max_files - 1, 0, -1):
                old_name = f"{self.base_path}.{i}" if i > 1 else self.base_path
                new_name = f"{self.base_path}.{i + 1}"
                
                try:
                    os.rename(old_name, new_name)
                except OSError:
                    pass
            
            return True
            
        except Exception as e:
            print(f"Log rotation error: {e}")
            return False

class LogBuffer:
    """Memory buffer for log entries"""
    
    def __init__(self, max_size=DEFAULT_BUFFER_SIZE):
        self.max_size = max_size
        self.buffer = []
        self.total_size = 0
    
    def add(self, entry):
        """Add entry to buffer"""
        entry_size = len(entry)
        
        # Remove old entries if buffer is full
        while self.total_size + entry_size > self.max_size and self.buffer:
            removed = self.buffer.pop(0)
            self.total_size -= len(removed)
        
        self.buffer.append(entry)
        self.total_size += entry_size
    
    def get_all(self):
        """Get all buffered entries"""
        return self.buffer.copy()
    
    def clear(self):
        """Clear the buffer"""
        self.buffer.clear()
        self.total_size = 0
    
    def flush_to_file(self, file_path):
        """Flush buffer contents to file"""
        if not self.buffer:
            return True
        
        try:
            with open(file_path, "a") as f:
                for entry in self.buffer:
                    f.write(entry + "\n")
            
            self.clear()
            return True
            
        except Exception as e:
            print(f"Buffer flush error: {e}")
            return False

class Logger:
    """Main logging class"""
    
    def __init__(self, name="system", log_dir="/logs", level=DEFAULT_LOG_LEVEL):
        self.name = name
        self.log_dir = log_dir
        self.level = level
        self.initialized = False
        
        # Output options
        self.console_output = True
        self.file_output = True
        self.buffer_output = True
        
        # File handling
        self.log_file_path = None
        self.rotator = None
        
        # Memory buffer
        self.buffer = LogBuffer()
        
        # Statistics
        self.stats = {
            "entries_logged": 0,
            "errors": 0,
            "last_error": None,
            "start_time": time.monotonic()
        }
        
        # Try to initialize
        self._initialize()
    
    def _initialize(self):
        """Initialize the logger"""
        try:
            # Create log directory if it doesn't exist
            self._ensure_log_directory()
            
            # Set up log file path
            self.log_file_path = f"{self.log_dir}/{self.name}.log"
            
            # Set up log rotator
            self.rotator = LogRotator(self.log_file_path)
            
            # Test file writing
            if self.file_output:
                self._test_file_writing()
            
            self.initialized = True
            
            # Log initialization
            self._log_internal(LOG_LEVEL_INFO, "LOGGER", "Logging service initialized")
            self._log_internal(LOG_LEVEL_INFO, "LOGGER", f"Log level: {LOG_LEVEL_NAMES[self.level]}")
            self._log_internal(LOG_LEVEL_INFO, "LOGGER", f"Log directory: {self.log_dir}")
            
        except Exception as e:
            print(f"Logger initialization failed: {e}")
            self.initialized = False
            self.file_output = False  # Disable file output on init failure
    
    def _ensure_log_directory(self):
        """Ensure log directory exists"""
        try:
            # Check if directory exists
            os.listdir(self.log_dir)
        except OSError:
            # Directory doesn't exist, try to create it
            try:
                # Create parent directories if needed
                parts = self.log_dir.strip("/").split("/")
                current_path = ""
                
                for part in parts:
                    if part:
                        current_path += "/" + part
                        try:
                            os.listdir(current_path)
                        except OSError:
                            os.mkdir(current_path)
                
            except Exception as e:
                raise Exception(f"Cannot create log directory {self.log_dir}: {e}")
    
    def _test_file_writing(self):
        """Test if we can write to log files"""
        try:
            test_file = f"{self.log_dir}/test_write.tmp"
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            print(f"File writing test failed: {e}")
            self.file_output = False
    
    def _format_timestamp(self):
        """Format current timestamp"""
        try:
            current_time = time.localtime()
            return f"{current_time[0]:04d}-{current_time[1]:02d}-{current_time[2]:02d} " \
                   f"{current_time[3]:02d}:{current_time[4]:02d}:{current_time[5]:02d}"
        except:
            # Fallback to monotonic time if RTC not available
            return f"T+{time.monotonic():.1f}"
    
    def _format_entry(self, level, category, message):
        """Format a log entry"""
        timestamp = self._format_timestamp()
        level_name = LOG_LEVEL_NAMES.get(level, "UNKNOWN")
        return f"[{timestamp}] [{level_name}] {category}: {message}"
    
    def _log_internal(self, level, category, message):
        """Internal logging method"""
        if level < self.level:
            return  # Below log level threshold
        
        try:
            # Format the entry
            entry = self._format_entry(level, category, message)
            
            # Console output
            if self.console_output:
                print(entry)
            
            # Buffer output
            if self.buffer_output:
                self.buffer.add(entry)
            
            # File output
            if self.file_output and self.log_file_path:
                self._write_to_file(entry)
            
            # Update statistics
            self.stats["entries_logged"] += 1
            
            # Periodic maintenance
            if self.stats["entries_logged"] % 50 == 0:
                self._maintenance()
            
        except Exception as e:
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            print(f"Logging error: {e}")
    
    def _write_to_file(self, entry):
        """Write entry to log file"""
        try:
            # Check if rotation is needed
            if self.rotator:
                self.rotator.rotate_logs()
            
            # Write to file
            with open(self.log_file_path, "a") as f:
                f.write(entry + "\n")
            
        except Exception as e:
            print(f"File write error: {e}")
            self.file_output = False  # Disable file output on error
    
    def _maintenance(self):
        """Periodic maintenance tasks"""
        try:
            # Garbage collection
            gc.collect()
            
            # Flush buffer if it's getting large
            if self.buffer.total_size > DEFAULT_BUFFER_SIZE * 0.8:
                if self.file_output and self.log_file_path:
                    self.buffer.flush_to_file(self.log_file_path)
            
        except Exception as e:
            print(f"Maintenance error: {e}")
    
    # Public logging methods
    def debug(self, category, message):
        """Log debug message"""
        self._log_internal(LOG_LEVEL_DEBUG, category, message)
    
    def info(self, category, message):
        """Log info message"""
        self._log_internal(LOG_LEVEL_INFO, category, message)
    
    def warn(self, category, message):
        """Log warning message"""
        self._log_internal(LOG_LEVEL_WARN, category, message)
    
    def error(self, category, message):
        """Log error message"""
        self._log_internal(LOG_LEVEL_ERROR, category, message)
    
    def critical(self, category, message):
        """Log critical message"""
        self._log_internal(LOG_LEVEL_CRITICAL, category, message)
    
    def log(self, level, category, message):
        """Log message at specified level"""
        self._log_internal(level, category, message)
    
    # Configuration methods
    def set_level(self, level):
        """Set logging level"""
        self.level = level
        self.info("LOGGER", f"Log level changed to {LOG_LEVEL_NAMES[level]}")
    
    def set_console_output(self, enabled):
        """Enable/disable console output"""
        self.console_output = enabled
        self.info("LOGGER", f"Console output {'enabled' if enabled else 'disabled'}")
    
    def set_file_output(self, enabled):
        """Enable/disable file output"""
        if enabled and not self.file_output:
            self._test_file_writing()
        self.file_output = enabled
        self.info("LOGGER", f"File output {'enabled' if enabled else 'disabled'}")
    
    # Utility methods
    def get_stats(self):
        """Get logging statistics"""
        uptime = time.monotonic() - self.stats["start_time"]
        stats = self.stats.copy()
        stats["uptime"] = uptime
        stats["buffer_size"] = self.buffer.total_size
        stats["buffer_entries"] = len(self.buffer.buffer)
        return stats
    
    def get_recent_logs(self, count=20):
        """Get recent log entries from buffer"""
        entries = self.buffer.get_all()
        return entries[-count:] if len(entries) > count else entries
    
    def flush(self):
        """Flush all pending log entries"""
        if self.file_output and self.log_file_path:
            return self.buffer.flush_to_file(self.log_file_path)
        return True
    
    def cleanup(self):
        """Clean up logging resources"""
        try:
            self.flush()
            self.info("LOGGER", "Logging service shutting down")
        except:
            pass

# Global logger instance
_global_logger = None

def init_logging(log_dir="/logs", name="system", level=DEFAULT_LOG_LEVEL):
    """Initialize global logging service"""
    global _global_logger
    
    try:
        _global_logger = Logger(name, log_dir, level)
        return _global_logger
    except Exception as e:
        print(f"Failed to initialize logging: {e}")
        return None

def get_logger():
    """Get the global logger instance"""
    return _global_logger

# Convenience functions for global logger
def log_debug(category, message):
    """Log debug message to global logger"""
    if _global_logger:
        _global_logger.debug(category, message)
    else:
        print(f"[DEBUG] {category}: {message}")

def log_info(category, message):
    """Log info message to global logger"""
    if _global_logger:
        _global_logger.info(category, message)
    else:
        print(f"[INFO] {category}: {message}")

def log_warn(category, message):
    """Log warning message to global logger"""
    if _global_logger:
        _global_logger.warn(category, message)
    else:
        print(f"[WARN] {category}: {message}")

def log_error(category, message):
    """Log error message to global logger"""
    if _global_logger:
        _global_logger.error(category, message)
    else:
        print(f"[ERROR] {category}: {message}")

def log_critical(category, message):
    """Log critical message to global logger"""
    if _global_logger:
        _global_logger.critical(category, message)
    else:
        print(f"[CRITICAL] {category}: {message}")

def flush_logs():
    """Flush all pending logs"""
    if _global_logger:
        return _global_logger.flush()
    return True

def get_log_stats():
    """Get logging statistics"""
    if _global_logger:
        return _global_logger.get_stats()
    return {"error": "Logger not initialized"}

def get_recent_logs(count=20):
    """Get recent log entries"""
    if _global_logger:
        return _global_logger.get_recent_logs(count)
    return []

def cleanup_logging():
    """Clean up logging service"""
    global _global_logger
    if _global_logger:
        _global_logger.cleanup()
        _global_logger = None

# Configuration utilities
def set_log_level(level):
    """Set global log level"""
    if _global_logger:
        _global_logger.set_level(level)

def enable_console_logging(enabled=True):
    """Enable/disable console logging"""
    if _global_logger:
        _global_logger.set_console_output(enabled)

def enable_file_logging(enabled=True):
    """Enable/disable file logging"""
    if _global_logger:
        _global_logger.set_file_output(enabled)

# Emergency logging for when main logger fails
def emergency_log(category, message, level="ERROR"):
    """Emergency logging when main logger is unavailable"""
    try:
        timestamp = time.monotonic()
        entry = f"[T+{timestamp:.1f}] [EMERGENCY-{level}] {category}: {message}"
        print(entry)
        
        # Try to write to emergency log file
        try:
            with open("/emergency.log", "a") as f:
                f.write(entry + "\n")
        except:
            pass  # If we can't write to file, at least we printed to console
            
    except Exception as e:
        # Last resort - just print
        print(f"EMERGENCY: {category}: {message} (logging failed: {e})")

# Log analysis utilities
class LogAnalyzer:
    """Analyze log files for patterns and issues"""
    
    def __init__(self, log_file_path):
        self.log_file_path = log_file_path
    
    def get_error_summary(self):
        """Get summary of errors from log file"""
        try:
            errors = []
            warnings = []
            
            with open(self.log_file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if "[ERROR]" in line:
                        errors.append(line)
                    elif "[WARN]" in line:
                        warnings.append(line)
            
            return {
                "errors": errors[-10:],  # Last 10 errors
                "warnings": warnings[-10:],  # Last 10 warnings
                "error_count": len(errors),
                "warning_count": len(warnings)
            }
            
        except Exception as e:
            return {"error": f"Failed to analyze log: {e}"}
    
    def get_boot_sequence(self):
        """Extract boot sequence from logs"""
        try:
            boot_entries = []
            
            with open(self.log_file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if any(keyword in line.upper() for keyword in 
                          ["BOOT", "INIT", "START", "MOUNT", "LOAD"]):
                        boot_entries.append(line)
            
            return boot_entries[-20:]  # Last 20 boot-related entries
            
        except Exception as e:
            return [f"Failed to extract boot sequence: {e}"]
    
    def get_system_health(self):
        """Analyze system health from logs"""
        try:
            health_data = {
                "status": "UNKNOWN",
                "issues": [],
                "last_boot": None,
                "error_rate": 0
            }
            
            total_entries = 0
            error_count = 0
            
            with open(self.log_file_path, "r") as f:
                for line in f:
                    line = line.strip()
                    total_entries += 1
                    
                    if "[ERROR]" in line or "[CRITICAL]" in line:
                        error_count += 1
                        
                        # Extract common issues
                        if "MEMORY" in line.upper():
                            health_data["issues"].append("Memory issues detected")
                        elif "SD" in line.upper() or "MOUNT" in line.upper():
                            health_data["issues"].append("Storage issues detected")
                        elif "WIFI" in line.upper() or "NETWORK" in line.upper():
                            health_data["issues"].append("Network issues detected")
                    
                    if "BOOT" in line.upper() and "COMPLETE" in line.upper():
                        health_data["last_boot"] = line
            
            # Calculate error rate
            if total_entries > 0:
                health_data["error_rate"] = (error_count / total_entries) * 100
            
            # Determine overall status
            if health_data["error_rate"] < 5:
                health_data["status"] = "HEALTHY"
            elif health_data["error_rate"] < 15:
                health_data["status"] = "WARNING"
            else:
                health_data["status"] = "CRITICAL"
            
            return health_data
            
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}

def analyze_logs(log_file_path=None):
    """Analyze log files and return summary"""
    if not log_file_path and _global_logger:
        log_file_path = _global_logger.log_file_path
    
    if not log_file_path:
        return {"error": "No log file specified"}
    
    try:
        analyzer = LogAnalyzer(log_file_path)
        
        return {
            "error_summary": analyzer.get_error_summary(),
            "boot_sequence": analyzer.get_boot_sequence(),
            "system_health": analyzer.get_system_health()
        }
        
    except Exception as e:
        return {"error": f"Log analysis failed: {e}"}

# Log export utilities
def export_logs_to_json(output_path="/sd/logs_export.json"):
    """Export recent logs to JSON format"""
    try:
        if not _global_logger:
            return False
        
        export_data = {
            "export_time": time.monotonic(),
            "logger_stats": _global_logger.get_stats(),
            "recent_logs": _global_logger.get_recent_logs(100),
            "system_info": {
                "free_memory": gc.mem_free(),
                "log_level": LOG_LEVEL_NAMES[_global_logger.level],
                "file_output": _global_logger.file_output,
                "console_output": _global_logger.console_output
            }
        }
        
        with open(output_path, "w") as f:
            json.dump(export_data, f)
        
        log_info("EXPORT", f"Logs exported to {output_path}")
        return True
        
    except Exception as e:
        log_error("EXPORT", f"Failed to export logs: {e}")
        return False

def import_logs_from_json(input_path="/sd/logs_export.json"):
    """Import logs from JSON format"""
    try:
        with open(input_path, "r") as f:
            import_data = json.load(f)
        
        imported_logs = import_data.get("recent_logs", [])
        
        if _global_logger:
            for entry in imported_logs:
                _global_logger.buffer.add(f"[IMPORTED] {entry}")
        
        log_info("IMPORT", f"Imported {len(imported_logs)} log entries")
        return True
        
    except Exception as e:
        log_error("IMPORT", f"Failed to import logs: {e}")
        return False

# System integration utilities
def setup_system_logging():
    """Set up logging for the entire system"""
    try:
        # Try SD card first, then flash
        log_dirs = ["/sd/logs", "/logs"]
        
        for log_dir in log_dirs:
            try:
                logger = init_logging(log_dir, "medusa_system", LOG_LEVEL_INFO)
                if logger and logger.initialized:
                    log_info("SYSTEM", f"System logging initialized: {log_dir}")
                    return logger
            except Exception as e:
                print(f"Failed to initialize logging in {log_dir}: {e}")
        
        # If all else fails, console only
        print("File logging unavailable - using console only")
        return None
        
    except Exception as e:
        print(f"System logging setup failed: {e}")
        return None

def log_system_startup():
    """Log system startup information"""
    try:
        import board
        import microcontroller
        
        log_info("STARTUP", "=== MEDUSA SYSTEM STARTUP ===")
        log_info("STARTUP", f"Board: {board.board_id}")
        log_info("STARTUP", f"Free memory: {gc.mem_free()} bytes")
        
        # Log NVM status
        try:
            recovery_flag = microcontroller.nvm[0]
            boot_mode = microcontroller.nvm[1]
            dev_mode = microcontroller.nvm[2]
            
            log_info("STARTUP", f"NVM Recovery Flag: {recovery_flag}")
            log_info("STARTUP", f"NVM Boot Mode: {boot_mode}")
            log_info("STARTUP", f"NVM Developer Mode: {dev_mode}")
        except Exception as e:
            log_warn("STARTUP", f"Could not read NVM: {e}")
        
        # Log filesystem status
        try:
            flash_files = len(os.listdir("/"))
            log_info("STARTUP", f"Flash filesystem: {flash_files} items")
        except Exception as e:
            log_warn("STARTUP", f"Flash filesystem error: {e}")
        
        try:
            sd_files = len(os.listdir("/sd"))
            log_info("STARTUP", f"SD filesystem: {sd_files} items")
        except Exception as e:
            log_warn("STARTUP", f"SD filesystem not available: {e}")
        
        log_info("STARTUP", "=== STARTUP LOGGING COMPLETE ===")
        
    except Exception as e:
        log_error("STARTUP", f"Startup logging failed: {e}")

# Performance monitoring
class PerformanceLogger:
    """Log performance metrics"""
    
    def __init__(self):
        self.start_times = {}
    
    def start_timer(self, operation):
        """Start timing an operation"""
        self.start_times[operation] = time.monotonic()
    
    def end_timer(self, operation, category="PERF"):
        """End timing and log the result"""
        if operation in self.start_times:
            duration = time.monotonic() - self.start_times[operation]
            log_info(category, f"{operation} completed in {duration:.3f}s")
            del self.start_times[operation]
            return duration
        else:
            log_warn(category, f"Timer for {operation} was not started")
            return None
    
    def log_memory_usage(self, operation="", category="MEMORY"):
        """Log current memory usage"""
        free_mem = gc.mem_free()
        log_info(category, f"Memory usage{' after ' + operation if operation else ''}: {free_mem} bytes free")
        return free_mem

# Global performance logger
_perf_logger = PerformanceLogger()

def start_performance_timer(operation):
    """Start performance timer"""
    _perf_logger.start_timer(operation)

def end_performance_timer(operation, category="PERF"):
    """End performance timer"""
    return _perf_logger.end_timer(operation, category)

def log_memory_usage(operation="", category="MEMORY"):
    """Log memory usage"""
    return _perf_logger.log_memory_usage(operation, category)

# Context manager for performance logging
class LoggedOperation:
    """Context manager for logging operation performance"""
    
    def __init__(self, operation_name, category="PERF"):
        self.operation_name = operation_name
        self.category = category
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.monotonic()
        log_debug(self.category, f"Starting {self.operation_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.monotonic() - self.start_time
        
        if exc_type is None:
            log_info(self.category, f"{self.operation_name} completed in {duration:.3f}s")
        else:
            log_error(self.category, f"{self.operation_name} failed after {duration:.3f}s: {exc_val}")

# Export all public functions and classes
__all__ = [
    # Core logging
    'Logger', 'init_logging', 'get_logger',
    
    # Convenience functions
    'log_debug', 'log_info', 'log_warn', 'log_error', 'log_critical',
    'flush_logs', 'get_log_stats', 'get_recent_logs', 'cleanup_logging',
    
    # Configuration
    'set_log_level', 'enable_console_logging', 'enable_file_logging',
    
    # Emergency logging
    'emergency_log',
    
    # Analysis
    'LogAnalyzer', 'analyze_logs',
    
    # Export/Import
    'export_logs_to_json', 'import_logs_from_json',
    
    # System integration
    'setup_system_logging', 'log_system_startup',
    
    # Performance logging
    'PerformanceLogger', 'start_performance_timer', 'end_performance_timer',
    'log_memory_usage', 'LoggedOperation',
    
    # Constants
    'LOG_LEVEL_DEBUG', 'LOG_LEVEL_INFO', 'LOG_LEVEL_WARN', 
    'LOG_LEVEL_ERROR', 'LOG_LEVEL_CRITICAL'
]

print("Medusa Logging Service V2.0 loaded")

