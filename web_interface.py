"""
StageTwo - WebUI for ESP32-S3-Geek. 
version 0.1  (C) 2025 Devin Ranger
Single mode with all features: Editor, File Manager, Display Mirror, Button Control,
Code Execution, App Browser, TOTP Security, QR Generation



"""

import os
import json
import time
import board
import digitalio
import microcontroller
import supervisor
import wifi
import socketpool
import gc
import sys
import traceback
import binascii
import hashlib
import struct
from adafruit_httpserver import Server, Request, Response, GET, POST

# Version
__version__ = "3.0"
__author__ = "ESP32-S3-Geek Team"

# TOTP Implementation
class TOTP:
    """Time-based One-Time Password implementation"""
    
    def __init__(self):
        self.secrets = self._load_secrets()
    
    def _load_secrets(self):
        """Load TOTP secrets from NVM storage"""
        try:
            import microcontroller
            # Try to load from NVM - simplified for now
            # In production, implement proper NVM storage
            return {
                "main": "JBSWY3DPEHPK3PXP",  # Example secret
            }
        except:
            return {}
    
    def _save_secrets(self):
        """Save TOTP secrets to NVM storage"""
        try:
            # Implement NVM storage here
            pass
        except:
            pass
    
    def generate_secret(self):
        """Generate a new TOTP secret"""
        import urandom
        secret = ""
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        for _ in range(16):
            secret += chars[urandom.getrandbits(5)]
        return secret
    
    def add_secret(self, name, secret):
        """Add a new TOTP secret"""
        self.secrets[name] = secret
        self._save_secrets()
    
    def get_totp(self, secret, timestamp=None):
        """Generate TOTP code"""
        if timestamp is None:
            timestamp = time.time()
        
        # Convert secret from base32
        secret_bytes = self._base32_decode(secret)
        
        # Time counter (30 second intervals)
        counter = int(timestamp // 30)
        
        # HMAC-SHA1
        hmac_result = self._hmac_sha1(secret_bytes, struct.pack(">Q", counter))
        
        # Dynamic truncation
        offset = hmac_result[-1] & 0x0f
        code = struct.unpack(">I", hmac_result[offset:offset+4])[0]
        code = (code & 0x7fffffff) % 1000000
        
        return f"{code:06d}"
    
    def verify_totp(self, secret, code, window=1):
        """Verify TOTP code with time window"""
        current_time = time.time()
        for i in range(-window, window + 1):
            test_time = current_time + (i * 30)
            if self.get_totp(secret, test_time) == code:
                return True
        return False
    
    def _base32_decode(self, s):
        """Simple base32 decode"""
        # Simplified implementation
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        result = bytearray()
        
        # Remove padding and convert to uppercase
        s = s.upper().rstrip('=')
        
        # Convert each character to 5-bit value
        bits = ""
        for char in s:
            if char in alphabet:
                bits += f"{alphabet.index(char):05b}"
        
        # Convert bits to bytes
        for i in range(0, len(bits) - 7, 8):
            byte_bits = bits[i:i+8]
            if len(byte_bits) == 8:
                result.append(int(byte_bits, 2))
        
        return bytes(result)
    
    def _hmac_sha1(self, key, message):
        """HMAC-SHA1 implementation"""
        if len(key) > 64:
            key = hashlib.sha1(key).digest()
        if len(key) < 64:
            key = key + b'\x00' * (64 - len(key))
        
        o_key_pad = bytes(x ^ 0x5C for x in key)
        i_key_pad = bytes(x ^ 0x36 for x in key)
        
        inner = hashlib.sha1(i_key_pad + message).digest()
        return hashlib.sha1(o_key_pad + inner).digest()


class QRGenerator:
    """QR Code generator for TOTP setup"""
    
    def generate_totp_qr(self, secret, issuer="ESP32-S3", account="admin"):
        """Generate QR code data for TOTP setup"""
        try:
            from adafruit_miniqr import QRCode
            
            # Create TOTP URL
            url = f"otpauth://totp/{issuer}:{account}?secret={secret}&issuer={issuer}"
            
            # Generate QR code
            qr = QRCode()
            qr.add_data(url.encode())
            qr.make()
            
            # Convert to displayable format
            matrix = []
            for row in range(qr.modules_count):
                matrix_row = []
                for col in range(qr.modules_count):
                    matrix_row.append(qr.modules[row][col])
                matrix.append(matrix_row)
            
            return {
                "url": url,
                "matrix": matrix,
                "size": qr.modules_count
            }
            
        except Exception as e:
            return {"error": f"QR generation failed: {e}"}


class FileManager:
    """Advanced file manager with full CRUD operations"""
    
    def __init__(self):
        self.current_path = "/"
    
    def list_directory(self, path="/"):
        """List directory contents with details"""
        try:
            items = []
            
            # Add parent directory if not root
            if path != "/":
                parent = self._get_parent_path(path)
                items.append({
                    "name": "..",
                    "type": "directory",
                    "path": parent,
                    "size": 0,
                    "is_parent": True
                })
            
            # List all items
            for item in sorted(os.listdir(path)):
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                
                try:
                    stat = os.stat(item_path)
                    is_dir = stat[0] & 0x4000
                    
                    items.append({
                        "name": item,
                        "type": "directory" if is_dir else "file",
                        "path": item_path,
                        "size": stat[6] if not is_dir else 0,
                        "is_parent": False
                    })
                except:
                    # If stat fails, assume it's a file
                    items.append({
                        "name": item,
                        "type": "file",
                        "path": item_path,
                        "size": 0,
                        "is_parent": False
                    })
            
            return items
            
        except Exception as e:
            return []
    
    def read_file(self, filepath):
        """Read file contents"""
        try:
            with open(filepath, 'r') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"Failed to read file: {e}")
    
    def write_file(self, filepath, content):
        """Write file contents"""
        try:
            # Ensure directory exists
            self._ensure_directory(filepath)
            
            with open(filepath, 'w') as f:
                f.write(content)
            return True
        except Exception as e:
            raise Exception(f"Failed to write file: {e}")
    
    def delete_file(self, filepath):
        """Delete file or directory"""
        try:
            if self._is_directory(filepath):
                # Remove directory (must be empty)
                os.rmdir(filepath)
            else:
                os.remove(filepath)
            return True
        except Exception as e:
            raise Exception(f"Failed to delete: {e}")
    
    def create_directory(self, dirpath):
        """Create directory"""
        try:
            os.mkdir(dirpath)
            return True
        except Exception as e:
            raise Exception(f"Failed to create directory: {e}")
    
    def rename_item(self, old_path, new_path):
        """Rename file or directory"""
        try:
            # Ensure target directory exists
            self._ensure_directory(new_path)
            
            # Simple rename by copying and deleting
            if self._is_directory(old_path):
                raise Exception("Directory renaming not supported")
            else:
                # Copy file content
                content = self.read_file(old_path)
                self.write_file(new_path, content)
                os.remove(old_path)
            
            return True
        except Exception as e:
            raise Exception(f"Failed to rename: {e}")
    
    def _get_parent_path(self, path):
        """Get parent directory path"""
        if path == "/":
            return "/"
        parts = path.strip("/").split("/")
        if len(parts) <= 1:
            return "/"
        return "/" + "/".join(parts[:-1])
    
    def _is_directory(self, path):
        """Check if path is directory"""
        try:
            stat = os.stat(path)
            return bool(stat[0] & 0x4000)
        except:
            return False
    
    def _ensure_directory(self, filepath):
        """Ensure directory exists for file"""
        parts = filepath.strip("/").split("/")
        if len(parts) > 1:
            dir_path = "/" + "/".join(parts[:-1])
            if not self._path_exists(dir_path):
                # Create directory recursively
                current = ""
                for part in parts[:-1]:
                    current += "/" + part
                    if not self._path_exists(current):
                        os.mkdir(current)
    
    def _path_exists(self, path):
        """Check if path exists"""
        try:
            os.stat(path)
            return True
        except:
            return False


class DisplayMirror:
    """Display mirroring with advanced capture"""
    
    def __init__(self):
        self.last_capture = None
        self.capture_error = None
    
    def capture_display(self):
        """Capture current display state"""
        try:
            if not hasattr(board, 'DISPLAY') or not board.DISPLAY:
                return {"error": "No display available", "available": False}
            
            display = board.DISPLAY
            
            capture_data = {
                "width": display.width,
                "height": display.height,
                "available": True,
                "timestamp": time.monotonic(),
                "elements": []
            }
            
            # Capture display elements
            if hasattr(display, 'root_group') and display.root_group:
                capture_data["elements"] = self._extract_elements(display.root_group)
                capture_data["has_content"] = len(capture_data["elements"]) > 0
            else:
                capture_data["has_content"] = False
            
            self.last_capture = capture_data
            self.capture_error = None
            
            return capture_data
            
        except Exception as e:
            self.capture_error = str(e)
            return {"error": f"Display capture failed: {e}", "available": False}
    
    def _extract_elements(self, group, offset_x=0, offset_y=0):
        """Extract drawable elements from display group"""
        elements = []
        
        try:
            group_x = getattr(group, 'x', 0) + offset_x
            group_y = getattr(group, 'y', 0) + offset_y
            
            for item in group:
                try:
                    if hasattr(item, '__len__'):
                        # It's a sub-group
                        elements.extend(self._extract_elements(item, group_x, group_y))
                    else:
                        # It's an element
                        element = {
                            "type": type(item).__name__,
                            "x": getattr(item, 'x', 0) + group_x,
                            "y": getattr(item, 'y', 0) + group_y
                        }
                        
                        # Extract common properties
                        for prop in ['width', 'height', 'color', 'fill', 'text']:
                            if hasattr(item, prop):
                                value = getattr(item, prop)
                                if prop in ['color', 'fill'] and isinstance(value, int):
                                    element[prop] = f"#{value:06x}"
                                else:
                                    element[prop] = str(value)
                        
                        elements.append(element)
                        
                except Exception:
                    continue
                    
        except Exception:
            pass
        
        return elements


