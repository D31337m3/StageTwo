import wifi
import socketpool
import adafruit_httpserver
import microcontroller
import os
import time
import json
import gc

# Import WiFi configuration utilities
try:
    from wifi_config import get_saved_networks, get_primary_network, save_wifi_network, load_settings
    WIFI_CONFIG_AVAILABLE = True
except ImportError:
    WIFI_CONFIG_AVAILABLE = False
    print("Warning: wifi_config.py not available - limited WiFi functionality")

class PropellantIDE:
    def __init__(self):
        self.pool = None
        self.server = None
        self.current_file = "/sd/mycode.py" 
        self.file_tree = {}
        self.wifi_connected = False
        self.server_running = False
        
    def check_wifi_connection(self):
        """Check if WiFi is connected"""
        try:
            if hasattr(wifi, 'radio') and hasattr(wifi.radio, 'connected'):
                return wifi.radio.connected
        except Exception:
            pass
        return False
    
    def get_wifi_networks(self):
        """Get available and saved WiFi networks"""
        networks = {
            'saved': [],
            'available': [],
            'current': None
        }
        
        if not WIFI_CONFIG_AVAILABLE:
            return networks
        
        try:
            # Get saved networks
            saved_networks = get_saved_networks()
            networks['saved'] = [{'ssid': ssid, 'saved': True} for ssid, _ in saved_networks]
            
            # Get current primary network
            primary_ssid, _ = get_primary_network()
            if primary_ssid:
                networks['current'] = primary_ssid
            
            # Scan for available networks
            if hasattr(wifi, 'radio') and wifi.radio.enabled:
                try:
                    scan_results = wifi.radio.start_scanning_networks()
                    available = {}
                    
                    for network in scan_results:
                        try:
                            ssid = network.ssid
                            if isinstance(ssid, bytes):
                                ssid = ssid.decode("utf-8", errors='ignore')
                            
                            if ssid and ssid.strip():
                                rssi = getattr(network, 'rssi', -100)
                                if ssid not in available or available[ssid]['rssi'] < rssi:
                                    available[ssid] = {
                                        'ssid': ssid,
                                        'rssi': rssi,
                                        'saved': any(s['ssid'] == ssid for s in networks['saved'])
                                    }
                        except Exception:
                            continue
                    
                    wifi.radio.stop_scanning_networks()
                    networks['available'] = sorted(available.values(), key=lambda x: x['rssi'], reverse=True)
                    
                except Exception as e:
                    print(f"WiFi scan failed: {e}")
        
        except Exception as e:
            print(f"Error getting WiFi networks: {e}")
        
        return networks
    
    def connect_to_wifi(self, ssid, password=None):
        """Connect to WiFi network"""
        try:
            if not hasattr(wifi, 'radio'):
                return False, "WiFi radio not available"
            
            if not wifi.radio.enabled:
                wifi.radio.enabled = True
                time.sleep(1)
            
            # Disconnect if already connected
            if wifi.radio.connected:
                wifi.radio.disconnect()
                time.sleep(1)
            
            # Get password from saved networks if not provided
            if not password and WIFI_CONFIG_AVAILABLE:
                saved_networks = get_saved_networks()
                for saved_ssid, saved_password in saved_networks:
                    if saved_ssid == ssid:
                        password = saved_password
                        break
            
            if not password:
                return False, "Password required"
            
            # Attempt connection
            wifi.radio.connect(ssid, password, timeout=15)
            
            # Verify connection
            time.sleep(2)
            if wifi.radio.connected:
                # Save network if successful and wifi_config is available
                if WIFI_CONFIG_AVAILABLE:
                    save_wifi_network(ssid, password, make_primary=True)
                return True, f"Connected to {ssid}"
            else:
                return False, "Connection failed"
                
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    def setup_wifi(self):
        """Setup WiFi connection"""
        print("Setting up WiFi connection...")
        
        # Check if already connected
        if self.check_wifi_connection():
            print(f"Already connected to WiFi: {wifi.radio.ap_info.ssid if wifi.radio.ap_info else 'Unknown'}")
            self.wifi_connected = True
            return True
        
        # Try to connect using saved primary network
        if WIFI_CONFIG_AVAILABLE:
            try:
                primary_ssid, primary_password = get_primary_network()
                if primary_ssid and primary_password:
                    print(f"Attempting to connect to primary network: {primary_ssid}")
                    success, message = self.connect_to_wifi(primary_ssid, primary_password)
                    if success:
                        print(f"Connected to primary network: {message}")
                        self.wifi_connected = True
                        return True
                    else:
                        print(f"Primary network connection failed: {message}")
            except Exception as e:
                print(f"Error connecting to primary network: {e}")
        
        # If no primary network or connection failed, we'll handle this via web interface
        print("No WiFi connection established - will provide setup via web interface")
        return False
    
    def get_file_tree(self, path="/", max_depth=3, current_depth=0):
        """Get file tree structure"""
        if current_depth >= max_depth:
            return {}
        
        tree = {}
        try:
            items = os.listdir(path)
            for item in sorted(items):
                if item.startswith('.'):
                    continue
                    
                item_path = f"{path}/{item}" if path != "/" else f"/{item}"
                
                try:
                    stat = os.stat(item_path)
                    is_dir = stat[0] & 0x4000  # Check if directory
                    
                    if is_dir:
                        tree[item] = {
                            'type': 'directory',
                            'path': item_path,
                            'children': self.get_file_tree(item_path, max_depth, current_depth + 1)
                        }
                    else:
                        tree[item] = {
                            'type': 'file',
                            'path': item_path,
                            'size': stat[6]
                        }
                except OSError:
                    continue
                    
        except OSError:
            pass
            
        return tree
    
    def read_file(self, file_path):
        """Read file content"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try reading as binary for non-text files
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                    return f"<Binary file - {len(content)} bytes>"
            except Exception:
                return "<Unable to read file>"
        except Exception as e:
            return f"<Error reading file: {e}>"
    
    def write_file(self, file_path, content):
        """Write file content"""
        try:
            # Create directory if it doesn't exist
            dir_path = "/".join(file_path.split("/")[:-1])
            if dir_path and dir_path != "/":
                self.create_directory(dir_path)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, "File saved successfully"
        except Exception as e:
            return False, f"Error saving file: {e}"
    
    def create_directory(self, dir_path):
        """Create directory recursively"""
        try:
            parts = [p for p in dir_path.split("/") if p]
            current = ""
            for part in parts:
                current = f"{current}/{part}" if current else f"/{part}"
                try:
                    os.mkdir(current)
                except OSError:
                    pass  # Directory might already exist
            return True
        except Exception:
            return False
    
    def delete_file(self, file_path):
        """Delete file or directory"""
        try:
            stat = os.stat(file_path)
            is_dir = stat[0] & 0x4000
            
            if is_dir:
                # Remove directory contents first
                try:
                    items = os.listdir(file_path)
                    for item in items:
                        self.delete_file(f"{file_path}/{item}")
                    os.rmdir(file_path)
                except OSError:
                    return False, "Directory not empty or cannot be deleted"
            else:
                os.remove(file_path)
            
            return True, "Deleted successfully"
        except Exception as e:
            return False, f"Error deleting: {e}"
    def start_server(self):
        """Start the web server"""
        try:
            if not self.wifi_connected:
                # Create a simple AP mode or use existing connection
                if not self.check_wifi_connection():
                    print("No WiFi connection - server will be limited")
            
            self.pool = socketpool.SocketPool(wifi.radio)
            self.server = adafruit_httpserver.Server(self.pool, "/static", debug=True)
            
            # Setup routes
            self.setup_routes()
            
            # Start server
            ip_address = str(wifi.radio.ipv4_address) if wifi.radio.connected else "192.168.4.1"
            self.server.start(ip_address)
            
            print(f"Propellant IDE Server started!")
            print(f"Connect to: http://{ip_address}/")
            
            self.server_running = True
            return True
            
        except Exception as e:
            print(f"Failed to start server: {e}")
            return False
    
    def setup_routes(self):
        """Setup HTTP routes"""
        
        @self.server.route("/")
        def index(request):
            return adafruit_httpserver.Response(
                request, 
                content_type="text/html", 
                body=self.get_main_html()
            )
        
        @self.server.route("/api/wifi/networks", methods=["GET"])
        def get_networks(request):
            networks = self.get_wifi_networks()
            return adafruit_httpserver.Response(
                request,
                content_type="application/json",
                body=json.dumps(networks)
            )
        
        @self.server.route("/api/wifi/connect", methods=["POST"])
        def connect_wifi(request):
            try:
                length = int(request.headers.get("Content-Length", 0))
                body = request.body.read(length).decode()
                data = json.loads(body)
                
                ssid = data.get('ssid')
                password = data.get('password')
                
                if not ssid:
                    return adafruit_httpserver.Response(
                        request,
                        content_type="application/json",
                        body=json.dumps({"success": False, "message": "SSID required"})
                    )
                
                success, message = self.connect_to_wifi(ssid, password)
                self.wifi_connected = success
                
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": success, "message": message})
                )
                
            except Exception as e:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": False, "message": str(e)})
                )
        
        @self.server.route("/api/files", methods=["GET"])
        def get_files(request):
            path = request.query_params.get('path', '/')
            tree = self.get_file_tree(path)
            return adafruit_httpserver.Response(
                request,
                content_type="application/json",
                body=json.dumps(tree)
            )
        
        @self.server.route("/api/file/read", methods=["GET"])
        def read_file_api(request):
            file_path = request.query_params.get('path')
            if not file_path:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": False, "message": "File path required"})
                )
            
            content = self.read_file(file_path)
            return adafruit_httpserver.Response(
                request,
                content_type="application/json",
                body=json.dumps({"success": True, "content": content, "path": file_path})
            )
        
        @self.server.route("/api/file/save", methods=["POST"])
        def save_file_api(request):
            try:
                length = int(request.headers.get("Content-Length", 0))
                body = request.body.read(length).decode()
                data = json.loads(body)
                
                file_path = data.get('path')
                content = data.get('content', '')
                
                if not file_path:
                    return adafruit_httpserver.Response(
                        request,
                        content_type="application/json",
                        body=json.dumps({"success": False, "message": "File path required"})
                    )
                
                success, message = self.write_file(file_path, content)
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": success, "message": message})
                )
                
            except Exception as e:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": False, "message": str(e)})
                )
        
        @self.server.route("/api/file/delete", methods=["POST"])
        def delete_file_api(request):
            try:
                length = int(request.headers.get("Content-Length", 0))
                body = request.body.read(length).decode()
                data = json.loads(body)
                
                file_path = data.get('path')
                if not file_path:
                    return adafruit_httpserver.Response(
                        request,
                        content_type="application/json",
                        body=json.dumps({"success": False, "message": "File path required"})
                    )
                
                success, message = self.delete_file(file_path)
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": success, "message": message})
                )
                
            except Exception as e:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": False, "message": str(e)})
                )
        
        @self.server.route("/api/file/create", methods=["POST"])
        def create_file_api(request):
            try:
                length = int(request.headers.get("Content-Length", 0))
                body = request.body.read(length).decode()
                data = json.loads(body)
                
                file_path = data.get('path')
                is_directory = data.get('is_directory', False)
                
                if not file_path:
                    return adafruit_httpserver.Response(
                        request,
                        content_type="application/json",
                        body=json.dumps({"success": False, "message": "File path required"})
                    )
                
                if is_directory:
                    success = self.create_directory(file_path)
                    message = "Directory created" if success else "Failed to create directory"
                else:
                    success, message = self.write_file(file_path, "")
                
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": success, "message": message})
                )
                
            except Exception as e:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": False, "message": str(e)})
                )
        
        @self.server.route("/api/system/info", methods=["GET"])
        def system_info(request):
            try:
                import gc
                info = {
                    "free_memory": gc.mem_free(),
                    "allocated_memory": gc.mem_alloc(),
                    "wifi_connected": self.check_wifi_connection(),
                    "current_file": self.current_file,
                    "platform": "CircuitPython"
                }
                
                if wifi.radio.connected and wifi.radio.ap_info:
                    info["wifi_ssid"] = wifi.radio.ap_info.ssid
                    info["wifi_rssi"] = wifi.radio.ap_info.rssi
                    info["ip_address"] = str(wifi.radio.ipv4_address)
                
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps(info)
                )
            except Exception as e:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"error": str(e)})
                )
        
        @self.server.route("/api/system/restart", methods=["POST"])
        def restart_system(request):
            try:
                # Schedule restart after response
                def delayed_restart():
                    time.sleep(2)
                    microcontroller.reset()
                
                # This is a simple way to restart - in a real implementation
                # you might want to use threading or supervisor
                microcontroller.reset()
                
            except Exception as e:
                return adafruit_httpserver.Response(
                    request,
                    content_type="application/json",
                    body=json.dumps({"success": False, "message": str(e)})
                )
    
    def get_main_html(self):
        """Generate the main HTML interface"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Propellant IDE - CircuitPython Web Editor</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            height: 100vh;
            overflow: hidden;
        }
        
        .container {
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 300px;
            background: #252526;
            border-right: 1px solid #3e3e42;
            display: flex;
            flex-direction: column;
        }
        
        .sidebar-header {
            padding: 10px;
            background: #2d2d30;
            border-bottom: 1px solid #3e3e42;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .logo {
            font-size: 18px;
            font-weight: bold;
            color: #007acc;
        }
        
        .status-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #f14c4c;
        }
        
        .status-indicator.connected {
            background: #89d185;
        }
        
        .tabs {
            display: flex;
            background: #2d2d30;
            border-bottom: 1px solid #3e3e42;
        }
        
        .tab {
            padding: 8px 16px;
            cursor: pointer;
            border-right: 1px solid #3e3e42;
            background: #2d2d30;
            color: #cccccc;
        }
        
        .tab.active {
            background: #1e1e1e;
            color: #ffffff;
        }
        
        .tab:hover {
            background: #37373d;
        }
        
        .tab-content {
            flex: 1;
            overflow-y: auto;
            padding: 10px;
        }
        
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .toolbar {
            background: #2d2d30;
            border-bottom: 1px solid #3e3e42;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .btn {
            background: #0e639c;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 3px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .btn:hover {
            background: #1177bb;
        }
        
        .btn.secondary {
            background: #5a5a5a;
        }
        
        .btn.secondary:hover {
            background: #6a6a6a;
        }
        
        .btn.danger {
            background: #f14c4c;
        }
        
        .btn.danger:hover {
            background: #ff6b6b;
        }
        
        .editor-container {
            flex: 1;
            position: relative;
        }
        
        .editor {
            width: 100%;
            height: 100%;
            background: #1e1e1e;
            color: #d4d4d4;
            border: none;
            outline: none;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.5;
            padding: 16px;
            resize: none;
            tab-size: 4;
        }
        
        .file-tree {
            list-style: none;
        }
        
        .file-item {
            padding: 4px 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .file-item:hover {
            background: #37373d;
        }
        
        .file-item.selected {
            background: #094771;
        }
        
        .file-icon {
            width: 16px;
            height: 16px;
            display: inline-block;
        }
        
        .folder-icon::before {
            content: "📁";
        }
        
        .file-icon::before {
            content: "📄";
        }
        
        .python-icon::before {
            content: "🐍";
        }
        
        .wifi-section {
            margin-bottom: 20px;
        }
        
        .wifi-network {
            padding: 8px;
            margin: 4px 0;
            background: #37373d;
            border-radius: 4px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .wifi-network:hover {
            background: #404040;
        }
        
        .wifi-network.connected {
            background: #0e4f1f;
        }
        
        .wifi-network.saved {
            border-left: 3px solid #007acc;
        }
        
        .signal-strength {
            font-size: 12px;
            color: #888;
        }
        
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000;
        }
        
        .modal-content {
            background: #2d2d30;
            margin: 10% auto;
            padding: 20px;
            width: 400px;
            border-radius: 6px;
            border: 1px solid #3e3e42;
        }
        
        .modal-header {
            margin-bottom: 16px;
            font-size: 16px;
            font-weight: bold;
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-label {
            display: block;
            margin-bottom: 4px;
            font-size: 12px;
            color: #cccccc;
        }
        
        .form-input {
            width: 100%;
            padding: 8px;
            background: #1e1e1e;
            border: 1px solid #3e3e42;
            border-radius: 3px;
            color: #d4d4d4;
            font-size: 14px;
        }
        
        .form-input:focus {
            outline: none;
            border-color: #007acc;
        }
        
        .modal-actions {
            display: flex;
            gap: 8px;
            justify-content: flex-end;
        }
        
        .status-bar {
            background: #007acc;
            color: white;
            padding: 4px 16px;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .loading {
            display: inline-block;
            width: 12px;
            height: 12px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .hidden {
            display: none !important;
        }
        
        .breadcrumb {
            padding: 8px 16px;
            background: #37373d;
            font-size: 12px;
            color: #cccccc;
            border-bottom: 1px solid #3e3e42;
        }
        
        .breadcrumb-item {
            cursor: pointer;
            color: #007acc;
        }
        
        .breadcrumb-item:hover {
            text-decoration: underline;
        }
        
        .context-menu {
            position: absolute;
            background: #2d2d30;
            border: 1px solid #3e3e42;
            border-radius: 4px;
            padding: 4px 0;
            min-width: 150px;
            z-index: 1000;
            display: none;
        }
        
        .context-menu-item {
            padding: 8px 16px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .context-menu-item:hover {
            background: #37373d;
        }
        
        .system-info {
            font-size: 11px;
            color: #888;
            padding: 8px;
            background: #1e1e1e;
            border-top: 1px solid #3e3e42;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="logo">Propellant IDE</div>
                <div class="status-indicator" id="wifiStatus"></div>
            </div>
            
            <div class="tabs">
                <div class="tab active" data-tab="files">Files</div>
                <div class="tab" data-tab="wifi">WiFi</div>
                <div class="tab" data-tab="system">System</div>
            </div>
            
            <div class="tab-content">
                <div id="files-tab" class="tab-panel">
                    <div class="breadcrumb" id="breadcrumb">/</div>
                    <ul class="file-tree" id="fileTree"></ul>
                </div>
                
                <div id="wifi-tab" class="tab-panel hidden">
                    <div class="wifi-section">
                        <h3>WiFi Networks</h3>
                        <button class="btn" id="scanWifi">Scan Networks</button>
                        <div id="wifiNetworks"></div>
                    </div>
                </div>
                
                <div id="system-tab" class="tab-panel hidden">
                    <div class="system-info" id="systemInfo">
                        Loading system information...
                    </div>
                    <button class="btn danger" id="restartBtn">Restart System</button>
                </div>
            </div>
        </div>
        
        <div class="main-content">
            <div class="toolbar">
                <button class="btn" id="saveBtn">Save (Ctrl+S)</button>
                <button class="btn secondary" id="newFileBtn">New File</button>
                <button class="btn secondary" id="newFolderBtn">New Folder</button>
                <span id="currentFile">/sd/mycode.py</span>
            </div>
            
            <div class="editor-container">
                <textarea class="editor" id="editor" placeholder="Select a file to edit..."></textarea>
            </div>
            
            <div class="status-bar">
                <span id="statusText">Ready</span>
                <span id="systemStats">Memory: -- | WiFi: --</span>
            </div>
        </div>
    </div>
    
    <!-- WiFi Password Modal -->
    <div class="modal" id="wifiModal">
        <div class="modal-content">
            <div class="modal-header">Connect to WiFi</div>
            <div class="form-group">
                <label class="form-label">Network Name (SSID)</label>
                <input type="text" class="form-input" id="wifiSSID" readonly>
            </div>
            <div class="form-group">
                <label class="form-label">Password</label>
                <input type="password" class="form-input" id="wifiPassword" placeholder="Enter WiFi password">
            </div>
            <div class="modal-actions">
                <button class="btn secondary" id="cancelWifi">Cancel</button>
                <button class="btn" id="connectWifi">Connect</button>
            </div>
        </div>
    </div>
    
    <!-- New File/Folder Modal -->
    <div class="modal" id="newItemModal">
        <div class="modal-content">
            <div class="modal-header" id="newItemTitle">Create New Item</div>
            <div class="form-group">
                <label class="form-label">Name</label>
                <input type="text" class="form-input" id="newItemName" placeholder="Enter name">
            </div>
            <div class="modal-actions">
                <button class="btn secondary" id="cancelNewItem">Cancel</button>
                <button class="btn" id="createNewItem">Create</button>
            </div>
        </div>
    </div>
    
    <!-- Context Menu -->
    <div class="context-menu" id="contextMenu">
        <div class="context-menu-item" id="deleteItem">Delete</div>
        <div class="context-menu-item" id="renameItem">Rename</div>
    </div>
    <script>
        class PropellantIDE {
            constructor() {
                this.currentFile = '/code.py';
                this.currentPath = '/';
                this.fileTree = {};
                this.isNewItemFolder = false;
                this.selectedFile = null;
                this.unsavedChanges = false;
                
                this.initializeEventListeners();
                this.loadFileTree();
                this.updateSystemInfo();
                this.checkWiFiStatus();
                
                // Auto-save and status updates
                setInterval(() => this.updateSystemInfo(), 5000);
                setInterval(() => this.checkWiFiStatus(), 10000);
            }
            
            initializeEventListeners() {
                // Tab switching
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.addEventListener('click', (e) => this.switchTab(e.target.dataset.tab));
                });
                
                // Editor events
                const editor = document.getElementById('editor');
                editor.addEventListener('input', () => {
                    this.unsavedChanges = true;
                    this.updateStatus('Modified');
                });
                
                // Keyboard shortcuts
                document.addEventListener('keydown', (e) => {
                    if (e.ctrlKey && e.key === 's') {
                        e.preventDefault();
                        this.saveCurrentFile();
                    }
                });
                
                // Toolbar buttons
                document.getElementById('saveBtn').addEventListener('click', () => this.saveCurrentFile());
                document.getElementById('newFileBtn').addEventListener('click', () => this.showNewItemModal(false));
                document.getElementById('newFolderBtn').addEventListener('click', () => this.showNewItemModal(true));
                
                // WiFi events
                document.getElementById('scanWifi').addEventListener('click', () => this.scanWiFiNetworks());
                document.getElementById('connectWifi').addEventListener('click', () => this.connectToWiFi());
                document.getElementById('cancelWifi').addEventListener('click', () => this.hideWiFiModal());
                
                // New item modal events
                document.getElementById('createNewItem').addEventListener('click', () => this.createNewItem());
                document.getElementById('cancelNewItem').addEventListener('click', () => this.hideNewItemModal());
                
                // System events
                document.getElementById('restartBtn').addEventListener('click', () => this.restartSystem());
                
                // Context menu
                document.addEventListener('contextmenu', (e) => this.showContextMenu(e));
                document.addEventListener('click', () => this.hideContextMenu());
                document.getElementById('deleteItem').addEventListener('click', () => this.deleteSelectedItem());
                
                // Modal click outside to close
                document.querySelectorAll('.modal').forEach(modal => {
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            modal.style.display = 'none';
                        }
                    });
                });
            }
            
            switchTab(tabName) {
                // Update tab appearance
                document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
                document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
                
                // Show/hide tab content
                document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.add('hidden'));
                document.getElementById(`${tabName}-tab`).classList.remove('hidden');
                
                // Load tab-specific content
                if (tabName === 'wifi') {
                    this.loadWiFiNetworks();
                } else if (tabName === 'system') {
                    this.updateSystemInfo();
                }
            }
            
            async loadFileTree(path = '/') {
                try {
                    this.updateStatus('Loading files...');
                    const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
                    const tree = await response.json();
                    
                    this.fileTree = tree;
                    this.currentPath = path;
                    this.renderFileTree(tree);
                    this.updateBreadcrumb(path);
                    this.updateStatus('Ready');
                } catch (error) {
                    console.error('Error loading file tree:', error);
                    this.updateStatus('Error loading files', true);
                }
            }
            
            renderFileTree(tree, container = null, level = 0) {
                if (!container) {
                    container = document.getElementById('fileTree');
                    container.innerHTML = '';
                }
                
                Object.entries(tree).forEach(([name, item]) => {
                    const li = document.createElement('li');
                    li.className = 'file-item';
                    li.style.paddingLeft = `${8 + level * 16}px`;
                    
                    const icon = document.createElement('span');
                    if (item.type === 'directory') {
                        icon.className = 'file-icon folder-icon';
                    } else if (name.endsWith('.py')) {
                        icon.className = 'file-icon python-icon';
                    } else {
                        icon.className = 'file-icon';
                    }
                    
                    const nameSpan = document.createElement('span');
                    nameSpan.textContent = name;
                    
                    li.appendChild(icon);
                    li.appendChild(nameSpan);
                    
                    if (item.type === 'directory') {
                        li.addEventListener('click', () => this.loadFileTree(item.path));
                    } else {
                        li.addEventListener('click', (event) => this.openFile(item.path, event));
                        li.addEventListener('contextmenu', (e) => {
                            e.preventDefault();
                            this.selectedFile = item.path;
                            this.showContextMenu(e);
                        });
                    }
                    
                    container.appendChild(li);
                    
                    // Render subdirectories
                    if (item.type === 'directory' && item.children && Object.keys(item.children).length > 0) {
                        const subList = document.createElement('ul');
                        subList.className = 'file-tree';
                        this.renderFileTree(item.children, subList, level + 1);
                        container.appendChild(subList);
                    }
                });
            }
            
            updateBreadcrumb(path) {
                const breadcrumb = document.getElementById('breadcrumb');
                const parts = path.split('/').filter(p => p);
                
                let html = '<span class="breadcrumb-item" onclick="ide.loadFileTree(\'/\')">root</span>';
                let currentPath = '';
                
                parts.forEach(part => {
                    currentPath += '/' + part;
                    html += ` / <span class="breadcrumb-item" onclick="ide.loadFileTree('${currentPath}')">${part}</span>`;
                });
                
                breadcrumb.innerHTML = html;
            }
            
            async openFile(filePath, event = null) {
                try {
                    this.updateStatus('Loading file...');
                    const response = await fetch(`/api/file/read?path=${encodeURIComponent(filePath)}`);
                    const data = await response.json();
                    
                    if (data.success) {
                        document.getElementById('editor').value = data.content;
                        this.currentFile = filePath;
                        document.getElementById('currentFile').textContent = filePath;
                        this.unsavedChanges = false;
                        this.updateStatus('File loaded');
                        
                        // Highlight selected file
                        document.querySelectorAll('.file-item').forEach(item => item.classList.remove('selected'));
                        if (event && event.target) {
                            event.target.closest('.file-item').classList.add('selected');
                        }
                    } else {
                        this.updateStatus('Error loading file: ' + data.message, true);
                    }
                } catch (error) {
                    console.error('Error opening file:', error);
                    this.updateStatus('Error opening file', true);
                }
            }
            
            async saveCurrentFile() {
                if (!this.currentFile) {
                    this.updateStatus('No file selected', true);
                    return;
                }
                
                try {
                    this.updateStatus('Saving...');
                    const content = document.getElementById('editor').value;
                    
                    const response = await fetch('/api/file/save', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            path: this.currentFile,
                            content: content
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.unsavedChanges = false;
                        this.updateStatus('File saved');
                    } else {
                        this.updateStatus('Error saving: ' + data.message, true);
                    }
                } catch (error) {
                    console.error('Error saving file:', error);
                    this.updateStatus('Error saving file', true);
                }
            }
            
            showNewItemModal(isFolder) {
                this.isNewItemFolder = isFolder;
                document.getElementById('newItemTitle').textContent = `Create New ${isFolder ? 'Folder' : 'File'}`;
                document.getElementById('newItemName').value = '';
                document.getElementById('newItemModal').style.display = 'block';
                document.getElementById('newItemName').focus();
            }
            
            hideNewItemModal() {
                document.getElementById('newItemModal').style.display = 'none';
            }
            
            async createNewItem() {
                const name = document.getElementById('newItemName').value.trim();
                if (!name) return;
                
                const path = this.currentPath === '/' ? `/${name}` : `${this.currentPath}/${name}`;
                
                try {
                    const response = await fetch('/api/file/create', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            path: path,
                            is_directory: this.isNewItemFolder
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.hideNewItemModal();
                        this.loadFileTree(this.currentPath);
                        this.updateStatus(`${this.isNewItemFolder ? 'Folder' : 'File'} created`);
                        
                        if (!this.isNewItemFolder) {
                            // Open the new file for editing
                            setTimeout(() => this.openFile(path), 500);
                        }
                    } else {
                        this.updateStatus('Error creating item: ' + data.message, true);
                    }
                } catch (error) {
                    console.error('Error creating item:', error);
                    this.updateStatus('Error creating item', true);
                }
            }
            
            showContextMenu(event) {
                if (!this.selectedFile) return;
                
                event.preventDefault();
                const menu = document.getElementById('contextMenu');
                menu.style.display = 'block';
                menu.style.left = event.pageX + 'px';
                menu.style.top = event.pageY + 'px';
            }
            
            hideContextMenu() {
                document.getElementById('contextMenu').style.display = 'none';
            }
            
            async deleteSelectedItem() {
                if (!this.selectedFile) return;
                
                if (!confirm(`Are you sure you want to delete ${this.selectedFile}?`)) {
                    return;
                }
                
                try {
                    const response = await fetch('/api/file/delete', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ path: this.selectedFile })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.loadFileTree(this.currentPath);
                        this.updateStatus('Item deleted');
                        
                        // Clear editor if deleted file was open
                        if (this.currentFile === this.selectedFile) {
                            document.getElementById('editor').value = '';
                            this.currentFile = null;
                            document.getElementById('currentFile').textContent = 'No file selected';
                        }
                    } else {
                        this.updateStatus('Error deleting: ' + data.message, true);
                    }
                } catch (error) {
                    console.error('Error deleting item:', error);
                    this.updateStatus('Error deleting item', true);
                }
                
                this.hideContextMenu();
                this.selectedFile = null;
            }
            
            async checkWiFiStatus() {
                try {
                    const response = await fetch('/api/system/info');
                    const info = await response.json();
                    
                    const indicator = document.getElementById('wifiStatus');
                    if (info.wifi_connected) {
                        indicator.classList.add('connected');
                        indicator.title = `Connected to ${info.wifi_ssid || 'WiFi'}`;
                    } else {
                        indicator.classList.remove('connected');
                        indicator.title = 'WiFi not connected';
                    }
                } catch (error) {
                    console.error('Error checking WiFi status:', error);
                }
            }
            
            async loadWiFiNetworks() {
                try {
                    this.updateStatus('Loading WiFi networks...');
                    const response = await fetch('/api/wifi/networks');
                    const networks = await response.json();
                    
                    this.renderWiFiNetworks(networks);
                    this.updateStatus('WiFi networks loaded');
                } catch (error) {
                    console.error('Error loading WiFi networks:', error);
                    this.updateStatus('Error loading WiFi networks', true);
                }
            }
            
            async scanWiFiNetworks() {
                document.getElementById('scanWifi').innerHTML = '<span class="loading"></span> Scanning...';
                document.getElementById('scanWifi').disabled = true;
                
                try {
                    await this.loadWiFiNetworks();
                } finally {
                    document.getElementById('scanWifi').innerHTML = 'Scan Networks';
                    document.getElementById('scanWifi').disabled = false;
                }
            }
            
            renderWiFiNetworks(networks) {
                const container = document.getElementById('wifiNetworks');
                container.innerHTML = '';
                
                // Show current connection
                if (networks.current) {
                    const currentDiv = document.createElement('div');
                    currentDiv.innerHTML = `<strong>Current: ${networks.current}</strong>`;
                    currentDiv.style.marginBottom = '10px';
                    currentDiv.style.color = '#89d185';
                    container.appendChild(currentDiv);
                }
                
                // Combine and deduplicate networks
                const allNetworks = new Map();
                
                // Add saved networks
                networks.saved.forEach(network => {
                    allNetworks.set(network.ssid, { ...network, saved: true });
                });
                
                // Add available networks
                networks.available.forEach(network => {
                    if (allNetworks.has(network.ssid)) {
                        allNetworks.get(network.ssid).rssi = network.rssi;
                        allNetworks.get(network.ssid).available = true;
                    } else {
                        allNetworks.set(network.ssid, { ...network, available: true });
                    }
                });
                
                // Render networks
                Array.from(allNetworks.values()).forEach(network => {
                    const networkDiv = document.createElement('div');
                    networkDiv.className = 'wifi-network';
                    
                    if (network.saved) {
                        networkDiv.classList.add('saved');
                    }
                    
                    if (network.ssid === networks.current) {
                        networkDiv.classList.add('connected');
                    }
                    
                    const nameSpan = document.createElement('span');
                    nameSpan.textContent = network.ssid;
                    
                    const infoSpan = document.createElement('span');
                    infoSpan.className = 'signal-strength';
                    
                    let infoText = '';
                    if (network.saved) infoText += 'Saved ';
                    if (network.rssi !== undefined) {
                        infoText += `${network.rssi}dBm`;
                    }
                    infoSpan.textContent = infoText;
                    
                    networkDiv.appendChild(nameSpan);
                    networkDiv.appendChild(infoSpan);
                    
                    networkDiv.addEventListener('click', () => this.showWiFiModal(network.ssid));
                    
                    container.appendChild(networkDiv);
                });
                
                if (allNetworks.size === 0) {
                    container.innerHTML = '<div style="color: #888; text-align: center; padding: 20px;">No networks found</div>';
                }
            }
            
            showWiFiModal(ssid) {
                document.getElementById('wifiSSID').value = ssid;
                document.getElementById('wifiPassword').value = '';
                document.getElementById('wifiModal').style.display = 'block';
                document.getElementById('wifiPassword').focus();
            }
            
            hideWiFiModal() {
                document.getElementById('wifiModal').style.display = 'none';
            }
            
            async connectToWiFi() {
                const ssid = document.getElementById('wifiSSID').value;
                const password = document.getElementById('wifiPassword').value;
                
                if (!ssid) return;
                
                const connectBtn = document.getElementById('connectWifi');
                connectBtn.innerHTML = '<span class="loading"></span> Connecting...';
                connectBtn.disabled = true;
                
                try {
                    const response = await fetch('/api/wifi/connect', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ ssid, password })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        this.hideWiFiModal();
                        this.updateStatus('WiFi connected successfully');
                        this.checkWiFiStatus();
                        this.loadWiFiNetworks();
                    } else {
                        this.updateStatus('WiFi connection failed: ' + data.message, true);
                    }
                } catch (error) {
                    console.error('Error connecting to WiFi:', error);
                    this.updateStatus('WiFi connection error', true);
                } finally {
                    connectBtn.innerHTML = 'Connect';
                    connectBtn.disabled = false;
                }
            }
            
            async updateSystemInfo() {
                try {
                    const response = await fetch('/api/system/info');
                    const info = await response.json();
                    
                    const systemInfoDiv = document.getElementById('systemInfo');
                    systemInfoDiv.innerHTML = `
                        <div><strong>Platform:</strong> ${info.platform || 'Unknown'}</div>
                        <div><strong>Free Memory:</strong> ${this.formatBytes(info.free_memory || 0)}</div>
                        <div><strong>Used Memory:</strong> ${this.formatBytes(info.allocated_memory || 0)}</div>
                        <div><strong>WiFi Status:</strong> ${info.wifi_connected ? 'Connected' : 'Disconnected'}</div>
                        ${info.wifi_ssid ? `<div><strong>Network:</strong> ${info.wifi_ssid}</div>` : ''}
                        ${info.wifi_rssi ? `<div><strong>Signal:</strong> ${info.wifi_rssi}dBm</div>` : ''}
                        ${info.ip_address ? `<div><strong>IP Address:</strong> ${info.ip_address}</div>` : ''}
                        <div><strong>Current File:</strong> ${info.current_file || 'None'}</div>
                    `;
                    
                    // Update status bar
                    const memoryText = `Memory: ${this.formatBytes(info.free_memory || 0)} free`;
                    const wifiText = info.wifi_connected ? `WiFi: ${info.wifi_ssid || 'Connected'}` : 'WiFi: Disconnected';
                    document.getElementById('systemStats').textContent = `${memoryText} | ${wifiText}`;
                    
                } catch (error) {
                    console.error('Error updating system info:', error);
                }
            }
            
            formatBytes(bytes) {
                bytes = Number(bytes);
                if (isNaN(bytes) || bytes <= 0) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
            }
            
            async restartSystem() {
                if (!confirm('Are you sure you want to restart the system? Unsaved changes will be lost.')) {
                    return;
                }
                
                try {
                    this.updateStatus('Restarting system...');
                    await fetch('/api/system/restart', { method: 'POST' });
                    
                    // Show restart message
                    document.body.innerHTML = `
                        <div style="display: flex; justify-content: center; align-items: center; height: 100vh; background: #1e1e1e; color: #d4d4d4; font-family: sans-serif;">
                            <div style="text-align: center;">
                                <div class="loading" style="margin: 0 auto 20px; width: 40px; height: 40px; border-width: 4px;"></div>
                                <h2>System Restarting...</h2>
                                <p>Please wait while the system restarts.</p>
                                <p>This page will automatically reload when the system is ready.</p>
                            </div>
                        </div>
                    `;
                    
                    // Try to reconnect after restart
                    setTimeout(() => {
                        const checkRestart = setInterval(() => {
                            fetch('/api/system/info')
                                .then(() => {
                                    clearInterval(checkRestart);
                                    window.location.reload();
                                })
                                .catch(() => {
                                    // System still restarting
                                });
                        }, 2000);
                    }, 5000);
                    
                } catch (error) {
                    console.error('Error restarting system:', error);
                    this.updateStatus('Error restarting system', true);
                }
            }
            
            updateStatus(message, isError = false) {
                const statusText = document.getElementById('statusText');
                statusText.textContent = message;
                statusText.style.color = isError ? '#f14c4c' : '#d4d4d4';
                
                // Clear status after 3 seconds
                if (!isError) {
                    setTimeout(() => {
                        if (statusText.textContent === message) {
                            statusText.textContent = 'Ready';
                            statusText.style.color = '#d4d4d4';
                        }
                    }, 3000);
                }
            }
        }
        
        // Initialize IDE when page loads
        let ide;
        document.addEventListener('DOMContentLoaded', () => {
            ide = new PropellantIDE();
        });
        
        // Prevent accidental page reload with unsaved changes
        window.addEventListener('beforeunload', (e) => {
            if (ide && ide.unsavedChanges) {
                e.preventDefault();
                e.returnValue = '';
            }
        });
    </script>
</body>
</html>'''

    def run(self):
        """Main run loop"""
        print("Starting Propellant IDE...")
        
        # Setup WiFi
        self.setup_wifi()
        
        # Start web server
        if not self.start_server():
            print("Failed to start server")
            return
        
        # Main server loop
        try:
            while self.server_running:
                try:
                    self.server.poll()
                    
                    # Periodic cleanup
                    gc.collect()
                    
                except Exception as e:
                    print(f"Server error: {e}")
                    time.sleep(0.1)
                    
        except KeyboardInterrupt:
            print("Server stopped by user")
        except Exception as e:
            print(f"Server crashed: {e}")
        finally:
            self.server_running = False
            print("Propellant IDE stopped")

# Main execution
def main():
    """Main entry point"""
    try:
        ide = PropellantIDE()
        ide.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        # Try to restart after a delay
        time.sleep(5)
        microcontroller.reset()

if __name__ == "__main__":
    main()