class CodeExecutor:
    """Live code execution engine"""
    
    def __init__(self):
        self.globals_dict = {}
        self.locals_dict = {}
        self.output_buffer = []
        self.max_output_lines = 200
    
    def execute_code(self, code, timeout=30):
        """Execute Python code with output capture"""
        try:
            self.output_buffer = []
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            
            class OutputCapture:
                def __init__(self, executor):
                    self.executor = executor
                
                def write(self, text):
                    if text.strip():
                        self.executor.output_buffer.append(text.strip())
                        if len(self.executor.output_buffer) > self.executor.max_output_lines:
                            self.executor.output_buffer.pop(0)
                
                def flush(self):
                    pass
            
            sys.stdout = OutputCapture(self)
            sys.stderr = OutputCapture(self)
            
            start_time = time.monotonic()
            
            try:
                compiled_code = compile(code, '<live_editor>', 'exec')
                exec(compiled_code, self.globals_dict, self.locals_dict)
                
                execution_time = time.monotonic() - start_time
                
                return {
                    "success": True,
                    "output": self.output_buffer.copy(),
                    "execution_time": execution_time,
                    "message": f"Executed successfully in {execution_time:.3f}s"
                }
                
            except Exception as e:
                execution_time = time.monotonic() - start_time
                
                return {
                    "success": False,
                    "output": self.output_buffer.copy(),
                    "error": f"{type(e).__name__}: {str(e)}",
                    "traceback": traceback.format_exc().split('\n'),
                    "execution_time": execution_time,
                    "message": f"Execution failed after {execution_time:.3f}s"
                }
            
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution setup failed: {str(e)}",
                "output": [],
                "message": "Failed to initialize code execution"
            }
    
    def execute_file(self, filepath):
        """Execute a Python file"""
        try:
            with open(filepath, 'r') as f:
                code = f.read()
            
            result = self.execute_code(code)
            result["filepath"] = filepath
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"File execution failed: {str(e)}",
                "output": [],
                "message": f"Failed to execute {filepath}"
            }


class AppBrowser:
    """Application browser and launcher"""
    
    def __init__(self):
        self.app_directories = ["/apps", "/examples", "/projects", "/"]
    
    def scan_apps(self):
        """Scan for Python applications"""
        apps = []
        
        for app_dir in self.app_directories:
            if self._directory_exists(app_dir):
                try:
                    for item in os.listdir(app_dir):
                        if item.endswith('.py') and not item.startswith('_'):
                            app_path = f"{app_dir}/{item}" if app_dir != "/" else f"/{item}"
                            
                            app_info = {
                                "name": item.replace('.py', '').replace('_', ' ').title(),
                                "filename": item,
                                "path": app_path,
                                "directory": app_dir,
                                "size": self._get_file_size(app_path),
                                "type": self._classify_app(item, app_dir)
                            }
                            
                            # Try to extract description from file
                            try:
                                description = self._extract_description(app_path)
                                if description:
                                    app_info["description"] = description
                            except:
                                pass
                            
                            apps.append(app_info)
                            
                except Exception:
                    continue
        
        return sorted(apps, key=lambda x: x["name"])
    
    def _directory_exists(self, path):
        """Check if directory exists"""
        try:
            os.listdir(path)
            return True
        except:
            return False
    
    def _get_file_size(self, filepath):
        """Get file size"""
        try:
            return os.stat(filepath)[6]
        except:
            return 0
    
    def _classify_app(self, filename, directory):
        """Classify application type"""
        if directory == "/":
            return "system"
        elif "example" in directory.lower():
            return "example"
        elif filename in ["main.py", "code.py", "boot.py"]:
            return "system"
        else:
            return "user"
    
    def _extract_description(self, filepath):
        """Extract description from Python file"""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
                
            # Look for docstring or comment description
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if line.startswith('"""') or line.startswith("'''"):
                    # Extract docstring
                    if line.count('"""') >= 2 or line.count("'''") >= 2:
                        return line.strip('"""').strip("'''").strip()
                    else:
                        # Multi-line docstring - get first line
                        return line.strip('"""').strip("'''").strip()
                elif line.startswith('#') and len(line) > 5:
                    # Extract comment
                    return line[1:].strip()
            
            return None
            
        except:
            return None


class EnhancedWebServer:
    """Production-ready web server with all features"""
    
    def __init__(self, port=80):
        self.port = port
        self.pool = socketpool.SocketPool(wifi.radio)
        self.server = None
        self.running = False
        
        # Initialize components
        self.totp = TOTP()
        self.qr_generator = QRGenerator()
        self.file_manager = FileManager()
        self.display_mirror = DisplayMirror()
        self.code_executor = CodeExecutor()
        self.app_browser = AppBrowser()
        
        # Authentication
        self.authenticated_sessions = set()
        self.auth_required = True
        
        # System status
        self.system_status = {}
        self.last_status_update = 0
        
        # Virtual button
        self.virtual_button_pressed = False
        self.button_available = False
        
        # Initialize physical button
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.button_available = True
        except:
            self.button = None
        
        print(f"🚀 Enhanced Web Server V{__version__} initialized")
    
    def start(self):
        """Start the enhanced web server"""
        try:
            if not wifi.radio.connected:
                print("❌ WiFi not connected")
                return False
            
            print("🌐 Starting enhanced HTTP server...")
            self._setup_routes()
            
            if self.server:
                self.running = True
                print(f"✅ Enhanced web server started")
                print(f"🌐 Access: http://{wifi.radio.ipv4_address}:{self.port}")
                print("🔐 TOTP authentication enabled")
                
                self._run_server_loop()
                return True
            else:
                print("❌ Failed to start server")
                return False
                
        except Exception as e:
            print(f"❌ Server start error: {e}")
            return False
    
    def _setup_routes(self):
        """Setup all HTTP routes"""
        try:
            self.server = Server(self.pool, "/static", debug=False)
            
            # Main interface
            @self.server.route("/", "GET")
            def handle_root(request):
                return self._handle_root(request)
            
            # Authentication
            @self.server.route("/api/auth", "POST")
            def handle_auth(request):
                return self._handle_auth(request)
            
            @self.server.route("/api/totp/setup", "GET")
            def handle_totp_setup(request):
                return self._handle_totp_setup(request)
            
            # System APIs
            @self.server.route("/api/status", "GET")
            def handle_status(request):
                return self._handle_status(request)
            
            # Code execution
            @self.server.route("/api/execute", "POST")
            def handle_execute(request):
                return self._handle_execute(request)
            
            # File management
            @self.server.route("/api/files", "GET")
            def handle_files_list(request):
                return self._handle_files_list(request)
            
            @self.server.route("/api/files/read", "POST")
            def handle_file_read(request):
                return self._handle_file_read(request)
            
            @self.server.route("/api/files/write", "POST")
            def handle_file_write(request):
                return self._handle_file_write(request)
            
            @self.server.route("/api/files/delete", "POST")
            def handle_file_delete(request):
                return self._handle_file_delete(request)
            
            @self.server.route("/api/files/rename", "POST")
            def handle_file_rename(request):
                return self._handle_file_rename(request)
            
            @self.server.route("/api/files/mkdir", "POST")
            def handle_mkdir(request):
                return self._handle_mkdir(request)
            
            # Display mirroring
            @self.server.route("/api/display", "GET")
            def handle_display(request):
                return self._handle_display(request)
            
            # Virtual button
            @self.server.route("/api/button", "POST")
            def handle_button(request):
                return self._handle_button(request)
            
            # App browser
            @self.server.route("/api/apps", "GET")
            def handle_apps(request):
                return self._handle_apps(request)
            
            @self.server.route("/api/apps/run", "POST")
            def handle_app_run(request):
                return self._handle_app_run(request)
            
            # Start server
            self.server.start(str(wifi.radio.ipv4_address), self.port)
            print(f"✅ HTTP routes configured on {wifi.radio.ipv4_address}:{self.port}")
            
        except Exception as e:
            print(f"❌ Route setup error: {e}")
            self.server = None
    
    def _run_server_loop(self):
        """Main server loop"""
        try:
            while self.running:
                try:
                    self.server.poll()
                except Exception as e:
                    print(f"Poll error: {e}")
                
                # Update system status
                current_time = time.monotonic()
                if current_time - self.last_status_update > 2.0:
                    self._update_system_status()
                    self.last_status_update = current_time
                
                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("🛑 Server stopped by user")
        except Exception as e:
            print(f"❌ Server loop error: {e}")
        
        self.stop()
    
    def _check_auth(self, request):
        """Check if request is authenticated"""
        if not self.auth_required:
            return True
        
        # Simple session-based auth for demo
        # In production, implement proper JWT or session management
        auth_header = request.headers.get('Authorization', '')
        return 'authenticated' in auth_header
    
    def _handle_root(self, request):
        """Serve main web interface"""
        try:
            html = self._get_main_interface_html()
            return Response(request, html, content_type="text/html")
        except Exception as e:
            return Response(request, f"Error: {e}", status=500)
    
    def _handle_auth(self, request):
        """Handle TOTP authentication"""
        try:
            if not request.body:
                return Response(request, json.dumps({"error": "No data"}), status=400, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            totp_code = data.get('totp', '')
            
            # Verify TOTP
            if 'main' in self.totp.secrets:
                if self.totp.verify_totp(self.totp.secrets['main'], totp_code):
                    return Response(request, json.dumps({
                        "success": True,
                        "token": "authenticated_session_token"
                    }), content_type="application/json")
            
            return Response(request, json.dumps({"error": "Invalid TOTP code"}), status=401, content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_totp_setup(self, request):
        """Handle TOTP setup and QR generation"""
        try:
            # Generate new secret if needed
            if 'main' not in self.totp.secrets:
                secret = self.totp.generate_secret()
                self.totp.add_secret('main', secret)
            else:
                secret = self.totp.secrets['main']
            
            # Generate QR code
            qr_data = self.qr_generator.generate_totp_qr(secret, "ESP32-S3-Geek", "admin")
            
            return Response(request, json.dumps({
                "secret": secret,
                "qr_url": qr_data.get("url", ""),
                "qr_matrix": qr_data.get("matrix", []),
                "qr_size": qr_data.get("size", 0)
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_status(self, request):
        """Handle system status request"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            self._update_system_status()
            return Response(request, json.dumps(self.system_status), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_execute(self, request):
        """Handle code execution"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            code = data.get('code', '')
            
            if not code.strip():
                return Response(request, json.dumps({"error": "No code provided"}), status=400, content_type="application/json")
            
            result = self.code_executor.execute_code(code)
            return Response(request, json.dumps(result), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_files_list(self, request):
        """Handle file listing"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            # Get path from query parameters
            path = "/"
            request_str = str(request.raw_request) if hasattr(request, 'raw_request') else str(request)
            if '?path=' in request_str:
                path = request_str.split('?path=')[1].split(' ')[0].replace('%2F', '/')
            
            files = self.file_manager.list_directory(path)
            return Response(request, json.dumps({
                "files": files,
                "current_path": path
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_file_read(self, request):
        """Handle file reading"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            filepath = data.get('filepath', '')
            
            content = self.file_manager.read_file(filepath)
            return Response(request, json.dumps({
                "content": content,
                "filepath": filepath
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_file_write(self, request):
        """Handle file writing"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            filepath = data.get('filepath', '')
            content = data.get('content', '')
            
            self.file_manager.write_file(filepath, content)
            return Response(request, json.dumps({
                "success": True,
                "filepath": filepath,
                "message": "File saved successfully"
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_file_delete(self, request):
        """Handle file deletion"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            filepath = data.get('filepath', '')
            
            self.file_manager.delete_file(filepath)
            return Response(request, json.dumps({
                "success": True,
                "filepath": filepath,
                "message": "Item deleted successfully"
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_file_rename(self, request):
        """Handle file renaming"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            old_path = data.get('old_path', '')
            new_path = data.get('new_path', '')
            
            self.file_manager.rename_item(old_path, new_path)
            return Response(request, json.dumps({
                "success": True,
                "old_path": old_path,
                "new_path": new_path,
                "message": "Item renamed successfully"
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_mkdir(self, request):
        """Handle directory creation"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            dirpath = data.get('dirpath', '')
            
            self.file_manager.create_directory(dirpath)
            return Response(request, json.dumps({
                "success": True,
                "dirpath": dirpath,
                "message": "Directory created successfully"
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_display(self, request):
        """Handle display mirroring"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            display_data = self.display_mirror.capture_display()
            return Response(request, json.dumps(display_data), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_button(self, request):
        """Handle virtual button control"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            action = data.get('action', 'press')
            
            if action == 'press':
                self.virtual_button_pressed = True
            elif action == 'release':
                self.virtual_button_pressed = False
            elif action == 'click':
                self.virtual_button_pressed = True
                time.sleep(0.1)
                self.virtual_button_pressed = False
            
            return Response(request, json.dumps({
                "success": True,
                "action": action,
                "button_state": self.virtual_button_pressed
            }), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_apps(self, request):
        """Handle app browser"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            apps = self.app_browser.scan_apps()
            return Response(request, json.dumps({"apps": apps}), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _handle_app_run(self, request):
        """Handle app execution"""
        try:
            if not self._check_auth(request):
                return Response(request, json.dumps({"error": "Unauthorized"}), status=401, content_type="application/json")
            
            data = json.loads(request.body.decode('utf-8'))
            app_path = data.get('app_path', '')
            
            result = self.code_executor.execute_file(app_path)
            return Response(request, json.dumps(result), content_type="application/json")
            
        except Exception as e:
            return Response(request, json.dumps({"error": str(e)}), status=500, content_type="application/json")
    
    def _update_system_status(self):
        """Update system status"""
        try:
            # Get button state
            button_pressed = self.virtual_button_pressed
            if self.button_available and self.button:
                try:
                    button_pressed = button_pressed or (not self.button.value)
                except:
                    pass
            
            self.system_status = {
                "timestamp": time.monotonic(),
                "memory": {
                    "free": gc.mem_free(),
                    "allocated": gc.mem_alloc() if hasattr(gc, 'mem_alloc') else None
                },
                "uptime": time.monotonic(),
                "wifi": {
                    "connected": wifi.radio.connected,
                    "ip_address": str(wifi.radio.ipv4_address) if wifi.radio.connected else None
                },
                "board": {
                    "id": board.board_id,
                    "has_display": hasattr(board, 'DISPLAY') and board.DISPLAY is not None
                },
                "button": {
                    "pressed": button_pressed,
                    "physical_available": self.button_available,
                    "virtual_pressed": self.virtual_button_pressed
                },
                "server": {
                    "running": self.running,
                    "version": __version__
                }
            }
            
            # Add CPU info if available
            try:
                self.system_status["cpu"] = {
                    "frequency": getattr(microcontroller.cpu, 'frequency', None),
                    "temperature": getattr(microcontroller.cpu, 'temperature', None)
                }
            except:
                pass
                
        except Exception as e:
            self.system_status = {
                "error": str(e),
                "timestamp": time.monotonic()
            }
    
    def _get_main_interface_html(self):
        """Get the main web interface HTML"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESP32-S3-Geek Enhanced Control Panel</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            min-height: 100vh;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .auth-panel {
            background: white;
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            max-width: 400px;
            margin: 50px auto;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        
        .main-interface {
            display: none;
        }
        
        .status-bar {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            color: white;
        }
        
        .tabs {
            display: flex;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            margin-bottom: 20px;
            overflow: hidden;
        }
        
        .tab {
            flex: 1;
            padding: 15px;
            text-align: center;
            cursor: pointer;
            color: white;
            transition: background 0.3s;
        }
        
        .tab.active {
            background: rgba(255,255,255,0.2);
        }
        
        .tab:hover {
            background: rgba(255,255,255,0.15);
        }
        
        .panel {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            display: none;
        }
        
        .panel.active {
            display: block;
        }
        
        .panel h3 {
            margin-bottom: 15px;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        
        .btn {
            padding: 10px 15px;
            margin: 5px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
            background: #667eea;
            color: white;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }
        
        .btn.danger { background: #f44336; }
        .btn.success { background: #4CAF50; }
        .btn.warning { background: #ff9800; }
        
        .code-editor {
            width: 100%;
            height: 300px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
            resize: vertical;
        }
        
        .file-browser {
            border: 1px solid #ddd;
            border-radius: 5px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .file-item {
            padding: 10px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .file-item:hover {
            background: #f5f5f5;
        }
        
        .file-item.directory {
            font-weight: bold;
            color: #2196F3;
        }
        
        .console {
            background: #1e1e1e;
            color: #00ff00;
            padding: 15px;
            border-radius: 8px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        
        .display-mirror {
            border: 2px solid #ddd;
            border-radius: 10px;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
            background: #f9f9f9;
            min-height: 200px;
        }
        
        .virtual-button {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: linear-gradient(145deg, #667eea, #764ba2);
            border: none;
            color: white;
            font-size: 18px;
            cursor: pointer;
            margin: 20px auto;
            display: block;
            transition: all 0.2s ease;
            box-shadow: 0 8px 16px rgba(0,0,0,0.2);
        }
        
        .virtual-button:active,
        .virtual-button.pressed {
            transform: scale(0.95);
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .input-group input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        
        .output {
            margin-top: 15px;
            padding: 15px;
            border-radius: 5px;
            background: #f5f5f5;
            border-left: 4px solid #2196F3;
            display: none;
        }
        
        .output.success {
            border-left-color: #4CAF50;
            background: #e8f5e8;
        }
        
        .output.error {
            border-left-color: #f44336;
            background: #ffeaea;
        }
        
        .qr-code {
            display: inline-block;
            margin: 20px;
        }
        
        .qr-pixel {
            width: 4px;
            height: 4px;
            display: inline-block;
        }
        
        .qr-pixel.black { background: #000; }
        .qr-pixel.white { background: #fff; }
        
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .tabs { flex-direction: column; }
            .code-editor { height: 200px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 ESP32-S3-Geek Enhanced Control Panel</h1>
            <p>Production-Ready Development Interface</p>
        </div>

        <!-- Authentication Panel -->
        <div id="authPanel" class="auth-panel">
            <h2>🔐 TOTP Authentication</h2>
            <p>Enter your 6-digit TOTP code:</p>
            <div class="input-group" style="margin-top: 20px;">
                <input type="text" id="totpInput" placeholder="000000" maxlength="6" style="text-align: center; font-size: 18px;">
                <button class="btn" onclick="authenticate()">Login</button>
            </div>
            <div style="margin-top: 20px;">
                <button class="btn" onclick="setupTOTP()">Setup TOTP</button>
            </div>
            <div id="totpSetup" style="display: none; margin-top: 20px;">
                <h3>TOTP Setup</h3>
                <p>Scan this QR code with Google Authenticator:</p>
                <div id="qrCode"></div>
                <p>Secret: <code id="totpSecret"></code></p>
            </div>
        </div>

        <!-- Main Interface -->
        <div id="mainInterface" class="main-interface">
            <!-- Status Bar -->
            <div class="status-bar">
                <div id="statusDisplay">Loading system status...</div>
            </div>

            <!-- Navigation Tabs -->
            <div class="tabs">
                <div class="tab active" onclick="showTab('editor')">📝 Code Editor</div>
                <div class="tab" onclick="showTab('files')">📁 File Manager</div>
                <div class="tab" onclick="showTab('display')">🖥️ Display Mirror</div>
                <div class="tab" onclick="showTab('button')">🔘 Button Control</div>
                <div class="tab" onclick="showTab('apps')">📱 App Browser</div>
                <div class="tab" onclick="showTab('system')">⚙️ System</div>
            </div>

            <!-- Code Editor Panel -->
            <div id="editorPanel" class="panel active">
                <h3>🐍 Live Python Code Editor</h3>
                <textarea id="codeEditor" class="code-editor" placeholder="# Enter your Python code here
import board
import time
print('Hello from ESP32-S3-Geek!')
print('Board ID:', board.board_id)"></textarea>
                <div style="margin-top: 10px;">
                    <button class="btn success" onclick="executeCode()">▶️ Execute</button>
                    <button class="btn" onclick="clearEditor()">🧹 Clear</button>
                    <button class="btn" onclick="saveCode()">💾 Save</button>
                    <button class="btn" onclick="loadCode()">📂 Load</button>
                </div>
                <div id="codeOutput" class="output"></div>
            </div>

            <!-- File Manager Panel -->
            <div id="filesPanel" class="panel">
                <h3>📁 File Manager</h3>
                <div class="input-group">
                    <input type="text" id="currentPath" value="/" readonly>
                    <button class="btn" onclick="refreshFiles()">🔄 Refresh</button>
                    <button class="btn success" onclick="createFile()">📄 New File</button>
                    <button class="btn success" onclick="createFolder()">📁 New Folder</button>
                </div>
                <div id="fileBrowser" class="file-browser"></div>
                
                <!-- File Editor -->
                <div id="fileEditor" style="display: none; margin-top: 20px;">
                    <h4>Editing: <span id="editingFile"></span></h4>
                    <textarea id="fileContent" class="code-editor" style="height: 200px;"></textarea>
                    <div style="margin-top: 10px;">
                        <button class="btn success" onclick="saveFile()">💾 Save</button>
                        <button class="btn" onclick="closeFileEditor()">❌ Close</button>
                    </div>
                </div>
            </div>

            <!-- Display Mirror Panel -->
            <div id="displayPanel" class="panel">
                <h3>🖥️ Display Mirror</h3>
                <div style="text-align: center; margin-bottom: 20px;">
                    <button class="btn" onclick="refreshDisplay()">🔄 Refresh Display</button>
                    <button class="btn" onclick="toggleAutoRefresh()">⏱️ Auto Refresh</button>
                </div>
                <div id="displayMirror" class="display-mirror">
                    <p>Display content will appear here...</p>
                </div>
            </div>

            <!-- Button Control Panel -->
            <div id="buttonPanel" class="panel">
                <h3>🔘 Virtual Button Control</h3>
                <div style="text-align: center;">
                    <button id="virtualButton" class="virtual-button" 
                            onmousedown="pressButton()" 
                            onmouseup="releaseButton()" 
                            onmouseleave="releaseButton()"
                            ontouchstart="pressButton()" 
                            ontouchend="releaseButton()">
                        PRESS
                    </button>
                    <p id="buttonStatus">Button Ready</p>
                    <div style="margin-top: 20px;">
                        <button class="btn" onclick="quickClick()">⚡ Quick Click</button>
                        <button class="btn" onclick="longPress()">⏳ Long Press</button>
                    </div>
                </div>
            </div>

            <!-- App Browser Panel -->
            <div id="appsPanel" class="panel">
                <h3>📱 Application Browser</h3>
                <div style="margin-bottom: 20px;">
                    <button class="btn" onclick="scanApps()">🔍 Scan Apps</button>
                </div>
                <div id="appsList"></div>
            </div>

            <!-- System Panel -->
            <div id="systemPanel" class="panel">
                <h3>⚙️ System Control</h3>
                <div class="console" id="console"></div>
                <div class="input-group">
                    <input type="text" id="commandInput" placeholder="Enter system command">
                    <button class="btn" onclick="sendCommand()">Send</button>
                </div>
                <div style="margin-top: 20px;">
                    <button class="btn" onclick="runGC()">🗑️ Garbage Collect</button>
                    <button class="btn warning" onclick="resetSystem()">🔄 Reset System</button>
                    <button class="btn" onclick="checkMemory()">💾 Memory Info</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Global variables
        let authToken = null;
        let currentPath = '/';
        let displayAutoRefresh = false;
        let displayRefreshInterval = null;
        let buttonPressed = false;
        
        // Authentication
        function authenticate() {
            const totp = document.getElementById('totpInput').value;
            if (!totp || totp.length !== 6) {
                alert('Please enter a 6-digit TOTP code');
                return;
            }
            
            fetch('/api/auth', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({totp: totp})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    authToken = data.token;
                    document.getElementById('authPanel').style.display = 'none';
                    document.getElementById('mainInterface').style.display = 'block';
                    initializeInterface();
                } else {
                    alert('Authentication failed: ' + (data.error || 'Invalid code'));
                }
            })
            .catch(error => {
                alert('Authentication error: ' + error.message);
            });
        }
        
        function setupTOTP() {
            fetch('/api/totp/setup')
            .then(response => response.json())
            .then(data => {
                if (data.secret) {
                    document.getElementById('totpSecret').textContent = data.secret;
                    
                    // Generate QR code display
                    const qrDiv = document.getElementById('qrCode');
                    qrDiv.innerHTML = '';
                    
                    if (data.qr_matrix && data.qr_matrix.length > 0) {
                        const qrContainer = document.createElement('div');
                        qrContainer.className = 'qr-code';
                        
                        for (let row of data.qr_matrix) {
                            const rowDiv = document.createElement('div');
                            for (let cell of row) {
                                const pixel = document.createElement('span');
                                pixel.className = 'qr-pixel ' + (cell ? 'black' : 'white');
                                rowDiv.appendChild(pixel);
                            }
                            qrContainer.appendChild(rowDiv);
                        }
                        qrDiv.appendChild(qrContainer);
                    } else {
                        qrDiv.innerHTML = '<p>QR Code: ' + data.qr_url + '</p>';
                    }
                    
                    document.getElementById('totpSetup').style.display = 'block';
                }
            })
            .catch(error => {
                alert('TOTP setup error: ' + error.message);
            });
        }
        
        // Interface initialization
        function initializeInterface() {
            addToConsole('🚀 ESP32-S3-Geek Enhanced Interface loaded');
            refreshStatus();
            refreshFiles();
            scanApps();
            
            // Start status refresh
            setInterval(refreshStatus, 5000);
            
            // Setup keyboard shortcuts
            document.addEventListener('keydown', function(e) {
                if (e.ctrlKey && e.key === 'Enter') {
                    e.preventDefault();
                    executeCode();
                }
            });
            
            document.getElementById('commandInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendCommand();
                }
            });
        }
        
        // Tab management
        function showTab(tabName) {
            // Hide all panels
            const panels = document.querySelectorAll('.panel');
            panels.forEach(panel => panel.classList.remove('active'));
            
            // Remove active from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected panel
            document.getElementById(tabName + 'Panel').classList.add('active');
            
            // Activate selected tab
            event.target.classList.add('active');
        }
        
        // Status management
        function refreshStatus() {
            fetch('/api/status', {
                headers: {'Authorization': 'Bearer ' + authToken}
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('statusDisplay').innerHTML = '❌ ' + data.error;
                } else {
                    const memory = Math.round(data.memory.free / 1024);
                    const uptime = Math.round(data.uptime);
                    const status = `✅ Connected | Memory: ${memory}KB | Uptime: ${uptime}s | Button: ${data.button.pressed ? 'Pressed' : 'Released'}`;
                    document.getElementById('statusDisplay').innerHTML = status;
                }
            })
            .catch(error => {
                document.getElementById('statusDisplay').innerHTML = '❌ Status Error: ' + error.message;
            });
        }
        
        // Code execution
        function executeCode() {
            const code = document.getElementById('codeEditor').value;
            if (!code.trim()) {
                alert('No code to execute');
                return;
            }
            
            const output = document.getElementById('codeOutput');
            output.style.display = 'block';
            output.className = 'output';
            output.innerHTML = '⏳ Executing code...';
            
            fetch('/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({code: code})
            })
            .then(response => response.json())
            .then(result => {
                let html = '';
                if (result.success) {
                    output.className = 'output success';
                    html = `<strong>✅ ${result.message}</strong>`;
                    if (result.output && result.output.length >
                    if (result.output && result.output.length > 0) {
                        html += '<br><strong>Output:</strong><br>';
                        result.output.forEach(line => {
                            if (line.trim()) html += line + '<br>';
                        });
                    }
                } else {
                    output.className = 'output error';
                    html = `<strong>❌ ${result.message}</strong><br>`;
                    html += `<strong>Error:</strong> ${result.error}<br>`;
                    if (result.output && result.output.length > 0) {
                        html += '<strong>Output before error:</strong><br>';
                        result.output.forEach(line => {
                            if (line.trim()) html += line + '<br>';
                        });
                    }
                }
                output.innerHTML = html;
                addToConsole(`Code execution ${result.success ? 'completed' : 'failed'} in ${result.execution_time.toFixed(3)}s`);
            })
            .catch(error => {
                output.className = 'output error';
                output.innerHTML = '❌ Execution error: ' + error.message;
                addToConsole('Execution error: ' + error.message);
            });
        }
        
        function clearEditor() {
            document.getElementById('codeEditor').value = '';
            document.getElementById('codeOutput').style.display = 'none';
        }
        
        function saveCode() {
            const filename = prompt('Enter filename (e.g., my_code.py):');
            if (filename) {
                const code = document.getElementById('codeEditor').value;
                const filepath = currentPath === '/' ? '/' + filename : currentPath + '/' + filename;
                
                fetch('/api/files/write', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({filepath: filepath, content: code})
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        addToConsole('✅ Code saved to ' + filepath);
                        refreshFiles();
                    } else {
                        alert('Save failed: ' + result.error);
                    }
                })
                .catch(error => {
                    alert('Save error: ' + error.message);
                });
            }
        }
        
        function loadCode() {
            // This would open a file picker from the file browser
            showTab('files');
            addToConsole('💡 Use the File Manager to select a file to load into the editor');
        }
        
        // File management
        function refreshFiles() {
            fetch('/api/files?path=' + encodeURIComponent(currentPath), {
                headers: {'Authorization': 'Bearer ' + authToken}
            })
            .then(response => response.json())
            .then(data => {
                if (data.files) {
                    displayFiles(data.files);
                    document.getElementById('currentPath').value = data.current_path;
                    currentPath = data.current_path;
                } else {
                    alert('File listing error: ' + data.error);
                }
            })
            .catch(error => {
                alert('File refresh error: ' + error.message);
            });
        }
        
        function displayFiles(files) {
            const browser = document.getElementById('fileBrowser');
            browser.innerHTML = '';
            
            files.forEach(file => {
                const item = document.createElement('div');
                item.className = 'file-item' + (file.type === 'directory' ? ' directory' : '');
                
                const info = document.createElement('div');
                const icon = file.type === 'directory' ? '📁' : '📄';
                info.innerHTML = `${icon} ${file.name}`;
                if (file.type === 'file' && file.size > 0) {
                    info.innerHTML += ` (${formatBytes(file.size)})`;
                }
                
                const actions = document.createElement('div');
                
                if (file.type === 'directory') {
                    const openBtn = document.createElement('button');
                    openBtn.className = 'btn';
                    openBtn.textContent = 'Open';
                    openBtn.onclick = () => {
                        currentPath = file.path;
                        refreshFiles();
                    };
                    actions.appendChild(openBtn);
                } else {
                    const editBtn = document.createElement('button');
                    editBtn.className = 'btn';
                    editBtn.textContent = 'Edit';
                    editBtn.onclick = () => editFile(file.path);
                    actions.appendChild(editBtn);
                    
                    const runBtn = document.createElement('button');
                    runBtn.className = 'btn success';
                    runBtn.textContent = 'Run';
                    runBtn.onclick = () => runFile(file.path);
                    actions.appendChild(runBtn);
                }
                
                if (!file.is_parent) {
                    const renameBtn = document.createElement('button');
                    renameBtn.className = 'btn warning';
                    renameBtn.textContent = 'Rename';
                    renameBtn.onclick = () => renameItem(file.path, file.name);
                    actions.appendChild(renameBtn);
                    
                    const deleteBtn = document.createElement('button');
                    deleteBtn.className = 'btn danger';
                    deleteBtn.textContent = 'Delete';
                    deleteBtn.onclick = () => deleteItem(file.path, file.name);
                    actions.appendChild(deleteBtn);
                }
                
                item.appendChild(info);
                item.appendChild(actions);
                browser.appendChild(item);
            });
        }
        
        function editFile(filepath) {
            fetch('/api/files/read', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({filepath: filepath})
            })
            .then(response => response.json())
            .then(data => {
                if (data.content !== undefined) {
                    document.getElementById('editingFile').textContent = filepath;
                    document.getElementById('fileContent').value = data.content;
                    document.getElementById('fileEditor').style.display = 'block';
                    document.getElementById('fileEditor').dataset.filepath = filepath;
                } else {
                    alert('Failed to read file: ' + data.error);
                }
            })
            .catch(error => {
                alert('File read error: ' + error.message);
            });
        }
        
        function saveFile() {
            const filepath = document.getElementById('fileEditor').dataset.filepath;
            const content = document.getElementById('fileContent').value;
            
            fetch('/api/files/write', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({filepath: filepath, content: content})
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    addToConsole('✅ File saved: ' + filepath);
                    refreshFiles();
                } else {
                    alert('Save failed: ' + result.error);
                }
            })
            .catch(error => {
                alert('Save error: ' + error.message);
            });
        }
        
        function closeFileEditor() {
            document.getElementById('fileEditor').style.display = 'none';
        }
        
        function runFile(filepath) {
            fetch('/api/apps/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({app_path: filepath})
            })
            .then(response => response.json())
            .then(result => {
                addToConsole(`🏃 Running ${filepath}...`);
                if (result.success) {
                    addToConsole(`✅ Execution completed in ${result.execution_time.toFixed(3)}s`);
                    if (result.output && result.output.length > 0) {
                        result.output.forEach(line => {
                            if (line.trim()) addToConsole('  ' + line);
                        });
                    }
                } else {
                    addToConsole(`❌ Execution failed: ${result.error}`);
                }
            })
            .catch(error => {
                addToConsole('❌ Run error: ' + error.message);
            });
        }
        
        function createFile() {
            const filename = prompt('Enter new filename:');
            if (filename) {
                const filepath = currentPath === '/' ? '/' + filename : currentPath + '/' + filename;
                
                fetch('/api/files/write', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({filepath: filepath, content: ''})
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        addToConsole('✅ File created: ' + filepath);
                        refreshFiles();
                    } else {
                        alert('Create failed: ' + result.error);
                    }
                })
                .catch(error => {
                    alert('Create error: ' + error.message);
                });
            }
        }
        
        function createFolder() {
            const foldername = prompt('Enter new folder name:');
            if (foldername) {
                const dirpath = currentPath === '/' ? '/' + foldername : currentPath + '/' + foldername;
                
                fetch('/api/files/mkdir', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({dirpath: dirpath})
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        addToConsole('✅ Folder created: ' + dirpath);
                        refreshFiles();
                    } else {
                        alert('Create folder failed: ' + result.error);
                    }
                })
                .catch(error => {
                    alert('Create folder error: ' + error.message);
                });
            }
        }
        
        function renameItem(oldPath, oldName) {
            const newName = prompt('Enter new name:', oldName);
            if (newName && newName !== oldName) {
                const pathParts = oldPath.split('/');
                pathParts[pathParts.length - 1] = newName;
                const newPath = pathParts.join('/');
                
                fetch('/api/files/rename', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({old_path: oldPath, new_path: newPath})
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        addToConsole('✅ Renamed: ' + oldPath + ' → ' + newPath);
                        refreshFiles();
                    } else {
                        alert('Rename failed: ' + result.error);
                    }
                })
                .catch(error => {
                    alert('Rename error: ' + error.message);
                });
            }
        }
        
        function deleteItem(filepath, filename) {
            if (confirm(`Delete "${filename}"? This cannot be undone.`)) {
                fetch('/api/files/delete', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({filepath: filepath})
                })
                .then(response => response.json())
                .then(result => {
                    if (result.success) {
                        addToConsole('✅ Deleted: ' + filepath);
                        refreshFiles();
                    } else {
                        alert('Delete failed: ' + result.error);
                    }
                })
                .catch(error => {
                    alert('Delete error: ' + error.message);
                });
            }
        }
        
        // Display mirroring
        function refreshDisplay() {
            fetch('/api/display', {
                headers: {'Authorization': 'Bearer ' + authToken}
            })
            .then(response => response.json())
            .then(data => {
                const mirror = document.getElementById('displayMirror');
                
                if (data.available) {
                    let html = `<h4>Display: ${data.width}x${data.height}</h4>`;
                    
                    if (data.has_content && data.elements && data.elements.length > 0) {
                        html += '<div style="border: 1px solid #ccc; margin: 10px; padding: 10px; background: white;">';
                        
                        // Create a simple representation of display elements
                        data.elements.forEach(element => {
                            html += `<div style="margin: 5px; padding: 5px; border: 1px dashed #999;">`;
                            html += `<strong>${element.type}</strong> at (${element.x}, ${element.y})`;
                            if (element.text) html += ` - Text: "${element.text}"`;
                            if (element.color) html += ` - Color: ${element.color}`;
                            html += '</div>';
                        });
                        
                        html += '</div>';
                    } else {
                        html += '<p>No display content detected</p>';
                    }
                } else {
                    html = '<p>❌ Display not available: ' + (data.error || 'Unknown error') + '</p>';
                }
                
                mirror.innerHTML = html;
            })
            .catch(error => {
                document.getElementById('displayMirror').innerHTML = '❌ Display error: ' + error.message;
            });
        }
        
        function toggleAutoRefresh() {
            displayAutoRefresh = !displayAutoRefresh;
            
            if (displayAutoRefresh) {
                displayRefreshInterval = setInterval(refreshDisplay, 1000);
                addToConsole('✅ Display auto-refresh enabled');
            } else {
                if (displayRefreshInterval) {
                    clearInterval(displayRefreshInterval);
                    displayRefreshInterval = null;
                }
                addToConsole('⏹️ Display auto-refresh disabled');
            }
        }
        
        // Button control
        function pressButton() {
            if (buttonPressed) return;
            buttonPressed = true;
            
            document.getElementById('virtualButton').classList.add('pressed');
            document.getElementById('buttonStatus').textContent = 'Button Pressed';
            
            fetch('/api/button', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({action: 'press'})
            })
            .then(response => response.json())
            .then(result => {
            .then(result => {
                addToConsole('🔘 Virtual button pressed');
            })
            .catch(error => {
                addToConsole('Button press error: ' + error.message);
            });
        }
        
        function releaseButton() {
            if (!buttonPressed) return;
            buttonPressed = false;
            
            document.getElementById('virtualButton').classList.remove('pressed');
            document.getElementById('buttonStatus').textContent = 'Button Released';
            
            fetch('/api/button', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({action: 'release'})
            })
            .then(response => response.json())
            .then(result => {
                addToConsole('🔘 Virtual button released');
            })
            .catch(error => {
                addToConsole('Button release error: ' + error.message);
            });
        }
        
        function quickClick() {
            fetch('/api/button', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({action: 'click', duration: 0.1})
            })
            .then(response => response.json())
            .then(result => {
                addToConsole('🔘 Quick click sent');
                
                // Visual feedback
                const btn = document.getElementById('virtualButton');
                btn.classList.add('pressed');
                setTimeout(() => btn.classList.remove('pressed'), 100);
            })
            .catch(error => {
                addToConsole('Quick click error: ' + error.message);
            });
        }
        
        function longPress() {
            fetch('/api/button', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({action: 'click', duration: 2.0})
            })
            .then(response => response.json())
            .then(result => {
                addToConsole('🔘 Long press sent (2s)');
                
                // Visual feedback
                const btn = document.getElementById('virtualButton');
                btn.classList.add('pressed');
                setTimeout(() => btn.classList.remove('pressed'), 2000);
            })
            .catch(error => {
                addToConsole('Long press error: ' + error.message);
            });
        }
        
        // App browser
        function scanApps() {
            fetch('/api/apps', {
                headers: {'Authorization': 'Bearer ' + authToken}
            })
            .then(response => response.json())
            .then(data => {
                if (data.apps) {
                    displayApps(data.apps);
                    addToConsole(`📱 Found ${data.apps.length} applications`);
                } else {
                    alert('App scan error: ' + data.error);
                }
            })
            .catch(error => {
                alert('App scan error: ' + error.message);
            });
        }
        
        function displayApps(apps) {
            const appsList = document.getElementById('appsList');
            appsList.innerHTML = '';
            
            if (apps.length === 0) {
                appsList.innerHTML = '<p>No applications found</p>';
                return;
            }
            
            apps.forEach(app => {
                const appDiv = document.createElement('div');
                appDiv.className = 'file-item';
                appDiv.style.flexDirection = 'column';
                appDiv.style.alignItems = 'flex-start';
                
                const header = document.createElement('div');
                header.style.display = 'flex';
                header.style.justifyContent = 'space-between';
                header.style.width = '100%';
                header.style.alignItems = 'center';
                
                const info = document.createElement('div');
                const typeIcon = app.type === 'system' ? '⚙️' : app.type === 'example' ? '📚' : '📱';
                info.innerHTML = `<strong>${typeIcon} ${app.name}</strong><br>`;
                info.innerHTML += `<small>${app.path} (${formatBytes(app.size)})</small>`;
                if (app.description) {
                    info.innerHTML += `<br><em>${app.description}</em>`;
                }
                
                const actions = document.createElement('div');
                
                const runBtn = document.createElement('button');
                runBtn.className = 'btn success';
                runBtn.textContent = '▶️ Run';
                runBtn.onclick = () => runApp(app.path);
                actions.appendChild(runBtn);
                
                const editBtn = document.createElement('button');
                editBtn.className = 'btn';
                editBtn.textContent = '✏️ Edit';
                editBtn.onclick = () => {
                    showTab('files');
                    editFile(app.path);
                };
                actions.appendChild(editBtn);
                
                header.appendChild(info);
                header.appendChild(actions);
                appDiv.appendChild(header);
                appsList.appendChild(appDiv);
            });
        }
        
        function runApp(appPath) {
            addToConsole(`🚀 Running application: ${appPath}`);
            
            fetch('/api/apps/run', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({app_path: appPath})
            })
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    addToConsole(`✅ App completed in ${result.execution_time.toFixed(3)}s`);
                    if (result.output && result.output.length > 0) {
                        result.output.forEach(line => {
                            if (line.trim()) addToConsole('  ' + line);
                        });
                    }
                } else {
                    addToConsole(`❌ App failed: ${result.error}`);
                    if (result.output && result.output.length > 0) {
                        addToConsole('Output before error:');
                        result.output.forEach(line => {
                            if (line.trim()) addToConsole('  ' + line);
                        });
                    }
                }
            })
            .catch(error => {
                addToConsole('❌ App run error: ' + error.message);
            });
        }
        
        // System control
        function sendCommand() {
            const input = document.getElementById('commandInput');
            const command = input.value.trim();
            
            if (!command) return;
            
            addToConsole('> ' + command);
            input.value = '';
            
            // Handle some commands locally
            if (command === 'clear') {
                document.getElementById('console').innerHTML = '';
                return;
            }
            
            // Send to server
            fetch('/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({code: `print("Command: ${command}")
# Add command handling logic here
if "${command}" == "help":
    print("Available commands: help, status, memory, wifi, gc, reset")
elif "${command}" == "status":
    import gc, time, wifi, board
    print(f"Memory: {gc.mem_free()} bytes")
    print(f"Uptime: {time.monotonic():.1f}s")
    print(f"WiFi: {wifi.radio.connected}")
    print(f"Board: {board.board_id}")
elif "${command}" == "memory":
    import gc
    print(f"Free memory: {gc.mem_free()} bytes")
elif "${command}" == "wifi":
    import wifi
    print(f"WiFi connected: {wifi.radio.connected}")
    if wifi.radio.connected:
        print(f"IP: {wifi.radio.ipv4_address}")
elif "${command}" == "gc":
    import gc
    before = gc.mem_free()
    gc.collect()
    after = gc.mem_free()
    print(f"GC: {before} -> {after} bytes (+{after-before})")
elif "${command}" == "reset":
    print("Use the Reset System button for device reset")
else:
    print(f"Unknown command: {command}. Type 'help' for available commands.")
`})
            })
            .then(response => response.json())
            .then(result => {
                if (result.output && result.output.length > 0) {
                    result.output.forEach(line => {
                        if (line.trim() && !line.includes('Command:')) {
                            addToConsole(line);
                        }
                    });
                }
                if (!result.success && result.error) {
                    addToConsole('❌ ' + result.error);
                }
            })
            .catch(error => {
                addToConsole('❌ Command error: ' + error.message);
            });
        }
        
        function runGC() {
            fetch('/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({code: `
import gc
before = gc.mem_free()
gc.collect()
after = gc.mem_free()
print(f"Garbage collection: {before} -> {after} bytes (+{after-before})")
`})
            })
            .then(response => response.json())
            .then(result => {
                if (result.output && result.output.length > 0) {
                    addToConsole('🗑️ ' + result.output[0]);
                }
                refreshStatus();
            })
            .catch(error => {
                addToConsole('❌ GC error: ' + error.message);
            });
        }
        
        function resetSystem() {
            if (confirm('⚠️ Reset the system? This will disconnect the interface and restart the device.')) {
                addToConsole('🔄 Resetting system...');
                addToConsole('⚠️ Connection will be lost');
                
                fetch('/api/execute', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({code: 'import microcontroller; microcontroller.reset()'})
                })
                .catch(() => {
                    // Expected to fail as device resets
                });
            }
        }
        
        function checkMemory() {
            fetch('/api/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + authToken
                },
                body: JSON.stringify({code: `
import gc, microcontroller
print(f"Free memory: {gc.mem_free()} bytes ({gc.mem_free()/1024:.1f} KB)")
try:
    print(f"Allocated memory: {gc.mem_alloc()} bytes")
except:
    pass
try:
    print(f"CPU frequency: {microcontroller.cpu.frequency} Hz")
    print(f"CPU temperature: {microcontroller.cpu.temperature}°C")
except:
    pass
`})
            })
            .then(response => response.json())
            .then(result => {
                if (result.output && result.output.length > 0) {
                    addToConsole('💾 Memory Information:');
                    result.output.forEach(line => {
                        if (line.trim()) addToConsole('  ' + line);
                    });
                }
            })
            .catch(error => {
                addToConsole('❌ Memory check error: ' + error.message);
            });
        }
        
        // Utility functions
        function addToConsole(message) {
            const console = document.getElementById('console');
            const timestamp = new Date().toLocaleTimeString();
            const line = document.createElement('div');
            line.textContent = `[${timestamp}] ${message}`;
            console.appendChild(line);
            console.scrollTop = console.scrollHeight;
            
            // Limit console lines
            while (console.children.length > 100) {
                console.removeChild(console.firstChild);
            }
        }
        
        function formatBytes(bytes) {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            console.log('ESP32-S3-Geek Enhanced Interface loaded');
            
            // Auto-focus TOTP input
            document.getElementById('totpInput').focus();
            
            // Handle Enter key in TOTP input
            document.getElementById('totpInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    authenticate();
                }
            });
        });
    </script>
</body>
</html>
"""
    
    def stop(self):
        """Stop the enhanced web server"""
        try:
            print("🛑 Stopping enhanced web server...")
            self.running = False
            
            if self.server:
                self.server.stop()
            
            print("✅ Enhanced web server stopped")
            
        except Exception as e:
            print(f"❌ Server stop error: {e}")
    
    def _update_system_status(self):
        """Update comprehensive system status"""
        try:
            # Get button state
            button_pressed = self.virtual_button_pressed
            if self.button_available and self.button:
                try:
                    button_pressed = button_pressed or (not self.button.value)
                except:
                    pass
            
            self.system_status = {
                "timestamp": time.monotonic(),
                "memory": {
                    "free": gc.mem_free(),
                    "allocated": gc.mem_alloc() if hasattr(gc, 'mem_alloc') else None
                },
                "uptime": time.monotonic(),
                "wifi": {
                    "connected": wifi.radio.connected,
                    "ip_address": str(wifi.radio.ipv4_address) if wifi.radio.connected else None,
                    "mac_address": ":".join([f"{b:02x}" for b in wifi.radio.mac_address])
                },
                "board": {
                    "id": board.board_id,
                    "has_display": hasattr(board, 'DISPLAY') and board.DISPLAY is not None
                },
                "button": {
                    "pressed": button_pressed,
                    "physical_available": self.button_available,
                    "virtual_pressed": self.virtual_button_pressed
                },
                "server": {
                    "running": self.running,
                    "version": __version__,
                    "auth_enabled": self.auth_required
                }
            }
            
            # Add CPU info if available
            try:
                self.system_status["cpu"] = {
                    "frequency": getattr(microcontroller.cpu, 'frequency', None),
                    "temperature": getattr(microcontroller.cpu, 'temperature', None),
                    "voltage": getattr(microcontroller.cpu, 'voltage', None)
                }
            except:
                pass
                
        except Exception as e:
            self.system_status = {
                "error": str(e),
                "timestamp": time.monotonic()
            }


# Production server launcher
def start_production_server(port=80, auth_required=True):
    """Start the production-ready enhanced web server"""
    try:
        print("🚀 Starting ESP32-S3-Geek Enhanced Web Server...")
        print(f"📋 Version: {__version__}")
        print(f"🔐 Authentication: {'Enabled' if auth_required else 'Disabled'}")
        
        server = EnhancedWebServer(port=port)
        server.auth_required = auth_required
        
        # Display startup information
        if wifi.radio.connected:
            print(f"🌐 WiFi: Connected to {wifi.radio.ap_info.ssid}")
            print(f"📡 IP Address: {wifi.radio.ipv4_address}")
            print(f"🔗 Access URL: http://{wifi.radio.ipv4_address}:{port}")
        else:
            print("❌ WiFi not connected - server cannot start")
            return None
        
        # Start the server
        success = server.start()
        
        if success:
            print("✅ Enhanced web server started successfully")
            return server
        else:
            print("❌ Failed to start enhanced web server")
            return None
            
    except Exception as e:
        print(f"❌ Server startup error: {e}")
        return None


# Legacy compatibility function
def start_web_server(port=80, auto_start=True):
    """Legacy compatibility function - starts enhanced server"""
    if auto_start:
        return start_production_server(port=port, auth_required=False)
    else:
        server = EnhancedWebServer(port=port)
        server.auth_required = False
        return server


# Development utilities
class DevUtils:
    """Development utilities for the web server"""
    
    @staticmethod
    def generate_test_files():
        """Generate test files for development"""
        test_files = {
            "/test_blink.py": '''# LED Blink Test
import board
import digitalio
import time

try:
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    
    print("Starting LED blink test...")
    for i in range(5):
        led.value = True
        print(f"LED ON - Blink {i+1}")
        time.sleep(0.5)
        led.value = False
        print(f"LED OFF - Blink {i+1}")
        time.sleep(0.5)
    
    print("LED blink test completed!")
    
except Exception as e:
    print(f"LED test error: {e}")
''',
            "/test_sensors.py": '''# Sensor Reading Test
import board
import analogio
import time

try:
    # Test analog input if available
    if hasattr(board, 'A0'):
        sensor = analogio.AnalogIn(board.A0)
        
        print("Reading analog sensor on A0...")
        for i in range(10):
            raw_value = sensor.value
            voltage = (raw_value * 3.3) / 65536
            print(f"Reading {i+1}: Raw={raw_value}, Voltage={voltage:.3f}V")
            time.sleep(0.5)
    else:
        print("No analog pins available for testing")
        
except Exception as e:
    print(f"Sensor test error: {e}")
''',
            "/test_display.py": '''# Display Test
import board
import displayio
import terminalio
from adafruit_display_text import label

try:
    if hasattr(board, 'DISPLAY') and board.DISPLAY:
        display = board.DISPLAY
        
        # Create a main group
        main_group = displayio.Group()
        
        # Create text label
        text = "ESP32-S3-Geek\\nDisplay Test"
        text_area = label.Label(terminalio.FONT, text=text, color=0xFFFFFF)
        text_area.x = 10
        text_area.y = 20
        
        main_group.append(text_area)
        display.show(main_group)
        
        print("Display test completed - check your screen!")
        
    else:
        print("No display available for testing")
        
except Exception as e:
    print(f"Display test error: {e}")
''',
            "/test_button.py": '''# Button Test
import board
import digitalio
import time

try:
    if hasattr(board, 'BUTTON'):
        button = digitalio.DigitalInOut(board.BUTTON)
        button.direction = digitalio.Direction.INPUT
        button.pull = digitalio.Pull.UP
        
        print("Button test - press the button!")
        print("Test will run for 10 seconds...")
        
        last_state = button.value
        start_time = time.monotonic()
        press_count = 0
        
        while time.monotonic() - start_time < 10:
            current_state = button.value
            
            if current_state != last_state:
                if not current_state:  # Button pressed (active low)
                    press_count += 1
                    print(f"Button pressed! (Press #{press_count})")
                else:  # Button released
                    print("Button released")
                
                last_state = current_state
            
            time.sleep(0.01)
        
        print(f"Button test completed - {press_count} presses detected")
        
    else:
        print("No button available for testing")
        
except Exception as e:
    print(f"Button test error: {e}")
''',
            "/test_memory.py": '''# Memory Test
import gc
import time
import microcontroller

try:
    print("=== Memory Test ===")
    
    # Initial memory state
    initial_free = gc.mem_free()
    print(f"Initial free memory: {initial_free} bytes ({initial_free/1024:.1f} KB)")
    
    # Allocate some memory
    test_data = []
    for i in range(100):
        test_data.append(f"Test string {i} with some data to use memory")
    
    after_alloc = gc.mem_free()
    used = initial_free - after_alloc
    print(f"After allocation: {after_alloc} bytes ({used} bytes used)")
    
    # Clear the data
    test_data = None
    
    # Force garbage collection
    gc.collect()
    
    after_gc = gc.mem_free()
    recovered = after_gc - after_alloc
    print(f"After GC: {after_gc} bytes ({recovered} bytes recovered)")
    
    # System info
    print("\\n=== System Info ===")
    print(f"Board ID: {board.board_id}")
    
    try:
        print(f"CPU Frequency: {microcontroller.cpu.frequency} Hz")
        print(f"CPU Temperature: {microcontroller.cpu.temperature}°C")
    except:
        print("CPU info not available")
    
    print("Memory test completed!")
    
except Exception as e:
    print(f"Memory test error: {e}")
''',
            "/examples/hello_world.py": '''# Hello World Example
import board
import time

print("Hello from ESP32-S3-Geek!")
print(f"Board ID: {board.board_id}")
print(f"Current time: {time.monotonic():.2f} seconds")

# Count to 10
for i in range(1, 11):
    print(f"Count: {i}")
    time.sleep(0.5)

print("Hello World example completed!")
'''
        }
        
        created_files = []
        
        for filepath, content in test_files.items():
            try:
                # Create directory if needed
                if '/' in filepath[1:]:  # Skip the leading slash
                    dir_path = '/'.join(filepath.split('/')[:-1])
                    if dir_path and not DevUtils._directory_exists(dir_path):
                        try:
                            os.mkdir(dir_path)
                            print(f"📁 Created directory: {dir_path}")
                        except:
                            pass
                
                # Write file
                with open(filepath, 'w') as f:
                    f.write(content)
                
                created_files.append(filepath)
                print(f"📄 Created test file: {filepath}")
                
            except Exception as e:
                print(f"❌ Failed to create {filepath}: {e}")
        
        print(f"✅ Created {len(created_files)} test files")
        return created_files
    
    @staticmethod
    def _directory_exists(path):
        """Check if directory exists"""
        try:
            os.listdir(path)
            return True
        except:
            return False
    
    @staticmethod
    def cleanup_test_files():
        """Remove test files"""
        test_files = [
            "/test_blink.py",
            "/test_sensors.py", 
            "/test_display.py",
            "/test_button.py",
            "/test_memory.py",
            "/examples/hello_world.py"
        ]
        
        removed_files = []
        
        for filepath in test_files:
            try:
                if DevUtils._file_exists(filepath):
                    os.remove(filepath)
                    removed_files.append(filepath)
                    print(f"🗑️ Removed: {filepath}")
            except Exception as e:
                print(f"❌ Failed to remove {filepath}: {e}")
        
        # Try to remove examples directory if empty
        try:
            if DevUtils._directory_exists("/examples"):
                files = os.listdir("/examples")
                if len(files) == 0:
                    os.rmdir("/examples")
                    print("🗑️ Removed empty examples directory")
        except:
            pass
        
        print(f"✅ Removed {len(removed_files)} test files")
        return removed_files
    
    @staticmethod
    def _file_exists(filepath):
        """Check if file exists"""
        try:
            os.stat(filepath)
            return True
        except:
            return False
    
    @staticmethod
    def run_diagnostics():
        """Run system diagnostics"""
        print("🔍 Running ESP32-S3-Geek Diagnostics...")
        print("=" * 50)
        
        # Memory check
        try:
            free_mem = gc.mem_free()
            print(f"💾 Memory: {free_mem} bytes free ({free_mem/1024:.1f} KB)")
        except Exception as e:
            print(f"❌ Memory check failed: {e}")
        
        # WiFi check
        try:
            if wifi.radio.connected:
                print(f"📡 WiFi: Connected to {wifi.radio.ap_info.ssid}")
                print(f"🌐 IP: {wifi.radio.ipv4_address}")
            else:
                print("❌ WiFi: Not connected")
        except Exception as e:
            print(f"❌ WiFi check failed: {e}")
        
        # Board info
        try:
            print(f"🔧 Board: {board.board_id}")
        except Exception as e:
            print(f"❌ Board info failed: {e}")
        
        # CPU info
        try:
            print(f"⚡ CPU: {microcontroller.cpu.frequency} Hz")
            print(f"🌡️ Temperature: {microcontroller.cpu.temperature}°C")
        except Exception as e:
            print(f"❌ CPU info failed: {e}")
        
        # Display check
        try:
            if hasattr(board, 'DISPLAY') and board.DISPLAY:
                display = board.DISPLAY
                print(f"🖥️ Display: {display.width}x{display.height} available")
            else:
                print("❌ Display: Not available")
        except Exception as e:
            print(f"❌ Display check failed: {e}")
        
        # Button check
        try:
            if hasattr(board, 'BUTTON'):
                button = digitalio.DigitalInOut(board.BUTTON)
                button.direction = digitalio.Direction.INPUT
                button.pull = digitalio.Pull.UP
                state = "pressed" if not button.value else "released"
                print(f"🔘 Button: Available ({state})")
            else:
                print("❌ Button: Not available")
        except Exception as e:
            print(f"❌ Button check failed: {e}")
        
        # File system check
        try:
            files = os.listdir("/")
            print(f"📁 Root files: {len(files)} items")
        except Exception as e:
            print(f"❌ File system check failed: {e}")
        
        print("=" * 50)
        print("✅ Diagnostics completed")


# Main execution function
def main():
    """Main entry point"""
    try:
        print("🚀 ESP32-S3-Geek Enhanced Web Server")
        print(f"📋 Version: {__version__}")
        print("=" * 50)
        
        # Run diagnostics
        DevUtils.run_diagnostics()
        print()
        
        # Check WiFi connection
        if not wifi.radio.connected:
            print("❌ WiFi not connected - cannot start web server")
            print("💡 Please ensure WiFi is configured and connected")
            return False
        
        # Start the production server
        server = start_production_server(port=80, auth_required=True)
        
        if server:
            print("✅ Enhanced web server started successfully!")
            print("🔐 TOTP authentication is enabled")
            print("📱 Access the interface from any web browser")
            print("🛑 Press Ctrl+C to stop the server")
            
            try:
                # Keep server running
                while server.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Shutdown requested by user")
                server.stop()
                return True
        else:
            print("❌ Failed to start web server")
            return False
            
    except Exception as e:
        print(f"❌ Main execution error: {e}")
        import traceback
        traceback.print_exc()
        return False


# Auto-start if run directly
if __name__ == "__main__":
    success = main()
    if success:
        print("✅ Web server shutdown completed")
    else:
        print("❌ Web server failed to start or encountered errors")
else:
    print(f"📦 ESP32-S3-Geek Enhanced Web Server V{__version__} module loaded")
    print("🚀 Use start_production_server() for full features")
    print("🔧 Use start_web_server() for legacy compatibility")
    print("🛠️ Use DevUtils for development utilities")


# Export main classes and functions
__all__ = [
    'EnhancedWebServer',
    'start_production_server',
    'start_web_server',
    'DevUtils',
    'main'
]

# Final module information
print(f"✅ ESP32-S3-Geek Enhanced Web Server V{__version__} ready")
print("🌟 Features: TOTP Auth, File Manager, Display Mirror, Live Code Execution")

# Memory cleanup
try:
    gc.collect()
    print(f"💾 Memory after module load: {gc.mem_free()} bytes free")
except:
    pass

# Quick start examples
QUICK_START_EXAMPLES = {
    "basic_server": '''
# Basic server without authentication
from web_interface_server import start_web_server
server = start_web_server(port=80, auto_start=True)
''',
    
    "production_server": '''
# Production server with TOTP authentication
from web_interface_server import start_production_server
server = start_production_server(port=80, auth_required=True)
''',
    
    "development_setup": '''
# Development setup with test files
from web_interface_server import DevUtils, start_web_server

# Generate test files
DevUtils.generate_test_files()

# Run diagnostics
DevUtils.run_diagnostics()

# Start server
server = start_web_server(port=80)
''',
    
    "custom_server": '''
# Custom server configuration
from web_interface_server import EnhancedWebServer

server = EnhancedWebServer(port=8080)
server.auth_required = False
server.start()
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

# Add to exports
__all__.append('show_examples')
__all__.append('QUICK_START_EXAMPLES')

print("📖 Use show_examples() to see quick start code examples")
print("🎯 Module initialization complete - ready for use!")

# End of enhanced web interface server
